# COCO-Bench v0 · colour-fetch-4 (v0, draft for R3)

**Fetch by colour: the four rods.** The full task on the Depot with colour rods: the reference bot (planner + waypoint driver + Grasp Assist) fetches each rod (red 20 mm, green 24 mm, blue 28 mm, yellow 32 mm) and delivers it to Dispatch, driven by each global planner. Grasp Assist's approach planning stays A*, as in Play. Fetch by colour rules 2 (actors yield). Gazebo + Nav2 recordings of the same four rounds exist (STACK ghosts g2_colour_<colour>).

- World: `coco_depot_colours_v1` (World Spec sha256 `6a16532b6a9cff8a8609fc74bc48265b3d7b313ca66c3ec54d79c2c83d6d0eec`)
- Scenarios: 4 (frozen in [`coco_lab/coco_lab/benchmarks/colour-fetch-4.v0.json`](../../../../../coco_lab/coco_lab/benchmarks/colour-fetch-4.v0.json); generator `tools/r1/make_suites.py`, {"kind": "rounds", "rules": 2})
- Families: fulltask; metrics fixed per family in the suite file. Reference results committed for: fulltask.

Reference results: MODEL (coco_lab, hash version 3), every built-in algorithm at its default parameters (localisation: MCL 60 particles / 12 beams, EKF 12 beams), computed natively with `coco experiment run` (`tools/r1/make_references.py`). Counts are device-independent; `compute_ms` is wall time on the machine in each manifest. Success: Wilson 95% interval; metrics: median [IQR] (type-7 quantiles) over the runs where the metric is defined, with that N.

## fulltask — 20 runs, digest `d954ee57d494d7d7…`

| Algorithm | N | Success (Wilson 95%) | Outcomes | Time to complete (s): median [IQR] · N | Path efficiency (ratio): median [IQR] · N | Contacts (count): median [IQR] · N |
| --- | --- | --- | --- | --- | --- | --- |
| bfs | 4 | 4/4 · 100.0% [51.0, 100.0] | completed 4 | 59.85 [58.33, 61.95] · 4 | 0.9477 [0.9414, 0.9587] · 4 | 0 [0, 0] · 4 |
| dijkstra | 4 | 4/4 · 100.0% [51.0, 100.0] | completed 4 | 60 [58.55, 61.98] · 4 | 0.9498 [0.9445, 0.9596] · 4 | 0 [0, 0] · 4 |
| astar | 4 | 4/4 · 100.0% [51.0, 100.0] | completed 4 | 60.5 [58.03, 63.68] · 4 | 0.9534 [0.9467, 0.9632] · 4 | 0 [0, 0] · 4 |
| greedy | 4 | 4/4 · 100.0% [51.0, 100.0] | completed 4 | 60.15 [58.1, 62.8] · 4 | 0.9455 [0.9427, 0.9514] · 4 | 0 [0, 0] · 4 |
| weighted_astar | 4 | 4/4 · 100.0% [51.0, 100.0] | completed 4 | 60.15 [58.1, 62.8] · 4 | 0.9455 [0.9427, 0.9514] · 4 | 0 [0, 0] · 4 |

Files: [results.csv](fulltask/results.csv) · [summary.json](fulltask/summary.json) · [spec.json](fulltask/spec.json) · [manifest.json](fulltask/manifest.json) · [runs.jsonl](fulltask/runs.jsonl). Host: 13th Gen Intel(R) Core(TM) i5-13420H, 8 workers (the manifest's wall_s includes time the laptop was suspended; per-run compute_ms uses a monotonic clock that does not).

## Gazebo + Nav2 (STACK)

Nav2 driving these rounds in Gazebo (simulation; no physical robot exists), recorded in G2: driving legs only, no grasp. Watch one against the model in Play: "Race Nav2".

- blue: [`lab_web/public/stack/ghosts/g2_colour_blue.json`](../../../../../lab_web/public/stack/ghosts/g2_colour_blue.json)
- green: [`lab_web/public/stack/ghosts/g2_colour_green.json`](../../../../../lab_web/public/stack/ghosts/g2_colour_green.json)
- red: [`lab_web/public/stack/ghosts/g2_colour_red.json`](../../../../../lab_web/public/stack/ghosts/g2_colour_red.json)
- yellow: [`lab_web/public/stack/ghosts/g2_colour_yellow.json`](../../../../../lab_web/public/stack/ghosts/g2_colour_yellow.json)
