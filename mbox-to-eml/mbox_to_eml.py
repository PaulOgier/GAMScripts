#!/usr/bin/env python3
"""Split an mbox export into one .eml file per message, bytes untouched.

Usage: python3 mbox_to_eml.py <in.mbox> <out dir>

Each file is named "<YYYY-MM-DD HHMM> <subject>.eml" so the folder sorts by date in
Finder, Explorer and ls alike. A recipient without a mail client that reads mbox can
open any single message by double-clicking it (Outlook, Apple Mail, Thunderbird all
open .eml). The message bytes are written exactly as the mbox holds them: no header
is rewritten, no charset is touched, so what the recipient opens is what was exported.

Filenames are made safe for all three platforms at once. Windows is the strict one:
nine characters are illegal, a name may not end in a dot or a space, and CON, PRN, AUX,
NUL, COM1-9 and LPT1-9 are reserved whatever the extension. Subjects are cut at 60
characters so a long subject inside a deep folder stays under Windows' 260-character
path limit on machines that have not enabled long paths.

Exit codes: 0 = every message written, 1 = nothing written or a message failed, 2 = usage.
Copyright (c) 2026 Paul Ogier, Outsource House. Apache License 2.0.
Part of https://github.com/PaulOgier/GAMScripts
"""
import email.header
import email.utils
import mailbox
import os
import re
import sys

WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
SUBJECT_MAX = 60


def safe_name(subject):
    """Turn a decoded subject into a filename stem that every OS accepts."""
    name = ILLEGAL.sub(" ", subject)
    name = re.sub(r"\s+", " ", name).strip()[:SUBJECT_MAX].rstrip(". ")
    if not name:
        name = "(no subject)"
    if name.upper() in WINDOWS_RESERVED:
        name = "_" + name
    return name


def decoded_subject(msg):
    """RFC 2047 decode; a malformed header comes back raw rather than crashing the run."""
    raw = msg.get("Subject", "") or ""
    try:
        return str(email.header.make_header(email.header.decode_header(raw)))
    except Exception:
        return raw


def date_stamp(msg):
    """YYYY-MM-DD HHMM from the Date header; a missing or unparsable date sorts first."""
    try:
        return email.utils.parsedate_to_datetime(msg.get("Date")).strftime("%Y-%m-%d %H%M")
    except Exception:
        return "0000-00-00 0000"


def split(src, out):
    """Write one .eml per message and return (written, failed)."""
    os.makedirs(out, exist_ok=True)
    box = mailbox.mbox(src, create=False)
    written = failed = 0
    for key in box.iterkeys():
        try:
            raw = box.get_bytes(key)
            msg = box.get_message(key)
        except Exception as exc:  # one bad message must not stop the other thousand
            failed += 1
            print(f"FAILED to read message {key}: {exc}", file=sys.stderr)
            continue
        base = f"{date_stamp(msg)} {safe_name(decoded_subject(msg))}"
        path = os.path.join(out, base + ".eml")
        i = 1
        while os.path.exists(path):  # same minute and subject: keep both
            i += 1
            path = os.path.join(out, f"{base} ({i}).eml")
        with open(path, "wb") as f:
            f.write(raw)
        written += 1
    return written, failed


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[0])
        print(f"Usage: {os.path.basename(argv[0])} <in.mbox> <out dir>")
        return 2
    src, out = argv[1], argv[2]
    if not os.path.isfile(src):
        print(f"not a file: {src}", file=sys.stderr)
        return 2
    written, failed = split(src, out)
    print(f"{written} messages written to {out}" + (f", {failed} FAILED" if failed else ""))
    return 0 if written and not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
