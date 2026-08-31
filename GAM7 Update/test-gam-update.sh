#!/usr/bin/env bash
# Self-check for gam-update.sh's version-check logic.
#
# Runs the script in dry-run mode against a stub `gam` that reproduces GAM's
# real output and exit codes, so no GAM install and no network are needed.
#
# The case that matters is `crash` and `nonet`: a check that did not run must be
# an error. If either of those starts exiting 0, the script has regained the bug
# where an unknown state reads as "up to date" and upgrades are skipped in
# silence.
#
# Usage: ./test-gam-update.sh

set -uo pipefail
cd "$(dirname "$0")"
SCRIPT_UNDER_TEST="$PWD/gam-update.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/gam7"

make_stub() {
  case "$1" in
    current) body='Version Check:\n  Current: 7.48.01\n   Latest: 7.48.01'; code=0 ;;
    behind)  body='Version Check:\n  Current: 7.43.04\n   Latest: 7.48.01'; code=1 ;;
    crash)   body=''; code=139 ;;
    # gam can reach the end of its own check without contacting GitHub, printing
    # no Latest: line and still exiting 0. Indistinguishable from "current" if
    # the exit code is all you look at.
    nonet)   body='Version Check:\n  Current: 7.43.04'; code=0 ;;
  esac
  {
    echo '#!/usr/bin/env bash'
    echo 'if [[ "$1" == "version" && "$2" == "checkrc" ]]; then'
    if [[ "$1" == "crash" ]]; then
      echo '  echo "Segmentation fault" >&2'
    else
      printf '  printf %s\\\\n "%b"\n' "'%s'" "$body"
    fi
    echo "  exit $code"
    echo 'fi'
    echo 'echo "GAM 7.43.04 - https://github.com/GAM-team/GAM - pyinstaller"'
  } > "$tmp/gam7/gam"
  chmod +x "$tmp/gam7/gam"
}

fail=0
check() {
  local scenario="$1" want_rc="$2" want_text="$3"
  make_stub "$scenario"
  local out rc
  out=$(bash "$SCRIPT_UNDER_TEST" -d "$tmp/gam7" -n 2>&1); rc=$?
  if [[ "$rc" -ne "$want_rc" ]]; then
    echo "FAIL $scenario: exit $rc, wanted $want_rc"; echo "$out" | sed 's/^/      /'; fail=1; return
  fi
  if ! grep -q "$want_text" <<<"$out"; then
    echo "FAIL $scenario: output did not contain '$want_text'"; echo "$out" | sed 's/^/      /'; fail=1; return
  fi
  echo "ok   $scenario (exit $rc)"
}

check current 0 "already current"
check behind  0 "dry run"
check crash   1 "could not run"
check nonet   1 "did not complete"

[[ "$fail" -eq 0 ]] && echo "all checks passed" || echo "CHECKS FAILED"
exit "$fail"
