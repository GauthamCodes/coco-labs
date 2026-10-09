# M2.5 — Lab 5's scenarios: the model controllers against the stack

Evidence: `docs/v2/data/m2/m25/move_comparison.json` (made by
`move_comparison.py` beside it, 2026-10-09, CPython 3.12.3) for the
**MODEL** column; `docs/data/lab5/results.json` (54 runs of the full ROS 2
stack in Gazebo, 2026-10-07; `docs/labs/LAB5_MOVE.md`) for the **STACK**
column, read, not re-run. Nothing in the model was fitted to the stack.

## What is compared, and what is not the same

| | STACK (Lab 5) | MODEL (the Arena, M2.5) |
|---|---|---|
| controllers | Nav2 1.3.11's DWB, MPPI, RPP | teaching implementations written after them (`coco_lab/control.py`): DWA (after DWB), MPPI, RPP — not Nav2's code |
| configuration | the mission's DWB; MPPI and RPP from the Nav2 docs' examples (`nav2_move_overlay.yaml`) | the same values where the model has the knob; **DWA 11 × 21 samples (DWB 20 × 40 = 819), MPPI 128 samples (Lab 5: 2,000)**, fewer critics — every simplification listed in `control.py`'s docstring |
| path | the frozen SmacPlanner2D path, sent once | **the same files**, copied into `coco_lab/move_scenarios.py` (a test pins the copy to them) |
| start, goal, triggers, actor waypoints and speed | `lab5_scenarios.json` | the same file |
| local costmap | 3 × 3 m rolling, obstacle + voxel layers, inflation 0.5 m, scaling 65, robot radius 0.25 | 3 × 3 m at 0.05 m around the believed pose, marked from the current scan within 2.5 m, the same inflation rule — **rebuilt from each scan** (Nav2 keeps marks) |
| robot | Gazebo physics; DWB's limits 0.3 m/s, 1.0 rad/s, accelerations 3.0 / −2.5 m/s², 3.2 rad/s² | the Arena's unicycle at 0.3 m/s, 1.0 rad/s, **accelerations 2.0 m/s², 4.0 rad/s²** (the Arena's own, M1); the velocity smoother and the collision monitor are not modelled |
| **actors** | **visual only, no collision body**: the LiDAR sees them, nothing collides, they never stop | **solid**: the LiDAR sees them, the robot cannot drive into one, and an actor waits while its next step would walk into the robot |
| localisation | AMCL | none: belief = truth, except run 15's injected offset |
| runs | 5 per controller and scenario (3 for run 15), fresh simulator each | seeds 1–5; DWA and RPP are deterministic here (no sensor noise was configured), so their 5 seeds are identical; MPPI's noise follows the seed |
| metrics | `coco_lab.movemetrics` | **the same code**, Lab 5's footprint rectangle and obstacle list, over the window from the first command to the outcome |

## Outcomes

| scenario | DWB (STACK) | DWA (MODEL) | RPP (STACK) | RPP (MODEL) | MPPI (STACK) | MPPI (MODEL) |
|---|---|---|---|---|---|---|
| hairpin (`static_room`) | 5 × failed, 105 | 5 × failed, 105 | 5 succeeded | 5 succeeded | 5 succeeded | 5 succeeded |
| crossing | 5 succeeded | 5 succeeded | 5 succeeded | 5 succeeded | 5 succeeded | 5 succeeded |
| head-on (`oncoming`) | 5 succeeded, **contact 5/5** | **5 × failed, 104** | 5 × failed, 104 | 5 × failed, 104 | 5 succeeded, **contact 5/5** | **5 × failed, 104** |
| run 15 (`mislocalised`) | 3 × failed, 103 | 5 × failed, 103 | 3 × failed, 103 | 5 × failed, 103 | 3 × failed, 103 | 5 × failed, 103 |

Codes are Nav2's FollowPath results: 103 INVALID_PATH, 104 NO_VALID_CONTROL,
105 FAILED_TO_MAKE_PROGRESS.

**Agree: hairpin, crossing, run 15 — 9 of 9 controller-scenario cells,
counting the outcome and the code.** The hairpin is the one the stack
found surprising: DWB never got round the wall end (0 of 5, code 105) while
RPP and MPPI did. The model's DWA fails the same way with the same code.
That agreement is a measured coincidence of outcome, **not a demonstration
that the mechanism is the same**: the model's DWA has its own samples and
critics, and why it stalls before the turn has not been examined.

**Differ: head-on, for DWB/DWA and MPPI.** In Gazebo the person walked
*through* the robot — Lab 5 measured a contact (clearance 0) in all 10 of
DWB's and MPPI's runs, and they "succeeded" because the actor was a ghost.
In the Arena the person is solid, and the model's controllers stop in
front of them. DWA drove until the person was held against it (the actor
waited 4 ticks in every run, the robot at y −4.47): the robot's centre
then lies inside the person's inscribed band, every trajectory is refused,
and after 0.3 s FollowPath fails with 104. MPPI stopped earlier (y −3.39
to −3.41; the actor was held in 1 of 5 runs): every sample collided while
the person was still approaching. RPP fails in both worlds with the same
code: its collision check refuses the arc while the person is ahead.
Nobody swerved in either world: Lab 5's robots stayed within 0.261 m of
the path's line (`max_lateral_m`), the model's ended within 0.035 m of it.
**The difference is the actor model, by construction; the model does not
have to match here and does not.**

## Run 15 in the model (MODEL; STACK beside it)

`mislocalised`: the robot believes it is 3.4 m north of the truth (Lab 5's
operator `/initialpose`, here `move.belief_offset`), and is handed the
apron path. In the model, as in the stack, the whole path lies outside the
3 × 3 m local window around the BELIEVED pose, so the path is pruned to
nothing and every controller fails in its **first** cycle with
INVALID_PATH, having scored **0 candidates** — Lab 5's DWB likewise listed
0 of 0 candidates, "not 0 of 819". 15 of 15 model runs; **STACK: 9 of 9**
(3 per controller, code 103, within 4–12 ms of sim time). The model draws
it: the window around the believed pose, the given path 3.4 m away, the
robot at the truth (`docs/v2/data/m2/m25/browser/move_run15_explain.png`).
Run 15 itself (the v1 wedge world's corridor, "0 of 819") is not re-run
here, in the model or the stack.

## Metrics (median [min–max]; one value where all runs agree)

| scenario, controller | tracking mean (m) STACK / MODEL | time when succeeded (s) STACK / MODEL | RMS dv/dt (m/s²) STACK / MODEL | RMS dω/dt (rad/s²) STACK / MODEL | min clearance (m) STACK / MODEL |
|---|---|---|---|---|---|
| hairpin, DWB / DWA | 0.121 [0.089–0.141] / 0.043 | — / — | 0.255 [0.225–0.329] / 0.191 | 1.014 [0.738–1.755] / 0.423 | 0.402 [0.306–0.470] / 0.292 |
| hairpin, RPP | 0.097 [0.092–0.104] / 0.027 | 51.2 [51.0–51.4] / 46.1 | 0.137 [0.127–0.169] / 0.121 | 0.258 [0.236–0.277] / 0.304 | 0.322 [0.316–0.340] / 0.230 |
| hairpin, MPPI | 0.143 [0.135–0.152] / 0.021 [0.020–0.023] | 51.8 [51.5–52.8] / 86.2 [85.9–86.8] | 0.051 [0.046–4.865] / 0.215 [0.211–0.215] | 0.244 [0.231–1.345] / 0.561 [0.544–0.608] | 0.262 [0.236–0.289] / 0.277 [0.273–0.280] |
| crossing, DWB / DWA | 0.049 [0.047–0.070] / 0.037 | 26.3 [26.1–26.5] / 26.2 | 0.264 [0.219–0.272] / 0.174 | 0.900 [0.645–0.965] / 0.397 | 0.355 [0.340–0.361] / 0.316 |
| crossing, RPP | 0.052 [0.046–0.070] / 0.020 | 28.7 [28.5–28.9] / 26.6 | 0.327 [0.186–0.376] / 0.402 | 0.315 [0.288–0.375] / 0.386 | 0.345 [0.333–0.349] / 0.290 |
| crossing, MPPI | 0.069 [0.059–0.075] / 0.029 [0.028–0.030] | 29.5 [29.4–29.9] / 48.5 [48.4–48.9] | 0.145 [0.117–5.976] / 0.220 [0.194–0.236] | 0.280 [0.244–0.424] / 0.564 [0.556–0.658] | 0.457 [0.442–0.460] / 0.465 [0.452–0.468] |
| head-on, DWB / DWA | 0.045 [0.041–0.062] / 0.051 | 28.3 [28.1–28.6] / — | 0.259 [0.240–0.301] / 0.202 | 0.595 [0.558–0.677] / 0.520 | **0.000** (contact) / 0.082 |
| head-on, RPP | 0.058 [0.036–0.069] / 0.032 | — / — | 0.294 [0.289–0.330] / 0.305 | 0.244 [0.236–0.271] / 0.489 | 0.218 [0.209–0.242] / 0.256 |
| head-on, MPPI | 0.074 [0.066–0.094] / 0.032 [0.031–0.034] | 32.0 [31.9–32.5] / — | 0.133 [0.125–0.143] / 0.230 [0.193–0.281] | 0.246 [0.210–0.332] / 0.681 [0.608–1.070] | **0.000** (contact) / 0.126 [0.087–0.155] |

What the numbers say, without explaining more than was examined:

- **The model tracks the path more tightly** in every succeeded cell
  (0.020–0.043 m against 0.049–0.143 m). The model has no wheel slip, no
  localisation error and no smoother between the controller and the
  wheels; which of these accounts for the gap is **not attributed**.
- **The model's MPPI is much slower**: 86 s against 52 s on the hairpin,
  48.5 against 29.5 s on the crossing. It samples 128 sequences, not
  2,000, and omits the gamma term; the cause is **not attributed**.
- **Minimum clearances are smaller in the model** on the hairpin and the
  crossing for DWA and RPP (0.23–0.32 m against 0.32–0.40 m); the model's
  robot body (a 0.22 m circle in the Arena, scored with Lab 5's
  rectangle) and its local window differ, so this is a model gap, not a
  finding about the controllers.
- Smoothness differs in both directions and is not interpreted here.

## Reproduce

```bash
python3 docs/v2/data/m2/m25/move_comparison.py --out docs/v2/data/m2/m25/move_comparison.json
```
