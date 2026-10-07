# Google Workspace Admin Scripts for GAM7 (GoogleWorkspaceScripts)

This repository was called GAMScripts until October 2026. Old links redirect here.

Free, open-source Python and bash tools for **Google Workspace (formerly G Suite)
administration with GAM7 (Google Apps Manager)**: a read-only tenant security
audit, automated employee offboarding, a safety checker that says what a GAM
command does before you run it, GYB mailbox backup checks, a safe GAM7
updater, and utilities for oversized GAM CSV exports. Standard library only,
nothing to install beyond Python and GAM7.

Anything that makes changes has a safe default: the offboarding script is a
dry run until you pass `--doit`, and the audit, checker and GYB tools are
read-only.

Built and maintained by Paul Ogier, [Outsource House](https://osh.co.za).
Training at [Taming.Tech](https://taming.tech).

## The scripts

| Script | What it does |
| --- | --- |
| [**Google Workspace Security Audit**](google-workspace-security-audit/README.md) (`tenant_scope.py`) | Free, read-only Google Workspace security audit that renders a self-contained HTML report. Finds files public on the web and shared externally, mailboxes forwarding off-domain, super admins without 2-step verification, orphaned Shared Drives, dormant licensed accounts, licence waste, admin-role sprawl, risky third-party OAuth apps, and missing MX/SPF/DKIM/DMARC per domain. For day-one client scoping, a security-uplift baseline, pre-migration inventory, or acquisition due diligence. |
| [**Google Workspace User Offboarding**](google-workspace-offboarding/README.md) (`offboard_user.py`) | Automated Google Workspace employee offboarding in one run: pre-flight snapshot, containment (sign-out, password reset, token revocation), device review, group and delegate cleanup, licence recovery, Drive, calendar and alias transfer, mailbox migration or backup with GYB, forwarding and auto-reply, suspension last. Dry-run by default; ships with a no-code [command builder](google-workspace-offboarding/offboarding_command_builder.html). |
| [**GAM Script Checker**](gam-script-checker/README.md) (`gamcheck.py`) | Paste a gam command or point it at a script, and it tells you whether it only reads, changes, or deletes, before you run it. It never runs anything. For anyone about to run a command from a forum or an AI chat that they have not fully read. In testing: it can miss things. |
| [**GYB Gmail Backup Tools**](gyb-gmail-backup-tools/README.md) (`gyb_backup_doctor.py`, `gyb_header_scan.py`) | Check a [GYB](https://github.com/GAM-team/got-your-back) mailbox backup before you trust it: is it really a backup, how much is on disk, how far each restore got, and which message's oversized headers aborted an import. Read-only. |
| [**Mbox to EML**](mbox-to-eml/README.md) (`mbox_to_eml.py`, `mbox_vs_gam_diff.py`) | Open any mbox (Google Takeout, Vault, Thunderbird, Apple Mail) as one .eml per message, with filenames safe on Windows, macOS and Linux and no converter needed. For a mailbox split, prove a Vault mbox export holds exactly the messages you labelled with GAM, with drafts, Trash purges and label drift named. Read-only. |
| [**GAM7 Update**](gam7-update/README.md) (`gam-update.sh`) | A safety wrapper around GAM7's official installer: asks GAM whether it is behind, takes a rollback copy, then verifies the upgrade landed. Safe in cron. macOS and Linux; Windows users want [NoSubstitute/gamupdate](https://github.com/NoSubstitute/gamupdate). |
| [**Split GAM Calendar CSV**](split-gam-calendar-csv/README.md) (`split_by_size.py`, `filter_and_split.py`, `split_csv.py`) | Break up GAM calendar exports too big for Google Sheets or Excel: split by size, filter each user's recent events, or write one CSV per user. |

Each folder's README has the full feature list, flags and exit codes.

## Who this is for

- **Google Workspace administrators** who already use GAM7 and want tested
  scripts for the jobs the Admin console makes slow: audits, offboarding,
  bulk exports.
- **Managed service providers (MSPs) and IT consultants** who look after many
  tenants and need the same result on every one, with a log.
- **Anyone learning GAM** who wants working, commented examples of GAM7
  commands in real workflows.

## Prerequisites

* **Python 3.8+** (`python3 --version`); the audit and the checker need 3.9+
* **[GAM7](https://github.com/GAM-team/GAM/wiki)**, installed, configured and
  authorised against your domain. GAMADV-XTD3 users should upgrade; the
  [GAM7 Update](gam7-update/README.md) script does that safely.

No third-party packages: everything here is standard library only.

## Quick start

```
git clone https://github.com/PaulOgier/GoogleWorkspaceScripts.git
cd GoogleWorkspaceScripts/google-workspace-security-audit
python3 tenant_scope.py --admin admin@yourdomain.com
```

Every script prints what it would do before it does anything, and the audit
never changes the tenant at all.

## The course

If you want to go deeper on GAM, the Udemy course
[Taming GAM7 & GAMADV-XTD3: A Google Workspace Admin Guide](https://taming.tech/GAMCourse)
walks through administering Workspace efficiently and securely, step by step.

## Contributing

> **Safety first.** Some of these scripts perform destructive admin actions: suspending and deleting users, transferring data, bulk operations against a live tenant. **Always test against a non-production domain. Never test against a live tenant.**

Open an issue first for anything significant, then fork, branch, and open a
PR. Keep new scripts consistent with the existing style: PEP 8, a header
comment explaining what the script does, and a dry-run or safe default for
anything that makes changes.

## Credits

[**Gavin-X**](https://github.com/Gavin-X) read `offboard_user.py` closely and
filed twelve defects across two rounds, issues
[#2](https://github.com/PaulOgier/GoogleWorkspaceScripts/issues/2) to
[#6](https://github.com/PaulOgier/GoogleWorkspaceScripts/issues/6) and
[#9](https://github.com/PaulOgier/GoogleWorkspaceScripts/issues/9) to
[#15](https://github.com/PaulOgier/GoogleWorkspaceScripts/issues/15), with nine pull
requests ([#7](https://github.com/PaulOgier/GoogleWorkspaceScripts/pull/7),
[#8](https://github.com/PaulOgier/GoogleWorkspaceScripts/pull/8),
[#20](https://github.com/PaulOgier/GoogleWorkspaceScripts/pull/20) to
[#26](https://github.com/PaulOgier/GoogleWorkspaceScripts/pull/26)), including the
admin-account safety gate in v5.4.0. Most of them ended a run in a state the
operator could not see, which is the kind of bug you only find by reading the
code rather than running it. Thank you.

Dirk Grobler's question on the
[google-apps-manager group](https://groups.google.com/g/google-apps-manager/c/9r_AeuiWOSg)
is why the security audit is public.

## Licence

Apache-2.0. See [`LICENSE`](LICENSE).

## Contact

Paul Ogier, Outsource House and Taming.Tech.

* [paul@osh.co.za](mailto:paul@osh.co.za) / [osh.co.za](https://osh.co.za/?utm_source=github&utm_medium=readme&utm_campaign=googleworkspacescripts&utm_content=contact)
* [paul@taming.tech](mailto:paul@taming.tech) / [taming.tech](https://taming.tech/?utm_source=github&utm_medium=readme&utm_campaign=googleworkspacescripts&utm_content=contact)
