# G2.6 — why Gazebo + Nav2 failed on the Depot (Dock 1) and AMCL drifted

**STACK evidence, measured offline** from M6F.8's recorded runs (`~/coco_lab_runs/m6/m6f8_ghost_{1,2}`,
read only) with `tools/g2/diagnose_m6f8.py` and Nav2's own AMCL re-run on the recordings
(`tools/g2/amcl_replay.py`: `nav2_amcl` + `nav2_map_server`, the recorded `/scan`, wheel-odometry TF and
`/initialpose`; the recorded AMCL's `map → odom` dropped). Every number below is in the JSON files
beside this one. Laptop, ROS 2 Jazzy, no simulator running.

## The failure (M6F.8, recorded)

Leg 2 of the phone round (to Dock 1, (38.5, 1.3)) aborted with **205 START_OCCUPIED** at truth
(40.74, 5.48) / (41.50, 5.20), between `pallet_stage_3` and `pallet_stage_4` (a 0.8 m gap; north faces at
y = 5.0). AMCL was then 0.40 m / 0.35 m from the truth, to the south-west — its believed pose ~0.2 m
from the pallet face, inside the global costmap's inscribed radius (0.206 m).

## Hypotheses (the G2 prompt's list), each measured

| Hypothesis | Measurement | Verdict |
| --- | --- | --- |
| Map resolution or origin mismatch | The scan at the truth pose fits the map: 88–98 % of in-range beam ends within 0.1 m of an occupied cell; the best-fitting map offset, searched ±0.6 m, is (0.0, −0.05) m — one 5 cm cell (the rasteriser's half-cell growth) ([`diag_m6f8_ghost_1.json`](diag_m6f8_ghost_1.json)) | **not the cause** |
| The generated SDF's collision geometry | `pallet_stage_3/4`: boxes 1.2 × 1.0 × 1.4 m at (40.6 / 42.6, 4.5) — the World Spec's; north faces at y = 5.0 as in the map | **not the cause** |
| Wheel odometry | Over-counts rotation by 14.5 % (12.13 vs 10.59 rad turned; net heading 0.66 rad off), distance within 2 % (9.81 vs 10.00 m). **But AMCL replayed with the truth as a perfect odometry drifts more** (0.681 m vs 0.398 m) | **not the cause** (a robot-config issue, frozen; recorded) |
| Scan timestamps | The fit of turning scans (angular speed over 0.3 rad/s) peaks at Δt = 0: fraction of beams within 0.1 m — ghost 1: 0.901 at 0 s, 0.832 at −0.05 s, 0.804 at +0.05 s; ghost 2: 0.912, 0.808, 0.793 | **not the cause** |
| AMCL parameters | Replayed variants ([`amcl_replay_ghost1_*.json`](.)): z_hit 0.95/z_rand 0.05 → 0.405 m; sigma_hit 0.1 → 0.316 m; alphas 0.5 → 0.487 m; 12 m range + 240 beams → 0.407 m; **update_min_d/a 0.05 → 0.208 m** | update thresholds **contribute** |
| A missing scan-matching feature in a featureless area | AMCL's own likelihood (60 beams, σ 0.2, z_hit/z_rand 0.5, capped 2 m), scored on the recorded scans: during leg 1 (driving east along y ≈ 8.4 and turning at the pick pose) it **peaks 0.15–0.30 m south of the truth**; afterwards the truth scores higher but the filter does not climb back | the mechanism; see the inputs below |
| COCO's own body in its scan | **Retracted.** A first count over one run (ghost 1, ~70 returns under 0.6 m per scan, bearings 30–110°) looked like COCO seeing itself; counted on open floor only (COCO > 1 m from any mapped obstacle) it is **0.00 per scan** in both ghost runs and 0.19 in a smoke run ([`extra_m6f8_ghost_1.json`](extra_m6f8_ghost_1.json), [`extra_m6f8_ghost_2.json`](extra_m6f8_ghost_2.json): `short_returns_open_floor`, 338 and 332 open-floor scans): those returns were the pallets and the crate beside COCO, not COCO. Dropping close returns (`laser_min_range` 0.65) did reduce the replayed drift, but by discarding real obstacles; it is **not** used | **not the cause** |
| Bodies the map leaves out | Unmapped returns cluster at `bad_crate` (44.5, 7.5; 0.3 m tall, above the 0.2135 m scan plane), the parked walker (40, 8.75) and the parked north–south forklift. Crate added: 0.398 → 0.360 m; crate + actors: 0.333 m | **a cause** (smaller) |

## The fix (generated files only: `tools/m6/gen_level.py --derivation 2`)

AMCL `update_min_d` 0.05 and `update_min_a` 0.05 (from 0.25 m / 0.2 rad: a filter that updates often
is not captured by one leg's wrong peak); the map also holds the objects whose body crosses the scan
plane (`bad_crate`, 48 cells). Nothing else: the costmaps and the collision monitor are untouched. Each change and its reason
is in the generated `params_derivation.json`; checksums
[`coco_depot_v1_outputs_d2.json`](coco_depot_v1_outputs_d2.json). Derivation 1 (M6F.2's) still
verifies identical; the reference copies (`gazebo_models/config`, `maps`) are untouched.

Replayed offline with the fix ([`amcl_replay_ghost_1_fix_v2.json`](amcl_replay_ghost_1_fix_v2.json),
[`…ghost_2_fix_v2.json`](amcl_replay_ghost_2_fix_v2.json)): ghost 1 **0.398 → 0.243 m** at the end (max
0.410 → 0.267, mean 0.287 → 0.180); ghost 2 **0.354 → 0.182 m** (max 0.381 → 0.238, mean 0.260 → 0.153).
**A residual south-west bias of 0.15–0.24 m remains, not explained** (the likelihood peak south of the
truth on leg 1 is measured, its geometric source is not). Whether that is enough for the 0.8 m pallet
gap is what the live gate measures.

A first derivation 2 also set `laser_min_range` and the costmaps' `obstacle_min_range` to 0.65 m on the
self-hit reading above; gate run 1 ran with it before the reading was retracted (recorded in GATE.md).

## Live gate

See [`GATE.md`](GATE.md).
