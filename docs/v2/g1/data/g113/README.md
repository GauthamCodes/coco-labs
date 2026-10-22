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

## 3. AUTO press → motion: model-tick gaps (target: none over 100 ms)

`lab_web/tools/g1/fetch_timing.mjs` (the page's own keys: AUTO / GRAB / AUTO / DROP), desktop
1280 × 720, `tier=low`, **NVIDIA RTX 4050** (`G1_GPU=nvidia`, renderer recorded in each file),
balanced, on AC. Run back to back. Sharing the machine (recorded in each `machine` field):
Gautham's Brave browser (two renderers at ~45 % CPU) and the desktop on the NVIDIA GPU (Xorg
14–20 % SM, gnome-shell 14–19 %). The model's tick period is 100 ms.

| | Before (`a4b39a6`, rules 2 shift 1) | After, phone round 1 | After, Full shift 1 | Fix, phone round 1 | Fix, Full shift 1 |
|---|---|---|---|---|---|
| File | [`timing_before.json`](timing_before.json) | [`timing_after_phone.json`](timing_after_phone.json) | [`timing_after_full.json`](timing_after_full.json) | [`timing_fixed_phone.json`](timing_fixed_phone.json) | [`timing_fixed_full.json`](timing_fixed_full.json) |
| AUTO presses | 8 | 5 | 8 | 5 | 8 |
| Max tick gap around a press (worker message) | **269 ms** | **162 ms** | **132 ms** | 131 ms | 147 ms |
| … as the game receives the tick (G1.13 fix) | — | — | — | **119 ms** | **141 ms** |
| Worker step, max | 261.5 ms | 79 ms | 85.8 ms | 69.7 ms | 79.8 ms |
| All gaps (game side): p95 / max / over 110 ms | — | — | — | 107.2 / 137.5 / 75 of 1,993 | 107.8 / 143.1 / 109 of 3,474 |
| All arrivals (worker message): p95 / max | 113.1 / 269.2 | 117.7 / 162.2 | 117.5 / 155.3 | 114.9 / 139.4 | 115.4 / 175.8 |
| "Clock waits" banner | never | never | never | never | never |
| Deliveries | 3/3 | 2/2 | 3/3 | 2/2 | 3/3 |

**The target is not met** — before, after, or after the one fix.

**Cause** ([`timing_diagnosis_phone.json`](timing_diagnosis_phone.json): the head build with
every step's send time recorded): sends kept their cadence (send gap median 100.0, p95 106.9,
max 108.9 ms: the 10 ms pump); send → arrival = the worker's step + ≤ 5 ms; so every gap over
130 ms was a ~100 ms send gap plus a step 25–62 ms longer than the one before (step median
28 ms, max 88 ms). Half of all gaps exceeded 100 ms, AUTO or not: a tick was shown the moment
the worker finished it. The AUTO tick itself no longer stalls (worker step ≤ 86 ms, was 262 ms).

**The fix (once):** `lab_web/src/game/session.ts` sends an ordinary tick `lead` ms before it is
due (the 90th percentile of the last 32 send→arrival times + 5 ms, ≤ 80 ms) and hands it to the
game at its due time; a tick an input starts is still sent and shown at once.
`lab_web/test/g1_session_pacing.test.ts` (4 cases) checks it with a scripted worker.
**Re-measured:** game-side gaps p95 118 → 107 ms and over 110 ms from 13 % to 3.8 % of gaps; the
largest gap around a press 119 ms (phone) and 141 ms (Full shift). What remains: a step longer
than the lead (by construction about one in ten) is shown late; and with a timer-paced schedule
about half of the game-side gaps are 100.x ms, so "never over 100.0 ms" cannot hold literally.

**Touch-to-motion** (`tools/g1/input_check.mjs --only-latency --latency-trials 40`, emulated
Nothing Phone (1) viewport + touch + 4× CPU throttle, NVIDIA): after the fix, G1 Play median
**40.8 ms** (p90 46.9, 15 samples; [`latency_after/checks.json`](latency_after/checks.json)),
M5's Play in the same run 63.1 ms. The `a4b39a6` build gave only 2 samples of 40 (36.3 ms;
[`latency_before/checks.json`](latency_before/checks.json)) — too few to compare; M5's page
moved 47.4 ↔ 63.1 ms between runs. No evidence of added latency; not a controlled A/B.
