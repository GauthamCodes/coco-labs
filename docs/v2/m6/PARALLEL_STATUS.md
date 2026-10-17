# M6 foundations — parallel status

The short status for branch `v2/m6-foundations` (worktree
`~/coco_labs_ws/worktrees/m6-foundations`), built in parallel with Codex's M5
under `PARALLEL_PROMPT.md`. `docs/STATUS.md` is **not** edited on this branch;
the entries below are copied into it at merge.

## Current checkpoint and next step

- **Current:** M6F.0 Setup — done.
- **Next:** M6F.1 World Spec v3 and the modular level kit.

## Setup facts (M6F.0, 2026-10-17)

- Branch `v2/m6-foundations` was created from the **local** `v2/m5-focus` at
  `0254dea` ("[M5.7] Support four planners in the shared Compare worker").
  `origin/v2/m5-focus` **does not exist**: Codex has not pushed M5, so the
  prompt's `origin/v2/m5-focus` could not be used (deviation, recorded).
  Picking up newer M5 work means `git merge v2/m5-focus` (the local ref,
  read-only for Codex) or `origin/v2/m5-focus` once it exists.
- Python environment: `~/coco_labs_ws/worktrees/m6-venv` (Python 3.12.3,
  `--system-site-packages --without-pip`, made like `~/coco_labs_ws/test_venv`,
  with that venv's pinned hypothesis 6.98.15, networkx 2.8.8 and
  sortedcontainers 2.4.0 copied in). PYTHONPATH points at this worktree's
  `coco_schemas`, `coco_schemas/coco_schemas/gen`, `coco_lab`, `coco_config`
  and `/opt/ros/jazzy/lib/python3.12/site-packages` (the ament linters).
- Baseline, on the untouched branch at `0254dea`, under `nice -n 19` with
  Codex active (load average 4.2 on 12 cores):
  - `coco_lab`: **824 passed**, 0 failed, 0 skipped (290.7 s)
  - `coco_schemas`: **232 passed**, 0 failed, 0 skipped (6.5 s)
- Machine at setup: AC online, profile `balanced`, NVIDIA driver 580.178.04
  (RTX 4050 Laptop GPU), `gz` CLI present (`/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz`).
  Codex was running (`codex resume`, PID 18281, plus the Codex desktop app).
  No Gazebo, Isaac or ROS 2 process was running.

## Plan-change entries to copy into docs/STATUS.md at merge

- **2026-10-17 — M6 foundations start in parallel with M5 (Gautham).** By
  issuing `docs/v2/m6/PARALLEL_PROMPT.md`, Gautham authorised one plan change:
  M6's foundations (World Spec v3 and the level kit, the generators, the Depot
  level, the Depot planning benchmark, Grasp Assist on the model side, the
  Fetch Rush and Rush Hour rules engines, the ROS-shaped message model, and
  the Gazebo/Nav2 validation) start now on branch `v2/m6-foundations`,
  without any user interface, in parallel with M5. They merge only after M5
  merges.

## Known merge points with M5

(Files outside this branch's own new files that this branch changes, or that
M5 is likely to change too. Updated at every checkpoint.)

- none yet

## Pending heavy items

(Heavy jobs wait for an idle machine: Codex not running, no robot batch, AC.)

- none yet
