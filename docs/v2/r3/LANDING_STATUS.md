# R3 Part A · Landing R2 — status

Prompt: R3 prompt Part A (saved with Part B as [`R3_PROMPT.md`](R3_PROMPT.md) once R3 starts).
Branch `v2/r2-byoa` (PR #32). Worked from the `~/coco_labs_ws/worktrees/r1` checkout (local branch
`land/r2-byoa`, pushed to `v2/r2-byoa`): this session was pinned to that worktree and could not enter
`worktrees/r2`; the r2 worktree itself is untouched (its local branch simply lags the remote).

Machine at start (2026-11-06): AC online, power profile **power-saver** → set to **balanced** for the session
(restore power-saver at the end); no simulator running; Nothing Phone (1) **not connected** (`adb devices`
empty); 5.5 GB disk free.

## A0 · Standing authority

Recorded in README §9 ("Standing merge and deploy authority"), AGENTS.md (Git section) and `docs/STATUS.md`.

## A1 · Gautham's answers — see [R2_RESULTS "Gautham's answers"](../r2/R2_RESULTS.md)

| # | State |
| --- | --- |
| 1 D\* Lite exact | **done**: `Builtin.summation` + `measure_path(..., summation)`; `test_api_equivalence.py` 13/13 with exact equality (6 D\* Lite scenarios); no native result, hash or golden changed |
| 2 Theta\* costmap re-run | R3 (Gazebo), recorded in R3_STATUS |
| 3 stock + snapped Nav2 | R3 (Gazebo), recorded in R3_STATUS |
| 4 Studio view first on phone landscape | **done**: `studio_check.mjs` 13/13 (new assertion; emulated view y 323 / 412 px), [screens](screens/a1/) |
| 5 other questions | decided and recorded (3D view parked for R4; controller/localiser reference entries in R3) |

## A2 · Fixes before merging

| Fix | State |
| --- | --- |
| 1 double-build check (main red since R1) | fixed in R2.9 (`c23ace6`: narrow allow-list of three never-fetched URLs; suites runner `pipefail`); re-checked here: `check_dist` 0 failures; PR #32's lab_web job green on `c23ace6` |
| 2 Studio light theme contrast (92) | fixed in R2.9 (`7eaa7b6`); accessibility 24 pages 0 failures (R2.9) |
| 3 lint in the exporter and starters | fixed in R2.7/R2.9; package run with lint 1308 passed (R2.9); re-run in this landing's suites |
| 4 ROS 2 CI setup hardening | **done**: apt retries/timeouts + bounded (20 min) setup with two retries after `dpkg --configure -a`; job limit 90 → 100 min |
| 5 the Theta\* submission test | **done**: passes cleanly with no submission committed and is never vacuous (the layout rule is checked on a made-up submission too). A first attempt used `pytest.skip`; the Lab workflow allows **no skips** in `lab_web/tools` (so a skip cannot hide a test), and failed it (run 42250916620) — so no skip. |

## A3 · Merge and deploy

Pending: exact-head CI on the landing head, then merge PR #32 (merge commit), retarget PR #31, deploy, live smoke.
