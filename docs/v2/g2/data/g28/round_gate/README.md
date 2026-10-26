# G2.8 — the per-round Gazebo gate (owner, 2026-10-25): 5 of 5 for every round

**STACK** (the full ROS 2 stack in Gazebo Harmonic, headless; never hardware). Owner's rule: every
Fetch Rush phone round and every Fetch by colour round succeeds 5 of 5 times in Gazebo + Nav2, with
a real ROS 2 ghost per passing round; this includes the four-rod level's first Gazebo run.

**How:** `tools/g2/round_gate.sh` (a fresh headless simulator per run, `tools/m6/m6f8_run.sh
--initial-pose` as G2.6, never `--fast`, one simulator at a time: before each run it waits until no
simulator or launch has been up for 60 s). Goals from `tools/m6/m6f8_goals.py` (`ghost --rules 5`
for the four distinct phone rounds, seeds 1, 2, 3, 6; `colour --colour <c>` for the four rods);
driving legs only, no grasp; Gazebo's actors parked. Per-run legs, generated-file and bag checksums,
machine state: the JSON files here (`tools/g2/round_gate_summary.py`); raw runs in
`~/coco_lab_runs/g2/` (outside git). Laptop: balanced, AC, RTX 4050; every run here at **RTF
0.30–0.55** (73 runs) (G2.6's runs: 0.80; CPU at 91 °C during the gate and the owner's browsers busy; Nav2's
timers are in sim time).

## Result: derivation 4 — 8 rounds, 5 of 5 each

**40 of 40 runs, 0 void** (`tools/g2/round_gate.sh … 5`, 2026-10-26, derivation 4 at c1afe72; 160 of 160 legs SUCCEEDED).
Derivation 2 is the baseline; the colour rounds and the loading-dock round passed it too, but a
params change must be measured on every round, so all eight were run again on derivation 4.

| Round | Derivation 2 (G2.6's params) | Derivation 3 (+ rotation shim) | **Derivation 4 (Regulated Pure Pursuit)** |
|---|---|---|---|
| Fetch by colour, red | 5 / 5 | — | **5 / 5** |
| Fetch by colour, green | 5 / 5 | — | **5 / 5** |
| Fetch by colour, blue | 5 / 5 | — | **5 / 5** |
| Fetch by colour, yellow | 5 / 5 (+ 1 smoke run) | — | **5 / 5** |
| Fetch Rush phone, loading dock (seed 2; 4, 5 share it) | 5 / 5 | — | **5 / 5** |
| Fetch Rush phone, workshop (seed 6) | **1 / 5** | 1 / 2 (stopped) | **5 / 5** |
| Fetch Rush phone, workshop (seed 1) | not run (stopped for the A/B) | — | **5 / 5** |
| Fetch Rush phone, workshop (seed 3) | not run | — | **5 / 5** |

Tables per run: [`derivation4.md`](derivation4.md) ([`derivation4.json`](derivation4.json)),
[`derivation2_baseline.md`](derivation2_baseline.md), [`derivation3_seed6.md`](derivation3_seed6.md),
[`smoke_colour_yellow.md`](smoke_colour_yellow.md). Generated files: derivation 3 and 4 checksums for
both levels here (`*_outputs_d3.json`, `*_outputs_d4.json`); derivation 2: `../../g26/` and
`../../fetch_colour/coco_depot_colours_v1_outputs_d2_gate.json` (the colours level compiled at the
gate's resolutions; its first record was at the default 0.1 m map). Five runs per round are not a rate.

## Why derivation 2 failed the workshop rounds (measured, `diag/`)

All four seed-6 failures were in the workshop maze, entering or leaving `obj_maze_2`'s pre-grasp
pose: Nav2 aborted with 104 PATIENCE_EXCEEDED or 105 FAILED_TO_MAKE_PROGRESS. From run 2's bag:

- the global plan out of the maze is clear: >= 0.615 m from every mapped wall in its first 4 m
  (`diag/d2_seed6_run2_leg2_plan_clearance.txt`);
- the close LiDAR returns are a **mapped** wall (y ≈ 2.07, map distance 0.00): nothing unmapped
  (`…close_returns.txt`);
- the wheels follow their commands (truth yaw rate = wheel command; `…turn_check.txt`);
- **DWB itself commanded ~0** — v 0, w ~±0.03 rad/s — for ~40 s at a time; the collision monitor's
  PolygonSlow (0.3) shrank that further; only Nav2's recovery spins moved the robot
  (`…commands.txt`, `…trace.txt`).

That is the degeneracy C2-NAV.21 measured on the robot stack: at a sharp corner every forward arc
leaves the path line while standing still costs no more. G2.6's single runs of the same leg already
took 159–178 s.

**Derivation 3** (Nav2's RotationShimController around the same DWB) turned the robot toward the
path first; the maze exit improved (70.6 s), but at the maze corner the robot already faced the path
and DWB still stood still for ~120 s (`diag/d3_seed6_run1_leg1_*.txt`); 1 of 2, stopped.

**Derivation 4** replaces DWB with Nav2's Regulated Pure Pursuit at DWB's limits (0.3 m/s,
0.8 rad/s rotate-to-heading, 3.2 rad/s², collision checking on, no reversing, cost-regulated slowing
off). It steers to a point on the global path (which keeps >= 0.6 m from the walls there) and turns
in place first when the path turns sharply. Seed 6's maze entry: 39.3–39.8 s in all five runs
(derivation 2: 57–189 s, two of the five aborted). Only `controller_server.FollowPath` differs from derivation 2;
map and world are byte-identical; the Stack's own `gazebo_models/config/nav2_params.yaml` is
unchanged (generated files only, as G2.6).

## What derivation 4 costs (measured)

Legs end farther from the goal by ground truth: **median 0.34–0.37 m (max 0.456 m)** against
derivation 2's 0.20–0.27 m (max 0.375 m), same rounds. RPP stops once Nav2's goal checker is met
(`xy_goal_tolerance` 0.25 m, judged on AMCL's pose; AMCL's own error, median 0.12–0.17 m, adds to
it); DWB carried on to its own 0.05 m. For these driving-only legs and Race Nav2's ghosts that is
within the gate; **a grasp needs the pre-grasp pose closer** (the robot's mission tolerances are
not tested here). Run time: colours about equal; loading dock 194 s against 163 s per run; workshop
seed 6 196 s against 336 s (derivation 2's successful legs).

## Ghosts (one per passing round)

Run 1 of each round on derivation 4, converted by `tools/g2/make_ghost.py` into
`lab_web/public/stack/ghosts/` and indexed by `tools/g2/ghost_index.py` (rules-5 phone seeds take
their own recording first, then G2.6's rules-4 recording of the same round; the four colour
recordings replace the first ones made from derivation-2 runs, 33c02d9). Every leg succeeded.

| Round | File | Driving (sim) | sha256 | Bytes |
|---|---|---|---|---|
| Fetch by colour, blue | `g2_colour_blue.json` | 36.58 s | `23a0d7e50e70…` | 11,859 |
| Fetch by colour, green | `g2_colour_green.json` | 40.54 s | `f574bcd45c3d…` | 12,863 |
| Fetch by colour, red | `g2_colour_red.json` | 43.8 s | `c8f159c93ab7…` | 13,845 |
| Fetch by colour, yellow | `g2_colour_yellow.json` | 38.53 s | `80bdc5390e33…` | 12,345 |
| Fetch Rush phone, seed 1 | `r5_phone_seed1.json` | 186.74 s | `1d5ad8bde8a1…` | 53,899 |
| Fetch Rush phone, seed 2 | `r5_phone_seed2.json` | 169.49 s | `8565f08f67b0…` | 49,128 |
| Fetch Rush phone, seed 3 | `r5_phone_seed3.json` | 171.74 s | `94578ebddf9d…` | 49,615 |
| Fetch Rush phone, seed 6 | `r5_phone_seed6.json` | 195.2 s | `aa744080cb77…` | 56,338 |

Race Nav2 now shows Nav2 driving the workshop rounds in 172–195 s (G2.6's rules-4 recordings:
347–412 s) and the loading dock in 169 s (166 s).
