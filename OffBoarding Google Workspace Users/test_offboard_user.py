#!/usr/bin/env python3
"""
Offline unit tests for offboard_user.py.

Stdlib only (unittest + unittest.mock). All GAM/GYB/subprocess calls are
stubbed — these tests never touch a Google Workspace tenant, so they are
safe to run anywhere, any time. Run them before AND after every change to
offboard_user.py:

    python3 test_offboard_user.py -v

History: written red-first against v4.7.0 during the 2026-07-13 dev-tenant
test round (each bug-encoding test failed on 4.7.0, proving the bug), and
green as of v5.0.0. Several tests pin behaviour that was discovered by
running against a live tenant (alias-transfer propagation race, lying
suspension updates, popimap on mailbox-less users) — do not weaken them
without re-testing live.
"""

import builtins
import contextlib
import importlib.util
import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).parent / "offboard_user.py"

# Import offboard_user.py as a module despite spaces in the folder path.
_spec = importlib.util.spec_from_file_location("offboard_user", SCRIPT_PATH)
offb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(offb)

# Real `gam info user ... quick` output captured from a live GAM7 tenant 2026-07-13
# (2026-07-13, GAM 7.43.04). Used by the A8 fixture tests.
FIXTURE_ACTIVE_USER = """User: testoffboard1@yourdomain.com
  Settings:
    First Name: Alice
    Last Name: Standard
    Full Name: Alice Standard
    Is a Super Admin: False
    Is Delegated Admin: False
    2-step enrolled: False
    2-step enforced: False
    Account Suspended: False
    Included in GAL: False
    Last login time: 2026-05-13T14:58:25Z
    Google Org Unit Path: /Offboarding
"""

FIXTURE_SUSPENDED_USER = """User: testoffboard3@yourdomain.com
  Settings:
    First Name: Charlie
    Last Name: Suspended
    Full Name: Charlie Suspended
    Is a Super Admin: False
    Is Delegated Admin: False
    2-step enrolled: False
    2-step enforced: False
    Account Suspended: True
    Suspension Reason: ADMIN
    Last login time: Never
    Google Org Unit Path: /Offboarding
"""


class OffboardTestCase(unittest.TestCase):
    """Common reset of the module's global summary state."""

    def setUp(self):
        offb.logger = logging.getLogger("offboard-test")
        offb.logger.addHandler(logging.NullHandler())
        offb.logger.propagate = False
        del offb.summary_actions[:]
        del offb.summary_skipped[:]
        del offb.summary_errors[:]
        del offb.summary_warnings[:]
        offb.exit_code = 0
        offb.shutdown_requested = False

    def actions(self):
        return "\n".join(offb.summary_actions)


###############################################################################
# A1 — Summary honesty: a failed command must not be reported as an action
###############################################################################

class TestA1SummaryHonesty(OffboardTestCase):

    def test_a1_1_suspend_failure_not_reported_as_action(self):
        with mock.patch.object(offb, "run_gam", return_value=(False, "err")):
            offb.suspend_user("leaver@yourdomain.com", dry_run=False)
        self.assertNotIn("suspended", self.actions().lower(),
                         "failed suspension must not appear in Actions")

    def test_a1_1b_suspend_success_reported(self):
        def fake(args, **kwargs):
            if "info" in args:
                return True, "    Account Suspended: True"
            return True, ""

        with mock.patch.object(offb, "run_gam", side_effect=fake):
            offb.suspend_user("leaver@yourdomain.com", dry_run=False)
        self.assertIn("suspended", self.actions().lower())

    def test_a11_1_suspend_readback_catches_lying_update(self):
        # Finding 10 (live-found): 'Updated' can report success while the
        # account state does not change. The read-back must catch it.
        def fake(args, **kwargs):
            if "info" in args:
                return True, "    Account Suspended: False"
            return True, ""

        clock = _FakeClock()
        with mock.patch.object(offb, "run_gam", side_effect=fake), \
             mock.patch("time.time", clock.time), \
             mock.patch("time.sleep", clock.sleep):
            offb.suspend_user("leaver@yourdomain.com", dry_run=False)
        self.assertNotIn("suspended (verified", self.actions().lower())
        self.assertTrue(any("NOT verified" in e for e in offb.summary_errors),
                        "a lying suspend update must be a loud error")

    def test_a11_2_slow_flip_after_the_kill_switch_is_still_caught(self):
        # Measured on dev 2026-08-31: a suspension reads back in 4-5s on a
        # quiet account but took 54s straight after the kill switch's burst of
        # directory writes. The old window was ~18s, so every scorched-earth
        # run raised CRITICAL and exited 1 on an account that did suspend.
        # Reads stay False until 40s have passed, then flip.
        clock = _FakeClock()
        start = clock.now

        def fake(args, **kwargs):
            if "info" in args:
                elapsed = clock.now - start
                return True, ("    Account Suspended: True" if elapsed > 40
                              else "    Account Suspended: False")
            return True, ""

        with mock.patch.object(offb, "run_gam", side_effect=fake), \
             mock.patch("time.time", clock.time), \
             mock.patch("time.sleep", clock.sleep):
            offb.suspend_user("leaver@yourdomain.com", dry_run=False)
        self.assertIn("verified by read-back", self.actions().lower())
        self.assertFalse(offb.summary_errors)

    def test_a1_2_delete_failure_not_reported_as_deleted(self):
        with mock.patch.object(offb, "run_gam", return_value=(False, "err")):
            offb.delete_user("leaver@yourdomain.com", dry_run=False)
        self.assertNotIn("USER DELETED", self.actions(),
                         "failed deletion must not claim USER DELETED")

    def test_a1_2b_delete_success_reported(self):
        with mock.patch.object(offb, "run_gam", return_value=(True, "")):
            offb.delete_user("leaver@yourdomain.com", dry_run=False)
        self.assertIn("USER DELETED", self.actions())

    def test_a1_3_kill_switch_failures_not_reported_as_actions(self):
        with mock.patch.object(offb, "run_gam", return_value=(False, "err")):
            offb.execute_kill_switch("leaver@yourdomain.com", dry_run=False,
                                     is_suspended=False, is_2sv_enrolled=True)
        acts = self.actions()
        for claim in ("Wiped recovery email", "Forced sign-out",
                      "Password scrambled", "Hidden from GAL"):
            self.assertNotIn(claim, acts,
                             f"failed step must not claim: {claim!r}")

    def test_a1_3b_kill_switch_successes_reported(self):
        with mock.patch.object(offb, "run_gam", return_value=(True, "")):
            offb.execute_kill_switch("leaver@yourdomain.com", dry_run=False,
                                     is_suspended=False, is_2sv_enrolled=True)
        acts = self.actions()
        for claim in ("Wiped recovery email", "Forced sign-out",
                      "Password scrambled", "Hidden from GAL"):
            self.assertIn(claim, acts)

    def test_a1_4_calendar_failure_not_reported_as_action(self):
        with mock.patch.object(offb, "validate_destination", return_value=True), \
             mock.patch.object(offb, "run_gam", return_value=(False, "err")):
            offb.transfer_calendar("leaver@yourdomain.com",
                                   "dest@yourdomain.com", dry_run=False)
        self.assertNotIn("Calendar editor access", self.actions())

    def test_a1_4b_auto_reply_failure_not_reported_as_action(self):
        with mock.patch.object(offb, "run_gam", return_value=(False, "err")):
            offb.set_auto_reply("leaver@yourdomain.com", dry_run=False)
        self.assertNotIn("Auto-reply message configured", self.actions())


###############################################################################
# A2 — Forwarding verification must match the target address's own status line
###############################################################################

class _FakeClock:
    """Deterministic time.time()/time.sleep() so the 60s poll loop is instant."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        self.now += 5.0
        return self.now

    def sleep(self, secs):
        self.now += secs


class TestA2ForwardingVerification(OffboardTestCase):

    def _run_setup_forwarding(self, status_output, forward_to):
        """Drive setup_forwarding with stubbed run_gam; return activation flag."""
        activated = {"yes": False}

        def fake_run_gam(args, **kwargs):
            if "forwardingaddress" in args:            # step 1: register
                return True, ""
            if "forwardingaddresses" in args:          # poll: status
                return True, status_output
            if "forward" in args and "on" in args:     # step 3: activate
                activated["yes"] = True
                return True, ""
            return True, ""

        clock = _FakeClock()
        with mock.patch.object(offb, "validate_destination", return_value=True), \
             mock.patch.object(offb, "run_gam", side_effect=fake_run_gam), \
             mock.patch("time.time", clock.time), \
             mock.patch("time.sleep", clock.sleep):
            offb.setup_forwarding("leaver@yourdomain.com", forward_to,
                                  dry_run=False)
        return activated["yes"]

    def test_a2_1_other_accepted_address_must_not_verify_pending_target(self):
        status = ("forwardingEmail,verificationStatus\n"
                  "already-there@yourdomain.com,accepted\n"
                  "testoffboard.ops@yourdomain.com,pending\n")
        activated = self._run_setup_forwarding(
            status, "testoffboard.ops@yourdomain.com")
        self.assertFalse(
            activated,
            "target is pending; 'accepted' on a DIFFERENT address must not "
            "trigger activation")

    def test_a2_2_target_accepted_verifies(self):
        status = ("forwardingEmail,verificationStatus\n"
                  "testoffboard.ops@yourdomain.com,accepted\n")
        activated = self._run_setup_forwarding(
            status, "testoffboard.ops@yourdomain.com")
        self.assertTrue(activated)

    def test_a2_3_poll_failures_do_not_spam_summary_errors(self):
        poll_calls = []

        def fake_run_gam(args, **kwargs):
            if "forwardingaddress" in args:
                return True, ""
            if "forwardingaddresses" in args:
                poll_calls.append(kwargs)
                return False, "transient API error"
            return True, ""

        clock = _FakeClock()
        with mock.patch.object(offb, "validate_destination", return_value=True), \
             mock.patch.object(offb, "run_gam", side_effect=fake_run_gam), \
             mock.patch("time.time", clock.time), \
             mock.patch("time.sleep", clock.sleep):
            offb.setup_forwarding("leaver@yourdomain.com",
                                  "testoffboard.ops@yourdomain.com",
                                  dry_run=False)
        self.assertTrue(poll_calls, "poll loop never ran")
        for kwargs in poll_calls:
            self.assertTrue(
                kwargs.get("suppress_summary_error"),
                "poll attempts must pass suppress_summary_error=True so one "
                "transient failure doesn't add an error line per attempt")


###############################################################################
# A3 — Clean exit (no traceback) when stdin is closed before logging exists
###############################################################################

class TestA3PreLoggerCrash(unittest.TestCase):

    def test_a3_1_eof_on_user_prompt_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH)],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                cwd=tmp, timeout=60,
            )
        self.assertNotIn("Traceback", result.stderr,
                         f"crash instead of clean exit:\n{result.stderr}")
        self.assertEqual(result.returncode, 2,
                         "EOF at the user prompt should exit 2")


###############################################################################
# A4 — --force must not imply --unsuspend (documented contract:
# command builder: "Without this flag the script will abort early if the
# account is already suspended.")
###############################################################################

class TestA4ForceUnsuspend(OffboardTestCase):

    def test_a4_1_force_without_unsuspend_flag_does_not_unsuspend(self):
        # v4.8.0 extracts the decision into decide_unsuspend(); on v4.7.0
        # this attribute is missing and the test fails (red), which is the
        # bug being encoded: --force blanket-yes silently unsuspends.
        self.assertTrue(hasattr(offb, "decide_unsuspend"),
                        "decide_unsuspend() missing: --force still "
                        "auto-answers the unsuspend prompt with yes")
        self.assertFalse(offb.decide_unsuspend(force=True, unsuspend_flag=False,
                                               prompt_fn=lambda: True))
        self.assertTrue(offb.decide_unsuspend(force=True, unsuspend_flag=True,
                                              prompt_fn=lambda: False))

    def test_a4_2_interactive_prompt_still_asked_without_force(self):
        if not hasattr(offb, "decide_unsuspend"):
            self.skipTest("decide_unsuspend not present on this version")
        asked = {"yes": False}

        def prompt():
            asked["yes"] = True
            return True

        self.assertTrue(offb.decide_unsuspend(force=False, unsuspend_flag=False,
                                              prompt_fn=prompt))
        self.assertTrue(asked["yes"])


###############################################################################
# A5 — Licence labels must not be built by whitespace-splitting display names
###############################################################################

class TestA5LicenceLabels(OffboardTestCase):

    CACHED = ("primaryEmail,LicensesCount,Licenses,LicensesDisplay\n"
              "leaver@yourdomain.com,1,1010010001,Cloud Identity\n")

    def test_a5_1_multiword_display_name_stays_intact(self):
        deleted = []

        def fake_run_gam(args, **kwargs):
            if "delete" in args and "license" in args:
                deleted.append(args[-1])
            return True, ""

        with mock.patch.object(offb, "run_gam", side_effect=fake_run_gam):
            offb.remove_licences("leaver@yourdomain.com", dry_run=False,
                                 cached_output=self.CACHED)
        self.assertEqual(deleted, ["1010010001"])
        acts = self.actions()
        self.assertIn("Cloud Identity", acts,
                      "full display name must survive; whitespace-splitting "
                      "produces the truncated label 'Cloud (1010010001)'")

    def test_a5_2_multiple_licences_fall_back_to_sku_ids(self):
        cached = ("primaryEmail,LicensesCount,Licenses,LicensesDisplay\n"
                  "leaver@yourdomain.com,2,1010010001 1010020028,"
                  "Cloud Identity Google Workspace Enterprise Plus\n")
        with mock.patch.object(offb, "run_gam", return_value=(True, "")):
            offb.remove_licences("leaver@yourdomain.com", dry_run=False,
                                 cached_output=cached)
        acts = self.actions()
        # Alignment is impossible for >1 licence (space-joined multi-word
        # names); labels must not be misassembled from split fragments.
        self.assertNotIn("Cloud (", acts)
        self.assertNotIn("Identity (", acts)
        self.assertIn("1010010001", acts)
        self.assertIn("1010020028", acts)


###############################################################################
# A6 — Dry run must leave no directories behind
###############################################################################

class TestA6DryRunPurity(OffboardTestCase):

    def test_a6_1_dry_run_creates_no_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup_root = Path(tmp) / "offboarding_backups"
            with mock.patch.object(offb, "BACKUP_DIRECTORY", backup_root), \
                 mock.patch.object(offb, "validate_destination",
                                   return_value=True), \
                 mock.patch.object(offb, "run_gyb", return_value=(True, "")), \
                 mock.patch.object(offb, "run_gam", return_value=(True, "")):
                offb.migrate_email("leaver@yourdomain.com",
                                   "dest@yourdomain.com", dry_run=True)
                offb.backup_email_only("leaver@yourdomain.com", dry_run=True)
                offb.backup_drive_rclone("leaver@yourdomain.com", dry_run=True)
            self.assertFalse(
                backup_root.exists(),
                f"dry run created directories under {backup_root}")


###############################################################################
# A7 — Version consistency: header and snapshot must track SCRIPT_VERSION
###############################################################################

class TestA7VersionConsistency(unittest.TestCase):

    def test_a7_1_header_version_matches_script_version(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        import re
        m = re.search(r"^Version:\s+(\S+)", source, re.MULTILINE)
        self.assertIsNotNone(m, "no 'Version:' line in the header")
        self.assertEqual(m.group(1), offb.SCRIPT_VERSION,
                         "header Version: line has drifted from SCRIPT_VERSION")

    def test_a7_3_version_file_matches_script_version(self):
        # The VERSION file is what check_for_updates compares against, so a
        # drift here tells every user they are behind (or up to date) wrongly.
        # tenant_scope.py drifted across three places for six months the same way.
        version_file = SCRIPT_PATH.parent / "VERSION"
        self.assertEqual(version_file.read_text(encoding="utf-8").strip(),
                         offb.SCRIPT_VERSION,
                         "VERSION file has drifted from SCRIPT_VERSION")

    def test_a7_2_snapshot_embeds_script_version(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"script_version": "4.3"', source,
                         "snapshot hardcodes an old version; use SCRIPT_VERSION")


###############################################################################
# A8 — verify_user parsing against real captured GAM7 output (finding 5:
# cleared on dev 2026-07-13; these tests pin the contract)
###############################################################################

class TestA12Turnoff2svVerifyFirst(OffboardTestCase):
    """Finding 11 (live-found): step 5 must verify 2SV state instead of
    blindly re-firing turnoff2sv after deprovision already turned it off."""

    def _run_step5(self, enrolled_readback, turnoff_result=(True, "")):
        fired = {"turnoff2sv": 0}

        def fake(args, **kwargs):
            if "turnoff2sv" in args and "deprovision" not in args:
                fired["turnoff2sv"] += 1
                return turnoff_result
            if "info" in args:
                state = "True" if enrolled_readback else "False"
                return True, f"    2-step enrolled: {state}"
            return True, ""

        with mock.patch.object(offb, "run_gam", side_effect=fake):
            offb.execute_kill_switch("u@yourdomain.com", dry_run=False,
                                     is_suspended=False, is_2sv_enrolled=True,
                                     has_mailbox=True)
        return fired["turnoff2sv"]

    def test_a12_1_already_off_after_deprovision_no_refire(self):
        fired = self._run_step5(enrolled_readback=False)
        self.assertEqual(fired, 0, "turnoff2sv must not re-fire when 2SV "
                                   "already reads off")
        self.assertIn("2SV off (verified by read-back)", self.actions())
        self.assertFalse(offb.summary_errors)

    def test_a12_2_still_enrolled_fires_turnoff(self):
        fired = self._run_step5(enrolled_readback=True)
        self.assertEqual(fired, 1)
        self.assertIn("Turned off 2SV", self.actions())

    def test_a12_3_turnoff_fails_and_still_enrolled_is_error(self):
        self._run_step5(enrolled_readback=True, turnoff_result=(False, "boom"))
        self.assertTrue(any("turnoff2sv failed" in e
                            for e in offb.summary_errors))


class TestA10DeprovisionPopimap(OffboardTestCase):
    """Finding 9 (live-found): popimap must be omitted for mailbox-less users."""

    def _deprov_args(self, has_mailbox):
        seen = {}

        def fake(args, **kwargs):
            if "deprovision" in args:
                seen["args"] = args
            return True, ""

        with mock.patch.object(offb, "run_gam", side_effect=fake):
            offb.execute_kill_switch("u@yourdomain.com", dry_run=False,
                                     is_suspended=False, is_2sv_enrolled=False,
                                     has_mailbox=has_mailbox)
        return seen["args"]

    def test_a10_1_no_mailbox_drops_popimap(self):
        self.assertNotIn("popimap", self._deprov_args(has_mailbox=False))

    def test_a10_2_mailbox_keeps_popimap(self):
        self.assertIn("popimap", self._deprov_args(has_mailbox=True))


class TestA9AliasTransfer(OffboardTestCase):
    """Finding 8 (live-found): alias transfer must survive the Duplicate
    propagation race and never report success for a lost alias."""

    ALIAS_CSV = "Alias,Target,TargetType\nevan.legacy@yourdomain.com,testoffboard5@yourdomain.com,user\n"

    def _fake_gam(self, create_results):
        """run_gam stub: list -> ALIAS_CSV, delete -> ok, create -> scripted."""
        calls = {"creates": 0}

        def fake(args, **kwargs):
            if "print" in args and "aliases" in args:
                return True, self.ALIAS_CSV
            if args[0] == "delete" and args[1] == "alias":
                return True, ""
            if args[0] == "create" and args[1] == "alias":
                result = create_results[min(calls["creates"],
                                            len(create_results) - 1)]
                calls["creates"] += 1
                return result
            return True, ""

        return fake, calls

    def _clocked(self, fake):
        clock = _FakeClock()
        return mock.patch.object(offb, "validate_destination", return_value=True), \
               mock.patch.object(offb, "run_gam", side_effect=fake), \
               mock.patch("time.time", clock.time), \
               mock.patch("time.sleep", clock.sleep)

    def test_a9_1_duplicate_then_success_retries_and_reports_success(self):
        fake, calls = self._fake_gam([(False, "Update Failed: Duplicate"),
                                      (True, "Created")])
        p1, p2, p3, p4 = self._clocked(fake)
        with p1, p2, p3, p4:
            offb.transfer_aliases("testoffboard5@yourdomain.com",
                                  "testoffboard.dest@yourdomain.com",
                                  dry_run=False)
        self.assertGreaterEqual(calls["creates"], 2, "create was not retried")
        self.assertIn("evan.legacy@yourdomain.com", self.actions())
        self.assertFalse(offb.summary_errors)

    def test_a9_2_permanent_create_failure_is_an_error_not_success(self):
        fake, _ = self._fake_gam([(False, "Update Failed: Duplicate")])
        p1, p2, p3, p4 = self._clocked(fake)
        with p1, p2, p3, p4:
            offb.transfer_aliases("testoffboard5@yourdomain.com",
                                  "testoffboard.dest@yourdomain.com",
                                  dry_run=False)
        self.assertNotIn("evan.legacy", self.actions(),
                         "lost alias must not be reported as transferred")
        self.assertTrue(any("evan.legacy" in e for e in offb.summary_errors),
                        "lost alias must be a loud error")

    def test_a9_3_no_shell_pipe_used(self):
        import inspect
        func_src = inspect.getsource(offb.transfer_aliases)
        self.assertNotIn("run_shell_pipe", func_src,
                         "the csv-pipe update-alias pattern must stay gone")


class TestA8VerifyUserFixtures(OffboardTestCase):

    def test_a8_1_active_user_parsed(self):
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, FIXTURE_ACTIVE_USER)):
            info = offb.verify_user("testoffboard1@yourdomain.com")
        self.assertEqual(info["_is_suspended"], "False")
        self.assertEqual(info["_is_admin"], "False")
        self.assertEqual(info.get("2-step enrolled", "").lower(), "false")
        self.assertEqual(info.get("full name"), "Alice Standard")

    def test_a8_2_suspended_user_parsed(self):
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, FIXTURE_SUSPENDED_USER)):
            info = offb.verify_user("testoffboard3@yourdomain.com")
        self.assertEqual(info["_is_suspended"], "True")
        self.assertTrue(any("already suspended" in w.lower()
                            for w in offb.summary_warnings))


class TestB18AdminAccountGate(OffboardTestCase):

    ADMIN = {"_is_admin": "True"}
    USER = {"_is_admin": "False"}

    def test_b18_1_admin_is_blocked_by_default(self):
        with self.assertRaises(offb.AdminAccountSafetyError):
            offb.enforce_admin_account_gate(
                "admin@yourdomain.com", self.ADMIN,
                allow_admin_account=False)

    def test_b18_2_force_does_not_implicitly_bypass_gate(self):
        import inspect
        parameters = inspect.signature(
            offb.enforce_admin_account_gate).parameters
        self.assertNotIn("force", parameters)

    def test_b18_3_dedicated_override_allows_admin(self):
        offb.enforce_admin_account_gate(
            "admin@yourdomain.com", self.ADMIN,
            allow_admin_account=True)
        self.assertTrue(any("OVERRIDDEN" in w for w in offb.summary_warnings))

    def test_b18_4_normal_user_passes_quietly(self):
        with mock.patch.object(offb, "print_error") as printed:
            offb.enforce_admin_account_gate(
                "user@yourdomain.com", self.USER,
                allow_admin_account=False)
        printed.assert_not_called()
        self.assertFalse(offb.summary_warnings)

    def test_b18_5_remediation_uses_role_assignment_id(self):
        printed = []
        with mock.patch.object(offb, "print_error", printed.append):
            with self.assertRaises(offb.AdminAccountSafetyError):
                offb.enforce_admin_account_gate(
                    "admin@yourdomain.com", self.ADMIN,
                    allow_admin_account=False)
        output = "\n".join(printed)
        self.assertIn("gam print admins user admin@yourdomain.com", output)
        self.assertIn("gam delete admin <roleAssignmentId>", output)

    def test_b18_6_gate_runs_immediately_after_verification(self):
        import inspect
        src = inspect.getsource(offb.main)
        self.assertLess(src.index("enforce_admin_account_gate("),
                        src.index("preflight_destinations("))
        self.assertLess(src.index("enforce_admin_account_gate("),
                        src.index("execute_kill_switch("))

    def test_b18_7_override_is_explicit_cli_flag(self):
        import inspect
        self.assertIn('"--allow-admin-account"',
                      inspect.getsource(offb.parse_args))


class TestB1BatchLadder(unittest.TestCase):
    """
    The restore batch-size fallback used when Gmail throttles a run.

    Written against the behaviour agreed with the operator: 100 -> 75 -> 50,
    never stepping above the starting value and never below 10 unless the
    operator explicitly asked for less. The floor matters: at --batch-size 1
    GYB takes its single-message path, which never commits the resume DB inside
    the loop, so a crash at 99% restarts from message 1.
    """

    def test_b1_1_hundred_steps_as_specified(self):
        self.assertEqual(offb._build_batch_ladder(100), [100, 75, 50, 25, 10])

    def test_b1_2_never_steps_above_start_and_always_descends(self):
        for start in (500, 100, 50, 20, 10, 7, 1):
            ladder = offb._build_batch_ladder(start)
            self.assertEqual(ladder[0], start)
            self.assertEqual(ladder, sorted(ladder, reverse=True))
            self.assertEqual(len(ladder), len(set(ladder)))
            self.assertTrue(all(b <= start for b in ladder))

    def test_b1_3_floor_is_ten_unless_operator_asked_for_less(self):
        self.assertEqual(min(offb._build_batch_ladder(100)), 10)
        # An explicit small choice is honoured rather than raised to the floor.
        self.assertEqual(offb._build_batch_ladder(3), [3])


class TestB2RateLimitDetection(unittest.TestCase):
    """Only throttling-shaped failures should drag the batch size down."""

    def test_b2_1_throttling_markers_detected(self):
        for marker in ("rateLimitExceeded", "userRateLimitExceeded",
                       "quotaExceeded", "backendError", "Backing off 16 seconds"):
            self.assertTrue(offb._looks_rate_limited(f"blah {marker} blah"), marker)

    def test_b2_2_av_crash_is_not_treated_as_throttling(self):
        crash = ("Traceback (most recent call last):\n"
                 "PermissionError: [Errno 1] Operation not permitted: '/b/a.eml'")
        self.assertFalse(offb._looks_rate_limited(crash))


class TestB3QuarantineFromCrash(unittest.TestCase):
    """Quarantining the .eml named in a GYB crash, and only if still locked."""

    @staticmethod
    @contextlib.contextmanager
    def _unreadable(path):
        """Make ONE file raise PermissionError on open, on any OS.

        chmod(0o000) does not remove read access on Windows — os.chmod there
        only toggles the read-only bit — so the AV-lock simulation silently did
        nothing, the poison file read fine, and both tests failed on Windows 11
        (2026-07-29) while passing on macOS. Patch the read itself, which is
        what an AV lock actually does to us.
        """
        real_open = builtins.open

        def fake_open(file, *args, **kwargs):
            try:
                same = Path(file) == Path(path)
            except TypeError:
                same = False
            if same:
                raise PermissionError(13, "Permission denied")
            return real_open(file, *args, **kwargs)

        with mock.patch("builtins.open", fake_open):
            yield

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backup = Path(self.tmp.name) / "user@x.com_20260101"
        (self.backup / "2026" / "1").mkdir(parents=True)
        self.locked = self.backup / "2026" / "1" / "deadbeef.eml"
        self.locked.write_bytes(b"poison")
        self.readable = self.backup / "2026" / "1" / "cafe1234.eml"
        self.readable.write_bytes(b"fine")
        offb.summary_warnings.clear()

    def tearDown(self):
        # Make every 000-mode file readable again wherever it ended up, so the
        # temp dir can be removed. The poison file is expected to have MOVED in
        # the passing case, so its original path may legitimately be gone.
        for p in Path(self.tmp.name).rglob("*.eml"):
            try:
                p.chmod(0o644)
            except OSError:
                pass
        self.tmp.cleanup()

    def _crash(self, path):
        return ("Traceback (most recent call last):\n"
                f"PermissionError: [Errno 1] Operation not permitted: '{path}'")

    def test_b3_1_locked_file_named_in_crash_is_moved_aside(self):
        with self._unreadable(self.locked):
            moved = offb.quarantine_gyb_locked_file(
                self.backup, self._crash(self.locked))
        self.assertEqual(moved, ["deadbeef"])
        self.assertFalse(self.locked.exists(), "poison file should have been moved")
        quarantined = (self.backup.parent / f"{self.backup.name}_quarantined"
                       / "2026" / "1" / "deadbeef.eml")
        self.assertTrue(quarantined.exists(), "file must be moved, never deleted")

    def test_b3_2_file_readable_again_is_left_in_place(self):
        # Transient AV block: it killed the run but reads fine now. Moving it
        # would drop a legitimate message from the successor's mailbox.
        moved = offb.quarantine_gyb_locked_file(self.backup, self._crash(self.readable))
        self.assertEqual(moved, [])
        self.assertTrue(self.readable.exists())

    def test_b3_3_patched_gyb_warning_wording_also_parsed(self):
        out = (f"WARNING! could not read {self.locked} for message 60818: "
               f"[Errno 13] Permission denied")
        with self._unreadable(self.locked):
            self.assertEqual(offb.quarantine_gyb_locked_file(self.backup, out),
                             ["deadbeef"])

    def test_b3_4_path_outside_the_backup_is_ignored(self):
        outside = Path(self.tmp.name) / "elsewhere.eml"
        outside.write_bytes(b"x")
        outside.chmod(0o000)
        try:
            self.assertEqual(
                offb.quarantine_gyb_locked_file(self.backup, self._crash(outside)), [])
            self.assertTrue(outside.exists())
        finally:
            outside.chmod(0o644)

    def test_b3_5_unparseable_output_never_raises(self):
        self.assertEqual(offb.quarantine_gyb_locked_file(self.backup, "no paths here"), [])


class TestB4UndatedMessages(unittest.TestCase):
    """Counting epoch-dated messages; warn-only, so it must never raise."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backup = Path(self.tmp.name) / "b"
        self.backup.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _db(self, dates):
        import sqlite3
        with offb._gyb_db(self.backup / "msg-db.sqlite") as db:
            db.execute("CREATE TABLE messages(message_num INTEGER PRIMARY KEY, "
                       "message_filename TEXT, message_internaldate TIMESTAMP)")
            db.executemany("INSERT INTO messages VALUES (?,?,?)",
                           [(i, f"{i}.eml", d) for i, d in enumerate(dates, 1)])

    def test_b4_1_counts_epoch_dated_messages(self):
        self._db(["1970-01-01 02:00:00", "2026-07-21 17:18:09",
                  "1970-01-01 02:00:00"])
        self.assertEqual(offb.count_undated_messages(self.backup), 2)

    def test_b4_2_healthy_backup_counts_zero(self):
        self._db(["2024-01-01 00:00:00", "2026-07-21 17:18:09"])
        self.assertEqual(offb.count_undated_messages(self.backup), 0)

    def test_b4_3_missing_db_returns_zero_not_an_exception(self):
        self.assertEqual(offb.count_undated_messages(self.backup / "nope"), 0)


class TestB5SuspendedDestination(unittest.TestCase):
    """Rejecting a suspended destination, matching the field not the word."""

    def setUp(self):
        offb.summary_errors.clear()

    def test_b5_1_suspended_destination_rejected(self):
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, FIXTURE_SUSPENDED_USER)):
            self.assertFalse(offb.validate_destination("testoffboard3@yourdomain.com"))

    def test_b5_2_active_user_named_suspended_is_not_a_false_positive(self):
        # "Last Name: Suspended" / "Full Name: Charlie Suspended" must not trip it.
        active_but_named_suspended = FIXTURE_SUSPENDED_USER.replace(
            "Account Suspended: True", "Account Suspended: False")
        self.assertIn("Last Name: Suspended", active_but_named_suspended)
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, active_but_named_suspended)):
            self.assertTrue(offb.validate_destination("testoffboard3@yourdomain.com"))


class TestB6BackupCompleteness(unittest.TestCase):
    """Backup DB row count must match the .eml files actually on disk.

    Since the issue-#11-shaped fix, a shortfall is CLASSIFIED: messages in
    the sibling _quarantined/ folder are deliberate exclusions, and only a
    shortfall beyond those is an error (which holds licence removal via
    record_failure at the call sites).
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.b = Path(self.tmp.name) / "bk"
        (self.b / "2026" / "1").mkdir(parents=True)
        offb.summary_warnings.clear()
        offb.summary_errors.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def _make(self, rows, files, quarantined=0):
        import sqlite3
        with offb._gyb_db(self.b / "msg-db.sqlite") as db:
            db.execute("CREATE TABLE messages(message_num INTEGER PRIMARY KEY, "
                       "message_filename TEXT, message_internaldate TIMESTAMP)")
            db.executemany("INSERT INTO messages VALUES (?,?,?)",
                           [(i, f"2026/1/{i}.eml", "2026-01-01") for i in range(1, rows + 1)])
        for i in range(1, files + 1):
            (self.b / "2026" / "1" / f"{i}.eml").write_bytes(b"x")
        if quarantined:
            qdir = self.b.parent / f"{self.b.name}_quarantined"
            qdir.mkdir()
            for i in range(quarantined):
                (qdir / f"q{i}.eml").write_bytes(b"x")

    def test_b6_1_matching_backup_passes_quietly(self):
        self._make(5, 5)
        self.assertEqual(offb.verify_backup_complete(self.b), (5, 5))
        self.assertFalse(offb.summary_warnings)
        self.assertFalse(offb.summary_errors)

    def test_b6_2_genuine_shortfall_is_an_error_not_a_warning(self):
        # Nothing quarantined, so 2 messages are simply gone: an error, so
        # record_failure holds licence removal and the Gmail access a
        # re-download needs survives.
        self._make(5, 3)
        self.assertEqual(offb.verify_backup_complete(self.b), (5, 3))
        self.assertTrue(any("missing" in e for e in offb.summary_errors))

    def test_b6_3_missing_db_returns_zeroes(self):
        self.assertEqual(offb.verify_backup_complete(self.b / "nope"), (0, 0))

    def test_b6_4_quarantine_accounted_shortfall_is_clean(self):
        # All 2 missing files are in the sibling quarantine folder: that is
        # the tooling doing its job (malware never restored), not data loss.
        self._make(5, 3, quarantined=2)
        offb.verify_backup_complete(self.b)
        self.assertFalse(offb.summary_errors)
        self.assertFalse(offb.summary_warnings)

    def test_b6_5_shortfall_beyond_quarantine_still_errors(self):
        self._make(5, 2, quarantined=2)
        offb.verify_backup_complete(self.b)
        self.assertTrue(any("missing 1" in e for e in offb.summary_errors))

    def test_b6_6_extra_files_on_disk_warn_only(self):
        self._make(3, 5)
        offb.verify_backup_complete(self.b)
        self.assertFalse(offb.summary_errors)
        self.assertTrue(any("more .eml" in w for w in offb.summary_warnings))


# Real `gam user <u> show gmailprofile` output, dev.osh.co.za 2026-07-28.
FIXTURE_GMAIL_OFF = "User: nolic@yourdomain.com, Gmail Service/App not enabled\n"
FIXTURE_GMAIL_ON = ("User: ok@yourdomain.com, historyId: 50524, "
                    "messagesTotal: 3296, threadsTotal: 3180\n")


class TestB7GmailEnabled(unittest.TestCase):
    """Restore must refuse a destination with no Gmail service."""

    def setUp(self):
        offb.summary_errors.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.b = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_b7_1_gmail_disabled_blocks_the_restore(self):
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, FIXTURE_GMAIL_OFF)):
            self.assertFalse(
                offb.check_restore_destination_ready("nolic@yourdomain.com",
                                                     self.b, dry_run=False))
        self.assertTrue(any("Gmail not enabled" in e for e in offb.summary_errors))

    def test_b7_2_gmail_enabled_proceeds(self):
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, FIXTURE_GMAIL_ON)):
            self.assertTrue(
                offb.check_restore_destination_ready("ok@yourdomain.com",
                                                     self.b, dry_run=False))


FIXTURE_DRIVESETTINGS = """User: leaver@yourdomain.com, Show 1 Drive Settings
  name: A Leaver
  appInstalled: False
  limit: 329.85 TB
  maxUploadSize: 5.24 TB
  usage: 7.66 GB
  usageInDrive: 0 KB
  usageInDriveTrash: 0 KB
"""


class TestB8StorageSizeParsing(unittest.TestCase):
    """GAM prints human-formatted sizes; a digits-only read is off by ~10^12."""

    def test_b8_1_terabyte_limit_is_not_read_as_bytes(self):
        limit = offb._parse_gam_size(FIXTURE_DRIVESETTINGS, "limit")
        self.assertEqual(limit, int(329.85 * 1024 ** 4))

    def test_b8_2_gigabyte_usage_parsed(self):
        usage = offb._parse_gam_size(FIXTURE_DRIVESETTINGS, "usage")
        self.assertEqual(usage, int(7.66 * 1024 ** 3))

    def test_b8_3_usage_does_not_match_usageindrive(self):
        # usageInDrive is 0 KB and follows usage; anchoring must not pick it up.
        self.assertNotEqual(offb._parse_gam_size(FIXTURE_DRIVESETTINGS, "usage"), 0)

    def test_b8_4_headroom_is_positive_on_a_healthy_tenant(self):
        limit = offb._parse_gam_size(FIXTURE_DRIVESETTINGS, "limit")
        usage = offb._parse_gam_size(FIXTURE_DRIVESETTINGS, "usage")
        # The old digits-only regex gave 329 - 7 = 322 bytes, so every restore
        # over 322 bytes tripped the out-of-storage warning.
        self.assertGreater(limit - usage, 300 * 1024 ** 4)

    def test_b8_5_missing_or_unparseable_field_returns_none(self):
        self.assertIsNone(offb._parse_gam_size(FIXTURE_DRIVESETTINGS, "nosuch"))
        self.assertIsNone(offb._parse_gam_size("limit: banana", "limit"))


class TestB14ConsoleEncoding(unittest.TestCase):
    """Non-ASCII filenames must not kill, or vanish from, the console output.

    On Windows the console defaults to cp1252, so logging a name containing
    rclone's encoded newline (U+240A), CJK or an emoji raised UnicodeEncodeError
    inside the logging handler — which logging swallows, losing the very line
    that names a missing file. Windows 11 ARM64, 2026-07-29.
    """

    def test_b14_1_console_is_reconfigured_to_utf8(self):
        calls = []

        class FakeStream:
            def reconfigure(self, **kw):
                calls.append(kw)

        with mock.patch.object(offb.sys, "stdout", FakeStream()), \
             mock.patch.object(offb.sys, "stderr", FakeStream()):
            offb._force_utf8_console()
        self.assertEqual(len(calls), 2)
        for kw in calls:
            self.assertEqual(kw["encoding"], "utf-8")
            self.assertEqual(kw["errors"], "replace")

    def test_b14_2_a_stream_that_cannot_reconfigure_is_survivable(self):
        class Stubborn:
            def reconfigure(self, **kw):
                raise ValueError("underlying buffer detached")

        with mock.patch.object(offb.sys, "stdout", Stubborn()), \
             mock.patch.object(offb.sys, "stderr", Stubborn()):
            offb._force_utf8_console()   # must not raise


class TestB9DriveBackupReconciliation(unittest.TestCase):
    """rclone exits 0 even when same-name files overwrite each other on disk."""

    def setUp(self):
        offb.summary_warnings.clear()
        offb.summary_errors.clear()
        offb.exit_code = 0
        self.tmp = tempfile.TemporaryDirectory()
        self.b = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _filelist(n, forms=0):
        rows = [f"u,id{i},application/vnd.google-apps.document" for i in range(n - forms)]
        rows += [f"u,form{i},application/vnd.google-apps.form" for i in range(forms)]
        return "Owner,id,mimeType\n" + "\n".join(rows)

    def test_b9_1_short_backup_warns(self):
        (self.b / "one.docx").write_text("x")
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, self._filelist(3))):
            drive, local = offb.verify_drive_backup_complete("u@d.com", self.b)
        self.assertEqual((drive, local), (3, 1))
        # Was a summary_warning, which left exit_code 0 and let a wrapper
        # reading only the exit status delete the source account (issue #11).
        self.assertTrue(any("unaccounted for" in e for e in offb.summary_errors))
        self.assertEqual(offb.exit_code, 1)

    def test_b9_2_matching_backup_is_quiet(self):
        for name in ("a.docx", "b.docx"):
            (self.b / name).write_text("x")
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, self._filelist(2))):
            drive, local = offb.verify_drive_backup_complete("u@d.com", self.b)
        self.assertEqual((drive, local), (2, 2))
        self.assertFalse(offb.summary_warnings)

    def test_b9_3_nested_files_are_counted(self):
        sub = self.b / "Projects" / "2024"
        sub.mkdir(parents=True)
        (sub / "deep.docx").write_text("x")
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, self._filelist(1))):
            self.assertEqual(offb.verify_drive_backup_complete("u@d.com", self.b),
                             (1, 1))

    def test_b9_5_gam_progress_lines_do_not_inflate_the_count(self):
        # run_gam merges stderr into stdout; GAM writes two progress lines
        # there. Counting raw lines invented a 2-file shortfall on every run.
        out = ("Getting all Drive Files/Folders for u@d.com\n"
               "Got 2 Drive Files/Folders that matched query for u@d.com...\n"
               + self._filelist(2))
        for name in ("a.docx", "b.docx"):
            (self.b / name).write_text("x")
        with mock.patch.object(offb, "run_gam", return_value=(True, out)):
            self.assertEqual(offb.verify_drive_backup_complete("u@d.com", self.b),
                             (2, 2))
        self.assertFalse(offb.summary_warnings)

    def test_b9_6_paged_output_uses_the_last_running_total(self):
        # Captured live on dev 2026-07-29: GAM prints one "Got N" per page,
        # CARRIAGE-RETURN separated, N being the running total. Reading the
        # first gave 100 for a 256-file user, so a 106-file shortfall passed
        # as "matches Drive". The last one is the answer.
        out = (self._filelist(256) + "\n"
               "Getting all Drive Files/Folders for u@d.com\n"
               "Got 100 Drive Files/Folders for u@d.com...\r"
               "Got 200 Drive Files/Folders for u@d.com...\r"
               "Got 256 Drive Files/Folders for u@d.com...")
        for i in range(150):
            (self.b / f"f{i}.docx").write_text("x")
        with mock.patch.object(offb, "run_gam", return_value=(True, out)):
            drive, local = offb.verify_drive_backup_complete("u@d.com", self.b)
        self.assertEqual((drive, local), (256, 150))
        self.assertTrue(any("unaccounted for" in e for e in offb.summary_errors))
        self.assertEqual(offb.exit_code, 1)

    def test_b9_7_row_fallback_ignores_stray_progress_lines(self):
        # Fallback path (no "Got" line at all): stderr is appended AFTER the
        # CSV, so anything GAM writes there must not count as a file row.
        out = self._filelist(2) + "\nGetting all Drive Files/Folders for u@d.com"
        with mock.patch.object(offb, "run_gam", return_value=(True, out)):
            self.assertEqual(
                offb.verify_drive_backup_complete("u@d.com", self.b)[0], 2)

    def test_b9_8_rclone_named_duplicates_are_listed_not_guessed(self):
        # rclone prints "NOTICE: <path>: Duplicate object found in source -
        # ignoring" and still exits 0. Captured live on Windows 11 2026-07-29;
        # it is the exact list the count can otherwise only guess at.
        (self.b / "one.docx").write_text("x")
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, self._filelist(3))):
            offb.verify_drive_backup_complete(
                "u@d.com", self.b, ["folder/Notes.docx", "folder/Line one.docx"])
        joined = " ".join(offb.summary_errors)
        self.assertIn("folder/Notes.docx", joined)
        self.assertIn("folder/Line one.docx", joined)
        self.assertEqual(offb.exit_code, 1)

    def test_b9_9_forms_only_shortfall_stays_a_warning(self):
        # Forms and Sites have no export format, so rclone can never fetch
        # them. That shortfall is a limit of the API, not lost data, and must
        # not hold licence removal or fail the run.
        (self.b / "one.docx").write_text("x")
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, self._filelist(3, forms=2))):
            drive, local = offb.verify_drive_backup_complete("u@d.com", self.b)
        self.assertEqual((drive, local), (3, 1))
        self.assertFalse(offb.summary_errors)
        self.assertEqual(offb.exit_code, 0)
        self.assertTrue(any("not exportable" in w for w in offb.summary_warnings))

    def test_b9_10_shortfall_beyond_the_forms_is_an_error(self):
        # 4 in Drive, 1 of them a Form, 1 on disk: the Form explains one of the
        # three missing, the other two are real and must fail the run.
        (self.b / "one.docx").write_text("x")
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, self._filelist(4, forms=1))):
            offb.verify_drive_backup_complete("u@d.com", self.b)
        self.assertTrue(any("2 of them unaccounted for" in e
                            for e in offb.summary_errors))
        self.assertEqual(offb.exit_code, 1)

    def test_b9_4_gam_failure_does_not_raise_or_warn(self):
        with mock.patch.object(offb, "run_gam", return_value=(False, "")):
            self.assertEqual(offb.verify_drive_backup_complete("u@d.com", self.b),
                             (0, 0))
        self.assertFalse(offb.summary_warnings)


SD_LIST = ("Getting all Shared Drives for leaver@yourdomain.com\n"
           "Got 1 Shared Drive for leaver@yourdomain.com...\n"
           "User,id,name,role\n"
           "leaver@yourdomain.com,0ABC123,Client Contracts,organizer\n")

# Real `gam print drivefileacls` shape: indexed permissions.N.* columns.
SD_ACL_SOLE = (
    "Owner,id,permissions,permissions.0.emailAddress,permissions.0.role\n"
    "leaver@yourdomain.com,0ABC123,1,leaver@yourdomain.com,organizer\n"
)

SD_ACL_SHARED = (
    "Owner,id,permissions,permissions.0.emailAddress,permissions.0.role,"
    "permissions.1.emailAddress,permissions.1.role\n"
    "leaver@yourdomain.com,0ABC123,2,leaver@yourdomain.com,organizer,"
    "successor@yourdomain.com,organizer\n"
)


class TestB11SharedDrives(unittest.TestCase):
    """Nothing in an offboarding touches Shared Drives; they must be reported."""

    def setUp(self):
        offb.summary_warnings.clear()

    def test_b11_1_sole_organizer_is_flagged_as_orphaned(self):
        with mock.patch.object(offb, "run_gam",
                               side_effect=[(True, SD_LIST), (True, SD_ACL_SOLE)]):
            orphaned = offb.check_shared_drives("leaver@yourdomain.com", dry_run=False)
        self.assertEqual(len(orphaned), 1)
        self.assertIn("Client Contracts", orphaned[0])
        self.assertTrue(any("no organizer other than" in w
                            for w in offb.summary_warnings))

    def test_b11_2_another_organizer_means_not_orphaned(self):
        with mock.patch.object(offb, "run_gam",
                               side_effect=[(True, SD_LIST), (True, SD_ACL_SHARED)]):
            orphaned = offb.check_shared_drives("leaver@yourdomain.com", dry_run=False)
        self.assertEqual(orphaned, [])
        # Still warns that the content is not backed up or transferred.
        self.assertTrue(offb.summary_warnings)

    def test_b11_3_no_shared_drives_is_quiet(self):
        empty = "Got 0 Shared Drives\nUser,id,name,role\n"
        with mock.patch.object(offb, "run_gam", return_value=(True, empty)):
            self.assertEqual(
                offb.check_shared_drives("leaver@yourdomain.com", dry_run=False), [])
        self.assertFalse(offb.summary_warnings)

    def test_b11_4_gam_failure_never_raises(self):
        with mock.patch.object(offb, "run_gam", return_value=(False, "")):
            self.assertEqual(
                offb.check_shared_drives("leaver@yourdomain.com", dry_run=False), [])

    def test_b11_6_unreadable_acl_is_unknown_not_orphaned(self):
        # Proved on dev 2026-07-29: a drive WITH a second organizer was
        # reported as having none when the ACL read failed. A failed read is
        # not evidence of absence, and the red warning states it as fact.
        with mock.patch.object(offb, "run_gam",
                               side_effect=[(True, SD_LIST), (False, "")]):
            orphaned = offb.check_shared_drives("leaver@yourdomain.com", dry_run=False)
        self.assertEqual(orphaned, [])
        self.assertTrue(any("unknown" in w.lower() for w in offb.summary_warnings))
        self.assertFalse(any("no organizer other than" in w
                             for w in offb.summary_warnings))

    def test_b11_7_unparseable_drive_list_is_not_silence(self):
        with mock.patch.object(offb, "run_gam", return_value=(True, "garbage")):
            self.assertEqual(
                offb.check_shared_drives("leaver@yourdomain.com", dry_run=False), [])
        self.assertTrue(any("inconclusive" in w for w in offb.summary_warnings))

    def test_b11_8_remedy_command_runs_as_the_leaver(self):
        # A non-member cannot grant themselves organizer: GAM answers
        # "Add Failed: Does not exist" (dev, 2026-07-29). The printed command
        # must name the leaver, who is the only organizer left.
        printed = []
        with mock.patch.object(offb, "run_gam",
                               side_effect=[(True, SD_LIST), (True, SD_ACL_SOLE)]):
            with mock.patch.object(offb, "print_error", printed.append):
                offb.check_shared_drives("leaver@yourdomain.com", dry_run=False)
        self.assertTrue(any("gam user leaver@yourdomain.com add drivefileacl" in p
                            for p in printed))

    def test_b11_9_zero_shared_drives_exit_60_is_not_a_failed_read(self):
        # GAM 7.48.01 exits 60 on `print shareddrives` for a user in no shared
        # drive, having printed the CSV header perfectly well (dev, 2026-08-31,
        # all three test VMs). run_gam only forgives a non-zero exit when the
        # output matches a non-fatal pattern, so without one every ordinary
        # leaver got "Could not list Shared Drives ... check by hand".
        with mock.patch.object(offb, "run_gam", return_value=(True, "")) as rg:
            offb.check_shared_drives("leaver@yourdomain.com", dry_run=False)
        patterns = rg.call_args.kwargs.get("non_fatal_patterns") or []
        self.assertTrue(any("0 shared drives" in p.lower() for p in patterns))

    def test_b11_5_dry_run_makes_no_calls(self):
        with mock.patch.object(offb, "run_gam") as rg:
            self.assertEqual(
                offb.check_shared_drives("leaver@yourdomain.com", dry_run=True), [])
        rg.assert_not_called()


class _Args:
    """Minimal stand-in for the argparse namespace preflight_destinations reads."""
    def __init__(self, **kw):
        self.no_drive = self.no_email = self.no_alias = False
        self.no_calendar = self.no_forward = False
        self.drive_to = self.email_to = self.alias_to = None
        self.calendar_to = self.forward_to = None
        self.all_transfer_to = None
        self.force = True
        self.__dict__.update(kw)


class TestB10SelfTransferGuard(unittest.TestCase):
    """Transferring a leaver's data to the leaver is always an operator error."""

    def setUp(self):
        # The guard resolves the source's aliases; stub the lookup by default.
        p = mock.patch.object(offb, "_list_aliases", return_value=[])
        p.start()
        self.addCleanup(p.stop)

    def test_b10_6_an_alias_of_the_leaver_is_caught(self):
        # A different address, the same mailbox. The literal comparison alone
        # let this through: Drive to self, mail to self, forward to self.
        args = _Args(all_transfer_to="l.old@yourdomain.com")
        with mock.patch.object(offb, "_list_aliases",
                               return_value=["l.old@yourdomain.com"]):
            with mock.patch.object(offb, "validate_destination", return_value=True):
                with self.assertRaises(SystemExit) as cm:
                    offb.preflight_destinations(args, source="leaver@yourdomain.com")
        self.assertEqual(cm.exception.code, 2)

    def test_b10_7_alias_lookup_is_skipped_when_nothing_is_targeted(self):
        args = _Args(no_drive=True, no_email=True, no_alias=True,
                     no_calendar=True, no_forward=True)
        with mock.patch.object(offb, "_list_aliases") as la:
            offb.preflight_destinations(args, source="leaver@yourdomain.com")
        la.assert_not_called()

    def test_b10_1_destination_equal_to_source_is_refused(self):
        args = _Args(all_transfer_to="leaver@yourdomain.com")
        with mock.patch.object(offb, "validate_destination", return_value=True):
            with self.assertRaises(SystemExit) as cm:
                offb.preflight_destinations(args, source="leaver@yourdomain.com")
        self.assertEqual(cm.exception.code, 2)

    def test_b10_2_case_and_domain_case_still_caught(self):
        args = _Args(all_transfer_to="Leaver@YourDomain.com")
        with mock.patch.object(offb, "validate_destination", return_value=True):
            with self.assertRaises(SystemExit):
                offb.preflight_destinations(args, source="leaver@yourdomain.com")

    def test_b10_3_one_phase_self_targeted_is_enough(self):
        args = _Args(all_transfer_to="successor@yourdomain.com",
                     forward_to="leaver@yourdomain.com")
        with mock.patch.object(offb, "validate_destination", return_value=True):
            with self.assertRaises(SystemExit):
                offb.preflight_destinations(args, source="leaver@yourdomain.com")

    def test_b10_4_a_real_successor_passes(self):
        args = _Args(all_transfer_to="successor@yourdomain.com")
        with mock.patch.object(offb, "validate_destination", return_value=True):
            got = offb.preflight_destinations(args, source="leaver@yourdomain.com")
        self.assertEqual(got["drive"], "successor@yourdomain.com")

    def test_b10_5_no_source_given_skips_the_check(self):
        # Keeps the function usable without a source (older call sites).
        args = _Args(all_transfer_to="leaver@yourdomain.com")
        with mock.patch.object(offb, "validate_destination", return_value=True):
            got = offb.preflight_destinations(args)
        self.assertEqual(got["drive"], "leaver@yourdomain.com")


class _PlanArgs(_Args):
    """argparse stand-in for collect_plan: adds the skip flags it reads."""
    def __init__(self, **kw):
        super().__init__()
        self.no_auto_reply = self.no_suspend = False
        self.strip_labels = True
        self.__dict__.update(kw)


class TestB12Plan2SVDecision(unittest.TestCase):
    """collect_plan decides turnoff2sv up front so it cannot blow up mid-run.

    turnoff2sv errors with GAM exit 50 when 2SV is ENFORCED by an OU policy or
    an enforcement group, because moving OUs does not clear a group policy.
    Under --force the plan must therefore only attempt it when it can succeed.
    Proved live on dev 2026-07-29 (testoffboard4, enrolled, /Offboarding OU
    enforcing): exit 50, "user is required by admin policy to have 2-Step
    Verification". The plan's reading is necessary but NOT sufficient — see
    TestB13, the OU move changes the answer underneath it.
    """

    @staticmethod
    def _plan(enrolled, enforced):
        args = _PlanArgs(no_drive=True, no_email=True, no_alias=True,
                         no_calendar=True, no_forward=True)
        dest_map = {k: None for k in
                    ("drive", "email", "alias", "calendar", "forward")}
        return offb.collect_plan(args, dest_map, enrolled, enforced)

    def test_b12_1_not_enrolled_means_nothing_to_turn_off(self):
        self.assertFalse(self._plan(False, False)["turnoff2sv"]["do"])

    def test_b12_2_enrolled_not_enforced_is_attempted(self):
        self.assertTrue(self._plan(True, False)["turnoff2sv"]["do"])

    def test_b12_3_enforced_is_still_attempted_under_force(self):
        # Was "skip if enforced". Wrong in both directions: enforcement follows
        # the OU and the kill switch moves the user first, so the plan-time
        # reading describes the OU being left. Attempt, and handle the refusal.
        self.assertTrue(self._plan(True, True)["turnoff2sv"]["do"])

    def test_b12_4_enforced_but_not_enrolled_still_skipped(self):
        self.assertFalse(self._plan(False, True)["turnoff2sv"]["do"])


ENFORCED_ERR = ('User: leaver@yourdomain.com, Turn Off 2-Step Verification '
                'Failed: 2-Step Verification cannot be turned off: user is '
                'required by admin policy to have 2-Step Verification '
                '("enforced")')


class TestB132SVEnforcedRefusal(unittest.TestCase):
    """An enforced refusal is a fact to report, not an outcome to predict.

    Proved on dev 2026-07-29 (testoffboard4, enrolled, /Offboarding enforcing):
    `deprovision popimap signout turnoff2sv` exits 50, but every other action in
    the bundle completed first — ASPs, backup codes, tokens, sign-out, POP/IMAP.
    Reporting that as a failed deprovision tells the operator containment did
    not happen, which is the opposite of the truth.
    """

    def setUp(self):
        offb.summary_warnings.clear()
        offb.summary_errors.clear()
        offb.summary_actions.clear()

    def _kill(self, gam_side_effect, enrolled_readback=False):
        with mock.patch.object(offb, "_read_2sv_enrolled",
                               return_value=enrolled_readback):
            with mock.patch.object(offb, "run_gam", side_effect=gam_side_effect):
                offb.execute_kill_switch(
                    "leaver@yourdomain.com", dry_run=False, is_suspended=False,
                    is_2sv_enrolled=True, has_mailbox=True, turn_off_2sv=True)

    def test_b13_1_bundle_reports_containment_done_not_failed(self):
        def fake(args, **kw):
            return (True, ENFORCED_ERR) if "deprovision" in args else (True, "")
        self._kill(fake)
        self.assertTrue(any("Deprovisioned" in a for a in offb.summary_actions))
        self.assertFalse(any("deprovision" in e.lower()
                             for e in offb.summary_errors))

    def test_b13_2_explicit_turnoff2sv_refusal_is_a_warning_not_an_error(self):
        # "Retry manually" was the old advice. Policy is refusing, so the retry
        # fails identically; the message must name what would actually change.
        def fake(args, **kw):
            return (False, ENFORCED_ERR) if "turnoff2sv" in args else (True, "")
        self._kill(fake, enrolled_readback=True)
        self.assertTrue(any("enforced by policy" in w
                            for w in offb.summary_warnings))
        self.assertFalse(any("turnoff2sv failed" in e
                             for e in offb.summary_errors))

    def test_b13_3_an_unrelated_failure_is_still_a_real_error(self):
        def fake(args, **kw):
            return ((False, "Turn Off 2-Step Verification Failed: backendError")
                    if "turnoff2sv" in args and "deprovision" not in args
                    else (True, ""))
        self._kill(fake, enrolled_readback=True)
        self.assertTrue(any("turnoff2sv failed" in e
                            for e in offb.summary_errors))

    def test_b13_4_not_enrolled_after_deprovision_is_success_not_a_skip(self):
        # The directory read lags: deprovision turned 2SV off at 12:26:12 and
        # `gam info user quick` still said enrolled at 12:26:22 (dev, live).
        # The run then reported "turnoff2sv skipped" for a 2SV it had removed.
        not_enrolled = ("\nUser: leaver@yourdomain.com, Turn Off 2-Step "
                        "Verification Failed: 2-Step Verification cannot be "
                        "turned off: user not enrolled in 2-Step Verification")

        def fake(args, **kw):
            return (False, not_enrolled) if "turnoff2sv" in args else (True, "")
        self._kill(fake, enrolled_readback=True)
        self.assertTrue(any("Turned off 2SV" in a for a in offb.summary_actions))
        self.assertFalse(any("skipped" in w for w in offb.summary_warnings))

    def test_b13_5_a_reason_is_never_quoted_as_an_empty_string(self):
        # stdout is empty and stderr is appended after it, so line [0] is blank
        # and the message printed "turnoff2sv skipped: " with nothing after it.
        self.assertEqual(offb._first_line("\nreal reason\nmore"), "real reason")
        self.assertEqual(offb._first_line(""), "no reason given")


###############################################################################
# B15 — Issue #2: a preflight abort must not leave a suspended account active
###############################################################################

class TestB15SuspensionRestore(OffboardTestCase):
    """The temporary unsuspend is a promise: the account goes back."""

    def test_b15_1_suspended_field_is_read_not_substring_matched(self):
        # testoffboard3 is Charlie SUSPENDED and is genuinely suspended; the
        # active fixture below is the one a substring match gets wrong.
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, FIXTURE_SUSPENDED_USER)):
            self.assertIs(offb.read_suspended("x@yourdomain.com"), True)
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, FIXTURE_ACTIVE_USER)):
            self.assertIs(offb.read_suspended("x@yourdomain.com"), False)

    def test_b15_2_unreadable_state_is_none_not_false(self):
        with mock.patch.object(offb, "run_gam", return_value=(False, "")):
            self.assertIsNone(offb.read_suspended("x@yourdomain.com"))

    def test_b15_3_poll_gives_up_instead_of_hanging(self):
        clock = _FakeClock()
        with mock.patch.object(offb, "read_suspended", return_value=False), \
                mock.patch("time.time", clock.time), \
                mock.patch("time.sleep", clock.sleep):
            self.assertFalse(offb.wait_for_suspended("x@yourdomain.com", True,
                                                     timeout=30))

    def test_b15_4_already_suspended_makes_no_change(self):
        with mock.patch.object(offb, "read_suspended", return_value=True), \
                mock.patch.object(offb, "run_gam") as gam:
            self.assertTrue(offb.restore_original_suspension("x@yourdomain.com"))
        gam.assert_not_called()

    def test_b15_5_restore_is_attempted_then_reported_as_an_error(self):
        clock = _FakeClock()
        with mock.patch.object(offb, "read_suspended", return_value=False), \
                mock.patch.object(offb, "run_gam", return_value=(True, "")) as gam, \
                mock.patch("time.time", clock.time), \
                mock.patch("time.sleep", clock.sleep):
            ok = offb.restore_original_suspension("x@yourdomain.com", attempts=2)
        self.assertFalse(ok)
        self.assertEqual(gam.call_count, 2)
        self.assertTrue(any("NOT restored" in e for e in offb.summary_errors))

    def test_b15_6_destinations_are_validated_before_the_unsuspend(self):
        # The bug was ordering: preflight exit(2) ran after the unsuspend.
        import inspect
        src = inspect.getsource(offb.main)
        self.assertLess(src.index("preflight_destinations(args"),
                        src.index("Temporarily unsuspending user"),
                        "preflight must run before any account change")

    def test_b15_7_unverified_unsuspend_aborts(self):
        import inspect
        src = inspect.getsource(offb.main)
        self.assertIn("wait_for_suspended(user_email, False)", src)
        self.assertIn("atexit.register(restore_original_suspension", src)


###############################################################################
# B16 — Issue #3: a failed transfer must not be followed by licence removal
###############################################################################

class TestB16TransferFailureHold(OffboardTestCase):

    def test_b16_1_a_phase_that_errors_is_recorded(self):
        failures = []
        with offb.record_failure("Drive transfer", failures):
            offb.summary_error("Drive transfer lost 3 files")
        self.assertEqual(failures, ["Drive transfer"])

    def test_b16_2_a_clean_phase_is_not_recorded(self):
        failures = []
        with offb.record_failure("Drive transfer", failures):
            offb.summary_action("Transferred 244 files")
        self.assertEqual(failures, [])

    def test_b16_3_an_exception_still_records_and_propagates(self):
        failures = []
        with self.assertRaises(RuntimeError):
            with offb.record_failure("Email migration", failures):
                offb.summary_error("boom")
                raise RuntimeError("boom")
        self.assertEqual(failures, ["Email migration"])

    def test_b16_4_licence_removal_is_behind_the_hold(self):
        import inspect
        src = inspect.getsource(offb.main)
        # rindex: the scorched-earth short circuit has its own earlier call,
        # and that path transfers nothing so the hold does not apply to it.
        self.assertLess(src.index("if transfer_failures and not dry_run"),
                        src.rindex("remove_licences(user_email"),
                        "licence removal must sit behind the transfer-failure hold")


###############################################################################
# B17 — Issue #5: containment failure must be visible and acted on
###############################################################################

class TestB17ContainmentOutcome(OffboardTestCase):

    def _kill(self, gam_side_effect):
        with mock.patch.object(offb, "run_gam", side_effect=gam_side_effect):
            return offb.execute_kill_switch(
                "leaver@yourdomain.com", dry_run=False, is_suspended=False,
                is_2sv_enrolled=False, has_mailbox=True, turn_off_2sv=False)

    def test_b17_1_failed_password_scramble_is_not_contained(self):
        def fake(args, **kw):
            return (False, "Update Failed") if "password" in args else (True, "")
        result = self._kill(fake)
        self.assertFalse(result["contained"])
        self.assertFalse(result["password_scrambled"])
        self.assertTrue(any("CONTAINMENT INCOMPLETE" in e
                            for e in offb.summary_errors))

    def test_b17_2_a_clean_kill_switch_reports_contained(self):
        result = self._kill(lambda args, **kw: (True, ""))
        self.assertTrue(result["contained"])
        self.assertFalse(any("CONTAINMENT INCOMPLETE" in e
                             for e in offb.summary_errors))

    def test_b17_3_deprovision_signout_covers_a_failed_explicit_signout(self):
        # The bundle in step 3 signs the user out too, so one failing call is
        # not a containment failure on its own.
        def fake(args, **kw):
            return (False, "") if args[:3] == ["user", "leaver@yourdomain.com",
                                               "signout"] else (True, "")
        result = self._kill(fake)
        self.assertTrue(result["signed_out"])
        self.assertTrue(result["contained"])

    def test_b17_4_no_suspend_is_overridden_when_containment_fails(self):
        import inspect
        src = inspect.getsource(offb.main)
        self.assertIn('force_suspend = not containment.get("contained", False)', src)
        self.assertIn("skip_suspend = args.no_suspend and not force_suspend", src)




class TestB19MahatiRunFixes(OffboardTestCase):
    """Fixes from the Mahati (udank.shah) production run and the 2026-08-03
    dev round: mailbox-less email destination caught in preflight, backup
    folder reuse on re-run, exit-56 drive transfer as warning, honest restore
    attempt counts."""

    def test_b19_1_gmail_disabled_detected_despite_gam_failure(self):
        """gam exits 73 (ok=False) for a mailbox-less user; the 'not enabled'
        text must still block the restore."""
        def fake(args, **kw):
            if "gmailprofile" in args:
                return (False, "User: d@x, Gmail Service/App not enabled")
            return (True, "")
        with mock.patch.object(offb, "run_gam", side_effect=fake):
            ready = offb.check_restore_destination_ready(
                "d@x", Path("/nonexistent"), dry_run=False)
        self.assertFalse(ready)
        self.assertTrue(any("Gmail not enabled" in e for e in offb.summary_errors))

    def test_b19_2_preflight_blocks_mailboxless_email_destination(self):
        import argparse
        args = argparse.Namespace(
            no_drive=True, no_email=False, no_alias=True, no_calendar=True,
            no_forward=True, drive_to=None, email_to="dest@x", alias_to=None,
            calendar_to=None, forward_to=None, all_transfer_to=None, force=True)
        def fake(cmd, **kw):
            if "gmailprofile" in cmd:
                return (False, "Gmail Service/App not enabled")
            return (True, "First Name: D\nAccount Suspended: False")
        with mock.patch.object(offb, "run_gam", side_effect=fake), \
             mock.patch.object(offb, "_list_aliases", return_value=[]):
            with self.assertRaises(SystemExit) as cm:
                offb.preflight_destinations(args, source="leaver@x")
        self.assertEqual(cm.exception.code, 2)

    @staticmethod
    def _dated_backup(root, days_ago):
        from datetime import datetime, timedelta
        stamp = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
        folder = root / "mailboxes" / f"leaver@x_{stamp}"
        folder.mkdir(parents=True)
        (folder / "msg-db.sqlite").touch()
        return folder

    def test_b19_3_force_resumes_recent_folder(self):
        """A next-day --force re-run must resume into the existing backup
        folder, not mint a new dated one and re-download the whole mailbox."""
        with tempfile.TemporaryDirectory() as td:
            old = self._dated_backup(Path(td), days_ago=2)
            with mock.patch.object(offb, "BACKUP_DIRECTORY", Path(td)):
                chosen = offb._select_email_backup_path("leaver@x", force=True)
        self.assertEqual(chosen, old)

    def test_b19_3b_force_starts_fresh_when_folder_is_stale(self):
        """A folder past REUSE_BACKUP_MAX_AGE_DAYS is likely a previous
        engagement (rehire case) — under --force it must NOT be resumed."""
        with tempfile.TemporaryDirectory() as td:
            old = self._dated_backup(Path(td), days_ago=40)
            with mock.patch.object(offb, "BACKUP_DIRECTORY", Path(td)):
                chosen = offb._select_email_backup_path("leaver@x", force=True)
        self.assertNotEqual(chosen, old)

    def test_b19_3c_interactive_prompt_decides(self):
        with tempfile.TemporaryDirectory() as td:
            old = self._dated_backup(Path(td), days_ago=2)
            with mock.patch.object(offb, "BACKUP_DIRECTORY", Path(td)), \
                 mock.patch.object(offb, "prompt_yes_no", return_value=True):
                self.assertEqual(
                    offb._select_email_backup_path("leaver@x"), old)
            with mock.patch.object(offb, "BACKUP_DIRECTORY", Path(td)), \
                 mock.patch.object(offb, "prompt_yes_no", return_value=False):
                fresh = offb._select_email_backup_path("leaver@x")
        self.assertNotEqual(fresh, old)

    def test_b19_3d_declined_same_day_folder_gets_distinct_name(self):
        """Declining reuse of a folder named for TODAY must not hand back
        the same path under a different intention."""
        with tempfile.TemporaryDirectory() as td:
            old = self._dated_backup(Path(td), days_ago=0)
            with mock.patch.object(offb, "BACKUP_DIRECTORY", Path(td)), \
                 mock.patch.object(offb, "prompt_yes_no", return_value=False):
                fresh = offb._select_email_backup_path("leaver@x")
        self.assertNotEqual(fresh, old)

    def test_b19_4_backup_path_ignores_foreign_and_empty_folders(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "mailboxes" / "leaver@x_email_20260701").mkdir(parents=True)
            empty = root / "mailboxes" / "leaver@x_20260702"
            empty.mkdir()  # no msg-db.sqlite: not a resumable GYB backup
            with mock.patch.object(offb, "BACKUP_DIRECTORY", root):
                chosen = offb._select_email_backup_path("leaver@x", force=True)
        self.assertNotEqual(chosen.name, "leaver@x_email_20260701")
        self.assertNotEqual(chosen, empty)
        self.assertRegex(chosen.name, r"^leaver@x_\d{8}$")

    def test_b19_5_drive_transfer_exit_56_is_warning_not_error(self):
        """Exit 56 = non-owned files skipped; must not block licence removal
        (ticket 10077)."""
        proc = mock.MagicMock()
        proc.stdout = iter(["Got 3 Drive Files/Folders for Source User\n",
                            "Ownership Transferred to User: ok\n"])
        proc.returncode = 56
        proc.wait = mock.MagicMock()
        with mock.patch.object(offb, "run_gam", return_value=(True, "First Name: D")), \
             mock.patch.object(offb.subprocess, "Popen", return_value=proc):
            offb.transfer_drive("leaver@x", "dest@x", dry_run=False)
        self.assertFalse(offb.summary_errors)
        self.assertTrue(any("exit 56" in w for w in offb.summary_warnings))

    def test_b19_6_drive_transfer_other_exit_still_error(self):
        proc = mock.MagicMock()
        proc.stdout = iter([])
        proc.returncode = 1
        proc.wait = mock.MagicMock()
        with mock.patch.object(offb, "run_gam", return_value=(True, "First Name: D")), \
             mock.patch.object(offb.subprocess, "Popen", return_value=proc):
            offb.transfer_drive("leaver@x", "dest@x", dry_run=False)
        self.assertTrue(any("Drive transfer failed" in e for e in offb.summary_errors))

    def test_b19_7_restore_failure_reports_actual_attempts(self):
        source = inspect_getsource(offb.migrate_email)
        self.assertIn('f"Email restore to {destination} FAILED after {attempt} "',
                      source)


class TestB20InteractiveDestinationGuards(unittest.TestCase):
    """Interactively typed destinations get the same guards as flag-supplied
    ones: the self-transfer/alias refusal and the email-mailbox probe.

    Before this, only preflight_destinations (the flag path) ran them — an
    operator typing the leaver's own alias at the plan prompt got a mailbox
    restored into itself, and an unlicensed destination failed only after the
    full multi-hour download.
    """

    def test_b20_1_leavers_alias_is_refused_then_reasks(self):
        with mock.patch.object(offb, "prompt_email",
                               side_effect=["leaver.alias@x", "successor@x"]), \
             mock.patch.object(offb, "validate_destination", return_value=True), \
             mock.patch.object(offb, "_list_aliases",
                               return_value=["leaver.alias@x"]):
            got = offb._plan_email("Email dest", source="leaver@x")
        self.assertEqual(got, "successor@x")

    def test_b20_2_leaver_literal_is_refused(self):
        with mock.patch.object(offb, "prompt_email",
                               side_effect=["LEAVER@x", "successor@x"]), \
             mock.patch.object(offb, "validate_destination", return_value=True), \
             mock.patch.object(offb, "_list_aliases", return_value=[]):
            got = offb._plan_email("Drive dest", source="leaver@x")
        self.assertEqual(got, "successor@x")

    def test_b20_3_mailboxless_email_dest_is_refused_then_reasks(self):
        with mock.patch.object(offb, "prompt_email",
                               side_effect=["nolic@x", "successor@x"]), \
             mock.patch.object(offb, "validate_destination", return_value=True), \
             mock.patch.object(offb, "_list_aliases", return_value=[]), \
             mock.patch.object(offb, "_email_mailbox_missing",
                               side_effect=["Gmail service not enabled", None]):
            got = offb._plan_email("Email dest", source="leaver@x",
                                   needs_mailbox=True)
        self.assertEqual(got, "successor@x")

    def test_b20_4_mailbox_probe_not_run_for_non_email_prompts(self):
        with mock.patch.object(offb, "prompt_email", return_value="successor@x"), \
             mock.patch.object(offb, "validate_destination", return_value=True), \
             mock.patch.object(offb, "_list_aliases", return_value=[]), \
             mock.patch.object(offb, "_email_mailbox_missing") as probe:
            offb._plan_email("Drive dest", source="leaver@x")
        probe.assert_not_called()

    def test_b20_5_collect_plan_wires_source_and_mailbox_probe(self):
        args = _PlanArgs(no_drive=True, no_alias=True, no_calendar=True,
                         no_forward=True, force=False)
        dest_map = {k: None for k in
                    ("drive", "email", "alias", "calendar", "forward")}
        with mock.patch.object(offb, "prompt_yes_no", return_value=True), \
             mock.patch.object(offb, "_plan_email",
                               return_value="successor@x") as pe:
            offb.collect_plan(args, dest_map, False, False, source="leaver@x")
        pe.assert_called_once_with("Email migration destination email",
                                   source="leaver@x", needs_mailbox=True)


class TestB21BackupAndExit56Holds(OffboardTestCase):
    """Failures before licence removal must be loud enough to hold it.

    Two silent-swallow paths from the 2026-08-05 audit: exit 56 with zero
    transfer confirmations read as benign skips, and --backup-email never
    reconciling msg-db against disk (the only copy on an archive-only
    offboarding).
    """

    def test_b21_1_exit56_zero_moved_is_an_error(self):
        proc = mock.MagicMock()
        proc.stdout = iter(["Got 3 Drive Files/Folders for Source User\n"])
        proc.returncode = 56
        proc.wait = mock.MagicMock()
        with mock.patch.object(offb, "run_gam", return_value=(True, "First Name: D")), \
             mock.patch.object(offb.subprocess, "Popen", return_value=proc):
            offb.transfer_drive("leaver@x", "dest@x", dry_run=False)
        self.assertTrue(any("0 files" in e for e in offb.summary_errors))

    def test_b21_2_exit56_with_moves_still_a_warning(self):
        proc = mock.MagicMock()
        proc.stdout = iter(["Ownership Transferred to User: ok\n"])
        proc.returncode = 56
        proc.wait = mock.MagicMock()
        with mock.patch.object(offb, "run_gam", return_value=(True, "First Name: D")), \
             mock.patch.object(offb.subprocess, "Popen", return_value=proc):
            offb.transfer_drive("leaver@x", "dest@x", dry_run=False)
        self.assertFalse(offb.summary_errors)
        self.assertTrue(any("exit 56" in w for w in offb.summary_warnings))

    def test_b21_3_backup_email_only_fails_on_short_backup(self):
        def short_verify(path):
            offb.summary_error(f"Backup at {path} is missing 2 message(s)")
            return (5, 3)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(offb, "BACKUP_DIRECTORY", Path(tmp)), \
             mock.patch.object(offb, "run_gyb", return_value=(True, "")), \
             mock.patch.object(offb, "verify_backup_complete",
                               side_effect=short_verify):
            ok = offb.backup_email_only("leaver@x", dry_run=False)
        self.assertFalse(ok)
        self.assertFalse(any("backed up via GYB" in a for a in offb.summary_actions))

    def test_b21_4_backup_email_only_verified_clean_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(offb, "BACKUP_DIRECTORY", Path(tmp)), \
             mock.patch.object(offb, "run_gyb", return_value=(True, "")), \
             mock.patch.object(offb, "verify_backup_complete",
                               return_value=(5, 5)):
            ok = offb.backup_email_only("leaver@x", dry_run=False)
        self.assertTrue(ok)
        self.assertTrue(any("backed up via GYB" in a for a in offb.summary_actions))


class TestB22NoSuspendCrashGuard(OffboardTestCase):
    """The atexit re-suspend guard must cover --no-suspend runs that die.

    Only a run that REACHES the suspension phase makes an informed
    --no-suspend choice to leave the account active; a crash or Ctrl+C
    before that must re-suspend. The waiver flag is set exactly there.
    """

    def setUp(self):
        super().setUp()
        offb.no_suspend_contract_waived = False

    def tearDown(self):
        offb.no_suspend_contract_waived = False
        super().tearDown()

    def test_b22_1_guard_resuspends_when_not_waived(self):
        with mock.patch.object(offb, "read_suspended", return_value=False), \
             mock.patch.object(offb, "run_gam", return_value=(True, "")) as rg, \
             mock.patch.object(offb, "wait_for_suspended", return_value=True):
            self.assertTrue(offb.restore_original_suspension("leaver@x"))
        rg.assert_called()

    def test_b22_2_guard_stands_down_after_normal_no_suspend_completion(self):
        offb.no_suspend_contract_waived = True
        with mock.patch.object(offb, "run_gam") as rg:
            self.assertTrue(offb.restore_original_suspension("leaver@x"))
        rg.assert_not_called()

    def test_b22_3_registration_is_unconditional(self):
        # The old code guarded atexit.register behind `if not args.no_suspend`,
        # which left a crashed --no-suspend run's account silently active.
        source = inspect_getsource(offb.main)
        self.assertIn("atexit.register(restore_original_suspension", source)
        idx = source.index("atexit.register(restore_original_suspension")
        preceding = source[:idx].rsplit("\n", 3)[-3:]
        self.assertFalse(any("if not args.no_suspend" in line
                             for line in preceding))


DRIVESETTINGS_FIXTURE = """User: leaver@x
  limit: 329.85 TB
  usage: 12.5 GB
  usageInDrive: 2.5 GB
  usageInDriveTrash: 0.5 GB
"""


class TestB23BackupSizing(OffboardTestCase):
    """Disk-space preflight estimate and Drive backup folder resume."""

    def test_b23_1_mailbox_estimate_subtracts_drive_usage(self):
        with mock.patch.object(offb, "run_gam",
                               return_value=(True, DRIVESETTINGS_FIXTURE)):
            est = offb._estimate_mailbox_bytes("leaver@x")
        gb = 1024 ** 3
        self.assertEqual(est, int(12.5 * gb) - int(2.5 * gb) - int(0.5 * gb))

    def test_b23_2_mailbox_estimate_none_when_unparseable(self):
        with mock.patch.object(offb, "run_gam", return_value=(True, "garbage")):
            self.assertIsNone(offb._estimate_mailbox_bytes("leaver@x"))
        with mock.patch.object(offb, "run_gam", return_value=(False, "")):
            self.assertIsNone(offb._estimate_mailbox_bytes("leaver@x"))

    def test_b23_3_drive_backup_resumes_recent_folder_under_force(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(offb, "BACKUP_DIRECTORY", Path(tmp)):
            stamp = offb.datetime.now().strftime("%Y%m%d")
            prior = Path(tmp) / "drive" / f"leaver@x_{stamp}"
            prior.mkdir(parents=True)
            (prior / "somefile.pdf").write_bytes(b"x")
            got = offb._select_drive_backup_path("leaver@x", force=True)
            self.assertEqual(got, prior)

    def test_b23_4_drive_backup_old_folder_starts_fresh_under_force(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(offb, "BACKUP_DIRECTORY", Path(tmp)):
            old = Path(tmp) / "drive" / "leaver@x_20200101"
            old.mkdir(parents=True)
            (old / "somefile.pdf").write_bytes(b"x")
            got = offb._select_drive_backup_path("leaver@x", force=True)
            self.assertNotEqual(got, old)

    def test_b23_5_empty_prior_folder_is_not_offered(self):
        # An empty date-stamped folder (e.g. an aborted mkdir-only run)
        # carries nothing to resume into.
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(offb, "BACKUP_DIRECTORY", Path(tmp)), \
             mock.patch.object(offb, "prompt_yes_no") as p:
            stamp = offb.datetime.now().strftime("%Y%m%d")
            (Path(tmp) / "drive" / f"leaver@x_{stamp}").mkdir(parents=True)
            offb._select_drive_backup_path("leaver@x", force=False)
        p.assert_not_called()


class TestB24TerminalFailFast(unittest.TestCase):
    """Terminal 4xx refusals stop the restore loop on attempt 1, not 3.

    2026-08-03 dev round: a failedPrecondition burned three attempts, each
    with a full quarantine re-scan of the corpus, before the stall bail-out
    fired. The first response already decided the outcome.
    """

    def test_b24_1_terminal_markers_detected(self):
        self.assertEqual(offb._looks_terminal("... failedPrecondition ..."),
                         "failedPrecondition")
        self.assertEqual(offb._looks_terminal("Mail service not enabled"),
                         "Mail service not enabled")
        self.assertIsNone(offb._looks_terminal("rateLimitExceeded, Backing off"))
        self.assertIsNone(offb._looks_terminal(""))

    def test_b24_2_throttle_markers_stay_retryable(self):
        # The two classifiers must never overlap: a marker in both would
        # step the batch down AND kill the loop.
        for m in ("rateLimitExceeded", "userRateLimitExceeded",
                  "quotaExceeded", "Backing off", "backendError"):
            self.assertIsNone(offb._looks_terminal(m))
            self.assertTrue(offb._looks_rate_limited(m))


def inspect_getsource(fn):
    import inspect
    return inspect.getsource(fn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
