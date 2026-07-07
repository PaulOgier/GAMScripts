#!/usr/bin/env python3
"""
Google Workspace User Offboarding Script
=============================================================================
Copyright (c) 2026 Paul Ogier, Outsource House (South Africa)
Website: https://osh.co.za | Email: support@osh.co.za
Training provided by Taming.Tech (https://taming.tech)

Google Workspace GAM7 Course on Udemy   https://taming.tech/GAMCourse
Google Workspace Admin Course on Udemy  https://www.taming.tech/GoogleWorkspaceAdmin
Google Workspace End-User Course on Udemy  https://www.taming.tech/TheCompleteWorkspaceCourse

Licence: Apache License 2.0 (full text in LICENSE at the repository root)

In plain English:
  - Free to use, including for commercial purposes.
  - Modify and redistribute freely; closed-source derivatives are allowed.
  - PLEASE KEEP THE ATTRIBUTION above intact. If you redistribute this
    file (modified or not), the copyright, contact, and course-link block
    at the top must stay in place. This is the one real obligation the
    licence puts on you (Apache 2.0 clause 4(c)) and it is what lets
    users find the original author and the training resources. Removing
    or replacing it is a licence violation.
  - No warranty: the disclaimer below is part of the licence terms.
  - "OSH", "Outsource House", and "Taming.Tech" are trademarks and are
    not licensed for use in your own product or marketing names
    (Apache 2.0 clause 6).

DISCLAIMER & LIMITATION OF LIABILITY:
This software has been tested in production environments; however, it is
provided "AS IS", without warranty of any kind, express or implied.

The authors (Paul Ogier, Outsource House) and training providers (Taming.Tech)
accept NO RESPONSIBILITY for any damages, data loss, or system issues that
may arise from its use. This exclusion applies regardless of whether the
issue results from defects in the script logic or from user error during
execution (e.g., misconfiguration).

YOU ASSUME ALL RISK ASSOCIATED WITH THE USE OF THIS SOFTWARE.
=============================================================================

Author:       Paul Ogier
Created:      2023-06-22
Updated:      2026-05-13
Version:      4.5.0
Status:       Production
Python:       3.8+
Dependencies: GAM ADV X (GAM7), GYB (optional), rclone (optional), PyYAML (optional)

Verified against GAM7 wiki as of May 2026.
Safe-by-default (DRY RUN), summary-driven, production-friendly.

Features:
- Cross-platform (Windows/macOS/Linux) using Python subprocess
- Robust CSV parsing for GAM outputs (no shell pipelines)
- Clear CLI flags for all operations
- Pre-flight snapshot of user state before changes (audit trail)
- Email backup and migration via GYB with Migrated/<user> labelling
- Drive transfer with organised folder creation
- Drive backup via rclone (optional)
- Shared Drives ownership handling
- Device wipe and ChromeOS deprovisioning
- Vacation responder, email forwarding, mailbox delegation cleanup
- Calendar transfer / ACL wipe and signature backup
- Already-suspended user detection with optional --unsuspend
- Coloured terminal output
- Startup version check against remote VERSION file (toggleable)

Prerequisites:
- GAM ADV X (GAM7) installed and in PATH (or full path set in CONFIGURATION)
- (Optional) GYB installed for email migration
- (Optional) rclone configured with a Google Drive remote for Drive backup

IMPORTANCE LEGEND:
  [CRITICAL]    - Must execute for security; failure needs immediate attention
  [IMPORTANT]   - Strongly recommended; skip only with good reason
  [RECOMMENDED] - Best practice; safe to skip in some scenarios
  [OPTIONAL]    - Nice to have; purely convenience

Execution order rationale:
  1.  Pre-flight snapshot  - Capture state BEFORE any changes (audit trail)
  2.  Kill switch          - Containment first (OU move, deprovision, password)
  3.  Device management    - Remove mobile/ChromeOS access
  4.  Group removal        - Revoke group-based permissions
  5.  Delegate cleanup     - Remove inbound AND outbound delegates
  6.  Data transfers       - Drive, email, aliases, calendar (licence must still be active)
  7.  Email forwarding     - Set up forwarding to successor
  8.  Auto-reply           - Inform senders (only useful pre-suspension)
  9.  Licence removal      - Free up seats (after transfers; before suspension)
  10. Suspension           - LAST, because many operations fail on suspended users

Default mode: DRY RUN (no changes made). Execution requires explicit --doit flag.

Example usage:
  python offboard_user.py                                          # Dry run
  python offboard_user.py --doit                                   # Execute
  python offboard_user.py --doit --backup-drive --backup-email     # Backup locally
  python offboard_user.py --doit --no-transfer --backup-drive      # Backup, no transfers
  python offboard_user.py --doit --force --user leaver@yourdomain.com \
      --all-transfer-to testoffboard.team@yourdomain.com                              # Non-interactive, one destination
  python offboard_user.py --doit --force --user leaver@yourdomain.com \
      --all-transfer-to testoffboard.team@yourdomain.com \
      --drive-to testoffboard.manager@yourdomain.com                                  # Split: Drive -> manager, rest -> team
  python offboard_user.py --doit --force --scorched-earth          # DELETE user
  python offboard_user.py --help

Transfer destination precedence (Drive, Email, Alias, Calendar, Forward):
  1. Phase-specific flag (--drive-to, --email-to, --alias-to,
     --calendar-to, --forward-to) -- highest priority
  2. --all-transfer-to (fallback default for any unspecified phase)
  3. Interactive prompt (only when --force is NOT set)

  Under --force, every non-skipped transfer phase MUST resolve to a
  destination via (1) or (2), or the run aborts before any change is
  made. Use --no-drive / --no-email / --no-alias / --no-calendar /
  --no-forward to opt phases out of the requirement.

Cross-platform notes:
- Windows: Colours auto-disabled on legacy CMD; works in Windows Terminal
- macOS/Linux: Full colour support in any modern terminal
- Path handling uses pathlib for OS-agnostic paths
- Subprocess calls use shell=False with list args for safety
- Pipe commands use platform-aware shell detection

Changelog
  2023-06-22 - v0.1.0 - Initial commit with basic user suspension logic.
  2023-07-14 - v0.2.0 - Added basic GAM command wrappers.
  2023-08-05 - v0.3.0 - Implemented dry-run safety toggle as default.
  2023-09-12 - v0.4.0 - Added initial GYB email migration support.
  2023-10-30 - v0.5.0 - Replaced os.system with subprocess for security.
  2023-11-18 - v0.6.0 - Added logging to file and console.
  2023-12-20 - v0.7.0 - Fixed paths for Windows cross-platform compatibility.
  2024-02-15 - v1.1.0 - Implemented coloured terminal output.
  2024-03-10 - v1.2.0 - Added mobile and ChromeOS device listing.
  2024-04-22 - v1.3.0 - Added Drive transfer with organised folder creation.
  2024-05-30 - v1.4.0 - Added interactive confirmation prompts for kill switch.
  2024-07-20 - v2.0.0 - Added calendar and alias transfer features.
  2024-08-25 - v2.1.0 - Added progress timers for long-running operations.
  2024-09-30 - v2.2.0 - Added pre-flight validation for destination users.
  2024-10-28 - v3.0.0 - Updated all commands for GAM7 (GAM ADV X) compatibility.
  2024-11-15 - v3.1.0 - Refactored CSV output parsing for GAM7 format changes.
  2025-02-20 - v3.3.0 - Added vacation responder configuration.
  2025-06-10 - v3.5.0 - Added email signature (sendas) capture as part of the pre-flight snapshot.
  2025-11-05 - v3.9.0 - Updated code comments and cleaned up docstrings.
  2026-01-15 - v4.0.0 - Linked code comments to GAM7/GYB KB; reordered deployment for better logic.
  2026-03-08 - v4.1.0 - Added pre-flight snapshot, email forwarding, mailbox delegation, calendar transfer/ACL wipe, --force, --log-dir, exit codes, signal handling, and resilient try/except per phase.
  2026-04-22 - v4.2.0 - Added rclone Drive backup (--backup-drive), already-suspended detection (--unsuspend), GYB backup-only mode (--backup-email).
  2026-05-06 - v4.3.0 - GYB restore applies Migrated/<source-user> label; mailbox/Drive backups moved to dedicated subdirs; fixed calendar ACL syntax (calendaracl -> calendaracls, user <email> -> user:<email>).
  2026-05-07 - v4.4.0 - Added startup version check against remote VERSION file (CHECK_FOR_UPDATES toggle, fail-silent); restored author/contact header with Outsource House copyright and three Udemy course links; aligned in-script licence reference with the repo LICENSE (Apache 2.0) and added a plain-English summary emphasising attribution retention.
  2026-05-13 - v4.5.0 - BREAKING: renamed --transfer-to to --all-transfer-to. Added per-phase destination flags (--drive-to, --email-to, --alias-to, --calendar-to, --forward-to) that override the global default; precedence is phase-specific > --all-transfer-to > interactive prompt. Added upfront destination resolution and validation before any phase runs: under --force, any non-skipped phase without a resolvable destination aborts the run with a clear error instead of half-offboarding.
  2026-05-14 - v4.6.0 - Added end-of-run MANUAL ACTION block surfacing admin-console instructions for durable mail capture (alias / recipient address map / group) since GAM cannot configure recipient address map and Gmail-level forwarding stops on suspension/deletion; new --forward-alias-to flag explicitly nominates the successor printed in the block (falls back to --forward-to then --all-transfer-to), no automated change is made. Guide gains a "Mail capture after suspension" section and the order-of-operations list flags forwarding's suspension limitation.
  2026-07-07 - v4.7.0 - Email migration hardened against AV-quarantined messages: a malicious email in the source mailbox can be quarantined on local disk by endpoint antivirus after GYB writes it during backup, and GYB's restore crashes on the unreadable file. A pre-restore scan now probes every backed-up .eml and moves unreadable ones to a sibling <backup>_quarantined/ folder so GYB's own missing-file handling skips them; skipped messages are listed (Gmail message ID + date) in <backup>_skipped-messages.csv next to the backup and flagged in the run summary. Also fixed the restore result being ignored: a failed restore now reports an error with the retained backup path instead of logging "Email migrated".

Planned Features (not yet implemented)
  - Batch processing via CSV file: accept a list of users (e.g. --csv users.csv)
    and iterate the full offboarding flow per row, with per-user logs and a
    consolidated run summary.
  - --manager shortcut flag: auto-resolve the departing user's manager (from
    the directory) as the default --all-transfer-to destination, so common
    cases do not need an explicit address.
  - --wipe-devices flag: opt-in automatic mobile account_wipe and ChromeOS
    deprovision_retiring_device actions, instead of only listing devices and
    printing manual guidance.
  - YAML configuration file support: load defaults (GAM/GYB/rclone paths,
    OFFBOARDING_OU, BACKUP_DIR, default flags) from a config.yaml so the
    CONFIGURATION constants do not need to be edited in-script. Would
    activate the currently-unused PyYAML optional dependency.
  - JSON output mode (--json): emit a machine-readable run summary (per-phase
    status, counts, errors, paths to artefacts) for automation pipelines, in
    addition to the existing human-readable summary.
  - Dedicated signature backup: write the user's sendas/signature HTML to a
    standalone file in the backup directory (today it is only captured as a
    field inside the pre-flight JSON snapshot).
"""

import argparse
import csv
import io
import subprocess
import sys
import os
import re
import json
import logging
import signal
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import shutil


###############################################################################
# CONFIGURATION SECTION [CRITICAL]
# Customise these settings for your environment before first use.
###############################################################################

# [IMPORTANT] Current local script version. Bumped on each release.
# Compared against the remote VERSION file to detect updates.
SCRIPT_VERSION = "4.7.0"

# [OPTIONAL] Check for a newer script version on startup.
# When True (default), the script makes a single 3-second HTTP request to
# fetch the remote VERSION file and warns if a newer release exists. Set to
# False to disable (e.g. for offline/air-gapped environments or to skip the
# tiny startup delay). The check is fail-silent: any network or parse error
# is ignored so it can never block an offboarding run.
CHECK_FOR_UPDATES = True

# [OPTIONAL] URL of the remote VERSION file used for update checks.
# Points to the raw VERSION file on the main branch of the public repo.
UPDATE_CHECK_URL = (
    "https://raw.githubusercontent.com/PaulOgier/GAMScripts/main/"
    "OffBoarding%20Google%20Workspace%20Users/VERSION"
)

# [CRITICAL] The OU to move the user into during offboarding.
# This OU MUST have NO 2SV enforcement policy, otherwise the script cannot
# disable 2FA on the departing user's account. Create a dedicated OU in your
# Google Workspace admin console (e.g. /Offboarding or /Suspended Users)
# and ensure no 2SV enforcement policies are applied to it.
OFFBOARDING_OU = "/Offboarding"

# [IMPORTANT] The GAM command name or full path.
# On most systems "gam" works if GAM7 is in your PATH.
# On Windows you may need "gam.exe" or the full path, e.g.:
#   r"C:\GAM7\gam.exe"
# On macOS/Linux, the installer typically places it in ~/bin/gam7/gam
GAM_COMMAND = "gam"

# [OPTIONAL] GYB command for email migration.
# Only needed if you want to back up and restore email to another account.
# If GYB is not installed, set this to None or leave as "gyb".
GYB_COMMAND = "gyb"

# [IMPORTANT] Directory for backups, snapshots, and email migration data.
# Uses OS-agnostic path handling via pathlib.
BACKUP_DIRECTORY = Path("./offboarding_backups")

# [OPTIONAL] Auto-reply message set on the departing user's account.
# Customise this with your organisation's standard wording.
AUTO_REPLY_MESSAGE = (
    "This person is no longer with the organisation. "
    "Please contact reception for further assistance."
)

# [OPTIONAL] rclone command name or full path.
# Only needed if you want to back up Drive files locally (--backup-drive).
# rclone must be configured with a Google Drive remote that uses a service
# account for domain-wide delegation (can reuse GAM7's oauth2service.json).
RCLONE_COMMAND = "rclone"

# [OPTIONAL] rclone remote name from 'rclone config'.
# Must support --drive-impersonate for service account access.
RCLONE_REMOTE = "workspace"

# [OPTIONAL] Export formats for Google Docs/Sheets/Slides.
RCLONE_EXPORT_FORMATS = "docx,xlsx,pptx,pdf"


###############################################################################
# COLOUR CODES FOR TERMINAL OUTPUT [OPTIONAL]
# Makes output more readable. Auto-disabled on legacy Windows CMD.
###############################################################################

class Colours:
    """ANSI colour codes for terminal output.

    Uses bright (high-intensity, 90-97) variants in bold for better
    contrast on dark terminal backgrounds. The standard codes (30-37)
    render as dark navy / muddy green on most dark themes and are hard
    to read; the bright variants are the standard accessibility fix.
    """
    RED = '\033[1;91m'      # bright red, bold
    GREEN = '\033[1;92m'    # bright green, bold
    YELLOW = '\033[1;93m'   # bright yellow, bold
    BLUE = '\033[1;94m'     # bright blue, bold — readable on dark bg
    MAGENTA = '\033[1;95m'  # bright magenta, bold
    CYAN = '\033[1;96m'     # bright cyan, bold — readable [INFO] colour
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def strip_colours():
        """Disable colours for environments that do not support ANSI codes."""
        Colours.RED = ''
        Colours.GREEN = ''
        Colours.YELLOW = ''
        Colours.BLUE = ''
        Colours.MAGENTA = ''
        Colours.CYAN = ''
        Colours.RESET = ''
        Colours.BOLD = ''


# [IMPORTANT] Auto-detect terminal colour support.
# Windows 10+ cmd.exe supports ANSI once virtual-terminal processing is
# enabled via SetConsoleMode; Windows Terminal and modern PowerShell have
# it on by default. On macOS/Linux, colours work whenever stdout is a TTY.
def _enable_windows_ansi() -> bool:
    """Enable ANSI escape processing on the current Windows console.

    Returns True if VT processing is active (or was already), False on
    older Windows where the call fails. Safe to call on non-Windows.
    """
    if os.name != 'nt':
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11; ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


if os.name == 'nt':
    if not (
        os.environ.get('WT_SESSION')
        or os.environ.get('TERM_PROGRAM')
        or _enable_windows_ansi()
    ):
        Colours.strip_colours()
elif not sys.stdout.isatty():
    Colours.strip_colours()


###############################################################################
# GLOBAL STATE
###############################################################################

# Track timing per phase
phase_timings: List[Tuple[str, float]] = []

# Summary tracking
summary_actions: List[str] = []
summary_skipped: List[str] = []
summary_errors: List[str] = []
summary_warnings: List[str] = []

# Exit code (escalates: 0 -> 1 -> 2)
exit_code = 0

# Graceful shutdown flag
shutdown_requested = False


###############################################################################
# SIGNAL HANDLING [RECOMMENDED]
# Allows Ctrl+C to exit gracefully with a summary instead of a traceback.
###############################################################################

def signal_handler(_signum, _frame):
    global shutdown_requested
    if shutdown_requested:
        # Second Ctrl+C, force exit
        print(f"\n{Colours.RED}Forced exit.{Colours.RESET}")
        sys.exit(2)
    shutdown_requested = True
    print(f"\n{Colours.YELLOW}[WARN] Ctrl+C received. Finishing current operation, then exiting...{Colours.RESET}")
    print(f"{Colours.YELLOW}[WARN] Press Ctrl+C again to force quit immediately.{Colours.RESET}")


signal.signal(signal.SIGINT, signal_handler)
# SIGTERM is not available on Windows
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, signal_handler)


###############################################################################
# LOGGING SETUP [IMPORTANT]
# Maintains an audit trail of all operations for compliance and debugging.
# Logs go to both console and a timestamped file.
###############################################################################

LOG_FILENAME = ""  # Set in main() after args are parsed


def setup_logging(log_dir: Optional[Path] = None, user_email: str = "", timestamp: str = ""):
    """Initialise logging with both file and console handlers."""
    global LOG_FILENAME

    if not timestamp:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    prefix = f"{user_email}_{timestamp}" if user_email else f"offboarding_{timestamp}"
    filename = f"{prefix}.log"

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        LOG_FILENAME = str(log_dir / filename)
    else:
        LOG_FILENAME = filename

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILENAME, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


logger: Optional[logging.Logger] = None


###############################################################################
# SUMMARY HELPERS
###############################################################################

def summary_action(msg: str):
    summary_actions.append(msg)


def summary_skip(msg: str):
    summary_skipped.append(msg)


def summary_error(msg: str):
    global exit_code
    summary_errors.append(msg)
    if exit_code < 1:
        exit_code = 1


def summary_warning(msg: str):
    summary_warnings.append(msg)


###############################################################################
# DISPLAY HELPERS [OPTIONAL]
###############################################################################

def print_header(title: str):
    width = 60
    logger.info("")
    logger.info(f"{Colours.BLUE}{'=' * width}")
    logger.info(f"  {title}")
    logger.info(f"{'=' * width}{Colours.RESET}")


def print_success(msg: str):
    logger.info(f"{Colours.GREEN}[OK] {msg}{Colours.RESET}")


def print_warning(msg: str):
    logger.warning(f"{Colours.YELLOW}[WARN] {msg}{Colours.RESET}")


def print_error(msg: str):
    logger.error(f"{Colours.RED}[ERROR] {msg}{Colours.RESET}")


def print_info(msg: str):
    logger.info(f"{Colours.CYAN}[INFO] {msg}{Colours.RESET}")


###############################################################################
# UPDATE CHECK [OPTIONAL]
# Fetches the remote VERSION file and warns if the local script is out of
# date. Disabled by setting CHECK_FOR_UPDATES = False in the CONFIGURATION
# section above. Fail-silent on any network or parse error.
###############################################################################

def _parse_version(value: str) -> Tuple[int, ...]:
    """Parse 'X.Y' or 'X.Y.Z' into a tuple of ints for comparison."""
    parts = []
    for piece in value.strip().split("."):
        digits = "".join(c for c in piece if c.isdigit())
        if not digits:
            raise ValueError(f"Non-numeric version segment: {piece!r}")
        parts.append(int(digits))
    if not parts:
        raise ValueError("Empty version string")
    return tuple(parts)


def check_for_updates():
    """Compare SCRIPT_VERSION against the remote VERSION file.

    Prints a warning if a newer version is available, otherwise stays quiet.
    Any error (no network, timeout, malformed response) is swallowed so the
    check can never block an offboarding run.
    """
    if not CHECK_FOR_UPDATES:
        print_info("Update check disabled (CHECK_FOR_UPDATES = False)")
        return

    try:
        # Imported lazily so disabling the check has zero import cost.
        from urllib.request import Request, urlopen
        req = Request(UPDATE_CHECK_URL, headers={"User-Agent": "offboard_user.py"})
        with urlopen(req, timeout=3) as resp:
            remote_raw = resp.read().decode("utf-8", errors="replace")
        remote_version = remote_raw.strip().splitlines()[0].strip()

        local_tuple = _parse_version(SCRIPT_VERSION)
        remote_tuple = _parse_version(remote_version)

        if remote_tuple > local_tuple:
            print_warning(
                f"A newer version is available: v{remote_version} "
                f"(you are running v{SCRIPT_VERSION})"
            )
            print_warning(
                "What changed + download: "
                "https://github.com/PaulOgier/GAMScripts/releases   "
                "(git pull if you cloned; set CHECK_FOR_UPDATES = False to "
                "silence this check)"
            )
        elif remote_tuple < local_tuple:
            print_info(
                f"Running v{SCRIPT_VERSION} (remote VERSION reports v{remote_version})"
            )
        else:
            print_info(f"Script is up to date (v{SCRIPT_VERSION})")
    except Exception as exc:
        # Fail silent: never let the update check block a run.
        print_info(f"Update check skipped ({type(exc).__name__})")


###############################################################################
# PHASE TIMING [RECOMMENDED]
# Records how long each phase takes for the summary report.
###############################################################################

class PhaseTimer:
    """Context manager to time a phase and record it."""
    def __init__(self, phase_name: str):
        self.phase_name = phase_name
        self.start = 0.0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        elapsed = time.time() - self.start
        phase_timings.append((self.phase_name, elapsed))


###############################################################################
# COMMAND EXECUTION [CRITICAL]
# All GAM/GYB commands flow through these functions for:
#   - Dry run support (shows what would happen without executing)
#   - Logging of every command and its output
#   - Error capture and reporting
#   - Graceful shutdown checking
###############################################################################

def run_gam(args: List[str], dry_run: bool = True,
            capture_output: bool = False,
            timeout: int = 300,
            non_fatal_patterns: Optional[List[str]] = None,
            stdout_only: bool = False,
            suppress_summary_error: bool = False) -> Tuple[bool, str]:
    """
    Execute a GAM command with full logging and dry-run support.

    Args:
        args: List of command arguments (GAM_COMMAND is prepended automatically)
        dry_run: If True, command is logged but not executed
        capture_output: If True, return stdout instead of printing it
        timeout: Seconds before the command is killed (default 300)
        non_fatal_patterns: Additional output substrings that should NOT be
            treated as errors (e.g. ["auto-assigned"]). Matched case-insensitively.
        suppress_summary_error: If True, a failed call does NOT record a
            summary_error entry. Use when the caller has a fallback path
            (e.g. probe-as-user, then fall back to probe-as-group) so the
            final summary doesn't list the probe failure as a real error.

    Returns:
        Tuple of (success: bool, output: str). Returns (True, output) when a
        non-fatal pattern matches so the caller can inspect output and decide.
    """
    if shutdown_requested:
        return False, "Shutdown requested"

    full_cmd = [GAM_COMMAND] + args
    cmd_str = " ".join(full_cmd)

    if dry_run:
        print_info(f"DRY RUN: {cmd_str}")
        return True, ""

    logger.info(f"Executing: {cmd_str}")

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = result.stdout.strip()
        if not stdout_only and result.stderr.strip():
            output += "\n" + result.stderr.strip()

        if result.returncode == 0:
            if capture_output:
                return True, output
            if output:
                logger.info(output)
            return True, output
        else:
            # Check for known non-fatal "errors"
            lower = output.lower()
            base_non_fatal = ["0 entities", "no tokens"]
            all_non_fatal = base_non_fatal + (non_fatal_patterns or [])
            if any(p.lower() in lower for p in all_non_fatal):
                return True, output
            if suppress_summary_error:
                # Caller flagged this call as a probe with a fallback path
                # (e.g. validate_destination's user-then-group probe), so
                # downgrade the red [ERROR] lines to info to avoid alarming
                # the user about an expected failure. The output is still
                # logged so a real problem remains debuggable.
                logger.info(f"Probe failed (exit {result.returncode}): {cmd_str}")
                if output:
                    logger.info(output)
            else:
                print_error(f"Command failed (exit {result.returncode}): {cmd_str}")
                if output:
                    print_error(output)
                summary_error(f"Failed: {cmd_str}")
            return False, output

    except subprocess.TimeoutExpired:
        print_error(f"Command timed out after {timeout}s: {cmd_str}")
        if not suppress_summary_error:
            summary_error(f"Timeout: {cmd_str}")
        return False, "Timeout"
    except FileNotFoundError:
        print_error(
            f"GAM command not found: {GAM_COMMAND}. "
            f"Ensure GAM7 is installed and in your PATH."
        )
        summary_error("GAM7 not found in PATH")
        return False, "Not found"
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        summary_error(f"Exception: {e}")
        return False, str(e)


def run_shell_pipe(cmd_str: str, dry_run: bool = True,
                   timeout: int = 300) -> Tuple[bool, str]:
    """
    Execute a shell pipe command (e.g. gam print ... | gam csv ...).

    This is needed for GAM's CSV piping pattern. Uses platform-aware
    shell detection to avoid issues on Windows vs Unix.

    EDGE CASE: On Windows, subprocess with shell=True uses cmd.exe by
    default, which handles pipes correctly. On Unix, it uses /bin/sh.
    """
    if shutdown_requested:
        return False, "Shutdown requested"

    if dry_run:
        print_info(f"DRY RUN: {cmd_str}")
        return True, ""

    logger.info(f"Executing (shell pipe): {cmd_str}")

    try:
        result = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = (result.stdout + "\n" + result.stderr).strip()

        if result.returncode == 0:
            return True, output
        else:
            if "0 entities" in output.lower():
                return True, output
            print_error(f"Pipe command failed (exit {result.returncode})")
            if output:
                print_error(output)
            return False, output

    except subprocess.TimeoutExpired:
        print_error(f"Pipe command timed out after {timeout}s")
        return False, "Timeout"
    except Exception as e:
        print_error(f"Pipe command exception: {e}")
        return False, str(e)


def run_gyb(args: List[str], dry_run: bool = True) -> Tuple[bool, str]:
    """
    Execute a GYB command, streaming output to the log including tqdm
    progress bars.

    GYB uses tqdm for progress, which writes \\r (carriage return) to
    overwrite the same line. A naive line iterator only yields on \\n,
    so progress updates would stay invisible until GYB prints a real
    newline at phase completion. We read in small chunks and treat both
    \\r and \\n as line separators, then throttle identical-prefix
    progress lines to at most one log entry per second so the log file
    isn't flooded with thousands of bar-redraw frames.

    No overall timeout: a real mailbox backup/restore can legitimately
    run for hours. stdin is closed so GYB never silently hangs waiting
    for interactive input.
    """
    if shutdown_requested:
        return False, "Shutdown requested"

    full_cmd = [GYB_COMMAND] + args + ["--service-account"]
    cmd_str = " ".join(full_cmd)

    if dry_run:
        print_info(f"DRY RUN: {cmd_str}")
        return True, ""

    logger.info(f"Executing: {cmd_str}")

    try:
        # PYTHONUNBUFFERED=1 nudges GYB's child Python to flush stdout
        # promptly so progress updates aren't held in a 4KB block buffer.
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )

        collected: List[str] = []
        buffer = ""
        # Throttle repeated progress lines: only log a redraw of the
        # same bar if >=1s has passed since the last identical-prefix
        # line. A bar's "prefix" is the text up to the percentage.
        last_progress_log = 0.0
        last_progress_prefix = ""

        def emit(line: str):
            nonlocal last_progress_log, last_progress_prefix
            line = line.rstrip()
            if not line:
                return
            # Is this a tqdm-style progress line? They typically contain
            # "%|" or a fraction like " 123/4567 ".
            is_progress = "%|" in line or "it/s" in line
            if is_progress:
                # Prefix = everything before the first digit-percent, used
                # to detect "same bar being redrawn".
                prefix = line.split("%", 1)[0][:40]
                now = time.time()
                if prefix == last_progress_prefix and now - last_progress_log < 1.0:
                    return
                last_progress_prefix = prefix
                last_progress_log = now
            logger.info(line)
            collected.append(line)

        assert proc.stdout is not None
        while True:
            if shutdown_requested:
                proc.terminate()
                break
            chunk = proc.stdout.read(256)
            if not chunk:
                break
            buffer += chunk
            # Split on either CR or LF so tqdm redraws surface as lines.
            while True:
                idx = -1
                for sep in ("\r", "\n"):
                    i = buffer.find(sep)
                    if i != -1 and (idx == -1 or i < idx):
                        idx = i
                if idx == -1:
                    break
                emit(buffer[:idx])
                buffer = buffer[idx + 1:]

        if buffer:
            emit(buffer)

        proc.wait()
        output = "\n".join(collected)

        if proc.returncode == 0:
            return True, output
        else:
            print_error(f"GYB command failed (exit {proc.returncode}): {cmd_str}")
            summary_error(f"GYB failed: {cmd_str}")
            return False, output

    except FileNotFoundError:
        print_error(f"GYB command not found: {GYB_COMMAND}")
        summary_error("GYB not found in PATH")
        return False, "Not found"
    except Exception as e:
        print_error(f"GYB exception: {e}")
        summary_error(f"GYB exception: {e}")
        return False, str(e)


###############################################################################
# DEPENDENCY CHECKS [IMPORTANT]
###############################################################################

def check_dependencies(need_gyb: bool = False, need_rclone: bool = False,
                       user_email: str = "") -> bool:
    """
    [IMPORTANT] Check that required tools are available and authorised.

    EDGE CASE: GAM can be installed but not yet authorised (no oauth2.txt).
    We detect this by running 'gam info domain' and checking for auth errors.

    When need_gyb=True and user_email is provided, validates that the GYB
    service account can impersonate the target user via --action quota.
    """
    print_header("DEPENDENCY CHECK")

    # Check GAM7 exists in PATH
    gam_path = shutil.which(GAM_COMMAND)
    if gam_path:
        print_success(f"GAM7 found: {gam_path}")
    else:
        print_error(
            f"GAM7 not found in PATH as '{GAM_COMMAND}'. "
            f"Install from https://github.com/GAM-team/GAM"
        )
        return False

    # Check GAM7 version and auth
    success, output = run_gam(["version"], dry_run=False, capture_output=True)
    if success and output:
        version_match = re.search(r'GAM\s+(\d+\.\d+\.\d+)', output)
        if version_match:
            print_success(f"GAM7 version: {version_match.group(1)}")
        else:
            print_info(f"GAM7 version output: {output.splitlines()[0]}")

    # EDGE CASE: Check GAM7 is actually authorised
    success, output = run_gam(
        ["info", "domain"],
        dry_run=False,
        capture_output=True,
        timeout=30
    )
    if not success:
        if "oauth" in output.lower() or "unauthorized" in output.lower() or "credentials" in output.lower():
            print_error(
                "GAM7 is installed but does not appear to be authorised. "
                "Run 'gam oauth create' and 'gam user admin@domain.com check serviceaccount' first."
            )
            return False
        # Other errors might be transient, warn but continue
        print_warning(f"Could not verify domain info: {output.splitlines()[0] if output else 'no output'}")

    # Check Python version (some features need 3.7+)
    if sys.version_info < (3, 7):
        print_error(f"Python 3.7+ required. Current: {sys.version}")
        return False
    print_success(f"Python: {sys.version.split()[0]}")

    # Verify the offboarding OU exists. Without this, the kill-switch phase
    # silently degrades: GAM rejects `update user ... org /Offboarding`
    # with "Invalid Organizational Unit", the user is never moved into
    # containment, and subsequent OU-dependent steps (e.g. relaxed 2SV
    # enforcement in the offboarding OU) also fail. Catching it here lets
    # the admin create the OU or update OFFBOARDING_OU before any change.
    ou_ok, ou_output = run_gam(
        ["info", "org", OFFBOARDING_OU],
        dry_run=False,
        capture_output=True,
        timeout=30,
        suppress_summary_error=True,
    )
    if ou_ok:
        print_success(f"Offboarding OU exists: {OFFBOARDING_OU}")
    else:
        print_error(
            f"Offboarding OU '{OFFBOARDING_OU}' does not exist or is not "
            f"accessible. GAM output: "
            f"{ou_output.splitlines()[0] if ou_output else 'no output'}"
        )
        # Show concrete remediation steps so the admin doesn't have to
        # leave the terminal to fix this. Green = actionable next steps.
        ou_name = OFFBOARDING_OU.lstrip("/")
        print_success("To create the offboarding OU, choose one of:")
        print_success(f"  [GAM]  gam create org \"{ou_name}\" "
                      f"description \"Offboarded users\" parent /")
        print_success("  [Admin Console]  https://admin.google.com/ac/orgunits  "
                      "-> Create organizational unit -> "
                      f"Name: \"{ou_name}\", Parent: /")
        print_success(
            f"Alternatively, edit OFFBOARDING_OU near the top of "
            f"offboard_user.py to point at an existing OU."
        )
        return False

    # Check GYB if needed
    if need_gyb:
        gyb_path = shutil.which(GYB_COMMAND)
        if not gyb_path:
            print_warning(f"GYB not found. Email migration will not be available.")
            return False
        print_success(f"GYB found: {gyb_path}")

        # Validate GYB service account can impersonate the target user
        if user_email:
            print_info(f"Verifying GYB service account access for {user_email}...")
            try:
                result = subprocess.run(
                    [GYB_COMMAND, "--email", user_email, "--action", "quota",
                     "--service-account"],
                    capture_output=True, text=True,
                    stdin=subprocess.DEVNULL, timeout=30
                )
                output = (result.stdout + result.stderr).strip()
                if result.returncode == 0:
                    print_success("GYB service account authorised")
                else:
                    print_error(
                        f"GYB service account cannot access {user_email}. "
                        f"Ensure domain-wide delegation is configured for the "
                        f"GYB service account with the Gmail API scope. "
                        f"Output: {output.splitlines()[0] if output else 'no output'}"
                    )
                    return False
            except subprocess.TimeoutExpired:
                print_error("GYB service account check timed out (30s). "
                            "Check service account configuration.")
                return False
            except Exception as e:
                print_error(f"GYB service account check failed: {e}")
                return False


    # Check rclone if needed
    if need_rclone:
        rclone_path = shutil.which(RCLONE_COMMAND)
        if rclone_path:
            print_success(f"rclone found: {rclone_path}")
            try:
                result = subprocess.run(
                    [RCLONE_COMMAND, "listremotes"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    remotes = result.stdout.strip().split('\n')
                    if f"{RCLONE_REMOTE}:" in remotes:
                        print_success(f"rclone remote \'{RCLONE_REMOTE}\' configured")
                    else:
                        print_error(
                            f"rclone remote \'{RCLONE_REMOTE}\' not found. "
                            f"Available: {', '.join(remotes)}. "
                            f"Run \'rclone config\' or update RCLONE_REMOTE."
                        )
                        return False
            except Exception as e:
                print_warning(f"Could not verify rclone remotes: {e}")
        else:
            print_error(
                f"rclone not found in PATH. "
                f"Install from https://rclone.org/ or remove --backup-drive."
            )
            return False

    # Ensure backup directory exists
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    print_success(f"Backup directory: {BACKUP_DIRECTORY.resolve()}")

    return True


###############################################################################
# DESTINATION VALIDATION [IMPORTANT]
def resolve_dest(specific: Optional[str], all_default: Optional[str]) -> Optional[str]:
    """Return the per-phase destination if set, else the global default, else None.

    Implements the precedence rule for transfer destinations:
    phase-specific flag (--drive-to, etc.) > --all-transfer-to > unset.
    """
    return specific or all_default or None


def preflight_destinations(args) -> Dict[str, Optional[str]]:
    """Resolve destinations for every transfer phase and validate them up front.

    Under --force, any non-skipped phase without a destination is a fatal error
    (we cannot fall back to an interactive prompt in non-interactive mode and
    silent skipping would leave the offboarding half-done). Every unique
    resolved destination is checked against the directory via
    validate_destination() so we fail before any destructive action.

    Returns a dict mapping phase name to the resolved email (or None if the
    phase has no destination and will be resolved interactively later).
    """
    phases = {
        "drive":    (args.no_drive,    args.drive_to),
        "email":    (args.no_email,    args.email_to),
        "alias":    (args.no_alias,    args.alias_to),
        "calendar": (args.no_calendar, args.calendar_to),
        "forward":  (args.no_forward,  args.forward_to),
    }

    resolved: Dict[str, Optional[str]] = {}
    missing: List[str] = []
    for name, (skipped, specific) in phases.items():
        if skipped:
            resolved[name] = None
            continue
        dest = resolve_dest(specific, args.all_transfer_to)
        resolved[name] = dest
        if args.force and not dest:
            missing.append(name)

    if missing:
        print_error("--force requires a destination for every non-skipped phase.")
        print_error(f"Missing destinations for: {', '.join(missing)}")
        print_error(
            "Fix by adding --all-transfer-to <email>, a specific "
            "--<phase>-to <email>, or skipping with --no-<phase>."
        )
        sys.exit(2)

    # Only the forward phase may target a group address; all other phases
    # require a real user account (Drive/Email/Alias/Calendar transfers
    # cannot be received by a group).
    if resolved:
        print_info("Validating transfer destinations...")
        seen: Dict[str, bool] = {}
        for name, dest in resolved.items():
            if not dest:
                continue
            allow_group = (name == "forward")
            cache_key = f"{dest}|{allow_group}"
            if cache_key in seen:
                continue
            if not validate_destination(dest, allow_group=allow_group):
                print_error(f"Destination validation failed: {dest}")
                sys.exit(2)
            seen[cache_key] = True

    return resolved


# Verifies that a destination user exists before attempting transfers.
###############################################################################

def validate_destination(email: str, allow_group: bool = False) -> bool:
    """
    Check that a destination exists and is active.

    When allow_group is True, a Google Group address is also accepted
    (used for email-forwarding destinations, which Gmail allows to point
    at a same-domain group).
    """
    # Probe as user first. Suppress summary_error so a not-a-user response
    # doesn't surface as a real error when the group fallback succeeds, or
    # when the caller is just probing.
    success, output = run_gam(
        ["info", "user", email, "quick"],
        dry_run=False,
        capture_output=True,
        timeout=30,
        suppress_summary_error=True,
    )
    if success:
        for line in output.splitlines():
            if "suspended" in line.lower() and "true" in line.lower():
                print_warning(f"Destination user {email} is SUSPENDED. Transfers may fail.")
                return False
        return True

    if allow_group:
        ok_group, _ = run_gam(
            ["info", "group", email],
            dry_run=False,
            capture_output=True,
            timeout=30,
            suppress_summary_error=True,
        )
        if ok_group:
            print_info(f"Destination {email} is a group — accepted for forwarding.")
            return True

    # No fallback worked — this is now a genuine error worth reporting.
    print_error(f"Destination user not found: {email}")
    summary_error(f"Destination not found: {email}")
    return False


###############################################################################
# USER VERIFICATION [CRITICAL]
###############################################################################

def verify_user(email: str) -> Optional[Dict[str, str]]:
    """
    [CRITICAL] Verify the user exists and display their current status.
    Returns a dict with user info on success, None on failure.
    """
    print_header("USER VERIFICATION")

    success, output = run_gam(
        ["info", "user", email, "quick"],
        dry_run=False,
        capture_output=True
    )

    if not success:
        print_error(f"User not found or not accessible: {email}")
        return None

    # Parse key fields from output
    user_info = {}
    for line in output.splitlines():
        line = line.strip()
        if ':' in line:
            key, _, value = line.partition(':')
            user_info[key.strip().lower()] = value.strip()

    # Display user summary
    print_info(f"User: {email}")
    print_info(f"Full Name: {user_info.get('full name', '?')}")
    print_info(f"Suspended: {user_info.get('account suspended', '?')}")
    print_info(f"OU: {user_info.get('google org unit path', '?')}")
    print_info(f"Last Login: {user_info.get('last login time', '?')}")
    print_info(f"2SV Enrolled: {user_info.get('2-step enrolled', '?')}")
    print_info(f"2SV Enforced: {user_info.get('2-step enforced', '?')}")

    # EDGE CASE: Already suspended user
    is_suspended = user_info.get('account suspended', '').lower() == 'true'
    if is_suspended:
        print_warning(
            "User is ALREADY SUSPENDED. The following operations will fail "
            "on suspended users: deprovision (backup codes), turnoff2sv, "
            "delegate setup, email forwarding, auto-reply. "
            "Consider unsuspending first, running offboarding, then re-suspending."
        )
        summary_warning("User was already suspended at start of offboarding")

    # EDGE CASE: User is an admin
    is_admin = user_info.get('is a super admin', '').lower() == 'true' or \
               user_info.get('is delegated admin', '').lower() == 'true'
    if is_admin:
        print_error(
            "User has admin privileges. Consider revoking admin role "
            "BEFORE offboarding. This script does not revoke admin roles "
            "as a safety measure."
        )
        summary_warning("User had admin privileges at start of offboarding")

    user_info['_is_suspended'] = str(is_suspended)
    user_info['_is_admin'] = str(is_admin)

    return user_info


###############################################################################
# INTERACTIVE PROMPTS [RECOMMENDED]
###############################################################################

def prompt_yes_no(question: str, default: bool = False, force: bool = False) -> bool:
    """Ask a yes/no question. In --force mode, returns True always."""
    if force:
        print_info(f"{question} -> auto-yes (--force)")
        return True
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        try:
            answer = input(f"{Colours.YELLOW}{question}{suffix}{Colours.RESET}").strip().lower()
        except EOFError:
            # EDGE CASE: stdin is not a terminal (piped input)
            return default
        if answer == '':
            return default
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print("Please enter 'y' or 'n'.")


def prompt_email(question: str, force_value: Optional[str] = None) -> str:
    """Ask for an email address with basic validation."""
    if force_value:
        return force_value
    while True:
        try:
            email = input(f"{Colours.YELLOW}{question}: {Colours.RESET}").strip()
        except EOFError:
            print_error("No email provided (stdin closed).")
            sys.exit(2)
        if re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            return email
        print("Please enter a valid email address.")


###############################################################################
# PHASE 0: PRE-FLIGHT SNAPSHOT [RECOMMENDED]
# Captures the user's complete state before any changes are made.
# This is your audit trail and rollback reference.
###############################################################################

def preflight_snapshot(email: str, dry_run: bool, timestamp: str = "") -> Tuple[Optional[Path], Optional[str]]:
    """
    [RECOMMENDED] Export user state to a JSON file before making changes.

    Captures: user info, group memberships, aliases, delegates,
    forwarding settings, licences, and Drive file counts.

    This runs even in dry-run mode because it is read-only.

    Returns (snapshot_file_path, licences_csv_output) so callers can
    reuse the licences output in Phase 5 without re-running the slow
    `gam print licenses` query.
    """
    print_header("PHASE 0: PRE-FLIGHT SNAPSHOT")

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "user": email,
        "dry_run": dry_run,
        "script_version": "4.3",
        "data": {}
    }

    # User info
    print_info("Capturing user info...")
    success, output = run_gam(
        ["info", "user", email],
        dry_run=False,
        capture_output=True,
        timeout=60
    )
    if success:
        snapshot["data"]["user_info"] = output

    # Group memberships
    print_info("Capturing group memberships...")
    success, output = run_gam(
        ["user", email, "print", "groups"],
        dry_run=False,
        capture_output=True,
        timeout=60,
        stdout_only=True
    )
    if success:
        snapshot["data"]["groups"] = output

    # Aliases
    print_info("Capturing aliases...")
    success, output = run_gam(
        ["print", "aliases", "user", email],
        dry_run=False,
        capture_output=True,
        timeout=30,
        stdout_only=True
    )
    if success:
        snapshot["data"]["aliases"] = output

    # Delegates
    print_info("Capturing delegates...")
    success, output = run_gam(
        ["user", email, "show", "delegates"],
        dry_run=False,
        capture_output=True,
        timeout=30
    )
    if success:
        snapshot["data"]["delegates"] = output

    # Forwarding
    print_info("Capturing forwarding settings...")
    success, output = run_gam(
        ["user", email, "show", "forward"],
        dry_run=False,
        capture_output=True,
        timeout=30
    )
    if success:
        snapshot["data"]["forwarding"] = output

    # Licences
    # The licensing API is consistently slow (20-30s typical in some tenants);
    # use a generous timeout so the snapshot doesn't trip a false alarm.
    print_info("Capturing licences...")
    success, output = run_gam(
        ["user", email, "print", "licenses"],
        dry_run=False,
        capture_output=True,
        timeout=180,
        stdout_only=True
    )
    licences_output: Optional[str] = None
    if success:
        snapshot["data"]["licenses"] = output
        licences_output = output

    # Send-as addresses
    print_info("Capturing send-as addresses...")
    success, output = run_gam(
        ["user", email, "show", "sendas"],
        dry_run=False,
        capture_output=True,
        timeout=30
    )
    if success:
        snapshot["data"]["sendas"] = output

    # Save snapshot
    snapshot_dir = BACKUP_DIRECTORY / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = snapshot_dir / f"{email}_{timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    try:
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, default=str)
        print_success(f"Snapshot saved: {snapshot_file}")
        summary_action(f"Pre-flight snapshot saved to {snapshot_file}")
        return snapshot_file, licences_output
    except Exception as e:
        print_error(f"Failed to save snapshot: {e}")
        summary_error(f"Snapshot save failed: {e}")
        return None, licences_output


###############################################################################
# PHASE 1: KILL SWITCH [CRITICAL]
###############################################################################

def execute_kill_switch(email: str, dry_run: bool, is_suspended: bool,
                        is_2sv_enrolled: bool = True):
    """
    [CRITICAL] Immediate containment of the user account.

    EXECUTION ORDER REASONING:
      1. OU move FIRST (allows turnoff2sv by removing 2SV enforcement)
      2. Wipe recovery info (prevents "Forgot Password" re-entry)
      3. Deprovision (tokens, ASPs, backup codes, POP/IMAP, signout, 2SV)
      4. Explicit signout (belt-and-braces)
      5. Explicit turnoff2sv (belt-and-braces, skipped if not enrolled)
      6. Scramble password (blocks login even if above steps partially fail)
      7. Hide from GAL (cosmetic but important for clean directory)

    EDGE CASE: If user is already suspended, deprovision backup codes
    and turnoff2sv will fail. We handle this by logging warnings rather
    than aborting the entire phase.

    EDGE CASE: If user is not enrolled in 2SV, skip turnoff2sv steps to
    avoid GAM exit-50 errors that pollute the error summary.
    """
    print_header("PHASE 1: KILL SWITCH (CONTAINMENT)")

    if is_suspended:
        print_warning(
            "User is already suspended. Deprovision backup codes and "
            "turnoff2sv will likely fail. Continuing with other steps."
        )

    # Step 1: Move to holding OU [CRITICAL]
    print_info("Step 1/7: Moving user to offboarding OU...")
    success, _ = run_gam(
        ["update", "user", email, "org", OFFBOARDING_OU],
        dry_run=dry_run
    )
    if success:
        summary_action(f"Moved to OU: {OFFBOARDING_OU}")
    else:
        print_error("CRITICAL: Failed to move user to offboarding OU.")

    # Step 2: Wipe recovery info [CRITICAL]
    print_info("Step 2/7: Wiping recovery email and phone...")
    run_gam(
        ["update", "user", email, "recoveryemail", "", "recoveryphone", ""],
        dry_run=dry_run
    )
    summary_action("Wiped recovery email and phone")

    # Step 3: Deprovision [CRITICAL]
    # GAM7 wiki (Users-Deprovision):
    #   gam <UserTypeEntity> deprovision|deprov [popimap] [signout] [turnoff2sv]
    # Deletes ASPs, backup codes, OAuth tokens.
    # [popimap] also disables POP/IMAP.
    # [signout] forces sign-out.
    # [turnoff2sv] disables 2-Step Verification.
    #
    # NOTE: Will partially fail on suspended users (backup codes).
    # NOTE: Only include turnoff2sv if the user is actually enrolled, otherwise
    #       GAM exits with code 50 which pollutes the error summary.
    deprov_args = ["user", email, "deprovision", "popimap", "signout"]
    if is_2sv_enrolled:
        deprov_args.append("turnoff2sv")
    label = "ASPs, backup codes, tokens, POP/IMAP, signout" + (", 2SV" if is_2sv_enrolled else "")
    print_info(f"Step 3/7: Deprovisioning ({label})...")
    success, output = run_gam(deprov_args, dry_run=dry_run, capture_output=True)
    if success:
        summary_action(f"Deprovisioned: {label}")
    # Check for partial failure (backup codes on suspended user)
    if output and "not deprovisioned" in output.lower():
        print_warning(f"Partial deprovision: {output}")
        summary_warning("Deprovision partially failed (likely suspended user)")

    # Step 4: Explicit signout [RECOMMENDED]
    # GAM7 wiki (Users-Signout-Turnoff2SV):
    #   gam <UserTypeEntity> signout
    print_info("Step 4/7: Forcing sign-out from all sessions...")
    run_gam(["user", email, "signout"], dry_run=dry_run)
    summary_action("Forced sign-out")

    # Step 5: Turn off 2SV [RECOMMENDED]
    # GAM7 wiki (Users-Signout-Turnoff2SV):
    #   gam <UserTypeEntity> turnoff2sv
    # Will fail if: suspended, not enrolled, OU enforces 2SV, or Advanced Protection
    # Skipped entirely if not enrolled to avoid spurious GAM exit-50 errors.
    if not is_2sv_enrolled:
        print_info("Step 5/7: Skipping turnoff2sv (user not enrolled in 2SV).")
        summary_warning("turnoff2sv skipped (user not enrolled in 2SV)")
    else:
        print_info("Step 5/7: Turning off 2-Step Verification...")
        success, output = run_gam(
            ["user", email, "turnoff2sv"],
            dry_run=dry_run,
            capture_output=True
        )
        if success:
            summary_action("Turned off 2SV")
        elif output and ("not enrolled" in output.lower() or "suspended" in output.lower()):
            print_warning(f"turnoff2sv skipped: {output.splitlines()[0] if output else 'unknown reason'}")
            summary_warning("turnoff2sv skipped (user not enrolled or suspended)")

    # Step 6: Scramble password [CRITICAL]
    # GAM7 wiki (Users): gam update user <email> password random
    print_info("Step 6/7: Scrambling password...")
    run_gam(
        ["update", "user", email, "password", "random", "changepassword", "on"],
        dry_run=dry_run
    )
    summary_action("Password scrambled and forced change on next login")

    # Step 7: Hide from GAL [IMPORTANT]
    # GAM7 wiki (Users): gam update user <email> gal off
    print_info("Step 7/7: Hiding from Global Address List...")
    run_gam(
        ["update", "user", email, "gal", "off"],
        dry_run=dry_run
    )
    summary_action("Hidden from GAL")


###############################################################################
# PHASE 2: DEVICE MANAGEMENT [IMPORTANT]
###############################################################################

def manage_devices(email: str, _dry_run: bool):
    """
    [IMPORTANT] List and optionally wipe devices associated with the user.
    Actual wipe operations are logged as guidance, not executed automatically,
    because factory-resetting a device is destructive and irreversible.
    """
    print_header("PHASE 2: DEVICE MANAGEMENT")

    # Mobile devices
    print_info("Querying mobile devices...")
    success, output = run_gam(
        ["print", "mobile", "query", f"email:{email}"],
        dry_run=False,
        capture_output=True,
        stdout_only=True
    )
    mobile_lines = [l for l in output.splitlines() if l.strip()]
    if success and len(mobile_lines) > 1:
        print_warning("Mobile devices found. Review and wipe manually:")
        print_info("  Account wipe (corp data): gam update mobile <resourceId> action account_wipe")
        print_info("  Factory reset: gam update mobile <resourceId> action wipe")
        summary_action("Mobile devices found and listed for review")
    else:
        print_success("No mobile devices found.")
        summary_action("No mobile devices")

    # ChromeOS devices
    print_info("Querying ChromeOS devices...")
    success, output = run_gam(
        ["print", "cros", "query", f"user:{email}"],
        dry_run=False,
        capture_output=True,
        stdout_only=True
    )
    cros_lines = [l for l in output.splitlines() if l.strip()]
    if success and len(cros_lines) > 1:
        print_warning("ChromeOS devices found. Review and disable/deprovision manually:")
        print_info("  Disable: gam update cros <deviceId> action disable")
        print_info("  Deprovision: gam update cros <deviceId> action deprovision_retiring_device")
        summary_action("ChromeOS devices found and listed for review")
    else:
        print_success("No ChromeOS devices found.")
        summary_action("No ChromeOS devices")


###############################################################################
# PHASE 3: GROUP REMOVAL [IMPORTANT]
###############################################################################

def remove_groups(email: str, dry_run: bool):
    """
    [IMPORTANT] Remove the user from all groups.

    GAM7: gam user <email> delete groups
    """
    print_header("PHASE 3: GROUP REMOVAL")

    print_info("Listing current group memberships...")
    # stdout_only=True: keep stderr out of the captured CSV so GAM's
    # "Getting Groups for user@..." / "Got N Groups" progress lines
    # can't be mistaken for CSV rows by DictReader.
    success, output = run_gam(
        ["user", email, "print", "groups"],
        dry_run=False,
        capture_output=True,
        stdout_only=True,
    )

    group_count = 0
    group_names: List[str] = []
    if success and output.strip():
        # GAM's `print groups` CSV column ordering and naming varies by
        # version, and GAM sometimes prepends a "Getting N Groups for
        # user@..." info line on stderr that run_gam merges into stdout.
        # Strip any leading non-CSV lines (no comma) before parsing, and
        # match the group-address column by a substring search rather
        # than exact name so we tolerate "Group", "GroupEmail", "group
        # Email", "groupKey" etc.
        all_lines = output.strip().splitlines()
        # Drop leading info lines until we find one that looks like CSV.
        csv_lines = list(all_lines)
        while csv_lines and "," not in csv_lines[0]:
            csv_lines.pop(0)

        if csv_lines:
            try:
                reader = csv.DictReader(io.StringIO("\n".join(csv_lines)))
                rows = list(reader)
                group_count = len(rows)
                fieldnames = [f for f in (reader.fieldnames or []) if f]
                # Prefer a column with "group" in the name; otherwise
                # take the first column that holds an email-looking value
                # that ISN'T the queried user's own address.
                group_col = next(
                    (f for f in fieldnames if "group" in f.lower()),
                    None,
                )
                if not group_col and rows:
                    for f in fieldnames:
                        v = (rows[0].get(f) or "").strip()
                        if "@" in v and v.lower() != email.lower():
                            group_col = f
                            break
                if group_col:
                    for row in rows:
                        v = (row.get(group_col) or "").strip()
                        if v:
                            group_names.append(v)

                # Diagnostic: if we counted rows but couldn't extract any
                # names, dump headers + first row so the GAM output format
                # is debuggable straight from the log file without a re-run.
                if group_count > 0 and not group_names:
                    first_row = rows[0] if rows else {}
                    logger.info(
                        f"Group preview empty despite {group_count} row(s). "
                        f"Headers: {fieldnames}. Chose column: {group_col!r}. "
                        f"First row: {dict(first_row)!r}"
                    )
            except csv.Error:
                group_count = max(0, len(csv_lines) - 1)

    if group_count == 0:
        print_success("User is not a member of any groups.")
        summary_action("No group memberships to remove")
        return

    preview = ", ".join(group_names[:5])
    if len(group_names) > 5:
        preview += f", ... (+{len(group_names) - 5} more)"
    print_info(f"Found {group_count} group membership(s): {preview}")

    if dry_run:
        run_gam(["user", email, "delete", "groups"], dry_run=True)
        summary_action(f"Would remove {group_count} group membership(s)")
        return

    print_info(f"Removing from {group_count} group(s)...")
    ok, _ = run_gam(["user", email, "delete", "groups"], dry_run=False)
    if ok:
        summary_action(f"Removed from {group_count} group(s)")
    else:
        summary_error(f"Group removal failed (was member of {group_count} group(s))")


###############################################################################
# PHASE 4: DELEGATE CLEANUP [IMPORTANT]
# This is NEW in v4.1. Removes both:
#   - Delegates who have access TO this user's mailbox
#   - Delegate access this user has TO other mailboxes
###############################################################################

def cleanup_delegates(email: str, dry_run: bool):
    """
    [IMPORTANT] Remove all mailbox delegation relationships.

    Two directions to clean up:
    1. People who can read THIS user's mailbox (inbound delegates)
    2. Mailboxes THIS user can read (outbound, harder to find)

    For inbound, we use:
      gam user <email> print delegates -> get list
      gam user <email> delete delegate <delegate>

    For outbound, there is no single GAM command to find all mailboxes
    a user is a delegate of. This would require iterating all users.
    We log a warning about this limitation.

    GAM7 wiki (Users-Gmail-Delegates):
      gam <UserTypeEntity> delete delegate <UserEntity>
      gam <UserTypeEntity> show delegates
    """
    print_header("PHASE 4: DELEGATE CLEANUP")

    # Inbound: who can access this user's mailbox?
    print_info("Checking who has delegate access to this mailbox...")
    success, output = run_gam(
        ["user", email, "show", "delegates"],
        dry_run=False,
        capture_output=True
    )

    if success and output:
        # Parse delegate addresses from output
        delegates = re.findall(r'Delegate:\s+(\S+@\S+)', output, re.IGNORECASE)
        if delegates:
            total = len(delegates)
            print_info(f"Found {total} delegate(s) with access to this mailbox.")
            removed = 0
            for i, delegate in enumerate(delegates, 1):
                print_info(f"  [{i}/{total}] Removing delegate: {delegate}")
                ok, _ = run_gam(
                    ["user", email, "delete", "delegate", delegate],
                    dry_run=dry_run
                )
                if ok:
                    removed += 1
            if dry_run:
                summary_action(f"Would remove {total} inbound delegate(s)")
            else:
                summary_action(f"Removed {removed}/{total} inbound delegate(s)")
        else:
            print_success("No inbound delegates found.")
            summary_action("No inbound delegates to remove")
    else:
        print_success("No delegates found or unable to query.")

    # Outbound warning
    print_warning(
        "NOTE: This script cannot automatically find all mailboxes this "
        "user has delegate access TO (it would require scanning all users). "
        "Check the pre-flight snapshot's delegate section for any references, "
        "or run: gam all users print delegates | grep <email>"
    )
    summary_warning("Outbound delegate cleanup requires manual verification")


###############################################################################
# PHASE 5: LICENCE REMOVAL [RECOMMENDED]
###############################################################################

def remove_licences(email: str, dry_run: bool, cached_output: Optional[str] = None):
    """
    [RECOMMENDED] Remove all licences from the user to free up seats.

    Uses: gam print licenses users <email>
    which outputs per-SKU rows (User, productId, skuId, skuDisplayName),
    then deletes each licence individually. Avoids the shell pipe pattern
    whose CSV headers differ from the per-user summary command.

    If `cached_output` is supplied (typically the licences CSV captured
    during the pre-flight snapshot), it is reused instead of re-running
    the slow `gam print licenses` query.
    """
    print_header("PHASE 5: LICENCE REMOVAL")

    # gam user <email> print licenses outputs a summary row:
    #   primaryEmail,LicensesCount,Licenses,LicensesDisplay
    # where Licenses is a space-separated list of skuIds.
    if cached_output is not None:
        print_info("Reusing licence list from pre-flight snapshot...")
        success, output = True, cached_output
    else:
        print_info("Querying assigned licences...")
        success, output = run_gam(
            ["user", email, "print", "licenses"],
            dry_run=False,
            capture_output=True,
            timeout=180
        )

    if not success:
        # Timeout or API failure — do NOT claim there are no licences,
        # otherwise a timed-out query silently leaves paid seats assigned.
        print_error("Could not query licences; manual cleanup required.")
        summary_error(
            f"Licence query failed for {email} — verify and remove manually "
            f"with: gam user {email} print licenses"
        )
        return

    if not output.strip():
        print_success("No licences to remove")
        summary_action("No licences found")
        return

    # Parse the Licenses (skuIds) and LicensesDisplay (human names) columns
    # from the summary row. We zip them so error/summary messages can show
    # display names instead of opaque skuIds.
    sku_ids: List[str] = []
    sku_names: List[str] = []
    lines = output.strip().splitlines()
    if len(lines) > 1:
        headers = [h.strip() for h in lines[0].split(',')]
        try:
            lic_idx = headers.index('Licenses')
            count_idx = headers.index('LicensesCount')
        except ValueError:
            print_error(f"Unexpected licence output format — headers: {lines[0]}")
            summary_error(f"Licence removal issue: unexpected CSV headers: {lines[0]}")
            return
        display_idx = headers.index('LicensesDisplay') if 'LicensesDisplay' in headers else None
        data = [v.strip() for v in lines[1].split(',')]
        count = int(data[count_idx]) if data[count_idx].isdigit() else 0
        if count > 0 and len(data) > lic_idx and data[lic_idx]:
            sku_ids = data[lic_idx].split()
            if display_idx is not None and len(data) > display_idx and data[display_idx]:
                sku_names = data[display_idx].split()
            # Pad names to match ids in case the display column is shorter.
            while len(sku_names) < len(sku_ids):
                sku_names.append(sku_ids[len(sku_names)])

    if not sku_ids:
        print_success("No licences to remove")
        summary_action("No licences found")
        return

    def label(i: int) -> str:
        """Human-readable licence label, falling back to skuId when no name."""
        name = sku_names[i] if i < len(sku_names) else sku_ids[i]
        if name and name != sku_ids[i]:
            return f"{name} ({sku_ids[i]})"
        return sku_ids[i]

    labels = [label(i) for i in range(len(sku_ids))]
    print_info(f"Found {len(sku_ids)} licence(s): {', '.join(labels)}")

    if dry_run:
        for sku_id in sku_ids:
            run_gam(["user", email, "delete", "license", sku_id], dry_run=True)
        summary_action(f"Licences listed (dry run): {', '.join(labels)}")
        return

    removed_labels, auto_assigned_labels, failed_labels = [], [], []
    for i, sku_id in enumerate(sku_ids):
        lbl = labels[i]
        print_info(f"  [{i + 1}/{len(sku_ids)}] Removing licence: {lbl}")
        ok, delete_output = run_gam(
            ["user", email, "delete", "license", sku_id],
            dry_run=False,
            capture_output=True,
            non_fatal_patterns=["auto-assigned"]
        )
        if "auto-assigned" in delete_output.lower():
            auto_assigned_labels.append(lbl)
        elif ok:
            removed_labels.append(lbl)
        else:
            failed_labels.append(lbl)

    if removed_labels:
        print_success(f"Removed {len(removed_labels)} licence(s): {', '.join(removed_labels)}")
        summary_action(f"Removed {len(removed_labels)} licence(s): {', '.join(removed_labels)}")
    if auto_assigned_labels:
        print_warning(
            f"Licence(s) {', '.join(auto_assigned_labels)} have auto-assignment "
            f"enabled and cannot be removed via API. Remove manually in Admin "
            f"Console > Billing > Subscriptions."
        )
        summary_warning(
            f"Licence(s) {', '.join(auto_assigned_labels)} are auto-assigned; "
            f"manual removal required in Admin Console"
        )
    if not removed_labels and not auto_assigned_labels and not failed_labels:
        print_success("No licences to remove")
        summary_action("No licences found")
    if failed_labels:
        summary_error(f"Licence removal failed for: {', '.join(failed_labels)}")


###############################################################################
# PHASE 6: DATA TRANSFERS [IMPORTANT]
###############################################################################

def transfer_drive(source: str, destination: str, dry_run: bool):
    """
    [IMPORTANT] Transfer Drive file ownership.

    Streams GAM's per-file progress to the log instead of buffering it,
    so the user can see "Got N files" / "Transferring file X of Y" while
    the transfer is in flight. Uses no overall timeout because large
    drives can legitimately take hours.

    GAM7 wiki (Users-Drive-Transfer):
      gam user <source> transfer drive <destination> [keepuser]
    """
    print_header("DRIVE TRANSFER")

    if not validate_destination(destination):
        summary_error(f"Drive transfer skipped: destination {destination} invalid")
        return

    print_info(f"Transferring Drive files: {source} -> {destination}")
    print_info(
        "Progress is also visible in Admin Console -> Reporting -> Audit "
        "and investigation -> Drive log events (filter Actor=source user, "
        f"Event=Change owner), or in {destination}'s Drive UI under "
        "'Shared with me'."
    )

    full_cmd = [GAM_COMMAND, "user", source, "transfer", "drive",
                destination, "keepuser"]
    cmd_str = " ".join(full_cmd)

    if dry_run:
        print_info(f"DRY RUN: {cmd_str}")
        summary_action(f"Drive transfer planned to {destination}")
        return

    logger.info(f"Executing: {cmd_str}")

    try:
        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,  # line-buffered so progress appears live
        )

        for line in proc.stdout:  # type: ignore[union-attr]
            if shutdown_requested:
                proc.terminate()
                break
            line = line.rstrip()
            if line:
                logger.info(line)

        proc.wait()

        if proc.returncode == 0:
            summary_action(f"Drive transferred to {destination}")
        else:
            print_error(f"Drive transfer failed (exit {proc.returncode}): {cmd_str}")
            summary_error(f"Drive transfer failed: {source} -> {destination}")

    except FileNotFoundError:
        print_error(f"GAM command not found: {GAM_COMMAND}")
        summary_error("GAM7 not found in PATH")
    except Exception as e:
        print_error(f"Drive transfer exception: {e}")
        summary_error(f"Drive transfer exception: {e}")


def transfer_aliases(source: str, destination: str, dry_run: bool):
    """
    [RECOMMENDED] Transfer email aliases.

    Uses CSV pipe pattern:
      gam print aliases user <source> |
      gam csv - gam update alias ~alias user <destination>
    """
    print_header("ALIAS TRANSFER")

    if not validate_destination(destination):
        summary_error(f"Alias transfer skipped: destination {destination} invalid")
        return

    print_info(f"Transferring aliases: {source} -> {destination}")

    if dry_run:
        run_gam(
            ["print", "aliases", "user", source],
            dry_run=False,
            capture_output=True
        )
        summary_action(f"Aliases listed (dry run)")
        return

    quoted_dest = f'"{destination}"' if os.name == 'nt' else f"'{destination}'"
    cmd_str = (
        f'{GAM_COMMAND} print aliases user {source} | '
        f'{GAM_COMMAND} csv - gam update alias ~Alias user {quoted_dest}'
    )

    success, output = run_shell_pipe(cmd_str, dry_run=False, timeout=120)
    if success:
        print_success("Aliases transferred")
        summary_action(f"Aliases transferred to {destination}")
    else:
        summary_error(f"Alias transfer issue: {output[:200]}")


def quarantine_unreadable_messages(backup_path: Path) -> List[str]:
    """
    Move unreadable .eml files out of the GYB backup folder so the restore
    skips them instead of crashing, and write a skipped-messages CSV.

    Why: endpoint antivirus can quarantine a message file in place right
    after GYB writes it during backup (a genuinely malicious email that was
    sitting in the source mailbox). The file still exists on disk but every
    read raises PermissionError, and GYB's restore has no per-message
    read-error handling, so one locked file kills the whole restore mid-run.
    GYB DOES skip a file that is absent (its own os.path.isfile() check), so
    the portable fix is to make the bad file absent: probe each .eml with a
    one-byte read and move any unreadable one to a sibling
    <backup>_quarantined/ folder, outside --local-folder. Moving works even
    while reading is blocked, because a rename is a directory metadata
    operation, not a file read. Nothing is deleted.

    Each skipped file is reported by its basename, which is the Gmail
    immutable message ID: admins can look the message up in their AV
    quarantine log, Google Vault, or the Security Investigation Tool. The
    message date is pulled from GYB's msg-db.sqlite (read-only) when
    available. A CSV of skipped messages is written next to the backup
    folder.

    Never raises: any unexpected condition degrades to a loud warning so the
    pre-scan can slow a run down but cannot break one. Side benefit: reading
    every file here provokes on-access AV to flag bad files BEFORE the
    restore starts rather than partway through it.
    """
    skipped: List[str] = []
    moved_to: Dict[str, Path] = {}
    try:
        quarantine_dir = backup_path.parent / f"{backup_path.name}_quarantined"
        for eml in sorted(backup_path.rglob("*.eml")):
            try:
                with open(eml, "rb") as fh:
                    fh.read(1)
            except OSError as read_err:
                target = quarantine_dir / eml.relative_to(backup_path)
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(eml), str(target))
                except OSError as move_err:
                    print_warning(
                        f"Unreadable message {eml.name} could not be moved aside "
                        f"({move_err}); the GYB restore may crash on it. "
                        f"Move or delete it manually, then re-run."
                    )
                    continue
                print_warning(
                    f"Skipping unreadable message {eml.stem} ({read_err}); "
                    f"moved to {target}"
                )
                skipped.append(eml.stem)
                moved_to[eml.stem] = target

        if skipped:
            # Message dates from GYB's own catalogue (read-only; we never
            # write to any GYB sqlite file). Basename match avoids the
            # Windows/POSIX path-separator difference in stored filenames.
            dates: Dict[str, str] = {}
            try:
                with sqlite3.connect(backup_path / "msg-db.sqlite") as db:
                    for msg_id in skipped:
                        row = db.execute(
                            "SELECT message_internaldate FROM messages "
                            "WHERE message_filename LIKE ?",
                            (f"%{msg_id}%",),
                        ).fetchone()
                        if row:
                            dates[msg_id] = str(row[0])
            except (sqlite3.Error, OSError) as db_err:
                print_warning(f"Could not read message dates from msg-db.sqlite: {db_err}")

            csv_path = backup_path.parent / f"{backup_path.name}_skipped-messages.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["gmail_message_id", "message_date", "quarantined_file", "note"])
                for msg_id in skipped:
                    writer.writerow([
                        msg_id,
                        dates.get(msg_id, "unknown"),
                        str(moved_to[msg_id]),
                        "Unreadable on disk (likely quarantined by local antivirus). "
                        "NOT restored to the destination mailbox. Look it up by "
                        "message ID in your AV quarantine log, Google Vault, or the "
                        "Security Investigation Tool.",
                    ])
            # Enumerated in red so the skipped mail cannot be missed in the
            # scroll-back or the end-of-run summary.
            skipped_list = ", ".join(
                f"{msg_id} (dated {dates.get(msg_id, 'unknown')})" for msg_id in skipped
            )
            print_warning(
                f"{Colours.RED}{len(skipped)} unreadable message(s) moved to "
                f"{quarantine_dir} and excluded from the restore: {skipped_list}. "
                f"Details: {csv_path}{Colours.RESET}"
            )
            summary_warning(
                f"{Colours.RED}{len(skipped)} email message(s) skipped as "
                f"unreadable/AV-quarantined (not migrated): {skipped_list}; "
                f"see {csv_path}{Colours.RESET}"
            )
    except Exception as scan_err:  # pre-scan must never break an offboarding run
        print_warning(f"Backup pre-scan for unreadable messages failed: {scan_err}")
    return skipped


def migrate_email(source: str, destination: str, dry_run: bool, strip_labels: bool = True):
    """
    [OPTIONAL] Back up and restore email using GYB.

    When strip_labels is True (the default), GYB's --strip-labels is passed on
    restore so all original Gmail labels — including INBOX — are discarded, and
    the only label remaining on each restored message is Migrated/<source-user>.
    Effectively this archives the migrated mail under a single namespaced label.
    When False, original labels (INBOX, custom labels, system labels) are
    preserved and the migration label is added on top.

    GYB syntax:
      gyb --email <src> --action backup --local-folder <path>
      gyb --email <dst> --action restore --local-folder <path>
    """
    print_header("EMAIL MIGRATION")

    if not validate_destination(destination):
        summary_error(f"Email migration skipped: destination {destination} invalid")
        return

    print_info(f"Migrating email: {source} -> {destination}")
    backup_path = BACKUP_DIRECTORY / "mailboxes" / f"{source}_{datetime.now().strftime('%Y%m%d')}"
    backup_path.mkdir(parents=True, exist_ok=True)

    # Backup
    print_info(f"Backing up email to: {backup_path}")
    print_info(
        "GYB will print a live progress bar (e.g. ' 42%|####  | 1234/2950 [01:23<02:45]'). "
        "For large mailboxes this phase can run for tens of minutes."
    )
    success, _ = run_gyb(
        ["--email", source, "--action", "backup", "--local-folder", str(backup_path)],
        dry_run=dry_run
    )
    if not success and not dry_run:
        print_error("Email backup failed; skipping restore.")
        summary_error("Email backup failed")
        return

    # Pre-scan: move any unreadable (AV-quarantined) messages aside so the
    # restore cannot crash on them. See quarantine_unreadable_messages().
    skipped: List[str] = []
    if not dry_run:
        print_info("Scanning backup for unreadable (AV-quarantined) messages...")
        skipped = quarantine_unreadable_messages(backup_path)

    # Restore
    migration_label = f"Migrated/{source}"
    mode_desc = "archived under single label" if strip_labels else "original labels preserved + migration label"
    print_info(f"Restoring email to: {destination} (label: {migration_label}; {mode_desc})")
    restore_args = ["--email", destination, "--action", "restore",
                    "--local-folder", str(backup_path),
                    "--label-restored", migration_label]
    if strip_labels:
        restore_args.append("--strip-labels")
    success, _ = run_gyb(restore_args, dry_run=dry_run)
    if not success and not dry_run:
        print_error(f"Email restore failed; backup retained at {backup_path}")
        summary_error(
            f"Email restore to {destination} FAILED partway; backup retained at "
            f"{backup_path}. Re-run the same gyb restore command (resume is on "
            f"by default) or re-run this script."
        )
        return
    migrated_desc = f"Email migrated to {destination} under label '{migration_label}' ({mode_desc})"
    if skipped:
        migrated_desc += f", excluding {len(skipped)} unreadable/AV-quarantined message(s)"
    summary_action(migrated_desc)


def transfer_calendar(source: str, destination: str, dry_run: bool):
    """
    [RECOMMENDED] Add the destination user as a manager of the
    departing user's calendar so they can see/manage existing events.

    GAM7:
      gam user <source> add calendaracl <destination> role editor

    NOTE: Full calendar ownership transfer is now possible via the
    Google Admin console (October 2025 update), but not yet directly
    via the Calendar API/GAM. This step grants editor access as
    the closest API-supported equivalent.
    """
    print_header("CALENDAR ACCESS TRANSFER")

    if not validate_destination(destination):
        summary_error(f"Calendar transfer skipped: destination {destination} invalid")
        return

    print_info(f"Granting calendar editor access: {source} -> {destination}")
    # GAM7 syntax: gam user <src> add calendaracls <calendarid> <role> user:<email>
    # Use the source email as the calendar ID (their primary calendar).
    run_gam(
        ["user", source, "add", "calendaracls", source, "writer", f"user:{destination}"],
        dry_run=dry_run
    )
    summary_action(f"Calendar editor access granted to {destination}")


###############################################################################
# PHASE 7: EMAIL FORWARDING [RECOMMENDED]
# Sets up email forwarding to a successor so incoming mail is not lost.
###############################################################################

def setup_forwarding(email: str, forward_to: str, dry_run: bool):
    """
    [RECOMMENDED] Set up email forwarding to a successor.

    Two-step process (GAM7 wiki, Users-Gmail-Forwarding):
      1. gam user <email> add forwardingaddress <forward_to>
      2. gam user <email> forward on <forward_to> keep

    The 'keep' action leaves a copy in the departing user's mailbox
    (useful for Vault retention). Alternatives: archive, delete, markread.

    EDGE CASE: Forwarding only works within the same domain or to
    verified alias/secondary domains. Cross-domain forwarding may fail.

    EDGE CASE: The forwarding address must be registered BEFORE it
    can be activated. There may be a brief delay between the two steps.
    """
    print_header("EMAIL FORWARDING SETUP")

    if not validate_destination(forward_to, allow_group=True):
        summary_error(f"Forwarding skipped: destination {forward_to} invalid")
        return

    # Step 1: Register the forwarding address
    print_info(f"Registering forwarding address: {forward_to}")
    success, output = run_gam(
        ["user", email, "add", "forwardingaddress", forward_to],
        dry_run=dry_run,
        capture_output=True,
        non_fatal_patterns=["already exists"]
    )

    if not dry_run and not success:
        print_error(f"Could not register forwarding address. Output: {output}")
        summary_error(f"Forwarding registration failed for {forward_to}")
        return

    if not dry_run and "already exists" in output.lower():
        print_info("Forwarding address already registered — continuing to activate.")

    # Step 2: Wait until the address shows verificationStatus=accepted.
    # Activating before verification propagates fails with
    # "Set Failed: Invalid forwarding address" even for same-domain destinations.
    if not dry_run:
        print_info("Waiting for forwarding address to be verified...")
        verified = False
        deadline = time.time() + 60  # poll up to 60s total
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            ok, status_output = run_gam(
                ["user", email, "show", "forwardingaddresses"],
                dry_run=False,
                capture_output=True,
                timeout=30,
                stdout_only=True
            )
            if ok:
                lower_out = status_output.lower()
                if forward_to.lower() in lower_out and "accepted" in lower_out:
                    verified = True
                    print_success(
                        f"Forwarding address verified after {attempt} check(s)."
                    )
                    break
            time.sleep(3)

        if not verified:
            print_error(
                f"Forwarding address {forward_to} did not reach 'accepted' "
                f"state within 60s. Skipping activation."
            )
            summary_error(
                f"Forwarding NOT activated for {email}: {forward_to} unverified. "
                f"Once verified, run: gam user {email} forward on {forward_to} keep"
            )
            return

    # Step 3: Activate forwarding
    print_info(f"Activating forwarding: {email} -> {forward_to} (keep copy)")
    activate_ok, _ = run_gam(
        ["user", email, "forward", "on", forward_to, "keep"],
        dry_run=dry_run,
        capture_output=True
    )

    if dry_run or activate_ok:
        summary_action(f"Email forwarding set to {forward_to} (keep copy)")
    else:
        summary_error(
            f"Forwarding activation failed for {email} -> {forward_to}. "
            f"Retry with: gam user {email} forward on {forward_to} keep"
        )


###############################################################################
# RCLONE DRIVE BACKUP [RECOMMENDED]
# Downloads the user's entire Drive to local disk before any transfers.
###############################################################################

def backup_drive_rclone(email: str, dry_run: bool) -> bool:
    """
    [RECOMMENDED] Back up user's Drive to local disk via rclone.

    Uses --drive-impersonate to access the user's Drive via domain-wide
    delegation (same service account as GAM7).

    Returns True on success, False on failure.
    """
    print_header("DRIVE BACKUP (RCLONE)")

    backup_path = BACKUP_DIRECTORY / "drive" / f"{email}_{datetime.now().strftime('%Y%m%d')}"
    backup_path.mkdir(parents=True, exist_ok=True)

    rclone_args = [
        RCLONE_COMMAND, "sync",
        f"{RCLONE_REMOTE}:", str(backup_path),
        "--drive-impersonate", email,
        "--drive-export-formats", RCLONE_EXPORT_FORMATS,
        "-P", "--fast-list", "--transfers=4"
    ]
    cmd_str = " ".join(rclone_args)

    if dry_run:
        print_info(f"DRY RUN: {cmd_str}")
        summary_action(f"Drive backup planned to {backup_path}")
        return True

    print_info(f"Backing up Drive to: {backup_path}")
    print_info(
        "rclone -P prints a live transfer summary (Transferred: X / Y, N%, "
        "MiB/s, ETA). Updates are throttled to one log line per second."
    )

    try:
        # rclone -P repaints its summary using \r; we treat \r and \n as
        # line separators and throttle identical-prefix progress redraws
        # to one log entry per second to keep the log file manageable.
        proc = subprocess.Popen(
            rclone_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        last_progress_log = 0.0
        last_summary_line = ""
        buffer = ""

        def emit(line: str):
            nonlocal last_progress_log, last_summary_line
            line = line.rstrip()
            if not line:
                return
            is_progress = line.startswith("Transferred:") or "ETA" in line or "%" in line
            if is_progress:
                now = time.time()
                if now - last_progress_log < 1.0:
                    return
                last_progress_log = now
                last_summary_line = line
            logger.info(line)

        assert proc.stdout is not None
        while True:
            if shutdown_requested:
                proc.terminate()
                break
            chunk = proc.stdout.read(256)
            if not chunk:
                break
            buffer += chunk
            while True:
                idx = -1
                for sep in ("\r", "\n"):
                    i = buffer.find(sep)
                    if i != -1 and (idx == -1 or i < idx):
                        idx = i
                if idx == -1:
                    break
                emit(buffer[:idx])
                buffer = buffer[idx + 1:]
        if buffer:
            emit(buffer)

        proc.wait()

        if proc.returncode == 0:
            print_success(f"Drive backed up to: {backup_path}")
            if last_summary_line:
                print_info(f"  {last_summary_line}")
            summary_action(f"Drive backed up via rclone to {backup_path}")
            return True
        else:
            print_error(f"rclone failed (exit {proc.returncode})")
            summary_error(f"rclone backup failed (exit {proc.returncode})")
            return False

    except FileNotFoundError:
        print_error(f"rclone not found: {RCLONE_COMMAND}")
        summary_error("rclone not found in PATH")
        return False
    except Exception as e:
        print_error(f"rclone exception: {e}")
        summary_error(f"rclone exception: {e}")
        return False


###############################################################################
# GYB EMAIL BACKUP ONLY [RECOMMENDED]
# Downloads the user's mailbox to local disk WITHOUT restoring elsewhere.
###############################################################################

def backup_email_only(email: str, dry_run: bool) -> bool:
    """
    [RECOMMENDED] Back up user's email to local disk via GYB.
    Does NOT restore to another user; local archive only.

    Returns True on success, False on failure.
    """
    print_header("EMAIL BACKUP (GYB, LOCAL ONLY)")

    backup_path = BACKUP_DIRECTORY / "mailboxes" / f"{email}_email_{datetime.now().strftime('%Y%m%d')}"
    backup_path.mkdir(parents=True, exist_ok=True)

    print_info(f"Backing up email to: {backup_path}")

    success, output = run_gyb(
        ["--email", email, "--action", "backup", "--local-folder", str(backup_path)],
        dry_run=dry_run
    )

    if success:
        print_success(f"Email backed up to: {backup_path}")
        summary_action(f"Email backed up via GYB to {backup_path}")
        return True
    else:
        if not dry_run:
            print_error("Email backup failed")
            summary_error("GYB email backup failed")
        return False


###############################################################################
# USER DELETION [CRITICAL]
# Permanently deletes the user account. ONLY used in --scorched-earth mode.
###############################################################################

def delete_user(email: str, dry_run: bool):
    """
    [CRITICAL] Permanently delete the user account.

    GAM7 wiki (Users): gam delete user <email>

    IRREVERSIBLE after Google's 20-day undelete window.
    Only called in --scorched-earth mode.
    """
    print_header("PHASE FINAL: USER DELETION (SCORCHED EARTH)")

    print_error("WARNING: PERMANENTLY DELETING user account.")
    print_error(f"User: {email}")
    print_error("Irreversible after 20-day recovery window.")

    run_gam(
        ["delete", "user", email],
        dry_run=dry_run
    )
    summary_action(f"USER DELETED: {email}")


###############################################################################
# PHASE 8: AUTO-REPLY [RECOMMENDED]
###############################################################################

def set_auto_reply(email: str, dry_run: bool):
    """
    [RECOMMENDED] Set an out-of-office auto-reply.

    GAM7: gam user <email> vacation on subject <subject> message <message>

    EDGE CASE: This will not work if the user is suspended, so it must
    happen BEFORE suspension.
    """
    print_header("PHASE 8: AUTO-REPLY SETUP")

    run_gam(
        [
            "user", email, "vacation", "on",
            "subject", "Out of Office",
            "message", AUTO_REPLY_MESSAGE
        ],
        dry_run=dry_run
    )
    summary_action("Auto-reply message configured")


###############################################################################
# PHASE 9: SUSPENSION [IMPORTANT]
###############################################################################

def suspend_user(email: str, dry_run: bool):
    """
    [IMPORTANT] Suspend the user account.

    GAM7 wiki (Users): gam update user <email> suspended on

    This is ALWAYS the last step because:
      - deprovision backup codes fails on suspended users
      - turnoff2sv fails on suspended users
      - delegate setup fails on suspended users
      - email forwarding fails on suspended users
      - auto-reply setup fails on suspended users
      - vacation settings cannot be changed on suspended users
    """
    print_header("PHASE 9: SUSPENSION")

    run_gam(
        ["update", "user", email, "suspended", "on"],
        dry_run=dry_run
    )
    summary_action("User account suspended")


###############################################################################
# SUMMARY REPORT [RECOMMENDED]
###############################################################################

def print_summary(dry_run: bool):
    print_header("OFFBOARDING SUMMARY")

    if dry_run:
        print_warning("DRY RUN ONLY, NO CHANGES WERE MADE")
        print_info("Re-run with --doit to execute these operations.")

    # Actions
    if summary_actions:
        print("")
        print_info(f"Actions completed ({len(summary_actions)}):")
        for action in summary_actions:
            logger.info(f"  + {action}")

    # Warnings
    if summary_warnings:
        print("")
        print_warning(f"Warnings ({len(summary_warnings)}):")
        for warn in summary_warnings:
            logger.info(f"  ~ {warn}")

    # Skipped
    if summary_skipped:
        print("")
        print_info(f"Skipped ({len(summary_skipped)}):")
        for skip in summary_skipped:
            logger.info(f"  - {skip}")

    # Errors
    if summary_errors:
        print("")
        print_error(f"Errors ({len(summary_errors)}):")
        for error in summary_errors:
            logger.info(f"  ! {error}")

    # Phase timings
    if phase_timings:
        print("")
        print_info("Phase timings:")
        total = 0.0
        for phase, elapsed in phase_timings:
            logger.info(f"  {phase}: {elapsed:.1f}s")
            total += elapsed
        logger.info(f"  Total: {total:.1f}s")

    print("")
    print_info(f"Log file: {LOG_FILENAME}")


def print_mail_capture_instructions(offboarded_email: str, successor_email: str):
    """
    Print the end-of-run MANUAL ACTION block with three admin-console options
    for capturing mail to the offboarded address after suspension/deletion.

    Surfaced because GAM cannot configure the "Recipient address map" Gmail
    routing feature directly, and Gmail user-level forwarding stops once the
    source account is suspended/deleted. This block tells the admin what to
    do in the console.
    """
    width = 70
    bar = "=" * width
    logger.info("")
    logger.info(f"{Colours.YELLOW}{bar}")
    logger.info(f"  MANUAL ACTION REQUIRED — Mail capture for {offboarded_email}")
    logger.info(f"{bar}{Colours.RESET}")
    lines = [
        "",
        "Once the offboarded user is suspended or deleted, Gmail-level",
        "forwarding stops. To keep capturing mail sent to",
        f"  {offboarded_email}",
        "choose ONE of the following in the Admin console:",
        "",
        "OPTION 1 — Add as alias on the successor (simplest, single recipient)",
        f"  1. Admin console -> Directory -> Users -> {successor_email}",
        "  2. User information -> Email aliases -> ADD AN ALIAS",
        f"  3. Alias: {offboarded_email.split('@')[0]}",
        "  4. SAVE",
        "  Note: requires the offboarded address to be released. If the user",
        "  was only suspended, delete them first OR rename them.",
        "",
        "OPTION 2 — Recipient address map (works while user still exists)",
        "  1. Admin console -> Apps -> Google Workspace -> Gmail",
        "     -> Default routing",
        "  2. ADD ANOTHER RULE",
        f"  3. Single recipient: {offboarded_email}",
        f"  4. Action: Change envelope recipient -> {successor_email}",
        "  5. SAVE — takes effect within ~1 hour",
        "",
        "OPTION 3 — Convert to a Group (multiple recipients)",
        "  1. Admin console -> Directory -> Groups -> CREATE GROUP",
        f"  2. Group email: {offboarded_email}",
        f"  3. Add {successor_email} (and any others) as members",
        "  Note: same address-release requirement as Option 1.",
        "",
        f"Successor on record: {successor_email}",
    ]
    for line in lines:
        logger.info(line)
    logger.info(f"{Colours.YELLOW}{bar}{Colours.RESET}")


###############################################################################
# ARGUMENT PARSING [IMPORTANT]
###############################################################################

def parse_args():
    parser = argparse.ArgumentParser(
        description=f"Google Workspace User Offboarding Script v{SCRIPT_VERSION} (GAM7)",
        epilog=(
            "Examples:\n"
            "  python offboard_user.py                                          # Dry run\n"
            "  python offboard_user.py --doit                                   # Execute\n"
            "  python offboard_user.py --doit --backup-drive --backup-email     # Backup locally\n"
            "  python offboard_user.py --doit --no-transfer --backup-drive      # Backup, no transfers\n"
            "  python offboard_user.py --doit --force --user leaver@yourdomain.com \\\n"
            "      --all-transfer-to testoffboard.team@yourdomain.com                              # All transfers -> one user\n"
            "  python offboard_user.py --doit --force --user leaver@yourdomain.com \\\n"
            "      --all-transfer-to testoffboard.team@yourdomain.com \\\n"
            "      --drive-to testoffboard.manager@yourdomain.com                                  # Split: Drive -> manager, rest -> team\n"
            "  python offboard_user.py --doit --force --user leaver@yourdomain.com \\\n"
            "      --drive-to testoffboard.manager@yourdomain.com \\\n"
            "      --email-to testoffboard.ops@yourdomain.com --no-alias \\\n"
            "      --no-calendar --no-forward                                                       # Per-phase routing, no global default\n"
            "  python offboard_user.py --doit --force --scorched-earth          # DELETE user\n"
            "\n"
            "Transfer destination precedence (Drive, Email, Alias, Calendar, Forward):\n"
            "  1. Phase-specific flag (--drive-to, --email-to, --alias-to,\n"
            "     --calendar-to, --forward-to) -- always wins.\n"
            "  2. --all-transfer-to -- fallback for any phase without a specific flag.\n"
            "  3. Interactive prompt -- only when --force is NOT set.\n"
            "\n"
            "  With --force, every non-skipped transfer phase MUST resolve to a\n"
            "  destination via (1) or (2), or the run aborts before any change\n"
            "  is made. Skip a phase with --no-drive / --no-email / --no-alias /\n"
            "  --no-calendar / --no-forward.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # --- Execution mode ---
    parser.add_argument("--doit", action="store_true",
                        help="Execute changes (default is dry-run mode)")
    parser.add_argument("--force", action="store_true",
                        help="Skip all interactive prompts (auto-yes)")

    # --- Backup flags ---
    backup_grp = parser.add_argument_group("Backup options")
    backup_grp.add_argument(
        "--backup-drive", action="store_true",
        help="Download Drive files locally via rclone BEFORE any transfer. "
             "Requires rclone configured with a Google Drive remote.")
    backup_grp.add_argument(
        "--backup-email", action="store_true",
        help="Download email locally via GYB WITHOUT restoring to another user. "
             "Requires GYB. Does NOT prevent --no-email migration if both used.")

    # --- Mode flags ---
    mode_grp = parser.add_argument_group("Operation modes")
    mode_grp.add_argument(
        "--no-transfer", action="store_true",
        help="Skip ALL data transfers, forwarding, aliases, calendar, delegates, "
             "and auto-reply. Only runs: kill switch, devices, groups, licences, "
             "backups (if specified), and suspension.")
    mode_grp.add_argument(
        "--scorched-earth", action="store_true",
        help="DANGER: Kill switch, remove groups/licences, suspend, then "
             "permanently DELETE the user. No backups, no transfers. "
             "Requires --doit and --force. You must type the email to confirm.")

    # --- Skip flags ---
    skip_grp = parser.add_argument_group("Skip options")
    skip_grp.add_argument("--no-devices", action="store_true",
                          help="Skip device management")
    skip_grp.add_argument("--no-drive", action="store_true",
                          help="Skip Drive ownership transfer")
    skip_grp.add_argument("--no-email", action="store_true",
                          help="Skip email migration (GYB backup+restore)")
    skip_grp.add_argument("--no-alias", action="store_true",
                          help="Skip alias transfer")
    skip_grp.add_argument("--no-calendar", action="store_true",
                          help="Skip calendar access transfer")
    skip_grp.add_argument("--no-forward", action="store_true",
                          help="Skip email forwarding setup")
    skip_grp.add_argument("--no-auto-reply", action="store_true",
                          help="Skip auto-reply message")
    skip_grp.add_argument("--no-snapshot", action="store_true",
                          help="Skip pre-flight snapshot")
    skip_grp.add_argument("--no-delegates", action="store_true",
                          help="Skip delegate cleanup")
    skip_grp.add_argument("--no-suspend", action="store_true",
                          help="Skip final suspension")
    skip_grp.add_argument("--unsuspend", action="store_true",
                          help="Temporarily unsuspend an already-suspended user to allow "
                               "full offboarding; they will be re-suspended at the end")

    # --- Email migration label handling (mutually exclusive) ---
    label_grp = parser.add_argument_group("Email label options")
    label_mx = label_grp.add_mutually_exclusive_group()
    label_mx.add_argument("--strip-labels", dest="strip_labels", action="store_true", default=None,
                          help="On email restore, discard all original Gmail labels (including "
                               "INBOX) and keep only Migrated/<source-user>. Migrated mail is "
                               "effectively archived under one namespaced label. This is the "
                               "default in --force mode; without --force you are prompted.")
    label_mx.add_argument("--keep-labels", dest="strip_labels", action="store_false",
                          help="Preserve original Gmail labels (INBOX, custom labels) on restore; "
                               "Migrated/<source-user> is added on top.")

    # --- Target flags ---
    target_grp = parser.add_argument_group("Target options")
    target_grp.add_argument("--user", type=str,
                            help="Email of user to offboard")
    target_grp.add_argument("--all-transfer-to", type=str,
                            help="Default destination for ALL transfer phases "
                                 "(Drive, Email, Alias, Calendar, Forward). "
                                 "Overridden per-phase by --drive-to, --email-to, "
                                 "--alias-to, --calendar-to, --forward-to.")
    target_grp.add_argument("--drive-to", type=str,
                            help="Destination for Drive transfer "
                                 "(overrides --all-transfer-to for this phase).")
    target_grp.add_argument("--email-to", type=str,
                            help="Destination for email migration "
                                 "(overrides --all-transfer-to for this phase).")
    target_grp.add_argument("--alias-to", type=str,
                            help="Destination for alias transfer "
                                 "(overrides --all-transfer-to for this phase).")
    target_grp.add_argument("--calendar-to", type=str,
                            help="Destination for calendar access transfer "
                                 "(overrides --all-transfer-to for this phase).")
    target_grp.add_argument("--forward-to", type=str,
                            help="Destination for email forwarding "
                                 "(overrides --all-transfer-to for this phase).")
    target_grp.add_argument("--forward-alias-to", type=str,
                            help="Successor address to surface in the end-of-run "
                                 "MANUAL ACTION block, with admin-console "
                                 "instructions for capturing mail to the "
                                 "offboarded address after suspension/deletion "
                                 "(alias / recipient address map / group). "
                                 "If omitted, falls back to --forward-to then "
                                 "--all-transfer-to. No automated change is made.")
    target_grp.add_argument("--log-dir", type=str,
                            help="Directory for log files")

    args = parser.parse_args()

    # === Flag validation and implications ===

    if args.scorched_earth:
        if not args.doit:
            parser.error("--scorched-earth requires --doit")
        if not args.force:
            parser.error("--scorched-earth requires --force")
        # Override everything: no backups, no transfers, no frills
        args.no_snapshot = True
        args.no_drive = True
        args.no_email = True
        args.no_alias = True
        args.no_calendar = True
        args.no_forward = True
        args.no_delegates = True
        args.no_auto_reply = True
        args.backup_drive = False
        args.backup_email = False

    if args.no_transfer:
        args.no_drive = True
        args.no_email = True
        args.no_alias = True
        args.no_calendar = True
        args.no_forward = True
        args.no_delegates = True
        args.no_auto_reply = True

    return args


###############################################################################
# MAIN EXECUTION [CRITICAL]
###############################################################################

def main():
    global logger, exit_code

    args = parse_args()
    dry_run = not args.doit

    # Get user email before logging so the filename can include it
    user_email = args.user or prompt_email("Enter the email of the user to offboard")

    # Capture start timestamp once so log and snapshot filenames match
    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Setup logging
    log_dir = Path(args.log_dir) if args.log_dir else Path("./logs")
    logger = setup_logging(log_dir, user_email, run_timestamp)

    print_header(f"GOOGLE WORKSPACE OFFBOARDING v{SCRIPT_VERSION}")
    print_info(f"Platform: {sys.platform}")
    print_info(f"Python: {sys.version.split()[0]}")
    print_info(f"Execution mode: {'LIVE' if args.doit else 'DRY RUN'}")
    print_info(f"Interactive: {'No (--force)' if args.force else 'Yes'}")
    print_info(f"Offboarding OU: {OFFBOARDING_OU}")

    # Non-blocking check against the remote VERSION file.
    check_for_updates()

    # Mode announcements
    if args.scorched_earth:
        print_error("MODE: SCORCHED EARTH - User will be DELETED")
    elif args.no_transfer:
        print_info("MODE: No-transfer - No data moves to other users")
    if args.backup_drive:
        print_info("BACKUP: Drive download via rclone enabled")
    if args.backup_email:
        print_info("BACKUP: Email download via GYB enabled (local only)")

    # Log skip flags
    skip_flags = [
        ("--no-devices", args.no_devices),
        ("--no-drive", args.no_drive),
        ("--no-email", args.no_email),
        ("--no-alias", args.no_alias),
        ("--no-calendar", args.no_calendar),
        ("--no-forward", args.no_forward),
        ("--no-auto-reply", args.no_auto_reply),
        ("--no-snapshot", args.no_snapshot),
        ("--no-delegates", args.no_delegates),
        ("--no-suspend", args.no_suspend),
    ]
    for flag, value in skip_flags:
        if value:
            print_warning(f"{flag} enabled")

    # Mode-aware dependency check
    need_gyb = (not args.no_email) or args.backup_email
    need_rclone = args.backup_drive
    if not check_dependencies(need_gyb=need_gyb, need_rclone=need_rclone,
                              user_email=user_email):
        print_error("Dependency check failed. Aborting.")
        sys.exit(2)

    # Verify user exists
    user_info = verify_user(user_email)
    if user_info is None:
        print_error("User verification failed. Aborting.")
        sys.exit(2)

    is_suspended = user_info.get('_is_suspended', 'False') == 'True'
    originally_suspended = is_suspended
    temp_unsuspended = False
    is_2sv_enrolled = user_info.get('2-step enrolled', 'false').lower() == 'true'

    # --- Temporarily unsuspend if requested ---
    if is_suspended and not args.scorched_earth:
        do_unsuspend = args.unsuspend or prompt_yes_no(
            "User is suspended. Temporarily unsuspend to allow full offboarding? "
            "(Will be re-suspended at the end)",
            default=False,
            force=args.force
        )
        if do_unsuspend:
            print_info("Temporarily unsuspending user for offboarding...")
            success, _ = run_gam(
                ["update", "user", user_email, "suspended", "off"],
                dry_run=dry_run
            )
            if success:
                is_suspended = False
                temp_unsuspended = True
                print_success("User unsuspended. Will be re-suspended at the end.")
                summary_action("Temporarily unsuspended for offboarding")
            else:
                print_error("Failed to unsuspend user. Continuing with limited offboarding.")

    # --- Scorched earth confirmation (even with --force, must type email) ---
    if args.scorched_earth and not dry_run:
        print("")
        print_error("=" * 60)
        print_error("  SCORCHED EARTH MODE")
        print_error(f"  User: {user_email}")
        print_error("  This will PERMANENTLY DELETE the user and ALL data.")
        print_error("  No undo after 20-day recovery window.")
        print_error("=" * 60)
        try:
            confirm = input(
                f"{Colours.RED}Type the full email address to confirm: {Colours.RESET}"
            ).strip()
        except EOFError:
            confirm = ""
        if confirm != user_email:
            print_error("Email mismatch. Aborting.")
            sys.exit(2)

    elif not dry_run and not args.force:
        print("")
        print_warning(f"You are about to OFFBOARD: {user_email}")
        print_warning("This will revoke access, scramble password, and optionally suspend.")
        if not prompt_yes_no("Are you sure you want to proceed?"):
            print_info("Aborted by operator.")
            sys.exit(0)

    # Resolve and validate transfer destinations up front so we fail fast
    # before any destructive action if --force is missing destinations.
    dest_map = preflight_destinations(args)

    # =========================================================================
    # PHASE 0: Pre-flight Snapshot
    # =========================================================================
    cached_licences_output: Optional[str] = None
    if args.no_snapshot:
        summary_skip("Pre-flight snapshot (--no-snapshot)")
    else:
        with PhaseTimer("Pre-flight snapshot"):
            try:
                _, cached_licences_output = preflight_snapshot(
                    user_email, dry_run, run_timestamp
                )
            except Exception as e:
                print_error(f"Snapshot phase failed: {e}")
                summary_error(f"Snapshot exception: {e}")

    if shutdown_requested:
        print_summary(dry_run)
        sys.exit(exit_code)

    # =========================================================================
    # PHASE 1: Kill Switch (always runs)
    # =========================================================================
    with PhaseTimer("Kill switch"):
        try:
            execute_kill_switch(user_email, dry_run, is_suspended, is_2sv_enrolled)
        except Exception as e:
            print_error(f"Kill switch phase failed: {e}")
            summary_error(f"Kill switch exception: {e}")

    if shutdown_requested:
        print_summary(dry_run)
        sys.exit(exit_code)

    # =========================================================================
    # SCORCHED EARTH: Short circuit after kill switch
    # =========================================================================
    if args.scorched_earth:
        with PhaseTimer("Group removal"):
            try:
                remove_groups(user_email, dry_run)
            except Exception as e:
                summary_error(f"Group removal: {e}")

        with PhaseTimer("Licence removal"):
            try:
                remove_licences(user_email, dry_run)
            except Exception as e:
                summary_error(f"Licence removal: {e}")

        with PhaseTimer("Suspension"):
            try:
                suspend_user(user_email, dry_run)
            except Exception as e:
                summary_error(f"Suspension: {e}")

        with PhaseTimer("User deletion"):
            try:
                delete_user(user_email, dry_run)
            except Exception as e:
                print_error(f"Deletion failed: {e}")
                summary_error(f"Deletion exception: {e}")

        print_summary(dry_run)
        sys.exit(exit_code)

    # =========================================================================
    # PHASE 2: Device Management
    # =========================================================================
    if args.no_devices:
        summary_skip("Device management (--no-devices)")
    else:
        with PhaseTimer("Device management"):
            try:
                manage_devices(user_email, dry_run)
            except Exception as e:
                print_error(f"Device phase failed: {e}")
                summary_error(f"Device exception: {e}")

    if shutdown_requested:
        print_summary(dry_run)
        sys.exit(exit_code)

    # =========================================================================
    # PHASE 3: Group Removal
    # =========================================================================
    with PhaseTimer("Group removal"):
        try:
            remove_groups(user_email, dry_run)
        except Exception as e:
            print_error(f"Group removal failed: {e}")
            summary_error(f"Group exception: {e}")

    # =========================================================================
    # PHASE 4: Delegate Cleanup
    # =========================================================================
    if args.no_delegates:
        summary_skip("Delegate cleanup (--no-delegates)")
    else:
        with PhaseTimer("Delegate cleanup"):
            try:
                cleanup_delegates(user_email, dry_run)
            except Exception as e:
                print_error(f"Delegate cleanup failed: {e}")
                summary_error(f"Delegate exception: {e}")

    if shutdown_requested:
        print_summary(dry_run)
        sys.exit(exit_code)

    # =========================================================================
    # PHASE 6A: Local Backups (BEFORE any ownership transfers)
    # These run even with --no-transfer so you can archive without moving data.
    # =========================================================================
    if args.backup_drive:
        with PhaseTimer("Drive backup (rclone)"):
            try:
                backup_drive_rclone(user_email, dry_run)
            except Exception as e:
                print_error(f"Drive backup failed: {e}")
                summary_error(f"Drive backup exception: {e}")

    if args.backup_email:
        with PhaseTimer("Email backup (GYB, local only)"):
            try:
                backup_email_only(user_email, dry_run)
            except Exception as e:
                print_error(f"Email backup failed: {e}")
                summary_error(f"Email backup exception: {e}")

    if shutdown_requested:
        print_summary(dry_run)
        sys.exit(exit_code)

    # =========================================================================
    # PHASE 6B: Data Transfers
    # =========================================================================
    print_header("DATA TRANSFER DESTINATIONS")

    # Drive transfer
    if args.no_drive:
        summary_skip("Drive transfer (--no-drive)")
    elif prompt_yes_no("Transfer Drive files to another user?", force=args.force):
        drive_dest = dest_map["drive"] or prompt_email("Drive destination email")
        with PhaseTimer("Drive transfer"):
            try:
                transfer_drive(user_email, drive_dest, dry_run)
            except Exception as e:
                print_error(f"Drive transfer failed: {e}")
                summary_error(f"Drive exception: {e}")
    else:
        summary_skip("Drive transfer (declined)")

    # Email migration
    if args.no_email:
        summary_skip("Email migration (--no-email)")
    elif prompt_yes_no("Migrate email to another user (requires GYB)?", force=args.force):
        email_dest = dest_map["email"] or prompt_email("Email migration destination email")
        # Resolve label-handling mode: CLI flag wins; otherwise prompt (default = strip+archive).
        if args.strip_labels is None:
            strip_labels = prompt_yes_no(
                "Strip original Gmail labels and archive migrated mail under "
                "Migrated/<source-user> only? (No keeps INBOX and custom labels)",
                default=True, force=args.force)
        else:
            strip_labels = args.strip_labels
        with PhaseTimer("Email migration"):
            try:
                migrate_email(user_email, email_dest, dry_run, strip_labels=strip_labels)
            except Exception as e:
                print_error(f"Email migration failed: {e}")
                summary_error(f"Email exception: {e}")
    else:
        summary_skip("Email migration (declined)")

    # Alias transfer
    if args.no_alias:
        summary_skip("Alias transfer (--no-alias)")
    elif prompt_yes_no("Transfer aliases to another user?", force=args.force):
        alias_dest = dest_map["alias"] or prompt_email("Alias destination email")
        with PhaseTimer("Alias transfer"):
            try:
                transfer_aliases(user_email, alias_dest, dry_run)
            except Exception as e:
                print_error(f"Alias transfer failed: {e}")
                summary_error(f"Alias exception: {e}")
    else:
        summary_skip("Alias transfer (declined)")

    # Calendar transfer
    if args.no_calendar:
        summary_skip("Calendar transfer (--no-calendar)")
    elif prompt_yes_no("Grant calendar access to another user?", force=args.force):
        cal_dest = dest_map["calendar"] or prompt_email("Calendar access destination email")
        with PhaseTimer("Calendar transfer"):
            try:
                transfer_calendar(user_email, cal_dest, dry_run)
            except Exception as e:
                print_error(f"Calendar transfer failed: {e}")
                summary_error(f"Calendar exception: {e}")
    else:
        summary_skip("Calendar transfer (declined)")

    if shutdown_requested:
        print_summary(dry_run)
        sys.exit(exit_code)

    # =========================================================================
    # PHASE 7: Email Forwarding
    # =========================================================================
    if args.no_forward:
        summary_skip("Email forwarding (--no-forward)")
    elif prompt_yes_no("Set up email forwarding to a successor?", force=args.force):
        fwd_dest = dest_map["forward"] or prompt_email("Forward emails to")
        with PhaseTimer("Email forwarding"):
            try:
                setup_forwarding(user_email, fwd_dest, dry_run)
            except Exception as e:
                print_error(f"Forwarding setup failed: {e}")
                summary_error(f"Forwarding exception: {e}")
    else:
        summary_skip("Email forwarding (declined)")

    # =========================================================================
    # PHASE 8: Auto-Reply
    # =========================================================================
    if args.no_auto_reply:
        summary_skip("Auto-reply (--no-auto-reply)")
    elif prompt_yes_no("Set an auto-reply message on the account?", force=args.force):
        with PhaseTimer("Auto-reply"):
            try:
                set_auto_reply(user_email, dry_run)
            except Exception as e:
                print_error(f"Auto-reply failed: {e}")
                summary_error(f"Auto-reply exception: {e}")
    else:
        summary_skip("Auto-reply (declined)")

    # =========================================================================
    # PHASE 5: Licence Removal (after all transfers so licence is intact
    # for Drive/Gmail API access during data operations)
    # =========================================================================
    with PhaseTimer("Licence removal"):
        try:
            remove_licences(user_email, dry_run, cached_output=cached_licences_output)
        except Exception as e:
            print_error(f"Licence removal failed: {e}")
            summary_error(f"Licence exception: {e}")

    # =========================================================================
    # PHASE 9: Suspend (always last)
    # =========================================================================
    # If we temporarily unsuspended an already-suspended user at the start of
    # the run, we promised to re-suspend at the end. Honour that contract:
    # skip the prompt and force suspension so the account never ends in a
    # less-restricted state than it started in. --no-suspend still wins, but
    # we make a lot of noise about it.
    if temp_unsuspended:
        if args.no_suspend:
            summary_skip("Suspension (--no-suspend)")
            summary_warning(
                "CONTRACT VIOLATION: User was suspended at start of run, "
                "temporarily unsuspended, and --no-suspend prevented "
                "re-suspension. Account is now ACTIVE — suspend manually "
                "immediately."
            )
            print_error(
                "WARNING: account started suspended and is now ACTIVE due "
                "to --no-suspend. Suspend manually."
            )
        else:
            print_info(
                "Re-suspending: account was suspended at start of run "
                "(temporary unsuspend honoured)."
            )
            with PhaseTimer("Suspension"):
                try:
                    suspend_user(user_email, dry_run)
                    summary_action("Re-suspended (restored original state)")
                except Exception as e:
                    print_error(f"Suspension failed: {e}")
                    summary_error(f"Suspension exception: {e}")
    elif args.no_suspend:
        summary_skip("Suspension (--no-suspend)")
        summary_warning(
            "User was NOT suspended. Remember to suspend manually when "
            "the transition period is over."
        )
    elif prompt_yes_no("Suspend the user account?", default=True, force=args.force):
        with PhaseTimer("Suspension"):
            try:
                suspend_user(user_email, dry_run)
            except Exception as e:
                print_error(f"Suspension failed: {e}")
                summary_error(f"Suspension exception: {e}")
    else:
        summary_skip("Suspension (declined)")

    # =========================================================================
    # Summary
    # =========================================================================
    print_summary(dry_run)

    # End-of-run MANUAL ACTION block for mail capture. GAM cannot configure
    # the "Recipient address map" routing feature, and Gmail user-level
    # forwarding stops once the source account is suspended/deleted — so
    # surface admin-console instructions whenever a successor was specified.
    mail_capture_successor = (
        args.forward_alias_to or args.forward_to or args.all_transfer_to
    )
    if mail_capture_successor:
        print_mail_capture_instructions(user_email, mail_capture_successor)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
