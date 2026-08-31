#!/usr/bin/env bash
# Upgrade GAM7 in place, with a rollback copy.
#
# This is a wrapper around the official installer
# (https://raw.githubusercontent.com/GAM-team/GAM/master/src/gam-install.sh),
# which it downloads and runs. Everything the upgrade itself does is upstream's
# work. What this adds is the safety net around it:
#
#   - asks GAM whether it is current and exits without touching anything when
#     it is
#   - copies the whole install to <dir>.bak-<old version> first, so a failed or
#     interrupted upgrade is recoverable (upstream deletes lib/ and extracts
#     over the top, with no undo)
#   - asks GAM again afterwards to confirm the upgrade actually landed
#
# GAM7 ONLY. GAMADV-XTD3 is a different project with its own installer and its
# own install folder; do not point this at one. Windows users want
# https://github.com/NoSubstitute/gamupdate instead of this script.
#
# Credentials are NOT touched: the binary lives in the install dir while gam.cfg
# (~/.gam) and the config_dir it points at (holding client_secrets.json,
# oauth2.txt and oauth2service.json) sit elsewhere. The installer only writes
# into the target folder.
#
# Usage: gam-update.sh [-d <install dir>] [-n]
#   -d  install dir (default $HOME/bin/gam7, which is where the official
#       installer puts GAM unless you gave it -d as well)
#   -n  dry run: report installed vs latest, change nothing
#
# Rollback: rm -rf <dir> && mv <dir>.bak-<version> <dir>

set -euo pipefail

GAMDIR="$HOME/bin/gam7"
DRYRUN=false
while getopts "d:n" o; do
  case "$o" in
    d) GAMDIR="${OPTARG%/}" ;;
    n) DRYRUN=true ;;
    *) echo "usage: $0 [-d <install dir>] [-n]" >&2; exit 2 ;;
  esac
done

# The default is deliberately a path, not a lookup. `command -v gam` finds
# nothing on a working macOS or Linux install, because the official installer
# writes a shell ALIAS into the rc files rather than putting gam on PATH, and an
# alias does not exist inside a non-interactive script.
[[ -x "$GAMDIR/gam" ]] || { echo "ERROR: no gam binary at $GAMDIR/gam" >&2; exit 1; }

# GAM does its own release check: exit 1 means a newer version exists, exit 0
# means this is the latest. That replaces querying the GitHub API here, along
# with its 60-requests-per-hour limit on unauthenticated callers.
#
# Any other exit code means gam did not run, so the answer is unknown. Treating
# an unknown as "up to date" is the trap: a check that never ran then reads as
# success and the upgrade is skipped silently, for as long as whatever broke
# stays broken.
set +e
checkoutput=$("$GAMDIR/gam" version checkrc 2>&1)
rc=$?
set -e

case "$rc" in
  0|1) ;;
  *)   echo "ERROR: could not run '$GAMDIR/gam version checkrc' (exit $rc)." >&2
       echo "$checkoutput" >&2
       exit 1 ;;
esac

# gam can also exit 0 having failed to reach GitHub, which would look identical
# to "you are on the latest version". The Latest: line only appears when the
# check actually completed.
grep -q "Latest:" <<<"$checkoutput" || {
  echo "ERROR: GAM's version check did not complete. GAM said:" >&2
  echo "$checkoutput" >&2
  exit 1
}

current=$(awk '/Current:/ {print $2; exit}' <<<"$checkoutput")
latest=$(awk '/Latest:/ {print $2; exit}' <<<"$checkoutput")
echo "installed: $current"
echo "latest:    $latest"

[[ "$rc" -eq 0 ]] && { echo "already current, nothing to do"; exit 0; }
$DRYRUN && { echo "(dry run, stopping here)"; exit 0; }

backup="$GAMDIR.bak-$current"
[[ -e "$backup" ]] && { echo "ERROR: $backup already exists, move it first" >&2; exit 1; }
cp -a "$GAMDIR" "$backup"
echo "rollback copy: $backup"

# -l upgrades and exits before the project/auth prompts, so this never blocks.
# -p false skips the rc-file alias edit; an existing install already has the
# alias and the PATH entry.
# -d takes the PARENT of the gam7 folder, which is why dirname is used here.
# Plain mktemp, no -t: BSD mktemp on macOS appends randomness to a template
# without X's, GNU mktemp on Linux rejects it with "too few X's in template".
installer=$(mktemp)
curl -fsSL -o "$installer" \
  https://raw.githubusercontent.com/GAM-team/GAM/master/src/gam-install.sh
bash "$installer" -l -p false -d "$(dirname "$GAMDIR")"
rm -f "$installer"

# Ask GAM again rather than trusting the installer's own report. Exit 0 now
# means it considers itself current, which is the upgrade having landed.
set +e
"$GAMDIR/gam" version checkrc >/dev/null 2>&1
newrc=$?
set -e
new=$("$GAMDIR/gam" version 2>/dev/null | head -1 | awk '{print $2}')
echo "now on: $new"
[[ "$newrc" -eq 0 ]] || { echo "WARNING: still not on the latest version after upgrading (expected $latest, on $new)" >&2; exit 1; }

# Upgrading cannot change which tenant your config points at, but you are about
# to run gam commands and this is the cheapest moment to look. If you administer
# more than one Google Workspace tenant you switch between them by pointing
# config_dir at a different folder, and nothing in gam's own output reminds you
# which one is loaded. Reading the domain back here means the answer is on
# screen before the first real command, not after it ran somewhere unexpected.
echo "--- tenant currently loaded ---"
"$GAMDIR/gam" info domain 2>&1 | head -3
