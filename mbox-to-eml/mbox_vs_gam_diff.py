#!/usr/bin/env python3
"""Reconcile a Vault mbox export against a GAM read of the label it was built from.

Usage: python3 mbox_vs_gam_diff.py <export.mbox> <gam-label-read.csv>

The CSV is the output of

    gam user <user> print messages query "label:<Label>" includespamtrash \\
        headers From,To,Cc,Bcc,Date,Subject showlabels > gam-label-read.csv

Messages are matched on the Date header as a UTC timestamp plus the first 30 characters
of the decoded subject, reduced to printable ASCII. Two things make a naive comparison
lie: RFC 2047 encoded subjects differ byte for byte between the two sources while
meaning the same thing, and a sender who declares ISO-8859-1 but sends a Windows-1252
apostrophe decodes differently from GAM's UTF-8 rendering. On a real export of about
1,100 messages the raw comparison reported about 300 mismatches; the true difference
was one.

The report says how many messages each side has, lists every message only one side
holds (with From and To for the mbox side), and names the drafts in the GAM read and
whether each reached the mbox. That is enough to tell the three usual causes apart:
Vault's "Exclude email drafts" switch was off; Gmail purged a trashed message after the
GAM read while Vault still holds it; or the label was edited between the read and the
export.

Read-only, standard library only.
Exit codes: 0 = sets identical, 1 = differences listed, 2 = usage or a CSV without the
expected columns.
Copyright (c) 2026 Paul Ogier, Outsource House. Apache License 2.0.
Part of https://github.com/PaulOgier/GAMScripts
"""
import collections
import csv
import email.utils
import mailbox
import os
import re
import sys
from email.header import decode_header, make_header

NEEDED_COLUMNS = {"Date", "Subject", "From", "Labels"}


def dec(s):
    """Decode an RFC 2047 header; a malformed one comes back raw."""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s


def norm(s):
    """Match key: decoded, whitespace-collapsed, printable ASCII only, first 30 characters."""
    return re.sub(r"[^\x20-\x7e]", "", re.sub(r"\s+", " ", dec(s or ""))).strip()[:30]


def ts(date_header):
    """Date header as a UTC epoch second, or None when missing or unparsable."""
    if not date_header:
        return None
    try:
        return int(email.utils.parsedate_to_datetime(date_header).timestamp())
    except Exception:
        return None


def compare(mbox_path, csv_path, out=sys.stdout):
    """Print the reconciliation and return the number of differences found."""
    msgs = [(ts(m.get("Date")), norm(m.get("Subject")), norm(m.get("From")), norm(m.get("To")))
            for m in mailbox.mbox(mbox_path, create=False)]
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing_cols = NEEDED_COLUMNS - set(reader.fieldnames or [])
        if missing_cols:
            raise ValueError(
                f"CSV is missing {sorted(missing_cols)}; produce it with "
                'gam user <user> print messages query "label:<Label>" includespamtrash '
                "headers From,To,Cc,Bcc,Date,Subject showlabels")
        rows = list(reader)
    gam_keys = collections.Counter((ts(r["Date"]), norm(r["Subject"])) for r in rows)
    mbox_keys = collections.Counter((t, s) for t, s, _, _ in msgs)
    drafts = [r for r in rows if "DRAFT" in r["Labels"].split()]
    print(f"mbox {len(msgs)} | gam {len(rows)} (drafts {len(drafts)}, non-draft {len(rows) - len(drafts)})", file=out)
    only_mbox = {k for k in mbox_keys if mbox_keys[k] > gam_keys[k]}
    only_gam = {k for k in gam_keys if gam_keys[k] > mbox_keys[k]}
    for t, s, frm, to in msgs:
        if (t, s) in only_mbox:
            print(f"ONLY IN MBOX: {t} | {s} | from {frm} | to {to}", file=out)
    for r in rows:
        if (ts(r["Date"]), norm(r["Subject"])) in only_gam:
            print(f"ONLY IN GAM:  {r['Date']} | {norm(r['Subject'])} | from {norm(r['From'])} | labels {r['Labels']}", file=out)
    for r in drafts:
        present = (ts(r["Date"]), norm(r["Subject"])) in mbox_keys
        print(f"DRAFT in GAM read: {r['Date']} | {norm(r['Subject'])} | in mbox: {present}", file=out)
    differences = len(only_mbox) + len(only_gam)
    if not differences:
        print("sets identical", file=out)
    return differences


def main(argv):
    if len(argv) != 3:
        print(f"Usage: {os.path.basename(argv[0])} <export.mbox> <gam-label-read.csv>")
        return 2
    for p in argv[1:]:
        if not os.path.isfile(p):
            print(f"not a file: {p}", file=sys.stderr)
            return 2
    try:
        return 1 if compare(argv[1], argv[2]) else 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
