# R1 · Research Workbench — status

Prompt: [`R1_PROMPT.md`](R1_PROMPT.md). Plan-change entry: [`../../STATUS.md`](../../STATUS.md) (2026-10-31).

## Now

- **State (2026-11-02): R1.1 Model side done** ([`data/r11/README.md`](data/r11/README.md)): `coco_lab.experiments`
  (spec, scenarios, four families, stats, runner, exports, CLI), golden experiment, 112 focused tests pass, every
  v1/v2/v3 golden unchanged.
- **State (2026-10-31): R1.0 Baseline done** ([`data/r10/README.md`](data/r10/README.md)): every suite on
  `3a03f48` (= main `7bbb430` + paperwork) green — coco_lab 1161, lab_web/tools 244, vitest 619 (80 files), native
  gate exact, coco verify 18/18, identical builds, v1 and terrain determinism in four engines 0 differences,
  screenshots/chase HUD/saved view/v1 links/replays pass; packages: all 12 pass (the first run refused: the R1
  overlay had no test venv; re-run with `--make-venv`). Before screenshots (title, Compare, Recordings, Learn;
  desktop + emulated phone) in [`screens/before/`](screens/before/).

## Setup facts

- Base: `origin/main` `7bbb430` (Merge PR #28, G2 · Sim Identity). Branch `v2/r1-workbench`.
- Worktree `~/coco_labs_ws/worktrees/r1`. Test venv `~/coco_labs_ws/r1_venv` (Python 3.12.3, CI pins from
  `coco_lab/requirements-test.txt`: pytest 7.4.4, hypothesis 6.98.15, networkx 2.8.8, PyYAML 6.0.1). ROS overlay
  `~/coco_lab_r1_ws` (`scripts/build_overlay.sh`). Node 24.21.0 (`~/coco_v2_ws/node/...`).
- Suites: `G2_VENV=~/coco_labs_ws/r1_venv/bin/python COCO_WS=~/coco_lab_r1_ws tools/g2/suites.sh OUT`.
- Laptop at start: 12 cores, 15 GB RAM, ~11 GB disk free; power profile **balanced, on battery (AC 0)**; on AC from
  about 11:00Z. Timing measurements only on AC. No phone connected (adb: no device).
- The coco_lab suite step's wall time (7 h 15 min vs G2's 25 min) includes time the laptop was not running the tests
  (the clock moved ~7 h while it ran); no test failed and nothing is concluded from it.
- Notebook venv `~/coco_labs_ws/r1_nb_venv` (pandas 2.2.3, matplotlib 3.9.2, nbclient 0.10.0, nbformat 5.10.4,
  ipykernel 6.29.5) for R1.6; the CI-pinned test venv is untouched.

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
- Statistics are hand-written (the browser's trimmed stdlib has no `statistics`): Wilson 95%, type-7 median/IQR,
  Wilcoxon signed-rank (exact conditional p by integer DP up to 50 non-zero pairs; normal approximation with tie and
  continuity corrections above), rank-biserial r and Hodges–Lehmann effect sizes, McNemar exact for paired success,
  Holm adjustment across algorithm pairs. No bootstrap (not asked; median and IQR are). The format is fixed in
  [ADR 0011](../adr/0011-experiments-v1.md).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| R1.0 Baseline | done | [`data/r10/README.md`](data/r10/README.md), [`screens/before/`](screens/before/) |
| R1.1 Model side | done | [`data/r11/README.md`](data/r11/README.md), [ADR 0011](../adr/0011-experiments-v1.md) |
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

- The before set has no Play shot of a running game: G1's Play opens on its mode select (no canvas), so the shared
  tool's ready condition timed out on `play`; those three shots are kept and labelled. The prompt's four
  surfaces (title, Compare, Research, Learn) are all ready.

## Questions for Gautham

- None yet.
