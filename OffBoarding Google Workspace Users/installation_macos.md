# macOS Installation Guide: GAM7, GYB, and rclone

This guide installs three tools on **macOS (Apple Silicon — M1/M2/M3/M4)**
and wires them all to a **single Google service account** that GAM7
provisions:

1. **GAM7** — creates the GCP project, the service account, and downloads
   the service-account JSON key (`oauth2service.json`).
2. **GYB** — re-uses the same `oauth2service.json` for mailbox archive.
3. **rclone** — re-uses the same `oauth2service.json` for cloud storage.

One service account, three tools, one set of scope authorisations in the
Admin Console.

Run everything from **Terminal.app** (or iTerm2) — the default shell on
modern macOS is **zsh**, so the commands below assume `~/.zshrc` for
persistent environment changes. If you're still on bash, substitute
`~/.bash_profile` everywhere `~/.zshrc` appears.

---

## 0. Prerequisites

- Google Workspace tenant where you are a **Super Admin**.
- **Python 3.10+** on PATH:
  ```bash
  python3 --version
  ```
  macOS ships a stub `python3` at `/usr/bin/python3` that triggers the
  Xcode Command Line Tools installer on first use — that's acceptable but
  slow to update. Two better options:

  - **python.org installer** (preferred for predictable versioning).
    Download the *macOS 64-bit universal2 installer* from
    [python.org/downloads/macos](https://www.python.org/downloads/macos/),
    run the `.pkg`, and it adds `python3` to PATH automatically by
    writing into `/etc/paths.d/`. Open a fresh Terminal afterwards.
  - **Homebrew** — `brew install python` works fine if you already use
    Homebrew for other things, but this guide otherwise avoids Homebrew
    for parity with the Windows guide.

  Unlike Windows there is **no `python3` vs `python` confusion** on macOS
  — `python3` is the universal command and every example in the repo
  (offboarding script, test setup guide) uses it as-is.

- **A directory for user-scoped binaries.** This guide installs all
  three tools under `~/bin/`. Create it now if it doesn't exist:

  ```bash
  mkdir -p ~/bin
  ```

  No `sudo` is needed anywhere in this guide — everything lives in your
  home directory. That also means no `/usr/local` or `/opt/homebrew`
  pollution, no system-wide PATH edits, and no admin password prompts
  during day-to-day use.

- **Gatekeeper / quarantine awareness.** Anything you download via a
  browser gets the `com.apple.quarantine` extended attribute, and on
  first run macOS will pop *"cannot be opened because the developer
  cannot be verified"* for unsigned binaries. The official GAM7 and GYB
  install scripts use `curl` (which doesn't set the quarantine bit), so
  this is mostly a non-issue. If you do hit it on a manually-downloaded
  binary, clear the attribute:

  ```bash
  xattr -d com.apple.quarantine /path/to/binary
  ```

  Alternatively, after the "cannot be opened" dialog appears once, open
  **System Settings → Privacy & Security**, scroll to the *Security*
  section, and click **Open Anyway** for the blocked binary. Same effect.

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

GAM7 ships an official installer for macOS that detects your
architecture (arm64 on Apple Silicon), downloads the right binary,
extracts to `~/bin/gam7/`, and edits your shell rc file to add `~/bin/gam7`
to PATH and set `GAMCFGDIR=~/.gam/gam7`.

```bash
bash <(curl -s -S -L https://git.io/install-gam) -l
```

The `-l` flag picks the "latest stable" channel non-interactively. When
it finishes, **close Terminal and open a fresh window** so the rc-file
changes take effect.

Verify:

```bash
gam version
```

You should see GAM7 print its version and the config directory
(`~/.gam/gam7` by default). If you prefer a different config path —
e.g. to mirror the Windows convention of one obvious folder — export it
in `~/.zshrc`:

```bash
echo 'export GAMCFGDIR="$HOME/.gam"' >> ~/.zshrc
```

For the rest of this guide we'll refer to the config dir as
**`$GAMCFGDIR`** — whatever path GAM picked or you overrode.

Create a working directory for CSV imports/exports (analogous to
`C:\GAMWork` on Windows):

```bash
mkdir -p ~/GAMWork
gam config drive_dir ~/GAMWork verify
```

### 1.2 Create the Google Cloud project + service account

The single command `gam create project` does four things: creates a GCP
project, enables the right APIs, creates OAuth client credentials, **and
creates a service account with domain-wide delegation**. It writes three
files into `$GAMCFGDIR`:

| File | What it is |
|---|---|
| `client_secrets.json` | OAuth client for admin-as-user calls |
| `oauth2.txt` | Cached admin OAuth token (created in 1.3) |
| `oauth2service.json` | **Service-account private key — the shared credential GYB and rclone will reuse** |

Run:

```bash
gam create project
```

Follow the prompts — sign in as a Super Admin when the browser opens, pick
or create a project, confirm. When it finishes, confirm the key file is
there:

```bash
ls -l "$GAMCFGDIR/oauth2service.json"
```

> **Keep `oauth2service.json` safe.** It is the private key for a service
> account that can impersonate any user in your tenant. Treat it like a
> password — don't email it, don't commit it to git. The file is already
> created with mode `600` (owner read/write only); leave it that way.

### 1.3 Authorise the admin OAuth flow

```bash
gam oauth create
```

Sign in as Super Admin in the browser tab it opens, paste the verification
code back. This writes `oauth2.txt`.

### 1.4 Authorise the service account scopes (covers all 3 tools)

This is the **key step** that lets one service account drive GAM, GYB, and
rclone. We authorise every scope the three tools will ever need, in one
visit to the Admin Console.

```bash
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

```bash
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

```bash
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
   ```bash
   gyb --action check-service-account --email <super-admin@yourdomain.com>
   ```
   All four scopes should now show **PASS**.

> Why GAM's picker omits these: the picker only surfaces scopes GAM
> itself uses. `apps.groups.migration` and `drive.appdata` are
> GYB-specific, so you have to add them out-of-band in the Admin
> Console. This is a one-time step per service account.

### 1.5 GAM7 smoke test

```bash
gam info domain
gam info user <super-admin@yourdomain.com>
```

Both should return real data. GAM7 is done.

---

## 2. GYB — install and connect to the shared service account

### 2.1 Install GYB

GYB has an official installer matching the GAM one. It places the binary
at `~/bin/gyb/gyb` and adds `~/bin/gyb` to PATH in `~/.zshrc`:

```bash
bash <(curl -s -S -L https://git.io/gyb-install) -l
```

Close Terminal and open a fresh window. Verify:

```bash
gyb --version
```

### 2.2 Connect GYB to GAM's service account

GYB looks for `oauth2service.json` **in its own install folder** (it does
not read `GAMCFGDIR`). Point it at the GAM-issued key by creating a
symbolic link — that way, if you ever rotate the key via GAM, GYB picks
up the new file automatically.

```bash
ln -s "$GAMCFGDIR/oauth2service.json" ~/bin/gyb/oauth2service.json
```

> Symlinks need no special permissions on macOS — unlike Windows, there's
> no Developer Mode toggle. If the link already exists from a previous
> install, replace it with `ln -sf ...`.

> The Gmail and Groups Migration scopes you authorised in **§1.4** are
> what makes this work — GYB does not need its own OAuth client or
> project.

### 2.3 GYB smoke test

First, confirm GYB's own scope requirements are all authorised against
the service account:

```bash
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

```bash
gyb --action quota --email <super-admin@yourdomain.com> --service-account
```

Should print the mailbox storage usage.

---

## 3. rclone — install and connect to the shared service account

### 3.1 Install rclone

Download the Apple Silicon zip from
[rclone.org/downloads](https://rclone.org/downloads/) — the asset name is
`rclone-current-osx-arm64.zip`. Or from Terminal:

```bash
cd /tmp
curl -L -o rclone.zip https://downloads.rclone.org/rclone-current-osx-arm64.zip
unzip rclone.zip
mv rclone-*-osx-arm64/rclone ~/bin/rclone
chmod +x ~/bin/rclone
rm -rf rclone.zip rclone-*-osx-arm64
```

Make sure `~/bin` is on PATH. The GAM/GYB installers already added
`~/bin/gam7` and `~/bin/gyb` to `~/.zshrc`, but not `~/bin` itself.
Append it:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
```

Open a fresh Terminal and verify:

```bash
rclone version
```

If macOS blocks the binary on first run with *"cannot be opened because
the developer cannot be verified"*, clear the quarantine attribute:

```bash
xattr -d com.apple.quarantine ~/bin/rclone
```

### 3.2 Create a Drive remote that uses the service account JSON

Run the interactive config:

```bash
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
| `service_account_file>` | `~/.gam/oauth2service.json` (or wherever `$GAMCFGDIR` points — use the **absolute** path, not `$GAMCFGDIR`, since rclone doesn't expand env vars in its config) |
| `Edit advanced config?` | `y` — we need to set `impersonate` |
| `impersonate>` | `<super-admin@yourdomain.com>` (the user the SA should act as) |
| Other advanced prompts | accept defaults (Enter) |
| `Use auto config?` | `n` (not relevant for SA) |
| `Configure as shared drive?` | `n` (unless you want one — answer `y` and pick the team drive) |
| `Keep this "gdrive" remote?` | `y` |
| Exit | `q` |

The resulting `rclone.conf` (at `~/.config/rclone/rclone.conf`) should
look like:

```ini
[gdrive]
type = drive
scope = drive
service_account_file = /Users/you/.gam/oauth2service.json
impersonate = super-admin@yourdomain.com
```

> Note the **absolute** path. `~` and `$GAMCFGDIR` are shell constructs;
> rclone reads its config as a plain ini file and won't expand them.

### 3.3 rclone smoke test

```bash
rclone lsd gdrive:
```

Should list the top-level folders of the impersonated user's Drive. To
target a different user without re-configuring, pass
`--drive-impersonate user@yourdomain.com` on the command line.

---

## 4. Final end-to-end check

Open a **fresh** Terminal window and run:

```bash
python3 --version
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
  effect. Close *all* Terminal windows and open a new one, or run
  `source ~/.zshrc`. Verify with `echo $PATH`.
- **`gam` writes to the wrong folder** — `GAMCFGDIR` is not set or not in
  your session. Run `echo $GAMCFGDIR`; if empty, add
  `export GAMCFGDIR="$HOME/.gam"` to `~/.zshrc` and open a fresh
  Terminal.
- **GYB: "service account not authorized for scope ..."** — go back to
  §1.4 and re-run `gam user ... update serviceaccount`, making sure the
  Gmail (`https://mail.google.com/`) scope is selected. Also double-check
  the two GYB-only scopes are appended in the Admin Console (§1.4
  subsection).
- **rclone: `failed to configure token: invalid_grant`** — the
  `impersonate` user does not exist or domain-wide delegation is not
  authorised. Re-run §1.4 with the Drive scope selected.
- **rclone: `service_account_file` not found** — you used `~` or
  `$GAMCFGDIR` instead of an absolute path in `rclone.conf`. Edit
  `~/.config/rclone/rclone.conf` and replace with the full
  `/Users/<you>/...` path.
- **"cannot be opened because the developer cannot be verified"** —
  Gatekeeper quarantine. Run `xattr -d com.apple.quarantine <path>` or
  approve the binary in System Settings → Privacy & Security.
- **Key rotation** — to rotate the service-account key, re-run
  `gam create project` (or rotate via the GCP console) and overwrite
  `$GAMCFGDIR/oauth2service.json`. GYB picks up the new key automatically
  via the symlink from §2.2. rclone needs no change — it reads the path
  on every call.
- **`python3` opens Xcode installer prompt** — you're on the Apple-shipped
  stub at `/usr/bin/python3`. Install from python.org (§0) and open a
  fresh Terminal so the new `/usr/local/bin/python3` wins on PATH.
