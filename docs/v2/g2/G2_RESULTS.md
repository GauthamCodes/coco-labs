# G2 · Sim Identity — results

Prompt: [`G2_PROMPT.md`](G2_PROMPT.md) · state: [`G2_STATUS.md`](G2_STATUS.md) · before/after:
[`BEFORE_AFTER.md`](BEFORE_AFTER.md). Branch `v2/g2-sim-identity` from `origin/main` `7475896`.
Evidence classes as AGENTS.md: **MODEL** (the browser model), **STACK** (recorded ROS 2 in
Gazebo, never hardware), MEASURED, EMULATED, UNRESOLVED.

**Still owed:** a quiet-laptop re-run of the Full-shift timing (below) and five Gazebo runs of each final phone round (both need a
quiet laptop on mains power); the touch-to-motion samples over 1 s are UNRESOLVED (below).

## Checkpoints

| Checkpoint | Result | Evidence |
| --- | --- | --- |
| G2.0 Baseline | done | [`data/g20/README.md`](data/g20/README.md) |
| G2.1 Decisions | done | [`data/g21/README.md`](data/g21/README.md) |
| G2.2 GAME \| SIM | done; real phone SIM 60 fps | [`data/g22/README.md`](data/g22/README.md), [`screens/g22/`](screens/g22/) |
| G2.3 Telemetry | done | same |
| G2.4 Panels | done | same |
| G2.5 rosbag2 export | done | [`data/g25/README.md`](data/g25/README.md) |
| G2.6 Gazebo + Nav2, ghosts, Race Nav2 | done | [`data/g26/DIAGNOSIS.md`](data/g26/DIAGNOSIS.md), [`data/g26/GATE.md`](data/g26/GATE.md), [`screens/g26/`](screens/g26/) |
| G2.7 Looks | done; real phone GAME 60 fps median | [`data/g27/budgets.json`](data/g27/budgets.json), [`screens/g27/`](screens/g27/) |
| G2.8 Close | done except the AUTO-gap re-measure and the per-round Gazebo gate | this file, [`data/g28/`](data/g28/) |

## Decisions applied (G2.1) — MODEL

- **Crossings:** routes may cross the east–west forklift lane only at a marked crossing, never run
  along it (Fetch Rush **rules 4**; rules 3 and its records unchanged). Measured: both marked crossings
  are the walkers' own paths, and **0 of 600** start times let COCO cross clear of the walker, so both
  are closed and **no route crosses the lane**. (Question 1 below.)
- **Phone budget 26 m.** No budget from 22 m to 81 m gives ≥ 3 distinct rounds with every timer ≤ 5:00
  (the 5:00 sweep, continued past G2's choice, had reached 92 m with none qualifying); **26 m is the smallest giving them ≤ 6:00**: 4 distinct rounds —
  loading dock (seeds 2, 4, 5) 4:35.9 · workshop (3) 4:59.1 · workshop (1) 5:31.4 · workshop (6) 5:49.1.
- **AUTO stall 119–141 ms:** accepted, open. Re-measured (G2.8, `tools/g1/fetch_timing.mjs`, NVIDIA, desktop,
  low tier, AC; [`data/g28/auto_gap/`](data/g28/auto_gap/)): the largest tick gap around an AUTO press as the game
  shows it is **117 ms** (phone round, G1.13: 119) and **116 ms** (Full shift, G1.13: 141) — G2 did not make it
  worse. **But** the Full-shift run also had one 332 ms gap and a 272 ms worker step away from AUTO (G1.13's
  Full shift: max 143 ms); it ran while two build/generation jobs shared the laptop, so it is **UNRESOLVED**
  whether that is G2 or the load — to re-measure on a quiet laptop.
- **Heavy settings on phones:** one-tap "Switch to recommended settings" toast after 10 s under
  55 fps; never silent (`fps_watch.ts`, tested).
- **Old phone screenshots in history:** accepted, no rewrite.

## GAME | SIM — MODEL

- **GAME** keeps G1's look plus faint LiDAR rays and hits, the footprint ring, base_link's TF axes and a
  thin global plan.
- **SIM** (V key or the switch) is RViz-like: dark grid, flat translucent world, TF frames with labels
  (map, odom, base_footprint, base_link, lidar_link and the arm's URDF links), LaserScan points by
  range, Map, global and local costmaps in RViz's costmap palette, global plan, the commanded arc
  (the model samples no local candidates, and says so), footprint, goal arrow and an RViz orbit
  camera. Play has no localiser (belief = truth), so no particle cloud or ellipse is drawn — said in
  the Learn text.
- **Frame rate:** laptop (NVIDIA RTX 4050, high tier, balanced, AC) **60 fps in both views** (median
  frame 16.6 ms; SIM p99 18.9 ms). **Real phone, SIM view, every display on: 60 fps** (2 min: median
  60, min 60, p99 19.6 ms, 0 frames over 50 ms) — after fixing a defect the phone found (below).
- **Budgets** (`tools/g1/budgets.mjs`, now with SIM view): within every stated budget; the Depot's
  maximum draw calls 62 (low) / 204 (high), SIM view 33 / 103.

## Telemetry, console, panels — MODEL

Telemetry strip (`/cmd_vel` v ω · `/odom` x y θ · sim time), Gazebo-style bar (desktop, SIM view:
sim time, real time, RTF, iterations), `/rosout` from model events only with the model graph's node
names; panels Displays, ROS 2 graph (model of COCO's stack, Stack counterparts as text), Topic echo
(`ros2 topic echo` YAML), Plot, Learn. The TypeScript ROS shapes equal `coco_lab.ros_shapes` field by
field (1e-12) in CI. Panels never reach STOP (measured on desktop, emulated phone and the real phone's
710 × 269 tab size).

## rosbag2 export — MODEL file, checked with real ROS 2 tools

"SAVE AS ROSBAG2 (MCAP)" in the pause menu and on results. From a real browser run: `ros2 bag info`
accepts it (mcap, jazzy, 1,955 messages); `ros2 bag play` publishes `/scan` at 10.000 Hz with `/map` and
`/tf_static` latched; RViz shows map, scan, TF and plan (Global Status Ok). The CDR bytes equal
`rclpy`'s for all 7 message types. Inside the file: `evidence: MODEL`, "no ROS 2 ran". Foxglove not
tried (not installed).

## Gazebo + Nav2 — STACK

- **Cause of the Dock 1 failure:** AMCL updated only every 0.25 m / 0.2 rad, so one leg's wrong
  likelihood peak (0.15–0.30 m south while driving east and turning at the pick) captured it, helped by
  an unmapped crate (`bad_crate`) crossing the scan plane. AMCL ended 0.35–0.40 m south-west, putting
  the believed pose inside the inscribed radius at the 0.8 m pallet gap: 205 START_OCCUPIED.
- **Ruled out by measurement:** map origin and resolution, the SDF's collision boxes, scan stamps,
  and wheel odometry (it over-counts rotation by 14.5 %, but AMCL with perfect odometry drifts more).
  A "COCO sees itself" reading was **retracted** (0.00 close returns per scan on open floor).
- **Fix (generated files only, derivation 2):** AMCL `update_min_d` / `update_min_a` 0.05 and the crate
  in the map. Derivation 1 still verifies identical; the reference copies are untouched.
- **Result:** Dock 1 round **5 of 5** fresh-simulator runs (20/20 legs; M6F.8: 0 of 2). The final phone
  rounds: one recorded run each, **16/16 legs**. Five runs are not a rate. **Residual AMCL bias up to
  0.28 m remains, unexplained.**
- **Ghosts** (`lab_web/public/stack/ghosts/`, sha256 in `index.json`): `r4_phone_seed1.json`
  `f0f2ccd600d4…`, `r4_phone_seed2.json` `9afd627d83ac…`, `r4_phone_seed3.json` `227d6ee2e9b5…`,
  `r4_phone_seed6.json` `5f548d4e31ad…`. Race Nav2 is offered on the mode select and at
  `?race=nav2`; results add a three-way card (you · planner MODEL · Nav2 in Gazebo STACK, "driving only,
  no grasp; actors parked; never hardware"). Nav2 drives the three workshop rounds in 347–412 s,
  longer than their timers; the loading-dock round in 166.3 s.

## Looks — MODEL

Environment map (procedural `RoomEnvironment`), polished floor and GTAO ambient occlusion on high
only, COCO's metal / plastic / rubber materials (wheel and arm motion are G1's — the model's wheel speeds and
arm joint states; G2 added no motion and did not re-measure the wheels' direction), the title "COCO Lab · a ROS 2 robot you can drive in your browser" with plain-text
badges and an ⓘ that says the browser does not run ROS 2, and a "what the planner computed" inset on
results. Before / after: [`BEFORE_AFTER.md`](BEFORE_AFTER.md).

## Tests and determinism

`tools/g2/suites.sh` on tree `5c77bbe` (laptop, balanced, AC; [`data/g28/suites.txt`](data/g28/suites.txt)):

| Suite | Result |
| --- | --- |
| coco_lab (CI venv route) / gz | 1108 passed / 2 passed (G2.0: 1077 / 2) |
| `pytest lab_web/tools` | 235 passed, **1 failed** → fixed (`test_g2_ghosts` assumed a track starts at t = 0; the first truth pose is at 0.01 s) |
| vitest, typecheck, schemas, catalog, arena assets, build twice (same hash), check_dist | pass |
| native gate (CPython vs Pyodide, hash v3) | planners 818,951 / 818,951 exact; fetch_rush 1,436 / 1,436 exact |
| coco verify + play references | 18 of 18 earn their stars |
| determinism v1 (10 M1 sessions) | 1500 ticks × Chromium / Firefox / WebKit / Pyodide-Node, 0 mismatches, hash `9a9d582d03f4` |
| determinism terrain (3 M4 sessions) | 2100 ticks × the same four, 0 mismatches, hash `3a8c227eca45` |
| screenshots, replays, v1 links (50 forms), update isolation | pass |
| chase HUD + SIM pass (3 profiles × 20 poses) | 0 failed |
| saved SIM view (new, G2.8) | pass on desktop and phone landscape |
| ROS packages | functional tests all pass; **ament lint failed** in coco_lab (flake8 + pep257) and coco_lab_ros (flake8) on G2's new code — style only, being fixed |

v1/v2/v3 hashes: the determinism hashes and the native gate match; no golden changed.

## Real phone

Nothing Phone (1) (A063, Android 15, Chrome 156), full screen 803 × 361, **medium tier (shipped
default)**, pixel ratio 1.25, served by the laptop over USB from a frozen copy of the build;
`tools/phone/real_phone_free.mjs` (no DevTools while playing). The cool-start wait (battery ≤ 36 °C)
was **waived by Gautham** for these runs, so they started warm. [`data/g28/`](data/g28/),
screens [`screens/g28/real_phone/`](screens/g28/real_phone/) (looked at; no status bar or notification).

| Run | fps median / min / p05 | frame p99 / max | > 50 ms | skin °C | GPU °C | battery °C |
| --- | --- | --- | --- | --- | --- | --- |
| **GAME, Free Drive (Depot), 10 min** | 60 / 37 / 58 | 25.4 / 79.6 ms | 12 of 35,850 | 41.4 → 42.7 | 53.6 → 58.7 | 40 → 41 |
| GAME, Fetch Rush seed 1 (round ended at 5:31; then results) | 60 / 55 / 60 | 20.8 / 42.1 ms | 0 | 38.5 → 41.3 | 43.2 → 56.3 | 38 → 40 |
| **SIM, Fetch Rush seed 1, 2 min, every display on** | 60 / 58 / 59 | 20.5 / 39.0 ms | 0 | 41.3 → 42.5 | 56.0 → 60.2 | 40 |
| SIM check (before the close run) | 60 / 60 / 60 | 19.6 / 25.9 ms | 0 | 37.3 → 40.1 | 48.6 → 57.1 | 37 |

No WebGL context loss and no page error in any run; rotation settings restored (0 / 0) after each;
COCO's saved settings on the phone's usual origin were never touched (these runs used a fresh origin).
**Touch-to-motion: UNRESOLVED.** Medians 145–185 ms, but 25 of 62, 13 of 35 and 33 of 112 samples
took over 1 s (clusters near 1.3 s and 4.9 s; G2.0's 10-sample baseline already had a 4.9 s p90).
In the Fetch Rush runs COCO sat pressed against a wall at its start (178 contacts), which could make
inputs produce no motion; not yet tested.

**A defect the phone found, fixed:** Play opened with SIM view saved drew GAME's world under a SIM label
(the renderer's view was set before the world existed and the later call was skipped as "no change";
PLAY also forced the chase camera). The first phone SIM measurement measured that and is **discarded**
([`…BUGGED_build.json`](data/g28/real_phone_sim_2min_BUGGED_build.json), screen
`sim-BUG-saved-view-before-fix.png`). Fixed in `GameRenderer.setView` / `setGameCamera`;
`tools/g2/saved_view_check.mjs` fails on the old build and passes on the new one (in the suites).

## Stop conditions

None fired: no model or golden hash changed (v1/v2/v3 checks above), no logo or non-free asset, no UI
claims the browser runs ROS 2 (`g2_ros_honesty.test.ts`), and GAME view holds a 60 fps median on the
real phone (with the dips above: no optimisation pass was needed for the median, the dips are open).

## Questions for Gautham

1. The marked crossings are the walkers' own paths, so COCO can never cross there clear of a walker
   (0 of 600 start times). Move or widen them, or keep "routes never cross"?
2. Wheel odometry over-counts rotation by 14.5 % in the frozen robot config. Correct it in a later
   milestone?
3. AMCL still ends legs up to 0.28 m off; investigate further, or accept with the gate passing?
