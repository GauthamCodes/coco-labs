# M6F.8 — Gazebo and Nav2 validation of the Depot: the plan (pending, machine busy)

Not run. Throughout this session (2026-10-17, 16:10–18:40) Codex was active (`codex
resume`, PID 18281) with seven to eight `lab_web/tools/perf/serve_dist.mjs` measurement
servers up, and the prompt forbids starting Gazebo while Codex might be measuring. This
file is what the run needs, found by reading the launch files; nothing here is measured.

## Preconditions (check, record, refuse otherwise)

- `pgrep -fa codex` shows no Codex session and no `serve_dist.mjs`, playwright, vite
  preview or Chromium measurement runs; `ps aux | grep -Ei 'gz|gazebo|isaac|ros2'` shows no
  simulator and no robot batch; AC online; profile balanced (record power and driver).
- A colcon overlay of this worktree (none exists yet): `scripts/build_overlay.sh
  <overlay dir>` (a new directory, checked with `ls -d` first; never `~/coco_m1_ws`, the
  robot project's), plus the `moveit_prefix` symlink for the 7 MoveIt tests. The same
  overlay lets the 4 `coco_lab_ros` tests that need `gazebo_models` in the ament index run.

## Facts the run depends on (read from the code)

1. `full_world_robo.launch.py world:=<abs path>` accepts an absolute world path
   (`world_file = world_arg if os.path.isabs(world_arg) ...`).
2. `ros_clean.sh` sweeps simulators by `g[z] sim.*gazebo_models/worlds`: a world outside a
   `gazebo_models/worlds` directory would escape the orphan sweep. So the generated Depot
   world is written to `~/coco_lab_runs/m6/gazebo_models/worlds/coco_depot_v1.sdf` (with its
   `meshes/` and `actors.json`) — the sweep matches without editing `ros_clean.sh`.
3. COCO spawns at `coco_config.robot.SPAWN_XY` (world (−2, 0)), which is outside the Depot's
   hall. After the spawn and before Nav2: `gz service -s /world/coco_depot_v1/set_pose` to
   the Depot start (23, 6, 0). The derived `nav2_params.yaml` already sets AMCL's initial
   pose to the start (`tools/m6/gen_level.py`).
4. `traverse:=false` (the default): the generated world already contains its ramp and
   mezzanine; `traverse:=true` would also spawn the COCO arena's four bays.
5. Nav2: `nav.launch.py map:=<.../nav2/coco_depot_v1.yaml> params_file:=<.../nav2/nav2_params.yaml>`
   (generated at 0.05 m with `--nav-res 0.05`).
6. Actors: the generated world has them as models with collision bodies at their t = 0
   pose; moving them needs a driver calling `/world/coco_depot_v1/set_pose` from
   `actors.json` (Lab 5's `actor_node` pattern, through gz-transport). Not written: the
   smoke test runs with actors parked, and says so.

## The run

1. Generate: `tools/m6/gen_level.py worlds/coco_depot_v1.yaml --nav-res 0.05 --gz-check
   --out ~/coco_lab_runs/m6` and move/arrange as in fact 2; check the checksums against
   `docs/v2/m6/data/coco_depot_v1_outputs.json`.
2. Fresh simulator: `ros_clean.sh`, then launch headless (`gui:=false`) on a private
   `ROS_DOMAIN_ID`, never `--fast`; teleport COCO (fact 3); start Nav2 (fact 5); wait for
   `nav.online` / an AMCL pose.
3. Planning smoke test: `NavigateToPose` goals across the zones the Nav2 map allows (the
   loading dock, high-bay aisle 1 and 3, the office corridor and a room, the workshop
   maze, the dispatch floor; **not** the mezzanine deck, which the 2D Nav2 map holds as a
   silhouette), each recorded as succeeded / failed with Nav2's result code. Raw logs to
   `~/coco_lab_runs/m6/<run>/`; a summary with checksums to `docs/v2/m6/data/m6f8/`.
   Evidence class STACK.
4. If that works: the first real ROS 2 ghost — Nav2 driving Fetch Rush seed 1's driving
   legs (start → `obj_dock`'s pre-grasp pose → Dock 2), recorded as a bag and converted with
   `coco_lab_ros.adapter` into a Research recording with a checksum.
5. `ros_clean.sh` after every run; one simulator at a time; a fresh simulator per run.

MoveIt picks in the Depot are out of scope here (M6 UI-phase work).
