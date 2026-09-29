# COCO Lab — Phase 1C implementation plan (APPROVED)

## Owner decisions (recorded 2026-09-29, implementation session 1C-0)

The owner approved this plan with these answers to §H's D-1 … D-6. They
bind the implementation; nothing below is redefined after a measurement.

| # | Decision |
|---|---|
| D-1 | The real SLAM map-quality number is **OUT of 1C**; it moves to Lab 3. No privileged or generated map is substituted as a "real map-quality" result. |
| D-2 | The costmap snapshot is `/global_costmap/costmap_raw`, because `/global_costmap/costmap` loses information. |
| D-3 | The smoothing comparison uses SmacPlanner2D's published `unsmoothed_plan` output where available. It is **not** described as a configuration that disables smoothing: Nav2 1.3.11 has no verified smoothing-disable parameter in the deployed SmacPlanner2D configuration. |
| D-4 | The three real runs' goal is world **(0.5, 6.0), yaw 0**. |
| D-5 | Bundle format **1.1**, an additive backward-compatible extension, carries the recorded-run pose streams. |
| D-6 | The bundle set is committed to git only if its committed total is **≤ 10 MB**; otherwise the bundles stay outside git and their SHA-256 hashes and provenance are committed. |

- Source: `~/coco_lab_phase1c_plan.md`, SHA-256
  `35ba2f85e455d5d62012cbac45082cc7bb5cc6efd9d05f443fa71b7ffe80c438`, copied
  verbatim below this section.
- Implementation starts on branch `lab1` at `e06dc94893a3f61138f7b68f0f4c4ccdc7329883`
  (== `jazzy2/lab1`, tree clean).
- Discrepancies found at 1C-0 are listed in `docs/SESSION_LOG.md`, entry
  "1C-0".

---

# (the plan as approved)

Written 2026-09-29 in a planning-only session. **Nothing in the repository was
modified.** This file lives outside the repo on purpose; the first action of the
implementation session is to commit it as `docs/labs/PHASE_1C_PLAN.md`.

Labels: **FACT** (read from repo/git/source this session, with citation),
**OBS** (observed this session), **HYP** (hypothesis, to be tested),
**REC** (recommendation), **UNKNOWN**.

Upstream Nav2 source was read at tag **1.3.11** (= the installed
`nav2_smac_planner`, `nav2_costmap_2d`, `nav2_navfn_planner` package.xml
versions) from `raw.githubusercontent.com/ros-navigation/navigation2/1.3.11/…`.
Only headers are installed under `/opt/ros/jazzy/include`; the `.cpp` bodies
are not, so the implementation session must re-fetch the same tag and record
the file SHA-256s in the results (the planning copies were in the job tmp dir
and are not durable).

---

## A. VERIFIED CURRENT STATE

| Item | Value | Status |
|---|---|---|
| Worktree | `<repo>/.claude/worktrees/lab1` | FACT |
| Branch / HEAD | `lab1` @ `e06dc94893a3…` ("Phase 1B-2..1B-5: …") | FACT (`.git/worktrees/lab1/HEAD`, `refs/heads/lab1`, `git log`) |
| Working tree | clean (`git status --short` empty) | OBS |
| `jazzy2/lab1` (live) | `e06dc94` — equal to HEAD | FACT (`git ls-remote jazzy2`) |
| `jazzy2/main` (live) | `6853517` | FACT |
| local `main` | `9ee4a52` (Phase 0 CLOSED checkpoint, still unpushed — a carried owner item) | FACT |
| `lab1` vs local `main` | 3 commits ahead (`c3713dd`, `a12462a`, `e06dc94`), merge-base `9ee4a52` | FACT |
| Remotes | `jazzy2` = coco-robot-jazzy-2.0, `origin` = coco-robot-ros2 | FACT |
| `coco_lab` version | `0.2.0` (`coco_lab/coco_lab/__init__.py:37`) | FACT |
| `coco_lab_ros` | does not exist | FACT (repo root listing) |
| Nav2 installed | 1.3.11 (smac, costmap_2d, navfn); slam_toolbox 2.8.5; `rosbag2_py`, `nav2_simple_commander`, `nav2_msgs` present | FACT |

**Phase 1A (SESSION_LOG "Phase 1A", commit `c3713dd`)** — FACT as recorded:
`coco_lab` pure-Python, stdlib runtime, no rclpy; SearchGraph interface; Grid
(occupancy + optional cost layer, 4/8-conn, diagonal √2, corner-cutting OFF by
default with a toggle); declared cost `base × (1 + cost_weight·cost[b]/cost_scale)`,
defaults 2.0 / 252 (`coco_lab/coco_lab/grid.py:30-40,58-59,221-227`); five
algorithms; heuristics + `analyse()`; trace schema v1. 141/0/0 colcon, 138/0/0
pip at the time.

**Phase 1B (SESSION_LOG "Phase 1B — COMPLETE", commits `a12462a`, `e06dc94`)** —
FACT as recorded: map schema v1 + Nav2 import/export; teaching fixtures;
bundle format v1 (`source_kind` glass-box | recorded-run | sketch, `rosbag`
`{sha256, sim_time_start, sim_time_end}` required for recorded-run —
`docs/labs/BUNDLE_FORMAT.md:51,58`); HeadingGrid; ISRO investigation;
resolution study (0.05 m full-arena Dijkstra 1.022 s, 1.44 MB gz). Tests
recorded at 1B-5: **pip 314/0/0, colcon 317/0/0** (linters included).
**Not re-measured in this planning session** — step I.0 re-measures.

**Discrepancies between the session prompt and the repository**
1. The prompt summarises 1C as "compare cost models + three runs". The durable
   contract (`docs/LAB_PHASES.md:305-355`) is larger: a new `coco_lab_ros`
   package and planner node, a launch file + lab-only Nav2 overlay, ≥50-pair
   Smac conformance, the NavFn half (reproduce/refute M3's 6.2 %), then three
   runs.
2. Map quality: `LAB_PHASES.md §1C` does **not** mention SLAM or a map-quality
   number. But SESSION_LOG Phase 1B, owner decision 3, says "The honest number
   is deferred to 1C", and 1B-1 says "1C at the earliest". **Conflict → owner
   decision (H, D-1).**
3. The spec says snapshot `/global_costmap/costmap`. That topic is lossy (see
   C.4); conformance needs `/global_costmap/costmap_raw`. **Deviation in
   wording, proposed for approval (H, D-2).**
4. The spec asks for Smac "with smoothing disabled if the overlay allows it
   cleanly". In 1.3.11 it does not (C.5), but the raw path is published.
   **Substitute proposed (H, D-3).**
5. The prompt says remote state "pushed as e06dc94" — verified true.

---

## B. PHASE 1C CONTRACT (from `docs/LAB_PHASES.md:305-355`, authoritative)

Precondition: SESSION_LOG shows 1B complete (**met**). Branch `lab1`.
Simulator rules: fresh simulator per run, headless, never `--fast`, kill by
process name.

**Required**
- R1. New package `coco_lab_ros` (depends on `coco_lab`, `rclpy`, `nav2_msgs`).
  Planner node that: snapshots the global costmap per request and stores it
  with the trace; plans from AMCL belief (`map → base_footprint`); runs the
  requested `coco_lab` algorithm; publishes or writes the trace; sends the path
  to controller_server's `FollowPath`. **Never publishes velocity.** Verified at
  runtime AND in a test: exactly one publisher on the controller topic (the
  arbiter); no publisher added to the arbiter's inputs.
- R2. A launch file + lab-only Nav2 parameter overlay; mission `nav2_params`
  untouched. Lightest bringup giving Gazebo + Nav2 + arbiter, executive not
  driving; arbiter mode set through the existing path; state what was used.
- R3. Conformance vs SmacPlanner2D: read its source for the traversal-cost
  model, state how `coco_lab` differs; ≥50 seeded start/goal pairs in the arena;
  Smac path via `ComputePathToPose` on the same costmap snapshot; compare length
  and cost under the declared cost function; gap distribution with smoothing as
  configured, and without if the overlay allows it cleanly. **Do not tune
  `coco_lab` to match.**
- R4. NavFn half: same pairs (or stated subset), NavFn `use_astar` false and
  true via the overlay; compare with Smac and `coco_lab`'s optimum. Reproduce or
  refute M3 (3.165 m vs 3.373 m, 6.2 %); if the M3 goal does not exist in this
  world, say so and use the fresh pairs.
- R5. Three real runs, same start and goal, driven by `coco_lab` A\*, Dijkstra,
  greedy best-first through `FollowPath`. rosbag2: ground-truth pose, AMCL pose,
  TF, planned path, trace, wheel commands, costmap snapshot. Export each to a
  bundle. Report tracking error (GT vs path), duration, recoveries, arbiter
  trace.
- R6. Everything in `docs/RESULTS.md` marked (measured); checkpoint SESSION_LOG;
  commit; stop.

**Optional** — none named by the spec. ("smoothing disabled" is conditional.)

**Deferred (by the spec's silence + ROADMAP)** — the map-quality number *unless*
the owner confirms 1B decision 3 (H, D-1); Lab 3 is its roadmap home
(`docs/ROADMAP.md:280-295`).

**Out of scope** — UI/web/TypeScript/Pyodide (1D–1E); new algorithms (cap is
five); SLAM implementation; any new wheel publisher; arbiter/collision-monitor
changes; `protocol.py`/coco.v1 changes (live mode is Phase 4); MoveIt, RL, Isaac;
changes to the mission's `nav2_params.yaml`; tuning `coco_lab` to Smac.

**Approval gates** (`LAB_PHASES.md:19-30`) — commit/push to `lab1`
pre-approved; push to `main` only as a fast-forward from `lab1` with every test
green; releases/assets ask first; never force-push, `git clean`,
`reset --hard`, force-remove worktrees; user-owned files additive only with the
diff shown.

**UNKNOWN in the contract** — the goal pose for R5; which pairs count as "in
the arena"; the tolerance that counts as conformance agreement; whether the
bundle must carry pose streams (R5 "export each to a bundle" implies yes; 1E
item 8 consumes GT/AMCL/plan overlays). Proposals below; owner confirms.

---

## C. ARCHITECTURE FINDINGS

C.1 **Command chain (FACT, `gazebo_models/launch/nav.launch.py:34-53`,
`custom_teleop/custom_teleop/cmd_vel_arbiter.py:68-87`):**
`controller_server → /cmd_vel_nav → velocity_smoother → /cmd_vel_smoothed →
collision_monitor → /cmd_vel → cmd_vel_relay → /cmd_vel_gated (arbiter:=true)
→ cmd_vel_arbiter → /diff_drive_controller/cmd_vel`. Arbiter inputs:
`/cmd_vel_teleop`, `/cmd_vel_gated`, `/cmd_vel_rl`, `/cmd_vel_approach`,
`/mission/mode`. A `FollowPath` goal enters at controller_server, so the
lab's path rides the existing chain with **no new publisher**. The hook
belongs **above** controller_server, as an action client — nowhere else.

C.2 **Arbiter mode (FACT):** `/mission/mode` (std_msgs/String) or the
`initial_mode` parameter (`arbiter.launch.py:39,61-62`, default `idle`;
`cmd_vel_arbiter.py:216-233`). **REC:** launch the arbiter with
`initial_mode:=nav`. Publishing `/mission/mode` from the lab would add a
publisher to an arbiter input, which R1 forbids.

C.3 **Bringup (FACT):** `nav.launch.py` accepts `params_file:=` and
`arbiter:=true` (`:87-92`), and `mission.launch.py:329-332` composes exactly
`nav.launch.py arbiter:=true` + `arbiter.launch.py`. `full_world_robo.launch.py`
defaults `world:=coco_navigation.world`, `traverse:=false` (`:341-347`). With
`traverse:=false` it spawns ONE ramp at y = 0 (`:191-200`), while the saved map
`coco_navigation` carries four ramp bays at y = ±2, ±6
(`gazebo_models/config/navigation_world.json` `ramp_bays.centres_y`).
**HYP:** `traverse:=false` gives a map/world mismatch; `traverse:=true` (what
every mission run uses) matches. **REC:** lab bringup =
`full_world_robo.launch.py gui:=false traverse:=true` (episode_level fixed) +
`custom_teleop arbiter.launch.py initial_mode:=nav` + `gazebo_models
nav.launch.py arbiter:=true params_file:=<merged lab params>` + the lab node.
No executive, perception, MoveIt, web, platform or RViz.

C.4 **Costmap topics (FACT, `nav2_costmap_2d/src/costmap_2d_publisher.cpp`
@1.3.11 :91-103,158,76):** `/global_costmap/costmap` (OccupancyGrid) is
translated: 0→0, 1..252→`1 + 97(i−1)/251` (i.e. 1..98), 253→99, 254→100,
255→−1. **Lossy — Smac's costs cannot be recovered from it.**
`/global_costmap/costmap_raw` (`nav2_msgs/Costmap`) carries the uint8 master
costs. The global costmap is 0.05 m, `track_unknown_space: true`, layers
`static, obstacle(scan), voxel(scan), inflation(r 0.5, csf 5.0)`,
`robot_radius 0.20` (`gazebo_models/config/nav2_params.yaml:273-332`). It is
**live** (scan layers), so a snapshot is an instant, not the static map.

C.5 **SmacPlanner2D as deployed (FACT, `nav2_params.yaml:345-383` and
source @1.3.11):** plugin id `GridBased`; `tolerance 0.25`,
`allow_unknown false`, `max_iterations 1000000`,
`max_on_approach_iterations 1000`, `max_planning_time 2.0`,
`cost_travel_multiplier 2.0`, `use_final_approach_orientation false`,
`downsample_costmap false`. No `smoother` block ⇒ smoother defaults.
`smac_planner_2d.cpp`: the smoother is constructed unconditionally (:131-136)
and `_smoother->smooth(...)` is called on every non-trivial plan (:323) — **no
parameter disables it.** But the raw A\* path is published on
`unsmoothed_plan` **only when that topic has a subscriber** (:146, :307-310).
`NavFn` is already registered (`use_astar: false`, `tolerance 0.5`,
`allow_unknown false`).

C.6 **Ground truth (FACT):** `/model/coco/odometry` bridged from gz
(`gazebo_models/config/bridge.yaml:46-50`); world→map offset `(2, 0)`
(`navigation_world.json` `world_to_map`; `plan_compare.py:WORLD_TO_MAP_X`);
spawn world (−2, 0) (`coco_config/robot.py:40`) = AMCL initial pose map (0, 0)
(`nav2_params.yaml:52-56`).

C.7 **Reusable pieces (FACT):** `gazebo_models/scripts/plan_compare.py`
(ComputePathToPose client by `planner_id`); `docs/data/navigation_world_run.sh`
(fresh-sim runner with REFUSE-if-anything-running and `ros_clean.sh --list`
checks); `gazebo_models/scripts/ros_clean.sh` (bracketed pattern list,
`:54-231`); `gazebo_models/test/test_cmd_vel_wiring.py` (publisher-count
tests on a private domain); `c2nav42_cmdpath.py record` (command chain +
monitor + GT recorder, referenced by the runner).

C.8 **Where the hook goes (REC):** a new ament_python package `coco_lab_ros`
that depends on `coco_lab`, `rclpy`, `nav2_msgs`, `nav_msgs`,
`geometry_msgs`, `tf2_ros`, `std_msgs`, and (exec only, for its launch file)
`gazebo_models`, `custom_teleop`. Nothing depends on it, so the graph stays
acyclic (CLAUDE.md §6). `coco_lab` never imports `coco_lab_ros` or rclpy.
Pure conversion/metric code lives in `coco_lab_ros` modules that do **not**
import rclpy at module level (duck-typed message inputs), so it is
unit-testable without a ROS graph.

---

## D. COST-MODEL COMPARISON DESIGN

**Two coco_lab configurations, fixed now (pre-registered), not tuned later:**
- **C0 — coco_lab default:** 8-conn, diagonal √2, `corner_cutting=False`,
  `cost_weight 2.0`, `cost_scale 252`.
- **C1 — "same graph as Smac":** C0 with `corner_cutting=True`. Every
  parameter is a toggle or default that existed at `c3713dd`. It models Smac's
  *graph* as read from source, not its output.

Blocked-cell rule for both: raw cost ≥ 253 → OCCUPIED; 255 → UNKNOWN (blocked
by coco_lab's default; matches `allow_unknown: false`); 0..252 → free, with the
cost layer = raw value exactly.

| # | coco_lab quantity | Smac2D / Nav2 quantity | Relation | Label |
|---|---|---|---|---|
| 1 | `edge_cost = base·(1 + 2.0·c[b]/252)` (`grid.py:221-227`) | `getTraversalCost = len·(1 + ctm·c[child]/252)`, ctm = `cost_travel_multiplier` = 2.0 (`node_2d.cpp:68-84`) | **Same form, same constants.** Smac float32, coco_lab float64 | FACT |
| 2 | diagonal √2 | √2 if dx²+dy² > 1.05 | same | FACT |
| 3 | 8-connectivity | 8 offsets always (`node_2d.cpp:110-111`) | same | FACT |
| 4 | corner cutting OFF (C0) / ON (C1) | no corner check (`getNeighbors` :114-153) | **C0 mismatch, declared**; C1 matches | FACT |
| 5 | occupancy: ≥253 blocked, 255 unknown-blocked | `inCollision`: centre cost ≥ INSCRIBED(253); UNKNOWN blocked unless traverse_unknown (`collision_checker.cpp:172-182`) | same after the adapter mapping | FACT (adapter to be tested) |
| 6 | heuristic `euclidean` (cells) | `hypot(dx, dy)` in cells (`node_2d.cpp:86-95`) | same; admissible because multiplier ≥ 1 | FACT |
| 7 | goal test on expansion, closed never reopened | goal test after pop; `wasVisited` skip; `g < g_old` relax (`a_star.cpp:306-378`) | same semantics | FACT |
| 8 | tie-break `low_h` / `fifo` | priority queue on f only; ties are heap order | **not matchable** ⇒ compare costs, never cell sequences | FACT |
| 9 | exact goal cell | on-approach exit: once best h < tolerance/res (0.25/0.05 = 5 cells), returns the best-h node after 1000 more iterations (`a_star.cpp:350-355,381-384`) | **mismatch**: Smac may end ≠ goal ⇒ endpoint check per pair | FACT |
| 10 | start/goal cell | `floor(worldToMapContinuous)` (`smac_planner_2d.cpp:224-247`) | adapter uses the identical floor; tested | FACT |
| 11 | raw cell path | returned path = **smoothed**; raw on `unsmoothed_plan` | compare raw↔raw, smoothed separately | FACT |
| 12 | geometric length L (m) | L of returned poses | directly comparable | derived |
| 13 | waypoint count | pose count | **reported, never compared as quality** (the ISRO "Steps" lesson) | — |
| 14 | planning time (pure Python) | `planning_time` in the action result (C++) | **not comparable** (implementations); reported only | — |
| 15 | — | NavFn per-cell cost `50 + 0.8·c`, obstacle ≥ 253 (`navfn.hpp:52-67`); gradient-descent extraction | **different cost model**; compare by L and I only | FACT (constants); propagation not source-read here |
| 16 | — | map quality | **no relation**; not part of D | — |

**Metrics (formulas fixed now):**
- **L** = Σ‖pᵢ₊₁ − pᵢ‖ over the path poses (m).
- **E** (grid edge-sum cost, cells) = Σ C1-`edge_cost`(aᵢ→aᵢ₊₁) over the cell
  sequence, computed by `coco_lab.Grid.edge_cost` in float64. Defined only
  when consecutive cells are 8-neighbours (true for coco_lab and, HYP, for
  Smac's raw path — checked; a path that fails the check is reported as
  "E undefined", not coerced).
- **I** (continuous declared cost, m) = Σ over samples every Δ = res/20 =
  2.5 mm along the polyline of Δ·(1 + 2.0·c(x)/252), c(x) = raw cost of the
  cell containing x. Flag `enters_blocked` if any sample has c ≥ 253 or 255.
  Applied identically to every path (coco_lab, Smac raw, Smac smoothed, NavFn
  ×2). I ≠ E·res even for grid paths (entering-cell vs. along-path
  convention); E is the conformance quantity, I is the cross-planner quantity.
- **endpoint_ok** = last cell == goal cell.
- **c_max** = max c(x) along the path (a clearance proxy in costmap units).

**Pre-registered prediction (HYP, stated before any measurement):** for
every valid pair with `endpoint_ok(Smac raw)`, E(Smac raw) = E(coco_lab
C1 Dijkstra) within **relative 1e-4** (float32 accumulation over ≲ 10³ edges;
the bound is a derived allowance, not a measured one). A pair outside it is a
**disagreement**: reported with its cells and investigated, never tuned
away. E(C0) ≥ E(C1) always, since C0's graph is a subgraph of C1's (a
property the implementation also tests on random maps).

---

## E. THREE-RUN EXPERIMENT DESIGN (plus the conformance experiment)

### E.1 Conformance (R3 + R4) — one fresh simulator, robot stationary

Fixed: git commit; merged params SHA-256; map `coco_navigation.yaml/.pgm`
SHA-256; world `coco_navigation.world`, `traverse:=true`, episode fixed;
Nav2 1.3.11; ROS_DOMAIN_ID (REC 65, unused by prior harnesses); robot at spawn;
AMCL initial (0, 0, 0).

1. Bring up (C.3) with an overlay whose ONLY change is
   `planner_plugins: ["GridBased", "NavFn", "NavFnAStar"]` + a `NavFnAStar`
   block = NavFn's block with `use_astar: true`. GridBased and NavFn untouched.
2. Wait for all Nav2 lifecycle nodes active, `costmap_raw` arriving, and two
   consecutive `costmap_raw` messages with an identical content hash
   (stationary settle).
3. Snapshot S0. Candidate cells = raw cost ≤ 252. Draw pairs with
   `random.Random(20260929)` over the row-major-sorted candidate list; accept
   if start–goal distance ≥ 2.0 m. Pairs coco_lab C1 finds unreachable are
   kept in a separate "no-path" list (Smac must also fail them; reported).
4. For each pair, subscribe `unsmoothed_plan` first, then
   `ComputePathToPose(use_start=true, planner_id=X)` for X ∈ {GridBased,
   NavFn, NavFnAStar}; bracket each call with `costmap_raw` hashes. A pair is
   **void** if any hash differs from S0; void pairs are counted and reported.
5. Continue until **50 valid** pairs, cap 100 draws. <50 valid at the cap =
   a documented failure (F-5), not a relaxed rule.
6. coco_lab on S0: Dijkstra C1, A\* C1 (euclidean), Dijkstra C0.
7. **Named extra (not one of the 50):** the M3-analogue — spawn → current
   `plan_compare.py` default goal (world (0.5, 6.0) = yellow pre-ramp).
   **FACT: the M3 goal does not exist in this world** — M3 went to "the
   pre-ramp pose in lane +0.75" around "the Zone A gate" (`docs/RESULTS.md:88-95`);
   the current lanes are y = ±2, ±6 (`coco_config/robot.py:330-339`) and the map
   is 500 × 380 cells, where the comment at `nav2_params.yaml:279-280` records a
   254 × 199 arena. So M3's 6.2 % is **neither reproduced nor refuted** on its
   own inputs; the analogue is labelled as a different world.

Reported: per pair, every metric in D for every path; distributions (n, min,
p25, median, p75, max) of E-gap (Smac raw vs C1), I-gap and L-gap (Smac smoothed
vs C1), NavFn(false)/NavFn(true) L and I vs C1 and vs Smac; E(C0)/E(C1);
endpoint failures; void count; no-path agreement.

### E.2 The three real runs (R5)

| Run | Algorithm | Heuristic | Graph | Tie-break | Order |
|---|---|---|---|---|---|
| R-A | A\* | euclidean | C1 | low_h (default) | 1 |
| R-D | Dijkstra | zero | C1 | low_h | 2 |
| R-G | greedy best-first | euclidean | C1 | low_h | 3 |

Fixed for all three: start = spawn (world (−2, 0, 0)); **goal G\* = world
(0.5, 6.0), yaw 0 → map (2.5, 6.0, 0)** (REC, owner confirms — H, D-4; chosen
because it is the existing `plan_compare.py` default and a pose the mission
already drives, i.e. for reasons independent of these results); world,
params, map, commit, domain as E.1; `FollowPath(controller_id="FollowPath",
goal_checker_id="goal_checker")`; one plan per run, **no replanning** (stated
as a property of the lab node, unlike bt_navigator); a **fresh simulator per
run** with `ros_clean.sh` before and after.

Path handed to FollowPath: C1 cell centres in the map frame, identity
orientation replaced by direction of travel, last pose yaw = G\* yaw (mirrors
Smac with `use_final_approach_orientation: false`, `smac_planner_2d.cpp:344-346`).
Unsmoothed — the learner's path is the one driven.

Each run's start comes from its own AMCL belief at plan time, and its costmap
is its own snapshot. **The inputs are therefore held equal by construction but
not bit-identical across runs**: the start-cell and snapshot hashes of all
three runs are reported side by side, and differences are stated, not hidden.

Per run, measured: FollowPath result code; duration (sim time, goal accept →
result; wall time reported beside it, since RTF < 1); **tracking error** =
distance from each GT sample (map frame via `world_to_map`) to the nearest
point of the planned polyline — mean, p95, max; the endpoint GT distance to
G\*; **belief gap** = ‖AMCL − GT‖ at the AMCL rate — mean, max; recoveries =
goals seen on the behavior_server actions (`spin`, `backup`,
`drive_on_heading`, `wait`) during the run (expected 0, since no BT is in the
loop — measured, not assumed); arbiter trace = `/cmd_vel_arbiter/status`
source/mode timeline plus the `/diff_drive_controller/cmd_vel` publisher
count sampled at start, middle and end; collision-monitor state timeline.

A run that fails (FollowPath aborts, the goal is not reached) is a
**result**. A run is **void** only under pre-declared infrastructure causes:
the sim/Nav2 does not reach active within its budget, a foreign Gazebo is
detected, or the publisher invariant is broken by an external process. One
re-run per void run; voids are reported.

---

## F. EVIDENCE / ARTIFACT DESIGN

**Committed (small):**
- `coco_lab_ros/` — package, `config/nav2_lab_overlay.yaml`,
  `launch/lab_stack.launch.py`, tests.
- `docs/data/lab1c/` — `conformance.py`, `real_run.sh`, `export_run.py`,
  `metrics.py` if not in the package; `conformance.json` (every pair, every
  metric, all hashes), `runs.json` (per-run metrics + provenance),
  `README.md` (reproduction commands).
- `docs/labs/CONFORMANCE.md` — table D with the upstream file SHA-256s.
- `docs/RESULTS.md` "COCO Lab Phase 1C" (every number marked (measured) or
  (derived)); `BUNDLE_FORMAT.md` 1.1 (if D-5 approved); SESSION_LOG entries;
  PROJECT_STATE COCO LAB row; HOW_TO_RUN subsection.

**Not committed (large):** rosbag2 directories under
`~/coco_lab_runs/lab1c/<run_id>/`, with their SHA-256 recorded in the committed
JSON. Bag hash definition (declared; to be checked against what `bundle.py`
already expects): SHA-256 over the sorted list of `(relative path, file SHA-256)`
lines of the bag directory.

**Bundles:** one per real run, `source_kind: recorded-run`, embedding the
costmap snapshot (occupancy + raw cost layer), the full trace, and `rosbag`
`{sha256, sim_time_start, sim_time_end}`. Pose streams (GT, AMCL, plan, wheel
commands) as **additive arrays under a MINOR bump to bundle 1.1** (REC — H,
D-5): `run.gt.{t,x,y,yaw}`, `run.amcl.{t,x,y,yaw}`, `run.plan.{x,y}`,
`run.cmd.{t,v,w}` plus a `run` manifest object. Trace schema stays 1.0. 1D has
no decoder yet, so the bump is cheap now. One small synthetic recorded-run
golden fixture is added for 1D. Committed only if the three together are
≤ 10 MB (measured); otherwise ask (release asset = ask first).

**rosbag2 topics** (`--include-hidden-topics` for the action topics):
`/model/coco/odometry`, `/amcl_pose`, `/tf`, `/tf_static`, `/clock`,
`/lab/plan` (nav_msgs/Path, transient local), `/lab/status` (std_msgs/String:
algorithm, trace SHA-256, bundle path, phase), `/lab/costmap_snapshot`
(nav2_msgs/Costmap, transient local, published once — instead of recording
`costmap_raw` at 5 Hz), `/diff_drive_controller/cmd_vel`, `/cmd_vel_gated`,
`/cmd_vel_nav`, `/cmd_vel_smoothed`, `/cmd_vel`, `/cmd_vel_arbiter/status`,
`/collision_monitor_state`, `/follow_path/_action/{status,feedback}`, and the
behavior-server action status topics. Exact hidden-topic names: UNKNOWN until
listed live (step I.8 dry run).

**`run.json` provenance (every run and the conformance session):** run id
`lab1c-<conf|run>-<algo>-<UTC>`; git commit + dirty flag; `coco_lab` and
`coco_lab_ros` versions; Nav2 package versions; SHA-256 of the mission
`nav2_params.yaml` (must equal HEAD's), the overlay, the merged file, the map
yaml + pgm, and the world file; launch arguments; ROS_DOMAIN_ID; seed; start,
goal, algorithm, heuristic, graph config; snapshot `content_hash`; bag
SHA-256; sim-time range; wall start/end (UTC); load average; result/void
status with reason.

---

## G. TEST PLAN

**Unit (no ROS graph; `coco_lab_ros` pure modules)**
- `costmap_raw` → LabMap/Grid: the row flip (Nav2 row 0 = bottom, coco_lab
  row 0 = top) on an asymmetric fixture; 252 → free with cost 252, 253/254 →
  OCCUPIED, 255 → UNKNOWN; cost layer values exact.
- world↔cell: identical to Nav2 `worldToMapContinuous` + floor on boundary
  values; cell centre → world round trip.
- Path → `nav_msgs/Path`-shaped poses: centres, travel-direction yaw, final
  yaw = goal yaw.
- Metrics L, E, I, `endpoint_ok`, `c_max` against hand-computed fixtures,
  including "E undefined" for a non-neighbour step and the `enters_blocked`
  flag.
- Params deep-merge: nested override, lists replaced (not concatenated), base
  untouched, deterministic output bytes.

**Deterministic / property**
- Property (hypothesis, ≥1,000 maps, as in 1A): E\*(C0) ≥ E\*(C1), and the
  C1 optimum equals the networkx optimum on the corner-cutting graph.
- Golden: a committed small `costmap_raw` fixture → fixed C1 Dijkstra cost and
  trace SHA-256.
- The existing `coco_lab` rclpy-free guard still passes; a new guard: `coco_lab`
  has no import of `coco_lab_ros`.

**Integration (ROS, private domain, no Gazebo)**
- Safety guard: an AST scan of `coco_lab_ros` finds no `Twist`/`TwistStamped`
  import and no `create_publisher` on the controller topic or any arbiter
  input; the constructed node's publisher list (`get_publisher_names_and_types_by_node`)
  contains none of them.
- FollowPath client against a fake action server: the goal carries the
  expected poses, `controller_id` and `goal_checker_id`.
- **Static conformance smoke (REC):** `map_server` + `planner_server`
  (lab-merged params) + static TF on a committed small map; call
  `ComputePathToPose` and compare with C1 on the same raw costmap. It proves the
  pipeline and the `unsmoothed_plan` subscription before any Gazebo run.
  (Skipped-with-reason is not acceptable; if it cannot run, it is recorded as
  not built.)
- Launch test: `lab_stack.launch.py` resolves; the merged params differ from the
  mission's only in `planner_server.planner_plugins` + `NavFnAStar`.
- `ros_clean.sh` contains a bracketed pattern for every new executable
  (existing guard tests extended, not replaced).

**Real-run checks (in the runners, recorded as PASS/FAIL lines)**
- Refuse to start if any Gazebo / Nav2 / `ros_clean.sh --list` hit exists.
- Params readback of `planner_server` equals the merged file; the mission
  `nav2_params.yaml` SHA-256 equals HEAD's.
- `/diff_drive_controller/cmd_vel`: exactly 1 publisher, node
  `cmd_vel_arbiter`, at start/middle/end. Publisher sets on the 5 arbiter
  inputs identical before vs after the lab node starts.
- Arbiter status reports mode `nav`.

**Regression**
- `coco_lab` both routes (baseline 314 / 317, re-measured at I.0); the
  `coco_lab_ros` suite; `gazebo_models` (`ros_clean.sh` changes), per package,
  cwd = package dir, clean ROS graph, `--ignore=test_integration` as CLAUDE.md
  prescribes; `custom_teleop` must be unchanged (no file touched).

---

## H. RISKS AND UNKNOWNs

**Decisions needed from the owner before implementation**
- **D-1 Map quality in 1C?** The spec is silent; 1B decision 3 says "deferred to
  1C". REC: **keep it out of 1C** and record it for Lab 3 (it needs a
  SLAM drive, an alignment definition and a metric; `slam.launch.py` +
  `map_drive.py` exist). If the owner wants it in 1C, it gets its own design
  block and a 4th fresh-sim run, and nothing is scored against the generator
  map.
- **D-2** Snapshot `costmap_raw` instead of `costmap` (C.4). REC: yes; also
  store the lossy grid's hash for traceability.
- **D-3** "Smoothing disabled" → use `unsmoothed_plan` from the same call (C.5).
  REC: yes, and state in RESULTS.md that the overlay cannot disable it in 1.3.11.
- **D-4** Goal G\* for the three runs (E.2). REC: world (0.5, 6.0), yaw 0.
- **D-5** Bundle 1.1 additive pose arrays vs. a sidecar file. REC: 1.1.
- **D-6** Commit bundles to git (≤10 MB) vs. a release asset (ask first).

**Risks / unknowns (not facts)**
- HYP: `traverse:=false` mismatches the map (C.3) — verify by the rendered
  costmap vs. the map at I.8's dry run, whichever flag is used.
- UNKNOWN: whether `unsmoothed_plan` resolves to `/unsmoothed_plan` (the
  node-relative name on `planner_server`) — verify live.
- UNKNOWN: costmap stability while stationary (the scan layers may flicker) —
  the void rate is measured; a high rate is a finding.
- UNKNOWN: whether FollowPath/DWB tracks an unsmoothed 8-connected staircase
  well, especially greedy's cost-hugging path. A poor result is reported, not
  smoothed away.
- UNKNOWN: pure-Python planning latency on the 500 × 380 grid inside the node
  (1B measured 1.022 s full-arena Dijkstra at 0.05 m offline) — measured,
  reported.
- Concurrency: other agents (Codex/agy) run COCO sims on this machine (memory,
  SESSION_LOG Phase 0). "One Gazebo at a time" means the runner refuses, and the
  owner may need to clear the machine — that is a scheduling risk, not
  something the runner may kill (`ros_clean.sh` scoping rule).
- Load sensitivity: timing numbers are reported with the load average; the
  CLAUDE.md load-sensitivity note applies to test flakes.
- The upstream `.cpp` files are not installed: citations depend on re-fetching
  tag 1.3.11 and recording SHA-256s. If the installed binary were built from a
  patched source, the reading could differ — the static smoke (G) is the
  behavioural cross-check.
- HYP: NavFn's longer path in M3 comes from its ~2× stronger per-unit cost
  aversion (`1 + 0.016c` normalised vs Smac's `1 + 0.0079c`) and/or
  gradient-descent extraction. 1C measures on new pairs; it does **not**
  apportion the M3 gap on M3's inputs, which no longer exist.

**Failure handling (pre-declared; the experiment is never redefined afterwards)**
- F-1 Stack will not launch / Nav2 not active within budget → void, one
  retry, then stop and report.
- F-2 `unsmoothed_plan` not captured → Smac-raw rows marked "not captured";
  smoothed rows still reported; the conformance claim is **not** made.
- F-3 Planner config differs from D (readback mismatch) → stop before
  measuring; report.
- F-4 Robot fails to reach G\* → a result; all metrics up to the abort.
- F-5 <50 valid pairs by 100 draws, or maps differ unexpectedly (snapshot vs
  static map) → report counts and the diff; no rule change.
- F-6 E disagreement beyond 1e-4 → report each pair; investigate from source;
  no coco_lab change to close it.
- F-7 Incomplete bag (topic missing) → the run is reported with the missing
  topics named; the bundle omits those arrays (not zero-filled).
- F-8 Non-reproducible measurement → report both values; no averaging.

---

## I. IMPLEMENTATION SEQUENCE (smallest, ordered; commit after each green step)

0. **Baseline + plan in repo.** Commit this file as
   `docs/labs/PHASE_1C_PLAN.md` + a SESSION_LOG "1C-0" entry; re-measure `coco_lab`
   (pip + colcon) and `gazebo_models` baselines; re-fetch Nav2 1.3.11 sources
   and record SHA-256s.
1. `coco_lab_ros` skeleton + guard tests (no velocity publisher, rclpy-free
   `coco_lab`, graph acyclic).
2. Pure modules + unit/property tests: costmap adapter, world↔cell, path
   builder, metrics (L/E/I), params deep-merge.
3. Overlay YAML + merge + `lab_stack.launch.py` + `ros_clean.sh` patterns +
   launch tests.
4. `lab_planner` node (snapshot, TF belief, plan, trace/bundle write,
   `/lab/plan`, `/lab/status`, `/lab/costmap_snapshot`, FollowPath client) +
   fake-action-server test.
5. Static conformance smoke (map_server + planner_server, no Gazebo).
6. Bundle 1.1 (if D-5) + exporter bag → bundle + golden fixture + tests.
7. Conformance runner; one fresh-sim session; `conformance.json`.
8. Real-run runner: one dry run (topic list, hidden-topic names, map/world
   check — **not** counted as a run, and its data is not used); then R-A, R-D,
   R-G, a fresh sim each; export; `runs.json`.
9. Docs (RESULTS, CONFORMANCE, BUNDLE_FORMAT, PROJECT_STATE, HOW_TO_RUN),
   full regression, SESSION_LOG checkpoint, commit, push `lab1`.

---

## J. ACCEPTANCE CRITERIA (each objectively checkable)

1. `coco_lab_ros` builds with colcon; its tests pass 0 failed / 0 skipped.
2. `coco_lab` tests are still green on both routes (counts reported;
   ≥ 314 / ≥ 317); the rclpy-free guard passes.
3. A test proves `coco_lab_ros` creates no velocity publisher and no publisher on
   any arbiter input; the live check shows `/diff_drive_controller/cmd_vel`
   publisher count 1 (`cmd_vel_arbiter`) at start/middle/end of every run.
4. The mission `nav2_params.yaml` is byte-identical to `e06dc94`'s; the merged
   params differ only in `planner_plugins` + `NavFnAStar` (tested).
5. Every new executable has a bracketed `ros_clean.sh` pattern (tested).
6. `docs/labs/CONFORMANCE.md` states the Smac and NavFn cost models with
   upstream file + line + SHA-256 citations, and the C0/C1 differences.
7. `conformance.json` holds ≥ 50 valid pairs (or F-5 is documented), with
   L/E/I/endpoint/c_max per path and the void and no-path counts.
8. RESULTS.md reports the E-gap distribution (Smac raw vs C1), the I/L-gap
   distributions (smoothed), NavFn false/true vs C1 and vs Smac, and states
   plainly that M3's goal does not exist in this world.
9. Three real runs (R-A, R-D, R-G) each have a bag (SHA-256 recorded), a bundle
   that loads and validates with `coco_lab.bundle`, and `runs.json` with
   tracking error (mean/p95/max), duration (sim and wall), recoveries, belief
   gap, and the arbiter timeline — or a documented failure/void per E.2.
10. Every number added to docs is marked (measured) or (derived) and traces to
    a committed JSON or a test.
11. SESSION_LOG has a "Phase 1C — COMPLETE" (or "STOPPED at …") entry with the
    exact next command; `lab1` is pushed to `jazzy2`.

## K. MILESTONE BOUNDARY

**Phase 1C complete** = J1–J11 true. A negative result (conformance disagreement,
failed run) still completes 1C if it is documented per H.

**Not 1C; left for 1D and later:** the TypeScript bundle decoder (it must
handle bundle 1.1's run arrays), the trace player, Pyodide, CI, Pages (1D);
the exhibit and the "Driven by COCO" replay UI (1E); live mode / coco.v1 intents
(Phase 4); the map-quality number (Lab 3, unless D-1 says otherwise);
apportioning M3's historical 6.2 % on its original inputs (impossible here —
they do not exist in this world).

## L. NEXT ACTION (after approval)

In a fresh Claude Code session on branch `lab1` in
`<repo>/.claude/worktrees/lab1`: commit this plan (with the owner's D-1…D-6
answers recorded at its top) as `docs/labs/PHASE_1C_PLAN.md`, together with a
SESSION_LOG "1C-0" entry, then execute step I.0.
