# R3 · COCO-Bench v1 and the paper — status

Prompt: [`R3_PROMPT.md`](R3_PROMPT.md) (Part B; Part A in [`LANDING_STATUS.md`](LANDING_STATUS.md)).
Branch `v2/r3-bench-paper` from main `5df4427` (PR #32 merged). Worked in the
`~/coco_labs_ws/worktrees/r1` checkout (this session is pinned to it; `worktrees/r3` was not created).
Overlay for local package tests: `~/coco_lab_r3_ws` (symlink-install of this checkout).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| R3.0 Start, A1 follow-up tooling | in progress | `tools/r2/ros2_bench.py` (`--snap`, `--costs`), `tools/r3/ros2_queue_a1.sh` |
| R3.1 COCO-Bench v1 suites, tiers, datasheets | — | |
| R3.2 Browser-model baselines | — | |
| R3.3 Held-out from a secret salt (ADR 0014) + hostile tests | — | |
| R3.4 Gazebo + Nav2 baselines | — | |
| R3.5 Gap analysis, "Model vs ROS 2" page | — | |
| R3.6 Leaderboard v1 | — | |
| R3.7 The paper | — | |
| R3.8 Launch kit | — | |
| R3.9 Close | — | |

## Machine log

- 2026-11-06: start balanced/AC (profile changed from power-saver; restore at the end). Later the same day
  AC went offline (battery discharging, 98 %): the A1 Gazebo queue was stopped before any simulator started;
  it now waits for AC + balanced before every session (`on_ac` in the queue).

## Next step

Land PR #31 (verified by the sandboxed verifier and the trusted writer on main), deploy, live smoke; then
R3.1. The A1 Gazebo queue runs as soon as AC is back.
