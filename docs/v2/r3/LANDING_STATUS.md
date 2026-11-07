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

| step | state | evidence |
| --- | --- | --- |
| PR #32 (R2) merged | **done 2026-11-06**, merge commit `5df4427`; exact head `fc31c3e` green (CI 42256398076, Lab 42256398104); local suites on that tree: 12/12 packages, tools 263, vitest 640, build, check_dist 0 | self-review comment on #32 |
| PR #31 retargeted to main | done (REST API; `gh pr edit` failed on the classic-Projects deprecation) | |
| gap 1: the writer's own `result.json` broke both scope checks | fixed by **PR #33** (merged `90c3dce`) | |
| gap 2: the committed leaderboard index went stale when a result was committed | fixed by **PR #34** (merged `bbc94ca`): the index is generated at build | |
| gap 3: the generated index carried Theta\*'s `paper` URL into the site; `check_dist` refused it (twice: the intermediate shipped too) | fixed by **PR #35** (merged `56e9318`) | Lab run 42335350980 |
| PR #31 merge | **done 2026-11-07**, merge commit `adde736` (exact head `10488e0` all green; verified: public 100/100, ratio 0.978, held-out 20/20) | self-review on #31 |
| deploy + live smoke | **done**: deploy run 42356268133 (success); live smoke PASS (attempt 3; attempt 1 proved "New version ready" in an open tab) | [`data/deploy1/`](data/deploy1/README.md) |
| real phone | not connected: pending | |

Notes: each main merge into #31 moves its merge-base, which R2's public-salt held-out seed hashes, so the trusted
writer re-commits a new `result.json` (same-repository branch: overwritten, as #33 intends) and the bot commit's
runs wait for approval (approved through the API). The writer does not run again for the bot's own commit.
