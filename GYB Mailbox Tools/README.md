# 📬 GYB Mailbox Tools

Two small, read-only Python utilities for inspecting [GYB (Got Your Back)](https://github.com/GAM-team/got-your-back) mailbox backups before you trust one, or before you spend a night restoring one.

GYB is very good at moving Gmail. What it will not tell you is whether the folder you are pointing at is really a backup, how much of that backup is on disk, how far a half-finished restore got, or which single message is about to abort the whole run. These two scripts answer those questions in a couple of seconds, and neither one writes to your backup.

---

## 🔧 Prerequisites

1. **Python 3**: Python 3.6 or newer. Check with `python3 --version`. No third-party packages, standard library only.
2. **A GYB backup folder**: produced by `gyb --action backup`. GYB itself is not required to run these tools, since they read the backup rather than the mailbox.

---

## 📚 Scripts Library

### **1. Backup Doctor (`gyb_backup_doctor.py`)**

* **Description**: Reports the true state of a GYB backup folder: whether it is a GYB-format backup at all, how many messages the database claims, how many `.eml` files are on disk, and how far each restore got. Read-only, with every database opened in SQLite's `ro` mode.
* **Best For**: Checking a backup before you rely on it, and diagnosing a restore that finished suspiciously fast or died halfway.
* **Key Features**:
  * **Names the "restore did nothing" trap**. GYB decides a folder is a backup purely by the presence of `msg-db.sqlite`. Without that file, `--action restore` falls through to scanning for mbox files, finds none, and exits `0` in seconds having restored nothing. The doctor says so, and points you at `--action restore-mbox` if the folder holds mbox or `.eml` files instead.
  * **Reconciles the database against the disk**. A message counted in `msg-db.sqlite` but missing from disk means the backup is incomplete, and restoring it would migrate a mailbox that was never fully captured.
  * **Understands quarantine**. Files deliberately moved to a `<backup>_quarantined` sibling folder are accounted for rather than reported as missing, so a handled antivirus quarantine does not read as data loss.
  * **Reports restore progress per destination**. One backup restored into two accounts carries two resume databases, and each is reported separately with the count still outstanding.
  * **Flags a schema mismatch**. A `db_version` other than the expected `6` means the backup came from a different GYB generation.
  * **Warns about epoch-dated mail**. Messages whose sender sent an unparsable `Date` header are filed under `1970/` and get re-stamped with the restore date on import. Better to know that before the client asks why old mail arrived today.
  * **Optional read probe** (`--probe-reads`) opens every `.eml` to find files that exist but cannot be read, which is what endpoint antivirus does to quarantined mail. It turns a mid-restore crash into a list you can act on first.
  * Exit codes: `0`=healthy, `1`=problems found, `2`=not a GYB backup folder.
* **Usage**:
    ```bash
    # Check one backup
    python3 gyb_backup_doctor.py /path/to/GYB-GMail-Backup-user@domain.com

    # Check several at once
    python3 gyb_backup_doctor.py /backups/mailboxes/*

    # Also probe every file for antivirus locks (slow on a large backup)
    python3 gyb_backup_doctor.py --probe-reads /path/to/backup
    ```

<br>

### **2. Header Scanner (`gyb_header_scan.py`)**

* **Description**: Finds backed-up messages whose headers exceed Gmail's import limit, and names the files. Reads only the header block of each message, never the body.
* **Best For**: Running once before a large restore, so that a single malformed message does not abort it hours in.
* **Key Features**:
  * **Names the message GYB will not**. A restore that hits an oversized header aborts with `Bcc header value (76666 bytes) exceeds Google's limit of 32768` and no indication of which message caused it. On a six-figure mailbox that is otherwise a needle in a haystack.
  * **Unfolds before measuring**. Headers are folded across continuation lines in the file, but Google measures the unfolded value. A Bcc list of several thousand addresses looks harmless on every individual line and is only oversized once joined up.
  * **Reports unreadable files too**. A file that cannot be opened is usually an antivirus quarantine lock, which is the other thing that stops a restore dead.
  * **Adjustable limit** (`--limit`) for testing, or for a different API's ceiling.
  * Exit codes: `0`=every message checked and clean, `1`=problems found (oversized headers, unreadable files, or both), `2`=path missing or nothing readable at all.
* **Usage**:
    ```bash
    # Scan a backup before restoring it
    python3 gyb_header_scan.py /path/to/GYB-GMail-Backup-user@domain.com

    # Scan several backups
    python3 gyb_header_scan.py /backups/mailboxes/*
    ```

---

## ✅ Tests

`test_gyb_tools.py` builds throwaway GYB-shaped backup folders in a temp directory, so it needs no tenant, no credentials and no real mailbox:

```bash
python3 test_gyb_tools.py
```

---

## 💡 What to do with the answers

* **"NOT A GYB BACKUP"**: you are either pointing at the wrong folder (the parent, or the `_quarantined` sibling), or the folder holds an mbox export from Takeout or Vault, which needs `--action restore-mbox` rather than `--action restore`.
* **Messages in the database but not on disk**: re-run the backup before restoring. An incomplete backup restores an incomplete mailbox, and nothing downstream will tell you.
* **A restore with messages outstanding**: re-run the same restore command. It resumes rather than starting over, provided the original ran with `--batch-size` above 1, and Gmail de-duplicates on import so anything sent twice lands once.
* **Oversized headers, or files that will not open**: move the named files aside before restoring. A rename is a directory operation and succeeds even while every read of the file is blocked, so nothing needs deleting. Resist the urge to add an antivirus exclusion for the backup folder, because the lock is what stops malicious mail being uploaded into the destination mailbox.

---

## 📜 License

Distributed under the Apache-2.0 license. See `LICENSE` in the repository root.
