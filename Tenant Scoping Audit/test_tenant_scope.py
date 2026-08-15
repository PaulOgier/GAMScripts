#!/usr/bin/env python3
"""Unit tests for tenant_scope.py.

Style mirrors the offboarding suite: stdlib unittest, no fixtures on disk
beyond temp dirs, weight on the findings engine (fixture CSVs -> expected
findings), plus preflight parsing, exit-60/empty-CSV handling and manifest
resume. No GAM calls are made anywhere in here.
"""

import argparse
import json
import tempfile
import unittest
from pathlib import Path

import tenant_scope as ts


def make_args(**overrides):
    base = dict(admin="admin@example.com", output_dir=None, run_dir=None,
                list=False, only=None, skip=None, skip_tier=None, full=False,
                no_dns=False, include_suspended=False,
                grant_temp_access=False, render_only=False, dry_run=False,
                yes=True)
    base.update(overrides)
    return argparse.Namespace(**base)


class CtxTestCase(unittest.TestCase):
    """Base: a temp run dir with helpers to drop fixture CSVs in."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name)
        self.ctx = ts.RunContext(self.run_dir, make_args())
        self.ctx.internal_domains = ["example.com", "alias.example.com"]

    def tearDown(self):
        self._tmp.cleanup()

    def write_csv(self, key, text, status="ok"):
        (self.run_dir / f"{key}.csv").write_text(text.strip() + "\n",
                                                 encoding="utf-8")
        rows = max(0, len(text.strip().splitlines()) - 1)
        self.ctx.set_module(key, status if rows else "empty", rows)

    def finding_ids(self, findings):
        return [f.fid for f in findings]


USERS_HEADER = ("primaryEmail,suspended,archived,lastLoginTime,"
                "isEnrolledIn2Sv,isEnforcedIn2Sv,recoveryEmail,isAdmin,"
                "isDelegatedAdmin,LicensesDisplay")


class TestSuperAdminChecks(CtxTestCase):
    def test_single_super_admin_is_critical(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,True,True,,True,False,Business
user@example.com,False,False,2026-08-01T10:00:00Z,True,False,,False,False,Business""")
        ids = self.finding_ids(ts.check_super_admin_count(self.ctx))
        self.assertIn("few-super-admins", ids)

    def test_two_super_admins_is_clean(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,True,True,,True,False,Business
boss2@example.com,False,False,2026-08-01T10:00:00Z,True,True,,True,False,Business""")
        self.assertEqual([], ts.check_super_admin_count(self.ctx))

    def test_suspended_admin_does_not_count(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,True,True,,True,False,Business
old@example.com,True,False,2026-08-01T10:00:00Z,True,True,,True,False,Business""")
        ids = self.finding_ids(ts.check_super_admin_count(self.ctx))
        self.assertIn("few-super-admins", ids)

    def test_admin_without_2sv(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,False,False,,True,False,Business""")
        findings = ts.check_admin_2sv(self.ctx)
        self.assertEqual(["admin-no-2sv"], self.finding_ids(findings))
        self.assertEqual("CRITICAL", findings[0].severity)

    def test_admin_personal_recovery_email(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,True,True,boss@gmail.com,True,False,Business""")
        ids = self.finding_ids(ts.check_admin_recovery(self.ctx))
        self.assertIn("admin-personal-recovery", ids)

    def test_admin_internal_recovery_email_clean(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,True,True,other@example.com,True,False,Business""")
        self.assertEqual([], ts.check_admin_recovery(self.ctx))

    def test_admin_with_asps(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,True,True,,True,False,Business""")
        self.write_csv("asps", """User,codeId,name,creationTime
boss@example.com,1,Old mail app,2025-01-01T00:00:00Z""")
        ids = self.finding_ids(ts.check_admin_asps(self.ctx))
        self.assertIn("admin-asps", ids)

    def test_non_admin_asps_clean(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,True,True,,True,False,Business""")
        self.write_csv("asps", """User,codeId,name,creationTime
user@example.com,1,Old mail app,2025-01-01T00:00:00Z""")
        self.assertEqual([], ts.check_admin_asps(self.ctx))


class TestForwardingChecks(CtxTestCase):
    def test_external_forward_found(self):
        self.write_csv("forwards", """User,forwardingEnabled,forwardTo,disposition
user@example.com,True,rival@gmail.com,archive""")
        findings = ts.check_external_forwarding(self.ctx)
        self.assertEqual(["external-forwarding"], self.finding_ids(findings))
        self.assertEqual("CRITICAL", findings[0].severity)

    def test_internal_forward_clean(self):
        self.write_csv("forwards", """User,forwardingEnabled,forwardTo,disposition
user@example.com,True,team@alias.example.com,archive""")
        self.assertEqual([], ts.check_external_forwarding(self.ctx))

    def test_disabled_forward_clean(self):
        self.write_csv("forwards", """User,forwardingEnabled,forwardTo,disposition
user@example.com,False,rival@gmail.com,archive""")
        self.assertEqual([], ts.check_external_forwarding(self.ctx))

    def test_filter_forwarding_external(self):
        self.write_csv("filters", """User,id,from,forward
user@example.com,f1,boss@example.com,leak@evil.example.net""")
        ids = self.finding_ids(ts.check_filter_forwarding(self.ctx))
        self.assertIn("filter-external-forwarding", ids)

    def test_filter_forwarding_internal_clean(self):
        self.write_csv("filters", """User,id,from,forward
user@example.com,f1,boss@example.com,team@example.com""")
        self.assertEqual([], ts.check_filter_forwarding(self.ctx))


class TestDriveChecks(CtxTestCase):
    FILELIST_HEADER = ("Owner,id,name,mimeType,owners.0.emailAddress,"
                       "permission.id,permission.type,permission.role,"
                       "permission.emailAddress,permission.domain,"
                       "permission.allowFileDiscovery")

    def test_public_on_web_is_critical(self):
        self.write_csv("mydrive_external", f"""{self.FILELIST_HEADER}
u@example.com,f1,Plans.docx,application/vnd.google-apps.document,u@example.com,anyoneWithLink,anyone,reader,,,True""")
        findings = ts.check_public_files(self.ctx)
        ids = self.finding_ids(findings)
        self.assertIn("public-files-mydrive_external", ids)

    def test_link_only_below_threshold_clean(self):
        rows = "\n".join(
            f"u@example.com,f{i},Doc{i},doc,u@example.com,anyoneWithLink,"
            f"anyone,reader,,,False" for i in range(3))
        self.write_csv("mydrive_external", f"{self.FILELIST_HEADER}\n{rows}")
        self.assertEqual([], ts.check_public_files(self.ctx))

    def test_link_only_at_scale_is_high(self):
        rows = "\n".join(
            f"u@example.com,f{i},Doc{i},doc,u@example.com,anyoneWithLink,"
            f"anyone,reader,,,False" for i in range(ts.ANYONE_LINK_SCALE))
        self.write_csv("mydrive_external", f"{self.FILELIST_HEADER}\n{rows}")
        findings = ts.check_public_files(self.ctx)
        self.assertEqual(["anyone-link-mydrive_external"],
                         self.finding_ids(findings))
        self.assertEqual("HIGH", findings[0].severity)

    def test_orphaned_shared_drive(self):
        self.write_csv("shareddriveorganizers", """id,name,organizers
sd1,Leaver Sole Manager SD,
sd2,Healthy Drive,alive@example.com""")
        findings = ts.check_orphaned_shared_drives(self.ctx)
        self.assertEqual(["orphaned-shared-drives"],
                         self.finding_ids(findings))
        self.assertEqual(1, findings[0].count)

    def test_shared_drive_external_member(self):
        self.write_csv("shareddriveacls", """id,name,permission.id,permission.type,permission.emailAddress,permission.role,permission.deleted
sd1,Client Drive,p1,user,partner@other.example.net,writer,False
sd1,Client Drive,p2,user,staff@example.com,organizer,False""")
        findings = ts.check_shared_drive_external(self.ctx)
        ids = self.finding_ids(findings)
        self.assertIn("sd-external-members", ids)
        self.assertEqual(1, findings[0].count)

    def test_deleted_user_acl_not_external(self):
        # Deleted users remain as ACL rows with permission.deleted=True and
        # an EMPTY email; they must not be reported as external members.
        self.write_csv("shareddriveacls", """id,name,permission.id,permission.type,permission.emailAddress,permission.role,permission.deleted
sd1,Old Drive,p1,user,,organizer,True""")
        self.assertEqual([], ts.check_shared_drive_external(self.ctx))

    def test_open_shared_drive_settings(self):
        self.write_csv("shareddrives", """id,name,restrictions.domainUsersOnly,restrictions.driveMembersOnly
sd1,Open Drive,False,False
sd2,Locked Drive,True,True""")
        findings = ts.check_shared_drive_external(self.ctx)
        self.assertEqual(["sd-open-settings"], self.finding_ids(findings))
        self.assertEqual(1, findings[0].count)


class TestExternalFileShareChecks(CtxTestCase):
    MYDRIVE_HEADER = ("Owner,id,name,mimeType,owners,owners.0.emailAddress,"
                      "permission.type,permission.emailAddress,"
                      "permission.domain,permission.role,"
                      "permission.allowFileDiscovery")

    def test_named_and_domain_external_shares_found(self):
        self.write_csv("mydrive_external", self.MYDRIVE_HEADER + "\n"
                       "u@example.com,f1,ext.doc,doc,1,u@example.com,"
                       "user,out@other.com,other.com,reader,\n"
                       "u@example.com,f2,dom.doc,doc,1,u@example.com,"
                       "domain,,other.com,reader,\n"
                       "u@example.com,f3,int.doc,doc,1,u@example.com,"
                       "user,in@example.com,example.com,reader,")
        findings = {f.fid: f for f in ts.check_external_file_shares(self.ctx)}
        self.assertIn("external-user-shares", findings)
        self.assertIn("external-domain-shares", findings)
        self.assertEqual(1, len(findings["external-user-shares"].evidence))
        self.assertEqual("MEDIUM", findings["external-user-shares"].severity)
        self.assertEqual("HIGH", findings["external-domain-shares"].severity)

    def test_anyone_rows_not_double_reported(self):
        # anyone-type ACLs belong to check_public_files, not this check.
        self.write_csv("mydrive_external", self.MYDRIVE_HEADER + "\n"
                       "u@example.com,f1,pub.doc,doc,1,u@example.com,"
                       "anyone,,,reader,True")
        self.assertEqual([], ts.check_external_file_shares(self.ctx))

    def test_inbound_shares_are_info(self):
        self.write_csv("sharedwithme_external",
                       "Owner,id,name,owners,owners.0.emailAddress,"
                       "sharedWithMeTime\n"
                       "u@example.com,f9,inbound.txt,1,ext@other.com,"
                       "2026-08-15T15:38:35Z")
        findings = ts.check_external_file_shares(self.ctx)
        self.assertEqual(["external-inbound-shares"],
                         self.finding_ids(findings))
        self.assertEqual("INFO", findings[0].severity)


class TestGroupChecks(CtxTestCase):
    GROUPS_HEADER = ("email,name,directMembersCount,whoCanJoin,"
                     "allowExternalMembers,whoCanPostMessage")

    def test_anyone_can_join(self):
        self.write_csv("groups", f"""{self.GROUPS_HEADER}
open@example.com,Open,3,ANYONE_CAN_JOIN,false,ALL_MEMBERS_CAN_POST""")
        ids = self.finding_ids(ts.check_group_exposure(self.ctx))
        self.assertEqual(["groups-anyone-join"], ids)

    def test_external_members_and_open_post(self):
        self.write_csv("groups", f"""{self.GROUPS_HEADER}
ext@example.com,Ext,3,INVITED_CAN_JOIN,true,ANYONE_CAN_POST""")
        ids = self.finding_ids(ts.check_group_exposure(self.ctx))
        self.assertEqual(["groups-external-members", "groups-anyone-post"],
                         ids)

    def test_locked_group_clean(self):
        self.write_csv("groups", f"""{self.GROUPS_HEADER}
safe@example.com,Safe,3,INVITED_CAN_JOIN,false,ALL_MEMBERS_CAN_POST""")
        self.assertEqual([], ts.check_group_exposure(self.ctx))


class TestAccountHygieneChecks(CtxTestCase):
    def test_2sv_enrolment_percentage(self):
        self.write_csv("users", f"""{USERS_HEADER}
a@example.com,False,False,2026-08-01T10:00:00Z,True,True,,False,False,Business
b@example.com,False,False,2026-08-01T10:00:00Z,False,False,,False,False,Business""")
        findings = ts.check_2sv_enrolment(self.ctx)
        self.assertEqual(["2sv-enrolment"], self.finding_ids(findings))
        self.assertIn("50%", findings[0].title)

    def test_full_2sv_clean(self):
        self.write_csv("users", f"""{USERS_HEADER}
a@example.com,False,False,2026-08-01T10:00:00Z,True,True,,False,False,Business""")
        self.assertEqual([], ts.check_2sv_enrolment(self.ctx))

    def test_pop_imap_enabled(self):
        self.write_csv("imap", """User,enabled
a@example.com,True""")
        self.write_csv("pop", """User,enabled
a@example.com,False""")
        ids = self.finding_ids(ts.check_pop_imap(self.ctx))
        self.assertEqual(["imap-enabled"], ids)

    def test_dormant_tiers_split(self):
        self.write_csv("users", f"""{USERS_HEADER}
old@example.com,False,False,2024-01-01T10:00:00Z,True,True,,False,False,Business
never@example.com,False,False,Never,True,True,,False,False,Business
epoch@example.com,False,False,1970-01-01T00:00:00.000Z,True,True,,False,False,Business
fresh@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,False,Business
unlicensed@example.com,False,False,Never,True,True,,False,False,""")
        findings = ts.check_dormant_accounts(self.ctx)
        by_id = {f.fid: f for f in findings}
        self.assertEqual({"never-logged-in", "dormant-licensed"},
                         set(by_id))
        self.assertEqual(["never@example.com", "epoch@example.com"],
                         [r["User"] for r in by_id["never-logged-in"].evidence])
        self.assertEqual(["old@example.com"],
                         [r["User"] for r in by_id["dormant-licensed"].evidence])

    def test_dormant_admin_is_high_even_unlicensed(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-14T10:00:00Z,True,True,,True,False,Business
oldadmin@example.com,False,False,2024-01-01T10:00:00Z,True,True,,False,True,""")
        findings = ts.check_dormant_accounts(self.ctx)
        self.assertEqual(["dormant-admin"], self.finding_ids(findings))
        self.assertEqual("HIGH", findings[0].severity)
        self.assertEqual("delegated admin",
                         findings[0].evidence[0]["Admin role"])

    def test_unmanaged_accounts(self):
        self.write_csv("userinvitations", """email,state,updateTime
rogue@example.com,NOT_YET_SENT,2026-08-01T00:00:00Z""")
        ids = self.finding_ids(ts.check_unmanaged_accounts(self.ctx))
        self.assertEqual(["unmanaged-accounts"], ids)


class TestDelegationChecks(CtxTestCase):
    def test_admin_mailbox_delegate_is_high_and_map_emitted(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-14T10:00:00Z,True,True,,True,False,Business
pa@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,False,Business""")
        self.write_csv("delegates", """User,delegateAddress,delegationStatus
boss@example.com,pa@example.com,ACCEPTED""")
        findings = ts.check_mailbox_delegation(self.ctx)
        ids = self.finding_ids(findings)
        self.assertIn("delegates-on-admin-mailbox", ids)
        self.assertIn("delegation-map", ids)
        self.assertNotIn("delegation-unwatched", ids)

    def test_suspended_delegate_is_medium(self):
        self.write_csv("users", f"""{USERS_HEADER}
owner@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,False,Business
gone@example.com,True,False,2026-08-14T10:00:00Z,True,True,,False,False,Business""")
        self.write_csv("delegates", """User,delegateAddress,delegationStatus
owner@example.com,gone@example.com,ACCEPTED""")
        findings = ts.check_mailbox_delegation(self.ctx)
        by_id = {f.fid: f for f in findings}
        self.assertIn("delegation-unwatched", by_id)
        self.assertIn("delegate suspended",
                      by_id["delegation-unwatched"].evidence[0]["Why"])
        self.assertNotIn("delegates-on-admin-mailbox", by_id)

    def test_delegated_admin_mailbox_also_high(self):
        self.write_csv("users", f"""{USERS_HEADER}
helpdesk@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,True,Business
pa@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,False,Business""")
        self.write_csv("delegates", """User,delegateAddress,delegationStatus
helpdesk@example.com,pa@example.com,ACCEPTED""")
        findings = ts.check_mailbox_delegation(self.ctx)
        by_id = {f.fid: f for f in findings}
        self.assertIn("delegates-on-admin-mailbox", by_id)
        self.assertEqual("delegated admin",
                         by_id["delegates-on-admin-mailbox"]
                         .evidence[0]["Admin role"])

    def test_plain_delegation_only_info(self):
        self.write_csv("users", f"""{USERS_HEADER}
owner@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,False,Business
pa@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,False,Business""")
        self.write_csv("delegates", """User,delegateAddress,delegationStatus
owner@example.com,pa@example.com,ACCEPTED""")
        self.assertEqual(["delegation-map"],
                         self.finding_ids(ts.check_mailbox_delegation(self.ctx)))


class TestAtRiskComposite(CtxTestCase):
    def test_two_factors_flagged_one_not(self):
        # risky: no 2SV + personal recovery. clean: 2SV on, no other factor.
        self.write_csv("users", f"""{USERS_HEADER}
risky@example.com,False,False,2026-08-14T10:00:00Z,False,False,risky@gmail.com,False,False,Business
clean@example.com,False,False,2026-08-14T10:00:00Z,True,True,it@example.com,False,False,Business""")
        findings = ts.check_at_risk_accounts(self.ctx)
        self.assertEqual(["at-risk-accounts"], self.finding_ids(findings))
        self.assertEqual("MEDIUM", findings[0].severity)
        self.assertEqual(["risky@example.com"],
                         [r["User"] for r in findings[0].evidence])

    def test_admin_in_list_raises_to_high(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-14T10:00:00Z,False,False,it@example.com,True,False,Business""")
        findings = ts.check_at_risk_accounts(self.ctx)
        self.assertEqual("HIGH", findings[0].severity)
        self.assertIn("admin role", findings[0].evidence[0]["Risk factors"])

    def test_asps_and_risky_token_count_as_factors(self):
        self.write_csv("users", f"""{USERS_HEADER}
u@example.com,False,False,2026-08-14T10:00:00Z,True,True,it@example.com,False,False,Business""")
        self.write_csv("asps", """User,codeId,name,creationTime
u@example.com,1,Old mail app,2025-01-01T00:00:00Z""")
        self.write_csv("tokens", """user,clientId,displayText,scopes
u@example.com,c1,Got Your Back,https://mail.google.com/ openid""")
        findings = ts.check_at_risk_accounts(self.ctx)
        factors = findings[0].evidence[0]["Risk factors"]
        self.assertIn("app-specific passwords", factors)
        self.assertIn("app with full mail/Drive access", factors)

    def test_single_factor_clean(self):
        self.write_csv("users", f"""{USERS_HEADER}
u@example.com,False,False,2026-08-14T10:00:00Z,False,False,it@example.com,False,False,Business""")
        self.assertEqual([], ts.check_at_risk_accounts(self.ctx))


class TestSuspendedHoldingData(CtxTestCase):
    def test_suspended_licensed_and_data_footprint(self):
        self.write_csv("users", f"""{USERS_HEADER}
gone@example.com,True,False,2024-01-01T10:00:00Z,True,True,,False,False,Business""")
        self.write_csv("report_users", """email,accounts:gmail_used_quota_in_mb,accounts:drive_used_quota_in_mb
gone@example.com,1024,2048
here@example.com,10,10""")
        self.write_csv("shareddriveacls", """User,id,name,permission.emailAddress,permission.role,permission.deleted
admin@example.com,SD1,Finance,gone@example.com,organizer,False""")
        findings = ts.check_suspended_holding_data(self.ctx)
        by_id = {f.fid: f for f in findings}
        self.assertEqual({"suspended-licensed", "suspended-holding-data"},
                         set(by_id))
        holds = [r["Holds"] for r in by_id["suspended-holding-data"].evidence]
        self.assertIn("mailbox/Drive data", holds)
        self.assertIn('manager of Shared Drive "Finance"', holds)

    def test_unlicensed_suspended_reader_is_quiet(self):
        self.write_csv("users", f"""{USERS_HEADER}
gone@example.com,True,False,2024-01-01T10:00:00Z,True,True,,False,False,""")
        self.write_csv("report_users", """email,accounts:gmail_used_quota_in_mb,accounts:drive_used_quota_in_mb
gone@example.com,0,0""")
        self.write_csv("shareddriveacls", """User,id,name,permission.emailAddress,permission.role,permission.deleted
admin@example.com,SD1,Finance,gone@example.com,reader,False""")
        self.assertEqual([], ts.check_suspended_holding_data(self.ctx))

    def test_cloud_identity_only_is_not_licensed(self):
        # Free Cloud Identity auto-assigns; it must not count as a paid seat
        # for the suspended-licensed or dormancy findings. Premium must.
        self.write_csv("users", f"""{USERS_HEADER}
bob@example.com,True,False,Never,True,True,,False,False,Cloud Identity
prem@example.com,True,False,Never,True,True,,False,False,Cloud Identity Premium
mix@example.com,False,False,Never,True,True,,False,False,Cloud Identity Google Workspace Enterprise Plus (formerly G Suite Enterprise)""")
        findings = ts.check_suspended_holding_data(self.ctx)
        by_id = {f.fid: f for f in findings}
        self.assertEqual(["prem@example.com"],
                         [r["User"] for r in by_id["suspended-licensed"].evidence])
        dormant = ts.check_dormant_accounts(self.ctx)
        by_id = {f.fid: f for f in dormant}
        self.assertEqual(["mix@example.com"],
                         [r["User"] for r in by_id["never-logged-in"].evidence])

    def test_no_suspended_users_no_findings(self):
        self.write_csv("users", f"""{USERS_HEADER}
here@example.com,False,False,2026-08-14T10:00:00Z,True,True,,False,False,Business""")
        self.assertEqual([], ts.check_suspended_holding_data(self.ctx))


class TestOAuthTokenCheck(CtxTestCase):
    def test_full_mail_scope_flagged_and_ranked(self):
        self.write_csv("tokens", """user,clientId,displayText,scopes
a@example.com,c1,Got Your Back,https://mail.google.com/ openid
b@example.com,c1,Got Your Back,https://mail.google.com/
c@example.com,c2,Nice App,https://www.googleapis.com/auth/drive.readonly""")
        findings = ts.check_risky_oauth(self.ctx)
        self.assertEqual(["risky-oauth-apps"], self.finding_ids(findings))
        self.assertEqual("Got Your Back", findings[0].evidence[0]["App"])
        self.assertEqual("2", findings[0].evidence[0]["Users"])

    def test_readonly_drive_scope_not_flagged(self):
        # .../auth/drive must be matched as a whole token, not a prefix of
        # .../auth/drive.readonly.
        self.write_csv("tokens", """user,clientId,displayText,scopes
a@example.com,c2,Nice App,https://www.googleapis.com/auth/drive.readonly""")
        self.assertEqual([], ts.check_risky_oauth(self.ctx))

    def test_full_drive_scope_flagged(self):
        self.write_csv("tokens", """user,clientId,displayText,scopes
a@example.com,c3,Greedy App,https://www.googleapis.com/auth/drive openid""")
        findings = ts.check_risky_oauth(self.ctx)
        self.assertEqual(1, len(findings))


class TestCalendarCheck(CtxTestCase):
    def test_public_calendar_default_scope(self):
        self.write_csv("calendaracls", """primaryEmail,calendarId,role,scope.type,scope.value
a@example.com,a@example.com,reader,default,""")
        ids = self.finding_ids(ts.check_public_calendars(self.ctx))
        self.assertEqual(["public-calendars"], ids)

    def test_domain_reader_is_not_a_finding(self):
        # A domain-wide reader row is the tenant default sharing state.
        self.write_csv("calendaracls", """primaryEmail,calendarId,role,scope.type,scope.value
a@example.com,a@example.com,reader,domain,example.com""")
        self.assertEqual([], ts.check_public_calendars(self.ctx))


class TestDnsCheck(CtxTestCase):
    def test_dmarc_missing_via_doh(self):
        (self.run_dir / "dns.json").write_text(json.dumps({
            "example.com": {"path": "doh", "checks": {
                "mx": {"present": True}, "spf": {"present": True},
                "dkim": {"present": True}, "dmarc": {"present": False}}},
            "alias.example.com": {"path": "doh", "checks": {
                "dmarc": {"present": True}}},
        }), encoding="utf-8")
        findings = ts.check_dns_findings(self.ctx)
        self.assertEqual(["dmarc-missing"], self.finding_ids(findings))
        self.assertEqual(1, findings[0].count)

    def test_no_dns_file_no_finding(self):
        self.assertEqual([], ts.check_dns_findings(self.ctx))

    def test_tamingdns_info_findings_are_not_missing(self):
        # Org-domain inheritance and deprecated-tag notes come back as
        # info-severity findings with status "warn"; that is a present DMARC.
        (self.run_dir / "dns.json").write_text(json.dumps({
            "example.com": {"path": "tamingdns", "checks": {
                "dmarc": {"status": "warn", "findings": [
                    {"severity": "info",
                     "title": "DMARC inherited from organisational domain"}]}}},
        }), encoding="utf-8")
        self.assertEqual([], ts.check_dns_findings(self.ctx))

    def test_tamingdns_fail_status_is_missing(self):
        (self.run_dir / "dns.json").write_text(json.dumps({
            "example.com": {"path": "tamingdns", "checks": {
                "dmarc": {"status": "fail", "findings": [
                    {"severity": "critical", "title": "No DMARC record"}]}}},
        }), encoding="utf-8")
        findings = ts.check_dns_findings(self.ctx)
        self.assertEqual(["dmarc-missing"],
                         [f.fid for f in findings])


import csv as _csv


class PolicyTestCase(CtxTestCase):
    def write_policies(self, settings, broken_rows=()):
        """settings: list of (type, orgUnitPath, value-dict). Writes a
        policies.csv shaped like gam's formatjson output."""
        path = self.run_dir / "policies.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = _csv.writer(fh)
            writer.writerow(["name", "JSON"])
            for i, (stype, ou, value) in enumerate(settings):
                writer.writerow([f"policies/p{i}", json.dumps(
                    {"policyQuery": {"orgUnitPath": ou},
                     "setting": {"type": f"settings/{stype}",
                                 "value": value}})])
            for i, raw in enumerate(broken_rows):
                writer.writerow([f"policies/broken{i}", raw])
        self.ctx.set_module("policies", "ok", len(settings))


class TestPolicyParsing(PolicyTestCase):
    def test_licence_scoped_duplicates_collapse(self):
        value = {"minimumLength": 8}
        self.write_policies([("security.password", "/", value)] * 3)
        parsed = ts._policy_settings(self.ctx)
        self.assertEqual(1, len(parsed))
        self.assertEqual("security.password", parsed[0]["type"])

    def test_distinct_values_all_kept(self):
        self.write_policies([
            ("drive_and_docs.shared_drive_creation", "/",
             {"allowSharedDriveCreation": True}),
            ("drive_and_docs.shared_drive_creation", "/",
             {"allowSharedDriveCreation": False})])
        self.assertEqual(2, len(ts._policy_settings(self.ctx)))

    def test_gam_backslash_quote_artifact_repaired(self):
        # gam formatjson renders a quote inside a DLP rule name as \\",
        # which is invalid JSON after CSV decoding; the parser repairs it.
        broken = ('{"setting": {"type": "settings/rule.dlp", "value": '
                  '{"name": "contains \\\\"Credit card\\\\" data"}}, '
                  '"policyQuery": {"orgUnitPath": "/"}}')
        self.write_policies(
            [("security.password", "/", {"minimumLength": 8})],
            broken_rows=[broken])
        parsed = ts._policy_settings(self.ctx)
        types = {p["type"] for p in parsed}
        self.assertIn("security.password", types)
        self.assertIn("rule.dlp", types)

    def test_unparseable_row_skipped_not_fatal(self):
        self.write_policies(
            [("security.password", "/", {"minimumLength": 8})],
            broken_rows=["{this is not json at all"])
        self.assertEqual(1, len(ts._policy_settings(self.ctx)))


class TestPolicyChecks(PolicyTestCase):
    def test_short_minimum_length_flagged(self):
        self.write_policies([("security.password", "/",
                              {"minimumLength": 8, "allowedStrength": "STRONG",
                               "allowReuse": False})])
        findings = ts.check_password_policy(self.ctx)
        self.assertEqual(["password-policy-weak"], self.finding_ids(findings))
        self.assertIn("minimum length is 8",
                      findings[0].evidence[0]["Problem"])

    def test_strong_long_policy_clean(self):
        self.write_policies([("security.password", "/",
                              {"minimumLength": 14, "allowedStrength": "STRONG",
                               "allowReuse": False})])
        self.assertEqual([], ts.check_password_policy(self.ctx))

    def test_session_beyond_default_flagged(self):
        self.write_policies([("security.session_controls", "/",
                              {"webSessionDuration": "2592000s"})])
        findings = ts.check_session_policy(self.ctx)
        self.assertEqual(["session-length"], self.finding_ids(findings))
        self.assertEqual("30 days", findings[0].evidence[0]["Session length"])

    def test_google_default_session_clean(self):
        self.write_policies([("security.session_controls", "/",
                              {"webSessionDuration": "1209600s"})])
        self.assertEqual([], ts.check_session_policy(self.ctx))

    def test_2sv_enrolment_blocked_is_high_and_map_emitted(self):
        self.write_policies([
            ("security.two_step_verification_enrollment", "/Offboarding",
             {"allowEnrollment": False}),
            ("security.two_step_verification_enforcement", "/Offboarding",
             {"enforcedFrom": "1970-01-01T00:00:00Z"})])
        findings = ts.check_2sv_policy(self.ctx)
        by_id = {f.fid: f for f in findings}
        self.assertEqual({"2sv-enrolment-blocked", "2sv-policy-map"},
                         set(by_id))
        self.assertEqual("HIGH", by_id["2sv-enrolment-blocked"].severity)
        self.assertEqual("/Offboarding",
                         by_id["2sv-enrolment-blocked"].evidence[0]["Org unit"])

    def test_2sv_enrolment_allowed_only_map(self):
        self.write_policies([
            ("security.two_step_verification_enrollment", "/",
             {"allowEnrollment": True})])
        self.assertEqual(["2sv-policy-map"],
                         self.finding_ids(ts.check_2sv_policy(self.ctx)))

    def test_shared_drive_default_external_flagged(self):
        self.write_policies([("drive_and_docs.shared_drive_creation", "/",
                              {"allowExternalUserAccess": True,
                               "allowNonMemberAccess": True})])
        findings = ts.check_sharing_policy(self.ctx)
        self.assertEqual(["sd-default-external"], self.finding_ids(findings))

    def test_locked_shared_drive_default_clean(self):
        self.write_policies([("drive_and_docs.shared_drive_creation", "/",
                              {"allowExternalUserAccess": False,
                               "allowNonMemberAccess": False})])
        self.assertEqual([], ts.check_sharing_policy(self.ctx))

    def test_service_status_map_counts_and_lists_disabled(self):
        self.write_policies([
            ("takeout.service_status", "/", {"serviceState": "ENABLED"}),
            ("blogger.service_status", "/", {"serviceState": "DISABLED"})])
        findings = ts.check_service_status(self.ctx)
        self.assertEqual(["service-status"], self.finding_ids(findings))
        self.assertIn("1 enabled, 1 disabled", findings[0].title)
        self.assertEqual("blogger", findings[0].evidence[0]["Service"])

    def test_no_policies_module_no_findings(self):
        for check in (ts.check_password_policy, ts.check_session_policy,
                      ts.check_2sv_policy, ts.check_sharing_policy,
                      ts.check_service_status):
            self.assertEqual([], check(self.ctx))


class TestLicenceWaste(CtxTestCase):
    DOMAININFO = ("Customer ID: C046t23xk\n"
                  "Primary Domain: dev.osh.co.za\n"
                  "Google Workspace Enterprise Plus Licenses: 50\n"
                  "Cloud Identity Licenses: 100\n"
                  "Users: 7\n")

    def write_domaininfo(self, text=None):
        (self.run_dir / "domaininfo.txt").write_text(
            text if text is not None else self.DOMAININFO, encoding="utf-8")

    def test_parse_owned_licences(self):
        owned = ts.parse_owned_licences(self.DOMAININFO)
        self.assertEqual(50, owned["Google Workspace Enterprise Plus"])
        self.assertEqual(100, owned["Cloud Identity"])

    def test_large_gap_flagged_and_free_cloud_identity_ignored(self):
        self.write_domaininfo()
        self.write_csv("licenses", """userId,productId,productDisplay,skuId,skuDisplay
a@example.com,Google-Apps,Google Workspace,1010020020,Google Workspace Enterprise Plus
b@example.com,101001,Cloud Identity,1010010001,Cloud Identity""")
        findings = ts.check_licence_waste(self.ctx)
        self.assertEqual(["licence-waste"], self.finding_ids(findings))
        self.assertEqual(1, len(findings[0].evidence))
        row = findings[0].evidence[0]
        self.assertEqual("50", row["Seats owned"])
        self.assertEqual("1", row["Assigned"])
        self.assertEqual("49", row["Unused"])

    def test_small_gap_clean(self):
        self.write_domaininfo("Business Starter Licenses: 10\n")
        self.write_csv("licenses", """userId,skuId,skuDisplay
a@example.com,1010020027,Business Starter
b@example.com,1010020027,Business Starter
c@example.com,1010020027,Business Starter
d@example.com,1010020027,Business Starter
e@example.com,1010020027,Business Starter
f@example.com,1010020027,Business Starter""")
        self.assertEqual([], ts.check_licence_waste(self.ctx))

    def test_no_domaininfo_no_finding(self):
        self.write_csv("licenses", """userId,skuId,skuDisplay
a@example.com,1010020020,Google Workspace Enterprise Plus""")
        self.assertEqual([], ts.check_licence_waste(self.ctx))

    def test_unparseable_domaininfo_yields_nothing(self):
        self.write_domaininfo("Customer ID: C1\nSome other line\n")
        self.assertEqual([], ts.check_licence_waste(self.ctx))


ADMINS_HEADER = ("roleAssignmentId,roleId,role,assignedTo,assignedToUser,"
                 "assignedToGroup,assignedToServiceAccount,assignedToUnknown,"
                 "scopeType,orgUnitId,orgUnit")


class TestAdminRoles(CtxTestCase):
    def test_suspended_holder_high_and_unresolved_medium(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-14T10:00:00Z,True,True,,True,False,Business
gone@example.com,True,False,2024-01-01T10:00:00Z,True,True,,False,True,Business""")
        self.write_csv("admins", f"""{ADMINS_HEADER}
1,r1,_SEED_ADMIN_ROLE,111,boss@example.com,,,False,CUSTOMER,,
2,r2,_USER_MANAGEMENT_ADMIN_ROLE,222,gone@example.com,,,False,CUSTOMER,,
3,r1,_SEED_ADMIN_ROLE,333,,,,True,CUSTOMER,,""")
        findings = ts.check_admin_roles(self.ctx)
        by_id = {f.fid: f for f in findings}
        self.assertIn("admin-role-suspended-holder", by_id)
        self.assertEqual("HIGH", by_id["admin-role-suspended-holder"].severity)
        self.assertEqual("gone@example.com",
                         by_id["admin-role-suspended-holder"]
                         .evidence[0]["User"])
        self.assertIn("admin-role-unresolved", by_id)
        self.assertEqual("333", by_id["admin-role-unresolved"]
                         .evidence[0]["Assigned to (ID)"])
        self.assertIn("admin-role-map", by_id)
        self.assertEqual(3, by_id["admin-role-map"].count)

    def test_sprawl_flagged_above_threshold(self):
        users = [f"u{i}@example.com,False,False,2026-08-14T10:00:00Z,"
                 "True,True,,False,False,Business" for i in range(10)]
        self.write_csv("users", USERS_HEADER + "\n" + "\n".join(users))
        admins = [f"{i},r1,ROLE,{i},u{i}@example.com,,,False,CUSTOMER,,"
                  for i in range(3)]
        self.write_csv("admins", ADMINS_HEADER + "\n" + "\n".join(admins))
        by_id = {f.fid: f for f in ts.check_admin_roles(self.ctx)}
        self.assertIn("admin-sprawl", by_id)
        self.assertEqual(3, by_id["admin-sprawl"].count)

    def test_small_tenant_sprawl_not_scored(self):
        # 3 admins of 7 users is normal for a small shop; the sprawl score
        # only applies from ADMIN_SPRAWL_MIN_USERS up.
        users = [f"u{i}@example.com,False,False,2026-08-14T10:00:00Z,"
                 "True,True,,False,False,Business" for i in range(7)]
        self.write_csv("users", USERS_HEADER + "\n" + "\n".join(users))
        admins = [f"{i},r1,ROLE,{i},u{i}@example.com,,,False,CUSTOMER,,"
                  for i in range(3)]
        self.write_csv("admins", ADMINS_HEADER + "\n" + "\n".join(admins))
        ids = self.finding_ids(ts.check_admin_roles(self.ctx))
        self.assertNotIn("admin-sprawl", ids)
        self.assertIn("admin-role-map", ids)

    def test_ou_scoped_role_shows_ou(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-14T10:00:00Z,True,True,,True,False,Business""")
        self.write_csv("admins", f"""{ADMINS_HEADER}
1,r1,HELPDESK,111,boss@example.com,,,False,ORG_UNIT,id:o1,/Sales""")
        by_id = {f.fid: f for f in ts.check_admin_roles(self.ctx)}
        self.assertEqual("OU /Sales",
                         by_id["admin-role-map"].evidence[0]["Scope"])


class TestMissingModules(CtxTestCase):
    def test_checks_skip_when_module_absent(self):
        # No CSVs at all: every check must return [] rather than raise, and
        # the missing modules land on the report's "not checked" list.
        for check in ts.CHECKS:
            self.assertEqual([], check(self.ctx),
                             f"{check.__name__} produced findings with no data")

    def test_errored_module_not_usable(self):
        self.write_csv("forwards", """User,forwardingEnabled,forwardTo
u@example.com,True,x@gmail.com""")
        self.ctx.set_module("forwards", "error", 0, "exit 2: boom")
        self.assertEqual([], ts.check_external_forwarding(self.ctx))


class TestPreflightParsing(unittest.TestCase):
    def test_parse_info_domain(self):
        out = ("Customer ID: C046t23xk\n"
               "Primary Domain: dev.osh.co.za\n"
               "Default Language: en\n")
        info = ts.parse_info_domain(out)
        self.assertEqual("dev.osh.co.za", info["primary_domain"])
        self.assertEqual("C046t23xk", info["customer_id"])

    def test_parse_serviceaccount_pass_and_fail(self):
        out = (
            "System time status\n"
            "        Service Account Private Key Authentication: PASS\n"
            "https://www.googleapis.com/auth/calendar, PASS (1/3)\n"
            "https://www.googleapis.com/auth/gmail.settings.basic, FAIL (2/3)\n"
            "https://www.googleapis.com/auth/drive, PASS (3/3)\n"
            "Some scopes FAILED!\n")
        passed, failed = ts.parse_serviceaccount_check(out)
        self.assertIn("https://www.googleapis.com/auth/calendar", passed)
        self.assertIn("https://www.googleapis.com/auth/gmail.settings.basic",
                      failed)
        self.assertNotIn("https://www.googleapis.com/auth/gmail.settings.basic",
                         passed)

    def test_header_only_detection(self):
        self.assertTrue(ts.is_header_only("Owner,id,name\n"))
        self.assertTrue(ts.is_header_only(""))
        self.assertFalse(ts.is_header_only("Owner,id\nme,1\n"))


class TestHelpers(unittest.TestCase):
    def test_col_is_case_insensitive(self):
        row = {"primaryEmail": "a@b.c", "isEnrolledIn2Sv": "True"}
        self.assertEqual("a@b.c", ts.col(row, "primaryemail"))
        self.assertEqual("True", ts.col(row, "isenrolledin2sv"))
        self.assertEqual("", ts.col(row, "missing"))

    def test_email_domain(self):
        self.assertEqual("example.com", ts.email_domain("A@Example.COM"))
        self.assertEqual("", ts.email_domain("not-an-email"))

    def test_external_pm_args_uses_notdomainlist(self):
        # `pm not domain "d1,d2"` matches every ACL (domain takes a single
        # regex); the recipe must use notdomainlist instead.
        args = ts.external_pm_args(["b.com", "a.com"])
        self.assertNotIn("not", args)
        self.assertEqual(2, args.count("notdomainlist"))
        self.assertIn("a.com,b.com", args)


class TestManifestResume(CtxTestCase):
    def test_manifest_roundtrip(self):
        self.ctx.set_module("users", "ok", 7)
        ctx2 = ts.RunContext(self.run_dir, make_args())
        self.assertEqual("ok", ctx2.module_status("users"))
        self.assertEqual(["example.com", "alias.example.com"],
                         self.ctx.internal_domains)

    def test_internal_domains_persist(self):
        self.ctx.internal_domains = ["x.com"]
        self.ctx.save()
        ctx2 = ts.RunContext(self.run_dir, make_args())
        self.assertEqual(["x.com"], ctx2.internal_domains)

    def test_corrupt_manifest_starts_fresh(self):
        (self.run_dir / "manifest.json").write_text("{not json",
                                                    encoding="utf-8")
        ctx2 = ts.RunContext(self.run_dir, make_args())
        self.assertEqual("", ctx2.module_status("users"))


class TestModuleSelection(unittest.TestCase):
    def test_default_excludes_tier4(self):
        keys = {m["key"] for m in ts.selected_modules(make_args())}
        self.assertIn("users", keys)
        self.assertIn("dns", keys)
        self.assertNotIn("filters", keys)

    def test_full_includes_tier4(self):
        keys = {m["key"] for m in ts.selected_modules(make_args(full=True))}
        self.assertIn("filters", keys)
        self.assertIn("caalevels", keys)

    def test_only(self):
        keys = {m["key"] for m in
                ts.selected_modules(make_args(only="users,groups"))}
        self.assertEqual({"users", "groups"}, keys)

    def test_skip_tier(self):
        keys = {m["key"] for m in
                ts.selected_modules(make_args(skip_tier="2,3"))}
        self.assertNotIn("sendas", keys)
        self.assertNotIn("mydrive_external", keys)
        self.assertIn("users", keys)

    def test_no_dns(self):
        keys = {m["key"] for m in ts.selected_modules(make_args(no_dns=True))}
        self.assertNotIn("dns", keys)


class TestDeriveInternalDomains(CtxTestCase):
    def test_domains_and_aliases_merge(self):
        self.write_csv("domains", """domainName,verified,type
example.com,True,primary
alias.example.com,True,alias""")
        self.write_csv("domainaliases", """domainAliasName,parentDomainName,verified
extra.example.com,example.com,True""")
        self.ctx.internal_domains = []
        ts.derive_internal_domains(self.ctx)
        self.assertEqual(["alias.example.com", "example.com",
                          "extra.example.com"],
                         self.ctx.internal_domains)


class TestBackupCodesRedaction(CtxTestCase):
    def test_live_codes_never_reach_disk(self):
        gam_output = ("User,verificationCodes,verificationCodesCount\n"
                      "a@example.com,12345678 87654321,8\n")
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (0, gam_output, "")
        try:
            status, rows, note = ts.collect_backupcodes(
                self.ctx, ts.MODULE_BY_KEY["backupcodes"])
        finally:
            ts.run_gam = original
        self.assertEqual("ok", status)
        written = (self.run_dir / "backupcodes.csv").read_text(
            encoding="utf-8")
        self.assertNotIn("12345678", written)
        self.assertIn("verificationCodesCount", written)
        self.assertIn("8", written)


class TestCollectSimple(CtxTestCase):
    def test_exit_60_header_only_is_empty(self):
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (60, "Owner,id,name\n", "no rows")
        try:
            status, rows, note = ts.collect_simple(
                self.ctx, ts.MODULE_BY_KEY["userinvitations"])
        finally:
            ts.run_gam = original
        self.assertEqual("empty", status)
        self.assertEqual(0, rows)

    def test_partial_output_is_kept(self):
        # `all users print X` exits 73 when one user has Gmail disabled but
        # still emits the other users' rows; those rows must not be lost.
        gam_output = ("User,forwardingEnabled,forwardTo\n"
                      "a@example.com,False,\n"
                      "b@example.com,True,x@gmail.com\n")
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (
            73, gam_output,
            "User: dead@example.com, Gmail Service/App not enabled (4/4)")
        try:
            status, rows, note = ts.collect_simple(
                self.ctx, ts.MODULE_BY_KEY["forwards"])
        finally:
            ts.run_gam = original
        self.assertEqual("partial", status)
        self.assertEqual(2, rows)
        self.assertIn("exit 73", note)
        written = (self.run_dir / "forwards.csv").read_text(encoding="utf-8")
        self.assertIn("b@example.com", written)
        # And a partial module still feeds the checks engine.
        self.ctx.set_module("forwards", status, rows, note)
        ids = [f.fid for f in ts.check_external_forwarding(self.ctx)]
        self.assertEqual(["external-forwarding"], ids)

    def test_header_only_with_user_skip_is_partial(self):
        # Nobody has forwarding set AND one user has Gmail disabled: GAM
        # emits a bare header and exits 73. Partial-empty, not an error.
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (
            73, "User,forwardingEnabled,forwardTo\n",
            "User: dead@example.com, Gmail Service/App not enabled (4/4)")
        try:
            status, rows, note = ts.collect_simple(
                self.ctx, ts.MODULE_BY_KEY["forwards"])
        finally:
            ts.run_gam = original
        self.assertEqual("partial", status)
        self.assertEqual(0, rows)
        self.assertTrue((self.run_dir / "forwards.csv").is_file())

    def test_browsers_forbidden_is_skipped(self):
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (
            50, "", "ERROR: Chrome Browser Print Failed: Forbidden")
        try:
            status, rows, note = ts.collect_simple(
                self.ctx, ts.MODULE_BY_KEY["browsers"])
        finally:
            ts.run_gam = original
        self.assertEqual("skipped", status)
        self.assertIn("not authorised", note)

    def test_swm_external_filters_on_owner_domain(self):
        # The recipient of an externally-owned file sees no permissions
        # array, so pm filters can't decide externality — the collector
        # must keep/drop rows on owners.0.emailAddress in Python.
        self.write_csv("users", USERS_HEADER + "\n"
                       "u@example.com,False,False,2026-01-01T00:00:00Z,"
                       "True,True,r@x.com,False,False,Workspace")
        gam_output = (
            "Owner,id,name,owners,owners.0.emailAddress,sharedWithMeTime\n"
            "u@example.com,f1,ext.txt,1,paul@outside.co.za,2026-08-15T15:38:35Z\n"
            "u@example.com,f2,int.txt,1,other@example.com,2026-08-15T15:38:35Z\n")
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (0, gam_output, "")
        try:
            status, rows, note = ts.collect_swm_external(
                self.ctx, ts.MODULE_BY_KEY["sharedwithme_external"])
        finally:
            ts.run_gam = original
        self.assertEqual("ok", status)
        self.assertEqual(1, rows)
        written = (self.run_dir /
                   "sharedwithme_external.csv").read_text(encoding="utf-8")
        self.assertIn("paul@outside.co.za", written)
        self.assertNotIn("other@example.com", written)

    def test_real_failure_is_error(self):
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (2, "", "ERROR: something broke")
        try:
            status, rows, note = ts.collect_simple(
                self.ctx, ts.MODULE_BY_KEY["userinvitations"])
        finally:
            ts.run_gam = original
        self.assertEqual("error", status)
        self.assertIn("something broke", note)

    def test_caalevels_gcp_error_is_skipped_not_authorised(self):
        original = ts.run_gam
        ts.run_gam = lambda *a, **k: (
            2, "", "Please grant service account the Access Context Manager "
                   "Editor role in your GCP organization.")
        try:
            status, rows, note = ts.collect_simple(
                self.ctx, ts.MODULE_BY_KEY["caalevels"])
        finally:
            ts.run_gam = original
        self.assertEqual("skipped", status)
        self.assertIn("not authorised", note)


class TestRender(CtxTestCase):
    def test_report_is_self_contained_and_lists_not_checked(self):
        self.ctx.manifest["meta"]["primary_domain"] = "example.com"
        self.ctx.manifest["preflight"] = [["GAM7 binary", "found", "-"]]
        self.ctx.set_module("sendas", "skipped", 0,
                            "not authorised: DWD scope missing")
        findings = [ts.Finding(
            "test", "CRITICAL", "Something <bad> & risky",
            "It means trouble.", "Fix it.",
            [{"User": "a@example.com"}], "users.csv")]
        out = ts.render_html(self.ctx, findings)
        html = out.read_text(encoding="utf-8")
        self.assertIn("Something &lt;bad&gt; &amp; risky", html)
        self.assertIn("Not checked", html)
        self.assertIn("not authorised: DWD scope missing", html)
        # Self-contained: no external stylesheet/script/image references.
        self.assertNotIn("<script src", html)
        self.assertNotIn("<link", html)
        self.assertNotIn("<img", html)
        self.assertTrue((self.run_dir / "findings.csv").is_file())

    def test_findings_sorted_by_severity_in_run_checks(self):
        self.write_csv("users", f"""{USERS_HEADER}
boss@example.com,False,False,2026-08-01T10:00:00Z,False,False,,True,False,Business""")
        findings = ts.run_checks(self.ctx)
        severities = [f.severity for f in findings]
        self.assertEqual(severities,
                         sorted(severities,
                                key=ts.SEVERITY_ORDER.index))


class TestDohFallbackParsing(unittest.TestCase):
    def test_doh_fallback_shapes(self):
        answers = {
            ("example.com", "MX"): ["10 smtp.google.com."],
            ("example.com", "TXT"): ["v=spf1 include:_spf.google.com ~all"],
            ("google._domainkey.example.com", "TXT"): [],
            ("_dmarc.example.com", "TXT"): [],
        }
        original = ts.doh_query
        ts.doh_query = lambda name, rtype, timeout=10: answers.get(
            (name, rtype), [])
        try:
            result = ts.doh_fallback("example.com")
        finally:
            ts.doh_query = original
        self.assertTrue(result["checks"]["mx"]["present"])
        self.assertTrue(result["checks"]["spf"]["present"])
        self.assertFalse(result["checks"]["dkim"]["present"])
        self.assertFalse(result["checks"]["dmarc"]["present"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
