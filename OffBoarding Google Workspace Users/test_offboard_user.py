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


if __name__ == "__main__":
    unittest.main(verbosity=2)
