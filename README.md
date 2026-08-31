# Google Workspace & GAM Automation Scripts 🚀

Python and bash tools for **Google Workspace administration** with **GAM7 (Google Apps Manager)** — offboarding, tenant auditing, mailbox-backup checks, bulk CSV work, and keeping GAM itself current.

Anything that makes changes has a safe default: `offboard_user.py` is dry-run until you pass `--doit`, and the audit and GYB tools are read-only.

## 📚 The scripts

| Script | What it does |
| --- | --- |
| [**User Offboarding**](OffBoarding%20Google%20Workspace%20Users/) — `offboard_user.py` | The full offboarding workflow in one run: snapshot, containment, device review, group and delegate cleanup, licence recovery, Drive/calendar/alias transfer, forwarding and auto-reply, suspension last. Dry-run by default; ships with a no-code [command builder](OffBoarding%20Google%20Workspace%20Users/offboarding_command_builder.html). |
| [**Tenant Scoping Audit**](Tenant%20Scoping%20Audit/) — `tenant_scope.py` | Read-only tenant audit that renders a self-contained HTML report. Public files, external forwarding, admins without 2SV, orphaned Shared Drives, dormant licensed accounts, licence waste, admin-role sprawl, per-domain MX/SPF/DKIM/DMARC. For day-one scoping, a security-uplift baseline, or acquisition due diligence. |
| [**GYB Mailbox Tools**](GYB%20Mailbox%20Tools/) — `gyb_backup_doctor.py`, `gyb_header_scan.py` | Check a [GYB](https://github.com/GAM-team/got-your-back) mailbox backup before you trust it: is it really a backup, how much is on disk, how far each restore got, and which message's oversized headers aborted an import. Read-only. |
| [**GAM7 Update**](GAM7%20Update/) — `gam-update.sh` | A safety wrapper around GAM7's official installer: asks GAM whether it is behind, takes a rollback copy, then verifies the upgrade landed. Safe in cron. macOS and Linux; Windows users want [NoSubstitute/gamupdate](https://github.com/NoSubstitute/gamupdate). |
| [**Split Calendar CSV Events**](Split%20Calendar%20CSV%20Events/) — `split_by_size.py`, `filter_and_split.py`, `split_csv.py` | Break up GAM calendar exports too big for Sheets or Excel: split by size, filter each user's recent events, or write one CSV per user. |

Each folder's README has the full feature list, flags and exit codes.

## 🔧 Prerequisites

* **Python 3.6+** (`python3 --version`)
* **[GAM7](https://github.com/GAM-team/GAM/wiki)** or **[GAMADV-XTD3](https://github.com/taers232c/GAMADV-XTD3)**, installed, configured and authorised against your domain

No third-party packages: everything here is standard library only.

## 🎓 The course

If you want to go deeper on GAM, the Udemy course [Taming GAM7 & GAMADV-XTD3 — A Google Workspace Admin Guide](https://taming.tech/GAMCourse) walks through administering Workspace efficiently and securely, step by step.

## 🤝 Contributing

> ⚠️ **Safety first.** These scripts perform destructive admin actions — suspending and deleting users, transferring data, bulk operations against a live tenant. **Always test against a non-production domain. Never test against a live tenant.**

Open an issue first for anything significant, then fork, branch, and open a PR. Keep new scripts consistent with the existing style: PEP 8, a header comment explaining what the script does, and a dry-run / safe default for anything that makes changes.

## 🙏 Credits

[**Gavin-X**](https://github.com/Gavin-X) read `offboard_user.py` closely and filed twelve defects across two rounds — issues [#2](https://github.com/PaulOgier/GAMScripts/issues/2)–[#6](https://github.com/PaulOgier/GAMScripts/issues/6) and [#9](https://github.com/PaulOgier/GAMScripts/issues/9)–[#15](https://github.com/PaulOgier/GAMScripts/issues/15) — with nine pull requests ([#7](https://github.com/PaulOgier/GAMScripts/pull/7), [#8](https://github.com/PaulOgier/GAMScripts/pull/8), [#20](https://github.com/PaulOgier/GAMScripts/pull/20)–[#26](https://github.com/PaulOgier/GAMScripts/pull/26)), including the admin-account safety gate in v5.4.0. Most of them ended a run in a state the operator could not see, which is the kind of bug you only find by reading the code rather than running it. Thank you.

## 📜 License

Apache-2.0. See [`LICENSE`](LICENSE).

## 📧 Contact

Paul Ogier, OSH.co.za and Taming.Tech.

* [paul@osh.co.za](mailto:paul@osh.co.za) / [osh.co.za](https://osh.co.za/?utm_source=github&utm_medium=readme&utm_campaign=gamscripts&utm_content=contact)
* [paul@taming.tech](mailto:paul@taming.tech) / [taming.tech](https://taming.tech/?utm_source=github&utm_medium=readme&utm_campaign=gamscripts&utm_content=contact)
