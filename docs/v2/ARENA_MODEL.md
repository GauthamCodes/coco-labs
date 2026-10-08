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
