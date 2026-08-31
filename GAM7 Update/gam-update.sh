#!/usr/bin/env bash
# Upgrade GAM7 in place, with a rollback copy.
#
# This is a wrapper around the official installer
# (https://raw.githubusercontent.com/GAM-team/GAM/master/src/gam-install.sh),
# which it downloads and runs. Everything the upgrade itself does is upstream's
# work. What this adds is the safety net around it:
#
#   - compares installed against latest and exits without touching anything
#     when they already match
#   - copies the whole install to <dir>.bak-<old version> first, so a failed or
#     interrupted upgrade is recoverable (upstream deletes lib/ and extracts
#     over the top, with no undo)
#   - checks afterwards that the version on disk is the one that was expected
#
# GAM7 ONLY. GAMADV-XTD3 is a different project with its own installer and its
# own install folder; do not point this at one.
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

[[ -x "$GAMDIR/gam" ]] || { echo "ERROR: no gam binary at $GAMDIR/gam" >&2; exit 1; }

current=$("$GAMDIR/gam" version 2>/dev/null | head -1 | awk '{print $2}')
[[ -n "$current" ]] || { echo "ERROR: could not read a version from $GAMDIR/gam version" >&2; exit 1; }

# The unauthenticated GitHub API allows 60 requests/hour/IP and answers a
# refusal with HTTP 403 and a JSON body carrying "message", not a release. Read
# that message out rather than dying on a missing key, because "rate limit
# exceeded, try again in 20 minutes" and "GitHub is down" need different
# reactions from whoever is standing here.
release_json=$(curl -fsSL https://api.github.com/repos/GAM-team/GAM/releases/latest) || {
  echo "ERROR: could not reach the GitHub releases API. Network, or GitHub is down." >&2
  exit 1
}
latest=$(printf '%s' "$release_json" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    sys.exit("ERROR: GitHub returned something that is not JSON.")
if "tag_name" not in data:
    sys.exit("ERROR: GitHub did not return a release: %s" % data.get("message", data))
print(data["tag_name"].lstrip("v"))
') || exit 1

echo "installed: $current"
echo "latest:    $latest"
[[ "$current" == "$latest" ]] && { echo "already current, nothing to do"; exit 0; }
$DRYRUN && { echo "(dry run, stopping here)"; exit 0; }

backup="$GAMDIR.bak-$current"
[[ -e "$backup" ]] && { echo "ERROR: $backup already exists, move it first" >&2; exit 1; }
cp -a "$GAMDIR" "$backup"
echo "rollback copy: $backup"

# -l upgrades and exits before the project/auth prompts, so this never blocks.
# -p false skips the rc-file alias edit; an existing install already has the
# alias and the PATH entry.
# -d takes the PARENT of the gam7 folder, which is why dirname is used here.
installer=$(mktemp -t gam-install)
curl -fsSL -o "$installer" \
  https://raw.githubusercontent.com/GAM-team/GAM/master/src/gam-install.sh
bash "$installer" -l -p false -d "$(dirname "$GAMDIR")"
rm -f "$installer"

new=$("$GAMDIR/gam" version 2>/dev/null | head -1 | awk '{print $2}')
echo "now on: $new"
[[ "$new" == "$latest" ]] || { echo "WARNING: expected $latest, got $new" >&2; exit 1; }

# Upgrading cannot change which tenant your config points at, but you are about
# to run gam commands and this is the cheapest moment to look. If you administer
# more than one Google Workspace tenant you switch between them by pointing
# config_dir at a different folder, and nothing in gam's own output reminds you
# which one is loaded. Reading the domain back here means the answer is on
# screen before the first real command, not after it ran somewhere unexpected.
echo "--- tenant currently loaded ---"
"$GAMDIR/gam" info domain 2>&1 | head -3
