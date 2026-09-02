# Live test log

One row per live round of `offboard_user.py` against a test tenant, so the
manual end-to-end layer leaves a trace in the repo. No tenant names, user
names or log excerpts here; scenario IDs refer to TEST_PLAN.md.

| Version | Date | GAM | OS / VM | Scenarios | Result | Note |
|---|---|---|---|---|---|---|
| 5.7.0 | 2026-09-02 | 7.48.01 | Linux (Ubuntu 25.10 VM) | L1, L2, L3, L9, L10, L11, L13, L14 | pass | L2 exit 1 from the pending same-domain forwarding confirmation only; unit 210 + integration 23 green |
| 5.7.0 | 2026-09-02 | 7.48.01 | Windows 11 ARM64 VM | L1, L2 | pass | same forwarding note; unit 210 + integration 23 green |
| 5.7.0 | 2026-09-02 | 7.48.01 | macOS Tahoe 26.5 VM | L1, L2 | pass | same forwarding note; unit 210 + integration 23 green |
