# 🎓 Master GAM7 & GAMADV-XTD3 with an In-Depth Course

If you want to become an expert in Google Workspace administration, check out the comprehensive Udemy course: [Taming GAM7 & GAMADV-XTD3 - A Google Workspace Admin Guide](https://taming.tech/GAMCourse).

This course is designed to teach you how to administer Google Workspace more efficiently and effectively. It logically breaks down all the steps to ensure the optimum administration and security of your environment, making you more productive in your role.

# Google Workspace & GAM Automation Scripts 🚀

Welcome! This repository is a collection of powerful and easy-to-use Python scripts designed to supercharge your **Google Workspace administration** by leveraging the incredible capabilities of **GAM7 (Google Apps Manager)**.

Whether you're looking to perform **bulk operations**, process large CSV reports, or automate repetitive tasks, these scripts are here to save you time and prevent headaches.

---

## 🔧 Prerequisites

Before you begin, make sure you have the following installed and configured:

1.  **Python 3**: These scripts are written for Python 3.6 or newer. You can check your version with `python3 --version`.
2.  **GAMADV-XTD3 or GAM7**: The latest and most powerful version of GAM. Ensure it's properly installed, configured, and authorized to access your Google Workspace domain. You can find it here: [GAMADV-XTD3 GitHub Repository](https://github.com/taers232c/GAMADV-XTD3) or [GAM7 GitHub Repository](https://github.com/GAM-team/GAM/wiki).

---

## 📚 Scripts Library

Here is a breakdown of the available scripts. Each script is designed to solve a specific problem.

### **1. OffBoarding Google Workspace Users \ User Offboarding Script (`offboard_user.py`)**

* **Description**: A comprehensive, cross-platform Python script that automates the full Google Workspace user offboarding workflow using GAM7. Runs in **dry-run mode by default** — no changes are made until you pass `--doit`.
* **Best For**: Safely and consistently offboarding departing employees, covering security containment, data transfers, licence recovery, and audit logging in a single automated run.
* **Key Features**:
  * Pre-flight snapshot — exports the user's full state to JSON before any changes (audit trail)
  * Kill switch — moves user to Offboarding OU, wipes recovery details, resets password, and deprovisions app tokens
  * Device management — detects and lists mobile and ChromeOS devices for manual review
  * Group & delegate cleanup — removes group memberships and inbound/outbound delegates
  * Licence removal — frees up seats before suspension
  * Data transfers — Drive, aliases, and calendar ownership transferred to a successor
  * Email forwarding & auto-reply — notifies senders and routes mail to successor
  * Already-suspended users — detects suspension at start and offers to temporarily unsuspend for full offboarding, then re-suspends automatically at the end
  * Suspension last — ensures all GAM operations complete before the account is locked
  * Logs written to `logs/` subfolder by default (overridable with `--log-dir`)
  * Detailed phase-by-phase summary with timing and exit codes (`0`=success, `1`=errors, `2`=fatal)
* **Usage**:
    ```bash
    # Dry run (default — no changes made)
    python3 offboard_user.py

    # Execute offboarding
    python3 offboard_user.py --doit

    # Skip specific phases
    python3 offboard_user.py --doit --no-devices --no-drive

    # Non-interactive (scripted use)
    python3 offboard_user.py --doit --force --user user@yourdomain.com

    # Offboard an already-suspended user (unsuspend, offboard, re-suspend)
    python3 offboard_user.py --doit --unsuspend --user user@yourdomain.com

    # Custom log directory
    python3 offboard_user.py --doit --log-dir /var/log/offboarding
    ```
* **Command builder (no-code helper)**: If you don't want to hand-craft the command line, open `OffBoarding Google Workspace Users/offboarding_command_builder.html` in any browser. It is a single self-contained HTML page (no server, no install, works offline) that turns every flag into a form field, with inline help text for each one. Fill in the leaving user, successor, domain, and any phase toggles, and the page renders the exact `python3 offboard_user.py ...` command for you to copy. Useful for admins who only run an offboarding occasionally and don't want to re-read the flag list every time.
* **Additional Requirements**: GYB (optional, for email migration only). See `offboarding_test_setup_guide.md` for a full test environment setup guide, and `installation_macos.md` / `installation_windows.md` for the one-time GAM7 + GYB + rclone install.

<br>

### **2. Split Calendar CSV Events (`split_by_size.py`, `filter_and_split.py`, `split_csv.py`)**

* **Description**: A set of three utilities for working with large GAM calendar CSV exports. Split a massive CSV into size-limited chunks (`split_by_size.py`), filter and extract each user's recent events into individual files (`filter_and_split.py`), or create a separate CSV per user from a multi-user export (`split_csv.py`).
* **Best For**: Auditing calendar activity, preparing per-user data for compliance or archival purposes, and breaking down large GAM reports that are too big for Google Sheets or Excel.
* **Usage**:
    ```bash
    # Split a large CSV into chunks (default 5 MB each)
    python3 split_by_size.py <input_file.csv> [max_size_in_mb]

    # Filter events per user for a recent period
    python3 filter_and_split.py <input_file.csv> <days_ago>

    # Create one CSV per user from a multi-user export
    python3 split_csv.py <input_file.csv>
    ```

<br>

### **3. GYB Mailbox Tools (`gyb_backup_doctor.py`, `gyb_header_scan.py`)**

* **Description**: Two read-only utilities for inspecting [GYB (Got Your Back)](https://github.com/GAM-team/got-your-back) mailbox backups. `gyb_backup_doctor.py` reports whether a folder is really a GYB backup, how much of it is on disk, and how far each restore got. `gyb_header_scan.py` finds the messages whose headers exceed Gmail's import limit and names the files.
* **Best For**: Checking a mailbox backup before you rely on it, and diagnosing a restore that either died halfway or finished suspiciously fast. Useful alongside `offboard_user.py`, but they work on any GYB backup.
* **Key Features**:
  * Names the "restore did nothing" trap: GYB treats a folder as a backup purely by the presence of `msg-db.sqlite`, and without it `--action restore` finds nothing and exits `0` in seconds
  * Reconciles the message database against the `.eml` files on disk, so an incomplete backup is caught before it becomes an incomplete migration
  * Accounts for quarantined files separately, so a handled antivirus quarantine does not read as data loss
  * Reports restore progress per destination from GYB's own resume database
  * Finds the single oversized header that aborts a restore without GYB ever saying which message it was
  * Read-only throughout: databases are opened in SQLite `ro` mode and backups are never written to
* **Usage**:
    ```bash
    # Check a backup before trusting it
    python3 gyb_backup_doctor.py /path/to/GYB-GMail-Backup-user@domain.com

    # Also probe every file for antivirus locks
    python3 gyb_backup_doctor.py --probe-reads /path/to/backup

    # Find messages Gmail will reject on import
    python3 gyb_header_scan.py /path/to/backup
    ```
* **Additional Requirements**: None beyond Python 3. Standard library only, and GYB itself is not needed to run them. See `GYB Mailbox Tools/README.md` for what to do with each answer.

<br>

### **4. Tenant Scoping Audit (`tenant_scope.py`)**

* **Description**: A read-only Google Workspace tenant audit in a single Python file. Collects tenant and security-posture data through GAM7, runs a findings engine over it, and renders a self-contained HTML report (print it for a PDF) with plain-English "what this means" and "what to do" copy per finding.
* **Best For**: Day-one scoping of a tenant you have just taken over, a pre-migration or security-uplift baseline, and due-diligence gap reports when a company is being acquired and the buyer wants to know where the holes are.
* **Key Features**:
  * Read-only throughout, with one opt-in exception (`--grant-temp-access`) that grants itself Shared Drive access, scans, and removes the grant again
  * Preflight confirms the tenant (primary domain + customer ID) before anything is collected, so you never audit the wrong tenant
  * Findings ranked CRITICAL to INFO: public files, external forwarding, admins without 2SV, orphaned Shared Drives, dormant licensed accounts, per-OU 2SV policy gaps, licence waste, admin-role sprawl, and more
  * Every finding traceable to a raw CSV; anything that could not be checked is listed in the report rather than silently absent
  * Resumable runs: skip the heavy Drive scans on the first pass, rerun with `--run-dir` later and only the missing modules execute
  * Per-domain MX/SPF/DKIM/DMARC checks via tamingdns.com, with a dns.google fallback
  * 104 unit tests, standard library only, Windows/macOS/Linux
* **Usage**:
    ```bash
    # Show the module registry
    python3 tenant_scope.py --list

    # Default audit (tiers 1-3 + DNS)
    python3 tenant_scope.py --admin admin@yourdomain.com

    # Skip the heavy Drive scans, fill them in later
    python3 tenant_scope.py --admin admin@yourdomain.com --skip-tier 3
    python3 tenant_scope.py --admin admin@yourdomain.com --run-dir <dir>

    # Re-render the report from collected data, no GAM calls
    python3 tenant_scope.py --render-only --run-dir <dir>
    ```
* **Additional Requirements**: None beyond Python 3 and an authorised GAM7. See `Tenant Scoping Audit/README.md` for the full check list and the safety posture.

---

### **5. GAM7 Update (`gam-update.sh`)**

* **Description**: A safety wrapper around GAM7's official installer. Downloads and runs [`gam-install.sh`](https://raw.githubusercontent.com/GAM-team/GAM/master/src/gam-install.sh) in upgrade mode. The upgrade itself is upstream's work; this adds a version check, a rollback copy and a verification pass around it. **GAM7 only; GAMADV-XTD3 has its own installer and install folder.** This script is bash, so Windows users want [NoSubstitute/gamupdate](https://github.com/NoSubstitute/gamupdate) instead.
* **Best For**: Keeping GAM current without the risk of an interrupted upgrade leaving you with no working `gam`, and for anyone who wants an upgrade step that is safe to run on a schedule.
* **Key Features**:
  * Asks GAM itself (`gam version checkrc`) whether it is behind, so there is no GitHub API call and no rate limit. Exits `0` with "already current" when it is up to date, making it safe in cron or a login script
  * Treats a version check that could not run as an error, never as "already current". That is the failure mode that silently skips upgrades forever
  * Copies the whole install to `<dir>.bak-<old version>` first, because the official installer deletes `lib/` and extracts over the top with no undo
  * Asks GAM again after upgrading and fails if it still reports itself behind
  * Prints `gam info domain` at the end, so which tenant your config points at is on screen before the first real command
  * Credentials untouched: `~/.gam` and the `config_dir` it points at sit outside the install folder
  * Bash and curl; the official installer it runs needs Python 3, which GAM itself already requires
  * macOS and Linux, both tested end to end (macOS Tahoe 26.5 arm64 and Ubuntu 25.10 aarch64)
* **Usage**:
    ```bash
    # Dry run: print installed vs latest, change nothing
    ./gam-update.sh -n

    # Upgrade
    ./gam-update.sh

    # Non-default install location
    ./gam-update.sh -d /opt/gam7
    ```
* **Additional Requirements**: None. Ships with `test-gam-update.sh`, a self-check that needs no GAM install and no network. See `GAM7 Update/README.md` for the rollback command and exit codes.

---

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

> ⚠️ **Safety first.** These scripts perform destructive admin actions — suspending and deleting users, transferring data, and running bulk operations against a live Google Workspace tenant. **Always test your changes against a non-production / test domain before opening a PR. Never test against a live tenant.**

**Before you start:** Make sure you have the [Prerequisites](#-prerequisites) in place — Python 3.6+ and a configured, authorized GAM7 / GAMADV-XTD3 install. For significant changes, please open an issue first so we can discuss the approach before you sink time into a PR.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

Please keep new scripts consistent with the existing style: PEP 8, a clear header comment explaining what the script does, and a **dry-run / safe default** (like `offboard_user.py`'s `--doit` flag) for anything that makes changes.

---

## 🙏 Credits

[**Gavin-X**](https://github.com/Gavin-X) read `offboard_user.py` closely and filed five defects against it: [#2](https://github.com/PaulOgier/GAMScripts/issues/2), a preflight failure could leave a suspended account active; [#3](https://github.com/PaulOgier/GAMScripts/issues/3), failed transfers did not stop licence removal and suspension; [#4](https://github.com/PaulOgier/GAMScripts/issues/4), source and destination could be the same account; [#5](https://github.com/PaulOgier/GAMScripts/issues/5), a containment failure could leave an account accessible; and [#6](https://github.com/PaulOgier/GAMScripts/issues/6), dead code and confusing phase numbering. They also opened PRs [#7](https://github.com/PaulOgier/GAMScripts/pull/7) and [#8](https://github.com/PaulOgier/GAMScripts/pull/8) with proposed fixes. All five were valid, and all five are fixed in v5.2.0 and v5.3.0. Most of them ended a run in a state the operator could not see, which is the kind of bug you only find by reading the code rather than running it. Thank you.

They came back for a second round: seven more reports (issues [#9](https://github.com/PaulOgier/GAMScripts/issues/9)–[#15](https://github.com/PaulOgier/GAMScripts/issues/15)) spanning the script, the Windows installation guide, and the command builder, this time with seven working pull requests ([#20](https://github.com/PaulOgier/GAMScripts/pull/20)–[#26](https://github.com/PaulOgier/GAMScripts/pull/26)) — including the admin-account safety gate that headlines v5.4.0. All seven PRs were merged as submitted after review and a live test round. Thank you again.

---

## 📜 License

Distributed under the Apache-2.0 license. See `LICENSE` for more information.

---

## 📧 Contact

Paul Ogier, OSH.co.za and Taming.Tech.

* [paul@osh.co.za](mailto:paul@osh.co.za) / [osh.co.za](https://osh.co.za/?utm_source=github&utm_medium=readme&utm_campaign=gamscripts&utm_content=contact)
* [paul@taming.tech](mailto:paul@taming.tech) / [taming.tech](https://taming.tech/?utm_source=github&utm_medium=readme&utm_campaign=gamscripts&utm_content=contact)


