# Split Calendar CSV Events

Three standalone utilities for GAM calendar exports that are too big to open in Excel or Google Sheets. Standard library only — no packages to install. All three write their output files into the **current working directory**, so `cd` to where you want the results before running.

## Get the export out of GAM

```
gam redirect csv ./AllUsersPrimaryEvents.csv all users print events primary
```

That produces one CSV with every event for every user in the tenant. `split_csv.py` and `filter_and_split.py` both key off the `primaryEmail` column, so leave the header row alone.

## Which one do you want?

| Script | Splits by | Output |
| --- | --- | --- |
| `split_csv.py` | user | one CSV per person, whole history |
| `filter_and_split.py` | user, recent events only | one CSV per person, last N days |
| `split_by_size.py` | file size | numbered chunks, all users mixed |

---

## `split_csv.py` — one file per user

Groups every row by `primaryEmail` and writes each user their own CSV.

```bash
python3 split_csv.py AllUsersPrimaryEvents.csv
```

Output is named after the address with `@` and `.` replaced: `name@company.com` becomes `name_company_com.csv`. Rows with an empty `primaryEmail` are skipped with a warning.

## `filter_and_split.py` — one file per user, recent events only

Same per-user split, but first drops every event that starts before the cutoff. Takes the file and the number of days.

```bash
# last 30 days
python3 filter_and_split.py AllUsersPrimaryEvents.csv 30
```

Output: `name_company_com_filtered_events.csv` per user, and nothing at all for users with no events in the window.

Needs the `primaryEmail`, `start.date` and `start.dateTime` columns, and refuses to run without all three. It reads `start.dateTime` when present and falls back to `start.date` for all-day events. **Comparison is in naive local time** — timezones on the event are stripped, not converted, so events within a few hours of the cutoff can land on either side of it. Rows with an unparseable date are silently skipped.

## `split_by_size.py` — size-limited chunks

Cuts the file into pieces of at most N megabytes (default 5), repeating the header in each one. This one does not care about users; a person's events can straddle two chunks.

```bash
# 5 MB chunks
python3 split_by_size.py AllUsersPrimaryEvents.csv

# 20 MB chunks
python3 split_by_size.py AllUsersPrimaryEvents.csv 20
```

Output: `AllUsersPrimaryEvents_part_1.csv`, `_part_2.csv`, and so on. Chunk size is estimated from the raw row text, so a file lands near the limit rather than exactly on it.
