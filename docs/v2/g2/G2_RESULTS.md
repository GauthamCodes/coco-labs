# G2 · Sim Identity — results

Prompt: [`G2_PROMPT.md`](G2_PROMPT.md) · state: [`G2_STATUS.md`](G2_STATUS.md) · before/after:
[`BEFORE_AFTER.md`](BEFORE_AFTER.md). Branch `v2/g2-sim-identity` from `origin/main` `7475896`.
Evidence classes as AGENTS.md: **MODEL** (the browser model), **STACK** (recorded ROS 2 in
Gazebo, never hardware), MEASURED, EMULATED, UNRESOLVED.

**Added after the first G2.8 pass (2026-10-25/26):** Fetch Rush **rules 5** (actors yield, AUTO avoids),
**Fetch by colour** (four rods) with its rules 2, the **no-WebGL hotfix**, the **per-round Gazebo gate** (every
round 5 of 5, on a new controller: derivation 4), Race Nav2 for Fetch by colour, two /rosout layout fixes
the real phone found, and a final real-phone check. The touch-to-motion samples over 1 s remained
UNRESOLVED at G2.8; **G2.9 found their cause and removed them** (next section).

## Checkpoints

| Checkpoint | Result | Evidence |
| --- | --- | --- |
| G2.0 Baseline | done | [`data/g20/README.md`](data/g20/README.md) |
| G2.1 Decisions | done | [`data/g21/README.md`](data/g21/README.md) |
| G2.2 GAME \| SIM | done; real phone SIM 60 fps | [`data/g22/README.md`](data/g22/README.md), [`screens/g22/`](screens/g22/) |
| G2.3 Telemetry | done | same |
| G2.4 Panels | done | same |
| G2.5 rosbag2 export | done | [`data/g25/README.md`](data/g25/README.md) |
| G2.6 Gazebo + Nav2, ghosts, Race Nav2 | done; **superseded by the per-round gate** (derivation 4) | [`data/g26/DIAGNOSIS.md`](data/g26/DIAGNOSIS.md), [`data/g26/GATE.md`](data/g26/GATE.md), [`screens/g26/`](screens/g26/) |
| G2.7 Looks | done; real phone GAME 60 fps median | [`data/g27/budgets.json`](data/g27/budgets.json), [`screens/g27/`](screens/g27/) |
| Rules 5 (owner report 2026-10-24) | done | [`data/rules5/README.md`](data/rules5/README.md), [`data/rules5/g2_rerun.md`](data/rules5/g2_rerun.md) |
| Fetch by colour (owner request 2026-10-24) | done; rules 2 = rules 5's actors; Race Nav2 | [`data/fetch_colour/README.md`](data/fetch_colour/README.md) |
| No-WebGL hotfix (owner report 2026-10-24) | done; also PR #29 into main | [`../hotfix_webgl/README.md`](../hotfix_webgl/README.md) |
| Per-round Gazebo gate (owner 2026-10-25) | **every round 5 of 5** (derivation 4) | [`data/g28/round_gate/README.md`](data/g28/round_gate/README.md) |
| G2.8 Close | done | this file, [`data/g28/`](data/g28/), [`BEFORE_AFTER.md`](BEFORE_AFTER.md) |
| **G2.9 Polish before deploy** (Gautham's review, 2026-10-27) | done; see below | [`data/g29/`](data/g29/), [`BEFORE_AFTER.md`](BEFORE_AFTER.md) § G2.9 |

## G2.9 · Polish before deploy (2026-10-27/28)

Gautham's decisions of 2026-10-27 (G2_STATUS, STATUS): keep Regulated Pure Pursuit for driving recordings;
Gazebo's actors yield to COCO like Rules 5 (a scenario rule); calibrate the odometry turn scale in the
generated files only, then re-measure AMCL; the tagline "Drive COCO, a ROS 2 robot, modelled in your browser."

### 1. Touch-to-motion over 1 s — cause found, fixed; MEASURED on the real phone

- **Not a G2 regression.** `?perf`'s input → motion timer started on a drive input from rest and stopped at
  the first frame drawing COCO moved; a push into a wall never moves COCO (game rules), so the timer stayed
  armed until a later swipe moved it, and that swipe's ~0.13 s response was logged as 0.13 + k × 1.2 s (the
  soak's swipe period). G1.13's own 10-minute soak on 78a1596 shows it (median 1315 ms), so the bisect range
  starts with the artefact: there is no commit to bisect to. Laptop check `touch_blocked_check.mjs`: 1269 ms
  on 78a1596 (FAIL), 129 ms after the fix (PASS). Fix: releasing the input before any motion disarms the
  timer and is counted (`inputNoMotion`) ([`data/g29/touch/`](data/g29/touch/README.md)).
- **A real wait, also fixed (pacing only).** An input amended into a tick during its final synchronous
  stretch missed it and waited in the worker for the next scheduled send (up to 0.1 s). The tick after an
  amendment is now sent when the one in flight arrives; an input with nothing in flight is sent at once.
  EMULATED (4× CPU): median 132 → 90 ms; the worker step is the same in G1.13 and G2.9 (62.8 / 63.4 ms).
- **Real phone, final build `2977762`** ([`data/g29/real_phone/`](data/g29/real_phone/README.md)): **0 samples
  over 1 s** (313); GAME run medians **142 / 149 / 184 ms** (pooled 166 ms), SIM pooled 134 ms. The ≤ 150 ms
  target is met in 2 of 3 GAME runs, **not** in the hot 10-minute run (battery 41 → 43 °C); the G1.13 build
  measured 159 ms in the same session. What remains is the model's step (65–96 ms median on the phone).

### 2–3. SIM in RViz style; "Looks wrong" — done (MODEL; screenshots for Gautham)

Item by item in [`BEFORE_AFTER.md`](BEFORE_AFTER.md) § G2.9. Real phone, final build: **every run 60 fps
median**, GAME and SIM, SIM with every display on included (min 40–60, 0 WebGL losses, 0 page errors). The
results screen and the status pill checked on the device ([`screens/g29/real_phone/`](screens/g29/real_phone/)).

### Tests and determinism (final, `e869448`) — [`data/g29/suites/suites_final.txt`](data/g29/suites/suites_final.txt)

All green, laptop balanced on AC: coco_lab 1161 (+ 2 gz), lab_web tools 244, vitest 619, typecheck, schemas,
catalog, arena assets, build twice (same dist), native gate exact (hash v3: planners 818,951 / 818,951,
fetch_rush 1,436 / 1,436), coco verify 18 / 18, determinism v1 (10 sessions) and terrain (3) 0 mismatches on
Chromium / Firefox / WebKit / Pyodide-Node with unchanged hashes (`9a9d582d03f4`, `3a8c227eca45`), screenshots,
chase HUD (4 profiles × 20 poses + SIM) 0 failed, saved view, v1 links 50 / 0, replays, update isolation, ROS
packages 12 / 12 (coco_lab 1166 with ament lint). **No golden or hash changed.** (A pass on `5192ed8` found one
flake8 line-length failure in the new derivation 5 tests; wrapped.)

### 4. Gazebo: actors yield, odometry calibrated, AMCL re-measured — STACK

`tools/m6/gen_level.py --derivation 5` = derivation 4 (RPP kept) + `gazebo/diff_drive_calibration.yaml` (the
Stack's controller block, never edited, `wheel_separation_multiplier` 1.10 → 1.323, loaded over the running
controller by the runner) + `actors.json`'s labelled `scenario_rule` (driven by `tools/g2/actor_scenario.py`
with Rules 5's hold rule, from Gazebo's truth). Derivation 4 still verifies identical.

| Measure | derivation 4 (40 runs) | derivation 5 (40 runs) |
| --- | --- | --- |
| Per-round gate (8 rounds × 5) | 40 / 40 | **40 / 40** |
| Odometry turn / truth (pooled) | 1.2029 | **0.9986** (per run 0.976–1.013) |
| Odometry distance / truth | 0.991 | 0.991 |
| AMCL error at leg end: median / p90 / max | 0.148 / 0.231 / 0.261 m | 0.154 / 0.217 / 0.259 m |
| AMCL mean offset (dx, dy) | (−0.032, −0.083) m | (−0.025, −0.086) m |
| Legs' end to goal by truth (median) | 0.351 m | 0.363 m |

- **AMCL's residual did not change** with the odometry corrected: still ~0.15 m at leg ends with a mean
  offset ~8.6 cm south. (G2.6 had already measured that perfect odometry does not remove it.) UNRESOLVED.
- **The gate's routes never came near an actor** (0 holds; least clearance 1.19 m). A targeted check parked
  COCO on `walker_dock`'s path for 60 s: the walker stopped for it 2 times (154.8 s held), the east–west
  forklift 4 times (96.7 s), **0 overlap steps**, least clearance 0.106 m ([`data/g29/actor_yield/`](data/g29/actor_yield/)).
- **A driver defect the gate found:** in 5 of the 40 runs the driver stalled behind failed `set_pose_vector`
  calls (1 s timeouts), so their actors mostly stood still. Fixed (the rule steps by simulation time; one call
  sends the newest poses). Replacement runs with the fixed driver, one per
  stalled run (colour green, red, yellow; phone seeds 3 and 6): **5 / 5 succeeded**, every leg, 0 overlap
  steps, the world at most 1 step behind the rule (seed 6: once 34 steps, 1.7 s, then caught up). With them
  every round is 5 of 5 with the scenario working in every counted run ([`runs_d5_rerun.json`](data/g29/round_gate/runs_d5_rerun.json)).
- Ghosts re-recorded from derivation 5 ([`data/g29/round_gate/`](data/g29/round_gate/)); each says its actors
  moved under the rule.

## Decisions applied (G2.1) — MODEL

- **Crossings:** routes may cross the east–west forklift lane only at a marked crossing, never run
  along it (Fetch Rush **rules 4**; rules 3 and its records unchanged). Measured: both marked crossings
  are the walkers' own paths, and **0 of 600** start times let COCO cross clear of the walker, so both
  are closed and **no route crosses the lane**. (Question 1 below.)
- **Phone budget 26 m.** No budget from 22 m to 81 m gives ≥ 3 distinct rounds with every timer ≤ 5:00
  (the 5:00 sweep, continued past G2's choice, had reached 92 m with none qualifying); **26 m is the smallest giving them ≤ 6:00**: 4 distinct rounds —
  loading dock (seeds 2, 4, 5) 4:35.9 · workshop (3) 4:59.1 · workshop (1) 5:31.4 · workshop (6) 5:49.1.
- **AUTO stall 119–141 ms:** accepted, open. Re-measured twice (`tools/g1/fetch_timing.mjs`, NVIDIA, desktop, low tier,
  balanced, AC; [`data/g28/auto_gap/`](data/g28/auto_gap/)); the largest tick gap around an AUTO press **as the game
  shows it** (`presented.auto_max_tick_gap_ms`):

  | Run | Phone round, seed 1 | Full shift, seed 1 | Largest shown tick gap, Full shift |
  | --- | --- | --- | --- |
  | G1.13 | 119 ms | 141 ms | 143 ms |
  | G2.8 first pass (rules 4; two build jobs sharing the laptop) | 117 ms | 116 ms | **331.9 ms** |
  | **G2.8 close (rules 5; quiet laptop, 2026-10-27)** | **106 ms** | **110 ms** | **166.5 ms** |

  G2 did not make the AUTO stall worse; it is still above the 100 ms target (accepted). The 331.9 ms
  gap the first pass left UNRESOLVED did not recur on the quiet laptop (Full shift max 166.5 ms; phone
  168.1 ms): consistent with the load it ran under, from one quiet run each.
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

### The per-round gate (G2.8, owner 2026-10-25) — STACK

Every round 5 of 5 in fresh headless simulators ([`data/g28/round_gate/README.md`](data/g28/round_gate/README.md)):

| Round | Derivation 2 (G2.6's params) | **Derivation 4** |
| --- | --- | --- |
| Fetch by colour red / green / blue / yellow (the four-rod level's first Gazebo runs) | 5/5 each | **5/5 each** |
| Fetch Rush phone, loading dock (seed 2) | 5/5 | **5/5** |
| Fetch Rush phone, workshop (seeds 6 / 1 / 3) | seed 6: **1/5** (1 and 3 not run) | **5/5 each** |

- **Cause of the workshop failures (measured from bags):** DWB commanded ~0 (v 0, w ~±0.03 rad/s) for
  ~40 s at a time beside `obj_maze_2`'s pre-grasp pose, though the plan was clear (>= 0.615 m from the
  walls), nothing unmapped was near and the wheels followed their commands — C2-NAV.21's DWB
  degeneracy. A rotation shim around DWB (derivation 3) was not enough (1 of 2).
- **Fix (generated params only):** derivation 4 = derivation 2 with Nav2's Regulated Pure Pursuit in
  place of DWB, at DWB's limits. 40/40 runs, 160/160 legs. Five runs per round are not a rate.
- **Cost, measured:** legs end farther from the goal by truth — median 0.34–0.37 m against 0.20–0.27 m
  (Nav2's goal checker, 0.25 m on AMCL's pose, now decides; DWB drove on to 0.05 m). Fine for these
  driving-only legs and the ghosts; a grasp would need it closer (question 4).
- All gate runs at RTF 0.30–0.55 (G2.6: 0.80): the CPU sat at 91 °C with the owner's browsers busy.
- **Ghosts now:** run 1 of each round on derivation 4 — four Fetch by colour ghosts (Race Nav2 for
  Fetch by colour, new) and rules-5 phone ghosts for seeds 1, 2, 3, 6 (preferred over the rules-4 ones).
  Nav2 now drives the workshop rounds in 172–195 s (G2.6's recordings: 347–412 s).

## Rules 5, Fetch by colour, the hotfix — MODEL (Gazebo where said)

- **Rules 5:** in AUTO a forklift drove through a stopped COCO (the actors were a schedule). Now the
  actors stop for COCO and AUTO waits, re-plans around a stopped actor or backs off. Browser forklift
  check: 114 overlap ticks before, **0** after; every committed reference replays (rules 2–5); goldens
  unchanged. Phone timers unchanged. The Gazebo actors still never yield (said wherever STACK is shown).
- **Fetch by colour:** four rods on a derived level; the chosen colour's rod to Dispatch; rules 2 uses
  rules 5's actors (same rounds and scorecards as rules 1). All four colours delivered in the browser;
  records replay in CPython. Race Nav2 offered per colour (above).
- **No-WebGL hotfix:** no page goes blank; Play explains what to try and links to Compare and
  Recordings; Compare runs without 3D. 10/10 pages in Playwright with WebGL refused and working.

## Looks — MODEL

Environment map (procedural `RoomEnvironment`), polished floor and GTAO ambient occlusion on high
only, COCO's metal / plastic / rubber materials (wheel and arm motion are G1's — the model's wheel speeds and
arm joint states; G2 added no motion and did not re-measure the wheels' direction), the title "COCO Lab · a ROS 2 robot you can drive in your browser" with plain-text
badges and an ⓘ that says the browser does not run ROS 2, and a "what the planner computed" inset on
results. Before / after: [`BEFORE_AFTER.md`](BEFORE_AFTER.md).

## Tests and determinism

**Final (G2.8 close, 2026-10-26/27, laptop balanced, AC, NVIDIA):** `tools/g2/suites.sh` on `22e521d`
([`data/g28/close/suites_partial.txt`](data/g28/close/suites_partial.txt); paused on the owner's request after
saved_view), then the remaining steps on the final tree ([`data/g28/close/suites_after_pause.txt`](data/g28/close/suites_after_pause.txt)):

| Suite | Result |
| --- | --- |
| coco_lab (CI venv route) / gz | **1158 passed** / 2 passed (G2.0: 1077 / 2) |
| `pytest lab_web/tools` | **244 passed** |
| catalog, schemas (generated code current), typecheck, arena assets, build twice (same hash), check_dist | pass |
| vitest | **610 passed** (G2.0: 539) |
| native gate (CPython vs Pyodide, hash v3) | planners 818,951 / 818,951 exact; fetch_rush 1,436 / 1,436 exact |
| coco verify + play references | 18 of 18 earn their stars |
| update isolation | pass (9 checks) |
| determinism v1 (10 M1 sessions) | 1500 ticks × Chromium / Firefox / WebKit / Pyodide-Node, 0 mismatches, hash `9a9d582d03f4` (= G2.0) |
| determinism terrain (3 M4 sessions) | 2100 ticks × the same four, 0 mismatches, hash `3a8c227eca45` (= G2.0) |
| screenshots, saved SIM view, replays | pass |
| v1 links | 50 forms, 6 archive views, 0 failed (a first run, during which a rebuild wiped `dist/v1`, failed 10; re-run on the restored site) |
| chase HUD + SIM (4 profiles × 20 poses, incl. the real phone's 803 × 361) | **failed at 803 × 361** (/rosout vs joystick) → fixed (89ce9d0) → **0 failed** |
| ROS packages (colcon route, incl. ament lint) | **all 12 passed** — coco_lab 1163, coco_lab_ros 165, coco_web 863, … (the first pass's flake8/pep257 failures are fixed) |
| Rules 5 / Fetch by colour model checks | every committed reference replays (rules 2–5), v3 goldens identical, game references reproduce, colour rounds regenerate identical ([`data/rules5/g2_rerun.md`](data/rules5/g2_rerun.md)) |

First G2.8 pass (tree `5c77bbe`, [`data/g28/suites.txt`](data/g28/suites.txt)): `pytest lab_web/tools` 235 passed and **1 failed**
(`test_g2_ghosts` assumed a track starts at t = 0; fixed), and the ament lint **failed** in coco_lab and coco_lab_ros
(fixed since; above).

v1/v2/v3 hashes: the determinism hashes and the native gate match; no golden changed.

## Real phone

**Final check (2026-10-25, after Rules 5, Fetch by colour and the hotfix;
[`data/g28/real_phone_final/README.md`](data/g28/real_phone_final/README.md)):** same phone, medium tier,
full screen, on AC, `real_phone_free.mjs`; rotation settings restored after every run.

| Run (final layout) | fps median / min / p05 | frame p99 / max | > 50 ms | lost | skin °C |
| --- | --- | --- | --- | --- | --- |
| **GAME, Free Drive (Depot), 10 min** | 60 / 46 / 59 | 23.9 / 91.2 ms | 14 of 35,864 | 0 | 40.6 → 43.2 (started warm) |
| **SIM, Fetch Rush seed 1** (2 min on the strip fix; 1 min on the final clamp) | 60 / 56 / 60; 60 / 60 / 60 | 19.8 / 49.9; 21.4 / 27.7 ms | 0 | 0 | 39.4 → 40.2 |

The phone found two /rosout layout defects, both fixed and re-checked on it (12aa0ab): the collapsed line
ran under the telemetry strip, and showed the top of a third line through its padding. One run that
loaded the wrong build (port already held) was discarded and is said so in the README.

**First G2.8 pass (2026-10-24):**

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
4. The Depot's generated Nav2 params now use Regulated Pure Pursuit (derivation 4): every round 5 of 5,
   but legs end ~0.1 m farther from the goal than DWB's. Keep it for G2's recordings? Should the robot
   stack's own controller be revisited in a later milestone (its config is unchanged)?
5. Rules 5's actors yield only in the browser model; Gazebo's actors never do. Should the Gazebo
   actors be given the same rule in a later milestone?
