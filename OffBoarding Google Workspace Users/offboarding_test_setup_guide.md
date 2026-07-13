# GAM7 Offboarding Script v5: Test Environment Setup & Backup Guide

## Step 0: Run the offline unit tests first (no tenant needed)

The repo ships `test_offboard_user.py` next to the script — a stdlib-only
unittest suite in which every GAM/GYB call is stubbed, so it runs in
seconds and never touches a Google Workspace tenant. Run it before and
after ANY change to `offboard_user.py`:

```bash
python3 test_offboard_user.py -v
```

All tests must pass before you move on to the live tests below. Several
tests pin behaviour that only surfaced against a live tenant (the
alias-transfer propagation race, suspension updates that report success
without taking effect, deprovision on mailbox-less users) — if one fails
after your change, the script has regressed on a real, observed failure
mode, not a theoretical one.

## Conventions used in this guide

All command examples are written to run identically on macOS, Linux, and
Windows (PowerShell and cmd.exe). To achieve that, the guide follows these
rules — keep them in mind if you adapt the commands:

- **Single-line commands.** No `\` line continuations. `\` works in bash/zsh
  but not in Windows cmd (`^`) or PowerShell (`` ` ``). Single-line commands
  side-step the difference entirely. Lines are long; let your terminal wrap.
- **Single quotes around string arguments**, e.g. `'Alice'`,
  `'/Test Users/Offboard Candidates'`, `'T3st!ng_0ffb0ard_2026'`. Single
  quotes prevent shell interpretation on every platform. Double quotes break
  on zsh whenever the string contains `!` (history expansion).
- **`python3`**, never bare `python`. Modern macOS no longer ships Python 2
  and `python` is unavailable; `python3` is the universal command on
  macOS and Linux.

  **Windows note:** the python.org installer does *not* create a
  `python3.exe` — only `python.exe` and the `py` launcher. To keep this
  guide's `python3 ...` examples working unchanged on Windows, follow
  `installation_windows.md` (the *Python prerequisite → "Create a
  `python3.cmd` shim"* block). It creates a one-line `python3.cmd`
  wrapper on PATH that forwards to `py -3`. With the shim in place,
  every `python3 offboard_user.py ...` example in this guide runs
  identically on every admin's machine — macOS, Linux, and Windows —
  with no command translation. If you skip the shim, Windows admins
  must manually translate every `python3` to `py -3` (or `python`)
  on the fly.
- **File-creation patterns are platform-specific.** `echo > /tmp/file` is
  POSIX-only; Windows uses `%TEMP%\file` (cmd) or `$env:TEMP\file`
  (PowerShell). Where this appears, the guide shows separate blocks.
- **GAM must be on PATH.** A shell alias is not enough — the offboarding
  script runs `gam` via Python subprocess, which does not load shell aliases.
  Add the GAM directory to PATH in your shell rc file
  (`export PATH="/path/to/gam7:$PATH"` on macOS/Linux,
  `setx PATH "%PATH%;C:\path\to\gam7"` on Windows).
- **zsh users: enable interactive comments.** By default zsh does *not*
  treat `#` as a comment in interactive shells, so pasting a block like
  `# Groups (member, manager, owner roles)` produces noisy errors
  (`zsh: command not found: #`, `zsh: number expected`,
  `zsh: unknown sort specifier`, `zsh: unknown group` — the parenthesised
  text is parsed as a glob qualifier). Fix once:
  ```bash
  echo 'setopt interactive_comments' >> ~/.zshrc
  setopt interactive_comments   # also apply to the current shell
  ```
  bash, PowerShell, and cmd treat `#`/`REM` as comments natively and need
  no change.

## Part 1: Test User Setup (5 Users)

### Prerequisites

Before creating test users, ensure:

- GAM7 is installed, authorised, and working (`gam info domain` succeeds)
- GYB is installed and configured with service account delegation (`gyb --action quota --email known_user@yourdomain.com`)
- rclone is installed (`rclone version`)
- You have a Google Workspace edition with available licences (5 needed) if you only have 1 spare, then you would have to do this multiple times.
- You have an OU structure ready (or the script below creates one)
- **Automatic license assignment is OFF** for your paid Workspace SKU (see the licensing note below)

#### Licensing: automatic-assignment trap

The offboarding script removes the paid Workspace licence from the user so the
seat can be reclaimed. If your tenant has **automatic license assignment**
turned on for the only Workspace SKU you own, GAM cannot leave the user with
zero licences — the licence is re-attached immediately and the `gam user ...
delete license` step in the script fails (or appears to succeed but the seat
is not freed).

Check and fix this **before** running the offboarding script:

1. **See which SKUs are on the tenant:**
   [https://admin.google.com/ac/billing/subscriptions](https://admin.google.com/ac/billing/subscriptions)
2. **Check automatic assignment:**
   [https://admin.google.com/ac/billing/licensesettings](https://admin.google.com/ac/billing/licensesettings)
   - If you can set automatic assignment to **OFF** for the paid SKU, do so — you are done.
   - If the tenant has only one paid SKU and the UI will not let you turn it off, continue to step 3.
3. **Add the free Cloud Identity Free SKU** so the offboarded user can fall back to it:
   [https://admin.google.com/ac/billing/catalog](https://admin.google.com/ac/billing/catalog)
   → add **Cloud Identity Free**. This gives the tenant a no-cost identity-only
   SKU that does not consume a paid seat.
4. Return to the licence settings page and set automatic assignment for the
   **paid** SKU to **OFF** (Cloud Identity Free can remain on automatic).
   Offboarded users will now drop the paid licence cleanly and land on Cloud
   Identity Free.

### Step 1: Create the Offboarding OU

This OU must have **no 2SV enforcement** policy applied. The script moves users
here during the kill switch phase.

```bash
gam create org '/Offboarding'
gam create org '/Test Users'
gam create org '/Test Users/Offboard Candidates'
```

If you need to delete an OU later, use:
```bash
gam delete org '/Test Users'
```

Go to your Google Admin console and check the 2SV setting for the `/Offboarding` organisational unit. Navigate to **Security > 2-Step Verification** ([https://admin.google.com/ac/security/2sv](https://admin.google.com/ac/security/2sv)), select the `/Offboarding` OU from the left menu, and confirm that "Enforcement" is set to "Off" or "Allow user to turn it on". Don't use "Enforce".

### Step 2: Create 5 Test Users

Each user is designed to test a different edge case in the offboarding script.

```bash
# User 1: Standard user (clean offboarding, all features)
gam create user testoffboard1@yourdomain.com firstname 'Alice' lastname 'Standard' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users/Offboard Candidates'

# User 2: User with 2SV enabled (tests turnoff2sv logic)
gam create user testoffboard2@yourdomain.com firstname 'Bob' lastname 'TwoFactor' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users/Offboard Candidates'

# User 3: User who is already suspended (tests the edge case)
gam create user testoffboard3@yourdomain.com firstname 'Charlie' lastname 'Suspended' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users/Offboard Candidates'

# User 4: User with delegated admin role (tests admin detection)
gam create user testoffboard4@yourdomain.com firstname 'Diana' lastname 'AdminUser' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users/Offboard Candidates'

# User 5: User with lots of data (groups, delegates, aliases, drive, forward)
gam create user testoffboard5@yourdomain.com firstname 'Evan' lastname 'DataHeavy' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users/Offboard Candidates'
```

**Wait 30 to 60 seconds** for mailbox provisioning before proceeding.

### Step 3: Create the Transfer Destination Users

`testoffboard.dest` is the single-destination receiver used by most tests
(Drive, aliases, forwarding, calendar access).

The three additional receivers (`testoffboard.manager`, `testoffboard.team`,
`testoffboard.ops`) are only used by the split-routing tests (5b and 5c)
that exercise the per-phase `--drive-to`, `--email-to`, `--all-transfer-to`
combinations. If you do not plan to run those tests, you can omit them.

```bash
gam create user testoffboard.dest@yourdomain.com firstname 'Transfer' lastname 'Destination' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users'

# Receivers used by split-routing tests (5b, 5c). Skip if you do not run those.
gam create user testoffboard.manager@yourdomain.com firstname 'Manager' lastname 'Receiver' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users'
gam create user testoffboard.team@yourdomain.com firstname 'Team' lastname 'Receiver' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users'
gam create user testoffboard.ops@yourdomain.com firstname 'Ops' lastname 'Receiver' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users'
```

### Step 4: Populate Test Data

#### User 1 (Alice Standard): Clean baseline

```bash
# Add to a few groups
gam create group offboard-test-group1@yourdomain.com name 'Offboard Test Group 1' description 'For offboarding tests'
gam create group offboard-test-group2@yourdomain.com name 'Offboard Test Group 2' description 'For offboarding tests'
gam update group offboard-test-group1@yourdomain.com add member testoffboard1@yourdomain.com
gam update group offboard-test-group2@yourdomain.com add member testoffboard1@yourdomain.com
# Set a vacation message (to verify it gets overwritten)
gam user testoffboard1@yourdomain.com vacation on subject 'Old vacation' message 'This is an old vacation reply'
```
We would like to add 5 files so that we can test the transfer of files to another user. The filename includes a timestamp so re-runs produce distinct files. Please see the command that works for your platform.
##### macOS/Linux
```bash
# Upload 5 test Drive files (timestamp in filename so re-runs don't collide)
TS=$(date +%Y%m%d_%H%M%S); for i in 1 2 3 4 5; do F="/tmp/offboard_test_${TS}_${i}.txt"; echo "Test file $i for offboarding" > "$F"; gam user testoffboard1@yourdomain.com add drivefile localfile "$F"; done
```
##### Windows - please run each line by itself not as 1 command
```cmd
# Build a filename-safe timestamp from %DATE% and %TIME% (slashes/colons/spaces stripped)
set "TS=%DATE:/=-%_%TIME::=-%"
set "TS=%TS: =0%"
# Create and upload 5 test Drive files
for /L %i in (1,1,5) do echo Test file %i for offboarding > "%TEMP%\offboard_test_%TS%_%i.txt"
for /L %i in (1,1,5) do gam user testoffboard1@yourdomain.com add drivefile localfile "%TEMP%\offboard_test_%TS%_%i.txt"
```


#### User 2 (Bob TwoFactor): 2SV enrolled

After creating User 2, you will need to **manually enrol them in 2SV**
by logging into their account in a browser and setting up an authenticator
app or security key. This cannot be done via GAM because 2SV enrolment
requires interactive user consent.

Alternatively, you can test the "2SV not enrolled" failure path by just
leaving this user without 2SV. The script should handle both cases.

```bash
# Add to a group
gam update group offboard-test-group1@yourdomain.com add member testoffboard2@yourdomain.com
```

#### User 3 (Charlie Suspended): Already suspended

```bash
# Add some data first, then suspend
gam update group offboard-test-group1@yourdomain.com add member testoffboard3@yourdomain.com
# Suspend the user
gam update user testoffboard3@yourdomain.com suspended on
```

This tests the edge case where `deprovision` partially fails (backup codes
cannot be revoked on suspended users) and `turnoff2sv` fails.

#### User 4 (Diana AdminUser): Has admin privileges

```bash
# Make this user a delegated admin
# NOTE: Replace with your actual admin role name
gam create admin testoffboard4@yourdomain.com _SEED_ADMIN_ROLE customer
# Add to groups
gam update group offboard-test-group1@yourdomain.com add manager testoffboard4@yourdomain.com
gam update group offboard-test-group2@yourdomain.com add owner testoffboard4@yourdomain.com
```

Reference : https://github.com/GAM-team/GAM/wiki/Administrators
_SEED_ADMIN_ROLE is the built-in name for the Super Admin role in GAM7. If you want a delegated admin role instead of super admin, you'd replace _SEED_ADMIN_ROLE with the name of your custom role, for example:
```bash
gam create admin testoffboard4@yourdomain.com 'Help Desk Admin' customer
```
The customer argument specifies the scope of the admin role assignment.
In Google Workspace, admin roles can be scoped in two ways:

**customer** means the role applies across the entire Google Workspace organisation (all OUs, all users, everything)
**org_unit** means the role is restricted to a specific OU only, for example org_unit '/Sales'

So **customer** is essentially saying "assign this super admin role with domain-wide scope." For super admin it's the only option that makes sense, since a super admin scoped to a single OU wouldn't really be a super admin. For more limited delegated admin roles though, OU scoping is useful, for example giving a helpdesk admin rights only over the /Support OU.
```bash
# Domain-wide (full org)
gam create admin user@yourdomain.com _SEED_ADMIN_ROLE customer

# OU-scoped (delegated admin for a specific OU only)
gam create admin user@yourdomain.com 'Help Desk Admin' org_unit '/Support'
```

#### User 5 (Evan DataHeavy): Fully loaded test case

```bash
# Groups (member, manager, owner roles)
gam update group offboard-test-group1@yourdomain.com add member testoffboard5@yourdomain.com
gam update group offboard-test-group2@yourdomain.com add manager testoffboard5@yourdomain.com
# Alias
gam create alias evan.legacy@yourdomain.com user testoffboard5@yourdomain.com
# Delegate (give destination user access to this mailbox)
# NOTE: the delegator must be active (not suspended) for this to succeed.
gam user testoffboard5@yourdomain.com delegate to testoffboard.dest@yourdomain.com
# Drive files: skip here — create & upload them in the platform-specific block below.
# Send test emails (so GYB has something to back up)
gam user testoffboard5@yourdomain.com sendemail recipient testoffboard5@yourdomain.com subject 'Test email 1' message 'This is a test for GYB backup'
gam user testoffboard5@yourdomain.com sendemail recipient testoffboard5@yourdomain.com subject 'Test email 2' message 'Another test for GYB backup'
gam user testoffboard5@yourdomain.com sendemail recipient testoffboard5@yourdomain.com subject 'Test email 3 with attachment' message 'Testing attachments'
# Email forwarding
gam user testoffboard5@yourdomain.com add forwardingaddress testoffboard.dest@yourdomain.com
# Recovery info (so the script can wipe it)
gam update user testoffboard5@yourdomain.com recoveryemail 'evan.personal@gmail.com' recoveryphone '+27821234567'
# Calendar event (so calendar transfer has something visible)
# The start/end strings must carry a timezone — append 'Z' (UTC) or an offset
# like '+02:00'. The standalone 'timezone' flag does NOT cover bare times and
# leaves GAM erroring with "Missing time zone definition for start time".
# Also requires the Calendar service to be enabled on the user's licence/OU.
gam user testoffboard5@yourdomain.com add event calendar testoffboard5@yourdomain.com summary 'Weekly Standup' start '2026-04-01T09:00:00Z' end '2026-04-01T09:30:00Z'
```
For the Drive file creation, use the appropriate platform block
### macOS/Linux
```bash
echo 'Confidential document for offboard test' > /tmp/offboard_confidential.txt
echo 'Project plan for offboard test' > /tmp/offboard_project.txt
gam user testoffboard5@yourdomain.com add drivefile localfile /tmp/offboard_confidential.txt
gam user testoffboard5@yourdomain.com add drivefile localfile /tmp/offboard_project.txt
```
### Windows
```cmd
echo Confidential document for offboard test > %TEMP%\offboard_confidential.txt
echo Project plan for offboard test > %TEMP%\offboard_project.txt
```
And then run the below to upload the files with GAM
```cmd
gam user testoffboard5@yourdomain.com add drivefile localfile '%TEMP%\offboard_confidential.txt'
gam user testoffboard5@yourdomain.com add drivefile localfile '%TEMP%\offboard_project.txt'
```

### Step 5: Run the Test Matrix

Run each user through the offboarding script. Start with dry runs.

```bash
# Test 1: Dry run on clean user (verify no errors in dry mode)
python3 offboard_user.py --user testoffboard1@yourdomain.com

# Test 2: Live run on clean user (full offboarding)
python3 offboard_user.py --doit --user testoffboard1@yourdomain.com

# Test 3: Already-suspended user (expect partial failures, verify handling)
# Interactively you are asked whether to temporarily unsuspend. With --force,
# the script NEVER unsuspends unless you explicitly add --unsuspend (v5.0.0
# behaviour change); without it the run continues in limited mode and the
# suspension-dependent steps fail with warnings.
python3 offboard_user.py --doit --user testoffboard3@yourdomain.com

# Test 3b: Already-suspended user, fully scripted with temporary unsuspend
# (re-suspended automatically at the end)
python3 offboard_user.py --doit --force --unsuspend --user testoffboard3@yourdomain.com --no-transfer

# Test 4: Admin user (verify detection warning)
python3 offboard_user.py --doit --user testoffboard4@yourdomain.com

# Test 5: Data-heavy user, fully scripted (non-interactive, one destination for everything)
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com

# Test 5b: Split routing — Drive to manager, everything else to team inbox
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.team@yourdomain.com --drive-to testoffboard.manager@yourdomain.com

# Test 5c: Per-phase routing with NO global default (every non-skipped phase needs its own flag)
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --drive-to testoffboard.manager@yourdomain.com --email-to testoffboard.ops@yourdomain.com --no-alias --no-calendar --no-forward

# Test 5d: --force without a destination should ABORT before any change (expected failure)
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com
# Expect: exit code 2, message listing missing destinations for drive/email/alias/calendar/forward

# Test 6: Data-heavy user with selective skips
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com --no-email --no-devices --no-suspend

# Test 7: 2SV user (test turnoff2sv success or graceful failure)
python3 offboard_user.py --doit --user testoffboard2@yourdomain.com

# Test 8: Backup Drive locally via rclone, then transfer ownership
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com --backup-drive

# Test 9: Backup email locally only (no restore to another user)
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com --backup-email

# Test 10: Backup both Drive and email locally, but do NOT transfer anything
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --no-transfer --backup-drive --backup-email

# Test 11: No-transfer mode (kill switch + suspend only, no data moves)
python3 offboard_user.py --doit --force --user testoffboard1@yourdomain.com --no-transfer

# Test 12: Scorched earth (DELETE the user entirely)
# WARNING: Creates a throwaway user to delete. Do NOT run on real accounts.
gam create user testoffboard.delete@yourdomain.com firstname 'Throwaway' lastname 'DeleteMe' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users/Offboard Candidates'
# Wait 30 seconds for mailbox provisioning
python3 offboard_user.py --doit --force --scorched-earth --user testoffboard.delete@yourdomain.com
# You will be prompted to type the email to confirm even with --force
```

### Step 6: Verify Results After Each Test

```bash
# Check the user is suspended and in the correct OU
gam info user testoffboard1@yourdomain.com quick

# Check groups were removed
gam user testoffboard1@yourdomain.com print groups

# Check GAL is off — read the output and look for the "Included in GAL" line.
# (Avoid `| grep` here: pipes-to-grep are not available on Windows cmd.exe.)
gam info user testoffboard1@yourdomain.com

# Check delegates were removed
gam user testoffboard5@yourdomain.com show delegates

# Check Drive files transferred (single-line; inner single quotes are the Drive query syntax)
gam user testoffboard.dest@yourdomain.com print filelist query "name contains 'offboard'"

# Check aliases transferred
gam print aliases user testoffboard.dest@yourdomain.com

# Check forwarding
gam user testoffboard5@yourdomain.com show forward

# Check the pre-flight snapshot was saved
ls -la ./offboarding_backups/snapshots/

# Check rclone Drive backup (if --backup-drive was used)
ls -la ./offboarding_backups/drive/
du -sh ./offboarding_backups/drive/*/

# Check GYB mailbox backups (migration or --backup-email)
ls -la ./offboarding_backups/mailboxes/

# Check scorched earth (user should be gone entirely)
gam info user testoffboard.delete@yourdomain.com
# Expected: "Does not exist"

# Check the log file
cat logs/offboarding_*.log
```

### Step 7: Clean Up After Testing

```bash
# Delete test users
gam delete user testoffboard1@yourdomain.com
gam delete user testoffboard2@yourdomain.com
gam delete user testoffboard3@yourdomain.com
gam delete user testoffboard4@yourdomain.com
gam delete user testoffboard5@yourdomain.com
gam delete user testoffboard.dest@yourdomain.com
gam delete user testoffboard.manager@yourdomain.com
gam delete user testoffboard.team@yourdomain.com
gam delete user testoffboard.ops@yourdomain.com

# Delete test groups
gam delete group offboard-test-group1@yourdomain.com
gam delete group offboard-test-group2@yourdomain.com

# Delete test OUs (must be empty first)
gam delete org '/Test Users/Offboard Candidates'
gam delete org '/Test Users'
# Keep /Offboarding for production use
```

---

## Part 2: Email Backup (GYB) and Drive Backup (rclone)

### Does the script back up emails with GYB?

**Yes, but only if you choose to.** The email migration phase (Phase 6) uses
GYB to back up the departing user's entire mailbox to a local folder and then
restore it into the destination user's mailbox. The two-step process:

```
gyb --email user@domain.com --action backup --local-folder ./offboarding_backups/mailboxes/user@domain.com_20260330/
gyb --email dest@domain.com --action restore --local-folder ./offboarding_backups/mailboxes/user@domain.com_20260330/ --label-restored 'Migrated/user@domain.com' --strip-labels
```

This is a **migration**, not just a backup. It copies the email from A to B.
The local folder is kept on disk as well, so you have a local copy too.

**Label handling (default: strip + archive).** As of v4.5.1 the restore step
passes `--strip-labels` to GYB so all original Gmail labels — including
`INBOX`, `Sent`, and any custom labels — are discarded on the destination side
and the only label left on each migrated message is `Migrated/<source-user>`.
The result: migrated mail does **not** flood the destination user's inbox; it
lives under one namespaced label that they can browse, archive in bulk, or
delete after a retention period.

You can change this per-run:

- `--strip-labels` — force the default (only `Migrated/<source-user>`, archived).
- `--keep-labels` — opt out: keep `INBOX`, `Sent`, and custom labels and add
  `Migrated/<source-user>` on top. Useful if the destination user needs to see
  the original mailbox structure.
- Neither flag set, no `--force` — the script asks interactively (default = strip).
- Neither flag set, `--force` — strip is applied silently.

If you skip the migration (using `--no-email`) but still want a local backup
without restoring to another user, you can run GYB manually:

```bash
# Backup only (no restore)
gyb --email testoffboard5@yourdomain.com --action backup --local-folder ./offboarding_backups/mailboxes/testoffboard5_archive/
```

**Important:** GYB requires the user to NOT be suspended. If you have already
suspended the user, you need to unsuspend them first, run the backup, then
re-suspend.

### What happens if antivirus quarantines a backed-up message?

If the source mailbox contains a malicious email, your endpoint antivirus may
quarantine the corresponding `.eml` file on local disk right after GYB writes
it during the backup. The file still exists but cannot be read, and GYB's
restore would crash on it partway through.

As of v4.7.0 the script handles this automatically. Between backup and
restore it probes every backed-up `.eml` file; any unreadable file is moved to
a sibling folder next to the backup:

```
offboarding_backups/mailboxes/user@domain.com_20260330/              <- backup (GYB reads this)
offboarding_backups/mailboxes/user@domain.com_20260330_quarantined/  <- unreadable files moved here
offboarding_backups/mailboxes/user@domain.com_20260330_skipped-messages.csv
```

GYB then skips the missing files and the restore completes in one pass. The
skip machinery can be self-tested by `chmod 000` on one backed-up `.eml`
between backup and restore — but ONLY on a local-disk backup directory.
Inside an iCloud Drive folder the file provider silently restores the
read permission within seconds and the simulation no-ops (real antivirus
locks are unaffected — the scan probes actual reads, whatever the lock
mechanism). The
CSV lists each skipped message's Gmail message ID (the `.eml` filename), its
date, and where the file was moved. Those messages are intentionally NOT
restored to the destination mailbox — they are the flagged mail. To see what
each one was, search by message ID in your antivirus quarantine log, Google
Vault, or the Security Investigation Tool. The run summary also flags the
skip count.

### Does the script back up Drive files with rclone?

**Yes, when you use `--backup-drive`.** The v4.3 script has rclone support
built in. When you pass `--backup-drive`, it runs `rclone sync` with
`--drive-impersonate` to download the user's entire Drive to a local folder
BEFORE any ownership transfer happens via `transfer drive`.

You can also combine `--backup-drive` with `--no-transfer` to download files
locally without transferring ownership to anyone, effectively creating an
archive-only offboarding.

The dependency check verifies that rclone is installed AND that the configured
remote (set via `RCLONE_REMOTE` in the script) actually exists in
`rclone listremotes`. If either check fails, the script aborts before making
any changes.

### How to configure rclone for the offboarding script

rclone can use GAM7's existing service account credentials, so you do not need
a separate GCP project. Here is how to set it up and integrate it:

#### Step 1: Configure rclone with GAM7's service account

```bash
rclone config
```

Choose:

1. New remote
2. Name it `workspace` (or whatever you prefer)
3. Storage type: `drive` (Google Drive)
4. Client ID: copy from your GAM7 `client_secrets.json` file
5. Client secret: copy from the same file
6. Scope: `drive` (full access)
7. Service account file: point to your GAM7 `oauth2service.json`
8. Skip the browser auth (you are using a service account)

The key setting is the **service account file**. This lets rclone impersonate
users via domain-wide delegation, the same way GAM7 does.

#### Step 2: Test rclone access

```bash
# List the root of a user's Drive
rclone lsd workspace: --drive-impersonate testoffboard5@yourdomain.com

# Check total size
rclone size workspace: --drive-impersonate testoffboard5@yourdomain.com
```

#### Step 3: Back up a user's entire Drive locally

The script does this automatically when you pass `--backup-drive`:

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --backup-drive
```

Files are saved to `./offboarding_backups/drive/<email>_<date>/`.

If you want to test rclone manually first:

```bash
mkdir -p ./offboarding_backups/drive/testoffboard5/
rclone sync workspace: ./offboarding_backups/drive/testoffboard5/ --drive-impersonate testoffboard5@yourdomain.com --drive-export-formats docx,xlsx,pptx,pdf -P --fast-list --transfers=4
```

**Export formats explained:** Google Docs, Sheets, and Slides are not real
files; they are cloud-native objects. rclone converts them to downloadable
formats using `--drive-export-formats`. The setting `docx,xlsx,pptx,pdf` means:

- Google Docs become .docx
- Google Sheets become .xlsx
- Google Slides become .pptx
- Anything else falls back to .pdf

### Recommended backup strategy for offboarding

**rclone and GAM7 do different jobs — they are not alternatives.** rclone (`--backup-drive`) downloads the user's Drive to **local disk** as an offline archive. GAM7's Drive transfer (default, controlled by `--drive-to` / `--all-transfer-to`) reassigns **ownership inside Google Workspace** to another user; the files stay in the cloud. Use rclone when you want a copy that survives the source/destination accounts being deleted or that includes exported Office-format versions of Google-native files. Use GAM7 transfer when you want a teammate (e.g. the leaver's manager) to take over the files. You can use either, both, or neither — they are independent flags.

| Data type | Tool | Flag | What it does |
|-----------|------|------|-------------|
| Email (archive) | GYB | `--backup-email` | Downloads mailbox to local disk, no restore |
| Email (migrate) | GYB | (default) | Backs up and restores to destination user |
| Drive (archive) | rclone | `--backup-drive` | Downloads Drive to local disk |
| Drive (transfer) | GAM7 | (default) | Transfers ownership inside Google |
| Drive (both) | rclone+GAM7 | `--backup-drive` | Downloads first, then transfers |
| Calendar | GAM7 | (default) | Grants editor access to successor |
| All data, no moves | Various | `--no-transfer --backup-drive --backup-email` | Archive everything, move nothing |
| Nothing at all | GAM7 | `--scorched-earth` | Kill, suspend, delete |

### Order of operations for data preservation

This is the recommended sequence when you need both backups and transfers:

1. **rclone Drive backup** (local copy of files before any changes)
2. **GYB email backup** (local copy of mailbox)
3. **GAM7 Drive transfer** (ownership changes in Google)
4. **GYB email restore** (copy mailbox to destination user)
5. **GAM7 alias transfer** (redirect incoming mail)
6. **GAM7 forwarding setup** (catch new incoming mail — Gmail-level,
   stops working once the user is suspended/deleted)
7. **Suspension** (lock the account)
8. **Manual mail capture** (after the run — see the MANUAL ACTION block
   printed at the end of the summary, or the section below)

The key principle is: **back up before you transfer, transfer before you
suspend**. For durable mail capture beyond suspension, see the **Mail
capture after suspension** section below.

---

## Part 3: Quick Reference for Test Runs

### Dry run (safest, always start here)

```bash
python3 offboard_user.py --user testoffboard5@yourdomain.com
```

### Full live run with all prompts

```bash
python3 offboard_user.py --doit --user testoffboard5@yourdomain.com
```

### Transfer destination flags — how to think about them

There are six flags that control where a departing user's data ends up. Use
them in this order of thinking:

1. **`--all-transfer-to <email>`** — the global default. If you set only this,
   every non-skipped transfer phase (Drive, Email, Alias, Calendar, Forward)
   goes to that one address. This is the common case.
2. **Per-phase flags** override `--all-transfer-to` for a single phase:
   - `--drive-to <email>` — Drive ownership transfer destination
   - `--email-to <email>` — Mailbox migration target (via GYB)
   - `--alias-to <email>` — Alias re-assignment target
   - `--calendar-to <email>` — Calendar access grant target
   - `--forward-to <email>` — Gmail forwarding destination
3. **`--no-<phase>` skips** opt a phase out of the requirement entirely.

**Precedence (highest wins):** per-phase flag → `--all-transfer-to` → interactive
prompt (only when `--force` is **not** set).

**Behaviour under `--force`:** the script resolves every non-skipped phase's
destination up front and validates each address against the directory. If any
phase has no resolvable destination, the run aborts with exit code 2 **before
any destructive action**. This protects against half-offboarding from a typo
or forgotten flag.

**`--force` and suspended users (v5.0.0):** `--force` answers every prompt
with yes EXCEPT the temporary-unsuspend question. An already-suspended user
is only reactivated when you explicitly pass `--unsuspend`; without it the
run continues in limited mode (suspension-dependent steps fail with
warnings) and the account is never made less restricted than it started.

**Behaviour without `--force`:** any phase without a flag-resolved destination
falls back to an interactive prompt at runtime (current behaviour preserved).

### Mail capture after suspension (manual step)

`--forward-to` configures **Gmail-level forwarding**, which only works while
the source account is active. Once the user is suspended or deleted, Gmail
forwarding stops — inbound mail to their address bounces. GAM cannot
configure the **"Recipient address map"** routing feature that would solve
this, so the script handles it as a documented manual step instead.

At the very end of every run that knows a successor address, the script
prints a **MANUAL ACTION REQUIRED** block to both the console and the log
file. The block lists three admin-console options for durable mail capture:

1. **Add as alias on the successor** — simplest, single recipient. Requires
   the offboarded address to be released first (delete or rename the user).
2. **Recipient address map** (Admin console → Apps → Google Workspace →
   Gmail → Default routing) — works even while the offboarded user still
   exists. Rewrites the envelope recipient on inbound mail.
3. **Convert to a Group** — supports multiple recipients.

The successor printed in the block is resolved in this order:

1. `--forward-alias-to <email>` — explicit override for this block only.
2. `--forward-to <email>` — falls back to the Gmail-forwarding destination.
3. `--all-transfer-to <email>` — falls back to the global default.

If none of these are set, the block is suppressed. No automated change is
made for this — the script only surfaces the checklist.

### Fully scripted (no prompts, single destination for everything)

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com
```

### Split routing (Drive to one person, everything else to another)

```bash
# Drive ownership goes to the manager; mail/aliases/calendar/forward go to a team alias.
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.team@yourdomain.com --drive-to testoffboard.manager@yourdomain.com
```

### Fully per-phase routing (no global default)

```bash
# Every non-skipped phase must specify its own destination. Skipped phases need --no-*.
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --drive-to testoffboard.manager@yourdomain.com --email-to testoffboard.ops@yourdomain.com --no-alias --no-calendar --no-forward
```

### Selective run (skip heavy operations)

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com --no-email --no-devices
```

### Backup Drive and email locally, then transfer

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com --backup-drive --backup-email
```

### Backup only, no transfers at all (archive mode)

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --no-transfer --backup-drive --backup-email
```

### Backup email only, no restore (local archive)

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --backup-email --no-email
```

### No-transfer mode (kill switch + suspend, nothing else)

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --no-transfer
```

### Transition mode (no suspension, keep account alive)

```bash
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --all-transfer-to testoffboard.dest@yourdomain.com --no-suspend
```

### Scorched earth (DELETE user permanently)

```bash
python3 offboard_user.py --doit --force --scorched-earth --user testoffboard5@yourdomain.com
# Even with --force, you must type the email to confirm deletion
```
