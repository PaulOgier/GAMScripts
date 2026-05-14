# Windows Installation Guide: GAM7, GYB, and rclone

This guide installs three tools on **Windows 10 / 11** and wires them all
to a **single Google service account** that GAM7 provisions:

1. **GAM7** — creates the GCP project, the service account, and downloads
   the service-account JSON key (`oauth2service.json`).
2. **GYB** — re-uses the same `oauth2service.json` for mailbox archive.
3. **rclone** — re-uses the same `oauth2service.json` for cloud storage.

One service account, three tools, one set of scope authorisations in the
Admin Console.

Run everything from **Command Prompt (`cmd.exe`)** — open Start, type
`cmd`, press Enter. A few steps need an **elevated** prompt (right-click
Command Prompt → **Run as administrator**); those are flagged inline.
PowerShell works too, but the commands below are written for cmd so
they paste cleanly.

---

## 0. Prerequisites

- Google Workspace tenant where you are a **Super Admin**.
- **Python 3.10+** on PATH:
  ```cmd
  python --version
  ```
  Install from [python.org](https://www.python.org/downloads/windows/)
  (preferred) or the Microsoft Store. On the python.org installer:
  - tick **"Add python.exe to PATH"** on the first screen — without
    this, `python` is not on PATH and only `py -3` works. You can
    verify this later on the **Advanced Options** screen as
    *"Add Python to environment variables"* (same toggle, second
    chance to enable it).
  - on the final screen, click **"Disable path length limit"**. This
    removes the legacy 260-character `MAX_PATH` cap machine-wide. GAM,
    GYB, and rclone all generate paths that can exceed 260 chars — long
    Drive folder names, deeply nested Gmail label hierarchies (GYB
    mirrors each label as a folder), and timestamped backup paths under
    `C:\GAMWork\` add up quickly. Hitting `MAX_PATH` mid-run surfaces as
    confusing errors like `[Errno 2] No such file or directory` on files
    that clearly exist, or GYB silently skipping messages. The toggle is
    one click, reversible, and has no downside on an admin box.

  **If you missed "Add to PATH" on the first run:** open Settings →
  Apps → Installed apps → find Python 3.14 → `⋯` → **Modify** → Next →
  on the *Advanced Options* screen, tick **"Add Python to environment
  variables"** → Install. Then close all cmd windows and open a fresh
  one.

  **Gotcha — Microsoft Store app execution alias hijack.** Even with
  Python installed and PATH set correctly, you may still see:
  ```
  Python was not found; run without arguments to install from the
  Microsoft Store, or disable this shortcut from Settings > Apps >
  Advanced app settings > App execution aliases.
  ```
  Windows ships stub `python.exe` and `python3.exe` "app execution
  aliases" that open the Microsoft Store, and they sit *earlier* on
  PATH than your real install — so they win even though your real
  Python is on PATH too. Fix:
  1. **Settings → Apps → Advanced app settings → App execution aliases**.
  2. Find the rows labelled `python.exe` and `python3.exe` (source is
     "App Installer" / Microsoft Store).
  3. Toggle **both OFF**.
  4. Open a fresh cmd window:
     ```cmd
     python --version
     ```
     Should now print `Python 3.14.x`.

  **Gotcha — `python3` does not exist on Windows.** The `python3` command
  is a Unix/macOS convention. The python.org installer only creates
  `python.exe` and the `py` launcher. On Windows always use `python` (or
  `py -3`) — `python3 --version` will keep hitting the Store-alias error
  even after a healthy install.

  **Create a `python3.cmd` shim so cross-platform docs "just work".**
  The offboarding script and the test setup guide use `python3` in every
  example because that's the universal command on macOS / Linux. On
  Windows we get parity with a one-line wrapper.

  This matters most when **a team of admins shares the same runbook
  across mixed machines** — e.g. one admin on a MacBook, another on a
  Windows laptop, a third on a Linux jump host. Without the shim, every
  copy-pasted command from the wiki or this guide has to be mentally
  translated (`python3` → `python` or `py -3`) by the Windows users
  every time, and any locally-edited "Windows version" of a script
  drifts from the macOS version until they don't match. With the shim,
  the **same command runs identically on every machine** — no platform
  branches in the docs, no per-OS forks of helper scripts, no surprises
  when an admin moves between workstations.

  From an **elevated cmd** (so you can write to `C:\GAM7\`, which you'll
  create in §1.1 — if you're doing the install in order, run this *after*
  §1.1 step 2; otherwise pick any directory you control that's on PATH):

  ```cmd
  echo @py -3 %* > C:\GAM7\python3.cmd
  ```

  That writes a tiny batch file `C:\GAM7\python3.cmd` containing exactly:

  ```cmd
  @py -3 %*
  ```

  Because `C:\GAM7\` is on machine-wide PATH (added in §1.1) and you
  disabled the Microsoft Store `python3.exe` alias above, the shim wins.
  Verify in a fresh cmd window:

  ```cmd
  python3 --version
  ```

  Should print `Python 3.14.x`. From here on, every example in the
  repo's docs that says `python3 offboard_user.py ...` will run as-is on
  this Windows box — same command, same behaviour as the macOS and
  Linux admins on the team.

  > Why `C:\GAM7\` and not somewhere else? It's already a directory you
  > created, already on machine-wide PATH, and lives outside `%PATH%`
  > entries Windows might rewrite. Any PATH directory you control works
  > equally well.
- **Local administrator rights on the Windows machine.** Several steps
  below cannot be done from a standard user account:

  - **Writing to `C:\`.** This guide installs everything under root-level
    folders (`C:\GAM7`, `C:\GAMConfig`, `C:\GAMWork`, `C:\GYB`,
    `C:\rclone`). Creating folders directly under `C:\` requires admin —
    a standard user is blocked by UAC. If you genuinely cannot get admin,
    install under `%USERPROFILE%` (e.g. `C:\Users\<you>\GAM7`) instead and
    update every path in the guide accordingly.
  - **Machine-wide environment variables.** The `setx ... /M` commands
    write to the *system* PATH and to `GAMCFGDIR` so any user / scheduled
    task on the box sees them. `/M` requires an **elevated Command
    Prompt** (right-click → *Run as administrator*). Without admin, drop
    the `/M` flag — variables are then written to your user profile only
    and will not be visible to services or other users.
  - **Creating a symbolic link (§2.2).** The `mklink` step that points
    GYB at GAM's `oauth2service.json` needs an elevated prompt unless
    Windows Developer Mode is on (Settings → Privacy & security → For
    developers → *Developer Mode*). With Developer Mode on, any user can
    `mklink`. Without it, either elevate the prompt or use the
    `copy` fallback shown in §2.2.
  - **`winget` for rclone (§3.1).** A normal user can run `winget install`
    only for packages that support per-user installs. `Rclone.Rclone` is
    a machine-scope package, so it will silently re-prompt for UAC.
    Either elevate or fall back to the manual zip install in §3.1.
  - **AV / Endpoint Protection exclusions.** GAM and rclone make many
    API calls and are sometimes flagged. Adding exclusions in Microsoft
    Defender or third-party AV requires admin. See *Troubleshooting* at
    the end.

  A practical shortcut: open one **elevated Command Prompt** at the start
  of §1 and do the whole installation from it. Once everything is on PATH,
  day-to-day GAM/GYB/rclone use does **not** require admin — only setup
  does.

- **Google Workspace edition that allows API access.** Free legacy / G
  Suite Basic without API access will not work — GAM needs the Admin SDK
  and Directory APIs which require Business Starter or higher (or any
  Education / Enterprise SKU). Cloud Identity Free is fine for identity
  operations but cannot drive Drive / Gmail scopes.

- **Network access** to `*.googleapis.com`, `accounts.google.com`,
  `oauth2.googleapis.com`, and `github.com` (for downloads). If you are
  behind a corporate proxy, set `HTTPS_PROXY` before running GAM, GYB, or
  rclone — all three honour it.

- **A successor mailbox / Drive owner ready** (only relevant if you plan
  to run the offboarding script after this guide — not needed for
  installation itself, but worth lining up now).

---

## 1. GAM7 — install, project, and service account

This is the longest step because it creates the shared credentials the
other two tools will reuse.

### 1.1 Install GAM7

1. Open the [GAM7 releases page](https://github.com/GAM-team/GAM/releases/latest)
   and download the **Windows 64-bit zip** (asset name like
   `gam-<version>-windows-x86_64.zip`). GAM7 does not ship as an MSI or
   via winget — use the zip.
2. Extract it to `C:\GAM7\`. You should end up with `C:\GAM7\gam.exe`.
3. Create the two companion folders the wiki convention uses:
   ```cmd
   mkdir C:\GAMConfig C:\GAMWork
   ```
   - `C:\GAMConfig` — holds credentials (`client_secrets.json`,
     `oauth2.txt`, `oauth2service.json`).
   - `C:\GAMWork` — default working directory for CSV imports/exports.
4. Set PATH and the GAM config env var **permanently** (machine-level).
   This step needs an **elevated Command Prompt** (right-click cmd →
   *Run as administrator*) because `/M` writes to the system
   environment:
   ```cmd
   setx PATH "%PATH%;C:\GAM7" /M
   setx GAMCFGDIR "C:\GAMConfig" /M
   ```
   Close **every** Command Prompt window and open a fresh one so the new
   environment is picked up. If you don't have admin, drop the `/M` —
   the variables will be set for your user only.
5. Please close your cmd terminal and then open a new one (non-elevated is fine). 
   ```cmd
   gam version
   gam config drive_dir C:\GAMWork verify
   ```

### 1.2 Create the Google Cloud project + service account

The single command `gam create project` does four things: creates a GCP
project, enables the right APIs, creates OAuth client credentials, **and
creates a service account with domain-wide delegation**. It writes three
files into `C:\GAMConfig\`:

| File | What it is |
|---|---|
| `client_secrets.json` | OAuth client for admin-as-user calls |
| `oauth2.txt` | Cached admin OAuth token (created in 1.3) |
| `oauth2service.json` | **Service-account private key — the shared credential GYB and rclone will reuse** |

Run:

```cmd
gam create project
```

Follow the prompts — sign in as a Super Admin when the browser opens, pick
or create a project, confirm. When it finishes, confirm the key file is
there:

```cmd
dir C:\GAMConfig\oauth2service.json
```

> **Keep `oauth2service.json` safe.** It is the private key for a service
> account that can impersonate any user in your tenant. Treat it like a
> password — don't email it, don't commit it to git, restrict NTFS
> permissions to your admin account.

### 1.3 Authorise the admin OAuth flow

```cmd
gam oauth create
```

Sign in as Super Admin in the browser tab it opens, paste the verification
code back. This writes `oauth2.txt`.

### 1.4 Authorise the service account scopes (covers all 3 tools)

This is the **key step** that lets one service account drive GAM, GYB, and
rclone. We authorise every scope the three tools will ever need, in one
visit to the Admin Console.

```cmd
gam user <super-admin@yourdomain.com> update serviceaccount
```

You'll see a numbered scope picker. Items already selected are shown as
`[*]`; unselected as `[ ]`. The list runs `0)` through `49)` in current
GAM7 builds.

**Good news: the defaults cover all three tools.** You do not need to
change anything. The relevant items you should verify are checked:

| # | Scope (exact label from the picker) | Required by | Default? |
|---|---|---|---|
| 22 | `Drive API (supports readonly)` | rclone | `[*]` yes |
| 29 | `Gmail API - Full Access (Labels, Messages)` | GYB (backup + restore, incl. delete) | `[*]` yes |

You can leave the other `[*]` defaults as-is — they're what GAM itself
needs.

Things to **leave unchecked** (do not toggle them on):

- `23) Drive API - write todrive data - has access to all Drive` — GAM
  internal `todrive` feature, not used by rclone.
- `31) Gmail API - Full Access - readonly` — superseded by 29.
- `32) Gmail API - Send Messages - including todrive` — not needed.

Optional (only tick if you know you need it):

- `30) Gmail API - Full Access (Labels, Messages) except delete message`
  is selected by default and is harmless. If you want the minimal
  surface, you can uncheck it since 29 is a superset.

Press `c` (or whatever the picker prompts) to **continue** with the
current selection. GAM will print an Admin Console URL — open it in a
browser signed in as Super Admin and click **Authorize**.

Then verify every scope is live:

```cmd
gam user <super-admin@yourdomain.com> check serviceaccount
```

All scopes should show **PASS**. If any show **FAIL**, re-run the command
and re-authorise in the printed URL.

#### Add the two GYB-only scopes (not in GAM's picker)

GAM's scope picker does not include two scopes that GYB requires —
`apps.groups.migration` and `drive.appdata`. Without them, GYB fails with
`unauthorized_client` even though `gam check serviceaccount` shows all
PASS, because the SA's domain-wide delegation grant doesn't include
them.

GYB ships its own checker that lists exactly what it needs:

```cmd
gyb --action check-service-account --email <super-admin@yourdomain.com>
```

You'll see something like:

```
Scope: https://mail.google.com/                                PASS
Scope: https://www.googleapis.com/auth/apps.groups.migration   FAIL
Scope: https://www.googleapis.com/auth/drive.appdata           FAIL
Scope: https://www.googleapis.com/auth/userinfo.email          PASS
```

To add the two missing scopes:

1. Browser → [admin.google.com/ac/owl/domainwidedelegation](https://admin.google.com/ac/owl/domainwidedelegation)
   (signed in as Super Admin).
2. Find the row matching your service-account Client ID (printed at the
   end of `gam check serviceaccount`, e.g.
   `Service Account Client name: 107739561933972426654`). Click the row
   → **Edit**.
3. In the **OAuth scopes** field, **append** these two to the existing
   comma-separated list (do *not* replace the list):
   ```
   https://www.googleapis.com/auth/apps.groups.migration,https://www.googleapis.com/auth/drive.appdata
   ```
4. Click **Authorize**.
5. Wait ~1 minute for DWD to propagate, then re-run the GYB check:
   ```cmd
   gyb --action check-service-account --email <super-admin@yourdomain.com>
   ```
   All four scopes should now show **PASS**.

> Why GAM's picker omits these: the picker only surfaces scopes GAM
> itself uses. `apps.groups.migration` and `drive.appdata` are
> GYB-specific, so you have to add them out-of-band in the Admin
> Console. This is a one-time step per service account.

### 1.5 GAM7 smoke test

```cmd
gam info domain
gam info user <super-admin@yourdomain.com>
```

Both should return real data. GAM7 is done.

---

## 2. GYB — install and connect to the shared service account

### 2.1 Install GYB

1. Open the [GYB releases page](https://github.com/GAM-team/got-your-back/releases/latest)
   and download the Windows 64-bit zip.
2. Extract to `C:\GYB\` (you should have `C:\GYB\gyb.exe`).
3. Add to PATH (run from an **elevated Command Prompt** because of `/M`;
   drop `/M` if you don't have admin):
   ```cmd
   setx PATH "%PATH%;C:\GYB" /M
   ```
   Close all cmd windows and open a fresh one.

### 2.2 Connect GYB to GAM's service account

GYB looks for `oauth2service.json` **in its own install folder** (it does
not read `GAMCFGDIR`). Point it at the GAM-issued key by creating a
symbolic link — that way, if you ever rotate the key via GAM, GYB picks
up the new file automatically.

Run from an **elevated Command Prompt**:

```cmd
mklink C:\GYB\oauth2service.json C:\GAMConfig\oauth2service.json
```

If you can't run as Administrator (and Developer Mode is off), copy the
file instead — you'll need to re-copy whenever the key rotates:

```cmd
copy C:\GAMConfig\oauth2service.json C:\GYB\oauth2service.json
```

> The Gmail and Groups Migration scopes you authorised in **§1.4** are
> what makes this work — GYB does not need its own OAuth client or
> project.

### 2.3 GYB smoke test

First, confirm GYB's own scope requirements are all authorised against
the service account:

```cmd
gyb --action check-service-account --email <super-admin@yourdomain.com>
```

You should see **PASS** for all four scopes:

```
Scope: https://mail.google.com/                                PASS
Scope: https://www.googleapis.com/auth/apps.groups.migration   PASS
Scope: https://www.googleapis.com/auth/drive.appdata           PASS
Scope: https://www.googleapis.com/auth/userinfo.email          PASS
```

If any show **FAIL**, go back to **§1.4** — specifically the
"*Add the two GYB-only scopes (not in GAM's picker)*" subsection — and
append the missing scopes to the SA's domain-wide delegation in the
Admin Console.

Once all four are PASS, run the live test:

```cmd
gyb --action quota --email <super-admin@yourdomain.com> --service-account
```

Should print the mailbox storage usage.

---

## 3. rclone — install and connect to the shared service account

### 3.1 Install rclone

Easiest path is winget (run from an elevated cmd):

```cmd
winget install Rclone.Rclone
```

Or manually: download the Windows zip from
[rclone.org/downloads](https://rclone.org/downloads/), extract to
`C:\rclone\`, and add to PATH (elevated cmd; drop `/M` if no admin):

```cmd
setx PATH "%PATH%;C:\rclone" /M
```

Verify in a fresh cmd window:
```cmd
rclone version
```

### 3.2 Create a Drive remote that uses the service account JSON

Run the interactive config:

```cmd
rclone config
```

Answer the prompts as follows:

| Prompt | Answer |
|---|---|
| `n) New remote` | `n` |
| `name>` | `gdrive` |
| `Storage>` | `drive` (Google Drive) |
| `client_id>` | *(leave blank — not used with a service account)* |
| `client_secret>` | *(leave blank)* |
| `scope>` | `1` (full `drive`) |
| `service_account_file>` | `C:\GAMConfig\oauth2service.json` |
| `Edit advanced config?` | `y` — we need to set `impersonate` |
| `impersonate>` | `<super-admin@yourdomain.com>` (the user the SA should act as) |
| Other advanced prompts | accept defaults (Enter) |
| `Use auto config?` | `n` (not relevant for SA) |
| `Configure as shared drive?` | `n` (unless you want one — answer `y` and pick the team drive) |
| `Keep this "gdrive" remote?` | `y` |
| Exit | `q` |

The resulting `rclone.conf` (in `%APPDATA%\rclone\rclone.conf`) should look
like:

```ini
[gdrive]
type = drive
scope = drive
service_account_file = C:\GAMConfig\oauth2service.json
impersonate = super-admin@yourdomain.com
```

### 3.3 rclone smoke test

```cmd
rclone lsd gdrive:
```

Should list the top-level folders of the impersonated user's Drive. To
target a different user without re-configuring, pass
`--drive-impersonate user@yourdomain.com` on the command line.

---

## 4. Final end-to-end check

Open a **fresh** Command Prompt and run:

```cmd
python --version
gam info domain
gyb --action quota --email <super-admin@yourdomain.com> --service-account
rclone lsd gdrive:
```

If all four succeed, the shared-service-account setup is working and you
can run the offboarding script. See `offboarding_test_setup_guide.md` to
build a safe test environment before pointing it at a real user.

---

## Troubleshooting

- **`gam` / `gyb` / `rclone` not recognized** — PATH update did not take
  effect. Close *all* cmd windows and open a new one. Verify with
  `echo %PATH%`.
- **`gam` writes to the wrong folder** — `GAMCFGDIR` is not set or not in
  your session. Run `echo %GAMCFGDIR%` (or `set GAMCFGDIR` to see if
  it's defined) and re-do `setx GAMCFGDIR "C:\GAMConfig" /M` from an
  elevated cmd if blank.
- **GYB: "service account not authorized for scope ..."** — go back to
  §1.4 and re-run `gam user ... update serviceaccount`, making sure the
  Gmail (`https://mail.google.com/`) scope is selected.
- **rclone: `failed to configure token: invalid_grant`** — the
  `impersonate` user does not exist or domain-wide delegation is not
  authorised. Re-run §1.4 with the Drive scope selected.
- **Key rotation** — to rotate the service-account key, re-run
  `gam create project` (or rotate via the GCP console) and overwrite
  `C:\GAMConfig\oauth2service.json`. GYB picks up the new key
  automatically if you used a symlink in §2.2; otherwise re-copy the
  file. rclone needs no change — it reads the path on every call.
- **`setx` truncates PATH** — `setx` cuts PATH longer than 1024 chars.
  Edit it via **System Properties → Environment Variables** instead.
- **Antivirus quarantines `gam.exe`** — some AV products flag GAM because
  it makes many Google API calls. Add `C:\GAM7\` to the AV exclusion list.
