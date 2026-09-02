#!/usr/bin/env python3
"""
Google Workspace Tenant Scoping Audit
=============================================================================
Copyright (c) 2026 Paul Ogier, Outsource House (South Africa)
Website: https://osh.co.za | Email: support@osh.co.za
Training provided by Taming.Tech (https://taming.tech)

Google Workspace GAM7 Course on Udemy   https://taming.tech/GAMCourse
Google Workspace Admin Course on Udemy  https://www.taming.tech/GoogleWorkspaceAdmin
Google Workspace End-User Course on Udemy  https://www.taming.tech/TheCompleteWorkspaceCourse

Credit: after six months of using this script to audit our own clients, Dirk
Grobler's request for help with his tenant-scoping batch script on the
google-apps-manager group inspired us to publish it for the community
(https://groups.google.com/g/google-apps-manager/c/9r_AeuiWOSg).

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
This software is provided "AS IS", without warranty of any kind, express or
implied. The authors (Paul Ogier, Outsource House) and training providers
(Taming.Tech) accept NO RESPONSIBILITY for any damages, data loss, or system
issues that may arise from its use.

YOU ASSUME ALL RISK ASSOCIATED WITH THE USE OF THIS SOFTWARE.
=============================================================================

Author:       Paul Ogier
Created:      2026-08-15
Updated:      2026-09-01
Version:      1.5.0
Status:       Production
Python:       3.9+
Dependencies: GAM ADV X (GAM7) only. Stdlib only on the Python side.

What it does
------------
A READ-ONLY Google Workspace tenant audit. Three stages, each restartable:

  collect -> check -> render

  collect : runs a registry of GAM7 print/report commands, each writing one
            CSV into a timestamped run directory. manifest.json records
            completed modules so a re-run resumes instead of restarting.
  check   : a findings engine reads ONLY the collected CSVs and produces
            findings (severity, plain-English title, what it means,
            remediation, evidence rows).
  render  : a single self-contained HTML report (print stylesheet -> clean
            PDF). Preflight results and any modules that could not run are
            always listed - nothing is silently absent.

Safety posture
--------------
Every GAM command issued is a read (print / report / info / oauth info /
check serviceaccount), with ONE opt-in exception: --grant-temp-access
temporarily adds the auditing admin as organizer on Shared Drives they are
not a member of (GAM's filelist cannot use admin access, so a non-member scan
silently returns zero rows), scans, then removes that access again. Off by
default; without it those drives are reported as UNSCANNED.

Module tiers
------------
  1  tenant-level, cheap (domains, users, groups, admins, shared drive
     metadata, devices, policies, tokens, Vault, reports)
  2  per-user Gmail/Drive/Calendar settings via domain-wide delegation
     (send-as, delegates, forwarding, IMAP/POP, ASPs, backup-code counts,
     mailbox profile, file counts, calendar ACLs)
  3  heavy Drive scans, skippable (external sharing outbound and inbound,
     Shared Drive external exposure, Sites inventory)
  4  off by default, enabled with --full (filters, vacation, browsers,
     contact delegates, alerts, context-aware access levels)
  DNS  per-domain MX/SPF/DKIM/DMARC via the tamingdns.com MCP endpoint,
     with a dns.google fallback when it is unreachable

Example usage:
  python tenant_scope.py --list                      # show the module registry
  python tenant_scope.py --admin admin@example.com   # full default audit
  python tenant_scope.py --admin admin@example.com --only users,groups,dns
  python tenant_scope.py --admin admin@example.com --skip-tier 3
  python tenant_scope.py --admin admin@example.com --run-dir <dir>  # resume
  python tenant_scope.py --admin admin@example.com --full --grant-temp-access
  python tenant_scope.py --render-only --run-dir <dir>  # re-render, no GAM

Notes that matter when reading results:
  - "all users" in GAM iterates ACTIVE users only. By default this audit does
    the same and says so in the report; --include-suspended adds suspended
    users to the per-user modules.
  - Backup verification codes are LIVE codes. The collector keeps only the
    count; the codes themselves are never written to disk.
  - Spam/Trash, suspended-user mail settings and 2-day report lag are stated
    in the report where they apply.

Changelog
  2026-09-01 - v1.5.0 - Tenant-level modules collect four at a time; the
                        tier-3 Drive sweeps and calendar ACLs run as one GAM
                        batch per module instead of one process per user;
                        DNS domains are checked in parallel. A timeout now
                        kills GAM's batch children too, and Ctrl+C lets the
                        running module finish (exit 130). Fixes: the
                        external-forwarding check read a column GAM7 does
                        not emit and could never fire; licence waste fired
                        on every SKU when the licenses module had not run,
                        and summed archived-user seats into the parent SKU;
                        a selection filter that left nobody widened the scan
                        to every mailbox; --render-only without --run-dir
                        rendered an empty "clean" report; the log file
                        carried ANSI codes; a resumed run kept a DNS
                        fallback decided by a blip. App-password check now
                        covers delegated admins; archived accounts no longer
                        count as unenrolled or dormant. Load-tested on a
                        130k-file tenant: 5m51s, no rate-limit retries.
                        148 tests.
  2026-08-15 - v1.3.7 - First public release. Everything from the internal
                        1.x line: external-share findings (named users,
                        whole domains, inbound), people-centric checks
                        (dormancy tiers, mailbox delegation, at-risk
                        composite, offboarding debt), policy checks from
                        the Policy API (password, session length, per-OU
                        2SV, shared-drive defaults, per-service on/off),
                        licence waste, admin-role hygiene. 104 unit tests.
  2026-08-15 - v1.0.0 - Initial release: preflight gates, module registry
                        (tiers 1-4 + DNS), manifest-based resume, findings
                        engine, self-contained HTML report.
"""

import argparse
import csv
import io
import json
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

# `print policies formatjson` puts a whole policy JSON in one cell; the csv
# module's default 128 KB field limit raises mid-check on a large DLP rule.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

###############################################################################
# CONFIGURATION
###############################################################################

SCRIPT_VERSION = "1.5.0"

# [OPTIONAL] Startup check against the remote VERSION file. Fail-silent.
CHECK_FOR_UPDATES = True
UPDATE_CHECK_URL = (
    "https://raw.githubusercontent.com/PaulOgier/GAMScripts/main/"
    "Tenant%20Scoping%20Audit/VERSION"
)

# [IMPORTANT] The GAM command name or full path. If "gam" is not on PATH the
# preflight also tries the macOS installer location (~/bin/gam7/gam - the
# installer writes a shell alias, not a PATH entry, so which() misses it)
# and the conventional Windows path C:\GAM7\gam.exe.
GAM_COMMAND = "gam"
GAM_FALLBACK_PATHS = [
    Path.home() / "bin" / "gam7" / "gam",
    Path(r"C:\GAM7\gam.exe"),
]

# [IMPORTANT] Root directory for audit runs. Each run gets its own
# tenant_audit_<domain>_<timestamp> subfolder. Override with --output-dir.
OUTPUT_DIRECTORY = Path("./tenant_audit_runs")

# [OPTIONAL] DNS checks. Primary path is the tamingdns.com MCP endpoint
# (stateless JSON-RPC POST per check, responses arrive already shaped as
# findings). If it is unreachable the module falls back to dns.google over
# HTTPS with minimal presence checks, and the report says which path ran.
TAMINGDNS_MCP_URL = "https://tamingdns.com/mcp"
DOH_URL = "https://dns.google/resolve"

# Thresholds used by the findings engine.
DORMANT_DAYS = 90            # licensed account with no login for this long
ANYONE_LINK_SCALE = 20       # "anyone with the link" files before it's a finding
EVIDENCE_ROWS = 10           # evidence rows shown per finding in the report
PASSWORD_MIN_LENGTH = 12     # policy minimums below this are flagged
SESSION_MAX_SECONDS = 14 * 86400   # Google's default web session length
LICENCE_WASTE_MIN_GAP = 5    # unused seats before licence waste is flagged
LICENCE_WASTE_MIN_FRACTION = 0.2   # ...and as a share of seats owned
ADMIN_SPRAWL_FRACTION = 0.2  # share of active users holding any admin role
ADMIN_SPRAWL_MIN_USERS = 10  # below this many users, sprawl is not scored

# Rough per-user bytes each tier-2/3 module tends to produce, used only for
# the disk-space preflight estimate. Deliberately generous.
DISK_COST_PER_USER = {2: 20_000, 3: 200_000}

###############################################################################
# COLOURS / CONSOLE
###############################################################################


class Colours:
    """ANSI colour codes; bright variants for dark-background readability."""
    RED = '\033[1;91m'
    GREEN = '\033[1;92m'
    YELLOW = '\033[1;93m'
    BLUE = '\033[1;94m'
    CYAN = '\033[1;96m'
    RESET = '\033[0m'

    @staticmethod
    def strip_colours():
        Colours.RED = Colours.GREEN = Colours.YELLOW = ''
        Colours.BLUE = Colours.CYAN = Colours.RESET = ''


def _enable_windows_ansi() -> bool:
    """Enable ANSI escape processing on the Windows console (Windows 10+)."""
    if os.name != 'nt':
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


if os.name == 'nt':
    if not (os.environ.get('WT_SESSION') or os.environ.get('TERM_PROGRAM')
            or _enable_windows_ansi()):
        Colours.strip_colours()
elif not sys.stdout.isatty():
    Colours.strip_colours()


def _force_utf8_console():
    """Keep non-ASCII file/user names from killing console logging on
    Windows, where the streams default to the ANSI code page."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


###############################################################################
# LOGGING / DISPLAY
###############################################################################

logger: Optional[logging.Logger] = None
shutdown_requested = False


def signal_handler(_signum, _frame):
    global shutdown_requested
    if shutdown_requested:
        print(f"\n{Colours.RED}Forced exit.{Colours.RESET}")
        with _live_procs_lock:
            for proc in list(_live_procs):
                _kill_tree(proc)
        sys.exit(2)
    shutdown_requested = True
    print(f"\n{Colours.YELLOW}[WARN] Ctrl+C received. Finishing the current "
          f"module, then stopping. The run directory can be resumed with "
          f"--run-dir. Press Ctrl+C again to force quit.{Colours.RESET}")


signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, signal_handler)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class _PlainFormatter(logging.Formatter):
    """The console gets colour; the log file must not (every line would
    otherwise carry escape codes on a tty run)."""

    def format(self, record):
        return _ANSI_RE.sub("", super().format(record))


def setup_logging(run_dir: Path):
    global logger
    _force_utf8_console()
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    file_handler = logging.FileHandler(run_dir / "tenant_scope.log",
                                       encoding="utf-8")
    file_handler.setFormatter(_PlainFormatter(fmt))
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(fmt))
    # force=True: a second call in one process (main() is callable) would
    # otherwise be a silent no-op and log into the previous run directory.
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console],
                        force=True)
    logger = logging.getLogger(__name__)
    return logger


def _emit(level: str, text: str):
    if logger is None:
        print(text)
    elif level == 'error':
        logger.error(text)
    elif level == 'warning':
        logger.warning(text)
    else:
        logger.info(text)


def print_header(title: str):
    _emit('info', "")
    _emit('info', f"{Colours.BLUE}{'=' * 60}")
    _emit('info', f"  {title}")
    _emit('info', f"{'=' * 60}{Colours.RESET}")


def print_success(msg: str):
    _emit('info', f"{Colours.GREEN}[OK] {msg}{Colours.RESET}")


def print_warning(msg: str):
    _emit('warning', f"{Colours.YELLOW}[WARN] {msg}{Colours.RESET}")


def print_error(msg: str):
    _emit('error', f"{Colours.RED}[ERROR] {msg}{Colours.RESET}")


def print_info(msg: str):
    _emit('info', f"{Colours.CYAN}[INFO] {msg}{Colours.RESET}")


def check_for_updates():
    """Warn if a newer version exists. Any failure is swallowed."""
    if not CHECK_FOR_UPDATES:
        return
    try:
        req = urllib.request.Request(
            UPDATE_CHECK_URL, headers={"User-Agent": "tenant_scope.py"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            remote = resp.read().decode("utf-8", errors="replace").strip().splitlines()[0].strip()
        local_t = tuple(int(p) for p in SCRIPT_VERSION.split("."))
        remote_t = tuple(int(re.sub(r"\D", "", p) or 0) for p in remote.split("."))
        if remote_t > local_t:
            print_warning(f"A newer version is available: v{remote} "
                          f"(you are running v{SCRIPT_VERSION}) - "
                          f"https://github.com/PaulOgier/GAMScripts/releases")
    except Exception:
        pass


###############################################################################
# GAM EXECUTION
###############################################################################

GAM_PATH = GAM_COMMAND  # resolved in preflight

# GAM processes currently running, so a forced exit can take their batch
# children with them.
_live_procs: set = set()
_live_procs_lock = threading.Lock()


def _popen_isolated(cmd, **kwargs) -> subprocess.Popen:
    """Start GAM in its own process group / session.

    Two reasons. Ctrl+C in the terminal goes to the whole foreground group,
    so without this the GAM child died at the same moment the handler
    promised to "finish the current module". And a timeout kill has to reach
    GAM's batch children, which needs a group to signal.
    """
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _kill_tree(proc: subprocess.Popen):
    """Kill a GAM process and its batch children.

    proc.kill() reaches the parent only; with auto_batch_min the children are
    separate processes that keep writing the redirect CSV after the parent is
    gone, so the row count recorded and the file on disk would diverge.
    """
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def locate_gam() -> Optional[str]:
    """Find the gam binary: PATH first, then known installer locations."""
    found = shutil.which(GAM_COMMAND)
    if found:
        return found
    for candidate in GAM_FALLBACK_PATHS:
        if candidate.is_file():
            return str(candidate)
    return None


PROGRESS_EVERY = 30   # seconds between GAM progress lines echoed to the console


def _echo_progress(pipe, collected: List[str]):
    """Keep every stderr line, echo one every PROGRESS_EVERY seconds.

    A Shared Drive scan can run for hours with nothing on screen, which reads
    as a hang. GAM's own counters are the honest progress signal, so show
    them - throttled, and only once a command has been running long enough
    that silence would worry someone.
    """
    last = time.time()
    for line in pipe:
        collected.append(line)
        now = time.time()
        if line.strip() and now - last >= PROGRESS_EVERY:
            last = now
            _emit('info', "    " + line.strip()[:120])
    pipe.close()


def run_gam(args: List[str], timeout: int = 900,
            dry_run: bool = False) -> Tuple[int, str, str]:
    """Run one GAM command, shell=False, returning (rc, stdout, stderr).

    stdout is the clean CSV/report payload; every GAM progress line
    ("Getting all...", per-user counters) goes to stderr. Callers must keep
    the two apart - mixing them corrupts the CSVs.
    """
    cmd = [GAM_PATH] + args
    if dry_run:
        print_info("DRY RUN: " + " ".join(cmd))
        return 0, "", ""
    _emit('info', "Running: " + " ".join(cmd))
    try:
        # stdout goes to a temp file rather than a pipe: a large Drive scan
        # can outrun a pipe buffer, and a file survives the kill on timeout so
        # partial results are still returned. stderr is read live so GAM's
        # "Got N files..." counters reach the console during a long scan.
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8",
                                    errors="replace") as out_fh:
            proc = _popen_isolated(
                cmd, stdout=out_fh, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace")
            with _live_procs_lock:
                _live_procs.add(proc)
            collected: List[str] = []
            reader = threading.Thread(target=_echo_progress,
                                      args=(proc.stderr, collected),
                                      daemon=True)
            reader.start()
            timed_out = False
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                rc, timed_out = -1, True
                proc.wait()
            finally:
                with _live_procs_lock:
                    _live_procs.discard(proc)
            reader.join(timeout=5)
            out_fh.seek(0)
            out = out_fh.read()
        err = "".join(collected)
        if timed_out:
            err = (err + f"\nTimed out after {timeout}s").strip()
        return rc, out, err
    except FileNotFoundError:
        return -2, "", f"GAM not found at {GAM_PATH}"
    except Exception as exc:  # keep one module failure from killing the run
        return -3, "", f"{type(exc).__name__}: {exc}"


def is_header_only(text: str) -> bool:
    """True when GAM emitted at most a CSV header (an empty result set)."""
    return len([ln for ln in text.strip().splitlines() if ln.strip()]) <= 1


def csv_data_rows(source) -> int:
    """Number of data rows in a CSV (a Path or the text itself).

    Counted through the csv reader, not by lines: vacation messages and
    filter criteria carry newlines inside a cell, and a line count reports
    more rows than there are. Streams a file, so a redirect CSV of hundreds
    of MB is never held in memory.
    """
    def count(fh):
        return max(0, sum(1 for row in csv.reader(fh) if row) - 1)
    if isinstance(source, Path):
        with open(source, newline="", encoding="utf-8",
                  errors="replace") as fh:
            return count(fh)
    return count(io.StringIO(source))


###############################################################################
# CSV HELPERS
###############################################################################

def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def col(row: Dict[str, str], *names: str) -> str:
    """Case-insensitive column lookup, first match wins.

    GAM header casing follows the underlying API field names and has shifted
    between versions; matching by lowercase name keeps the checks engine
    working across that.
    """
    # Exact-key fast path first: every check calls this several times per
    # row, and rebuilding the lowered dict was the only measurable CPU cost
    # in the checks stage on a large file-share CSV.
    for name in names:
        if name in row:
            return (row[name] or "").strip()
    lowered = {k.lower().strip(): v for k, v in row.items() if k}
    for name in names:
        if name.lower() in lowered:
            return (lowered[name.lower()] or "").strip()
    return ""


def truthy(value: str) -> bool:
    return value.strip().lower() in ("true", "yes", "1", "enabled")


def email_domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower().strip() if "@" in address else ""


def write_rows(path: Path, rows: List[Dict[str, str]]):
    """Write dict rows with the union of all headers (per-user modules like
    filecounts have data-dependent columns that differ between users)."""
    headers: List[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, restval="")
        writer.writeheader()
        writer.writerows(rows)


###############################################################################
# MODULE REGISTRY
###############################################################################

# DWD scope URLs per module family. Client-auth (Directory/Reports API)
# modules are not scope-gated here: a standard GAM install authorises all of
# them, and a missing one fails loudly at collect time and lands on the
# "not checked" list anyway.
SCOPE_GMAIL_BASIC = "https://www.googleapis.com/auth/gmail.settings.basic"
SCOPE_GMAIL_SHARING = "https://www.googleapis.com/auth/gmail.settings.sharing"
# users.getProfile accepts any of mail.google.com / gmail.modify /
# gmail.readonly / gmail.metadata. GAM's standard DWD set grants gmail.modify
# (verified PASS on dev 2026-08-15; gmail.readonly FAILed there), so gate on
# that rather than readonly.
SCOPE_GMAIL_MODIFY = "https://www.googleapis.com/auth/gmail.modify"
SCOPE_DRIVE = "https://www.googleapis.com/auth/drive"
SCOPE_CALENDAR = "https://www.googleapis.com/auth/calendar"

# Registry entry keys:
#   key, title, tier, args (list, or None for special collectors),
#   collector ("simple" | "per_user" | "mydrive_external" | "sd_external" |
#              "swm_external" | "sites" | "dns" | "backupcodes"),
#   scopes (DWD URLs to verify before running), timeout, size_risk.
MODULES: List[Dict] = [
    # ---- Tier 1: tenant level ----
    dict(key="domains", title="Domains (incl. aliases)", tier=1,
         args=["print", "domains"]),
    dict(key="domainaliases", title="Domain aliases", tier=1,
         args=["print", "domainaliases"]),
    dict(key="orgs", title="Organisational units", tier=1,
         args=["print", "orgs"]),
    dict(key="ou_counts", title="User counts by OU", tier=1,
         args=["print", "usercountsbyorgunit"]),
    dict(key="licenses", title="Licence assignments", tier=1,
         args=["print", "licenses"]),
    dict(key="users", title="Users (security fields + licences)", tier=1,
         args=["print", "users", "fields",
               "primaryEmail,suspended,archived,lastLoginTime,fullname,"
               "orgUnitPath,creationTime,isenrolledin2sv,isenforcedin2sv,"
               "recoveryemail,recoveryphone,isadmin,isdelegatedadmin",
               "licenses"]),
    dict(key="admins", title="Admin role assignments", tier=1,
         args=["print", "admins"]),
    dict(key="adminroles", title="Admin roles", tier=1,
         args=["print", "adminroles"]),
    dict(key="schema", title="Custom user schemas", tier=1,
         args=["print", "schema"]),
    dict(key="groups", title="Groups + settings", tier=1,
         args=["print", "groups", "fields", "email,name,directmemberscount",
               "settings"]),
    dict(key="group_members", title="Group members", tier=1,
         args=["print", "group-members", "fields", "role,type,email,status"]),
    dict(key="resources", title="Calendar resources", tier=1,
         args=["print", "resources", "allfields"]),
    dict(key="buildings", title="Buildings", tier=1,
         args=["print", "buildings"]),
    dict(key="features", title="Resource features", tier=1,
         args=["print", "features"]),
    dict(key="shareddrives", title="Shared Drives (admin view)", tier=1,
         args=["print", "shareddrives", "adminaccess"]),
    dict(key="shareddriveacls", title="Shared Drive ACLs", tier=1,
         args=["print", "shareddriveacls", "oneitemperrow"]),
    dict(key="shareddriveorganizers", title="Shared Drive organizers", tier=1,
         args=["print", "shareddriveorganizers"]),
    dict(key="mobile", title="Mobile devices", tier=1,
         args=["print", "mobile"]),
    dict(key="cros", title="ChromeOS devices", tier=1,
         args=["print", "cros"]),
    dict(key="ssoprofiles", title="Inbound SSO profiles", tier=1,
         args=["print", "inboundssoprofiles"]),
    dict(key="ssoassignments", title="Inbound SSO assignments", tier=1,
         args=["print", "inboundssoassignments"]),
    dict(key="datatransfers", title="Data transfers", tier=1,
         args=["print", "datatransfers"]),
    dict(key="userinvitations", title="Unmanaged-account invitations", tier=1,
         args=["print", "userinvitations"]),
    dict(key="vaultmatters", title="Vault matters", tier=1,
         args=["print", "vaultmatters"]),
    dict(key="vaultholds", title="Vault holds", tier=1,
         args=["print", "vaultholds"]),
    dict(key="vaultexports", title="Vault exports", tier=1,
         args=["print", "vaultexports"]),
    dict(key="report_customers", title="Customer usage report", tier=1,
         args=["report", "customers"]),
    dict(key="report_users", title="Per-user usage report (~2-day lag)",
         tier=1, args=["report", "users"], timeout=1800),
    dict(key="policies", title="Tenant policies (formatjson)", tier=1,
         args=["print", "policies", "formatjson"]),
    dict(key="tokens", title="OAuth tokens (all users)", tier=1,
         args=["all", "users", "print", "tokens"], timeout=1800),
    # ---- Tier 2: per-user via DWD ----
    dict(key="sendas", title="Send-as addresses", tier=2,
         args=["all", "users", "print", "sendas", "compact"],
         scopes=[SCOPE_GMAIL_BASIC]),
    dict(key="delegates", title="Mailbox delegates", tier=2,
         args=["all", "users", "print", "delegates"],
         scopes=[SCOPE_GMAIL_SHARING]),
    dict(key="forwards", title="Mail forwarding", tier=2,
         args=["all", "users", "print", "forwards"],
         scopes=[SCOPE_GMAIL_SHARING]),
    dict(key="forwardingaddresses", title="Forwarding addresses", tier=2,
         args=["all", "users", "print", "forwardingaddresses"],
         scopes=[SCOPE_GMAIL_SHARING]),
    dict(key="imap", title="IMAP settings", tier=2,
         args=["all", "users", "print", "imap"],
         scopes=[SCOPE_GMAIL_BASIC]),
    dict(key="pop", title="POP settings", tier=2,
         args=["all", "users", "print", "pop"],
         scopes=[SCOPE_GMAIL_BASIC]),
    dict(key="asps", title="App-specific passwords", tier=2,
         args=["all", "users", "print", "asps"]),
    dict(key="backupcodes", title="Backup verification codes (count only)",
         tier=2, args=["all", "users", "print", "backupcodes"],
         collector="backupcodes"),
    dict(key="gmailprofile", title="Gmail profiles (mailbox sizing)", tier=2,
         args=["all", "users", "print", "gmailprofile"],
         scopes=[SCOPE_GMAIL_MODIFY]),
    dict(key="filecounts", title="Drive file counts", tier=2,
         args=["all", "users", "print", "filecounts"],
         scopes=[SCOPE_DRIVE], timeout=3600),
    dict(key="calendaracls", title="Primary calendar ACLs", tier=2,
         args=["all", "users", "print", "calendaracls", "primary"],
         scopes=[SCOPE_CALENDAR]),
    # ---- Tier 3: heavy Drive scans ----
    dict(key="mydrive_external", title="My Drive files shared externally",
         tier=3, args=None, collector="mydrive_external",
         scopes=[SCOPE_DRIVE], timeout=3600),
    # Applied per drive, not per module. 3600s killed a single large drive
    # mid-scan on a 660GB drive (2026-08-17) and lost every row for it.
    dict(key="shareddrive_external",
         title="Shared Drive files shared externally", tier=3,
         args=None, collector="sd_external",
         scopes=[SCOPE_DRIVE], timeout=14400),
    dict(key="sharedwithme_external",
         title="Files shared in from outside (inbound)", tier=3,
         args=None, collector="swm_external",
         scopes=[SCOPE_DRIVE], timeout=3600),
    dict(key="sites", title="Google Sites inventory", tier=3,
         args=None, collector="sites", scopes=[SCOPE_DRIVE], timeout=3600),
    # ---- Tier 4: off by default (--full) ----
    dict(key="filters", title="Gmail filters", tier=4,
         args=["all", "users", "print", "filters"],
         scopes=[SCOPE_GMAIL_BASIC], timeout=3600),
    dict(key="vacation", title="Vacation responders", tier=4,
         args=["all", "users", "print", "vacation"],
         scopes=[SCOPE_GMAIL_BASIC], timeout=3600),
    dict(key="browsers", title="Managed browsers", tier=4,
         args=["print", "browsers"]),
    dict(key="alerts", title="Alert Center alerts", tier=4,
         args=["print", "alerts"]),
    dict(key="caalevels", title="Context-aware access levels", tier=4,
         args=["print", "caalevels"]),
    # ---- DNS ----
    dict(key="dns", title="Mail DNS (MX/SPF/DKIM/DMARC)", tier=1,
         args=None, collector="dns"),
]

# print caalevels without a GCP-org role grant fails with this text; that is
# an authorisation gap, not a script failure.
CAALEVELS_AUTH_ERROR = "Access Context Manager"

# An `all users` print exits non-zero when ANY user fails; these stderr
# markers mean individual users were skipped (no Gmail licence, service off),
# not that the module itself broke. Seen live on dev: a Gmail-disabled user
# turned every Gmail-settings module into "exit 73" while the remaining
# users' data was fine.
PER_USER_SKIP_MARKERS = (
    "Service/App not enabled",
    "Service not applicable",
    "Does not exist",
)

# print browsers without Chrome browser management access fails 403.
BROWSERS_AUTH_ERROR = "Forbidden"

MODULE_BY_KEY = {m["key"]: m for m in MODULES}

# The external-share pm recipe. `pm not domain "d1,d2"` is WRONG (domain
# takes a single regex; a comma list matches nothing and `not` then matches
# every ACL) - hence notdomainlist throughout.
def external_pm_args(internal_domains: List[str]) -> List[str]:
    doms = ",".join(sorted(internal_domains))
    return ["pm", "typelist", "user,group", "notrole", "owner",
            "notdomainlist", doms, "em",
            "pm", "type", "domain", "notdomainlist", doms, "em",
            "pm", "type", "anyone", "em",
            "pmfilter", "oneitemperrow"]


###############################################################################
# RUN CONTEXT / MANIFEST
###############################################################################

class RunContext:
    """Everything the collect/check/render stages share for one run."""

    def __init__(self, run_dir: Path, args):
        self.run_dir = run_dir
        self.args = args
        self.manifest_path = run_dir / "manifest.json"
        self.manifest: Dict = {"modules": {}, "preflight": [], "meta": {}}
        if self.manifest_path.is_file():
            try:
                self.manifest = json.loads(
                    self.manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print_warning("manifest.json unreadable; starting a fresh one")
        self.internal_domains: List[str] = self.manifest["meta"].get(
            "internal_domains", [])
        self.admin: str = args.admin or self.manifest["meta"].get("admin", "")
        self.failed_scopes: List[str] = []
        self._rows_cache: Dict[str, List[Dict[str, str]]] = {}
        self._policy_cache: Optional[List[Dict]] = None
        self._log_lock = threading.Lock()

    def save(self):
        self.manifest["meta"]["internal_domains"] = self.internal_domains
        self.manifest["meta"]["admin"] = self.admin
        self.manifest_path.write_text(
            json.dumps(self.manifest, indent=2), encoding="utf-8")

    def module_status(self, key: str) -> str:
        return self.manifest["modules"].get(key, {}).get("status", "")

    def set_module(self, key: str, status: str, rows: int = 0, note: str = ""):
        self._rows_cache.pop(key, None)
        if key == "policies":
            self._policy_cache = None
        self.manifest["modules"][key] = {
            "status": status, "rows": rows, "note": note,
            "completed_at": datetime.now().isoformat(timespec="seconds")}
        self.save()

    def csv_path(self, key: str) -> Path:
        return self.run_dir / f"{key}.csv"

    def rows(self, key: str) -> List[Dict[str, str]]:
        """Parsed rows for a module, cached.

        The checks engine reads users.csv 13 times and policies.csv 5 times in
        one pass. Harmless on a 37-user tenant; on a few thousand users the
        heavy CSVs run to hundreds of MB and every re-read is a silent stall.
        set_module drops the entry, so a module collected after its file was
        read never serves a stale one.
        """
        if key not in self._rows_cache:
            self._rows_cache[key] = read_csv_rows(self.csv_path(key))
        return self._rows_cache[key]

    def stderr_log(self, key: str, text: str):
        """GAM progress output goes to a side log, keeping the console and
        the CSVs clean while preserving the full trail."""
        if not text.strip():
            return
        # Tier-1 modules collect in parallel; the lock keeps one module's
        # block from landing inside another's.
        with self._log_lock, open(self.run_dir / "gam_stderr.log", "a",
                                  encoding="utf-8") as fh:
            fh.write(f"\n===== {key} =====\n{text.strip()}\n")


###############################################################################
# PREFLIGHT
###############################################################################

def https_reachable(host: str, timeout: int = 5) -> bool:
    try:
        req = urllib.request.Request(f"https://{host}/", method="HEAD",
                                     headers={"User-Agent": "tenant_scope.py"})
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # got an HTTP response; the network path works
    except (urllib.error.URLError, socket.timeout, OSError):
        return False


def parse_info_domain(output: str) -> Dict[str, str]:
    """Pull Primary Domain and Customer ID out of `gam info domain`."""
    info = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key == "primary domain":
            info["primary_domain"] = value.strip()
        elif key == "customer id":
            info["customer_id"] = value.strip()
    return info


def parse_serviceaccount_check(output: str) -> Tuple[List[str], List[str]]:
    """Parse per-scope PASS/FAIL lines from `check serviceaccount scopes`.

    Returns (passed_scope_urls, failed_scope_urls). The command prints one
    line per tested scope containing the URL and PASS or FAIL, then
    "All scopes PASSED!" on full success.
    """
    passed, failed = [], []
    for line in output.splitlines():
        match = re.search(r"(https://\S+)", line)
        if not match:
            continue
        url = match.group(1).rstrip(",")
        # Anchor on the ", PASS" / ", FAIL" cell, not any word starting with
        # FAIL: a future "... FAILED to open" hint line would otherwise skip
        # a module.
        if re.search(r",\s*FAIL\b", line):
            failed.append(url)
        elif re.search(r",\s*PASS\b", line):
            passed.append(url)
    return passed, failed


def selected_modules(args) -> List[Dict]:
    """Apply --only / --skip / tier selection to the registry."""
    only = [k.strip() for k in (args.only or "").split(",") if k.strip()]
    skip = [k.strip() for k in (args.skip or "").split(",") if k.strip()]
    skip_tiers = set(args.skip_tier or [])
    for key in only + skip:
        if key not in MODULE_BY_KEY:
            print_error(f"Unknown module key: {key} (see --list)")
            sys.exit(2)
    chosen = []
    for mod in MODULES:
        if only:
            if mod["key"] in only:
                chosen.append(mod)
            continue
        if mod["key"] in skip:
            continue
        if mod["tier"] in skip_tiers:
            continue
        if mod["tier"] == 4 and not args.full:
            continue
        if mod["key"] == "dns" and args.no_dns:
            continue
        chosen.append(mod)
    return chosen


def preflight(ctx: RunContext, modules: List[Dict]) -> bool:
    """Gates 1-3 are hard stops; 4-5 degrade with a clear consequence.

    Everything lands in a check/result/consequence table that opens the run
    log and reappears in the report appendix.
    """
    global GAM_PATH
    args = ctx.args
    table: List[Tuple[str, str, str]] = []
    ok = True

    # Gate 1: GAM present and running.
    located = locate_gam()
    if not located:
        table.append(("GAM7 binary", "NOT FOUND",
                      "Install GAM7 or set GAM_COMMAND; run aborted"))
        ok = False
    else:
        GAM_PATH = located
        rc, out, err = run_gam(["version"], timeout=60)
        first = (out or err).strip().splitlines()[0] if (out or err).strip() else ""
        if rc == 0:
            table.append(("GAM7 binary", f"{located} ({first})", "-"))
        else:
            table.append(("GAM7 binary", f"{located} but `gam version` failed",
                          "Run aborted"))
            ok = False

    # Gate 2: internet.
    if ok:
        if https_reachable("www.googleapis.com"):
            table.append(("Internet (www.googleapis.com)", "reachable", "-"))
        else:
            table.append(("Internet (www.googleapis.com)", "UNREACHABLE",
                          "Run aborted"))
            ok = False
    dns_selected = any(m["key"] == "dns" for m in modules)
    if ok and dns_selected:
        reachable = https_reachable("tamingdns.com")
        if reachable:
            table.append(("DNS checker (tamingdns.com)", "reachable", "-"))
        else:
            table.append(("DNS checker (tamingdns.com)", "unreachable",
                          "DNS module falls back to dns.google (minimal checks)"))
        # Written on both branches: a resumed run must not inherit a fallback
        # decided by a network blip on the first attempt.
        ctx.manifest["meta"]["dns_fallback"] = not reachable

    # Gate 3: which tenant is this? Wrong-tenant audit is the worst silent
    # failure, and no per-tenant guard exists - so echo and confirm.
    if ok:
        rc, out, err = run_gam(["info", "domain"], timeout=120)
        if rc != 0:
            table.append(("Tenant identity (gam info domain)", "FAILED",
                          "Run aborted"))
            ctx.stderr_log("preflight", err)
            ok = False
        else:
            info = parse_info_domain(out)
            # The raw output also carries per-SKU seat counts; keep it for
            # the licence-waste check (a second call would be pure waste).
            (ctx.run_dir / "domaininfo.txt").write_text(out, encoding="utf-8")
            domain = info.get("primary_domain", "?")
            customer = info.get("customer_id", "?")
            ctx.manifest["meta"]["primary_domain"] = domain
            ctx.manifest["meta"]["customer_id"] = customer
            table.append(("Tenant", f"{domain} (customer {customer})",
                          "Confirmed by operator" if not args.yes
                          else "Confirmed via --yes"))
            print_header("TENANT CONFIRMATION")
            print_info(f"Primary domain : {domain}")
            print_info(f"Customer ID    : {customer}")
            if not args.yes:
                try:
                    answer = input("Audit THIS tenant? [y/N]: ").strip().lower()
                except EOFError:
                    # No console to answer with: a cron job, a pipe, an ssh
                    # command with no tty. Refuse rather than assume yes.
                    print_error("No console to confirm the tenant on. Re-run "
                                "with --yes once the domain above is the one "
                                "you meant to audit.")
                    return False
                if answer not in ("y", "yes"):
                    print_error("Tenant not confirmed; nothing was collected.")
                    return False

    # Gate 4 (degrade): authorisation for the DWD modules actually selected.
    if ok:
        rc, out, err = run_gam(["oauth", "info"], timeout=120)
        if rc == 0:
            granted = len(re.findall(r"https://", out))
            table.append(("Client OAuth (gam oauth info)",
                          f"{granted} scopes granted", "-"))
        else:
            table.append(("Client OAuth (gam oauth info)", "FAILED",
                          "Tenant-level modules may fail; each failure is "
                          "reported per module"))
            ctx.stderr_log("preflight", err)

        needed = sorted({s for m in modules for s in m.get("scopes", [])})
        if needed and ctx.admin:
            rc, out, err = run_gam(
                ["user", ctx.admin, "check", "serviceaccount", "scopes",
                 ",".join(needed)], timeout=300)
            combined = out + "\n" + err
            passed, failed = parse_serviceaccount_check(combined)
            ctx.failed_scopes = failed
            if failed:
                affected = sorted({m["key"] for m in modules
                                   if set(m.get("scopes", [])) & set(failed)})
                table.append(("Service account DWD scopes",
                              f"{len(failed)} scope(s) FAILED",
                              "Modules skipped (not authorised): "
                              + ", ".join(affected)))
                print_warning("DWD scopes missing. GAM printed the client ID "
                              "and Admin console path to authorise; see the "
                              "run log.")
                ctx.stderr_log("preflight_dwd", combined)
            else:
                table.append(("Service account DWD scopes",
                              f"all {len(needed)} required scopes PASS", "-"))
        elif needed:
            table.append(("Service account DWD scopes",
                          "NOT CHECKED (--admin not given)",
                          "Per-user modules will be attempted unverified"))

    # Gate 5 (degrade): output location sanity + disk estimate.
    if ok:
        try:
            probe = ctx.run_dir / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            table.append(("Output directory writable", str(ctx.run_dir), "-"))
        except OSError as exc:
            table.append(("Output directory writable", f"NO ({exc})",
                          "Run aborted"))
            ok = False
        synced_markers = ("icloud", "mobile documents", "dropbox",
                          "google drive", "onedrive", "cloudstorage")
        lowered = str(ctx.run_dir).lower()
        if any(marker in lowered for marker in synced_markers):
            table.append(("Cloud-synced output path", "LIKELY",
                          "Large CSVs will churn the sync client; consider "
                          "--output-dir on a local disk"))
        user_count = ctx.manifest["meta"].get("user_count", 0)
        if not user_count:
            # Order-of-magnitude only; refined after the users module runs.
            user_count = 100
        estimate = sum(DISK_COST_PER_USER.get(m["tier"], 0) * user_count
                       for m in modules)
        try:
            free = shutil.disk_usage(ctx.run_dir).free
            verdict = "-"
            if estimate > free:
                verdict = "Estimated output exceeds free space; run aborted"
                ok = False
            table.append(("Disk space",
                          f"~{estimate // 1_000_000} MB estimated, "
                          f"{free // 1_000_000} MB free", verdict))
        except OSError:
            table.append(("Disk space", "could not measure", "-"))

    ctx.manifest["preflight"] = [list(row) for row in table]
    ctx.save()

    print_header("PREFLIGHT")
    width = max(len(row[0]) for row in table) + 2
    for check, result, consequence in table:
        line = f"{check:<{width}} {result}"
        if consequence and consequence != "-":
            line += f"  -> {consequence}"
        _emit('info', line)
    return ok


###############################################################################
# COLLECT
###############################################################################

def active_users(ctx: RunContext) -> List[str]:
    rows = ctx.rows("users")
    return [col(r, "primaryEmail") for r in rows
            if col(r, "primaryEmail") and not truthy(col(r, "suspended"))]


def suspended_users(ctx: RunContext) -> List[str]:
    rows = ctx.rows("users")
    return [col(r, "primaryEmail") for r in rows
            if col(r, "primaryEmail") and truthy(col(r, "suspended"))]


def audited_users(ctx: RunContext) -> List[str]:
    users = active_users(ctx)
    if ctx.args.include_suspended:
        users += suspended_users(ctx)
    return users


PER_USER_TIMEOUT_SECONDS = 10   # per mailbox, for whole-tenant `all users` scans


def module_timeout(ctx: RunContext, mod: Dict, default: int) -> int:
    """Module timeout, scaled by tenant size for whole-tenant scans.

    `gam all users print ...` walks every mailbox inside one process, so a
    flat 900s is ample at 40 users and kills the module outright on a larger
    tenant - losing every row, not just the slow ones (reported by Kim
    Nilsson, 2026-08-17). A timeout is a ceiling, not a budget: raising it
    costs nothing on a tenant that finishes early.
    """
    base = mod.get("timeout", default)
    args = mod.get("args") or []
    if [a.lower() for a in args[:2]] != ["all", "users"]:
        return base
    users = ctx.manifest["meta"].get("user_count", 0)
    return max(base, users * PER_USER_TIMEOUT_SECONDS)


AUTO_BATCH_MIN = 10   # users in one command before GAM forks it into a batch
SCAN_THREADS = 20     # GAM processes per batch; gam.cfg default is 5
NEVER_LOGGED_IN = ("", "never", "1970-01-01t00:00:00.000z")


def scan_user_list(ctx: RunContext) -> Optional[Path]:
    """Write the mailbox list for the per-user scans, or None to use `all users`.

    Returns None when users.csv has not been collected yet, so a lone
    `--only sendas` still works.
    """
    if not ctx.rows("users"):
        return None
    wanted = set(audited_users(ctx))
    emails = []
    skipped_never = 0
    for row in ctx.rows("users"):
        email = col(row, "primaryEmail")
        if email not in wanted:
            continue
        last = col(row, "lastLoginTime").strip().lower()
        if ctx.args.skip_never_logged_in and last[:24] in NEVER_LOGGED_IN:
            skipped_never += 1
            continue
        emails.append(email)
    if not emails:
        # Not None: None means "use `all users`", which would scan every
        # mailbox in the tenant - the opposite of what the filters asked.
        raise LookupError("no users left to scan after the selection filters")
    path = ctx.run_dir / "_scan_users.csv"
    write_rows(path, [{"primaryEmail": e} for e in emails])
    ctx.manifest["meta"]["scanned_users"] = len(emails)
    ctx.manifest["meta"]["skipped_never_logged_in"] = skipped_never
    return path


def user_scan_args(ctx: RunContext, mod: Dict) -> Tuple[List[str], Optional[Path]]:
    """Rewrite an `all users` command into a parallel batch over a user list.

    Three changes, all needed together:
      - `csvfile <list>:primaryEmail` replaces `all users`, so the scan covers
        the accounts we chose rather than every mailbox in the tenant.
      - `config auto_batch_min/num_threads` makes GAM fork the scan. Left at
        the gam.cfg defaults (0 and 5) a multi-user print runs sequentially in
        one process: 3000 mailboxes at ~0.9s each is 45 minutes.
      - `redirect csv <file> multiprocess` collects the children's output.
        Without `multiprocess` the parent redirect does not follow the forks
        and the file comes back empty; without the redirect at all, a timeout
        throws away every row collected so far.

    The redirect path must be absolute - GAM resolves a relative one against
    drive_dir, not the working directory.
    """
    args = list(mod["args"])
    if [a.lower() for a in args[:2]] != ["all", "users"]:
        return args, None
    listing = scan_user_list(ctx)
    if listing is None:
        return args, None
    out_path = ctx.csv_path(mod["key"]).resolve()
    return (["config", "auto_batch_min", str(AUTO_BATCH_MIN),
             "num_threads", str(SCAN_THREADS),
             "redirect", "csv", str(out_path), "multiprocess",
             "csvfile", f"{listing.resolve()}:primaryEmail"] + args[2:],
            out_path)


def collect_simple(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    try:
        args, out_path = user_scan_args(ctx, mod)
    except LookupError as exc:
        return "skipped", 0, str(exc)
    rc, out, err = run_gam(args,
                           timeout=module_timeout(ctx, mod, 900),
                           dry_run=ctx.args.dry_run)
    ctx.stderr_log(mod["key"], err)
    if ctx.args.dry_run:
        return "dry-run", 0, ""
    target = ctx.csv_path(mod["key"])
    if out_path is not None and out_path.exists():
        # GAM wrote the CSV itself (redirect). Count it in place: a large
        # tenant's tokens.csv runs to hundreds of MB, and reading it back only
        # to write the same bytes again was four copies of it in memory.
        rows = csv_data_rows(out_path)
        header_only = rows == 0
    else:
        rows = csv_data_rows(out)
        header_only = is_header_only(out)
    # GAM reports a skipped mailbox on stderr; searching the CSV as well made
    # a signature containing "Does not exist" flip a clean module to partial.
    per_user_skips = any(marker in err for marker in PER_USER_SKIP_MARKERS)

    def keep():
        if out_path is None or not out_path.exists():
            target.write_text(out, encoding="utf-8")

    if rc == 0 or (rc == 60 and header_only):
        # Exit 60 with a header-only CSV is GAM for "no rows", not a failure.
        keep()
        if per_user_skips:
            # A batched scan exits 0 even when a mailbox failed: the failure
            # happened in a child process. Only stderr carries it, so without
            # this the module reports full coverage over a short result.
            note = [ln for ln in err.strip().splitlines()
                    if any(m in ln for m in PER_USER_SKIP_MARKERS)]
            return "partial", rows, f"some users failed - {note[-1].strip()}"
        return ("empty" if rows == 0 else "ok"), rows, ""
    if mod["key"] == "caalevels" and CAALEVELS_AUTH_ERROR in (out + err):
        return "skipped", 0, ("not authorised: service account needs the "
                              "Access Context Manager Editor role in GCP")
    if mod["key"] == "browsers" and BROWSERS_AUTH_ERROR in (out + err):
        return "skipped", 0, ("not authorised: Chrome browser management "
                              "access is missing for this admin/API")
    if header_only and per_user_skips:
        # Some users were skipped and the rest simply had nothing to report:
        # partial coverage over an empty result, not a module failure.
        keep()
        note = err.strip().splitlines()[-1:] or [""]
        return "partial", 0, f"some users failed - exit {rc}: {note[0]}"
    if not header_only:
        # An `all users` print exits non-zero when ANY user fails (e.g. exit
        # 73 for a user with Gmail disabled) but still emits every other
        # user's rows. Discarding those rows would lose good data; keep them
        # and say plainly that coverage is partial.
        keep()
        note = (err or out).strip().splitlines()[-1:] or ["unknown error"]
        return "partial", rows, f"some users failed - exit {rc}: {note[0]}"
    note = (err or out).strip().splitlines()[-1:] or ["unknown error"]
    return "error", 0, f"exit {rc}: {note[0]}"


def collect_backupcodes_args(ctx: RunContext, mod: Dict) -> List[str]:
    """The user list and an explicit no-fork, no-redirect command.

    Two things this module must not do, both for the same reason - GAM writing
    this CSV itself would put live backup codes on disk:
      - no `redirect csv`, so the output stays on stdout where only the count
        is kept;
      - and therefore no fork, because each child writes its own CSV header to
        stdout and nothing merges them. Four mailboxes came back as seven rows
        on the dev tenant (2026-08-17) before this was pinned to 0.
    """
    args, _ = user_scan_args(ctx, mod)
    if "redirect" in args:
        cut = args.index("redirect")
        args = args[:cut] + args[cut + 4:]   # redirect csv <path> multiprocess
    if "auto_batch_min" in args:
        args[args.index("auto_batch_min") + 1] = "0"
    if "num_threads" in args:
        # Meaningless without a fork; dropped so the intent reads at a glance.
        cut = args.index("num_threads")
        args = args[:cut] + args[cut + 2:]
    return args


def collect_backupcodes(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    """Backup codes come back as LIVE codes; only the count may touch disk.

    Takes the user list and threading from user_scan_args but never its
    redirect: GAM writing this CSV itself would put live codes on disk.
    """
    try:
        args = collect_backupcodes_args(ctx, mod)
    except LookupError as exc:
        return "skipped", 0, str(exc)
    rc, out, err = run_gam(args, timeout=module_timeout(ctx, mod, 900),
                           dry_run=ctx.args.dry_run)
    ctx.stderr_log(mod["key"], err)
    if ctx.args.dry_run:
        return "dry-run", 0, ""
    failed = not (rc == 0 or (rc == 60 and is_header_only(out)))
    if failed and is_header_only(out):
        note = (err or out).strip().splitlines()[-1:] or ["unknown error"]
        return "error", 0, f"exit {rc}: {note[0]}"
    reduced = []
    for row in csv.DictReader(io.StringIO(out)):
        count = ""
        for key, value in row.items():
            if key and "count" in key.lower():
                count = value
                break
        reduced.append({"User": col(row, "User"),
                        "verificationCodesCount": count})
    write_rows(ctx.csv_path(mod["key"]), reduced)
    if failed:
        # One mailbox failing (Gmail off, deleted mid-run) used to blank the
        # whole finding; the other users' counts are still good data.
        note = (err or out).strip().splitlines()[-1:] or ["unknown error"]
        return "partial", len(reduced), f"some users failed - exit {rc}: {note[0]}"
    return ("empty" if not reduced else "ok"), len(reduced), ""


def _batched_filelist(ctx: RunContext, mod: Dict, tail: List[str],
                      row_filter=None) -> Tuple[str, int, str]:
    """Run one `all users print filelist ...` through the batch machinery.

    One gam process per user cost ~2s of start-up per mailbox before a single
    file was listed, serially: the same shape the tier-2 modules had before
    1.4.0 and the same fix. user_scan_args turns this into a forked scan over
    the audited user list with a multiprocess redirect.

    row_filter, when given, is applied to the collected CSV afterwards - for
    the sweep where the externality test must run in Python because gam's pm
    filters cannot see the deciding field.
    """
    if not ctx.rows("users"):
        return "skipped", 0, "users module has no rows; run it first"
    if not ctx.internal_domains:
        return "skipped", 0, "domains module has no rows; run it first"
    scan = dict(mod, args=["all", "users", "print", "filelist"] + tail)
    status, rows, note = _collect_scan(ctx, scan)
    if row_filter is None or status not in ("ok", "partial", "empty"):
        return status, rows, note
    kept = [r for r in read_csv_rows(ctx.csv_path(mod["key"])) if row_filter(r)]
    write_rows(ctx.csv_path(mod["key"]), kept)
    if status == "ok" and not kept:
        status = "empty"
    return status, len(kept), note


def _collect_scan(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    """collect_simple with the Drive scan's longer per-user allowance.

    module_timeout's 10s per mailbox is sized for a Gmail-settings call; a
    Drive listing is bounded by file count, not user count, so the module's
    own ceiling stays the floor and the per-user term is tripled.
    """
    users = ctx.manifest["meta"].get("user_count", 0)
    scan = dict(mod, timeout=max(mod.get("timeout", 3600),
                                 users * PER_USER_TIMEOUT_SECONDS * 3))
    return collect_simple(ctx, scan)


def collect_mydrive_external(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    return _batched_filelist(
        ctx, mod, ["fields", "id,name,mimeType,owners.emailAddress,"
                   "basicpermissions"] + external_pm_args(ctx.internal_domains))


def collect_sites(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    return _batched_filelist(
        ctx, mod, ["showmimetype", "gsite", "fields",
                   "id,name,owners.emailAddress"])


def collect_swm_external(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    # No pm filter here: the recipient of an externally-owned file sees NO
    # permissions array at all (verified on dev 2026-08-15 - basicpermissions
    # came back empty on the planted inbound fixture), so any pm filter
    # silently excludes every genuinely external file. Externality must be
    # decided from owners.0.emailAddress in Python instead.
    internal = {d.lower() for d in ctx.internal_domains}

    def is_external(row):
        owner = col(row, "owners.0.emailAddress").lower()
        return "@" in owner and owner.rsplit("@", 1)[1] not in internal

    return _batched_filelist(
        ctx, mod, ["fullquery", "sharedWithMe and not 'me' in owners",
                   "fields", "id,name,owners.emailAddress,sharedWithMeTime"],
        row_filter=is_external)


def collect_sd_external(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    """Scan each Shared Drive for external ACLs.

    filelist has NO adminaccess option, so running it as a non-member of the
    drive returns zero rows and looks clean. Drives the auditing admin is not
    a member of are therefore reported UNSCANNED unless --grant-temp-access
    is set, in which case the admin is added as organizer (via admin access),
    the drive is scanned, and the grant is removed again - the one write in
    the whole script.
    """
    drives = ctx.rows("shareddrives")
    if not drives:
        return "skipped", 0, "shareddrives module has no rows; run it first"
    if not ctx.internal_domains:
        return "skipped", 0, "domains module has no rows; run it first"
    if not ctx.admin:
        return "skipped", 0, "--admin required for Shared Drive scans"
    acls = ctx.rows("shareddriveacls")
    member_drives = set()
    admin_lower = ctx.admin.lower()
    for acl in acls:
        if col(acl, "permission.emailAddress", "emailAddress").lower() == admin_lower:
            member_drives.add(col(acl, "id"))

    pm = external_pm_args(ctx.internal_domains)
    rows: List[Dict[str, str]] = []
    unscanned: List[str] = []
    failed: List[str] = []
    errors = 0
    for drive in drives:
        if shutdown_requested:
            return "error", len(rows), "interrupted"
        drive_id = col(drive, "id")
        drive_name = col(drive, "name")
        if not drive_id:
            continue
        is_member = drive_id in member_drives
        granted = False
        if not is_member:
            if not ctx.args.grant_temp_access:
                unscanned.append(f"{drive_name} ({drive_id})")
                continue
            rc, out, err = run_gam(
                ["user", ctx.admin, "add", "drivefileacl", drive_id,
                 "user", ctx.admin, "role", "organizer", "adminaccess"],
                timeout=120, dry_run=ctx.args.dry_run)
            ctx.stderr_log(mod["key"], err)
            if not ctx.args.dry_run and rc != 0:
                unscanned.append(f"{drive_name} ({drive_id}) - temp grant failed")
                errors += 1
                continue
            granted = True
        try:
            rc, out, err = run_gam(
                ["user", ctx.admin, "print", "filelist",
                 "select", "shareddriveid", drive_id, "fields",
                 "id,name,mimeType,basicpermissions"] + pm,
                timeout=mod.get("timeout", 3600), dry_run=ctx.args.dry_run)
            ctx.stderr_log(mod["key"], err)
            if ctx.args.dry_run:
                continue
            if rc == 0 or (rc == 60 and is_header_only(out)):
                for row in csv.DictReader(io.StringIO(out)):
                    row["shareddrive.id"] = drive_id
                    row["shareddrive.name"] = drive_name
                    rows.append(row)
            else:
                errors += 1
                failed.append(f"{drive_name} ({drive_id})")
                unscanned.append(f"{drive_name} ({drive_id}) - scan failed")
        finally:
            if granted:
                # Remove the temporary grant even when the scan itself failed.
                rc, out, err = run_gam(
                    ["user", ctx.admin, "delete", "drivefileacl", drive_id,
                     ctx.admin, "adminaccess"],
                    timeout=120, dry_run=ctx.args.dry_run)
                ctx.stderr_log(mod["key"], err)
                if not ctx.args.dry_run and rc != 0:
                    print_error(
                        f"Could not remove the temporary organizer grant on "
                        f"Shared Drive {drive_name} ({drive_id}). Remove "
                        f"{ctx.admin} manually in the Admin console.")
    if ctx.args.dry_run:
        return "dry-run", 0, ""
    write_rows(ctx.csv_path(mod["key"]), rows)
    ctx.manifest["meta"]["unscanned_shared_drives"] = unscanned
    note = ""
    not_member = len(unscanned) - len(failed)
    if not_member:
        note = (f"{not_member} drive(s) UNSCANNED (admin not a member; "
                f"re-run with --grant-temp-access to cover them)")
    if failed:
        # Name them: a timed-out drive contributes nothing and the operator
        # has to know which one to re-run.
        note = (note + "; " if note else "") + \
            f"{len(failed)} drive(s) FAILED mid-scan: {', '.join(failed)}"
    return ("empty" if not rows else "ok"), len(rows), note


# ---- DNS ----

def tamingdns_check(check: str, domain: str, timeout: int = 25,
                    extra_args: Optional[Dict] = None) -> Optional[Dict]:
    """One stateless JSON-RPC tools/call POST; the response is already shaped
    as findings (severity, explanation, remediation, grade, provider)."""
    arguments = {"domain": domain}
    arguments.update(extra_args or {})
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": check, "arguments": arguments},
    }).encode("utf-8")
    req = urllib.request.Request(
        TAMINGDNS_MCP_URL, data=payload,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "User-Agent": "tenant_scope.py"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    # The endpoint may answer as plain JSON or as a single SSE data: frame.
    if body.lstrip().startswith("event:") or "\ndata:" in body or body.lstrip().startswith("data:"):
        frames = [ln[5:].strip() for ln in body.splitlines()
                  if ln.startswith("data:")]
        body = frames[-1] if frames else body
    data = json.loads(body)
    result = data.get("result", {})
    content = result.get("content") or []
    if content and isinstance(content, list) and "text" in content[0]:
        try:
            return json.loads(content[0]["text"])
        except (json.JSONDecodeError, TypeError):
            return {"raw": content[0]["text"]}
    return result or None


def doh_query(name: str, rtype: str, timeout: int = 10) -> List[str]:
    url = f"{DOH_URL}?name={urllib.parse.quote(name)}&type={rtype}"
    req = urllib.request.Request(url, headers={"User-Agent": "tenant_scope.py"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return [answer.get("data", "").strip('"')
            for answer in data.get("Answer", [])]


def doh_fallback(domain: str) -> Dict:
    """Minimal presence/policy checks when tamingdns.com is unreachable."""
    result = {"path": "doh", "checks": {}}
    try:
        mx = doh_query(domain, "MX")
        result["checks"]["mx"] = {"present": bool(mx), "records": mx}
    except Exception as exc:
        result["checks"]["mx"] = {"error": str(exc)}
    try:
        txt = doh_query(domain, "TXT")
        spf = [t for t in txt if t.replace('" "', '').startswith("v=spf1")]
        result["checks"]["spf"] = {"present": bool(spf), "records": spf}
    except Exception as exc:
        result["checks"]["spf"] = {"error": str(exc)}
    try:
        dkim = doh_query(f"google._domainkey.{domain}", "TXT")
        result["checks"]["dkim"] = {"present": bool(dkim),
                                    "selector": "google"}
    except Exception as exc:
        result["checks"]["dkim"] = {"error": str(exc)}
    try:
        dmarc = doh_query(f"_dmarc.{domain}", "TXT")
        dmarc = [t for t in dmarc if "v=DMARC1" in t]
        result["checks"]["dmarc"] = {"present": bool(dmarc), "records": dmarc}
    except Exception as exc:
        result["checks"]["dmarc"] = {"error": str(exc)}
    return result


DNS_WORKERS = 4   # domains checked at once; tamingdns rate limits are unknown


def _dns_domain(domain: str, use_fallback: bool) -> Dict:
    """All four checks for one domain, tamingdns first, DoH if every one failed."""
    if use_fallback:
        return doh_fallback(domain)
    entry: Dict = {"path": "tamingdns", "checks": {}}
    for check in ("check_mx", "check_spf", "check_dkim", "check_dmarc"):
        try:
            extra = {"selector": "google"} if check == "check_dkim" else None
            entry["checks"][check.replace("check_", "")] = tamingdns_check(
                check, domain, extra_args=extra)
        except Exception as exc:
            entry["checks"][check.replace("check_", "")] = {
                "error": f"{type(exc).__name__}: {exc}"}
    if all("error" in (v or {}) for v in entry["checks"].values()):
        entry = doh_fallback(domain)
    return entry


def collect_dns(ctx: RunContext, mod: Dict) -> Tuple[str, int, str]:
    # Google's *.test-google-a.com alias exists on many tenants and is not a
    # mail domain; checking its DNS only adds noise to the report.
    domains = [d for d in ctx.internal_domains
               if not d.endswith("test-google-a.com")]
    if not domains:
        return "skipped", 0, "domains module has no rows; run it first"
    if ctx.args.dry_run:
        return "dry-run", 0, ""
    use_fallback = bool(ctx.manifest["meta"].get("dns_fallback"))
    results: Dict[str, Dict] = {}
    # Four HTTP checks per domain at up to 25s each: a dozen domains took
    # minutes in series and the calls share nothing, so run them together.
    with ThreadPoolExecutor(max_workers=DNS_WORKERS) as pool:
        futures = {pool.submit(_dns_domain, d, use_fallback): d for d in domains}
        for idx, fut in enumerate(as_completed(futures), 1):
            domain = futures[fut]
            results[domain] = fut.result()
            print_info(f"dns: {domain} done ({idx}/{len(domains)})")
    results = {d: results[d] for d in domains}   # report order = domain order
    (ctx.run_dir / "dns.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    dead = [d for d, e in results.items()
            if e.get("checks") and all("error" in (v or {})
                                       for v in e["checks"].values())]
    if len(dead) == len(domains):
        return "error", 0, "every DNS check failed on both paths"
    if dead:
        return "partial", len(results), f"checks failed for {', '.join(dead)}"
    return "ok", len(results), ""


COLLECTORS = {
    "simple": collect_simple,
    "backupcodes": collect_backupcodes,
    "mydrive_external": collect_mydrive_external,
    "sd_external": collect_sd_external,
    "swm_external": collect_swm_external,
    "sites": collect_sites,
    "dns": collect_dns,
}


def derive_internal_domains(ctx: RunContext):
    """The internal-domain list feeds every external-share recipe. domains
    includes aliases via the type column; domainaliases adds any stragglers."""
    domains = set()
    for row in ctx.rows("domains"):
        name = col(row, "domainName", "domain")
        if name:
            domains.add(name.lower())
    for row in ctx.rows("domainaliases"):
        name = col(row, "domainAliasName", "domainAlias", "domainName")
        if name:
            domains.add(name.lower())
    if domains:
        ctx.internal_domains = sorted(domains)
        ctx.save()


FIRST_MODULES = ("domains", "domainaliases", "users")
LIGHT_WORKERS = 4   # tenant-level gam prints run at once


def _is_batch(mod: Dict) -> bool:
    return [a.lower() for a in (mod.get("args") or [])[:2]] == ["all", "users"]


def _needs_run(ctx: RunContext, mod: Dict) -> bool:
    """Resume and scope gating, decided on the main thread."""
    key = mod["key"]
    status = ctx.module_status(key)
    note = ctx.manifest["modules"].get(key, {}).get("note", "")
    # A partial module is re-run only when it was cut short by a timeout;
    # partial because one mailbox has Gmail off would re-scan the whole
    # tenant on every resume and end partial again.
    if status in ("ok", "empty") or (status == "partial"
                                     and "Timed out" not in note):
        print_info(f"{key}: already collected, skipping (resume)")
        return False
    if ctx.failed_scopes and set(mod.get("scopes", [])) & set(ctx.failed_scopes):
        ctx.set_module(key, "skipped", 0, "not authorised: DWD scope "
                       "missing (see preflight)")
        print_warning(f"{key}: skipped, DWD scope not authorised")
        return False
    return True


def _run_collector(ctx: RunContext, mod: Dict) -> Tuple[str, int, str, float]:
    started = time.time()
    status, rows, note = COLLECTORS[mod.get("collector", "simple")](ctx, mod)
    return status, rows, note, time.time() - started


def _record(ctx: RunContext, mod: Dict, status: str, rows: int, note: str,
            elapsed: float):
    """Manifest write, console line and the post-module hooks. Main thread
    only: manifest.json is one file and save() is not atomic."""
    key = mod["key"]
    if status != "dry-run":
        ctx.set_module(key, status, rows, note)
    label = f"{key}: {status}, {rows} row(s) in {elapsed:.0f}s"
    if note:
        label += f" - {note}"
    if status in ("ok", "empty", "dry-run"):
        print_success(label)
    elif status in ("skipped", "partial"):
        print_warning(label)
    else:
        print_error(label)
    if key in ("domains", "domainaliases"):
        derive_internal_domains(ctx)
    if key == "users":
        ctx.manifest["meta"]["user_count"] = rows
        ctx.save()


def collect(ctx: RunContext, modules: List[Dict]):
    """Three passes: the modules everything depends on, then every
    tenant-level print together, then the per-mailbox and Drive scans one
    at a time.

    The per-mailbox modules already fork SCAN_THREADS gam processes each;
    two of those at once is forty processes for no quota headroom. The
    tenant-level prints are one process and a few seconds apiece, and the
    long ones (report users, tokens) hide the rest when they overlap.
    """
    print_header("STAGE 1 - COLLECT")
    ctx.manifest["meta"]["include_suspended"] = bool(ctx.args.include_suspended)
    ctx.manifest["meta"].setdefault(
        "collected_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    first = [m for m in modules if m["key"] in FIRST_MODULES]
    rest = [m for m in modules if m["key"] not in FIRST_MODULES]
    light = [m for m in rest
             if m.get("collector", "simple") in ("simple", "dns")
             and not _is_batch(m)]
    heavy = sorted([m for m in rest if m not in light],
                   key=lambda m: m["tier"])

    def stop() -> bool:
        if shutdown_requested:
            print_warning("Stopping; resume this run with --run-dir "
                          + str(ctx.run_dir))
        return shutdown_requested

    for mod in first:
        if stop():
            return
        if _needs_run(ctx, mod):
            _record(ctx, mod, *_run_collector(ctx, mod))

    pending = [m for m in light if _needs_run(ctx, m)]
    if pending and not stop():
        with ThreadPoolExecutor(max_workers=LIGHT_WORKERS) as pool:
            futures = {pool.submit(_run_collector, ctx, m): m for m in pending}
            for fut in as_completed(futures):
                _record(ctx, futures[fut], *fut.result())
                if shutdown_requested:
                    # Running gam processes finish (they are in their own
                    # group); queued modules are dropped for the resume.
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

    for mod in heavy:
        if stop():
            return
        if _needs_run(ctx, mod):
            _record(ctx, mod, *_run_collector(ctx, mod))


###############################################################################
# CHECK - FINDINGS ENGINE
###############################################################################

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "INFO"]


class Finding:
    """One report finding: fixed client-facing copy plus evidence rows."""

    def __init__(self, fid: str, severity: str, title: str, meaning: str,
                 remediation: str, evidence: List[Dict[str, str]],
                 source: str, count: Optional[int] = None):
        self.fid = fid
        self.severity = severity
        self.title = title
        self.meaning = meaning
        self.remediation = remediation
        self.evidence = evidence[:EVIDENCE_ROWS]
        self.count = count if count is not None else len(evidence)
        self.source = source


def _module_usable(ctx: RunContext, key: str) -> bool:
    return ctx.module_status(key) in ("ok", "empty", "partial")


def _super_admins(ctx: RunContext) -> List[Dict[str, str]]:
    return [r for r in ctx.rows("users") if truthy(col(r, "isAdmin"))
            and not truthy(col(r, "suspended"))]


def _admin_role(row: Dict[str, str]) -> str:
    """'super admin', 'delegated admin' or '' for a users.csv row."""
    if truthy(col(row, "isAdmin")):
        return "super admin"
    if truthy(col(row, "isDelegatedAdmin")):
        return "delegated admin"
    return ""


def _live_users(ctx: RunContext) -> List[Dict[str, str]]:
    """Accounts that can sign in: neither suspended nor archived. Archived
    accounts cannot authenticate, so counting them as unenrolled or dormant
    pads every people-centric finding."""
    return [r for r in ctx.rows("users")
            if not (truthy(col(r, "suspended")) or truthy(col(r, "archived")))]


def _risky_scope_labels(row: Dict[str, str]) -> List[str]:
    """Labels of RISKY_SCOPES present in a tokens.csv row. Scopes sit
    space-separated in one cell; match whole tokens so .../auth/drive does
    not also swallow .../auth/drive.readonly."""
    scopes = set(col(row, "scopes").split())
    return [label for url, label in RISKY_SCOPES.items() if url in scopes]


def check_public_files(ctx: RunContext) -> List[Finding]:
    findings = []
    for key, where in (("mydrive_external", "My Drive"),
                       ("shareddrive_external", "Shared Drives")):
        if not _module_usable(ctx, key):
            continue
        public = []
        linked = []
        for row in ctx.rows(key):
            if col(row, "permission.type") == "anyone":
                entry = {"File": col(row, "name"),
                         "Owner": col(row, "owners.0.emailAddress",
                                      "owners.emailAddress",
                                      "shareddrive.name"),
                         "File ID": col(row, "id")}
                if truthy(col(row, "permission.allowFileDiscovery")):
                    public.append(entry)
                else:
                    linked.append(entry)
        if public:
            findings.append(Finding(
                f"public-files-{key}", "CRITICAL",
                f"Files in {where} are public on the web",
                "These files are shared with \"anyone\" and marked "
                "discoverable, which means search engines can index them and "
                "anyone on the internet can open them without signing in.",
                "Open each file's sharing settings and change access to "
                "specific people, or at minimum switch off \"anyone can "
                "find\" so the link is required.",
                public, f"{key}.csv"))
        if len(linked) >= ANYONE_LINK_SCALE:
            findings.append(Finding(
                f"anyone-link-{key}", "HIGH",
                f"Large number of \"anyone with the link\" files in {where}",
                f"{len(linked)} files can be opened by anyone who has the "
                "link, with no sign-in. Links leak: they get forwarded, "
                "pasted into tickets and indexed from public pages.",
                "Review the list and restrict sharing to named people or "
                "groups where the open link is not deliberate.",
                linked, f"{key}.csv"))
    return findings


def check_external_file_shares(ctx: RunContext) -> List[Finding]:
    """Files shared to specific external people/groups or whole external
    domains, and external-owned files shared into the tenant.

    check_public_files only covers anyone-type ACLs; these named-target
    external shares were collected but surfaced nowhere until the 2026-08-15
    round-3 fixtures exposed the gap.
    """
    findings = []
    internal = {d.lower() for d in ctx.internal_domains}
    named, domains = [], []
    for key, where in (("mydrive_external", "My Drive"),
                       ("shareddrive_external", "Shared Drives")):
        if not _module_usable(ctx, key):
            continue
        for row in ctx.rows(key):
            ptype = col(row, "permission.type")
            entry = {"File": col(row, "name"),
                     "Where": where,
                     "Owner": col(row, "owners.0.emailAddress",
                                  "owners.emailAddress", "shareddrive.name"),
                     "Role": col(row, "permission.role"),
                     "File ID": col(row, "id")}
            if ptype in ("user", "group"):
                addr = col(row, "permission.emailAddress")
                if addr and email_domain(addr) not in internal:
                    entry["Shared with"] = addr
                    named.append(entry)
            elif ptype == "domain":
                dom = col(row, "permission.domain").lower()
                if dom and dom not in internal:
                    entry["Shared with"] = f"everyone at {dom}"
                    domains.append(entry)
    if domains:
        findings.append(Finding(
            "external-domain-shares", "HIGH",
            "Files shared with an entire external domain",
            "These files are open to every account in another organisation's "
            "domain, not to named people. Anyone that organisation hires "
            "gains access automatically.",
            "Replace the domain-wide share with the specific external people "
            "who need the file.",
            domains, "mydrive_external.csv"))
    if named:
        findings.append(Finding(
            "external-user-shares", "MEDIUM",
            "Files shared with people outside the organisation",
            "These files are shared to named external addresses. Individual "
            "external shares are often legitimate, but each one outlives the "
            "conversation it was created for and keeps working after the "
            "recipient changes role or employer.",
            "Review the list; remove shares whose purpose has passed, and "
            "prefer expiring access for the rest.",
            named, "mydrive_external.csv"))
    if _module_usable(ctx, "sharedwithme_external"):
        inbound = [{"File": col(r, "name"),
                    "External owner": col(r, "owners.0.emailAddress"),
                    "Shared with": col(r, "Owner"),
                    "Shared on": col(r, "sharedWithMeTime")}
                   for r in ctx.rows("sharedwithme_external")]
        if inbound:
            findings.append(Finding(
                "external-inbound-shares", "INFO",
                "Files owned outside the organisation shared into it",
                "Staff have externally-owned files in their \"Shared with "
                "me\". The data lives in someone else's tenant: the owner "
                "controls access and can withdraw or change it at any time.",
                "No action needed unless business data is being kept in "
                "externally-owned files; anything critical should be copied "
                "into a drive the organisation owns.",
                inbound, "sharedwithme_external.csv"))
    return findings


def check_super_admin_count(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "users"):
        return []
    admins = _super_admins(ctx)
    if len(admins) >= 2:
        return []
    evidence = [{"Super admin": col(r, "primaryEmail")} for r in admins]
    return [Finding(
        "few-super-admins", "CRITICAL",
        "Fewer than two super admin accounts",
        "With only one super admin, losing that one account (departure, "
        "lockout, compromise) locks the organisation out of its own "
        "Google Workspace tenant.",
        "Create a second super admin account (ideally a dedicated "
        "break-glass account with strong 2-step verification), and store "
        "its credentials securely.",
        evidence, "users.csv", count=len(admins))]


def check_admin_2sv(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "users"):
        return []
    weak = [r for r in _super_admins(ctx)
            if not truthy(col(r, "isEnrolledIn2Sv"))]
    if not weak:
        return []
    evidence = [{"Super admin": col(r, "primaryEmail"),
                 "Last login": col(r, "lastLoginTime")} for r in weak]
    return [Finding(
        "admin-no-2sv", "CRITICAL",
        "Super admin accounts without 2-step verification",
        "A super admin password on its own is the single key to the whole "
        "tenant. These accounts are not enrolled in 2-step verification, so "
        "one phished or reused password is enough to take over everything.",
        "Enrol every super admin in 2-step verification now, preferring "
        "security keys or passkeys, and then enforce 2SV for admins via "
        "policy.",
        evidence, "users.csv")]


def _asp_rows(ctx: RunContext) -> List[Dict[str, str]]:
    """Rows in asps.csv that are an actual app password.

    `gam all users print asps` emits one row per user with an `asps` count
    column when that user has none - a clean tenant yields 37 rows of
    `user,0`. Counting rows therefore flags everybody. Real app passwords
    carry a codeId.
    """
    real = []
    for row in ctx.rows("asps"):
        if col(row, "codeId", "codeid"):
            real.append(row)
            continue
        count = col(row, "asps")
        if count and count.strip().isdigit() and int(count) > 0:
            real.append(row)
    return real


def check_admin_asps(ctx: RunContext) -> List[Finding]:
    if not (_module_usable(ctx, "users") and _module_usable(ctx, "asps")):
        return []
    # Delegated admins too: an app password bypasses 2SV on any account that
    # can reset passwords or read audit logs, not only on a super admin.
    admins = {col(r, "primaryEmail").lower(): _admin_role(r)
              for r in _live_users(ctx) if _admin_role(r)}
    hits = [r for r in _asp_rows(ctx) if col(r, "User").lower() in admins]
    if not hits:
        return []
    evidence = [{"Admin": col(r, "User"),
                 "Role": admins[col(r, "User").lower()],
                 "App password name": col(r, "name"),
                 "Created": col(r, "creationTime")} for r in hits]
    return [Finding(
        "admin-asps", "CRITICAL",
        "Admin accounts using app passwords",
        "App passwords bypass 2-step verification: anything holding one can "
        "sign in as the admin without a second factor. On an admin account "
        "that undoes the strongest protection the tenant has.",
        "Identify what each app password is for, replace it with modern "
        "OAuth sign-in, and revoke the app passwords on all admin accounts.",
        evidence, "asps.csv")]


def check_external_forwarding(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "forwards"):
        return []
    internal = set(ctx.internal_domains)
    hits = []
    for row in ctx.rows("forwards"):
        # GAM7 emits User,forwardEnabled,forwardTo,disposition (verified on
        # the dev tenant). The older name is kept for gam builds that used it.
        if not truthy(col(row, "forwardEnabled", "forwardingEnabled", "enabled")):
            continue
        target = col(row, "forwardTo", "emailAddress", "forwardingAddress")
        if target and email_domain(target) not in internal:
            hits.append({"User": col(row, "User"),
                         "Forwards to": target})
    if not hits:
        return []
    return [Finding(
        "external-forwarding", "CRITICAL",
        "Mailboxes forwarding to addresses outside the organisation",
        "All mail arriving in these mailboxes is being copied or moved to an "
        "external address. This is a common way company data quietly leaves "
        "the organisation, and one of the first things attackers set up "
        "after compromising an account.",
        "Confirm with each user whether the forward is legitimate business "
        "use. Remove any that are not, and review the account's recent "
        "sign-in activity if the forward was not set up knowingly.",
        hits, "forwards.csv")]


def check_orphaned_shared_drives(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "shareddriveorganizers"):
        return []
    hits = []
    for row in ctx.rows("shareddriveorganizers"):
        if not col(row, "organizers"):
            hits.append({"Shared Drive": col(row, "name"),
                         "Drive ID": col(row, "id")})
    if not hits:
        return []
    return [Finding(
        "orphaned-shared-drives", "CRITICAL",
        "Shared Drives with no manager",
        "Nobody can manage membership, sharing or deletion on these drives - "
        "typically because every manager has left the organisation. The "
        "content is live but unowned, and access can no longer be corrected "
        "by the people using it.",
        "Have an admin appoint a new manager on each drive (Admin console > "
        "Apps > Google Workspace > Drive and Docs > Manage shared drives).",
        hits, "shareddriveorganizers.csv")]


def check_shared_drive_external(ctx: RunContext) -> List[Finding]:
    findings = []
    internal = set(ctx.internal_domains)
    if _module_usable(ctx, "shareddriveacls"):
        hits = []
        for row in ctx.rows("shareddriveacls"):
            if truthy(col(row, "permission.deleted")):
                continue
            addr = col(row, "permission.emailAddress", "emailAddress")
            if addr and email_domain(addr) not in internal:
                hits.append({"Shared Drive": col(row, "name"),
                             "External member": addr,
                             "Role": col(row, "permission.role", "role")})
        if hits:
            findings.append(Finding(
                "sd-external-members", "HIGH",
                "Shared Drives with members from outside the organisation",
                "External people are full members of these Shared Drives and "
                "see everything in them, now and in future - membership "
                "outlives the project it was granted for.",
                "Review each external member: still needed? If yes, confirm "
                "the drive holds nothing beyond their remit; if not, remove "
                "them.",
                hits, "shareddriveacls.csv"))
    if _module_usable(ctx, "shareddrives"):
        open_drives = []
        for row in ctx.rows("shareddrives"):
            domain_only = col(row, "restrictions.domainUsersOnly")
            members_only = col(row, "restrictions.driveMembersOnly")
            if domain_only and not truthy(domain_only):
                open_drives.append({
                    "Shared Drive": col(row, "name"),
                    "External sharing allowed": "yes",
                    "Non-members can open files":
                        "yes" if members_only and not truthy(members_only)
                        else "members only"})
        if open_drives:
            findings.append(Finding(
                "sd-open-settings", "HIGH",
                "Shared Drives configured to allow external sharing",
                "These drives permit files to be shared to people outside "
                "the organisation. That may be intentional for "
                "client-facing drives, but on internal drives it widens the "
                "blast radius of a single careless share.",
                "For drives that should stay internal, tick \"only people "
                "in the organisation\" in the shared drive's settings.",
                open_drives, "shareddrives.csv"))
    return findings


def check_group_exposure(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "groups"):
        return []
    findings = []
    open_join, ext_members, open_post = [], [], []
    for row in ctx.rows("groups"):
        entry = {"Group": col(row, "email"), "Name": col(row, "name")}
        if col(row, "whoCanJoin").upper() == "ANYONE_CAN_JOIN":
            open_join.append(entry)
        if truthy(col(row, "allowExternalMembers")):
            ext_members.append(entry)
        if col(row, "whoCanPostMessage").upper() == "ANYONE_CAN_POST":
            open_post.append(entry)
    if open_join:
        findings.append(Finding(
            "groups-anyone-join", "HIGH",
            "Groups anyone on the internet can join",
            "Joining one of these groups requires no approval and no "
            "organisation account. Whatever the group can access - shared "
            "files, mail history, calendar invites - is open to whoever "
            "joins.",
            "Change \"who can join\" to invited or organisation users only "
            "on each of these groups.",
            open_join, "groups.csv"))
    if ext_members:
        findings.append(Finding(
            "groups-external-members", "HIGH",
            "Groups that allow members from outside the organisation",
            "External addresses can be members of these groups. Any file or "
            "resource shared to the group is then shared outside the "
            "organisation, which is easy to miss when sharing \"to the "
            "team\".",
            "Where external membership is not deliberate, switch off "
            "\"allow external members\" and remove any outside addresses.",
            ext_members, "groups.csv"))
    if open_post:
        findings.append(Finding(
            "groups-anyone-post", "HIGH",
            "Groups anyone on the internet can post to",
            "Anyone can send mail into these groups without being a member. "
            "That makes them a spam and phishing delivery route straight "
            "into staff inboxes.",
            "Restrict posting to organisation users or members on each "
            "group, unless the address is a deliberate public contact "
            "point.",
            open_post, "groups.csv"))
    return findings


def check_filter_forwarding(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "filters"):
        return []
    internal = set(ctx.internal_domains)
    hits = []
    for row in ctx.rows("filters"):
        # GAM writes the action verb into the cell ("forward user@x.com"),
        # so the address has to come off the end of the value.
        target = col(row, "forward").removeprefix("forward").strip()
        if target and email_domain(target) not in internal:
            hits.append({"User": col(row, "User", "user"),
                         "Filter forwards to": target})
    if not hits:
        return []
    return [Finding(
        "filter-external-forwarding", "HIGH",
        "Gmail filters forwarding mail to external addresses",
        "These filters quietly send matching mail to an outside address. "
        "Unlike account-level forwarding they are easy to miss, and "
        "attackers use them to keep receiving a victim's mail after a "
        "password reset.",
        "Review each filter with the user; delete any that are not known, "
        "deliberate business arrangements, and review those accounts' "
        "recent sign-in activity.",
        hits, "filters.csv")]


def check_unmanaged_accounts(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "userinvitations"):
        return []
    rows = ctx.rows("userinvitations")
    if not rows:
        return []
    evidence = [{"Email": col(r, "email"),
                 "State": col(r, "state")} for r in rows]
    return [Finding(
        "unmanaged-accounts", "HIGH",
        "Personal Google accounts using company email addresses",
        "People have created personal (unmanaged) Google accounts on the "
        "organisation's own domain. Those accounts, and any company data in "
        "them, sit outside admin control: the organisation cannot enforce a "
        "password policy or 2-step verification on them, and cannot close "
        "them when the person leaves.",
        "Send invitations to convert these into managed accounts (Admin "
        "console > Directory > User invitations), and chase the holdouts.",
        evidence, "userinvitations.csv")]


def check_dns_findings(ctx: RunContext) -> List[Finding]:
    dns_path = ctx.run_dir / "dns.json"
    if not (_module_usable(ctx, "dns") and dns_path.is_file()):
        return []
    try:
        results = json.loads(dns_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(results, dict):
        return []
    missing = []
    for domain, entry in results.items():
        checks = entry.get("checks", {})
        dmarc = checks.get("dmarc") or {}
        if "present" in dmarc:                      # DoH fallback shape
            if not dmarc["present"]:
                missing.append({"Domain": domain, "Checked via": "dns.google"})
        elif "error" not in dmarc:                  # tamingdns shape
            # Trust the checker's own verdict: an overall "fail" status, or
            # any finding it grades critical/high, means the domain has no
            # working DMARC. Info/warn findings (deprecated tags, org-domain
            # inheritance) are not "missing".
            status = str(dmarc.get("status", "")).lower()
            worst = {str(f.get("severity", "")).lower()
                     for f in dmarc.get("findings", [])
                     if isinstance(f, dict)}
            if status in ("fail", "error") or worst & {"critical", "high"}:
                missing.append({"Domain": domain, "Checked via": "tamingdns.com"})
    if not missing:
        return []
    return [Finding(
        "dmarc-missing", "HIGH",
        "Domains without a working DMARC record",
        "Without DMARC, anyone can send mail that claims to be from these "
        "domains and receiving servers have no instruction to reject it. "
        "That enables convincing invoice fraud and phishing in the "
        "organisation's name.",
        "Publish a DMARC record for each domain, starting at p=none to "
        "observe, then move to quarantine/reject once legitimate senders "
        "are aligned. Full per-domain detail is in the DNS section below.",
        missing, "dns.json")]


def check_2sv_enrolment(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "users"):
        return []
    users = _live_users(ctx)
    if not users:
        return []
    unenrolled = [r for r in users if not truthy(col(r, "isEnrolledIn2Sv"))]
    if not unenrolled:
        return []
    pct = round(100 * (len(users) - len(unenrolled)) / len(users))
    evidence = [{"User": col(r, "primaryEmail"),
                 "Last login": col(r, "lastLoginTime")} for r in unenrolled]
    return [Finding(
        "2sv-enrolment", "MEDIUM",
        f"2-step verification enrolment is at {pct}%",
        f"{len(unenrolled)} of {len(users)} active accounts sign in with a "
        "password alone. A guessed or phished password on any of them gives "
        "an attacker the whole account.",
        "Run an enrolment campaign, then enforce 2-step verification by "
        "organisational unit once enrolment is high enough not to lock "
        "people out.",
        evidence, "users.csv", count=len(unenrolled))]


def check_pop_imap(ctx: RunContext) -> List[Finding]:
    findings = []
    for key, proto in (("imap", "IMAP"), ("pop", "POP")):
        if not _module_usable(ctx, key):
            continue
        hits = [{"User": col(r, "User", "user")} for r in ctx.rows(key)
                if truthy(col(r, "enabled"))]
        if hits:
            findings.append(Finding(
                f"{proto.lower()}-enabled", "MEDIUM",
                f"{proto} access is enabled on {len(hits)} mailbox(es)",
                f"{proto} lets older mail apps download the whole mailbox "
                "with just a password (or an app password). That sidesteps "
                "modern sign-in protections and leaves a full copy of the "
                "mail on whatever device connects.",
                f"Where no legacy mail client genuinely needs it, turn "
                f"{proto} off for the user - or disable it tenant-wide in "
                "Gmail settings if nobody does.",
                hits, f"{key}.csv"))
    return findings


GAM_NEVER_LOGIN = "Never"


def _paid_licences(row: Dict[str, str]) -> str:
    """The user's licence display string with free Cloud Identity stripped.

    Cloud Identity (non-Premium) auto-assigns and costs nothing, so an
    account holding only that is unlicensed for every costs-money finding.
    Cloud Identity Premium is a paid SKU and stays.
    """
    licences = col(row, "LicensesDisplay", "Licenses", "licenses")
    stripped = re.sub(r"Cloud Identity(?! Premium)( Free)?", "",
                      licences).strip()
    return licences if stripped else ""


def _never_logged_in(last: str) -> bool:
    # GAM prints "Never" or a 1970 epoch stamp for an account with no login.
    return not last or last == GAM_NEVER_LOGIN or last.startswith("1970-")


def _dormant_login(last: str, days: int = DORMANT_DAYS) -> bool:
    """True when the lastLoginTime string is absent, epoch, or older than
    `days`. Unparseable stamps count as NOT dormant - a formatting change in
    GAM must not flag the whole tenant."""
    if _never_logged_in(last):
        return True
    try:
        stamp = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp < datetime.now(timezone.utc) - timedelta(days=days)


def check_dormant_accounts(ctx: RunContext) -> List[Finding]:
    """Dormancy in three tiers: dormant admins (HIGH, licence irrelevant),
    licensed accounts that have never signed in, and licensed accounts idle
    past the cutoff."""
    if not _module_usable(ctx, "users"):
        return []
    admin_hits, never_hits, idle_hits = [], [], []
    for row in _live_users(ctx):
        last = col(row, "lastLoginTime")
        if not _dormant_login(last):
            continue
        paid = _paid_licences(row)
        entry = {"User": col(row, "primaryEmail"),
                 "Last login": "never" if _never_logged_in(last) else last,
                 "Licences": paid or "none"}
        role = _admin_role(row)
        if role:
            entry["Admin role"] = role
            admin_hits.append(entry)
        elif not paid:
            continue
        elif _never_logged_in(last):
            never_hits.append(entry)
        else:
            idle_hits.append(entry)
    findings = []
    if admin_hits:
        findings.append(Finding(
            "dormant-admin", "HIGH",
            "Admin accounts nobody has signed into for months",
            "These accounts hold admin rights but show no recent sign-in. "
            "An account with tenant-level power that nobody is watching is "
            "the one an attacker can use longest without being noticed.",
            "Confirm each account is still needed. Remove admin rights from "
            "accounts that no longer need them, and sign in periodically to "
            "the ones kept as break-glass access so activity is expected "
            "and monitored.",
            admin_hits, "users.csv"))
    if never_hits:
        findings.append(Finding(
            "never-logged-in", "MEDIUM",
            "Licensed accounts that have never been signed into",
            "These accounts were created, given a paid licence, and never "
            "used. They cost money every month and usually mean an "
            "onboarding that never happened or a leaver created in error.",
            "Confirm each account's purpose; delete or unlicense the ones "
            "that were never needed.",
            never_hits, "users.csv"))
    if idle_hits:
        findings.append(Finding(
            "dormant-licensed", "MEDIUM",
            f"Licensed accounts with no sign-in for over {DORMANT_DAYS} days",
            "These accounts hold paid licences but nobody has signed in for "
            "months. They cost money every month, and because nobody is "
            "watching them, a break-in there can go unnoticed for a long "
            "time.",
            "Confirm each account's purpose. Offboard leavers properly, "
            "convert genuine service accounts to unlicensed alternatives "
            "where possible, and reclaim the licences.",
            idle_hits, "users.csv"))
    return findings


def check_mailbox_delegation(ctx: RunContext) -> List[Finding]:
    """Who can read whose mail. Gmail delegates are internal-only, so there
    is no external-delegate case; the risk tiers are delegates on admin
    mailboxes and delegation nobody is watching.

    Caveat: the delegates module iterates ACTIVE users, so a suspended
    DELEGATOR's grants are invisible unless suspended users were included in
    the collection run."""
    if not (_module_usable(ctx, "delegates") and _module_usable(ctx, "users")):
        return []
    users = {col(r, "primaryEmail").lower(): r for r in ctx.rows("users")}
    admin_hits, watch_hits, table = [], [], []
    for row in ctx.rows("delegates"):
        delegator = col(row, "User", "user").lower()
        delegate = col(row, "delegateAddress", "delegateEmail",
                       "delegate").lower()
        if not delegate:
            continue
        table.append({"Mailbox": delegator, "Delegate": delegate,
                      "Status": col(row, "delegationStatus", "status")})
        entry = {"Mailbox": delegator, "Delegate": delegate}
        d_row = users.get(delegator)
        g_row = users.get(delegate)
        if d_row is not None and (truthy(col(d_row, "isAdmin"))
                                  or truthy(col(d_row, "isDelegatedAdmin"))):
            entry["Admin role"] = ("super admin"
                                   if truthy(col(d_row, "isAdmin"))
                                   else "delegated admin")
            admin_hits.append(entry)
        concerns = []
        for label, urow in (("mailbox owner", d_row), ("delegate", g_row)):
            if urow is None:
                continue
            if truthy(col(urow, "suspended")):
                concerns.append(f"{label} suspended")
            elif _dormant_login(col(urow, "lastLoginTime")):
                concerns.append(f"{label} dormant")
        if concerns:
            watch_hits.append(dict(entry, **{"Why": ", ".join(concerns)}))
    findings = []
    if admin_hits:
        findings.append(Finding(
            "delegates-on-admin-mailbox", "HIGH",
            "Admin mailboxes with delegates",
            "Someone else can read and send mail as an admin. Admin "
            "mailboxes receive password resets, security alerts and "
            "recovery mail - a delegate there can intercept all of it "
            "without ever knowing the admin's password.",
            "Remove delegation from admin mailboxes. If shared visibility "
            "of admin notifications is needed, route the alerts to a group "
            "instead.",
            admin_hits, "delegates.csv"))
    if watch_hits:
        findings.append(Finding(
            "delegation-unwatched", "MEDIUM",
            "Mailbox delegation involving suspended or dormant accounts",
            "These delegations involve an account that is suspended or has "
            "not signed in for months. Access that nobody is actively "
            "using or watching tends to be forgotten - and forgotten "
            "access is what turns up in incident reports.",
            "Remove delegations that are no longer in use, and re-point "
            "the ones that still serve a purpose at active accounts.",
            watch_hits, "delegates.csv"))
    if table:
        findings.append(Finding(
            "delegation-map", "INFO",
            "Who can read whose mailbox (delegation map)",
            "Every mailbox delegation in the tenant. Each row means the "
            "delegate can read, send and delete mail in that mailbox "
            "without the owner's password.",
            "No action needed; review the list for surprises.",
            table, "delegates.csv"))
    return findings


def check_at_risk_accounts(ctx: RunContext) -> List[Finding]:
    """One table per person instead of six separate lists: accounts scoring
    two or more independent risk factors."""
    if not _module_usable(ctx, "users"):
        return []
    internal = {d.lower() for d in ctx.internal_domains}
    asp_users = set()
    if _module_usable(ctx, "asps"):
        asp_users = {col(r, "User").lower() for r in _asp_rows(ctx)}
    risky_users = set()
    if _module_usable(ctx, "tokens"):
        risky_users = {col(r, "user").lower() for r in ctx.rows("tokens")
                       if _risky_scope_labels(r)}
    hits = []
    admin_flagged = False
    for row in _live_users(ctx):
        email = col(row, "primaryEmail").lower()
        admin = bool(_admin_role(row))
        reasons = []
        if not truthy(col(row, "isEnrolledIn2Sv")):
            reasons.append("no 2-step verification")
        recovery = col(row, "recoveryEmail")
        if not recovery:
            # Not a risk factor on an admin: check_admin_recovery tells them
            # to remove recovery details and rely on a second super admin,
            # and this check must not then score them for having done so.
            if not admin:
                reasons.append("no recovery email")
        elif email_domain(recovery) not in internal:
            reasons.append("personal recovery email")
        if email in asp_users:
            reasons.append("app-specific passwords")
        if email in risky_users:
            reasons.append("app with full mail/Drive access")
        if admin:
            reasons.append("admin role")
        if _dormant_login(col(row, "lastLoginTime")):
            reasons.append(f"no sign-in in {DORMANT_DAYS}+ days")
        if len(reasons) >= 2:
            admin_flagged = admin_flagged or admin
            hits.append({"User": col(row, "primaryEmail"),
                         "Risk factors": ", ".join(reasons)})
    if not hits:
        return []
    return [Finding(
        "at-risk-accounts", "HIGH" if admin_flagged else "MEDIUM",
        f"{len(hits)} account(s) carrying multiple risk factors",
        "Each account here combines at least two separate weaknesses - for "
        "example no 2-step verification plus a personal recovery address. "
        "Risk factors multiply: any one alone is survivable, together they "
        "make an account both easier to break into and harder to recover.",
        "Work through the list per person: enrol 2-step verification, "
        "point recovery details at organisation-controlled addresses, and "
        "revoke app passwords and over-broad app grants that are no longer "
        "needed.",
        hits, "users.csv")]


def check_suspended_holding_data(ctx: RunContext) -> List[Finding]:
    """Offboarding debt: suspended accounts that still cost money or still
    hold data nobody can reach."""
    if not _module_usable(ctx, "users"):
        return []
    suspended = {col(r, "primaryEmail").lower(): r for r in ctx.rows("users")
                 if truthy(col(r, "suspended"))}
    if not suspended:
        return []
    findings = []
    licensed = [{"User": email, "Licences": _paid_licences(row)}
                for email, row in sorted(suspended.items())
                if _paid_licences(row)]
    if licensed:
        findings.append(Finding(
            "suspended-licensed", "MEDIUM",
            f"{len(licensed)} suspended account(s) still holding a licence",
            "These accounts are suspended - typically leavers - but still "
            "hold paid licences. The organisation is paying every month "
            "for accounts nobody can sign into.",
            "Finish the offboarding: transfer any data that is still "
            "needed, then remove the licence (or delete the account once "
            "its data is safe).",
            licensed, "users.csv"))
    data_rows = []
    if _module_usable(ctx, "report_users"):
        for row in ctx.rows("report_users"):
            email = col(row, "email", "userEmail", "User").lower()
            if email not in suspended:
                continue
            gmail_mb = col(row, "accounts:gmail_used_quota_in_mb")
            drive_mb = col(row, "accounts:drive_used_quota_in_mb")
            if any(v not in ("", "0") for v in (gmail_mb, drive_mb)):
                data_rows.append({"User": email,
                                  "Gmail (MB)": gmail_mb or "0",
                                  "Drive (MB)": drive_mb or "0",
                                  "Holds": "mailbox/Drive data"})
    if _module_usable(ctx, "shareddriveacls"):
        for row in ctx.rows("shareddriveacls"):
            if truthy(col(row, "permission.deleted")):
                continue
            addr = col(row, "permission.emailAddress", "emailAddress").lower()
            role = col(row, "permission.role", "role")
            if addr in suspended and role in ("organizer", "fileOrganizer"):
                data_rows.append({"User": addr, "Gmail (MB)": "",
                                  "Drive (MB)": "",
                                  "Holds": f"manager of Shared Drive "
                                           f"\"{col(row, 'name')}\""})
    if data_rows:
        findings.append(Finding(
            "suspended-holding-data", "INFO",
            "Suspended accounts still holding data or drive roles",
            "These suspended accounts still hold mailbox or Drive data, or "
            "a manager role on a Shared Drive. The data is frozen with "
            "them: colleagues cannot reach it, and a drive whose only "
            "manager is suspended cannot be administered by its users. "
            "Usage figures lag about two days behind live state.",
            "Fold this into the offboarding plan: transfer mail and files "
            "to a successor, and re-point Shared Drive manager roles at "
            "active staff.",
            data_rows, "report_users.csv"))
    return findings


RISKY_SCOPES = {
    "https://mail.google.com/": "full Gmail access",
    "https://www.googleapis.com/auth/drive": "full Drive access",
}


def check_risky_oauth(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "tokens"):
        return []
    apps: Dict[str, Dict] = {}
    for row in ctx.rows("tokens"):
        matched = _risky_scope_labels(row)
        if not matched:
            continue
        client = col(row, "displayText") or col(row, "clientId")
        app = apps.setdefault(client, {"users": set(), "access": set()})
        app["users"].add(col(row, "user"))
        app["access"].update(matched)
    if not apps:
        return []
    ranked = sorted(apps.items(), key=lambda kv: -len(kv[1]["users"]))
    evidence = [{"App": name,
                 "Users": str(len(data["users"])),
                 "Access": ", ".join(sorted(data["access"]))}
                for name, data in ranked]
    return [Finding(
        "risky-oauth-apps", "MEDIUM",
        "Third-party apps holding full mailbox or Drive access",
        "These apps have been granted the widest Gmail or Drive scopes - "
        "they can read, change and delete everything in the accounts that "
        "authorised them. A breach at any one of these vendors becomes a "
        "breach of that data.",
        "Review each app: still in use, and does it genuinely need full "
        "access? Revoke the rest, and consider restricting future grants "
        "with app access control in the Admin console.",
        evidence, "tokens.csv", count=len(apps))]


def check_admin_recovery(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "users"):
        return []
    internal = set(ctx.internal_domains)
    hits = []
    for row in _super_admins(ctx):
        recovery = col(row, "recoveryEmail")
        if recovery and email_domain(recovery) not in internal:
            hits.append({"Super admin": col(row, "primaryEmail"),
                         "Recovery email": recovery})
    if not hits:
        return []
    return [Finding(
        "admin-personal-recovery", "MEDIUM",
        "Super admin accounts with personal recovery email addresses",
        "Account recovery for these admin accounts routes through a "
        "personal mailbox the organisation does not control. Whoever "
        "controls or compromises that mailbox can reset the admin "
        "password.",
        "Point admin recovery details at organisation-controlled "
        "addresses and phone numbers, or remove them and rely on a second "
        "super admin for recovery.",
        hits, "users.csv")]


def check_public_calendars(ctx: RunContext) -> List[Finding]:
    if not _module_usable(ctx, "calendaracls"):
        return []
    hits = []
    for row in ctx.rows("calendaracls"):
        # scope.type "default" is the public grant. A domain-wide reader row
        # is the tenant default and is NOT a finding.
        if col(row, "scope.type") == "default":
            hits.append({"User": col(row, "primaryEmail", "User"),
                         "Public role": col(row, "role")})
    if not hits:
        return []
    return [Finding(
        "public-calendars", "MEDIUM",
        "Primary calendars visible to anyone on the internet",
        "These calendars are shared with the public. Meeting titles, "
        "attendees and locations reveal a lot: who the organisation deals "
        "with, and when people are away.",
        "Have each user (or an admin) set the calendar's public sharing "
        "back to off; sharing inside the organisation is unaffected.",
        hits, "calendaracls.csv")]


def check_tenant_shape(ctx: RunContext) -> List[Finding]:
    """The INFO scorecard: tenant shape at a glance."""
    facts = []
    if _module_usable(ctx, "users"):
        rows = ctx.rows("users")
        active = [r for r in rows if not truthy(col(r, "suspended"))]
        facts.append({"Fact": "Users",
                      "Value": f"{len(active)} active, "
                               f"{len(rows) - len(active)} suspended"})
        facts.append({"Fact": "Super admins",
                      "Value": str(len(_super_admins(ctx)))})
    if _module_usable(ctx, "licenses"):
        facts.append({"Fact": "Licence assignments",
                      "Value": str(len(ctx.rows("licenses")))})
    if _module_usable(ctx, "groups"):
        facts.append({"Fact": "Groups", "Value": str(len(ctx.rows("groups")))})
    if _module_usable(ctx, "shareddrives"):
        facts.append({"Fact": "Shared Drives",
                      "Value": str(len(ctx.rows("shareddrives")))})
    if _module_usable(ctx, "mobile"):
        facts.append({"Fact": "Mobile devices",
                      "Value": str(len(ctx.rows("mobile")))})
    if _module_usable(ctx, "cros"):
        facts.append({"Fact": "ChromeOS devices",
                      "Value": str(len(ctx.rows("cros")))})
    if _module_usable(ctx, "vaultmatters"):
        facts.append({"Fact": "Vault matters",
                      "Value": str(len(ctx.rows("vaultmatters")))})
    if _module_usable(ctx, "vaultholds"):
        facts.append({"Fact": "Vault holds",
                      "Value": str(len(ctx.rows("vaultholds")))})
    if _module_usable(ctx, "datatransfers"):
        facts.append({"Fact": "Data transfers on record",
                      "Value": str(len(ctx.rows("datatransfers")))})
    if _module_usable(ctx, "ssoprofiles"):
        count = len(ctx.rows("ssoprofiles"))
        facts.append({"Fact": "Inbound SSO profiles",
                      "Value": str(count) if count else "none"})
    if not facts:
        return []
    return [Finding(
        "tenant-shape", "INFO", "Tenant at a glance",
        "The headline numbers for this tenant, from the collected data. "
        "Usage-report figures (storage per user) lag about two days behind "
        "live state.",
        "No action needed. This is context for the findings above.",
        facts, "multiple", count=len(facts))]


def _policy_settings(ctx: RunContext) -> List[Dict]:
    if ctx._policy_cache is not None:
        return ctx._policy_cache
    return _parse_policy_settings(ctx)


def _parse_policy_settings(ctx: RunContext) -> List[Dict]:
    """Parse policies.csv (formatjson: name,JSON) and return the RESOLVED
    settings as a list of {"type", "ou", "value"} dicts, "settings/"
    stripped.

    The Policy API returns every policy that could apply to a target, not
    the one that wins: Google's own defaults (type SYSTEM) sit alongside
    what the administrator set (type ADMIN), plus a licence-scoped copy per
    SKU. A tenant whose admin raised the password minimum still shows the
    SYSTEM default of 8 in its own row, so reading the rows as-is reports a
    weak policy that is not in force.

    Google resolves them with the Max/Merge reducer: for each field, the
    value from the policy with the greatest policyQuery.sortOrder wins
    (docs.cloud.google.com/identity/docs/concepts/policy-api-concepts).
    Admin policies carry a higher sortOrder than system ones (measured on
    a test tenant: an admin-set security.password at 201.00332 against
    three system rows at 101.000x), so merging the values of a
    (setting, OU) group in ascending sortOrder yields the setting actually
    in force.

    Licence filtering is not modelled - a policy scoped to one
    SKU is treated as applying to the whole OU. Where two SKUs in the same
    OU genuinely differ, the higher sortOrder wins and the divergence is
    invisible. Per-user resolution would need each user's licences.

    rule.* rows (DLP rules, system-defined alerts) are lists of rules, not
    reducible settings, so they keep one entry each.

    gam renders a quote inside a policy display name as \\\\" which is invalid
    JSON once the CSV layer has decoded it (seen on DLP rule names); one
    targeted repair recovers those rows, and rows that still fail to parse
    are skipped - on the dev tenant every such row is a rule.dlp or
    system-defined alert, not a settings policy.
    """
    if not _module_usable(ctx, "policies"):
        return []
    rules: List[Dict] = []
    groups: Dict[tuple, List[tuple]] = {}
    seen = set()
    for row in ctx.rows("policies"):
        raw = col(row, "JSON")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(raw.replace('\\\\"', '\\"'))
            except json.JSONDecodeError:
                continue
        setting = data.get("setting") or {}
        stype = str(setting.get("type", ""))
        if stype.startswith("settings/"):
            stype = stype[len("settings/"):]
        if not stype:
            continue
        value = setting.get("value") or {}
        query = data.get("policyQuery") or {}
        ou = str(query.get("orgUnitPath", ""))
        if stype.startswith("rule."):
            key = (stype, ou, json.dumps(value, sort_keys=True))
            if key not in seen:
                seen.add(key)
                rules.append({"type": stype, "ou": ou, "value": value})
            continue
        try:
            order = float(query.get("sortOrder", 0))
        except (TypeError, ValueError):
            order = 0.0
        groups.setdefault((stype, ou), []).append((order, value))
    out: List[Dict] = []
    for (stype, ou), entries in groups.items():
        resolved: Dict = {}
        for _, value in sorted(entries, key=lambda e: e[0]):
            if isinstance(value, dict):
                resolved.update(value)
        out.append({"type": stype, "ou": ou, "value": resolved})
    out.extend(rules)
    ctx._policy_cache = out
    return out


def check_password_policy(ctx: RunContext) -> List[Finding]:
    hits = []
    for pol in _policy_settings(ctx):
        if pol["type"] != "security.password":
            continue
        value = pol["value"]
        problems = []
        minlen = value.get("minimumLength")
        if isinstance(minlen, int) and minlen < PASSWORD_MIN_LENGTH:
            problems.append(f"minimum length is {minlen} characters")
        strength = str(value.get("allowedStrength", "")).upper()
        if strength and strength != "STRONG":
            problems.append("weak passwords are allowed")
        if value.get("allowReuse") is True:
            problems.append("password reuse is allowed")
        if problems:
            hits.append({"Org unit": pol["ou"] or "/",
                         "Problem": ", ".join(problems)})
    if not hits:
        return []
    return [Finding(
        "password-policy-weak", "MEDIUM",
        "Password policy permits weak passwords",
        f"The tenant's password rules fall short of current practice (a "
        f"minimum of {PASSWORD_MIN_LENGTH} characters, strong passwords "
        "only, no reuse). Short or reused passwords are the ones that fall "
        "to guessing and to credential lists from other sites' breaches.",
        "Raise the minimum length and disallow reuse in Admin console > "
        "Security > Authentication > Password management. Existing "
        "passwords are unaffected until changed, so pair this with 2-step "
        "verification rather than a forced reset.",
        hits, "policies.csv")]


def _duration_seconds(value: str) -> Optional[int]:
    """Policy durations arrive as strings like \"1209600s\"."""
    match = re.fullmatch(r"(\d+)s", str(value).strip())
    return int(match.group(1)) if match else None


def check_session_policy(ctx: RunContext) -> List[Finding]:
    hits = []
    for pol in _policy_settings(ctx):
        if pol["type"] != "security.session_controls":
            continue
        seconds = _duration_seconds(pol["value"].get("webSessionDuration"))
        if seconds is not None and seconds > SESSION_MAX_SECONDS:
            hits.append({"Org unit": pol["ou"] or "/",
                         "Session length": f"{seconds // 86400} days"})
    if not hits:
        return []
    return [Finding(
        "session-length", "MEDIUM",
        "Web sessions last longer than Google's 14-day default",
        "Signed-in browser sessions stay valid for longer than two weeks. "
        "The longer a session lives, the longer a stolen laptop or hijacked "
        "browser keeps working without ever seeing a password or 2-step "
        "prompt.",
        "Shorten the web session duration in Admin console > Security > "
        "Access and data control > Google session control.",
        hits, "policies.csv")]


def check_2sv_policy(ctx: RunContext) -> List[Finding]:
    """Per-OU 2SV policy. The one clear-cut signal verified on dev is
    allowEnrollment=false - users in that OU cannot switch 2SV on at all.
    Enforcement semantics (what enforcedFrom means when set to epoch) are
    NOT yet verified against a console fixture, so enforcement rows are
    reported as an INFO map rather than judged."""
    blocked, map_rows = [], []
    for pol in _policy_settings(ctx):
        if not pol["type"].startswith("security.two_step_verification"):
            continue
        setting = pol["type"].split(".", 1)[1]
        map_rows.append({"Setting": setting,
                         "Org unit": pol["ou"] or "/",
                         "Value": json.dumps(pol["value"], sort_keys=True)})
        if (setting == "two_step_verification_enrollment"
                and pol["value"].get("allowEnrollment") is False):
            blocked.append({"Org unit": pol["ou"] or "/"})
    findings = []
    if blocked:
        findings.append(Finding(
            "2sv-enrolment-blocked", "HIGH",
            "Organisational units where 2-step verification cannot be "
            "enrolled",
            "Policy in these organisational units stops users from turning "
            "on 2-step verification at all. Every account there is limited "
            "to password-only sign-in by design, whatever the users want.",
            "Allow 2-step verification enrolment for these organisational "
            "units in Admin console > Security > Authentication > 2-step "
            "verification, unless the OU exists precisely to hold such "
            "accounts and that trade-off is documented.",
            blocked, "policies.csv"))
    if map_rows:
        findings.append(Finding(
            "2sv-policy-map", "INFO",
            "2-step verification policy by organisational unit",
            "The tenant's 2-step verification policy settings as the API "
            "reports them, per organisational unit. Rows only appear where "
            "a policy is set.",
            "No action needed; check the enforcement rows match what the "
            "Admin console shows.",
            map_rows, "policies.csv"))
    return findings


def check_sharing_policy(ctx: RunContext) -> List[Finding]:
    hits = []
    for pol in _policy_settings(ctx):
        if pol["type"] != "drive_and_docs.shared_drive_creation":
            continue
        value = pol["value"]
        open_bits = []
        if value.get("allowExternalUserAccess") is True:
            open_bits.append("external people can be members")
        if value.get("allowNonMemberAccess") is True:
            open_bits.append("files can be shared to non-members")
        if open_bits:
            hits.append({"Org unit": pol["ou"] or "/",
                         "New shared drives default": ", ".join(open_bits)})
    if not hits:
        return []
    return [Finding(
        "sd-default-external", "MEDIUM",
        "New Shared Drives allow external sharing by default",
        "Tenant policy lets newly created Shared Drives take external "
        "members and share files beyond their membership. A tenant with no "
        "badly shared files today still scores clean while every future "
        "drive starts open - this is the default the next mistake inherits.",
        "In Admin console > Apps > Google Workspace > Drive and Docs > "
        "Shared drive settings, untick external and non-member access as "
        "the default; deliberately client-facing drives can be opened "
        "per drive.",
        hits, "policies.csv")]


def check_service_status(ctx: RunContext) -> List[Finding]:
    enabled, disabled = 0, []
    for pol in _policy_settings(ctx):
        if not pol["type"].endswith(".service_status"):
            continue
        service = pol["type"].rsplit(".", 1)[0]
        state = str(pol["value"].get("serviceState", ""))
        if state.upper() == "ENABLED":
            enabled += 1
        else:
            disabled.append({"Service": service, "State": state or "?",
                             "Org unit": pol["ou"] or "/"})
    if not enabled and not disabled:
        return []
    return [Finding(
        "service-status", "INFO",
        f"Google services: {enabled} enabled, {len(disabled)} disabled",
        "Which Google services the tenant switches on or off. Most tenants "
        "leave consumer services (Blogger, Photos, YouTube, Takeout) at "
        "their default of enabled without ever deciding to.",
        "No action needed. Worth a deliberate pass: services nobody uses "
        "are attack surface and data-export paths (Takeout in particular) "
        "that cost nothing to turn off.",
        disabled, "policies.csv", count=len(disabled))]


def _norm_sku(name: str) -> str:
    """Normalise a SKU name for matching `info domain` seat lines against
    licenses.csv display names ('Google Workspace Enterprise Plus' vs
    'Enterprise Plus')."""
    name = re.sub(r"\(formerly[^)]*\)", "", name.lower())
    # `info domain` prints "Workspace Enterprise Plus Licenses: 50" without
    # the leading "Google"; strip both spellings.
    for junk in ("google workspace", "workspace", "g suite", "licenses",
                 "license"):
        name = name.replace(junk, "")
    return " ".join(name.split())


def parse_owned_licences(text: str) -> Dict[str, int]:
    """Pull per-SKU seat counts out of raw `gam info domain` output
    (lines shaped like 'Google Workspace Enterprise Plus Licenses: 50').
    Unrecognised lines are ignored, so a format change yields no data
    rather than wrong data."""
    owned = {}
    for line in text.splitlines():
        match = re.match(r"\s*(.{3,}?)\s+Licenses:\s*(\d+)\s*$", line,
                         re.IGNORECASE)
        if match:
            owned[match.group(1).strip()] = int(match.group(2))
    return owned


def check_licence_waste(ctx: RunContext) -> List[Finding]:
    """Seats owned (from the preflight's `info domain` output) vs seats
    assigned (licenses.csv). Free Cloud Identity is not a seat."""
    path = ctx.run_dir / "domaininfo.txt"
    # domaininfo.txt always exists (preflight writes it); without the
    # licenses module every SKU would read as 100% unused.
    if not path.is_file() or not _module_usable(ctx, "licenses"):
        return []
    owned = parse_owned_licences(path.read_text(encoding="utf-8"))
    assigned: Dict[str, int] = {}
    for row in ctx.rows("licenses"):
        sku = _norm_sku(col(row, "skuDisplay", "skuId"))
        assigned[sku] = assigned.get(sku, 0) + 1
    hits = []
    for sku_name, seats in sorted(owned.items()):
        if re.search(r"cloud identity(?! premium)", sku_name.lower()):
            continue
        norm = _norm_sku(sku_name)
        if norm in assigned:
            used = assigned[norm]
        else:
            # Substring only as a fallback: on an exact hit it also summed
            # "Enterprise Plus - Archived User" into Enterprise Plus.
            used = sum(count for key, count in assigned.items()
                       if key and norm and (key in norm or norm in key))
        gap = seats - used
        if gap >= LICENCE_WASTE_MIN_GAP and seats \
                and gap / seats >= LICENCE_WASTE_MIN_FRACTION:
            hits.append({"Licence": sku_name, "Seats owned": str(seats),
                         "Assigned": str(used), "Unused": str(gap)})
    if not hits:
        return []
    return [Finding(
        "licence-waste", "MEDIUM",
        "Paying for licences that are not assigned to anyone",
        "The tenant owns more seats of these licences than it has assigned "
        "to users. Unassigned seats do nothing except appear on the "
        "invoice, every month, until someone notices.",
        "Reduce the seat count at the next renewal (or sooner on a "
        "flexible plan), or assign the spare seats where they are "
        "genuinely needed.",
        hits, "domaininfo.txt")]


def check_admin_roles(ctx: RunContext) -> List[Finding]:
    """Role-assignment hygiene from admins.csv: roles held by suspended or
    no-longer-resolvable accounts, how widely admin rights are spread, and
    the full who-holds-what map."""
    if not (_module_usable(ctx, "admins") and _module_usable(ctx, "users")):
        return []
    users = {col(r, "primaryEmail").lower(): r for r in ctx.rows("users")}
    active_count = len(_live_users(ctx))
    map_rows, suspended_hits, unresolved = [], [], []
    holders = set()
    for row in ctx.rows("admins"):
        role = col(row, "role")
        assignee = (col(row, "assignedToUser")
                    or col(row, "assignedToGroup")
                    or col(row, "assignedToServiceAccount"))
        ou = col(row, "orgUnit")
        scope = f"OU {ou}" if ou else col(row, "scopeType")
        map_rows.append({"Assignee": assignee or col(row, "assignedTo"),
                         "Role": role, "Scope": scope})
        if truthy(col(row, "assignedToUnknown")):
            unresolved.append({"Assigned to (ID)": col(row, "assignedTo"),
                               "Role": role})
            continue
        user_row = users.get(assignee.lower()) if assignee else None
        if user_row is not None:
            if truthy(col(user_row, "suspended")):
                suspended_hits.append({"User": assignee, "Role": role})
            else:
                holders.add(assignee.lower())
    findings = []
    if suspended_hits:
        findings.append(Finding(
            "admin-role-suspended-holder", "HIGH",
            "Admin roles still assigned to suspended accounts",
            "These suspended accounts - typically leavers - still hold "
            "admin roles. Reactivating the account, deliberately or "
            "through a compromise of the recovery path, reactivates the "
            "admin rights with it.",
            "Remove the role assignments as part of finishing the "
            "offboarding; the roles can be reassigned to active staff "
            "where the function is still needed.",
            suspended_hits, "admins.csv"))
    if unresolved:
        findings.append(Finding(
            "admin-role-unresolved", "MEDIUM",
            "Admin role assignments pointing at accounts that no longer "
            "resolve",
            "The API cannot resolve who these role assignments belong to - "
            "typically an account that was deleted while still holding the "
            "role. Stale assignments clutter the admin model and hide who "
            "actually holds power in the tenant.",
            "Review each assignment in Admin console > Account > Admin "
            "roles and delete the ones whose holder no longer exists.",
            unresolved, "admins.csv"))
    if (active_count >= ADMIN_SPRAWL_MIN_USERS
            and len(holders) / active_count > ADMIN_SPRAWL_FRACTION):
        pct = round(100 * len(holders) / active_count)
        findings.append(Finding(
            "admin-sprawl", "MEDIUM",
            f"{pct}% of active users hold an admin role",
            f"{len(holders)} of {active_count} active users hold some "
            "admin role. Every admin account is a higher-value target and "
            "a bigger blast radius when phished; rights this widely spread "
            "usually mean roles were granted to solve one ticket and never "
            "taken back.",
            "Review the role map below against who actually performs admin "
            "work, and remove the rest. Prefer narrow delegated roles over "
            "broad ones.",
            [{"User": h} for h in sorted(holders)], "admins.csv",
            count=len(holders)))
    if map_rows:
        findings.append(Finding(
            "admin-role-map", "INFO",
            f"Admin role assignments ({len(holders)} of {active_count} "
            "active users hold a role)",
            "Every admin role assignment in the tenant: who holds which "
            "role, and over what scope.",
            "No action needed; review the list for surprises.",
            map_rows, "admins.csv"))
    return findings


CHECKS = [
    check_public_files,
    check_external_file_shares,
    check_super_admin_count,
    check_admin_2sv,
    check_admin_asps,
    check_external_forwarding,
    check_orphaned_shared_drives,
    check_shared_drive_external,
    check_group_exposure,
    check_filter_forwarding,
    check_unmanaged_accounts,
    check_dns_findings,
    check_2sv_enrolment,
    check_pop_imap,
    check_dormant_accounts,
    check_mailbox_delegation,
    check_at_risk_accounts,
    check_suspended_holding_data,
    check_risky_oauth,
    check_admin_recovery,
    check_public_calendars,
    check_password_policy,
    check_session_policy,
    check_2sv_policy,
    check_sharing_policy,
    check_service_status,
    check_licence_waste,
    check_admin_roles,
    check_tenant_shape,
]


def run_checks(ctx: RunContext) -> List[Finding]:
    print_header("STAGE 2 - CHECK")
    findings: List[Finding] = []
    for check in CHECKS:
        try:
            findings.extend(check(ctx))
        except Exception as exc:
            # One broken check must not sink the report; surface it instead.
            print_error(f"Check {check.__name__} failed: "
                        f"{type(exc).__name__}: {exc}")
            findings.append(Finding(
                f"check-error-{check.__name__}", "INFO",
                f"Internal: check {check.__name__} did not run",
                f"The check raised {type(exc).__name__} while reading the "
                "collected data, so its result is unknown rather than "
                "clean.",
                "Report this to the script maintainer with the run log.",
                [], "tenant_scope.log"))
    findings.sort(key=lambda f: SEVERITY_ORDER.index(f.severity))
    for finding in findings:
        marker = {"CRITICAL": print_error, "HIGH": print_warning,
                  "MEDIUM": print_warning, "INFO": print_info}[finding.severity]
        marker(f"[{finding.severity}] {finding.title} ({finding.count})")
    return findings


###############################################################################
# RENDER
###############################################################################

SEVERITY_COLOURS = {"CRITICAL": "#c0392b", "HIGH": "#e67e22",
                    "MEDIUM": "#f1c40f", "INFO": "#3498db"}

TAMINGDNS_TOOL_LINKS = ("mx", "spf", "dkim", "dmarc")


def _evidence_table(finding: Finding) -> str:
    if not finding.evidence:
        return ""
    # Union of keys, not row 0's: evidence built from different joins (the
    # at-risk composite, the delegation map) can carry different columns.
    headers = list(dict.fromkeys(k for r in finding.evidence for k in r))
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = ""
    for row in finding.evidence:
        cells = "".join(f"<td>{escape(str(row.get(h, '')))}</td>"
                        for h in headers)
        body += f"<tr>{cells}</tr>"
    more = ""
    if finding.count > len(finding.evidence):
        more = (f"<p class='more'>Showing {len(finding.evidence)} of "
                f"{finding.count} - the full list is in "
                f"<code>{escape(finding.source)}</code> in the run "
                f"directory.</p>")
    return (f"<div class='scroll'><table><thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table></div>{more}")


def render_html(ctx: RunContext, findings: List[Finding]) -> Path:
    print_header("STAGE 3 - RENDER")
    meta = ctx.manifest["meta"]
    domain = meta.get("primary_domain", "unknown domain")
    counts = {sev: 0 for sev in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] += 1
    tiles = "".join(
        f"<div class='tile' style='border-top:6px solid "
        f"{SEVERITY_COLOURS[sev]}'><div class='num'>{counts[sev]}</div>"
        f"<div class='lbl'>{sev.title()}</div></div>"
        for sev in SEVERITY_ORDER)

    sections = ""
    for finding in findings:
        sections += f"""
<section class='finding'>
  <h3><span class='sev' style='background:{SEVERITY_COLOURS[finding.severity]}'>
  {finding.severity}</span> {escape(finding.title)}</h3>
  <p><strong>What this means:</strong> {escape(finding.meaning)}</p>
  <p><strong>What to do:</strong> {escape(finding.remediation)}</p>
  {_evidence_table(finding)}
</section>"""

    # Preflight appendix.
    preflight_rows = "".join(
        f"<tr><td>{escape(r[0])}</td><td>{escape(r[1])}</td>"
        f"<td>{escape(r[2])}</td></tr>"
        for r in ctx.manifest.get("preflight", []))

    # Modules that did not produce complete data are ALWAYS listed - a reader
    # must be able to tell "checked and clean" from "not checked", and a
    # partial module from a module that returned nothing at all.
    not_checked = ""
    for key, entry in sorted(ctx.manifest["modules"].items()):
        if entry["status"] in ("skipped", "error", "partial"):
            title = MODULE_BY_KEY.get(key, {}).get("title", key)
            note = entry.get("note", "")
            rows_n = entry.get("rows", 0)
            # A partial module WAS checked over the rows it did return; say so
            # and name the CSV, otherwise this table reads as "not audited".
            if entry["status"] == "partial" and rows_n:
                note = (f"{rows_n} row(s) collected and checked "
                        f"({key}.csv); {note}")
            not_checked += (f"<tr><td>{escape(title)}</td>"
                            f"<td>{escape(entry['status'])}</td>"
                            f"<td>{escape(note)}</td></tr>")
    unscanned = meta.get("unscanned_shared_drives", [])
    if unscanned:
        not_checked += (
            f"<tr><td>Shared Drive external scan</td><td>partial</td>"
            f"<td>{escape('; '.join(unscanned))}</td></tr>")
    not_checked_block = ""
    if not_checked:
        not_checked_block = f"""
<section class='finding'>
  <h3>Coverage gaps</h3>
  <p>These areas were not fully audited on this run, for the reason given.
  <strong>skipped</strong> and <strong>error</strong> mean no data at all -
  absence from the findings above does not mean they are clean.
  <strong>partial</strong> means the rows that did come back were collected
  and checked, and the raw rows are in the run folder's CSV; only the users
  named in the reason were missed.</p>
  <div class='scroll'><table><thead><tr><th>Area</th><th>Status</th>
  <th>Reason</th></tr></thead><tbody>{not_checked}</tbody></table></div>
</section>"""

    # DNS appendix with per-domain deep links.
    dns_block = ""
    dns_path = ctx.run_dir / "dns.json"
    if dns_path.is_file():
        try:
            dns_data = json.loads(dns_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            dns_data = {}
        rows = ""
        for dom, entry in dns_data.items():
            path = entry.get("path", "tamingdns")
            checks = entry.get("checks", {})
            summary = []
            for name in TAMINGDNS_TOOL_LINKS:
                value = checks.get(name)
                if value is None:
                    summary.append(f"{name.upper()}: not checked")
                elif "error" in (value or {}):
                    summary.append(f"{name.upper()}: check failed")
                elif "present" in value:
                    summary.append(
                        f"{name.upper()}: "
                        f"{'present' if value['present'] else 'MISSING'}")
                else:
                    grade = value.get("grade") or value.get("status") or "see dns.json"
                    summary.append(f"{name.upper()}: {grade}")
            links = " | ".join(
                f"<a href='https://tamingdns.com/{tool}?domain="
                f"{urllib.parse.quote(dom, safe='')}'>"
                f"{tool.upper()}</a>" for tool in TAMINGDNS_TOOL_LINKS)
            rows += (f"<tr><td>{escape(dom)}</td>"
                     f"<td>{escape(', '.join(summary))}</td>"
                     f"<td>{escape(path)}</td><td>{links}</td></tr>")
        if rows:
            dns_block = f"""
<section class='finding'>
  <h3>Mail DNS per domain</h3>
  <p>Checked via tamingdns.com where available (full detail in
  <code>dns.json</code>); "doh" means the fallback path ran with
  presence-only checks.</p>
  <div class='scroll'><table><thead><tr><th>Domain</th><th>Summary</th>
  <th>Checked via</th><th>Re-check</th></tr></thead>
  <tbody>{rows}</tbody></table></div>
</section>"""

    # From the manifest, not the flags: a --render-only re-run carries no
    # --include-suspended and would otherwise describe a sweep it did not do.
    included_suspended = meta.get("include_suspended",
                                  bool(ctx.args.include_suspended))
    coverage_note = ("Suspended users were included in the per-user checks."
                     if included_suspended else
                     "Per-user checks (mail settings, calendars, Drive "
                     "sharing) cover ACTIVE users only; suspended accounts "
                     "were not swept.")
    never_skipped = ctx.manifest["meta"].get("skipped_never_logged_in", 0)
    if never_skipped:
        coverage_note += (f" {never_skipped} account(s) that have never "
                          "signed in were excluded from those checks "
                          "(--skip-never-logged-in).")

    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Workspace Audit - {escape(domain)}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
         margin: 0; color: #222; background: #f5f6f8; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 24px; }}
  header.page {{ background: #1a2733; color: #fff; padding: 32px 24px; }}
  header.page h1 {{ margin: 0 0 4px; font-size: 26px; }}
  header.page p {{ margin: 0; color: #b8c4cf; }}
  .tiles {{ display: flex; gap: 16px; margin: 24px 0; flex-wrap: wrap; }}
  .tile {{ background: #fff; border-radius: 8px; padding: 16px 24px;
          box-shadow: 0 1px 3px rgba(0,0,0,.12); min-width: 110px;
          text-align: center; }}
  .tile .num {{ font-size: 32px; font-weight: 700; }}
  .tile .lbl {{ color: #667; }}
  section.finding {{ background: #fff; border-radius: 8px; padding: 16px 24px;
          margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
  .sev {{ color: #fff; font-size: 12px; padding: 2px 8px; border-radius: 4px;
          vertical-align: middle; margin-right: 6px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
  th, td {{ text-align: left; padding: 6px 10px;
          border-bottom: 1px solid #e4e7ea; }}
  th {{ background: #f0f2f4; }}
  .scroll {{ overflow-x: auto; }}
  .more {{ color: #667; font-size: 13px; }}
  footer {{ color: #667; font-size: 13px; padding: 24px; text-align: center; }}
  @media print {{
    body {{ background: #fff; }}
    section.finding, .tile {{ box-shadow: none;
          border: 1px solid #ccc; page-break-inside: avoid; }}
    a {{ color: #222; text-decoration: none; }}
  }}
</style>
</head>
<body>
<header class='page'>
  <h1>Google Workspace Audit - {escape(domain)}</h1>
  <p>Customer {escape(meta.get('customer_id', '?'))} &middot;
     collected {escape(meta.get('collected_at', 'unknown'))} &middot;
     rendered {datetime.now().strftime('%Y-%m-%d %H:%M')} &middot;
     tenant_scope.py v{SCRIPT_VERSION} (read-only audit)</p>
</header>
<div class='wrap'>
  <div class='tiles'>{tiles}</div>
  <section class='finding'>
    <h3>How to read this report</h3>
    <p>Findings are ordered by severity. Each one says what was found, why
    it matters, and what to do about it, with a sample of the affected
    items; full lists sit in the CSV files next to this report.
    {escape(coverage_note)}</p>
  </section>
  {sections}
  {dns_block}
  {not_checked_block}
  <section class='finding'>
    <h3>Preflight checks</h3>
    <div class='scroll'><table><thead>
    <tr><th>Check</th><th>Result</th><th>Consequence</th></tr></thead>
    <tbody>{preflight_rows}</tbody></table></div>
  </section>
</div>
<footer>Produced by tenant_scope.py v{SCRIPT_VERSION} -
Paul Ogier, Outsource House (osh.co.za) - print this page for a PDF copy.
</footer>
</body>
</html>"""
    out_path = ctx.run_dir / "audit_report.html"
    out_path.write_text(html, encoding="utf-8")
    print_success(f"Report written: {out_path}")
    findings_csv = ctx.run_dir / "findings.csv"
    with open(findings_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["severity", "id", "title", "count", "source"])
        for finding in findings:
            writer.writerow([finding.severity, finding.fid, finding.title,
                             finding.count, finding.source])
    print_success(f"Findings CSV written: {findings_csv}")
    return out_path


###############################################################################
# CLI / MAIN
###############################################################################

def _tier_list(value: str) -> List[int]:
    try:
        return [int(t) for t in value.split(",") if t.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"tiers are numbers: {value!r}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only Google Workspace tenant audit "
                    f"(v{SCRIPT_VERSION}). Collects tenant data via GAM7, "
                    "runs a findings engine, renders a client-readable HTML "
                    "report.")
    parser.add_argument("--admin", help="Auditing admin email; used for the "
                        "service-account scope check and the Shared Drive "
                        "scans")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Root folder for run directories "
                        f"(default {OUTPUT_DIRECTORY})")
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="Existing run directory to resume (completed "
                        "modules are skipped)")
    parser.add_argument("--list", action="store_true",
                        help="List the module registry and exit")
    parser.add_argument("--only", help="Comma-separated module keys to run "
                        "(everything else skipped)")
    parser.add_argument("--skip", help="Comma-separated module keys to skip")
    parser.add_argument("--skip-tier", type=_tier_list, default=[],
                        help="Comma-separated tiers to skip, e.g. --skip-tier 3")
    parser.add_argument("--full", action="store_true",
                        help="Include the tier-4 modules (filters, vacation, "
                        "browsers, alerts, context-aware access)")
    parser.add_argument("--no-dns", action="store_true",
                        help="Skip the DNS module")
    parser.add_argument("--include-suspended", action="store_true",
                        help="Include suspended users in the per-user "
                        "modules (default: active users only, stated in the "
                        "report)")
    parser.add_argument("--grant-temp-access", action="store_true",
                        help="THE ONE WRITE: temporarily add --admin as "
                        "organizer on Shared Drives they are not a member "
                        "of, scan, then remove the grant. Without this, "
                        "those drives are reported UNSCANNED.")
    parser.add_argument("--render-only", action="store_true",
                        help="Skip collection; re-run checks and render from "
                        "an existing --run-dir")
    parser.add_argument("--skip-never-logged-in", action="store_true",
                        help="Exclude accounts that have never signed in from "
                        "the per-user scans (big tenants carrying thousands "
                        "of placeholder accounts); coverage is stated in the "
                        "report")
    parser.add_argument("--no-open", action="store_true",
                        help="Do not open the finished report in a browser "
                        "(for headless or scheduled runs)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print every GAM command without executing")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the interactive tenant confirmation "
                        "(the tenant identity is still logged)")
    args = parser.parse_args(argv)
    if args.render_only and not args.run_dir:
        # Without this the branch renders a fresh, empty directory: zero
        # findings, no coverage table, exit 0 - the one report that says
        # nothing was checked and reads as clean.
        parser.error("--render-only needs --run-dir")
    if args.grant_temp_access and not args.admin:
        parser.error("--grant-temp-access needs --admin")
    return args


def list_modules():
    print(f"tenant_scope.py v{SCRIPT_VERSION} - module registry\n")
    for tier in (1, 2, 3, 4):
        print(f"Tier {tier}:")
        for mod in MODULES:
            if mod["tier"] == tier and mod["key"] != "dns":
                flags = []
                if mod.get("scopes"):
                    flags.append("DWD")
                if mod["tier"] == 4:
                    flags.append("--full only")
                suffix = f"  [{', '.join(flags)}]" if flags else ""
                print(f"  {mod['key']:<24} {mod['title']}{suffix}")
        print()
    print("DNS:")
    print(f"  {'dns':<24} Mail DNS (MX/SPF/DKIM/DMARC) via tamingdns.com, "
          "dns.google fallback")


def open_report(path: Path, args) -> bool:
    """Open the finished report in the default browser.

    A file:// URI, not the bare path: on Linux webbrowser hands a bare path to
    the browser as a relative URL and it 404s. as_uri() needs an absolute
    path, and the default output directory is relative, so resolve first.
    """
    if args.no_open:
        return False
    try:
        opened = webbrowser.open(path.resolve().as_uri())
    except Exception as exc:                       # headless box, no browser
        print_warning(f"Could not open the report automatically: {exc}")
        return False
    if not opened:
        # webbrowser returns False rather than raising when no browser exists.
        print_warning(f"No browser found; open the report by hand: {path}")
    return opened


def main(argv=None):
    args = parse_args(argv)
    if args.list:
        list_modules()
        return 0

    if args.run_dir:
        run_dir = args.run_dir
        if not run_dir.is_dir():
            print(f"Run directory not found: {run_dir}")
            return 2
    else:
        root = args.output_dir or OUTPUT_DIRECTORY
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = root / f"tenant_audit_{stamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(run_dir)
    print_header(f"TENANT SCOPING AUDIT v{SCRIPT_VERSION}")
    print_info(f"Run directory: {run_dir}")
    if not args.render_only:
        check_for_updates()

    ctx = RunContext(run_dir, args)
    modules = selected_modules(args)

    if args.render_only:
        findings = run_checks(ctx)
        open_report(render_html(ctx, findings), args)
        return 0

    if not preflight(ctx, modules):
        print_error("Preflight failed; nothing was collected.")
        return 1

    collect(ctx, modules)
    if args.dry_run:
        print_info("Dry run complete - no data collected, no report rendered.")
        return 0
    findings = run_checks(ctx)
    report_path = render_html(ctx, findings)
    if shutdown_requested:
        # A stopped run still renders what it has, but a scheduled --yes run
        # must be able to tell "complete" from "stopped at module 3".
        print_warning("Run was interrupted; the report covers the modules "
                      f"collected so far. Resume with --run-dir {run_dir}")
        return 130

    worst = next((f.severity for f in findings
                  if f.severity in ("CRITICAL", "HIGH")), None)
    if worst:
        print_warning(f"Highest severity found: {worst}. "
                      "Open audit_report.html for the detail.")
    else:
        print_success("No critical or high findings. "
                      "Open audit_report.html for the full picture.")
    open_report(report_path, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
