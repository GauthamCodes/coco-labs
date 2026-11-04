# R1.5 Benchmarks — COCO-Bench v0 (a draft for R3)

Evidence class: MODEL (reference results) / TESTED (checks).

## The suites (`coco_lab/coco_lab/benchmarks/*.v0.json`, frozen; `tools/r1/make_suites.py --check`)

| Suite | World | Scenarios | How chosen | Families |
| --- | --- | --- | --- | --- |
| `arena-nav-50` | Proving Ground (0.05 m) | 50 | seed 5001, ≥ 3 m apart, clearance > 0.35 m, connected | planning, control, localisation |
| `depot-nav-100` | Depot (0.1 m) | 100 | seed 1001, stratified by start zone (17/17/17/17/16/16 over the six zones), ≥ 5 m apart | planning, control, localisation |
| `depot-narrow-30` | Depot | 30 | from a seeded pool of 600: 15 whose reference A* path runs ≥ 5 m inside the workshop maze (a dead-end corner: one end in it) and 15 crossing ≥ 5 m of the high-bay rack aisles with both ends outside | planning, control |
| `colour-fetch-4` | Depot with colour rods | 4 | the four rods, Fetch by colour rules 2 (committed rounds) | full task |

Each suite file holds its scenarios, its metric set per family, the text saying what it tests, its
generator and the World Spec's sha256. Each has a README with its reference results:
[`../../bench/<suite>/README.md`](../../bench/).

The narrow-passage criterion was chosen from measurement, not guessed: a probe of 300 Depot pairs found no
reference path that passes through the workshop with both ends outside (it is a dead end), and minimum
clearance along A* paths does not discriminate (paths hug the inflation edge at 0.25 m), so the suite is
defined by in-zone path length instead.

## Reference results (`tools/r1/make_references.py`, committed in `docs/v2/r1/bench/<suite>/<family>/`)

Every built-in algorithm at its default parameters (localisation: MCL 60 particles / 12 beams, EKF 12 beams),
run natively by `coco experiment run` on 8 workers. Successes (N in each cell):

| Suite · family | Runs | Results (successes / N) | Digest |
| --- | --- | --- | --- |
| arena-nav-50 · planning | 300 | every planner 50/50 | `3533c4c3e74a…` |
| arena-nav-50 · control | 200 | waypoint driver 50/50, DWA 31/50, RPP 41/50, MPPI 49/50 | `b492b3de896c…` |
| arena-nav-50 · localisation | 150 | MCL 25/50, MCL + injection 28/50, EKF 47/50 | `66263713427e…` |
| depot-nav-100 · planning | 600 | every planner 100/100 | `86876cd8e3dd…` |
| depot-nav-100 · control | 400 | waypoint driver 100/100, DWA 64/100, RPP 37/100, MPPI 83/100 | `f8fe561af979…` |
| depot-narrow-30 · planning | 180 | every planner 30/30 | `2c35d5b4847c…` |
| depot-narrow-30 · control | 120 | waypoint driver 30/30, DWA 12/30, RPP 8/30, MPPI 23/30 | `86643da7d303…` |
| colour-fetch-4 · full task | 20 | every planner 4/4 | `d954ee57d494…` |

These are the teaching implementations in the model (README §5.7; MODEL, not Nav2's code): the local
controllers fail often in the Depot's tight places, and the failures stay in the results (each with its
outcome: `failed_to_make_progress`, `no_valid_control`, `timeout`). Localisation success means reaching the
goal with the estimate within 0.5 m and 0.3 rad. Medians, IQRs and every run are in each README and
`results.csv`. Timings: the manifests' `wall_s` includes time the laptop was suspended; per-run `compute_ms`
uses a monotonic clock that does not. Counts need no device.

**Reproduction:** a random 10% of every reference re-run with the tree's code (`python -m coco_lab.experiments
verify DIR --sample 0.1`): [`verify.txt`](verify.txt).

## Gazebo + Nav2

- `colour-fetch-4`: the four rounds were recorded with Nav2 in Gazebo in G2 (STACK ghosts
  `lab_web/public/stack/ghosts/g2_colour_*.json`); the suite page links each to Play's "Race Nav2".
- The navigation suites: no Gazebo + Nav2 recording of these scenarios exists; their pages say so.

## The Benchmarks tab

Each suite: its description, a map of all its scenarios (zones shaded; start circles, goal squares), the
reference tables (N, success with Wilson 95%, outcomes, median [IQR] of three key metrics), a "re-run this in
your browser" link carrying the reference digest, and the files. Audit: [`a11y/a11y.json`](a11y/a11y.json)
(desktop and emulated phone landscape, dark and light: 0 contrast failures, 0 unfocusable controls).
