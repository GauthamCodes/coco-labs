# Phase 6 (Lab 5, Move) evidence

Write-up: `docs/labs/LAB5_MOVE.md`. Numbers: `docs/RESULTS.md` "COCO Lab
Phase 6". Formats: `docs/labs/MOVE_FORMAT.md`.

## What is here

| path | what | made by |
|---|---|---|
| `drive/<scenario>/` | drive bundle 1.0 per scenario: the frozen path, the arena's boxes, every valid run (ground truth, AMCL, controller and wheel commands, actor tracks, chosen trajectories, DWB's per-cycle counts; candidates for the first run of each controller); metrics replay-checked | `lab5_evidence.py` from the matrix's `run.json` files |
| `results.json` | per scenario and controller: outcomes, metric distributions, supplementary checks, every run's row | `lab5_evidence.py` |
| `replan/arena_c/` | Experiment C as a glass-box replan bundle 1.0 | `lab5_replan_c.py` |
| `replan_c.json` | Experiment C's summary and rounds | `lab5_replan_c.py` |
| `replan_sketch_stats.json` | D\* Lite vs A\* work over Sketch seeds 0–199 | `lab5_replan_sketch_stats.py` |
| `snapshot_c1/` | the Experiment C session: both global costmaps (gzipped JSON), `meta.json`, `runner.log` | `lab5_run.sh snapshot` |

The raw bags are NOT committed: the slim bag per run (5–19 MB, measured
over the 54) and the heavy debug bag (DWB `/evaluation`, MPPI
`/trajectories`; e.g. 433,166,723 B for `static_room_DWB_1`). The
heavy bag of every matrix run was hashed (`heavy.files` in each run's record)
and deleted after extraction; the slim bags stay in
`~/coco_lab_runs/lab5/matrix/` on the machine that recorded them, their
SHA-256 in each run's record (`bag_sha256`).

## The tools

| file | needs | does |
|---|---|---|
| `lab5_run.sh` | an overlay (`COCO_WS`), Gazebo | one session on a FRESH simulator: `capture` (freeze the paths), `run OUT SCENARIO CONTROLLER`, `snapshot` (Experiment C). Refuses if any Gazebo runs or if processes of an earlier run on its ROS domain (66) are up; sweeps only its own domain |
| `lab5_matrix.sh` | as above | the 54-run matrix: interleaved controllers, extraction, actor check, heavy bag hashed then deleted; resumable, VOID runs set aside and retried |
| `lab5_watch.py` | ROS | live checks: wheel topic owner, arbiter inputs, lab node publishers; parameter readback that fails a section it cannot read; the `/initialpose` operator action |
| `lab5_capture.py` | ROS | ask SmacPlanner2D once per path; write the frozen path files |
| `lab5_snapshot.py` | ROS | save a settled `/global_costmap/costmap_raw` |
| `lab5_extract.py` | ROS (rosbag2_py) | condense a run's bags into `run.json` (map frame, sim clock) |
| `lab5_actor_seen.py` | ROS | per scan, the beam at the actor against ground-truth geometry |
| `lab5_evidence.py`, `lab5_replan_c.py`, `lab5_replan_sketch_stats.py`, `lab5_tables.py` | coco_lab only | the evidence above |

## Reproduce

```bash
# a COCO-only overlay of this tree with a quotable path (the worktree path
# has parentheses that break colcon/gz quoting): Phase 5's ~/coco_search_ws
scripts/build_overlay.sh ~/coco_search_ws
export COCO_WS=~/coco_search_ws ROS_DOMAIN_ID=66
R=$COCO_WS/src/coco-labs/docs/data/lab5
$R/lab5_run.sh capture ~/coco_lab_runs/lab5/capture1          # paths (already frozen in config/lab5_paths)
$R/lab5_matrix.sh ~/coco_lab_runs/lab5/matrix 5                # ~3 h on this machine
$R/lab5_run.sh snapshot ~/coco_lab_runs/lab5/snapshot_c1
# then, from the repository root, coco_lab importable, no ROS:
python3 -P docs/data/lab5/lab5_evidence.py ~/coco_lab_runs/lab5/matrix
python3 -P docs/data/lab5/lab5_replan_c.py docs/data/lab5/snapshot_c1
python3 -P docs/data/lab5/lab5_replan_sketch_stats.py
python3 docs/data/lab5/lab5_tables.py
```

Measured runs: the matrix ran from source `656264a` (clean), Experiment C
from `4cb984f` (clean), both on 2026-10-07.
