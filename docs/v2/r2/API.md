# coco_lab.api — writing your own planner, controller or localiser

`coco.algorithm.v1` ([ADR 0013](../adr/0013-algorithm-api-v1.md)). One Python file, three places to run it:

| Where | How | Evidence |
| --- | --- | --- |
| Your browser | Workbench → **Algorithm Studio** (a sandboxed worker; no install) | MODEL |
| Natively | `coco experiment run spec.json --algorithm my_planner.py` | MODEL |
| Real ROS 2 | Studio → **Export as ROS 2 package**, or `python -m coco_lab.ros2_export my_planner.py --name mine --out DIR` | STACK (Gazebo + Nav2) |

The same file gives the same numbers in the browser and natively (CI checks every starter template: 0 differences),
and runs unchanged as a ROS 2 node.

## 1. The three contracts

A file defines **exactly one** of these:

```python
def plan(costmap: Costmap, start: Pose2D, goal: Pose2D, ctx: Context) -> list[Pose2D] | None
def control(state: RobotState, scan: LaserScan, path: list[Pose2D], ctx: Context) -> Twist
def localise(odom: Odometry, scan: LaserScan, map: OccupancyGrid, ctx: Context) -> PoseWithCovariance
```

| | Called | Inputs come from (browser · ROS 2) | You return |
| --- | --- | --- | --- |
| `plan` | once per planning request (Nav2 asks again every second while driving) | the planning costmap · `/global_costmap/costmap_raw`; start and goal snapped to the centres of free cells | the poses from the start cell to the goal cell, or `None` |
| `control` | every tick (`ctx.dt` = 0.1 s) | believed pose, velocity and the goal · TF and `/odom`; the LiDAR · `/scan`; the global plan · `/plan` | a `Twist`: `linear.x` (m/s) and `angular.z` (rad/s) |
| `localise` | every tick | wheel odometry · `/odom`; the LiDAR · `/scan`; the map · `/map` | where the robot is, in the map frame, with a 6×6 covariance |

You do **not** check the goal in a controller: the runner does, exactly as Nav2's controller server does (0.25 m,
then a turn to the goal's heading within 0.25 rad). Raise `NoValidControl("why")` when nothing is safe (more than
0.3 s of it ends the run `no_valid_control`) and `InvalidPath("why")` when the path cannot be followed.
Less than 0.1 m of progress in 10 s ends it `failed_to_make_progress`.

## 2. Types (ROS 2 message shapes)

The fields and nesting are the Jazzy messages', so the code maps one to one onto a ROS 2 node.

| Type | ROS 2 message | Fields and helpers |
| --- | --- | --- |
| `Pose2D` | `geometry_msgs/Pose2D` | `x`, `y` (m, map frame), `theta` (rad) |
| `Twist` | `geometry_msgs/Twist` | `linear` (`Vector3`), `angular`; `Twist.of(v, w)` |
| `Pose`, `Point`, `Quaternion`, `Vector3` | `geometry_msgs/*` | `Pose.from_2d(x, y, th)`, `pose.to_2d()`; `yaw_of(q)`, `quaternion_from_yaw(th)` (exact round trip) |
| `PoseWithCovariance` | `geometry_msgs/PoseWithCovariance` | `pose`, `covariance` (36, row-major x y z roll pitch yaw); `PoseWithCovariance.of(x, y, th, var_x, var_y, var_th, cov_xy)` |
| `Costmap` | `nav2_msgs/Costmap` (`costmap_raw`) | `metadata` (`resolution`, `size_x`, `size_y`, `origin`), `data` (raw costs 0..255, row 0 at the origin); `cost(mx, my)`, `cost_at(x, y)`, `is_free(mx, my)`, `world_to_map(x, y)` → `(mx, my)` or `None`, `map_to_world(mx, my)` → cell centre, `width`, `height`, `resolution` |
| `OccupancyGrid` | `nav_msgs/OccupancyGrid` | `info` (`resolution`, `width`, `height`, `origin`), `data` (-1 unknown, 0 free, 100 occupied); `value(mx, my)`, `world_to_map`, `map_to_world` |
| `LaserScan` | `sensor_msgs/LaserScan` | `angle_min`, `angle_max`, `angle_increment`, `range_min`, `range_max`, `ranges` (inf: no return); `angles()`. Frame `lidar_link`: the LiDAR sits at `ctx.robot.lidar_mount` |
| `Odometry` | `nav_msgs/Odometry` | `pose.pose` (odom frame; it drifts), `twist.twist` |
| `RobotState` | (TF + `/odom`) | `pose` (`Pose2D`, believed), `twist`, `goal` (`Pose2D`; `theta` nan when none), `stamp` |

Costs (`nav2_costmap_2d`): `FREE_SPACE` 0, 1..252 the inflation's falling cost, `INSCRIBED_INFLATED_OBSTACLE` 253
(the robot's centre there touches an obstacle), `LETHAL_OBSTACLE` 254, `NO_INFORMATION` 255.

**Why `nav2_msgs/Costmap`, not the `OccupancyGrid` on `/global_costmap/costmap`?** That form scales costs to 0–100;
`costmap_raw` carries the raw costs, exactly what the browser has (ADR 0013).

## 3. `ctx`

| | |
| --- | --- |
| `ctx.rng` | the run's seeded generator: `random()`, `uniform(a, b)`, `gauss(mu, sigma)`, `randint(a, b)`, `randrange(n)`, `choice(seq)`, `shuffle(list)`, `sample(seq, k)`. **The only randomness**; `import random` is the same generator |
| `ctx.robot` | COCO: `radius` 0.22 m, `max_linear` 0.3 m/s, `max_angular` 1.0 rad/s, `max_linear_accel` 2.0, `max_angular_accel` 4.0, `wheel_radius`, `wheel_separation`, `lidar_mount` |
| `ctx.params` | your parameters: `user.<name>` in an experiment (sweepable), `params:` in a leaderboard `meta.yaml` |
| `ctx.config` | the family's settings (planning: `inflation_radius`, `cost_scaling_factor`, `robot_radius`, `cost_weight`, `connectivity`) |
| `ctx.memory` | a dict kept across the calls of one run (a controller's or localiser's state); a planner gets a fresh one per run |
| `ctx.time`, `ctx.dt` | sim time (s) and the tick (s) |
| `ctx.step(n=1)`, `ctx.budget` | count work against a deterministic step budget per call (planner 20,000,000; controller 200,000; localiser 2,000,000); past it, `BudgetExceeded` |
| `ctx.initial_pose` | where a localiser starts (`/initialpose` in ROS 2) |
| `ctx.cost(x, y)`, `ctx.world_to_map`, `ctx.map_to_world` | the planner's costmap helpers |
| `ctx.emit(kind, **data)` | your thinking, drawn like the built-ins' (§5) |

## 4. Validation (never silent)

- **Paths:** a list (≤ 200,000) of finite poses on the map; the first in the start cell, the last in the goal cell
  (else `invalid_output`); no cell the path crosses — every cell the straight segment between two consecutive poses
  touches — may cost 253 or more (else `collision`). Poses are measured at the centres of their cells: length
  `Σ hypot(Δrow, Δcol) × resolution`; cost along an 8-connected path; clearance over every crossed cell.
- **Twists:** must be a finite `Twist`; `linear.y/z` and `angular.x/y` are set to 0 and `|linear.x|` ≤ 0.3,
  `|angular.z|` ≤ 1.0 are enforced by **clamping, and every clamp is logged** in the Validation tab.
- **Covariances:** 36 finite values, symmetric, positive semi-definite; a unit quaternion.
- An exception ends the run `error` with the traceback mapped to your lines; the console keeps 64 KB of `print`.

## 5. Thinking: `ctx.emit` event kinds

| Kind | Fields | Drawn as |
| --- | --- | --- |
| `expand` | `x`, `y` | an expanded cell (Compare's search layer); counted as **expansions** |
| `push` | `x`, `y` | a cell joining the open list; counted as **pushes** |
| `frontier` | `x`, `y` | the frontier |
| `path` | `points` | a path you are considering |
| `candidate` | `points` [[x, y], ...], `cost`, `valid` | a trajectory a controller considered (the Move lens's fan) |
| `lookahead` | `x`, `y` | the point a controller chases |
| `particles` | `x`, `y`, `theta`, `weight` (lists) | a localiser's particle cloud |
| `estimate` | `x`, `y`, `theta` | an estimate |
| `marker` | `x`, `y`, `label` | a labelled point |
| `note` | `text` | a line in the console |

A planner's events all enter its run's hash chain; a controller's or localiser's first 20,000 per call are kept for
drawing (the rest are counted). Expansions are self-reported: the leaderboard shows them, labelled, and ranks by them last.

## 6. What a file may use (the guard, ADR 0012)

Imports: `math` (the functions that give the same bits in every runtime; `tanh`, `asin`, `log2`, `log10`, `degrees`,
`radians` are composed from them; others such as `sinh` are absent), `random` (the seeded generator), `heapq`,
`collections`, `itertools`, `functools`, `bisect`, `typing`, `dataclasses`, `coco_lab.api`. Not `js`, `pyodide`,
`os`, `sys`, `time`, `numpy` (not shipped). No attribute names starting with `_`; no `open`, `eval`, `exec`, `id`.
`x ** y` is computed exactly (the same bits everywhere). **Determinism:** every run is run twice and the hash chains
compared; set iteration over objects without a `__hash__` follows memory addresses and is not deterministic.

## 7. Worked examples

**A planner** (the A* starter, condensed):

```python
import heapq, math
from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D

def plan(costmap, start, goal, ctx):
    s, g = costmap.world_to_map(start.x, start.y), costmap.world_to_map(goal.x, goal.y)
    h = lambda c: math.hypot(c[0] - g[0], c[1] - g[1])
    heap, best, parent = [(h(s), 0.0, s)], {s: 0.0}, {s: None}
    while heap:
        _, gc, c = heapq.heappop(heap)
        ctx.emit('expand', x=costmap.map_to_world(*c)[0], y=costmap.map_to_world(*c)[1])
        if c == g:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dy)
            if costmap.cost(*n) < INSCRIBED_INFLATED_OBSTACLE and gc + 1 < best.get(n, math.inf):
                best[n], parent[n] = gc + 1, c
                heapq.heappush(heap, (gc + 1 + h(n), gc + 1, n))
    if g not in parent:
        return None
    cells = [g]
    while parent[cells[-1]] is not None:
        cells.append(parent[cells[-1]])
    return [Pose2D(*costmap.map_to_world(*c)) for c in reversed(cells)]
```

**A controller** (go to the goal, turning first):

```python
import math
from coco_lab.api import Twist

def control(state, scan, path, ctx):
    p, g = state.pose, path[-1]
    err = math.atan2(math.sin(math.atan2(g.y - p.y, g.x - p.x) - p.theta),
                     math.cos(math.atan2(g.y - p.y, g.x - p.x) - p.theta))
    return Twist.of(0.2 if abs(err) < 0.5 else 0.0, 1.5 * err)
```

**A localiser** (dead reckoning from `ctx.initial_pose`): see `coco_lab/coco_lab/templates/localiser_empty.py`.

**Experiments and the leaderboard:** in the Studio, "Benchmark it" runs your file and the built-ins on a COCO-Bench
suite with R1's statistics. Natively:

```bash
coco experiment run spec.json --algorithm my_planner.py --out results/   # adds it as "user"
python tools/r2/leaderboard.py claim leaderboard/submissions/depot-nav-100/my_planner
```

and [leaderboard/CONTRIBUTING.md](../../../leaderboard/CONTRIBUTING.md) for submitting.

**ROS 2:** the exported `coco_user_<name>` package's README says how to build and launch it in COCO's Nav2 (Gazebo
Harmonic, ROS 2 Jazzy). A planner serves `ComputePathToPose`, a controller `FollowPath` (its commands go through
COCO's `cmd_vel_arbiter`), a localiser replaces AMCL.

## 8. Templates

`coco_lab/coco_lab/templates/`: `planner_astar`, `planner_greedy`, `planner_empty`, `controller_pure_pursuit`,
`controller_empty`, `localiser_particle_filter`, `localiser_empty`, and two teaching starters for the Learn course:
`teach_heuristic` (A* with its heuristic left to you) and `teach_tune_dwa` (DWA with its critic weights exposed).
