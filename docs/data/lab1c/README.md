# Phase 1C evidence — `docs/data/lab1c/`

The tools and the committed results of COCO Lab Phase 1C. The design is
[`docs/labs/PHASE_1C_PLAN.md`](../../labs/PHASE_1C_PLAN.md); the results
are in [`docs/RESULTS.md`](../../RESULTS.md) "COCO Lab Phase 1C" and
[`docs/labs/CONFORMANCE.md`](../../labs/CONFORMANCE.md).

## Files

| file | what |
|---|---|
| `lab1c_run.sh` | one session on a fresh headless simulator: `conformance`, `run ALGO`, or `dry` |
| `lab1c_conformance.py` | the Smac/NavFn/coco_lab sweep (run by `lab1c_run.sh conformance`) |
| `lab1c_watch.py` | live checks: wheel/arbiter-input publishers, arbiter mode, lab node safety, params readback |
| `lab1c_report.py` | derives the conformance distributions from `conformance.json` |
| `conformance.json`, `conformance_summary.json` | the sweep's raw records and the derived summary |
| `S0_costmap_raw.bin.gz` | the sweep's costmap snapshot S0, raw Nav2-order bytes |
| `runs.json` | the three real runs: metrics and provenance |

Large artifacts (rosbag2 directories, and the bundles if their total
exceeds 10 MB — owner decision D-6) live under `~/coco_lab_runs/lab1c/`,
outside git; their SHA-256 hashes are in `runs.json`.

**Directory hash** (bags and bundles): SHA-256 over the lines
`<relative path> <file sha256>\n` of every file, sorted by path
(`coco_lab_ros.export.dir_sha256`).

## Reproduce

Build a COCO-only overlay of this repository and point the runner at it
(CLAUDE.md "Environment"):

```bash
scripts/build_overlay.sh "$HOME/coco_ws_build_lab"
export COCO_WS="$HOME/coco_ws_build_lab"
```

Nothing else may be running — the runner refuses otherwise, and it never
kills what it did not start (`ros_clean.sh` then sweeps its own orphans).
ROS domain 65 by default.

```bash
docs/data/lab1c/lab1c_run.sh conformance ~/coco_lab_runs/lab1c/conformance
python3 docs/data/lab1c/lab1c_report.py ~/coco_lab_runs/lab1c/conformance/conformance.json

docs/data/lab1c/lab1c_run.sh run ~/coco_lab_runs/lab1c/run_astar    astar
docs/data/lab1c/lab1c_run.sh run ~/coco_lab_runs/lab1c/run_dijkstra dijkstra
docs/data/lab1c/lab1c_run.sh run ~/coco_lab_runs/lab1c/run_greedy   greedy

ros2 run coco_lab_ros lab_export --bag RUN/bag --plan-dir RUN/plan \
    --out RUN/bundle --metrics RUN/metrics.json --run-id ID --checks RUN/checks.json
```

Each `run` is a fresh simulator (`full_world_robo.launch.py gui:=false
traverse:=true`), `lab_stack.launch.py` (arbiter `initial_mode:=nav`,
`nav.launch.py arbiter:=true` on the mission parameters merged with the
lab overlay), then `lab_planner` once: start = the AMCL belief at spawn,
goal G\* = world (0.5, 6.0), yaw 0 = map (2.5, 6.0), graph C1, one plan,
one FollowPath goal, no replanning, recorded with
`ros2 bag record --use-sim-time --include-hidden-topics -s mcap`.

Exit codes: 0 all runner checks passed; 1 a check failed (a result,
recorded); 3 refused; 4 void (infrastructure, plan E.2 / F-1); 5 the live
parameters differ from the merged file (F-3).
