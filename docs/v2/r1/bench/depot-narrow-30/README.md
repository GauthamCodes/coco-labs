# COCO-Bench v0 · depot-narrow-30 (v0, draft for R3)

**Depot: the workshop maze and the rack aisles.** Planning and control where the Depot is tight. 15 pairs whose reference A* path (default costmap: inflation 0.5 m, scaling 10, robot radius 0.25 m) runs at least 5 m inside the workshop maze (a dead-end corner of the Depot: one end is in the maze, so the route must thread it), and 15 whose reference path crosses at least 5 m of the high-bay rack aisles with both ends outside them. Pairs come in draw order from a seeded pool of 600 (seed 3001, separation >= 4 m); "passes" and "in_zone_m" record why each was chosen.

- World: `coco_depot_v1` (World Spec sha256 `1f912fcd8bb4055a411c97bb00b7472a727740ba671074978968bcb177b74841`)
- Scenarios: 30 (frozen in [`coco_lab/coco_lab/benchmarks/depot-narrow-30.v0.json`](../../../../../coco_lab/coco_lab/benchmarks/depot-narrow-30.v0.json); generator `tools/r1/make_suites.py`, {"kind": "filtered", "min_clearance_m": 0.35, "min_in_zone_m": 5.0, "min_separation_m": 4.0, "pool": 600, "reference": "astar on the default static costmap", "seed": 3001})
- Families: planning, control; metrics fixed per family in the suite file. Reference results committed for: control, planning.

Reference results: MODEL (coco_lab, hash version 3), every built-in algorithm at its default parameters (localisation: MCL 60 particles / 12 beams, EKF 12 beams), computed natively with `coco experiment run` (`tools/r1/make_references.py`). Counts are device-independent; `compute_ms` is wall time on the machine in each manifest. Success: Wilson 95% interval; metrics: median [IQR] (type-7 quantiles) over the runs where the metric is defined, with that N.

## control — 120 runs, digest `86643da7d30308b9…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Time to goal or end (s): median [IQR] · N | Distance driven (m): median [IQR] · N | Contacts (count): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| builtin | 30 | 30/30 · 100.0% [88.6, 100.0] | succeeded 30 | 128.7 [97.18, 147.8] · 30 | 37.21 [27.93, 43.19] · 30 | 0 [0, 0] · 30 |
| dwa | 30 | 12/30 · 40.0% [24.6, 57.7] | failed_to_make_progress 13, no_valid_control 5, succeeded 12 | 44.95 [20.4, 109] · 30 | 13.12 [2.682, 32.08] · 30 | 0 [0, 0] · 30 |
| rpp | 30 | 8/30 · 26.7% [14.2, 44.4] | no_valid_control 22, succeeded 8 | 24.75 [14.73, 82.23] · 30 | 6.826 [4.034, 23.92] · 30 | 0 [0, 0] · 30 |
| mppi | 30 | 23/30 · 76.7% [59.1, 88.2] | succeeded 23, timeout 7 | 251.6 [188.2, 289] · 30 | 37.98 [28.49, 43.74] · 30 | 0 [0, 0] · 30 |

Files: [results.csv](control/results.csv) · [summary.json](control/summary.json) · [spec.json](control/spec.json) · [manifest.json](control/manifest.json) · [runs.jsonl](control/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## planning — 180 runs, digest `2c35d5b4847ca997…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Expansions (count): median [IQR] · N | Path length (m): median [IQR] · N | Path cost (cost): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| bfs | 30 | 30/30 · 100.0% [88.6, 100.0] | found 30 | 87,235.5 [67,868.2, 100,038.2] · 30 | 37.71 [28.42, 43.67] · 30 | 542.1 [430, 683.5] · 30 |
| dijkstra | 30 | 30/30 · 100.0% [88.6, 100.0] | found 30 | 89,111 [65,985.8, 100,120.5] · 30 | 38.44 [29.12, 44.36] · 30 | 387.2 [294.6, 448.3] · 30 |
| astar | 30 | 30/30 · 100.0% [88.6, 100.0] | found 30 | 9,523.5 [6,034.2, 15,864] · 30 | 38.44 [29.12, 44.36] · 30 | 387.2 [294.6, 448.3] · 30 |
| greedy | 30 | 30/30 · 100.0% [88.6, 100.0] | found 30 | 2,159 [524.2, 3,783.5] · 30 | 39.15 [31.69, 45.69] · 30 | 638.5 [500.7, 707.9] · 30 |
| weighted_astar | 30 | 30/30 · 100.0% [88.6, 100.0] | found 30 | 2,076.5 [934.8, 4,295.8] · 30 | 38.58 [31.07, 45.44] · 30 | 442.4 [353.2, 521.9] · 30 |
| dstar_lite | 30 | 30/30 · 100.0% [88.6, 100.0] | found 30 | 18,547.5 [8,306.8, 41,855.2] · 30 | 38.44 [29.12, 44.36] · 30 | 387.2 [294.6, 448.3] · 30 |

Files: [results.csv](planning/results.csv) · [summary.json](planning/summary.json) · [spec.json](planning/spec.json) · [manifest.json](planning/manifest.json) · [runs.jsonl](planning/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## Gazebo + Nav2

No Gazebo + Nav2 recording of these scenarios exists yet.
