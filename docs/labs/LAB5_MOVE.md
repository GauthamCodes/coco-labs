# Lab 5 — Move

`?view=move` on the site. Phase 6 of `docs/ROADMAP.md`. Branch `lab5`.
Evidence: `docs/data/lab5/` (its README lists every file). Formats:
`docs/labs/MOVE_FORMAT.md`. Labels as everywhere in this repository:
**(measured)** from a run made in this phase, **(derived)** computed from
recorded or committed data, **(historical)** quoted from an earlier record,
**unverified** when nobody ran it.

## 1. What the lab teaches

**A path is not a motion.** A global planner draws a line on the map once. Ten
times a second a local controller has to turn that line into a speed and a turn
rate — with the robot's limits, from where the robot *believes* it is, around
whatever is in the way — and then a velocity smoother and a collision monitor
shape that command before `cmd_vel_arbiter`, the only thing that drives the
wheels, passes it on. The page draws that chain first, then:

1. **Same path, three controllers (Replay).** One global path, computed once by
   the mission's own SmacPlanner2D and frozen in a file, driven by DWB, MPPI
   and Regulated Pure Pursuit on the same robot with the same limits. The
   learner sees the path, every run's executed trajectory, the focused run's
   candidates as Nav2 published them (DWB's scored candidates with the
   rejected ones in red; a fifth of MPPI's samples), its chosen trajectory,
   AMCL's belief beside the truth, the collision monitor's state, and the
   moment of closest approach; predicts which controller tracks / clears /
   turns best, then sees the measured table.
2. **People on the apron (Replay).** A person crosses in front of the robot, or
   walks straight down its path. The global path does not move.
3. **Run 15: "0 of 819".** The historical log and AMCL table, quoted verbatim
   from `docs/RESULTS.md`, beside a mechanism reproduction made in this phase
   and labelled as not being run 15 (§4.3).
4. **When the map is wrong (D\* Lite, Sketch).** A robot plans on the map it
   has, meets obstacles its map lacks, and D\* Lite repairs the plan; A\*
   searches again from scratch beside every repair. The learner paints
   obstacles the robot does not know about and coco_lab runs the episode in
   the browser (Pyodide). Nav2's own costmap change (Experiment C) is a second
   world.
5. **What is proven:** every claim with its test or measurement.

## 2. Definitions (fixed before any controller was measured)

### 2.1 The controllers

`coco_lab_ros/config/nav2_move_overlay.yaml`, deep-merged onto a COPY of the
mission's `gazebo_models/config/nav2_params.yaml` (whose SHA-256 is pinned:
`06c308af…`). Its only change: `controller_plugins: [FollowPath, MPPI, RPP]`.

| id | plugin (Nav2 1.3.11) | configuration |
|---|---|---|
| `FollowPath` = **DWB** | `dwb_core::DWBLocalPlanner` | the mission's, untouched: 20 × 40 velocity samples (819 candidates per cycle, measured), 1.5 s rollouts, critics RotateToGoal, Oscillation, BaseObstacle, GoalAlign, PathAlign, PathDist, GoalDist |
| **MPPI** | `nav2_mppi_controller::MPPIController` | the Nav2 docs example: 2,000 samples, 28 steps × 0.1 s (the docs' 2.8 s horizon at the shared 10 Hz), temperature 0.3, the docs' eight critics |
| **RPP** | `nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController` | the Nav2 docs example: lookahead 0.6 m (0.3–0.9), regulated linear scaling, collision detection on the lookahead arc, rotate-to-heading |

Every robot limit is DWB's for all three: 0.3 m/s, no reversing, 1.0 rad/s,
linear acceleration 3.0 / −2.5 m/s², yaw acceleration 3.2 rad/s²
(`coco_lab_ros/test/test_lab5.py::test_no_controller_gets_a_faster_or_more_agile_robot`).
Goal and progress checkers, local costmap (`robot_radius` 0.25), velocity
smoother and collision monitor are the mission's and shared. The live
parameters are read back off the running nodes before every run (253 of 255
leaves; the 2 undeclared are pre-existing mission keys — §7).

### 2.2 The frozen global paths and the scenarios

`lab5_run.sh capture` asked planner_server for `GridBased` (SmacPlanner2D)
ONCE per path, on a fresh simulator (measured, 2026-10-07): `lab5_path_room.json`
(13.020 m, 248 poses, SHA-256 `5c460ab6…`) and `lab5_path_apron.json`
(7.500 m, 151 poses, `1e141d38…`). Every run READS the file
(`lab_planner path_file:=`) and sends it unchanged in one FollowPath goal; the
hash is checked in every run. The robot always starts at its spawn, map
(0, 0, 0). Map frame = world + (2, 0).

| scenario | path | what happens |
|---|---|---|
| `static_room` | room | north up the apron, a hairpin around the west spine's end, south into a room |
| `crossing` | apron | a person crosses the apron at y −4.5 (from x −1.5 to 0.8) when the robot's ground truth passes y −1.8 |
| `oncoming` | apron | a person walks up the robot's path (x = 0, from y −8.0 to −0.6) from when the robot passes y −1.0 |
| `mislocalised` | apron | one operator `/initialpose` puts AMCL's belief 3.4 m north of the truth (run 15's gap), then FollowPath |
| `parked` | — | Experiment C only: a person stands at (0, −2.2); the robot does not move |

`coco_lab_ros/config/lab5_scenarios.json`.

### 2.3 The actors

`coco_lab_ros/actors.py` and `lab_actors` (M7_DESIGN §2.6): an upright grey
cylinder Ø0.30 × 0.60 m, **visual only — no collision geometry**, gravity
off, its pose driven through Gazebo's `set_pose` at 20 Hz of sim time;
robot-triggered from ground truth; 0.25 m/s; validated to stay on the apron
(map x −1.7…1.0, every waypoint at least a radius inside). The LiDAR is a
`gpu_lidar`, which renders visuals, so it sees the actor (§4.4); the physics
engine has nothing to collide with, so a contact is never felt — it is
**measured**, from ground truth, as a clearance of 0. The actor never stops:
it is not a model of a person's behaviour, only of a moving obstacle.

### 2.4 The metrics (`coco_lab.movemetrics`)

All in the map frame, on the simulator clock, over the **window** from
FollowPath's acceptance to its result.

- **Tracking error** (m) — for every ground-truth sample (Gazebo's odometry of
  the model, 50 Hz) its distance to the nearest point of the path polyline;
  mean, p95 (nearest rank), max. Phase 1C's definition.
- **Travel time** (s) — the window's length; a travel time only for a run that
  reached the goal.
- **Smoothness** — RMS of the controller's commanded `dv/dt` (m/s²) and `dw/dt`
  (rad/s²) between consecutive `/cmd_vel_nav` messages (header stamps). It
  measures the controller, before the smoother and the monitor.
- **Minimum clearance** (m) — the smallest distance between the footprint
  rectangle (0.297 × 0.314 m, centred; the rectangle Lab 1 sweeps, from
  `coco_config`) at a ground-truth pose and any box of `navigation_world.json`
  (exact convex-polygon distance) or any actor (distance to its axis minus its
  radius); 0 and `contact` when they overlap.

Supplementary, outside the definitions and labelled so wherever shown: DWB's
cycles where it scored candidates and rejected every one, apart from cycles
with nothing to score; and the actor clearance over the **whole recording**
(a robot that aborted can still be walked into afterwards).

Every metric is recomputed from the drive bundle's own arrays at site build
(`movebundle.replay_drive`) and refused unless it matches.

### 2.5 D\* Lite

`coco_lab/coco_lab/dstarlite.py`: Koenig and Likhachev's D\* Lite (AAAI 2002,
the basic version of their Figure 3) on the same `SearchGraph` interface as
Lab 1's five algorithms. Backward search from the goal; `g` and `rhs`; keys
`(min(g, rhs) + h(start, s) + km, min(g, rhs))`; predecessors are the
neighbours on symmetric-adjacency graphs (a grid's, tested). Keys compare
within 1e-9 (§7). `coco_lab/coco_lab/replan.py`: the episode — an optimistic
map (it may lack obstacles, never invents one), sensing within a radius (or
every change at once), scheduled world changes, D\* Lite's repair and A\* from
scratch on the same map at every round, costs required to agree.

## 3. Claims and their evidence

| claim | evidence |
|---|---|
| Every controller drives the same path file, on the same robot limits | `coco_lab_ros/test/test_lab5.py::test_each_scenario_names_a_frozen_path_that_matches_it`, `::test_no_controller_gets_a_faster_or_more_agile_robot`; the path hash in every run's record |
| The mission's DWB parameters were not changed | `test_lab5.py::test_the_overlay_adds_two_controllers_and_changes_nothing_else`, `::test_the_mission_file_is_untouched` |
| No new wheel publisher; the arbiter stayed the wheel topic's only publisher | `coco_lab_ros/test/test_guards.py::test_every_publisher_names_a_lab_topic`; `test_lab5.py::test_the_actor_node_publishes_only_its_record_and_moves_on_trigger`; every run's watch (measured, §4.1) |
| Every displayed metric reproduces from the recording | `coco_lab/test/test_movebundle.py::test_a_metric_that_does_not_reproduce_is_refused`; `lab_web/tools/test_move_glue.py::test_the_catalog_serves_lab5_validated_and_replayed` |
| The actor has no collision geometry; a walk-through is counted as a contact | `test_lab5.py::test_the_actor_has_no_collision_geometry`; `coco_lab/test/test_movemetrics.py::test_an_actor_walking_through_the_robot_is_a_contact` |
| The actor schedule is deterministic | `test_lab5.py::test_the_schedule_is_a_pure_function_of_the_trigger_time` |
| D\* Lite is optimal after every change and move | `coco_lab/test/test_dstarlite.py::test_dstar_lite_is_optimal_after_every_change_and_move` (1,000 seeded maps, networkx oracle) |
| Every replan equals A\* from scratch | `coco_lab/test/test_replan.py::test_every_round_agrees_with_astar_from_scratch` (1,000 seeded worlds) |
| An optimistic robot arrives iff the world has a route | `test_replan.py::test_an_optimistic_robot_arrives_iff_the_world_has_a_route` (1,000) |
| D\* Lite episodes replay byte for byte | `test_movebundle.py::test_a_replan_bundle_round_trips_and_replays`, `::test_a_bundle_whose_arrays_tell_another_story_fails_replay` |
| Run 15's lines on the page are verbatim | `lab_web/tools/test_move_glue.py::test_the_run15_quotes_are_verbatim_in_results` (and the site build refuses otherwise) |
| The browser decodes exactly what Python wrote | `lab_web/test/movedecode.test.ts` against `lab_web/test/golden/move_expected.json` |

## 4. Measured

### 4.1 The controller matrix in Gazebo (measured, 54 runs, 2026-10-07)

`docs/data/lab5/lab5_matrix.sh` from the copy overlay `~/coco_search_ws` at
source `656264a` (clean): a FRESH simulator per run, controllers interleaved
(DWB, MPPI, RPP, DWB, …), 5 runs per controller per scenario (3 for
`mislocalised`), ROS domain 66. **54 valid runs, 0 void, every runner check
PASS** in every run: live parameters equal the merged file, every overlay key
declared, all three controllers loaded, and in every 1 s watch sample the wheel
topic's only publisher was `cmd_vel_arbiter`, the arbiter's inputs unchanged
and both lab nodes publishing only their declared topics. Medians over runs
[min–max]; `lab5_tables.py` output, pasted.

#### static_room — Around a wall end and into a room

Path `5c460ab60d57…`.

| controller | runs | outcome | tracking mean (m) | tracking max (m) | time, reached (s) | RMS dv/dt (m/s²) | RMS dw/dt (rad/s²) | min clearance (m) | contacts in window / whole recording |
|---|---|---|---|---|---|---|---|---|---|
| DWB | 5 | 5 follow_failed (code 105) | 0.121 [0.089–0.141] | 0.237 [0.222–0.255] | — | 0.26 [0.23–0.33] | 1.01 [0.74–1.75] | 0.402 [0.306–0.470] | 0 / 0 |
| MPPI | 5 | 5 succeeded | 0.143 [0.135–0.152] | 0.554 [0.542–0.560] | 51.8 [51.5–52.8] | 0.05 [0.05–4.86] | 0.24 [0.23–1.35] | 0.262 [0.236–0.289] | 0 / 0 |
| RPP | 5 | 5 succeeded | 0.097 [0.092–0.104] | 0.174 [0.169–0.184] | 51.2 [51.0–51.4] | 0.14 [0.13–0.17] | 0.26 [0.24–0.28] | 0.322 [0.316–0.340] | 0 / 0 |

- **DWB never got round the hairpin: 0 of 5.** Every run aborted with
  `FAILED_TO_MAKE_PROGRESS` (105): before the turn around the spine's end its
  heading swung back and forth, and in its last cycles the `Oscillation`
  critic rejected 400 of 819 candidates per cycle (measured in the smoke run's
  `/evaluation`), until the progress checker (0.1 m in 10 s) gave up. The mission never asks DWB
  for this turn. Why DWB stalls here is **not attributed** beyond that.
- **MPPI got round 5 of 5 by cutting the corner** — the largest tracking error
  (max 0.554 m) and the least room from the walls (0.236 m at worst).
- **RPP got round 5 of 5 closest to the line** (max 0.184 m) and as smoothly
  as MPPI in turn rate.
- MPPI's RMS dv/dt maxima (4.86 here, 5.98 in crossing) come from one
  command pair each: the controller server's zero "stop" command, 2 ms after
  MPPI's last command, in the runs where MPPI reached the goal still moving at
  about 0.23–0.25 m/s (measured: 3 of the 10 MPPI runs of these two
  scenarios — `static_room_MPPI_3` 0.231 → 0 m/s, `crossing_MPPI_1` 0.252 → 0,
  `crossing_MPPI_4` 0.250 → 0; the largest other pair in any of the 10 is
  1.52 m/s²). The metric was fixed before measuring and is reported as
  defined.

#### crossing — A person crosses the apron in front of the robot

Path `1e141d385a33…`.

| controller | runs | outcome | tracking mean (m) | tracking max (m) | time, reached (s) | RMS dv/dt (m/s²) | RMS dw/dt (rad/s²) | min clearance (m) | contacts in window / whole recording |
|---|---|---|---|---|---|---|---|---|---|
| DWB | 5 | 5 succeeded | 0.049 [0.047–0.070] | 0.158 [0.154–0.167] | 26.3 [26.1–26.5] | 0.26 [0.22–0.27] | 0.90 [0.65–0.97] | 0.355 [0.340–0.361] | 0 / 0 |
| MPPI | 5 | 5 succeeded | 0.069 [0.059–0.075] | 0.250 [0.231–0.257] | 29.5 [29.4–29.9] | 0.15 [0.12–5.98] | 0.28 [0.24–0.42] | 0.457 [0.442–0.460] | 0 / 0 |
| RPP | 5 | 5 succeeded | 0.052 [0.046–0.070] | 0.180 [0.174–0.186] | 28.7 [28.5–28.9] | 0.33 [0.19–0.38] | 0.32 [0.29–0.37] | 0.345 [0.333–0.349] | 0 / 0 |

15 of 15 reached the goal without contact; MPPI kept the most room from the
person (0.442 m at worst), DWB was fastest. The collision monitor's
`FootprintApproach`, `PolygonLimit` and `PolygonSlow` zones fired as the
person crossed (smoke run; per-run states are in the bundle).

#### oncoming — A person walks straight down the robot's path towards it

| controller | runs | outcome | tracking mean (m) | tracking max (m) | time, reached (s) | RMS dv/dt (m/s²) | RMS dw/dt (rad/s²) | min clearance (m) | contacts in window / whole recording |
|---|---|---|---|---|---|---|---|---|---|
| DWB | 5 | 5 succeeded | 0.045 [0.041–0.062] | 0.156 [0.149–0.181] | 28.3 [28.1–28.6] | 0.26 [0.24–0.30] | 0.59 [0.56–0.68] | 0.000 [0.000–0.000] | 5 / 5 |
| MPPI | 5 | 5 succeeded | 0.074 [0.066–0.094] | 0.237 [0.235–0.261] | 32.0 [31.9–32.5] | 0.13 [0.12–0.14] | 0.25 [0.21–0.33] | 0.000 [0.000–0.000] | 5 / 5 |
| RPP | 5 | 5 follow_failed (code 104) | 0.058 [0.036–0.069] | 0.179 [0.172–0.192] | — | 0.29 [0.29–0.33] | 0.24 [0.24–0.27] | 0.218 [0.209–0.242] | 0 / 5 |

**Nobody swerved.** In all 15 runs the robot stayed within 0.261 m of the
path's line (`max_lateral_m`), and in all 15 the person reached it while its
wheels were already commanded to 0 m/s (`actor_contacts_while_wheels_stopped`
15/15, measured): DWB and MPPI were stopped by the collision monitor's
`PolygonStop`, RPP stopped itself (`RegulatedPurePursuitController detected
collision ahead!`) and FollowPath aborted on `Controller patience exceeded`
(104) about a second before the person walked into it — which is why RPP's
in-window contact count is 0 and its whole-recording count 5. DWB's and MPPI's
"succeeded" exists only because the actor is a ghost that passes through; a
real obstacle would have left them stopped. Why neither sampling controller
left the path on a 2.8 m-wide apron is **not attributed**.

#### mislocalised — the run 15 mechanism (§4.3)

| controller | runs | outcome |
|---|---|---|
| DWB | 3 | 3 follow_failed (code 103, invalid path) |
| MPPI | 3 | 3 follow_failed (code 103) |
| RPP | 3 | 3 follow_failed (code 103) |

### 4.2 The frozen paths and the smoke runs (measured, not results)

The capture session and four smoke runs (DWB, MPPI, RPP on static_room; DWB
on crossing) preceded the matrix on the same code and are not in any
statistic. They found the readback blind spot and the extractor's frame and
stamp issues of §7.

### 4.3 Run 15

**Historical** (`docs/RESULTS.md`, "The one failure: run 15, and it is a
localisation failure", the M6 fetch matrix in the v1 wedge world; that text
entered RESULTS.md on 2026-08-06): after a successful pick, AMCL believed the
robot 3.4 m from the truth in a corridor the map leaves featureless; the
global planner still had a path; DWB logged `PathDistCritic: None of the 5
first of 5 (5) points of the global plan were in the local costmap and free`
and `No valid trajectories out of 819!`; the goal failed in 1.7 s.

**Run 15 itself cannot be re-run here**: that world and corridor are not this
arena. **Reproduced here: the mechanism, not the log line** (measured, 9 runs):
one operator `/initialpose` (RViz's "2D Pose Estimate") moved AMCL's belief
3.401–3.403 m from the truth (measured after 8 s of settling), then each
controller was handed the frozen apron path. All 9 runs failed within their
first control cycle (4–12 ms of sim time) with `INVALID_PATH` (103); every
controller logged `Resulting plan has 0 poses in it.` — the whole path lay
outside the robot's 3 × 3 m local costmap as the robot believed it, so Nav2
1.3.11 pruned it to nothing before any trajectory was scored. DWB's one
`/evaluation` lists **0 candidates** (0 of 0, not 0 of 819): cycles where it
rejected every candidate 0, cycles with nothing to score 1, in each run. Same
mechanism — a good global plan, a robot that does not know where it stands,
a local layer that refuses — different symptom. Engineering the geometry to
force the exact "0 of 819" line was not attempted.

### 4.4 The actors are seen (measured)

`lab5_actor_seen.py`, per scan while the actor is within 2.5 m and in the
LiDAR's field of view, the beam pointing at it against ground-truth geometry
(distance − radius, tolerance 0.08 m): crossing **1,523 of 1,523** scans hit
(per run 97–110, median error 1.9–4.2 mm); oncoming **777 of 939** (per run
50–55 of 60–65, median error 12.9–13.2 mm). The oncoming misses are **not
attributed**.

### 4.5 D\* Lite (derived: deterministic computations on committed inputs)

- **Sketch worlds** (`lab5_replan_sketch_stats.py`, seeds 0–199, sense radius
  2.5): costs agreed in every round of every episode; 177 reached the goal (23
  worlds have no route); D\* Lite's total work was below A\* from scratch in
  **191 of 200** (ratio median 0.59, range 0.26–2.14), but in **188 of 2,204**
  single replans it did more.
- **Experiment C** (measured inputs, derived episode; `lab5_run.sh snapshot`,
  every check PASS): Nav2's global `costmap_raw`, settled, before and after a
  person stopped at (0, −2.2) 2.2 m ahead of the robot; a 67 × 177-cell window
  (0.05 m) of the apron; C0 move model. The update changed 443 cells, 104 newly
  blocked. First plan: cost 150.0 (151 expansions, both). After the update:
  **D\* Lite 3,209 expansions, A\* from scratch 1,114**, the same cost (160.598
  cells). On this real change, repairing cost 2.9× searching again. Not
  attributed. Rebuilt from the committed snapshots it reproduces the same
  episode (measured: identical rounds and arrays at two commits); the
  committed bundle, made at clean `e5913c8`, is `sha256:2d032ada…`.

### 4.6 The site (measured, local build, headless Firefox)

`lab_web/tools/browser/check.py <site> <out> move move_phone`: 0 console
errors; the Replay loads, scrubs and reveals the measured table; a D\* Lite run
with three painted obstacles completed in Pyodide in 5.8 s cold (coco_lab 158
ms for 19 plans, every plan's cost equal to A\*'s); Pyodide is fetched only
when that run is asked for; no horizontal page scroll at 390 × 844 on any tab.

### 4.7 Tests

`COCO_WS=~/coco_search_ws ROS_DOMAIN_ID=77 scripts/run_all_package_tests.sh`
(a copy overlay of `5cd039d`, clean) on a quiet machine after the matrix:
**3,081 passed, 0 failed, 0 skipped** (Phase 5 closed at 2,975).

| package | Phase 5 | now | what is new |
|---|---|---|---|
| coco_lab | 533 | **604** | `test_dstarlite.py` (hand-checked cases; 1,000-map properties with change sequences), `test_replan.py` (1,000-world properties), `test_movemetrics.py`, `test_movebundle.py` (golden bundles, replay refusals, the format document) |
| coco_lab_ros | 86 | **121** | `test_lab5.py` (overlay diff and equal limits, scenarios, frozen paths clear the arena, actor rules and node), frozen-path planner tests, the per-node publisher guard, `lab_actors` in the sweep |
| coco_config, coco_sim, coco_mission, coco_web, gazebo_models, coco_rl, coco_perception, coco_moveit_config, custom_teleop | 93, 323, 371, 863, 229, 251, 139, 12, 75 | unchanged | |

`lab_web`: vitest 289 → **308** (`movedecode.test.ts`, `moveview.test.ts`,
and a Lab 5 catalog test; the catalog-version pin moved 1.4 → 1.5 — CI
caught it after a local run against a catalog built before Lab 5);
tools pytest 104 → **117** (`test_move_glue.py`, the Lab 5 expectations, the
extended no-algorithm guard); `tsc`, `vite build` and `check_dist` clean.

### 4.8 On the public site (measured)

`main` fast-forwarded `1970e42` → `0fef157` after PR #17's CI was green;
both workflows green on `main`; Pages deployment 6916595601; the public
catalog is 1.5, `built_from` `0fef157`, not dirty. Headless Firefox 157
against `https://gauthamcodes.github.io/coco-labs/` (2026-10-07 17:41 UTC,
load ≈ 1.9; `docs/data/lab5/public/report.json`):

- `move`: 0 console errors; the Replay, the reveal ("On the median run, RPP
  stays closest to the path"), the person drawn in the people tab, run 15's
  summary, and a D\* Lite run with three painted obstacles: 13.4 s cold
  including the Pyodide start (coco_lab 95 ms for 19 plans, every plan's
  cost equal to A\*'s); no Pyodide request before that run.
- `move_phone`: no horizontal page scroll at 390 × 844 on any of the five
  tabs.
- Earlier labs, unchanged: Lab 1 `smoke` 11 of 11 bundles drawn, 0 console
  errors; `localise_phone`, `mapping_phone`, `search_phone` no overflow, 0
  console errors.
- The demo video was recorded from this site (`docs/data/lab5/video/`).

## 5. Not verified

- A physical robot: everything is Gazebo.
- Rates: 5 runs per controller per scenario (3 mislocalised) are
  distributions, not rates.
- Why DWB stalls at the hairpin, why no controller swerved on the apron, why
  D\* Lite out-worked A\* on Experiment C, why oncoming scans miss: observed,
  not attributed.
- Tuned controllers: all three ran documented example settings with the
  robot's limits; a tuned DWB or MPPI may behave differently. Nothing here
  ranks the algorithms in general.
- D\* Lite driving the real robot: it runs in coco_lab (Sketch and on two real
  costmaps), not in the Nav2 loop.

## 6. Known limitations

- The actor never stops and has no collision geometry; "contact" means it
  walked into the robot. It models a moving obstacle, not a person.
- Run 15's exact symptom was not reproduced (§4.3).
- The metrics window ends at FollowPath's result; contacts after it are shown
  separately as supplementary.
- The browser keeps candidates for the first run of each controller only
  (bundle size: 1.0–1.7 MB per scenario as it is).
- Lab 5 ships four algorithms (DWB, MPPI, RPP, D\* Lite) — within §7's
  five.

## 7. Found and fixed during the phase (each measured)

- **D\* Lite stopped one state early** on 3 of 400 random cases (a cost 0.59
  below optimal): equal keys formed in a different order differ in the last
  bit (7.242640687119286 vs …285). Keys now compare within 1e-9 — and the
  heap peek must use the same tolerant order (a second failure: an entry
  (…0955, 5.41) sat behind (…095, 11.66)). Then 0 mismatches in 3,000 random
  change sequences and the 1,000-map properties.
- **A parameter readback that checked nothing passed:** a node's
  GetParameters service (rclcpp) answers a request naming ANY undeclared
  parameter with an EMPTY list, so the first readback "checked 63" while
  skipping `controller_server` and the local costmap entirely. `lab5_watch.py`
  falls back per name and fails a section that checks nothing. Phase 1C's own
  readback did check all 67 of its leaves (its committed `params_readback.json`
  files).
- **ros_clean.sh would have killed another session's process** (an orphaned
  `target_finder` of `~/coco_m1_ws`, ROS domain 181). It was left alone;
  `lab5_run.sh` sweeps only its own ROS domain and still refuses if any Gazebo
  runs.
- MPPI's marker stamps are zero (log time used); RPP's lookahead point is in
  `base_footprint` (frame chain verified: median 0.627 m from the true robot
  against a 0.6 m lookahead).

## 8. Reproduce

```bash
# overlay with a quotable path (CLAUDE.md), then:
docs/data/lab5/lab5_run.sh capture OUT                      # freeze the paths
docs/data/lab5/lab5_matrix.sh OUT_ROOT 5                     # the 54-run matrix
docs/data/lab5/lab5_run.sh snapshot OUT                     # Experiment C capture
python3 -P docs/data/lab5/lab5_evidence.py OUT_ROOT          # drive bundles, results.json
python3 -P docs/data/lab5/lab5_replan_c.py docs/data/lab5/snapshot_c1
python3 -P docs/data/lab5/lab5_replan_sketch_stats.py
python3 docs/data/lab5/lab5_tables.py                        # the tables above
python3 lab_web/tools/build_catalog.py                       # the site data
```
