# R1 · Research Workbench — status

Prompt: [`R1_PROMPT.md`](R1_PROMPT.md). Plan-change entry: [`../../STATUS.md`](../../STATUS.md) (2026-10-31).

## Now

- **State (2026-10-31): R1.0 Baseline in progress.** Worktree created, prompt saved, README §7 R track and the
  STATUS plan-change entry added. Baseline suites and before screenshots running.

## Setup facts

- Base: `origin/main` `7bbb430` (Merge PR #28, G2 · Sim Identity). Branch `v2/r1-workbench`.
- Worktree `~/coco_labs_ws/worktrees/r1`. Test venv `~/coco_labs_ws/r1_venv` (Python 3.12.3, CI pins from
  `coco_lab/requirements-test.txt`: pytest 7.4.4, hypothesis 6.98.15, networkx 2.8.8, PyYAML 6.0.1). ROS overlay
  `~/coco_lab_r1_ws` (`scripts/build_overlay.sh`). Node 24.21.0 (`~/coco_v2_ws/node/...`).
- Suites: `G2_VENV=~/coco_labs_ws/r1_venv/bin/python COCO_WS=~/coco_lab_r1_ws tools/g2/suites.sh OUT`.
- Laptop at start: 12 cores, 15 GB RAM, ~11 GB disk free; power profile **balanced, on battery (AC 0)**.
  Timing measurements wait for AC (recorded as pending, never estimated). No phone connected (adb: no device).

## Gautham's answers in planning, 2026-10-31

1. Top bar: **Play · Learn · Compare · Workbench**. Title doors: Play · Learn · Workbench. Workbench tabs:
   Experiments · Benchmarks · Recordings · Datasets.
2. Full-task scenarios use **the committed rounds only**: Fetch Rush seeds 1–6 × phone/full (rules 5) and the
   four colour rods (Fetch by colour rules 2). Stated as the v0 limit; no in-experiment round generation.

## Design decisions (agent, within the prompt)

- Every experiment run uses **state hash v3** (ADR 0010): the only version exact between CPython and Pyodide.
  v1/v2 behaviour and goldens are untouched.
- One runner in `coco_lab.experiments`, two hosts: CPython (`coco experiment run`) and the browser's Pyodide
  workers. Each run is a pure function of (spec, run index); per-run seeds come from `rng.Rng` splits.
- Statistics are hand-written (the browser's trimmed stdlib has no `statistics`): Wilson 95%, median/IQR,
  seeded bootstrap CI of the median, Wilcoxon signed-rank (exact conditional p by DP; normal approximation
  with tie correction beyond n = 300), rank-biserial r and Hodges–Lehmann effect sizes, McNemar exact for paired
  success, Holm adjustment for more than two algorithms.

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| R1.0 Baseline | in progress | |
| R1.1 Model side | pending | |
| R1.2 Worker pool | pending | |
| R1.3 Builder and results | pending | |
| R1.4 Links and verification | pending | |
| R1.5 Benchmarks | pending | |
| R1.6 Exports and notebook | pending | |
| R1.7 Compare and navigation | pending | |
| R1.8 Performance | pending | |
| R1.9 Close | pending | |

## Gautham: look at these

- (screenshots listed here as checkpoints produce them)

## Deviations so far

- None.

## Questions for Gautham

- None yet.
