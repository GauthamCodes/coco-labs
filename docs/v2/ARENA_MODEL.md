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
Pyodide are not claimed to agree**: they link different `libm`s, and
`sin`/`cos` may differ in the last bit.

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
  (`coco_lab.loc_arena` registers `localise`); a `config` for a subsystem
  whose pack is not loaded is refused.

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
