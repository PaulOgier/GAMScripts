# Mbox to EML: open an mbox on Windows, macOS or Linux, and check a Google Vault export against GAM

Two small, read-only Python utilities for the last mile of a mailbox split:
proving that a Google Vault export holds exactly the messages you labelled with
GAM, and turning that export into files a person can open without a mail
migration tool.

Neither script is tied to Vault or to labels. `mbox_to_eml.py` converts any
mbox file into individual `.eml` files: a Google Vault export, a Google Takeout
archive, a Thunderbird or Apple Mail export, a GYB `restore-mbox` source.
`mbox_vs_gam_diff.py` compares any Vault Gmail export against any
`gam print messages` read, whatever the query; a label is just the cleanest way
to define the set.

Built and maintained by Paul Ogier, [Outsource House](https://osh.co.za).
Training at [Taming.Tech](https://taming.tech).

## Contents

- [Who this is for](#who-this-is-for)
- [Requirements](#requirements)
- [Just need to open an mbox file?](#just-need-to-open-an-mbox-file)
- [The mailbox split workflow](#the-mailbox-split-workflow)
- [Export reconciler: mbox_vs_gam_diff.py](#export-reconciler-mbox_vs_gam_diffpy)
- [Mbox splitter: mbox_to_eml.py](#mbox-splitter-mbox_to_emlpy)
- [What to do with the answers](#what-to-do-with-the-answers)
- [Tests](#tests)
- [Licence](#licence)

## Who this is for

- **Google Workspace admins** handing someone their personal mail out of a
  company mailbox when they leave: a work account that also carried private
  correspondence, a mailbox the company keeps while the person who used it
  wants their own threads.
- **MSPs** who have to prove the handover held exactly what was agreed, and
  nothing else.
- **Anyone holding an mbox file they cannot open**, from Google Takeout,
  Vault, Thunderbird or Apple Mail.

GAM can label the subset precisely, and Vault can export a label. What neither
tells you is whether the export matches the label, or how the recipient is
going to open an mbox on a Windows laptop. These two scripts answer that.

## Requirements

- Python 3.6 or newer. Standard library only, nothing to install.
- GAM7 for the labelling and the label read. GAM is not needed to run the
  scripts themselves.
- Google Vault access, with a Vault-bearing licence on the admin doing the
  export. An unlicensed super admin gets "you do not have access to Google
  Vault" even with the Vault service switched on. The message points at the
  service switch; the cause is the licence.

## Just need to open an mbox file?

You do not need an mbox converter, an mbox viewer, Thunderbird, or an import
into anything. An mbox is a plain text file with every message stacked one
after another. The splitter cuts it back into one `.eml` per message,
attachments included, and `.eml` is what Outlook, Apple Mail, Thunderbird and
Windows Mail open with a double-click. It works on the
`All mail Including Spam and Trash.mbox` that Google Takeout produces, on a
Google Vault export, and on a Thunderbird or Apple Mail mailbox export.

```bash
python3 mbox_to_eml.py "All mail Including Spam and Trash.mbox" "My mail"
```

That works the same on Windows, macOS and Linux and writes each message
exactly as the mbox holds it. Each `.eml` opens one message at a time. If
the recipient uses Outlook and wants everything in one place, ask for a PST
export from Vault instead. If opening the file was the whole problem, you are
done; the rest of this page is the mailbox split the scripts were built for.

## The mailbox split workflow

1. **Label the subset in Gmail with GAM.** One `modify messages ... addlabel`
   per query, run against a count first so a query that matches nothing is
   caught before it is applied. Use a label with no spaces; Vault wants
   hyphens.

    ```bash
    # read-only: how many would this query label?
    gam user leaver@example.com print messages query "from:someone@example.org" countsonly

    # changes the mailbox: applies the label
    gam user leaver@example.com modify messages query "from:someone@example.org" max_to_modify 0 doit addlabel Handover
    ```

2. **Read the label back, and keep that CSV.** This is the file the diff
   compares against, and it is the only record of what the label held at the
   moment you exported. `includespamtrash` matters: without it GAM leaves Spam
   and Trash out, Vault's "All data" puts them in, and the two counts disagree
   for no interesting reason.

    ```bash
    # read-only
    gam user leaver@example.com print messages query "label:Handover" includespamtrash headers From,To,Cc,Bcc,Date,Subject showlabels > gam-label-read.csv
    ```

3. **Export the label from Vault.** In a matter, search Gmail with the terms
   `label:Handover` on the one account and export as **mbox** (and PST as well
   if the recipient uses Outlook). The Vault count should match the CSV row
   count. When it does not, the diff in step 4 tells you why.

4. **Reconcile, then split.**

    ```bash
    python3 mbox_vs_gam_diff.py export.mbox gam-label-read.csv
    python3 mbox_to_eml.py export.mbox "Mail for Leaver"
    ```

5. **Zip the folder** and deliver it. On a Mac use
   `ditto -c -k --norsrc --noextattr --noqtn --noacl --keepParent "Mail for Leaver" "Mail for Leaver.zip"`.
   Plain `zip` or Finder's Compress adds a `._` sidecar per file, which lands
   as junk on a Windows recipient.

## Export reconciler: `mbox_vs_gam_diff.py`

Compares every message in a Vault mbox export with a `gam print messages` read
of the same mailbox, and lists what only one side holds. This workflow reads a
label, but any query works. Read-only. Run it once between the Vault export
and the delivery, so the file handed over is proven to be the label and nothing
else.

- **Matches on meaning, not bytes.** Subjects are RFC 2047 decoded,
  whitespace-collapsed and reduced to printable ASCII before comparing. Raw
  subjects differ between the two sources for every encoded header, and a
  sender who declares ISO-8859-1 but sends a Windows-1252 apostrophe decodes
  differently again. On a real export of about 1,100 messages the raw
  comparison reported about 300 mismatches; the true difference was one
  message.
- **Names the drafts.** Vault's "Exclude email drafts" switch is not shown in
  the saved-query line on the Search tab, so a screenshot proves nothing about
  it. The report lists each draft in the GAM read and whether it reached the
  mbox, which settles the question.
- **Explains a Vault count that is higher than GAM's.** Gmail empties Trash
  after 30 days, and the message leaves every GAM read. Vault still holds and
  exports it. A message that is "ONLY IN MBOX" with a Trash-era date is
  that, not a Vault fault.
- **Catches label drift.** Anyone signed into the mailbox can add or remove the
  label between your read and your export. "ONLY IN GAM" and "ONLY IN MBOX"
  rows with recent dates are the tell; put them to the owner before
  delivering.
- **Refuses the wrong CSV.** A CSV without the `Date`, `Subject`, `From` and
  `Labels` columns exits `2` with the exact gam command that produces the right
  one, rather than a `KeyError` three lines in.
- Exit codes: `0` sets identical, `1` differences listed, `2` usage or wrong
  CSV shape.

```bash
python3 mbox_vs_gam_diff.py export.mbox gam-label-read.csv
```

## Mbox splitter: `mbox_to_eml.py`

Writes one `.eml` file per message, bytes untouched, named
`<YYYY-MM-DD HHMM> <subject>.eml` so the folder sorts by date. Every `.eml`
opens with a double-click in Outlook, Apple Mail or Thunderbird, and Apple Mail
can also import the whole folder.

- **Nothing is rewritten.** Each file is the message exactly as the mbox held
  it: headers, encoding, attachments. What the recipient opens is what Vault
  exported.
- **Filenames that survive all three platforms.** The nine characters Windows
  forbids are replaced, and trailing dots and spaces are stripped, because
  Windows drops them silently and two files then collide. The reserved names
  `CON`, `PRN`, `AUX`, `NUL`, `COM1-9` and `LPT1-9` get an underscore in
  front. Subjects are cut at 60 characters, so a deep folder path stays under
  Windows' 260-character limit.
- **Duplicates are kept, not overwritten.** Two messages with the same minute
  and subject become `name.eml` and `name (2).eml`.
- **One bad message does not stop the run.** An unreadable message is reported
  on stderr and counted as failed, and the rest are still written.
- Exit codes: `0` every message written, `1` nothing written or a message
  failed, `2` usage.

```bash
python3 mbox_to_eml.py export.mbox "Mail for Leaver"
```

## What to do with the answers

- **`sets identical`**: deliver. Count the `.eml` files against the mbox
  (`grep -c '^From ' export.mbox`) and you have three numbers that agree.
- **One `ONLY IN MBOX` row dated more than 30 days ago**: almost always a
  message that was in Trash at your GAM read and has since been purged. Vault
  kept it. Decide whether the recipient should have it; usually yes, since it
  was theirs.
- **A `DRAFT` row with `in mbox: True`**: the export ran with drafts included.
  Fine if the drafts are the recipient's own; re-export with "Exclude email
  drafts" if they are not.
- **Rows on either side with dates after your GAM read**: the label was edited
  by hand after you read it. Re-read the label, diff the new read against the
  old one, and ask the mailbox owner about every unexplained change before you
  export again. Every change after an export means rebuilding the zip, and the
  PST if there is one.
- **`ONLY IN GAM` rows with old dates**: the export is short. Check the Vault
  search terms and the account, then export again.

## Tests

`test_vault_export_tools.py` builds a five-message mbox and a matching
GAM-shaped CSV in a temp directory, so it needs no tenant, no Vault export and
no real mail:

```bash
python3 test_vault_export_tools.py
```

## Licence

Apache 2.0; see `LICENSE` at the repository root. Keep the attribution in each
script's header if you redistribute it.

GAM training from Taming.Tech: [GAM7 course](https://taming.tech/GAMCourse),
[Google Workspace Admin course](https://www.taming.tech/GoogleWorkspaceAdmin),
[Google Workspace End-User course](https://www.taming.tech/TheCompleteWorkspaceCourse).
