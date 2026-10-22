# G1.13 evidence — the laptop

Gautham's laptop prompt of 2026-10-22 ([`../../G1_LAPTOP_PROMPT.md`](../../G1_LAPTOP_PROMPT.md)).
Machine: Acer laptop, 13th Gen Intel Core i5-13420H, NVIDIA GeForce RTX 4050 Laptop GPU (driver
580.178.04) + Intel Raptor Lake-P graphics (Mesa 25.2.8-0ubuntu0.24.04.2), Ubuntu 24.04, kernel
6.8.0-147-generic, ROS 2 Jazzy, gz CLI 14.9.0; **balanced** power profile, **on AC** (recorded per
measurement in each JSON's `machine` fields). Worktree `~/coco_labs_ws/worktrees/g1`, colcon
overlay `~/coco_lab_g1_ws` (`--symlink-install`), CI-style venv `~/coco_labs_ws/g1_venv`
(setuptools 84.0.0, coco_lab, `coco_lab/requirements-test.txt`).

## 1. Gautham's decisions on the G1.12 questions

**Spawn heading.** `tools/g1/make_fetch_rush_rounds_r3.py`: the start faces the clear heading
(of 16; free run ≥ 2.1 m on the plan grid) closest to the direction from the start to the first
route's point 1 m along it; the start point is unchanged (the zone's roomiest free cell, ≥ 1.5 m
from the lanes). Loading dock: 337.5° (first route −27°: to `obj_dock`); Workshop: 315.0° (to
`obj_maze_2`). Test: `coco_lab/test/test_fetch_rush_r3.py::test_the_start_faces_the_clear_heading_nearest_the_first_route`
(12 rounds).

**Phone budget.** [`phone_budget_sweep.json`](phone_budget_sweep.json), made by
`tools/g1/sweep_phone_budget.py` (MODEL, CPython 3.12, hash v3): every whole metre from 22 m to
the longest trip in the lane-free table (82 m); per budget the six seeds' rounds, each drawn,
played by the reference bot and timed exactly as the generator does (`make_round`), the longest
planned round first, stopping at the first timer over 300 s. **No budget qualifies** (≥ 3
distinct rounds AND every timer ≤ 5:00):

| Budget | Distinct rounds drawn | Verdict |
|---|---|---|
| 22–25 m | 1 | 1 distinct round (timers 273.5 s at 22–24 m, 275.9 s at 25 m) |
| 26–28 m | 4 | seed 6 (Workshop): timer 349.1 s > 300 s |
| 29–31 m | 5–6 | seed 6: 365.7 s |
| 32–35 m | 6 | seed 6: 385.5 s |
| 36–44 m | 6 | seed 3: 446.1–457.3 s |
| … 82 m | 6 | seed 4: up to 653.1 s |

So 22 m stands (the decision's fallback): one round, `obj_dock` → Dock 1, `obj_dispatch` →
Dispatch, reference 182.3 s, **timer 273.5 s (4:33.5)**. The rounds file was regenerated
(phone and Full shift; no draw rejected); the table is in
[`docs/v2/m6/GAMES.md`](../../../m6/GAMES.md#fetch-rush-rules-3-g112-gauthams-2026-10-22-decisions).

**Camera look**: approved (BEFORE_AFTER "After G1.12"); nothing changed.

## 2. ROS package suites and the gz tests

- `scripts/run_all_package_tests.sh` in `~/coco_lab_g1_ws` (ROS_DOMAIN_ID 78): every package
  passed except coco_lab's three ament linters (flake8 19 + pep257 12 + copyright 5 findings,
  all in G1's cloud commits; the cloud and CI's plain venv never run them). Fixed in `9cbcea7`
  without changing code paths; the final counts are in [`suites.txt`](suites.txt).
- `pytest -m gz` (coco_lab): [`gz_tests.txt`](gz_tests.txt) — **2 passed, 0 skipped** (gz 14.9.0).
