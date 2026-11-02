# R1.0 Baseline — origin/main `7bbb430` (tree `3a03f48`: R1.0's paperwork only)

Evidence class: TESTED (suites) and screenshots (regression reference only; Gautham judges the look).

## Suites

`G2_VENV=~/coco_labs_ws/r1_venv/bin/python COCO_WS=~/coco_lab_r1_ws G2_PORT=4194 tools/g2/suites.sh OUT`
(the G2 runner, unchanged), started 2026-10-31T03:45Z; machine line in [`suites/suites_baseline.txt`](suites/suites_baseline.txt):
balanced, **on battery at the start** (AC 0; AC from about 11:00Z), RTX 4050 driver 580.178.04, Node 24.21.0, Python 3.12.3.

| Suite | Result |
| --- | --- |
| coco_lab (plain venv, `-m "not gz"`) | 1161 passed, 2 deselected ([log](suites/coco_lab_venv.log)) |
| coco_lab gz tests | 2 passed |
| lab_web/tools pytest | 244 passed |
| catalog, schemas `--check`, typecheck, arena assets | pass |
| vitest | 619 passed, 80 files ([log](suites/vitest.log)) |
| native gate (CPython vs Pyodide, hash v3) | pass: 818,951 planner values and 1,436 Fetch Rush values exact ([json](suites/native_gate.json)) |
| `coco verify` + reference stars | 18 of 18 references earn their stars under Pyodide 314.0.7 |
| build twice | identical tree hash |
| v1 site fetch, update isolation | pass |
| determinism v1 (10 sessions × Chromium, Firefox, WebKit, Pyodide-in-Node) | 1,500 hashes each, 0 differences |
| terrain determinism (3 sessions) | 2,100 hashes each, 0 differences |
| screenshots, chase HUD, saved view, v1 links (50 forms + 6 archive views), replays | pass |
| packages (`scripts/run_all_package_tests.sh`) | first run **refused to start**: the R1 overlay had no test venv (the runner's own guard; [log](suites/packages.log)); re-run with `--make-venv` on the same tree: **all 12 packages passed** (coco_lab 1166, coco_lab_ros 165, coco_schemas 241, coco_web 863, coco_mission 371, coco_sim 323, coco_rl 251, gazebo_models 231, coco_perception 139, coco_config 93, custom_teleop 75, coco_moveit_config 12; [log](suites/packages_rerun.log)) |

The coco_lab step's wall time (7 h 15 min, against 25 min in G2's final run) includes time the
laptop was not running the tests (it started on battery; the clock had moved ~7 h when next
checked); it says nothing about the tests' speed. No test failed.

## Before screenshots

[`../../screens/before/`](../../screens/before/) — `lab_web/tools/r1/screens.mjs` (G1's tool plus Learn) against the
served baseline build, rendered on the RTX 4050 (ANGLE, NVIDIA; [`shots.json`](../../screens/before/shots.json)): title,
Compare, Recordings and Learn at 1440 × 900 and on the emulated Nothing Phone (1) in landscape
and portrait (emulated: viewport, touch, 4× CPU throttle on this laptop's GPU, never a phone).
Learn opens Compare's tours today (`?view=learn` redirects to `?view=compare&tour=`). The three
`play` shots show Play's mode select (G1's Play draws no canvas before a game starts, so the
tool's ready condition timed out): they are kept, labelled, and not part of the prompt's set.
