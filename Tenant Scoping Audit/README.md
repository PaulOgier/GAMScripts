# Tenant Scoping Audit

A read-only Google Workspace tenant audit in a single Python file. It collects
tenant and security-posture data through [GAM7](https://github.com/GAM-team/GAM),
runs a findings engine over it, and renders a report your client (or your
manager) can actually read: what was found, why it matters, what to do.

Built and maintained by Paul Ogier, [Outsource House](https://osh.co.za).
Training at [Taming.Tech](https://taming.tech).

## Why this exists

We run IT for other companies, which means we regularly inherit Google
Workspace tenants that other people built. The same three situations kept
sending us into the Admin console with a checklist and a bad feeling:

- **A new client signs.** Day one, we need to know what is about to bite:
  which files are public on the web, whose mail quietly forwards off-domain,
  which admin left in 2019 but still holds the keys.
- **A client is preparing for something big**: a migration, a domain move, a
  security uplift. Before you change anything, you need an honest picture of
  what is there now.
- **A client is being acquired.** The buyer wants to know where the security
  gaps are before they sign, and "we clicked around the console for a day"
  is not an answer you can put in a due-diligence pack.

Clicking through the Admin console for that takes a day per tenant and still
misses things, because the console shows you settings one screen at a time
and never volunteers what you forgot to look at. This script pulls the data
in one pass, applies the checks we kept re-deriving by hand, and writes down
both the findings and the list of things it could not check.

Credit where it is due: we had been using this script on our own clients for
about six months when Dirk Grobler asked for help with his tenant-scoping
batch script on the
[google-apps-manager group](https://groups.google.com/g/google-apps-manager/c/9r_AeuiWOSg).
That question inspired us to open ours up to the Google admin community.
Thank you, Dirk.

## What you get

- `audit_report.html`: a single self-contained HTML file (no external
  assets), severity tiles up top, one section per finding with plain-English
  "what this means" and "what to do" copy, and evidence samples. Print it for
  a clean PDF.
- `findings.csv`: the findings list in machine-readable form.
- One CSV per collected module, so every finding can be traced back to raw
  data.
- `tenant_scope.log` + `gam_stderr.log`: the full audit trail.

## Safety posture

Every GAM command the script issues is a read (`print`, `report`, `info`,
`oauth info`, `check serviceaccount`), with one opt-in exception:
`--grant-temp-access` temporarily adds the auditing admin as organizer on
Shared Drives they are not a member of, scans them, and removes the grant
again. GAM's `filelist` has no admin-access mode, so without membership a
scan silently returns zero rows and the drive would look clean; by default
those drives are reported **UNSCANNED** instead.

Backup verification codes never reach disk. The collector keeps only the
per-user count.

## What it checks

**Critical:** files public on the web; fewer than two super admins; super
admins without 2-step verification; super admins with app passwords;
mailboxes forwarding outside the organisation; Shared Drives with no manager.

**High:** "anyone with the link" sharing at scale; files shared with entire
external domains; Shared Drives open to external sharing or holding external
members; groups anyone can join, post to, or that allow external members;
Gmail filters forwarding externally; unmanaged (personal) accounts on company
domains; domains without DMARC; admin accounts nobody has signed into for
months; delegates on admin mailboxes; accounts stacking multiple risk
factors; organisational units where policy blocks 2-step verification
enrolment; admin roles still held by suspended accounts.

**Medium:** 2-step verification enrolment percentage; POP/IMAP enabled;
files shared to named external people; licensed accounts that were never
signed into, or dormant more than 90 days; suspended accounts still holding
paid licences; mailbox delegation involving suspended or dormant accounts;
third-party apps holding full Gmail or Drive access; super admins with
personal recovery addresses; public primary calendars; password policy below
current practice; web sessions longer than Google's 14-day default; new
Shared Drives defaulting to external sharing; licences owned but not
assigned to anyone; admin role assignments pointing at deleted accounts;
admin rights spread across a large share of the userbase.

**Info:** the tenant at a glance (users, licences, groups, drives, devices,
Vault, SSO); the mailbox delegation map; the admin role map; 2-step
verification policy per organisational unit; which Google services are
switched on or off; suspended accounts still holding data or drive roles;
externally-owned files shared into the tenant.

Anything that could not be checked (missing authorisation, module error,
unscanned drives) is listed in the report. Absence of a finding never means
"checked and clean" unless the module ran.

## Requirements

- Python 3.9+ (standard library only)
- GAM7 (GAM ADV X) installed and authorised against the tenant you are
  auditing. The script finds it on PATH, at `~/bin/gam7/gam` (macOS
  installer), or `C:\GAM7\gam.exe` (Windows).
- Works on Windows, macOS and Linux.

## Usage

```
python3 tenant_scope.py --admin admin@yourdomain.com
```

That is the whole thing: tiers 1 to 3 plus the DNS checks, into a new
timestamped run directory, with the report opened at the end.

### Every flag

| Flag | What it does |
|---|---|
| `--admin <email>` | The auditing admin. Verifies the service account's DWD scopes in the preflight, and is the account the Shared Drive scans run as. Without it those scans are skipped and per-user modules run unverified. |
| `--list` | Print the module registry (key, title, tier) and exit. |
| `--full` | Add the tier-4 modules: Gmail filters, vacation responders, managed browsers, Alert Center, context-aware access. |
| `--only <keys>` | Comma-separated module keys; everything else is skipped. |
| `--skip <keys>` | Comma-separated module keys to skip. |
| `--skip-tier <n>` | Skip a whole tier, e.g. `--skip-tier 3` to leave out the heavy Drive scans. |
| `--no-dns` | Skip the DNS checks. |
| `--include-suspended` | Include suspended accounts in the per-user scans. Default is active accounts only, and the report says which. |
| `--skip-never-logged-in` | Exclude accounts that have never signed in from the per-user scans. |
| `--grant-temp-access` | The one write in the script. See below. |
| `--output-dir <dir>` | Where run directories are created. Default `./tenant_audit_runs/`. |
| `--run-dir <dir>` | Resume an existing run. Completed modules are skipped. |
| `--render-only` | Re-run the checks and rebuild the report from a `--run-dir`, with no GAM calls at all. |
| `--dry-run` | Print every GAM command without executing it. |
| `--no-open` | Don't open the report in a browser when the run finishes. |
| `--yes` | Skip the interactive tenant confirmation. The identity is still logged. |

### Worked examples

```
python3 tenant_scope.py --list
python3 tenant_scope.py --admin admin@yourdomain.com --full
python3 tenant_scope.py --admin admin@yourdomain.com --skip-tier 3
python3 tenant_scope.py --admin admin@yourdomain.com --only users,groups,dns
python3 tenant_scope.py --admin admin@yourdomain.com --run-dir <dir>
python3 tenant_scope.py --render-only --run-dir <dir>
python3 tenant_scope.py --admin admin@yourdomain.com --dry-run
python3 tenant_scope.py --admin admin@yourdomain.com --grant-temp-access
python3 tenant_scope.py --admin admin@yourdomain.com --skip-never-logged-in --no-open --yes
```

**Overnight on a large tenant.** `--skip-tier 3` first for the quick picture,
then the same run directory again without the skip so only the Drive scans
execute:

```
python3 tenant_scope.py --admin admin@yourdomain.com --skip-tier 3
python3 tenant_scope.py --admin admin@yourdomain.com --run-dir tenant_audit_runs/tenant_audit_<stamp>
```

**Re-render after a fix.** If a check itself was wrong, you do not need to
collect anything again:

```
python3 tenant_scope.py --render-only --run-dir tenant_audit_runs/tenant_audit_<stamp>
```

**Scheduled or headless.** `--yes` answers the tenant prompt, `--no-open`
leaves the browser alone:

```
python3 tenant_scope.py --admin admin@yourdomain.com --yes --no-open
```

**A tenant full of accounts nobody has ever used.** `--skip-never-logged-in`
drops them from the per-user scans, and the report states how many were
excluded. It is off by default because an admin-set forward on an account
nobody has ever signed into is exactly the thing an audit should find:

```
python3 tenant_scope.py --admin admin@yourdomain.com --skip-never-logged-in
```

**Shared Drives the admin is not a member of.** `filelist` has no admin-access
mode, so a non-member scan returns zero rows and looks clean. Those drives are
reported UNSCANNED unless you pass `--grant-temp-access`, which adds the
auditing admin as organizer, scans, and removes the grant again:

```
python3 tenant_scope.py --admin admin@yourdomain.com --grant-temp-access --only shareddrive_external
```

### How a run behaves

The preflight confirms the tenant (primary domain + customer ID) with you
before anything is collected, because auditing the wrong tenant is the worst
silent failure this kind of tool can have. `--yes` skips the prompt but still logs
the identity.

Timeouts scale with the size of the tenant, and per-user scans run as a
threaded GAM batch over an explicit list of the accounts being audited rather
than one sequential pass over every mailbox. GAM's own progress counters are
echoed to the console every 30 seconds during a long scan, so a Drive
enumeration that runs for hours doesn't look like a hang. If a command is
killed by its timeout, the rows collected up to that point are kept and the
module is marked partial rather than discarded.

Each run writes into its own timestamped directory under
`./tenant_audit_runs/` (change with `--output-dir`). Runs are resumable:
`manifest.json` records completed modules, and `--run-dir` picks up where a
run stopped.

A default run on a small tenant takes a few minutes. The tier-3 Drive scans
are the expensive part on large tenants; run them overnight, or start with
`--skip-tier 3` and fill in the blanks later: run again with
`--run-dir <that dir>` and no skip flag, and only the missing modules
execute before the report re-renders over the complete data set.

### Reading the report

A finding looks like this in the HTML:

> **[CRITICAL] Mailboxes forwarding to addresses outside the organisation**
>
> *What this means:* All mail arriving in these mailboxes is being copied or
> moved to an external address. This is a common way company data quietly
> leaves the organisation, and one of the first things attackers set up
> after compromising an account.
>
> *What to do:* Confirm with each user whether the forward is legitimate
> business use. Remove any that are not, and review the account's recent
> sign-in activity if the forward was not set up knowingly.

Evidence tables show a sample (10 rows by default) with the true total in
the headline; the full list is always in the module's CSV next to the
report.

### DNS checks

Per domain, MX/SPF/DKIM/DMARC are checked through
[tamingdns.com](https://tamingdns.com). If it is unreachable, the module
falls back to dns.google with presence-only checks, and the report says
which path ran.

### Things the report states rather than hides

- GAM's `all users` iterates ACTIVE users only. Per-user checks cover active
  users unless you pass `--include-suspended`; the report says which.
- Usage-report figures (storage) lag roughly two days behind live state.
- Shared Drives the auditing admin cannot scan are listed as UNSCANNED.
- Policy checks report the *resolved* setting. The Policy API returns
  Google's defaults, the administrator's own policy and a copy per
  licence SKU for the same org unit; the highest `sortOrder` wins, per
  Google's Max reducer. Licence scoping is not modelled, so a setting
  that genuinely differs between two SKUs in one org unit shows only the
  winner.

## Tests

```
python3 -m unittest test_tenant_scope -v
```

128 tests, no GAM calls, no fixtures on disk beyond temp directories.

## Licence

Apache 2.0; see `LICENSE` at the repository root. Keep the attribution
header in `tenant_scope.py` intact if you redistribute it.
