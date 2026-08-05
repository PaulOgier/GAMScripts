#!/usr/bin/env python3
"""Self-checks for gyb_backup_doctor.py and gyb_header_scan.py.

Builds throwaway GYB-shaped backup folders in a temp directory, so it needs no
tenant, no credentials and no real mailbox. Run: python3 test_gyb_tools.py
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import gyb_backup_doctor as doctor  # noqa: E402
import gyb_header_scan as scanner  # noqa: E402


def make_backup(root: Path, messages: list, db_version: str = "6") -> Path:
    """Create a GYB-format backup folder. messages = [(relpath, bytes)]."""
    backup = root / "GYB-GMail-Backup-test@example.com"
    backup.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(backup / "msg-db.sqlite")
    conn.executescript(
        """
        CREATE TABLE settings (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE messages(message_num INTEGER PRIMARY KEY,
                              message_filename TEXT,
                              message_internaldate TIMESTAMP);
        CREATE TABLE labels (message_num INTEGER, label TEXT);
        """
    )
    conn.execute("INSERT INTO settings VALUES ('email_address','test@example.com')")
    conn.execute("INSERT INTO settings VALUES ('db_version',?)", (db_version,))
    for num, (relpath, blob) in enumerate(messages, start=1):
        conn.execute(
            "INSERT INTO messages VALUES (?,?,?)",
            (num, relpath, "2026-01-01 00:00:00"),
        )
        target = backup / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    conn.commit()
    conn.close()
    return backup


SIMPLE = b"From: a@example.com\r\nSubject: hi\r\n\r\nbody\r\n"


def test_healthy_backup():
    with tempfile.TemporaryDirectory() as tmp:
        backup = make_backup(Path(tmp), [("2026/1/1/a.eml", SIMPLE)])
        assert doctor.doctor(backup) == 0, "a complete backup should exit 0"


def test_missing_msg_db_is_not_a_gyb_backup():
    """The 'restore exits in seconds doing nothing' case."""
    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp) / "not-a-backup"
        backup.mkdir()
        (backup / "stuff.mbox").write_bytes(SIMPLE)
        assert doctor.doctor(backup) == 2, "no msg-db.sqlite must exit 2"


def test_shortfall_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        backup = make_backup(
            Path(tmp), [("2026/1/1/a.eml", SIMPLE), ("2026/1/1/b.eml", SIMPLE)]
        )
        (backup / "2026/1/1/b.eml").unlink()
        assert doctor.doctor(backup) == 1, "a message in the DB but not on disk is a fault"


def test_quarantined_shortfall_is_not_a_fault():
    """Files moved aside deliberately are accounted for, not counted missing."""
    with tempfile.TemporaryDirectory() as tmp:
        backup = make_backup(
            Path(tmp), [("2026/1/1/a.eml", SIMPLE), ("2026/1/1/b.eml", SIMPLE)]
        )
        (backup / "2026/1/1/b.eml").unlink()
        quarantine = backup.parent / f"{backup.name}_quarantined/2026/1/1"
        quarantine.mkdir(parents=True)
        (quarantine / "b.eml").write_bytes(SIMPLE)
        assert doctor.doctor(backup) == 0, "quarantined files must not read as missing"


def test_wrong_db_version_is_a_fault():
    with tempfile.TemporaryDirectory() as tmp:
        backup = make_backup(Path(tmp), [("2026/1/1/a.eml", SIMPLE)], db_version="5")
        assert doctor.doctor(backup) == 1, "an unexpected db_version must be flagged"


def test_empty_backup_is_clean():
    with tempfile.TemporaryDirectory() as tmp:
        backup = make_backup(Path(tmp), [])
        assert doctor.doctor(backup) == 0, "an empty mailbox backup is not a fault"


def test_header_under_limit_passes():
    block = b"From: a@example.com\r\nBcc: " + b"x" * 100
    assert scanner.oversized_headers(block) == []


def test_oversized_header_is_found():
    block = b"From: a@example.com\r\nBcc: " + b"x" * 40000
    found = scanner.oversized_headers(block)
    assert len(found) == 1, found
    assert found[0][0] == "Bcc", found


def test_folded_header_counts_as_one_value():
    """Each line is small; the unfolded value is what Gmail measures."""
    folded = b"Bcc: start\r\n" + (b" " + b"y" * 900 + b"\r\n") * 40
    block = b"From: a@example.com\r\n" + folded
    found = scanner.oversized_headers(block)
    assert len(found) == 1 and found[0][0] == "Bcc", found
    assert found[0][1] > scanner.GOOGLE_HEADER_LIMIT, found


def test_body_is_not_scanned():
    """A huge body must not be mistaken for a huge header."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "big.eml"
        path.write_bytes(b"From: a@example.com\r\n\r\n" + b"z" * 100000)
        assert scanner.oversized_headers(scanner.read_header_block(path)) == []


def test_unreadable_file_is_not_reported_as_clean():
    """A file we could not open must not exit 0 - nothing was checked in it."""
    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp)
        good = backup / "good.eml"
        good.write_bytes(SIMPLE)
        locked = backup / "locked.eml"
        locked.write_bytes(SIMPLE)
        locked.chmod(0o000)
        try:
            assert scanner.scan(backup, scanner.GOOGLE_HEADER_LIMIT) == 1
        finally:
            locked.chmod(0o644)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
