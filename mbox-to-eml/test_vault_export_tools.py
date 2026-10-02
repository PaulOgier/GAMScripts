#!/usr/bin/env python3
"""Self-check for mbox_to_eml.py and mbox_vs_gam_diff.py.

Builds a five-message mbox and a matching GAM-shaped CSV in a temp directory, so it
needs no tenant, no Vault export and no real mail. Run: python3 test_vault_export_tools.py
"""
import csv
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mbox_to_eml  # noqa: E402
import mbox_vs_gam_diff  # noqa: E402

MESSAGES = [
    # (Date header, raw Subject header, From, labels in the GAM read)
    ("Wed, 01 Jul 2026 07:41:00 +0000", "Plain subject", "a@example.com", "INBOX Handover"),
    ("Wed, 01 Jul 2026 07:41:00 +0000", "Plain subject", "b@example.com", "INBOX Handover"),  # same minute+subject
    ("Thu, 02 Jul 2026 09:00:00 +0000", "=?UTF-8?B?WW914oCZcmUgaW52aXRlZA==?=", "c@example.com", "INBOX Handover"),  # You’re invited
    ("Fri, 03 Jul 2026 10:00:00 +0000", "CON", "d@example.com", "SENT Handover"),  # Windows reserved name
    ("Sat, 04 Jul 2026 11:00:00 +0000", "Re: draft to self...", "e@example.com", "DRAFT Handover"),
]


def build_mbox(path, messages):
    with open(path, "wb") as f:
        for date, subject, sender, _ in messages:
            f.write(b"From MAILER-DAEMON Wed Jul  1 07:41:00 2026\n")
            f.write(f"From: {sender}\nTo: x@example.com\nDate: {date}\nSubject: {subject}\n\nbody\n\n".encode())


def build_csv(path, messages):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["User", "threadId", "id", "From", "To", "Cc", "Bcc", "Date", "Subject", "LabelsCount", "Labels"])
        for i, (date, subject, sender, labels) in enumerate(messages):
            # GAM writes the DECODED subject with a UTF-8 curly apostrophe, not the RFC 2047 form
            decoded = "You’re invited" if subject.startswith("=?") else subject
            w.writerow(["x@example.com", f"t{i}", f"m{i}", sender, "x@example.com", "", "", date, decoded, 2, labels])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        mbox = os.path.join(tmp, "export.mbox")
        build_mbox(mbox, MESSAGES)

        # --- splitter ---
        out = os.path.join(tmp, "eml")
        written, failed = mbox_to_eml.split(mbox, out)
        names = sorted(os.listdir(out))
        assert (written, failed) == (5, 0), (written, failed)
        assert "2026-07-01 0741 Plain subject.eml" in names and "2026-07-01 0741 Plain subject (2).eml" in names, names
        assert "2026-07-02 0900 You’re invited.eml" in names, names
        assert "2026-07-03 1000 _CON.eml" in names, names  # reserved name prefixed
        assert "2026-07-04 1100 Re draft to self.eml" in names, names  # colon and trailing dots gone
        assert mbox_to_eml.safe_name("x" * 100) == "x" * 60
        assert mbox_to_eml.safe_name("   ") == "(no subject)"
        assert mbox_to_eml.safe_name("lpt3") == "_lpt3"
        # bytes untouched: the file is exactly the message as the mbox held it
        with open(os.path.join(out, "2026-07-03 1000 _CON.eml"), "rb") as f:
            assert f.read().startswith(b"From: d@example.com\n"), "message bytes were altered"

        # --- diff: identical sets ---
        gam_csv = os.path.join(tmp, "gam.csv")
        build_csv(gam_csv, MESSAGES)
        buf = io.StringIO()
        assert mbox_vs_gam_diff.compare(mbox, gam_csv, out=buf) == 0, buf.getvalue()
        assert "sets identical" in buf.getvalue() and "drafts 1" in buf.getvalue(), buf.getvalue()
        assert "in mbox: True" in buf.getvalue(), buf.getvalue()

        # --- diff: mbox holds one message the GAM read lost (a Trash purge) ---
        build_csv(gam_csv, MESSAGES[:-1] + [])  # drop the draft row
        buf = io.StringIO()
        assert mbox_vs_gam_diff.compare(mbox, gam_csv, out=buf) == 1, buf.getvalue()
        assert "ONLY IN MBOX" in buf.getvalue() and "Re: draft to self" in buf.getvalue(), buf.getvalue()

        # --- diff: the GAM read has a message the export lacks ---
        extra = MESSAGES + [("Sun, 05 Jul 2026 12:00:00 +0000", "Added after export", "f@example.com", "INBOX Handover")]
        build_csv(gam_csv, extra)
        buf = io.StringIO()
        assert mbox_vs_gam_diff.compare(mbox, gam_csv, out=buf) == 1
        assert "ONLY IN GAM" in buf.getvalue() and "Added after export" in buf.getvalue(), buf.getvalue()

        # --- diff: wrong CSV shape is a usage error, not a KeyError ---
        with open(gam_csv, "w", encoding="utf-8") as f:
            f.write("id,subject\n1,x\n")
        try:
            mbox_vs_gam_diff.compare(mbox, gam_csv, out=io.StringIO())
            raise AssertionError("expected ValueError on a CSV without the GAM columns")
        except ValueError as exc:
            assert "showlabels" in str(exc)

        # --- CLI exit codes ---
        assert mbox_to_eml.main(["mbox_to_eml.py"]) == 2
        assert mbox_vs_gam_diff.main(["mbox_vs_gam_diff.py", mbox]) == 2
    print("all checks passed")


if __name__ == "__main__":
    main()
