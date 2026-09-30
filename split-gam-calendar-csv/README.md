# Split a GAM Calendar Events CSV by User or File Size

Three small Python scripts for **GAM calendar exports that are too big to
open** in Google Sheets or Excel. Export every user's events with one GAM
command, then split the CSV into one file per user, one file per user with
only recent events, or numbered chunks under a size limit. Standard library
only, nothing to install.

All three write their output files into the **current working directory**, so
`cd` to where you want the results before running.

Built and maintained by Paul Ogier, [Outsource House](https://osh.co.za).
Training at [Taming.Tech](https://taming.tech).

## Contents

- [Get the export out of GAM](#get-the-export-out-of-gam)
- [Which one do you want?](#which-one-do-you-want)
- [split_csv.py: one file per user](#split_csvpy-one-file-per-user)
- [filter_and_split.py: one file per user, recent events only](#filter_and_splitpy-one-file-per-user-recent-events-only)
- [split_by_size.py: size-limited chunks](#split_by_sizepy-size-limited-chunks)
- [Frequently asked questions](#frequently-asked-questions)
- [Licence](#licence)

## Get the export out of GAM

```
gam redirect csv ./AllUsersPrimaryEvents.csv all users print events primary
```

That produces one CSV with every event for every user in the tenant.
`split_csv.py` and `filter_and_split.py` both key off the `primaryEmail`
column, so leave the header row alone.

## Which one do you want?

| Script | Splits by | Output |
| --- | --- | --- |
| `split_csv.py` | user | one CSV per person, whole history |
| `filter_and_split.py` | user, recent events only | one CSV per person, last N days |
| `split_by_size.py` | file size | numbered chunks, all users mixed |

## `split_csv.py`: one file per user

Groups every row by `primaryEmail` and writes each user their own CSV.

```bash
python3 split_csv.py AllUsersPrimaryEvents.csv
```

Output is named after the address with `@` and `.` replaced:
`name@company.com` becomes `name_company_com.csv`. Rows with an empty
`primaryEmail` are skipped with a warning.

## `filter_and_split.py`: one file per user, recent events only

Same per-user split, but first drops every event that starts before the
cutoff. Takes the file and the number of days.

```bash
# last 30 days
python3 filter_and_split.py AllUsersPrimaryEvents.csv 30
```

Output: `name_company_com_filtered_events.csv` per user, and nothing at all
for users with no events in the window.

Needs the `primaryEmail`, `start.date` and `start.dateTime` columns, and
refuses to run without all three. It reads `start.dateTime` when present and
falls back to `start.date` for all-day events. **Comparison is in naive local
time**: timezones on the event are stripped, not converted, so events within
a few hours of the cutoff can land on either side of it. Rows with an
unparseable date are silently skipped.

## `split_by_size.py`: size-limited chunks

Cuts the file into pieces of at most N megabytes (default 5), repeating the
header in each one. This one does not care about users; a person's events can
straddle two chunks.

```bash
# 5 MB chunks
python3 split_by_size.py AllUsersPrimaryEvents.csv

# 20 MB chunks
python3 split_by_size.py AllUsersPrimaryEvents.csv 20
```

Output: `AllUsersPrimaryEvents_part_1.csv`, `_part_2.csv`, and so on. Chunk
size is estimated from the raw row text, so a file lands near the limit
rather than exactly on it.

## Frequently asked questions

**Why will Google Sheets or Excel not open my GAM export?**
A tenant-wide `print events` file is often hundreds of megabytes. Google
Sheets refuses imports over 100 MB and spreadsheets over 10 million cells,
and Excel stops at 1,048,576 rows. Split by user or by size and open the
pieces.

**Do these work on other GAM CSV exports?**
`split_by_size.py` works on any CSV with a header row. The two per-user
scripts need a `primaryEmail` column, which most GAM `all users print ...`
exports have, and `filter_and_split.py` also needs the calendar start
columns.

**Do they change the original file?**
No. They read it and write new files next to where you run them.

## Licence

Apache 2.0; see `LICENSE` at the repository root.
