# Offboarding Research & Reference Links

> Last verified: 31 July 2026 against `offboard_user.py` v5.3.0 and the
> linked upstream documentation. Third-party examples are historical
> references and may use obsolete GAM syntax.

## 1. GAM Onboarding Script (adamme)
[github.com/adamme/gam-scripts — onboard_user.sh](https://github.com/adamme/gam-scripts/blob/master/onboard_user.sh)

Bash script that automates employee onboarding using GAM. It creates the
account, assigns an organisational unit based on employment type, and adds
the user to office and optionally selected Google Groups. Useful as a
counterpart reference to the offboarding workflow.

---

## 2. GAM Offboarding Script — Alternative (adamme)
[github.com/adamme/gam-scripts — offboard_user_alternative.sh](https://github.com/adamme/gam-scripts/blob/master/offboard_user_alternative.sh)

Bash script that automates offboarding by transferring Calendar and Drive
data to the departing user's manager, delegating mailbox access, wiping
managed mobile accounts, revoking authentication access, and removing the
user from Google Groups.

---

## 3. GAM Beginner's Guide — Security & Compliance (AccessOwl)
[accessowl.com — GAM Beginners Guide](https://www.accessowl.com/blog/gam-beginners-guide-how-to-manage-google-workspace-at-scale#security-and-compliance)

A broad GAM administration guide with a dedicated security section covering the risks of powerful GAM access, recommending least-privilege controls and monitoring of GAM installations to prevent misuse.

---

## 4. G Suite Account Archival Using Vault & GAM (Starshade)
[starshade.ca — G Suite Account Archival](https://starshade.ca/wordpress/g-suite-account-archival-using-vault-gam/)

Walkthrough of a GAM-based archival workflow that exports user email via Google Vault, compresses the files, and uploads them to Google Drive — with an option to delete the user account afterwards.

---

## 5. User Offboarding Script (JasonSatti)
[github.com/JasonSatti/user_offboarding](https://github.com/JasonSatti/user_offboarding)

Bash script for Google Workspace user offboarding via GAM, supporting both voluntary and involuntary termination scenarios as separate workflow paths.

---

# Tool Command Reference by Offboarding Phase

Official documentation for the GAM7 / GYB / rclone commands that each phase of
`offboard_user.py` runs. Use these to look up the exact syntax and options
behind any phase.

## Phase 0 — Pre-flight Snapshot
Reads the user's full state (`info user`, `print groups`, `print aliases`, `show delegates`, `show forward`, `print licenses`, `show sendas`).
- GAM — [Users](https://github.com/GAM-team/GAM/wiki/Users)
- GAM — [Users - Group Membership](https://github.com/GAM-team/GAM/wiki/Users-Group-Membership)
- GAM — [Aliases](https://github.com/GAM-team/GAM/wiki/Aliases)
- GAM — [Users - Gmail - Delegates](https://github.com/GAM-team/GAM/wiki/Users-Gmail-Delegates)
- GAM — [Users - Gmail - Forwarding](https://github.com/GAM-team/GAM/wiki/Users-Gmail-Forwarding)
- GAM — [Licenses](https://github.com/GAM-team/GAM/wiki/Licenses)
- GAM — [Users - Gmail - Send As/Signature/Vacation](https://github.com/GAM-team/GAM/wiki/Users-Gmail-Send-As-Signature-Vacation)

## Phase 1 — Kill Switch (Containment)
Moves the user to the Offboarding OU, wipes recovery details, deprovisions
credentials, forces session sign-out, conditionally disables 2SV and POP/IMAP
access, randomises the password, and hides the user from the GAL (`update user
org`, `update user recoveryemail/recoveryphone`, `deprovision`, `signout`,
`turnoff2sv`, `update user password random changepassword on`, `update user gal
off`).
- GAM — [Users](https://github.com/GAM-team/GAM/wiki/Users)
- GAM — [Organizational Units](https://github.com/GAM-team/GAM/wiki/Organizational-Units)
- GAM — [Users - Deprovision](https://github.com/GAM-team/GAM/wiki/Users-Deprovision)

## Phase 2 — Device Management
Lists the user's mobile and ChromeOS devices for manual review (`print mobile`, `print cros`).
- GAM — [Mobile Devices](https://github.com/GAM-team/GAM/wiki/Mobile-Devices)
- GAM — [ChromeOS Devices](https://github.com/GAM-team/GAM/wiki/ChromeOS-Devices)

## Phase 3 — Group Removal
Removes the user from all Google Groups (`user <email> print groups`, `user <email> delete groups`).
- GAM — [Users - Group Membership](https://github.com/GAM-team/GAM/wiki/Users-Group-Membership)

## Phase 4 — Delegate Cleanup
Removes inbound delegates who can access the departing user's mailbox (`show
delegates`, `delete delegate`). Outbound delegations, where the departing user
can access another mailbox, are reported for manual cleanup.
- GAM — [Users - Gmail - Delegates](https://github.com/GAM-team/GAM/wiki/Users-Gmail-Delegates)

## Phase 5 — Licence Removal
Lists and attempts to remove each assigned licence (`print licenses`, `delete
license <SKU>`). Auto-assigned licences are reported for manual removal in the
Admin Console.
- GAM — [Licenses](https://github.com/GAM-team/GAM/wiki/Licenses)

## Phase 6 — Data Transfers & Backups
Drive transfer (`user <src> transfer drive`), alias reassignment, calendar access grant (`add calendaracls`), plus optional local backups via GYB (mailbox) and rclone (Drive).
- GAM — [Users - Drive - Transfer](https://github.com/GAM-team/GAM/wiki/Users-Drive-Transfer)
- GAM — [Users - Drive - Ownership](https://github.com/GAM-team/GAM/wiki/Users-Drive-Ownership)
- GAM — [Aliases](https://github.com/GAM-team/GAM/wiki/Aliases)
- GAM — [Users - Calendars - Access](https://github.com/GAM-team/GAM/wiki/Users-Calendars-Access)
- GYB — [Got Your Back Wiki (backup / restore)](https://github.com/GAM-team/got-your-back/wiki)
- rclone — [`rclone sync`](https://rclone.org/commands/rclone_sync/)
- rclone — [Google Drive backend](https://rclone.org/drive/)

## Phase 7 — Email Forwarding
Registers and activates forwarding to a successor (`add forwardingaddress`, `forward on … keep`).
- GAM — [Users - Gmail - Forwarding](https://github.com/GAM-team/GAM/wiki/Users-Gmail-Forwarding)

## Phase 8 — Auto-Reply
Sets a vacation auto-reply on the account (`vacation on`).
- GAM — [Users - Gmail - Send As/Signature/Vacation](https://github.com/GAM-team/GAM/wiki/Users-Gmail-Send-As-Signature-Vacation)

## Phase 9 — Suspension / Deletion
Suspends (`update user suspended on`) or, in scorched-earth mode, deletes the user (`delete user`).
- GAM — [Users](https://github.com/GAM-team/GAM/wiki/Users)

---

## Tool Home Pages
- GAM7 — [Wiki](https://github.com/GAM-team/GAM/wiki) · [Latest release](https://github.com/GAM-team/GAM/releases/latest)
- GYB — [Wiki](https://github.com/GAM-team/got-your-back/wiki) · [Latest release](https://github.com/GAM-team/got-your-back/releases/latest)
- rclone — [Documentation](https://rclone.org/docs/) · [Downloads](https://rclone.org/downloads/)
