# COCO-Bench v0 · arena-nav-50 (v0, draft for R3)

**Proving Ground: 50 start/goal pairs.** Navigation on the original COCO arena (the Proving Ground, 0.05 m cells): 50 seeded start/goal pairs in free space (clearance > 0.35 m, at least 3 m apart, connected on the planning grid). The reference world for every existing STACK recording.

- World: `coco_arena_v1` (World Spec sha256 `87f5d88f40af39bc98bc0b9cfac5dd2ce1686370fcca7aec8d171ff0181290f0`)
- Scenarios: 50 (frozen in [`coco_lab/coco_lab/benchmarks/arena-nav-50.v0.json`](../../../../../coco_lab/coco_lab/benchmarks/arena-nav-50.v0.json); generator `tools/r1/make_suites.py`, {"kind": "sampled", "min_clearance_m": 0.35, "min_separation_m": 3.0, "n": 50, "rejected_separation": 3, "rejected_unreachable": 0, "require_reachable": true, "seed": 5001, "stratify": "none"})
- Families: planning, control, localisation; metrics fixed per family in the suite file. Reference results committed for: control, localisation, planning.

Reference results: MODEL (coco_lab, hash version 3), every built-in algorithm at its default parameters (localisation: MCL 60 particles / 12 beams, EKF 12 beams), computed natively with `coco experiment run` (`tools/r1/make_references.py`). Counts are device-independent; `compute_ms` is wall time on the machine in each manifest. Success: Wilson 95% interval; metrics: median [IQR] (type-7 quantiles) over the runs where the metric is defined, with that N.

## control — 200 runs, digest `b492b3de896c0b3b…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Time to goal or end (s): median [IQR] · N | Distance driven (m): median [IQR] · N | Contacts (count): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| builtin | 50 | 50/50 · 100.0% [92.9, 100.0] | succeeded 50 | 59.35 [38.53, 73.67] · 50 | 16.87 [10.84, 21.14] · 50 | 0 [0, 0] · 50 |
| dwa | 50 | 31/50 · 62.0% [48.2, 74.1] | failed_to_make_progress 18, no_valid_control 1, succeeded 31 | 38.3 [21.65, 61.18] · 50 | 10.81 [5.2, 17.72] · 50 | 0 [0, 0] · 50 |
| rpp | 50 | 41/50 · 82.0% [69.2, 90.2] | no_valid_control 9, succeeded 41 | 49.9 [26.9, 65.8] · 50 | 14.55 [7.466, 19.19] · 50 | 0 [0, 0] · 50 |
| mppi | 50 | 49/50 · 98.0% [89.5, 99.6] | no_valid_control 1, succeeded 49 | 113.1 [74.33, 143.5] · 50 | 17.04 [11.08, 21.44] · 50 | 0 [0, 0] · 50 |

Files: [results.csv](control/results.csv) · [summary.json](control/summary.json) · [spec.json](control/spec.json) · [manifest.json](control/manifest.json) · [runs.jsonl](control/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## localisation — 150 runs, digest `66263713427ed631…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Final position error (m): median [IQR] · N | Mean position error (m): median [IQR] · N | Convergence time (s): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| mcl | 50 | 25/50 · 50.0% [36.6, 63.4] | localised 25, timeout 25 | 0.1404 [0.08434, 0.1762] · 50 | 0.1384 [0.1181, 0.1538] · 50 | 0 [0, 0] · 50 |
| mcl_augmented | 50 | 28/50 · 56.0% [42.3, 68.8] | localised 28, timeout 22 | 0.1223 [0.09463, 0.1787] · 50 | 0.1359 [0.1147, 0.1752] · 50 | 0 [0, 0] · 50 |
| ekf | 50 | 47/50 · 94.0% [83.8, 97.9] | localised 47, timeout 3 | 0.01761 [0.009847, 0.03419] · 50 | 0.1039 [0.0971, 0.1112] · 50 | 0 [0, 0] · 50 |

Files: [results.csv](localisation/results.csv) · [summary.json](localisation/summary.json) · [spec.json](localisation/spec.json) · [manifest.json](localisation/manifest.json) · [runs.jsonl](localisation/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## planning — 300 runs, digest `3533c4c3e74a0255…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Expansions (count): median [IQR] · N | Path length (m): median [IQR] · N | Path cost (cost): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| bfs | 50 | 50/50 · 100.0% [92.9, 100.0] | found 50 | 68,521.5 [43,186, 85,834.2] · 50 | 17.11 [11.05, 21.53] · 50 | 499.9 [323, 675.5] · 50 |
| dijkstra | 50 | 50/50 · 100.0% [92.9, 100.0] | found 50 | 67,902 [41,760.2, 89,086.2] · 50 | 17.65 [11.43, 22.1] · 50 | 354.9 [229.9, 442.6] · 50 |
| astar | 50 | 50/50 · 100.0% [92.9, 100.0] | found 50 | 12,105 [3,149.8, 27,623.5] · 50 | 17.65 [11.43, 22.1] · 50 | 354.9 [229.9, 442.6] · 50 |
| greedy | 50 | 50/50 · 100.0% [92.9, 100.0] | found 50 | 1,155.5 [249.2, 3,155.5] · 50 | 18.6 [11.88, 24.53] · 50 | 575.2 [395.5, 797.7] · 50 |
| weighted_astar | 50 | 50/50 · 100.0% [92.9, 100.0] | found 50 | 2,874 [549, 8,712.5] · 50 | 17.79 [11.5, 22.37] · 50 | 405.6 [293.7, 547.9] · 50 |
| dstar_lite | 50 | 50/50 · 100.0% [92.9, 100.0] | found 50 | 10,847.5 [5,914.8, 24,658] · 50 | 17.65 [11.43, 22.1] · 50 | 354.9 [229.9, 442.6] · 50 |

Files: [results.csv](planning/results.csv) · [summary.json](planning/summary.json) · [spec.json](planning/spec.json) · [manifest.json](planning/manifest.json) · [runs.jsonl](planning/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## Gazebo + Nav2

No Gazebo + Nav2 recording of these scenarios exists yet.
