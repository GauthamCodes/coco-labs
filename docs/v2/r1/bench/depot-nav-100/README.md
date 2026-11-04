# COCO-Bench v0 · depot-nav-100 (v0, draft for R3)

**Depot: 100 pairs across its six zones.** Navigation across the COCO Depot (0.1 m cells): 100 seeded pairs stratified by the START's zone over the six region zones (17, 17, 17, 17, 16, 16 in spec order: loading dock, high bay, mezzanine, office, workshop, forklift lanes), goals in any zone, at least 5 m apart, connected on the planning grid.

- World: `coco_depot_v1` (World Spec sha256 `1f912fcd8bb4055a411c97bb00b7472a727740ba671074978968bcb177b74841`)
- Scenarios: 100 (frozen in [`coco_lab/coco_lab/benchmarks/depot-nav-100.v0.json`](../../../../../coco_lab/coco_lab/benchmarks/depot-nav-100.v0.json); generator `tools/r1/make_suites.py`, {"kind": "sampled", "min_clearance_m": 0.35, "min_separation_m": 5.0, "n": 100, "rejected_separation": 3, "rejected_unreachable": 0, "require_reachable": true, "seed": 1001, "stratify": "zone"})
- Families: planning, control, localisation; metrics fixed per family in the suite file. Reference results committed for: control, planning.

Reference results: MODEL (coco_lab, hash version 3), every built-in algorithm at its default parameters (localisation: MCL 60 particles / 12 beams, EKF 12 beams), computed natively with `coco experiment run` (`tools/r1/make_references.py`). Counts are device-independent; `compute_ms` is wall time on the machine in each manifest. Success: Wilson 95% interval; metrics: median [IQR] (type-7 quantiles) over the runs where the metric is defined, with that N.

## control — 400 runs, digest `f8fe561af97903a2…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Time to goal or end (s): median [IQR] · N | Distance driven (m): median [IQR] · N | Contacts (count): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| builtin | 100 | 100/100 · 100.0% [96.3, 100.0] | succeeded 100 | 102.3 [81.25, 129.6] · 100 | 29.47 [23.52, 36.88] · 100 | 0 [0, 0] · 100 |
| dwa | 100 | 64/100 · 64.0% [54.2, 72.7] | failed_to_make_progress 31, no_valid_control 5, succeeded 64 | 84.55 [45.58, 114.6] · 100 | 24.63 [11.23, 32.46] · 100 | 0 [0, 0] · 100 |
| rpp | 100 | 37/100 · 37.0% [28.2, 46.8] | no_valid_control 63, succeeded 37 | 64.5 [24.65, 88.03] · 100 | 18.75 [6.543, 26.1] · 100 | 0 [0, 0] · 100 |
| mppi | 100 | 83/100 · 83.0% [74.5, 89.1] | no_valid_control 4, succeeded 83, timeout 13 | 193.7 [151.5, 248.9] · 100 | 29.01 [22.55, 36.9] · 100 | 0 [0, 0] · 100 |

Files: [results.csv](control/results.csv) · [summary.json](control/summary.json) · [spec.json](control/spec.json) · [manifest.json](control/manifest.json) · [runs.jsonl](control/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## planning — 600 runs, digest `86876cd8e3dd3fd0…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Expansions (count): median [IQR] · N | Path length (m): median [IQR] · N | Path cost (cost): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| bfs | 100 | 100/100 · 100.0% [96.3, 100.0] | found 100 | 78,720 [38,905.8, 99,581] · 100 | 30.15 [24.01, 37.54] · 100 | 402.3 [300.6, 566.9] · 100 |
| dijkstra | 100 | 100/100 · 100.0% [96.3, 100.0] | found 100 | 75,898.5 [41,416.8, 101,936.2] · 100 | 30.21 [24.19, 38.73] · 100 | 305.2 [243, 393.5] · 100 |
| astar | 100 | 100/100 · 100.0% [96.3, 100.0] | found 100 | 12,872.5 [4,060, 22,323.8] · 100 | 30.21 [24.19, 38.73] · 100 | 305.2 [243, 393.5] · 100 |
| greedy | 100 | 100/100 · 100.0% [96.3, 100.0] | found 100 | 887 [268, 3,247.2] · 100 | 31.4 [24.95, 41.42] · 100 | 450.2 [318, 622.3] · 100 |
| weighted_astar | 100 | 100/100 · 100.0% [96.3, 100.0] | found 100 | 1,651 [427.5, 6,340] · 100 | 30.45 [24.35, 39.03] · 100 | 329.8 [265.5, 444] · 100 |
| dstar_lite | 100 | 100/100 · 100.0% [96.3, 100.0] | found 100 | 11,061 [5,241.8, 18,179.2] · 100 | 30.21 [24.19, 38.73] · 100 | 305.2 [243, 393.5] · 100 |

Files: [results.csv](planning/results.csv) · [summary.json](planning/summary.json) · [spec.json](planning/spec.json) · [manifest.json](planning/manifest.json) · [runs.jsonl](planning/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## Gazebo + Nav2

No Gazebo + Nav2 recording of these scenarios exists yet.
