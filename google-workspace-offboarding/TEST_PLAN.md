# Test plan

Three layers. The first two run anywhere with no tenant; the third needs a
test tenant and is done by hand.

## 1. Unit tests: `test_offboard_user.py`

Stdlib only, offline, a few seconds. Every gam, GYB and rclone call is
stubbed, and a module-level guard fails any test that reaches a real
subprocess. Fixtures under `fixtures/` are captured GAM 7.48.01 output
(domain rewritten to `yourdomain.com`); when GAM changes a format, recapture
the fixture rather than editing it by hand.

    python3 test_offboard_user.py

## 2. Integration tests: `test_offboard_main.py`

Drives `main()` end to end with a scripted gam and asserts the order of
commands, the exit code and the summary for the scenarios that only the
orchestrator decides: phase order, the licence hold after a failed transfer,
the forced suspension when containment fails, Ctrl+C during the kill switch,
the scorched-earth Shared Drive gate, the temporary-unsuspend contract, and
restore-only mode.

    python3 test_offboard_main.py

Both suites run in GitHub Actions on Ubuntu and Windows, Python 3.8 and 3.12.

## 3. Live scenarios (manual, test tenant)

The commands, the fixture users they need and the expected outcome for each
scenario are in `offboarding_test_setup_guide.md`, Step 5. Scenario IDs used
in `LIVE_TEST_LOG.md`:

| ID | Scenario | Expected |
|---|---|---|
| L1 | Dry run on a clean user | exit 0, no writes, snapshot written |
| L2 | Live run, clean user, one destination for everything | exit 0, every phase verified |
| L3 | Already-suspended user with `--force --unsuspend --no-transfer` | re-suspended and verified at the end |
| L4 | Admin user | refused before any change unless `--allow-admin-account` |
| L5 | `--force` without a destination | exit 2 before any change |
| L6 | 2SV-enrolled user | 2SV off, or the policy refusal reported plainly |
| L7 | `--backup-drive` then transfer | backup reconciled against Drive, then ownership moved |
| L8 | `--backup-email` only | GYB archive verified against msg-db |
| L9 | `--no-transfer` | containment and suspension only |
| L10 | Scorched earth on a throwaway user | deleted, snapshot kept |
| L11 | Scorched earth with a sole-organized Shared Drive | exit 2, account untouched |
| L12 | Short Drive backup (same-name files) | exit 1, licence held |
| L13 | Ctrl+C during the kill switch | containment completes, run stops after it |
| L14 | Ctrl+C after a temporary unsuspend | account re-suspended before exit |

Run each on every OS the script claims (Windows, Linux, macOS) before a
release, and add one row per OS to `LIVE_TEST_LOG.md`.
