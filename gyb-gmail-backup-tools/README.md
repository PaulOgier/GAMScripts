# GYB Gmail Backup Tools: verify a Got Your Back backup before you restore it

Two small, read-only Python utilities for
[GYB (Got Your Back)](https://github.com/GAM-team/got-your-back) Gmail
mailbox backups. Run them before you trust a backup, and before you spend a
night restoring one.

GYB is very good at moving Gmail. What it will not tell you is whether the
folder you are pointing at is really a backup, how much of that backup is on
disk, how far a half-finished restore got, or which single message is about
to abort the whole run. These two scripts answer those questions in a couple
of seconds, and neither one writes to your backup.

Built and maintained by Paul Ogier, [Outsource House](https://osh.co.za).
Training at [Taming.Tech](https://taming.tech).

## Contents

- [Who this is for](#who-this-is-for)
- [Requirements](#requirements)
- [Backup Doctor: gyb_backup_doctor.py](#backup-doctor-gyb_backup_doctorpy)
- [Header Scanner: gyb_header_scan.py](#header-scanner-gyb_header_scanpy)
- [What to do with the answers](#what-to-do-with-the-answers)
- [Frequently asked questions](#frequently-asked-questions)
- [Tests](#tests)
- [Licence](#licence)

## Who this is for

- **Google Workspace admins** migrating a leaver's mailbox to a successor with
  GYB, or archiving mailboxes before deleting accounts.
- **MSPs** who keep GYB backups for clients and need to prove a backup is
  complete before the licence is removed.
- **Anyone whose GYB restore** finished suspiciously fast, died halfway, or
  stopped with a header-size error and no filename.

## Requirements

- Python 3.6 or newer. Standard library only, nothing to install.
- A GYB backup folder produced by `gyb --action backup`. GYB itself is not
  needed to run these tools, since they read the backup rather than the
  mailbox.

## Backup Doctor: `gyb_backup_doctor.py`

Reports the true state of a GYB backup folder: whether it is a GYB-format
backup at all, how many messages the database claims, how many `.eml` files
are on disk, and how far each restore got. Read-only, with every database
opened in SQLite's `ro` mode.

Use it to check a backup before you rely on it, and to diagnose a restore that
finished suspiciously fast or died halfway.

- **Names the "restore did nothing" trap.** GYB decides a folder is a backup
  purely by the presence of `msg-db.sqlite`. Without that file,
  `--action restore` falls through to scanning for mbox files, finds none,
  and exits `0` in seconds having restored nothing. The doctor says so, and
  points you at `--action restore-mbox` if the folder holds mbox or `.eml`
  files instead.
- **Reconciles the database against the disk.** A message counted in
  `msg-db.sqlite` but missing from disk means the backup is incomplete, and
  restoring it would migrate a mailbox that was never fully captured.
- **Understands quarantine.** Files deliberately moved to a
  `<backup>_quarantined` sibling folder are accounted for rather than
  reported as missing, so a handled antivirus quarantine does not read as
  data loss.
- **Reports restore progress per destination.** One backup restored into two
  accounts carries two resume databases, and each is reported separately with
  the count still outstanding.
- **Flags a schema mismatch.** A `db_version` other than the expected `6`
  means the backup came from a different GYB generation.
- **Warns about epoch-dated mail.** Messages whose sender sent an unparsable
  `Date` header are filed under `1970/` and get re-stamped with the restore
  date on import. Better to know that before the client asks why old mail
  arrived today.
- **Optional read probe** (`--probe-reads`) opens every `.eml` to find files
  that exist but cannot be read, which is what endpoint antivirus does to
  quarantined mail. It turns a mid-restore crash into a list you can act on
  first.
- Exit codes: `0` healthy, `1` problems found, `2` not a GYB backup folder.

```bash
# Check one backup
python3 gyb_backup_doctor.py /path/to/GYB-GMail-Backup-user@domain.com

# Check several at once
python3 gyb_backup_doctor.py /backups/mailboxes/*

# Also probe every file for antivirus locks (slow on a large backup)
python3 gyb_backup_doctor.py --probe-reads /path/to/backup
```

## Header Scanner: `gyb_header_scan.py`

Finds backed-up messages whose headers exceed Gmail's import limit, and names
the files. Reads only the header block of each message, never the body. Run
it once before a large restore, so that a single malformed message does not
abort it hours in.

- **Names the message GYB will not.** A restore that hits an oversized header
  aborts with `Bcc header value (76666 bytes) exceeds Google's limit of 32768`
  and no indication of which message caused it. On a six-figure mailbox that
  is otherwise a needle in a haystack.
- **Unfolds before measuring.** Headers are folded across continuation lines
  in the file, but Google measures the unfolded value. A Bcc list of several
  thousand addresses looks harmless on every individual line and is only
  oversized once joined up.
- **Reports unreadable files too.** A file that cannot be opened is usually
  an antivirus quarantine lock, which is the other thing that stops a restore
  dead.
- **Adjustable limit** (`--limit`) for testing, or for a different API's
  ceiling.
- Exit codes: `0` every message checked and clean, `1` problems found
  (oversized headers, unreadable files, or both), `2` path missing or nothing
  readable at all.

```bash
# Scan a backup before restoring it
python3 gyb_header_scan.py /path/to/GYB-GMail-Backup-user@domain.com

# Scan several backups
python3 gyb_header_scan.py /backups/mailboxes/*
```

## What to do with the answers

- **"NOT A GYB BACKUP"**: you are either pointing at the wrong folder (the
  parent, or the `_quarantined` sibling), or the folder holds an mbox export
  from Takeout or Vault, which needs `--action restore-mbox` rather than
  `--action restore`.
- **Messages in the database but not on disk**: re-run the backup before
  restoring. An incomplete backup restores an incomplete mailbox, and nothing
  downstream will tell you.
- **A restore with messages outstanding**: re-run the same restore command.
  It resumes rather than starting over, provided the original ran with
  `--batch-size` above 1, and Gmail de-duplicates on import so anything sent
  twice lands once.
- **Oversized headers, or files that will not open**: move the named files
  aside before restoring. A rename is a directory operation and succeeds even
  while every read of the file is blocked, so nothing needs deleting. Resist
  the urge to add an antivirus exclusion for the backup folder, because the
  lock is what stops malicious mail being uploaded into the destination
  mailbox.

## Frequently asked questions

**My GYB restore finished in seconds and restored nothing. Why?**
The folder has no `msg-db.sqlite`, so GYB treated it as an mbox restore,
found no mbox files and exited cleanly. Run the Backup Doctor on the folder;
it will say whether the folder is a GYB backup and which restore action fits.

**A GYB restore stopped with "header value exceeds Google's limit of 32768".
Which message was it?**
Run the Header Scanner over the backup. It lists every message whose
unfolded headers are over the limit, with the file path, so you can move
them aside and re-run the restore.

**Is my GYB backup complete?**
The Backup Doctor compares the message count in the database with the `.eml`
files on disk and reports any shortfall, less anything you deliberately
quarantined.

**Can I run these on a backup that is being restored right now?**
Yes. They open the databases read-only and never write to the folder.

**Do they work with the offboarding script in this repository?**
Yes. The [Google Workspace offboarding script](../google-workspace-offboarding/README.md)
uses GYB for mailbox migration; these tools check the backup it leaves
behind and find the messages its skipped-messages CSV names.

## Tests

`test_gyb_tools.py` builds throwaway GYB-shaped backup folders in a temp
directory, so it needs no tenant, no credentials and no real mailbox:

```bash
python3 test_gyb_tools.py
```

## Licence

Apache 2.0; see `LICENSE` at the repository root.
