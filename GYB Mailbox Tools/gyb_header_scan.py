#!/usr/bin/env python3
"""Find messages whose headers exceed Gmail's import limits.

A single message with an oversized header aborts a GYB restore with

    Bcc header value (76666 bytes) exceeds Google's limit of 32768

and GYB does not say which message it was. On a six-figure mailbox that is a
needle in a haystack, so this walks the backup and names the offenders before
the restore starts.

Headers are folded across continuation lines in the file but Google measures
the unfolded value, so this unfolds before measuring.

Read-only. Only the header block of each file is read, never the body.

Exit codes:
  0  every message was checked and no oversized headers were found
  1  problems found: oversized headers, unreadable files, or both
  2  the path does not exist, or nothing could be read at all
"""

import argparse
import sys
from pathlib import Path

# The limit named in Gmail's own rejection message, in bytes, per header value.
GOOGLE_HEADER_LIMIT = 32768

# Stop reading a file once this much has gone by without a blank line. A
# legitimate header block is far smaller; anything larger is malformed, and we
# would rather report that than read a 50 MB attachment into memory.
MAX_HEADER_BYTES = 4 * 1024 * 1024


def read_header_block(path: Path) -> bytes:
    """Return the raw header block of an RFC822 file, up to the blank line."""
    chunks = []
    total = 0
    with open(path, "rb") as handle:
        while total < MAX_HEADER_BYTES:
            chunk = handle.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            blob = b"".join(chunks)
            for terminator in (b"\r\n\r\n", b"\n\n"):
                end = blob.find(terminator)
                if end != -1:
                    return blob[:end]
    return b"".join(chunks)[:MAX_HEADER_BYTES]


def oversized_headers(header_block: bytes, limit: int = GOOGLE_HEADER_LIMIT) -> list:
    """Return [(header_name, unfolded_value_length)] for values over the limit.

    Continuation lines (those starting with a space or tab) belong to the
    header above them and count towards its length, which is exactly how a
    Bcc list of thousands of addresses gets over the limit while every
    individual line in the file looks harmless.
    """
    found = []
    name = None
    length = 0

    def flush():
        if name is not None and length > limit:
            found.append((name, length))

    for raw_line in header_block.replace(b"\r\n", b"\n").split(b"\n"):
        if raw_line[:1] in (b" ", b"\t"):
            # Continuation of the header above.
            length += len(raw_line)
            continue
        flush()
        name, separator, value = raw_line.partition(b":")
        if not separator:
            # Not a header line (an envelope "From " line, or junk). Ignore it.
            name = None
            length = 0
            continue
        name = name.decode("ascii", "replace")
        length = len(value)
    flush()
    return found


def scan(backup: Path, limit: int) -> int:
    """Scan every .eml under a folder and report oversized headers."""
    if not backup.is_dir():
        print(f"NOT FOUND: {backup} does not exist or is not a directory.")
        return 2

    scanned = 0
    unreadable = 0
    hits = 0

    for path in sorted(backup.rglob("*.eml")):
        try:
            block = read_header_block(path)
        except OSError as exc:
            unreadable += 1
            print(f"UNREADABLE ({exc.__class__.__name__}): {path}")
            continue
        scanned += 1
        for name, length in oversized_headers(block, limit):
            hits += 1
            print(f"OVERSIZED: {path}")
            print(f"    {name} header is {length} bytes (limit {limit})")

    print(f"Scanned {scanned} message(s) under {backup}.")
    if unreadable:
        print(
            f"{unreadable} file(s) could not be read - usually an antivirus "
            "quarantine lock. Those are the other thing that kills a restore; "
            "gyb_backup_doctor.py --probe-reads lists them."
        )
    if hits:
        print(
            f"{hits} oversized header(s) found. Gmail's import API rejects "
            "these, and a stock GYB restore stops when it hits one. Move the "
            "named files aside before restoring, the same way an AV-locked "
            "file is handled."
        )
    else:
        print("No oversized headers. Nothing here will trip Gmail's header limit.")

    if not scanned and unreadable:
        # Nothing could be checked, so "clean" would be a lie.
        return 2
    return 1 if (hits or unreadable) else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find backed-up messages with headers Gmail will reject."
    )
    parser.add_argument("backup", nargs="+", type=Path, help="Backup folder(s).")
    parser.add_argument(
        "--limit",
        type=int,
        default=GOOGLE_HEADER_LIMIT,
        help=f"Byte limit per header value (default {GOOGLE_HEADER_LIMIT}).",
    )
    args = parser.parse_args()

    worst = 0
    for index, backup in enumerate(args.backup):
        if index:
            print()
        worst = max(worst, scan(backup, args.limit))
    return worst


if __name__ == "__main__":
    sys.exit(main())
