#!/usr/bin/env python3
"""Report the true state of a GYB backup folder.

Answers the three questions GYB itself will not: is this folder actually a GYB
backup, how much of it is really on disk, and how far did a restore get.

The most common confusing failure upstream is a restore that prints "Using
backup folder ..." and exits in seconds having done nothing. The cause is that
GYB decides a folder is "GYB format" purely by the presence of msg-db.sqlite;
without it, restore silently falls through to scanning for mbox files, finds
none, and exits 0. This script names that condition instead of leaving you to
guess.

Read-only. It opens every database with the sqlite3 'ro' URI mode and never
writes to the backup.

Exit codes:
  0  backup looks healthy (or is legitimately empty)
  1  problems found (message shortfall, schema mismatch, unreadable files)
  2  not a GYB-format backup folder, or the path does not exist
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# GYB writes db_version into the settings table. 6 is what v1.95 produces; a
# different value means the backup was written by a GYB whose layout this
# script has not been checked against.
EXPECTED_DB_VERSION = "6"


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    """Open a sqlite database read-only so a doctor run can never corrupt it."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    """Row count for a table, or -1 if the table is missing."""
    try:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    except sqlite3.DatabaseError:
        return -1


def read_settings(db_path: Path) -> dict:
    """Return msg-db.sqlite's settings table as a dict (empty if unreadable)."""
    try:
        with _connect_ro(db_path) as conn:
            return dict(conn.execute("SELECT name, value FROM settings"))
    except sqlite3.DatabaseError:
        return {}


def count_eml_files(backup: Path) -> int:
    """Count .eml files actually present under the backup folder."""
    return sum(1 for _ in backup.rglob("*.eml"))


def unreadable_eml_files(backup: Path, limit: int = 20) -> list:
    """Find .eml files that exist but cannot be opened.

    Endpoint antivirus holds an EPERM lock on quarantined mail, which is the
    single failure that kills a stock GYB restore outright. Probing for it
    before the restore turns a mid-run crash into a pre-run list.
    """
    bad = []
    for path in backup.rglob("*.eml"):
        try:
            with open(path, "rb") as handle:
                handle.read(1)
        except OSError as exc:
            bad.append((path, exc.__class__.__name__))
            if len(bad) >= limit:
                break
    return bad


def find_resume_dbs(backup: Path) -> list:
    """Return the per-destination restore resume databases in this folder.

    GYB names them <destination-email>-restored.sqlite, so one backup folder
    restored into two accounts carries two of them.
    """
    return sorted(backup.glob("*-restored.sqlite"))


def doctor(backup: Path, probe_reads: bool = False) -> int:
    """Print a state report for one backup folder and return an exit code."""
    if not backup.is_dir():
        print(f"NOT A BACKUP: {backup} does not exist or is not a directory.")
        return 2

    msg_db = backup / "msg-db.sqlite"
    print(f"Backup folder: {backup}")

    if not msg_db.is_file():
        mbox_like = [
            p.name
            for p in backup.iterdir()
            if p.suffix.lower() in (".mbox", ".mbx", ".eml")
        ]
        print("NOT A GYB BACKUP: msg-db.sqlite is missing.")
        print(
            "  GYB decides a folder is GYB-format solely by this file. Without "
            "it, --action restore falls through to mbox scanning, finds "
            "nothing, and exits 0 in seconds having restored nothing."
        )
        if mbox_like:
            print(
                f"  This folder does hold {len(mbox_like)} mbox/eml file(s) at "
                "the top level, so --action restore-mbox is probably what you "
                "want here, not --action restore."
            )
        else:
            print(
                "  No mbox/eml files at the top level either. Check you are "
                "pointing at the backup folder itself and not its parent."
            )
        return 2

    problems = 0

    settings = read_settings(msg_db)
    if not settings:
        print("PROBLEM: msg-db.sqlite is unreadable or has no settings table.")
        return 1

    print(f"  Backed-up account: {settings.get('email_address', '(unrecorded)')}")

    db_version = settings.get("db_version", "(unrecorded)")
    if db_version != EXPECTED_DB_VERSION:
        problems += 1
        print(
            f"  PROBLEM: db_version is {db_version}, expected "
            f"{EXPECTED_DB_VERSION}. This backup was written by a different "
            "GYB generation; verify before trusting a restore."
        )
    else:
        print(f"  DB schema version: {db_version}")

    with _connect_ro(msg_db) as conn:
        rows = _table_count(conn, "messages")
        labels = _table_count(conn, "labels")
        epoch_dated = conn.execute(
            "SELECT count(*) FROM messages "
            "WHERE message_internaldate < '1971-01-01'"
        ).fetchone()[0]

    on_disk = count_eml_files(backup)
    quarantine_dir = backup.parent / f"{backup.name}_quarantined"
    quarantined = count_eml_files(quarantine_dir) if quarantine_dir.is_dir() else 0

    print(f"  Messages in DB:    {rows}")
    print(f"  .eml files on disk: {on_disk}")
    if quarantined:
        print(f"  Quarantined aside:  {quarantined} (in {quarantine_dir.name})")

    if rows == 0:
        print(
            "  Empty backup. GYB backs up and restores an empty mailbox "
            "cleanly, so this is not in itself a fault - but if you expected "
            "mail, the source mailbox was empty or --search excluded it all."
        )

    # The shortfall test. Quarantined files are deliberate exclusions and are
    # accounted for; anything beyond that was never written or has vanished.
    missing = rows - on_disk - quarantined
    if missing > 0:
        problems += 1
        print(
            f"  PROBLEM: {missing} message(s) are in the DB but not on disk "
            "and not quarantined. The backup is incomplete - re-run it before "
            "restoring, or you will migrate a mailbox that was never fully "
            "captured."
        )
    elif rows and on_disk < rows:
        print(
            f"  Backup verified: the {rows - on_disk} message(s) not on disk "
            "are all quarantined (deliberate exclusions)."
        )
    elif rows:
        print("  Backup verified: every message in the DB is on disk.")

    if labels >= 0:
        print(f"  Label rows: {labels}")

    if epoch_dated:
        print(
            f"  NOTE: {epoch_dated} message(s) carry an unparsable Date header "
            "and are filed under 1970/. Gmail re-stamps these with the restore "
            "date on import; the original date survives only in Received "
            "headers, which the import API ignores."
        )

    for resume_db in find_resume_dbs(backup):
        destination = resume_db.name.replace("-restored.sqlite", "")
        try:
            with _connect_ro(resume_db) as conn:
                restored = _table_count(conn, "restored_messages")
        except sqlite3.DatabaseError:
            problems += 1
            print(f"  PROBLEM: resume DB for {destination} is unreadable.")
            continue

        remaining = rows - restored
        print(f"  Restore into {destination}: {restored} of {rows} done", end="")
        if remaining and remaining <= quarantined:
            print(
                f". The {remaining} not restored are quarantined messages that "
                "were never on disk to send, so this restore is as complete as "
                "it was ever going to be."
            )
        elif remaining > 0:
            print(
                f", {remaining} remaining. Re-running the same restore resumes "
                "from here - it does not start over, and Gmail de-duplicates "
                "anything sent twice."
            )
        else:
            print(". Complete.")

    if probe_reads:
        bad = unreadable_eml_files(backup)
        if bad:
            problems += 1
            print(f"  PROBLEM: {len(bad)} .eml file(s) exist but cannot be read:")
            for path, kind in bad:
                print(f"    {kind}: {path.relative_to(backup)}")
            print(
                "    Endpoint antivirus quarantines malicious mail in place. "
                "Move these aside (mv, which works even while reads are "
                "blocked) so GYB's missing-file handling skips them. Do not "
                "add an AV exclusion - the lock is what stops you uploading "
                "malware into the destination mailbox."
            )
        else:
            print("  Read probe: every .eml file opened cleanly.")

    print("  VERDICT: " + ("problems found." if problems else "healthy."))
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report the true state of a GYB backup folder (read-only)."
    )
    parser.add_argument("backup", nargs="+", type=Path, help="Backup folder(s).")
    parser.add_argument(
        "--probe-reads",
        action="store_true",
        help=(
            "Open every .eml to find antivirus-locked files. Slow on a large "
            "backup, but it turns a mid-restore crash into a pre-run list."
        ),
    )
    args = parser.parse_args()

    worst = 0
    for index, backup in enumerate(args.backup):
        if index:
            print()
        worst = max(worst, doctor(backup, probe_reads=args.probe_reads))
    return worst


if __name__ == "__main__":
    sys.exit(main())
