# GAM7 Offboarding Script v4.3: Test Environment Setup & Backup Guide

## Part 1: Test User Setup (5 Users)

### Prerequisites

Before creating test users, ensure:

- GAM7 is installed, authorised, and working (`gam info domain` succeeds)
- GYB is installed and configured with service account delegation (`gyb --action quota --email known_user@yourdomain.com`)
- rclone is installed (`rclone version`)
- You have a Google Workspace edition with available licences (5 needed) if you only have 1 spare, then you would have to do this multiple times.
- You have an OU structure ready (or the script below creates one)

### Step 1: Create the Offboarding OU

This OU must have **no 2SV enforcement** policy applied. The script moves users
here during the kill switch phase.

```bash
gam create org "/Offboarding"
gam create org "/Test Users"
gam create org "/Test Users/Offboard Candidates"
```

If you need to delete an OU later, use:
```bash
gam delete org "/Test Users"
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

### Step 3: Create the Transfer Destination User

This is the user who will receive Drive files, aliases, forwarding, and
calendar access during offboarding tests.

```bash
gam create user testoffboard.dest@yourdomain.com firstname 'Transfer' lastname 'Destination' password 'T3st!ng_0ffb0ard_2026' changepassword off org '/Test Users'
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
We would like to add a file so that we can test the transfer of the file to another user. Please see the comand that works for your platform.
##### macOS/Linux
```bash
# Upload a test Drive file
echo 'Test file for offboarding' > /tmp/offboard_test.txt
gam user testoffboard1@yourdomain.com add drivefile localfile /tmp/offboard_test.txt
```
##### Windows - please run each line by itself not as 1 command
```cmd
# Upload a test Drive file
echo Test file for offboarding > %TEMP%\offboard_test.txt
gam user testoffboard1@yourdomain.com add drivefile localfile '%TEMP%\offboard_test.txt'
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
gam user testoffboard5@yourdomain.com delegate to testoffboard.dest@yourdomain.com
# Drive files (see platform-specific file creation notes below)
gam user testoffboard5@yourdomain.com add drivefile localfile /tmp/offboard_confidential.txt
gam user testoffboard5@yourdomain.com add drivefile localfile /tmp/offboard_project.txt
# Send test emails (so GYB has something to back up)
gam user testoffboard5@yourdomain.com sendemail recipient testoffboard5@yourdomain.com subject 'Test email 1' message 'This is a test for GYB backup'
gam user testoffboard5@yourdomain.com sendemail recipient testoffboard5@yourdomain.com subject 'Test email 2' message 'Another test for GYB backup'
gam user testoffboard5@yourdomain.com sendemail recipient testoffboard5@yourdomain.com subject 'Test email 3 with attachment' message 'Testing attachments'
# Email forwarding
gam user testoffboard5@yourdomain.com add forwardingaddress testoffboard.dest@yourdomain.com
# Recovery info (so the script can wipe it)
gam update user testoffboard5@yourdomain.com recoveryemail 'evan.personal@gmail.com' recoveryphone '+27821234567'
# Calendar event (so calendar transfer has something visible)
gam user testoffboard5@yourdomain.com add event calendar testoffboard5@yourdomain.com summary 'Weekly Standup' start '2026-04-01T09:00:00' end '2026-04-01T09:30:00'
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
python3 offboard_user.py --doit --user testoffboard3@yourdomain.com

# Test 4: Admin user (verify detection warning)
python3 offboard_user.py --doit --user testoffboard4@yourdomain.com

# Test 5: Data-heavy user, fully scripted (non-interactive)
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --transfer-to testoffboard.dest@yourdomain.com

# Test 6: Data-heavy user with selective skips
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --transfer-to testoffboard.dest@yourdomain.com --no-email --no-devices --no-suspend

# Test 7: 2SV user (test turnoff2sv success or graceful failure)
python3 offboard_user.py --doit --user testoffboard2@yourdomain.com

# Test 8: Backup Drive locally via rclone, then transfer ownership
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --transfer-to testoffboard.dest@yourdomain.com --backup-drive

# Test 9: Backup email locally only (no restore to another user)
python3 offboard_user.py --doit --force --user testoffboard5@yourdomain.com --transfer-to testoffboard.dest@yourdomain.com --backup-email

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

# Check GAL is off
gam info user testoffboard1@yourdomain.com | grep -i "gal"

# Check delegates were removed
gam user testoffboard5@yourdomain.com show delegates

# Check Drive files transferred
gam user testoffboard.dest@yourdomain.com print filelist \
    query "name contains 'offboard'"

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

# Delete test groups
gam delete group offboard-test-group1@yourdomain.com
gam delete group offboard-test-group2@yourdomain.com

# Delete test OUs (must be empty first)
gam delete org "/Test Users/Offboard Candidates"
gam delete org "/Test Users"
# Keep /Offboarding for production use
```

---

## Part 2: Email Backup (GYB) and Drive Backup (rclone)

### Does the script back up emails with GYB?

**Yes, but only if you choose to.** The email migration phase (Phase 6) uses
GYB to back up the departing user's entire mailbox to a local folder and then
restore it into the destination user's mailbox. The two-step process:

```
gyb --email user@domain.com --action backup \
    --local-folder ./offboarding_backups/mailboxes/user@domain.com_20260330/
gyb --email dest@domain.com --action restore \
    --local-folder ./offboarding_backups/mailboxes/user@domain.com_20260330/ \
    --label-restored "Migrated/user@domain.com"
```

This is a **migration**, not just a backup. It copies the email from A to B.
The local folder is kept on disk as well, so you have a local copy too.

Restored messages are tagged with a `Migrated/<source-user>` label on the
destination mailbox, so the destination user can easily filter, archive, or
move the migrated mail in bulk without touching their own inbox. Existing
labels (including INBOX) are preserved — the migration label is added on top.

If you skip the migration (using `--no-email`) but still want a local backup
without restoring to another user, you can run GYB manually:

```bash
# Backup only (no restore)
gyb --email testoffboard5@yourdomain.com \
    --action backup \
    --local-folder ./offboarding_backups/mailboxes/testoffboard5_archive/
```

**Important:** GYB requires the user to NOT be suspended. If you have already
suspended the user, you need to unsuspend them first, run the backup, then
re-suspend.

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
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --backup-drive
```

Files are saved to `./offboarding_backups/drive/<email>_<date>/`.

If you want to test rclone manually first:

```bash
mkdir -p ./offboarding_backups/drive/testoffboard5/

rclone sync \
    workspace: ./offboarding_backups/drive/testoffboard5/ \
    --drive-impersonate testoffboard5@yourdomain.com \
    --drive-export-formats docx,xlsx,pptx,pdf \
    -P --fast-list --transfers=4
```

**Export formats explained:** Google Docs, Sheets, and Slides are not real
files; they are cloud-native objects. rclone converts them to downloadable
formats using `--drive-export-formats`. The setting `docx,xlsx,pptx,pdf` means:

- Google Docs become .docx
- Google Sheets become .xlsx
- Google Slides become .pptx
- Anything else falls back to .pdf

### Recommended backup strategy for offboarding

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
6. **GAM7 forwarding setup** (catch new incoming mail)
7. **Suspension** (lock the account)

The key principle is: **back up before you transfer, transfer before you
suspend**.

---

## Part 3: Quick Reference for Test Runs

### Dry run (safest, always start here)

```bash
python offboard_user.py --user testoffboard5@yourdomain.com
```

### Full live run with all prompts

```bash
python offboard_user.py --doit --user testoffboard5@yourdomain.com
```

### Fully scripted (no prompts, single destination)

```bash
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --transfer-to testoffboard.dest@yourdomain.com
```

### Selective run (skip heavy operations)

```bash
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --transfer-to testoffboard.dest@yourdomain.com \
    --no-email --no-devices
```

### Backup Drive and email locally, then transfer

```bash
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --transfer-to testoffboard.dest@yourdomain.com \
    --backup-drive --backup-email
```

### Backup only, no transfers at all (archive mode)

```bash
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --no-transfer --backup-drive --backup-email
```

### Backup email only, no restore (local archive)

```bash
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --backup-email --no-email
```

### No-transfer mode (kill switch + suspend, nothing else)

```bash
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --no-transfer
```

### Transition mode (no suspension, keep account alive)

```bash
python offboard_user.py --doit --force \
    --user testoffboard5@yourdomain.com \
    --transfer-to testoffboard.dest@yourdomain.com \
    --no-suspend
```

### Scorched earth (DELETE user permanently)

```bash
python offboard_user.py --doit --force --scorched-earth \
    --user testoffboard5@yourdomain.com
# Even with --force, you must type the email to confirm deletion
```
