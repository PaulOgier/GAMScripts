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
* **Additional Requirements**: GYB (optional, for email migration only). See `offboarding_test_setup_guide.md` for a full test environment setup guide.

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

---

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

## 📜 License

Distributed under the Apache-2.0 license. See `LICENSE` for more information.

---

## 📧 Contact

Paul Ogier / OSH.co.za and Taming.Tech - paul@osh.co.za https://osh.co.za paul@taming.tech https://taming.tech


