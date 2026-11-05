# R2.7 · The same file as a ROS 2 node in Gazebo + Nav2 — STACK (simulation) beside MODEL

**Evidence class: STACK** — the full ROS 2 Jazzy stack (Nav2 1.3.x, COCO's `cmd_vel_arbiter`) in Gazebo Harmonic,
headless, one fresh simulator per session, never `--fast`. **No physical robot exists; nothing here is HARDWARE.**
MODEL numbers beside them are COCO Lab's Python reference on the same scenarios. Raw runs (read-only evidence):
`~/coco_lab_runs/r2/` — every file the numbers come from is checksummed in [`raw_checksums.sha256`](raw_checksums.sha256).
All numbers: [`summary.json`](summary.json); the Studio's "Browser vs ROS 2" panel: [`stack.json`](stack.json) (keyed by
each file's sha256, so it shows only for that exact file).

## How

- **Export** (Studio → "Export ROS 2", or `python -m coco_lab.ros2_export FILE --name NAME`): an `ament_python`
  package `coco_user_<name>` with the file unchanged, the same allowed-modules guard as the browser
  (`coco_lab.user_code`), a node, a launch file and (planner/controller) a behaviour tree naming the user's server.
  The four packages here were built in `~/coco_lab_r2_ws` (this repository's overlay; **no change to COCO's robot
  repository**: the bring-up is this repository's `gazebo_models` and `custom_teleop`).
- **Swap-in** (`tools/r2/ros2_session.sh` → `tools/m6/m6f8_run.sh` with its additive `NAV_LAUNCH`, `NAV_DRIVER`,
  `NAV_NODES_OVERRIDE`; unset, M6F.8 runs exactly as before):
  planner = `ComputePathToPose` served as `user_compute_path_to_pose` on `/global_costmap/costmap_raw`;
  controller = `FollowPath` served as `user_follow_path`, publishing `TwistStamped` on `/cmd_vel_nav` into the
  velocity smoother, collision monitor and `cmd_vel_arbiter` (still the only wheel publisher: `wheel_publishers.txt`
  of every session); localiser = AMCL not started, the node publishes `/amcl_pose` and `map → odom`.
- **Driver** `tools/r2/ros2_bench.py`: `plan` (ComputePathToPose to each server in turn, same costmap, same request),
  `drive` and `round` (NavigateToPose; the result by Nav2's status, the truth by Gazebo's pose).
- **Scenarios**: every 5th of COCO-Bench `depot-nav-100` v0 ([`depot20_plan.json`](depot20_plan.json), 20; the Depot's
  world frame is its map frame) and 5 of them for drives ([`depot5_drive.json`](depot5_drive.json)); the four colour
  rounds of the Colours Depot ([`goals/`](goals), M6F.8's `m6f8_goals.py`), actors on (they stop for COCO).
- Files: the A* starter `coco_lab/templates/planner_astar.py` (sha256 `31ba4f66…`), Gautham's Lazy Theta*
  ([`files/theta_star.py`](files/theta_star.py), PR #31's file, `650c80cc…`), the pure-pursuit starter (`5a1f225d…`),
  the particle-filter starter (`de1102c9…`). Each node logs its file's sha256 at start (`nav.log`).

## Results (power-saver profile; see "Conditions")

### Planners — 20 scenarios × 3 sessions, each request sent to stock Nav2 (Smac 2D) and to the user planner(s)

| | plans found | median length (m) | STACK − MODEL, paired median | vs stock, paired median | planning time, median wall |
| --- | --- | --- | --- | --- | --- |
| stock Nav2 (Smac 2D) | **42/60** | 33.103 | — | — | 0.19 s |
| A* starter | **60/60** (MODEL 20/20) | 30.061 | +0.232 m (+0.8 %), n=60 | +0.551 m, n=42 | 3.46 s |
| Lazy Theta* | **57/60** (MODEL 20/20) | 28.495 | −0.086 m (−0.3 %), n=57 | −0.742 m, n=39 | 41.2 s |

- **Stock fails the same 6 scenarios in every session**: s036, s041, s046, s051 with 205 START_OCCUPIED, s061, s086
  with 208 NO_VALID_PATH. A convention difference, not a better algorithm: Nav2's planner_server refuses a start (or
  goal) cell in inflated cost, while COCO Lab's planning family — and therefore the user node — snaps start and goal to
  the nearest free cell first. Stated so the 60 vs 42 is not read as "the starter beats Smac".
- **Theta\*'s 3 misses are all session 1** (s006, s016, s026: no result within that session's 120 s wait). Sessions
  2 and 3 used a 600 s wait: 20/20 each (slowest 198 s). Pure-Python Lazy Theta* on the 0.05 m costmap is slow;
  that is the file's cost, reported, not hidden.
- **Caveat, session 2**: a Theta* node left over from session 1 was still running (found after the session; killed;
  the session tooling now kills every user node after a session). Both nodes ran the same file (same sha256), so
  session 2's answers are that file's either way, but its planning times may include the extra process's load.
- Planning time compares nothing across devices: MODEL times are not shown against it.

### Drives — NavigateToPose, 5 Depot goals, the planner swapped in, Nav2's stock controller (RPP)

| planner | reached | per goal (status, driven m, truth to goal m) |
| --- | --- | --- |
| stock Nav2 | **3/5** | s001 ✓ 19.8 / 0.26 · s021 ✓ 22.5 / 0.30 · s041 ✗ 208 · s061 ✗ 208 · s081 ✓ 35.7 / 0.26 |
| A* starter | **4/5** | s001 ✓ 19.9 / 0.38 · s021 ✓ 22.3 / 0.32 · s041 ✗ 208 · s061 ✓ 29.5 / **1.13** · s081 ✓ 36.2 / 0.29 |
| Lazy Theta\* | **0/5** | s001 ✗ 104 at 2.20 m · s021 ✗ 104 at 2.17 m · s041 ✗ 208 · s061 ✗ 104 · s081 ✗ 104 |

- **Theta\* plans, but Nav2's controller will not follow them.** Four aborts are 104 (FollowPath failed); the session
  logs RPP's "detected collision ahead!" **551** times (stock 39, A* starter 73). The plans are any-angle lines that
  take corners close (MODEL median minimum clearance 0.033 m on depot-nav-100, R2.6), and RPP's collision check stops
  when the robot projected along the path meets obstacle cost. *That mechanism is INFERENCE*: the cost under each path
  was not recorded. A planner that wins on path length in the model loses every drive here — the negative result stays
  visible in the panel beside its planning numbers.
- **s041 fails for all three planners** (208, the robot moves 0.005 m): in plan mode (explicit start) both user
  planners find it, so it is the live start in drive mode — the spawned robot's own pose with actors running.
  UNRESOLVED (classified, not diagnosed); it is the same for every planner, so it does not separate them.
- **A* starter s061**: Nav2 reported success, but Gazebo's truth was 1.13 m from the goal — a localisation error
  (AMCL), not the planner's; reported as measured.

### Controller — the pure-pursuit starter as Nav2's FollowPath, the four colour rounds, 5 runs each

| | rounds completed | legs reached | time per leg, median (sim s) | STACK − MODEL, paired per leg |
| --- | --- | --- | --- | --- |
| STACK | red 5/5, green 5/5, blue 5/5, yellow 5/5 | **40/40** | 19.24 | **+0.145 s** median (n=8 legs; range −0.76 to +0.59 s) |
| MODEL | — | 8/8 | 19.40 | |

Nav2's own `controller_server` received **no** FollowPath goal in these sessions (0, against 8 in the stock drive
session); `cmd_vel_arbiter` was the only wheel publisher. Truth to goal at each leg end: 0.22–0.40 m (Nav2's
tolerance 0.25 m is on the AMCL pose). Paired gap = median of a leg's 5 STACK runs minus the model's time on it.

### Localiser — the particle-filter starter in place of AMCL, one red round (a smoke run, not a rate)

AMCL not started (no `[amcl]` line in `nav.log`); the node published `/amcl_pose` and `map → odom`, and Nav2 drove on
it: **2/2 legs**; its estimate's error against Gazebo's truth at the leg ends **0.063 m, 0.258 m** (MODEL, same legs:
0.097 m, 0.110 m).

## Conditions

Laptop on AC, NVIDIA GeForce RTX 4050 Laptop GPU (driver 580.178.04), Nav2 package versions in each session's
`meta.json`. **Power profile: `power-saver` for every session above** (the laptop's own setting; the prompt asks for
balanced — a deviation, found afterwards in `meta.json`). Success counts and sim-time numbers do not depend on it;
**wall-clock planning times do**. The balanced check below re-runs the planning comparison and the Theta\* drive.
Sessions ran from the R2 branch with the R2.7 tools still uncommitted (`git_dirty_paths` in `meta.json`); the files
under test are named by sha256 in every session, and the tools are committed with this README.

## Balanced check

Pending: `plan_balanced_1` and `drive_balanced_coco_user_theta_star` (balanced, AC) are running.
