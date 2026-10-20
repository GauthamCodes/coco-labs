# The Arena model (M1.3)

Tier 1 of README §5.1: a deterministic 2D simulator that runs beside the
planners in the browser (Pyodide + `coco_lab`). Code:
[`coco_lab/coco_lab/arena.py`](../../coco_lab/coco_lab/arena.py), RNG
[`coco_lab/coco_lab/rng.py`](../../coco_lab/coco_lab/rng.py); tests
`coco_lab/test/test_arena.py`, `test_rng.py`. Evidence class: **MODEL**.

## What it is, and what it leaves out

The Arena is Sketch's world (Lab 2), run as a fixed-step simulator:

- **The world** is the occupancy map generated from the World Spec
  (`worldspec.arena_map`, equal to the Stack's saved map cell for cell;
  [WORLD_SPEC.md](WORLD_SPEC.md)).
- **Motion:** a unicycle integrated exactly for `dt` (Sketch's
  `step_pose`), with the commanded `(v, w)` approached at the spec's
  acceleration limits (2.0 m/s², 4.0 rad/s² for COCO). Wheels never slip.
- **Collision:** a step whose end puts the robot's centre within
  `radius / 2` of an obstacle is refused (Sketch's rule); the robot stays
  and its velocity is zeroed.
- **LiDAR:** Sketch's ray-caster (Amanatides and Woo) with the spec's
  480-beam LiDAR, optional Gaussian range noise (default 0: Gazebo's
  `gpu_lidar` for COCO declares none).
- **No localisation in M1:** the robot's belief is its true pose, so
  `coco.robot.state` and `coco.truth.pose` carry the same numbers (each
  labelled; M2 adds the estimate).
- **Planning:** a goal is planned with the chosen planner (BFS, Dijkstra,
  A\*, greedy, weighted A\* at w = 2) on the map inflated by the robot's
  radius, 8-connected; the route is thinned to its turns and followed with
  Sketch's `drive_command` (the same law that drove the Gazebo robot in
  Lab 2) at the spec's autonomous limits (0.3 m/s, 1.0 rad/s).

## Inputs

Every external action is an `InputEvent` (channel `coco.input.events.v1`),
applied at the **start** of its `tick`, in order:

| kind | effect |
|---|---|
| `goal` | plan to `(x, y)` (map frame) with the current planner; follow it |
| `teleop` | drive at `(linear, angular)`, clamped to the teleop limits (0.5 m/s, 1.2 rad/s); held until the next teleop, STOP or goal; cancels a goal |
| `stop` | `v = w = 0` at once; clears the goal |
| `planner` | choose a planner; a running goal is re-planned |
| `reset` | back to the spec's start pose, idle |
| `autonomy` | M4.3: hand the wheels back to the last autonomous goal (below) |
| `grasp` | M4.3: grasp, approach then grasp, or release, through the Stack's proximity gate (World Spec v2 only; below) |

A run is fully reproduced by **spec + seed + input log** (README §5.2).

## Determinism

- one fixed step, `spec.arena.dt` (0.1 s for COCO: Nav2's 10 Hz);
- one single-threaded loop (`Arena.step`), no clock read;
- every random number from `coco_lab.rng.Rng`: **xoshiro256\*\*** seeded
  by **SplitMix64**, integer arithmetic only, so a second implementation can
  reproduce it from its definition. Its outputs equal the authors' reference
  C, compiled with gcc 13.3, for five seeds (`coco_lab/test/rng_vectors.json`,
  from `docs/v2/data/m1/rng/xoshiro_reference.c`). Range noise draws from a
  stream split off the main one, so noise never shifts other draws.

## The per-tick state hash (`coco.arena.state.v1`)

After every step, `Arena.state_bytes()` is a canonical, quantized,
little-endian byte layout of the whole state, and the tick's hash is its
SHA-256. `Arena.chain` extends `sha256(chain || state_bytes)` every tick,
starting from `sha256(b"coco.arena.state.v1\0")`: one value per run.

| Field | Type | Quantization |
|---|---|---|
| `tick` | u64 | — |
| `x`, `y`, `theta`, `v`, `w` | 5 × int64 | `round(value × 10⁶)` (µm, µrad, µm/s, µrad/s) |
| `mode` (idle, teleop, goal), `planner` (index in bfs, dijkstra, astar, greedy, weighted_astar), `has_goal` | 3 × u8 | — |
| goal `x`, `y` (0 if none) | 2 × int64 | `round(value × 10⁶)` |
| waypoint index, waypoint count | 2 × u32 | — |
| main RNG state | 4 × u64 | — |
| noise RNG state | 4 × u64 | — |
| beam count | u32 | — |
| every range | u32 each | `round(range × 10⁴)` (0.1 mm); `0xFFFFFFFF` = no return |

`round` is Python's (half to even). 143 bytes + 4 per beam (2,063 bytes
for 480 beams). The layout is versioned by its name; any change gets a new
name.

The quantization defines a canonical form; it does not hide drift. Every
browser runs the same Pyodide WebAssembly, whose `libm` is part of the
binary, so the same inputs should give the same bits; the cross-browser
check (Chromium, Firefox, WebKit, Pyodide-in-Node, 100 sessions) is M1's
determinism criterion, measured in M1.5/M1.10. **Native CPython and
Pyodide are not claimed to agree under v1 or v2**: they link different
`libm`s, and `sin`/`cos` may differ in the last bit (measured: M5's review,
G1.6).

**State hash v3 (G1.8, ADR 0010)** is v2's snapshot under its own tag
(`coco.arena.state.v3`) with every transcendental computed by
`coco_lab.numerics` (fdlibm in pure Python on exactly-rounded IEEE
operations), so native CPython and Pyodide **do** agree bit for bit — a CI
gate (`lab_web/tools/g1/native_gate.mjs`) checks it. New runs use v3; v1 and
v2 are unchanged and replay as before.

## LiDAR fidelity, re-confirmed

Lab 2 measured Sketch's LiDAR against Gazebo's at 237 identical true
poses: 86.7 % of beams within 5 cm. Re-run with the Arena (world generated
from the spec, LiDAR from the spec), same rules:
**86.73124396264892 % within 5 cm — identical**, over the same 237 scans
and 113,760 beams, with identical beam classes (111,804 both, 12 Gazebo
only, 123 model only, 1,821 neither). **Why:** the Arena world equals the
saved map cell for cell, the LiDAR is the same 480 beams at the same mount,
and the ray-caster is Sketch's; the Arena's ranges equal Lab 2's Sketch
ranges on **every** beam (0 of 113,760 differ). Evidence:
[`docs/v2/data/m1/lidar/arena_lidar_fidelity.json`](data/m1/lidar/arena_lidar_fidelity.json)
(MODEL vs STACK; Gazebo recordings `~/coco_lab_runs/lab2/fidelity_1`,
`fidelity_s1`).

## The whole loop (M2)

M1's Arena had no localisation: its belief WAS its truth. From M2.3 two
more input kinds turn on the whole loop (`coco_lab/arena.py`):

| Input | Meaning |
|---|---|
| `kidnap` (x, y, θ) | the robot is carried; odometry and every filter are not told |
| `config` (`key=value`) | switch on or tune a subsystem: `arena.slip=on`, `arena.range_sigma=0.02`, `arena.odom_alphas=a1,a2,a3,a4`, `localise.filter=mcl\|ekf\|both\|off`, `localise.mcl.particles=500`, `localise.mcl.injection=augmented`, ... |

**Loop inputs apply first in their tick** and are committed at once; an
amendment cannot carry one (the worker holds it for the next tick). Until
the first loop input the Arena is exactly M1's: the same state, the same
hashes (M1's 100 recorded sessions still give 0 differing hashes).

From the first loop input the Arena keeps:

- **wheel odometry**: the wheels' motion each tick, through Sketch's
  odometry motion model (`sample_delta`, default alphas 0.02), on its own
  random stream split from the master at activation;
- **the wheel-slip option** (`arena.slip`, OFF by default, labelled on
  screen as a model option): in turns the body rotates `SLIP_TURN` =
  56.2 / 72.5 = 0.775 of what the wheels report — Lab 2's measured turn
  divergence of COCO's skid-steer wheel odometry on the recorded tour.
  Measured against all of Lab 2's recorded drives, it helps on one tour
  and the square and badly hurts on the other tour, so it stays off
  (`docs/v2/data/m2/m23/slip_fidelity.json`; `FIDELITY_v1.md`);
- **subsystems**, each registered in `SUBSYSTEMS` by its own Python pack
  (`coco_lab.loc_arena` registers `localise`, `coco_lab.map_arena`
  registers `map`, `coco_lab.move_arena` registers `move`); a `config` for
  a subsystem whose pack is not loaded is refused. A subsystem may also
  provide `command()` (it drives instead of M1's waypoint driver while a
  goal is followed), `discs()` (moving bodies: the LiDAR sees them and the
  robot cannot drive into them) and `world_step()` (it moves them, after
  the robot and before the scan). A subsystem asks for a goal with
  `Arena.request_goal(x, y)` (M2.6, the mission): it is committed at the
  start of the next tick, before the snapshot, like a loop input, so an
  amended tick still plans it and a learner's own input in that tick still
  wins;
- **`arena.plan_clearance=<m>`** (M2.6): plan on the map inflated by this
  much instead of the robot's radius (0.22 m, M1's), within [0.22, 1.0] m.
  The mission and the three local controllers raise it to 0.40 m: M1's
  planner keeps only the robot's radius from walls, inside the local
  window's 0.255 m inscribed band and with no margin for any localisation
  error (measured: DWA refused its first fetch leg; a 0.19 m MCL error put
  the robot against a box). Appended to the loop section of the hash
  (`clearance` + int64 micro-units) only when it differs from the radius,
  so every earlier hash is unchanged.

**Planning and driving use the BELIEF** (`Arena.belief()`: the localiser's
estimate, MCL's when both run), never the truth: a localisation error
reaches the planner (the search starts from the believed cell) and the
driver. The tick reports the belief as `pose` and the truth beside it; the
renderer draws the robot at the belief and the truth as the dashed outline.

### The loop section of the state hash (`coco.arena.loop.v1`)

Appended to the M1 layout only once the loop is on, little-endian:
`coco.arena.loop.v1\0`; odometry x, y, θ as int64 micro-units; slip u8;
range σ int64 micro-units; the four odometry alphas int64 micro-units; the
odometry stream's state (4 × u64); then for each subsystem in name order its
name (u32 length + UTF-8) and its state (u32 length + bytes). The localise
subsystem's state: filter u8; its stream (4 × u64); for MCL the particle
count u32, w_slow and w_fast (int64, ×10¹²), then x, y, θ, weight per
particle (int64 micro-units); for the EKF μ (3) and P (9) as int64
micro-units; the last update's odometry (3 × int64) and the update count u32.
The map subsystem's state: algorithm u8 and pose source u8 (indices into
`map_arena.ALGORITHMS` / `POSES`), the update count u32, its two streams
(8 × u64: FastSLAM's, the idealised landmark sensor's); the last mapping
estimate (3 × int64 micro-units); for FastSLAM x, y, θ, weight per particle
(int64 micro-units); for EKF-SLAM the whole state vector μ (int64
micro-units); for the pose graph the edge count u32. The built grid itself
is not hashed: it is a function of the hashed poses and the hashed scans.
The move subsystem's state: controller, scenario and outcome u8 (indices
into `move_arena.CONTROLLERS` / `SCENARIOS` / `OUTCOMES`), the belief
offset (3 × int64 micro-units), the cycle count u32 and the path index u64;
its stream (4 × u64); per actor x, y and distance walked (int64
micro-units), triggered u8 and ticks held u32; MPPI's warm-start control
sequence (2 × 28 int64 micro-units; nothing for DWA and RPP); the time no
valid command began (−1 if none) and the progress checker's time (int64
micro-units).
The mission subsystem's state: state u8, colour u8 (0 = none), the true
bay, the target bay and the location i8 (−1 = none / home), awaiting a plan
u8, the searched bays as a bit mask u32, the update count u32; the belief
over the bays (int64, × 10¹²); the state's start time, the world's
detection rate and the progress checker's time (int64 micro-units), the
recovery count and the leg u8; its stream (4 × u64).

### The map subsystem (M2.4)

`config` keys: `map.algorithm=occupancy|ekf_slam|fastslam|pose_graph|off`,
`map.poses=truth|odometry|belief` (whose poses an occupancy grid is built
from), `map.fastslam.particles=1..200`, `map.pose_graph.loop_closure=on|off`.
Each restarts the map from the current belief. The algorithms are Lab 3's
classes (`OccupancyGrid`, `EKFSlam`, `FastSlam`, `PoseGraph`), fed the
Arena's wheel odometry and LiDAR at Lab 3's update rule (0.1 m or 0.2 rad of
odometry); known-pose mapping is tested to give the grid Lab 3's class gives
on the same scans, and FastSLAM to give the class's estimate draw for draw.

- The grid is the arena at **0.10 m** (Lab 3's arena challenge resolution).
  The whole grid goes out as a float32 keyframe every 4th update
  (`coco.map.grid.snapshot.v1`) and after every pose-graph closure.
- **EKF-SLAM reads the IDEALISED landmark sensor** (`coco_lab.landmarks`:
  obstacle corners with known identities, no misses, no false detections;
  placed as Lab 3's arena challenge places them). COCO has none; the
  `coco.map.slam.header.v1` header says so in `sensor_label`, and the lens
  shows it.
- The pose graph emits its nodes and edges at each closure **twice**: the
  graph before optimising (`stage` `raw`, its χ²) and after (`optimised`);
  the lens keeps the last closure's before-graph, faint, until the next.
- Every 10 updates the subsystem scores itself against the truth the way
  Lab 3 scored: ATE (RMSE, aligned for SLAMs) and F1 / precision / recall
  of the map (`coco.metrics.values.v1`). The truth is used only for those
  scores and for the idealised sensor's observations (Lab 3's rule).

### The move subsystem (M2.5)

`config` keys: `move.controller=builtin|dwa|rpp|mppi`,
`move.scenario=static_room|crossing|oncoming|mislocalised|none`,
`move.belief_offset=dx,dy,dyaw`. The controllers are TEACHING
implementations written after Lab 5's Nav2 controllers
(`coco_lab/control.py`, evidence class MODEL; every simplification is in its
docstring); each cycle they see a 3 × 3 m local window at 0.05 m around the
BELIEVED pose, marked from the current scan within 2.5 m and inflated as the
mission's local costmap inflates, and the part of the path that lies in it.
FollowPath's outcomes are Nav2's: succeeded (0.25 m, then a turn to the
goal's heading), INVALID_PATH 103 (no path pose in the window), NO_VALID_CONTROL
104 (no valid command for more than 0.3 s), FAILED_TO_MAKE_PROGRESS 105
(under 0.1 m in 10 s).

- A scenario is Lab 5's, rebuilt from its definition
  (`coco_lab/move_scenarios.py`, generated from `coco_lab_ros/config/` and
  tested against it): the robot at map (0, 0, 0), handed the FROZEN path
  (not the Arena's plan), the actors at their first waypoint until the
  robot's TRUE pose crosses the trigger line, then walking once at their
  speed.
- **Actors are solid** (radius 0.15 m): the LiDAR sees them, the robot cannot
  drive into one, and an actor waits while its next step would walk into the
  robot. Lab 5's Gazebo actors had no collision body.
- `mislocalised` (and `move.belief_offset`) puts the belief a fixed offset
  from the truth when no localiser runs.
- Every cycle emits `coco.control.local.candidates.v1` (every candidate DWA
  scored; RPP's one arc; 24 of MPPI's 128 samples and its optimum; every
  third trajectory point), `coco.control.local.command.v1` and the metrics
  `n_valid`, `cmd_v`, `tracking_error`; an outcome emits `outcome.<name>`.
  Actors ride on the tick (`actors`), and a path given whole on the tick it
  was given (`path`).

The comparison with Lab 5's STACK results is `docs/v2/M2_MOVE_COMPARISON.md`.

### The mission subsystem (M2.6)

`config` keys: `mission.start=red|green|blue|yellow`, `mission.truth=bay_k`
(where the target really stands; default the frozen layout),
`mission.detect=<p>` (the camera's REAL rate, default 0.9), `mission.abort=1`.
The fetch runs **localise → choose a bay → plan → local control → detect →
grasp → return**, each step done by the pack that owns it, so a localisation
error reaches the planner (it plans from the believed cell), the controller
(it steers by the belief), the survey (the camera sees what is TRULY in
front of the robot) and the search (a miss is booked at the bay the robot
believes it searched).

- **The search is Lab 4's** (`coco_lab/regionsearch.py`; the problem in
  `coco_lab/fetch_problem.py`, generated from `build_search.arena_problem()`
  and pinned to it by a test): a uniform prior over the four bays, the robot's
  detection probability d = 0.9 **labelled ASSUMPTION** (in
  `coco.decide.search.header.v1` and on screen), Bayes on a miss, the next bay
  by the least expected metres driven over every order. Every choice emits the
  belief, the expected cost of every order of the bays left, and the action.
- **SIMPLIFIED:** the Arena is flat, so the ramp climb is not modelled; the
  robot surveys and grasps from the bay's pre-ramp pose. A bay is in view when
  the robot's TRUE position is within 0.6 m of that pose; detection is found
  with probability `mission.detect` when that bay holds the target, never a
  false positive (`coco.sensor.detect.colour.v1`).
- **The arm** (`coco_lab/arm.py`, geometry pinned to `arm_ik.py`): two
  revolute joints in the side view, two fingers and a magnet — **the magnet
  holds**; the pick is `pick_place.py`'s verified joint poses, interpolated
  (`coco.arm.state.v1`, with the elbow; additive fields 13–14).
- A leg fails as Nav2 would report it: no path, the controller's outcome,
  no progress (under 0.1 m in 10 s), 300 s. After a controller gives up
  (104/105) the robot backs up 0.30 m and re-plans, at most 3 times — after
  Nav2's BackUp recovery; SIMPLIFIED: no costmap clearing, spin or wait.
- Every 10 ticks it emits `loc_error` (the true error, which the learner can
  see and the robot cannot) and, with a localiser, `loc_sigma` (the robot's
  own uncertainty).

## Terrain, the command source and the grasp (M4.3)

M4.3 adds three things to the model. A World Spec v1 (flat) session never
meets any of them: its state bytes, and so every hash, golden trace and
share link made before M4, are unchanged (every flat golden-trace and hash
test passes unedited).

**Terrain (World Spec v2 only; ADR 0007).** The arena's ramps and platforms
(`elevation`: wedges and platforms) are `coco_lab.terrain.Terrain`, in the
map frame. Following is **kinematic**: each tick the robot moves in (x, y, θ)
exactly as on the flat, then stands on the surface. Its height is the
surface under the wheel base's centre; its pitch and roll come from the
surface under its four corners (half the wheel base, 0.09 m, front and back;
half the track left and right): pitch = atan2(h_back − h_front, 2 × 0.09),
positive nose **down**, roll = atan2(h_left − h_right, track), positive left
side **up** (REP-103). SIMPLIFIED MODEL: no suspension, no contact forces, no
slip on a slope, no tip-over. Where it can drive: `worldspec.terrain_map`
rasterises the surface and marks a cell occupied where its height steps from
a neighbour's by more than any slope here explains (`Terrain.drop_threshold`:
the steepest wedge's rise over one cell, plus 2 cm). So a ramp's slope is
free and its sides, a platform's sides and a ramp's raised end seen from
below are walls; driving into one is a **contact** (the tick's `contact`
flag), and the robot stops, as at any wall. The LiDAR sees the scan-height
silhouette (`Terrain.rects_above` at the beam's height): a horizontal beam
meets a ramp where the ramp rises above it. Measured against Gazebo's ground
truth over Lab 4's 17 recorded fetches: `docs/v2/FIDELITY_v1.md` §4.

**The command source.** Each tick reports who the wheels obeyed, by the
arbiter's priority (README §3 invariant 3): `stop` (a STOP applied this
tick) over `teleop` (a person driving) over `mission` or `planner`
(autonomy: the mission's legs and the grasp's approach, or a goal a person
set); `idle` when nothing drives. It is derived, not state: it is not in the
hash. Teleop preempts autonomy the moment it arrives, as in M1–M3 (that rule
is kept exactly: 98 of M1's 100 and 97 of M2.11's 100 committed determinism
sessions contain both a goal and a teleop, `docs/v2/data/m4/m43/
mixed_sessions.json`).
The new input `autonomy` (the 3D Arena's Tab) hands the wheels back: it
resumes the last autonomous goal, the mission's leg (`MissionArena.resume`
re-requests it if the fetch is still on a leg) or the person's own last
goal; with neither, the robot stops and waits.

**The gated grasp** (`coco_lab.grasp`; World Spec v2 only, where the targets
stand on the platforms at the frozen layout, `fetch_problem.TARGET_NOMINAL`).
The input `grasp` (the 3D Arena's E) is the Stack's proximity gate: a target
can be picked only when its axis is 0.151–0.1565 m ahead of `base_footprint`
and within 10 mm of the centreline (`coco_config.robot.approach_window`,
`GRASP_MAX_LATERAL`; copied and pinned by `test_sketch_constants.py`). With a
target already in that window the press picks; with one up to 0.6 m ahead and
within 30° of the nose it **approaches** first, as `approach_server` does:
turns to face it, creeps at 0.03 m/s (`approach_server.CREEP_SPEED`), and in
the last step proportionally (the model's 10 Hz tick would move 3 mm, more
than half the 5.5 mm window); then the gate decides, and says why when it
refuses. A teleop or a STOP cancels an approach. The pick is `coco_lab.arm`'s
kinematic script; afterwards the target rides with the robot (the magnet
holds it); a second press releases it in front of the robot. On a flat world
the press does nothing and says so (no state is created). SIMPLIFIED MODEL:
no contact, no forces, the target is assumed upright and where the gate saw
it.

### The terrain and grasp sections of the state hash

Appended after everything above, little-endian, `Q_STATE` micro-units:

- `coco.arena.grasp.v1\0`, only once a grasp input has created the grasp
  state: phase u8 (idle, approach, pick, carry, release), target u8 (0 =
  none, else 1 + the colour's index in name order), the phase's start time
  int64, the approach's creep count u32, then each target's x and y (int64,
  colours in name order: blue, green, red, yellow);
- `coco.arena.terrain.v1\0`, only on a World Spec v2 session: z, pitch and
  roll (3 × int64).

Every tick also reports (not hashed: derived from hashed state) `z`,
`pitch`, `roll`, the left and right wheel speeds (rad/s), the command source
and the contact flag; `coco.robot.state.v1` gained them as additive fields
9–15 and `coco.truth.pose.v1` gained z, roll and pitch (7–9), empty where
nothing produced them (a Stack recording that did not record height is
never given one).

### Determinism on the terrain

Measured in M4.3 over 100 recorded terrain sessions (`tools/perf/
determinism.mjs make --terrain 1`: 700 ticks each, most driving to a
platform and grasping there, among teleop, hand-backs, stops, planner
switches and random goals) on Chromium, Firefox, WebKit and Pyodide-in-Node:
`docs/v2/data/m4/m43/determinism/`.
