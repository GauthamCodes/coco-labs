# ADR 0013 — The algorithm API, `coco.algorithm.v1`

Date: 2026-11-04. Evidence class MODEL. Scope R2 · Bring Your Own Algorithm (R2.1).

## Problem

COCO Lab compared only its own algorithms. R2 lets anyone write a planner, controller or
localiser in Python and run it in the browser, natively, on the leaderboard verifier and as
a real ROS 2 node — one file, unchanged, in all four places — measured exactly as the
built-ins are.

## Decision

**Three functions** (module `coco_lab.api`, version `API_VERSION = 1`, schema
`coco.algorithm.v1`); a file defines exactly one:

```python
def plan(costmap: Costmap, start: Pose2D, goal: Pose2D, ctx: Context) -> list[Pose2D] | None
def control(state: RobotState, scan: LaserScan, path: list[Pose2D], ctx: Context) -> Twist
def localise(odom: Odometry, scan: LaserScan, map: OccupancyGrid, ctx: Context) -> PoseWithCovariance
```

**Types are ROS 2 message shapes** (fields and nesting of the Jazzy messages, plain Python,
no ROS import — invariant 1): `Time`, `Header`, `Point`, `Vector3`, `Quaternion`, `Pose`,
`Pose2D`, `Twist`, `PoseWithCovariance`, `TwistWithCovariance`, `MapMetaData`,
`OccupancyGrid`, `CostmapMetaData`, `Costmap`, `LaserScan`, `Odometry`. `RobotState` (pose,
twist, goal, stamp) is what Nav2's controller server knows from TF and `/odom`; `Robot` is
COCO's geometry and limits from its World Spec (radius 0.22 m, 0.3 m/s, 1.0 rad/s, 2.0 m/s²,
4.0 rad/s²: coco_config's and Nav2's numbers, pinned by existing tests).

- **The planner's costmap is `nav2_msgs/Costmap`** (Nav2's `/global_costmap/costmap_raw`:
  raw costs 0–255, 253 inscribed, 254 lethal, 255 unknown), not the `OccupancyGrid` form on
  `/global_costmap/costmap`. That form scales costs to 0–100, so the browser and the ROS node
  would see different numbers; `costmap_raw` is published by every Nav2 costmap and carries
  exactly what the browser has. *Deviation from the R2 prompt's wording, made for parity.*
- Grids are ROS-ordered: row `my = 0` is at the origin (the model's maps are top-down; the
  runner flips them, the wrappers flip back). Helpers: `world_to_map`, `map_to_world`,
  `cost`, `cost_at`, `is_free`, `in_bounds`, `index`; `yaw_of`, `quaternion_from_yaw` (a
  quaternion made from a yaw gives back exactly that yaw).

**`ctx` (`Context`)**: `rng` (the run's seeded xoshiro256** — the only randomness;
`import random` is a shim over it), `robot`, `params` (`user.<name>` in an experiment,
sweepable), `config` (the family's own settings: inflation, connectivity, ...), `memory`
(a dict kept across one run's calls; a fresh module per run, so nothing crosses runs),
`time` and `dt` (sim time), `budget` and `step()` (a deterministic step budget per call:
20,000,000 planner / 200,000 controller / 2,000,000 localiser; `BudgetExceeded`),
`initial_pose` (a localiser's `/initialpose`), and `emit(kind, **data)`.

**Thinking events** (`EVENT_KINDS`): `expand`, `push`, `frontier`, `path` (planners: drawn by
Compare's search layer); `candidate`, `lookahead` (controllers: the Move lens's trajectory
fan); `particles`, `estimate` (localisers: the Localise lens's cloud); `marker`, `note` (any).
Positions are map-frame metres. A planner's events all enter its run chain; a controller's or
localiser's are kept (20,000 per call) for drawing and the excess counted.

**Validation (never silent):**

| Output | Rule | On failure |
| --- | --- | --- |
| path | a list (≤ 200,000) of finite poses on the map, first in the start cell, last in the goal cell | `invalid_output` (contract error) |
| path | no cell it crosses (supercover between non-adjacent poses) has cost ≥ 253 | `collision` |
| `None` | no path | `no_path` |
| Twist | a Twist with finite fields | run ends `error` |
| Twist | `linear.y/z`, `angular.x/y` set to 0; `|linear.x|` ≤ 0.3, `|angular.z|` ≤ 1.0 | clamped, every clamp logged in the report |
| `NoValidControl` / `InvalidPath` raised | Nav2's controller exceptions | the FollowPath outcomes `no_valid_control` / `invalid_path` by the native rules |
| PoseWithCovariance | finite, unit quaternion (±1e-6), 36 values, symmetric (1e-9 relative), positive semi-definite (LDLᵀ with tolerance) | run ends `error` |
| any exception, `BudgetExceeded` | traceback mapped to the file's lines | `error` (planner: `budget_exceeded`) |

**Measured identically.** A path is measured at the centres of the cells its poses fall in:
length `Σ hypot(Δrow, Δcol) × resolution` added in order, cost the grid's edge costs along
an 8-connected path (none for an any-angle path), clearance over every cell the path crosses,
heading change, snap distances — the planning family's arithmetic. Control and localisation
run inside the Arena (`move.controller=user`, `localise.filter=user`): the goal checker,
progress checker, FollowPath outcomes, driver and error sampling are the native families'
own. `coco_lab.api_builtins` wraps the reference algorithms behind the same three signatures
(seeing only what user code sees) and `coco_lab/test/test_api_equivalence.py` proves they
reproduce the native results: status, path, expansions and every metric bit for bit for BFS,
Dijkstra, A*, greedy, weighted A*, DWA, RPP, MPPI, MCL, MCL + injection and EKF.

*D\* Lite is the exception, recorded as found:* its path, status and expansions are identical,
but its native adapter (`compare_planning.run_planner`, M5) sums the path length and cost with
Python's built-in `sum()`, which since Python 3.12 is compensated (Neumaier), while
`coco_lab.search` and the API add in sequence. Through the API its `path_length_m` and
`path_cost` differ from the native values by ≤ 3 × 10⁻¹⁵ relative. No native result, hash or
golden changes; one measurement cannot reproduce both conventions. Open question for Gautham
(R2_STATUS).

**Not wrapped:** the waypoint driver (`builtin`) is the Arena's own M1 driving loop, not a
controller function.

**Experiments** (`coco.experiment.v1`, ADR 0011, additive): an algorithm entry
`{"name": "user", "api": 1, "code_sha256": "<64 hex>", "id", "label", "params"}` names the
file by the sha256 of its UTF-8 bytes; the source travels beside the spec (`--algorithm`,
a link, `algorithms/<id>.py` in an export). Only a user run's descriptor carries `api` and
`code_sha256`, so every built-in descriptor, chain and experiment id is unchanged. New
planning statuses: `collision`, `invalid_output`, `budget_exceeded`. A full-task experiment
stays built-in only (a user planner inside the Arena's own planning loop is later work).

**Run chain** for a user planning run: `sha256(tag ‖ canonical(descriptor) ‖ every
emitted event as canonical([kind, data]) ‖ the path's cells ‖ the counts)`; for an Arena run,
every tick's state hash (v3) as for the built-ins. The engine of `move.controller=user` holds
plain data only; the algorithm, its `ctx` and memory live outside the Arena's state, so the
v2/v3 snapshot never meets user objects. Each user run is run twice; the record's
`deterministic` says whether the chains agree (ADR 0012).

## Consequences

- One file runs unchanged in the browser, natively, in CI and in ROS 2 (the generated
  package converts the real messages into these types).
- Adding a field to a type, an event kind or a validation rule is additive within
  `coco.algorithm.v1`; changing a meaning needs `API_VERSION = 2`, and older specs keep
  `api: 1`.
