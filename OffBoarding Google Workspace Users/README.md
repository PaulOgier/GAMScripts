# User Offboarding Script (`offboard_user.py`)

A comprehensive, cross-platform Python script that automates the full Google Workspace user offboarding workflow using GAM7. Runs in **dry-run mode by default** — no changes are made until you pass `--doit`.

**Best for:** safely and consistently offboarding departing employees, covering security containment, data transfers, licence recovery, and audit logging in a single automated run.

## Key features

* Pre-flight snapshot — exports the user's full state to JSON before any changes (audit trail)
* Kill switch — moves user to Offboarding OU, wipes recovery details, resets password, and deprovisions app tokens
* Device management — detects and lists mobile and ChromeOS devices for manual review
* Group & delegate cleanup — removes group memberships and inbound/outbound delegates
* Licence removal — frees up seats before suspension
* Data transfers — Drive, aliases, and calendar ownership transferred to a successor
* Email forwarding & auto-reply — notifies senders and routes mail to successor
* Already-suspended users — detects suspension at start and offers to temporarily unsuspend for full offboarding, then re-suspends automatically at the end
* Suspension last — ensures all GAM operations complete before the account is locked
* Logs written to `logs/` subfolder by default (overridable with `--log-dir`)
* Shared Drives — reports every drive the leaver organises and refuses a `--scorched-earth`
  delete that would leave one with no organiser (override: `--allow-orphaned-shared-drives`)
* Backups that fall short fail the run — an incomplete Drive backup exits non-zero and holds
  licence removal, rather than reporting success
* Detailed phase-by-phase summary with timing and exit codes (`0`=success, `1`=errors, `2`=fatal)

## Usage

```bash
# Dry run (default — no changes made)
python3 offboard_user.py

# Execute offboarding
python3 offboard_user.py --doit

# Skip specific phases
python3 offboard_user.py --doit --no-devices --no-drive

# Non-interactive (scripted use)
python3 offboard_user.py --doit --force --user user@yourdomain.com

# Offboard an already-suspended user (unsuspend, offboard, re-suspend)
python3 offboard_user.py --doit --unsuspend --user user@yourdomain.com

# Custom log directory
python3 offboard_user.py --doit --log-dir /var/log/offboarding
```

## Command builder (no-code helper)

If you don't want to hand-craft the command line, open [`offboarding_command_builder.html`](offboarding_command_builder.html) in any browser. It is a single self-contained HTML page (no server, no install, works offline) that turns every flag into a form field, with inline help text for each one. Fill in the leaving user, successor, domain, and any phase toggles, and the page renders the exact `python3 offboard_user.py ...` command for you to copy. Useful for admins who only run an offboarding occasionally and don't want to re-read the flag list every time.

## Requirements

Python 3.6+ and an authorised GAM7. [GYB](https://github.com/GAM-team/got-your-back) is optional, for email migration only.

* [`offboarding_test_setup_guide.md`](offboarding_test_setup_guide.md) — full test environment setup
* [`installation_macos.md`](installation_macos.md) / [`installation_windows.md`](installation_windows.md) — the one-time GAM7 + GYB + rclone install
