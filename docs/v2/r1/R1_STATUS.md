# R1 · Research Workbench — status

Prompt: [`R1_PROMPT.md`](R1_PROMPT.md). Plan-change entry: [`../../STATUS.md`](../../STATUS.md) (2026-10-31).

## Now

- **State (2026-11-03): R1.8 Performance done** ([`data/r18/README.md`](data/r18/README.md)): 400-run Depot
  experiment in the browser 54.3 s on 6 workers (native digest identical); emulated phone 2 × 20 in 18.0 s on 2
  workers; Play fps unchanged (60.07 / 60.02 medians vs baseline 60.07 / 60.02). Real phone: not connected.
- **State (2026-11-03): R1.7 Compare and navigation done** ([`data/r17/README.md`](data/r17/README.md)): Compare on every
  world; scenario picker (seeded / suite with Previous-Next / hand-placed) replaying the experiments' own runs (=
  the reference numbers); table links; hand-off to the builder; Play · Learn · Compare · Workbench; three doors; Learn page.
- **State (2026-11-03): R1.6 Exports, notebook, Datasets done** ([`data/r16/README.md`](data/r16/README.md)): a
  browser export (+ MCAP traces) equals the native one byte for byte (wall time removed); the notebook reproduces
  summary.json from results.csv (2.0e-16); Datasets tab: 11 checksummed datasets incl. 3 MODEL ↔ STACK pairs.
- **State (2026-11-03): R1.5 Benchmarks done** ([`data/r15/README.md`](data/r15/README.md)): COCO-Bench v0 — four
  frozen suites (50, 100, 30, 4 scenarios), 1,970 reference runs committed (the R1.5 commit message says 2,170: wrong); a random 10% re-run with the tree's
  code: 197 of 197 match; Benchmarks tab with maps and Race Nav2 links for the colour rounds.
- **State (2026-11-03): R1.4 Links and Verify done** ([`data/r14/README.md`](data/r14/README.md)): link → fresh
  context → "Reproduced exactly" in Chromium, Firefox and WebKit (and the fragment form); same digest natively.
- **State (2026-11-03): R1.3 Builder and results done** ([`data/r13/README.md`](data/r13/README.md)): form ⇄ JSON/YAML,
  results (N, Wilson, median/IQR, charts, paired tests, every run, failures filter); a11y 12 pages pass.
- **State (2026-11-03): R1.2 Worker pool done** ([`data/r12/README.md`](data/r12/README.md)): `ExperimentPool`
  (streaming, pause, cancel with partial results, ETA); native-vs-Pyodide parity on the four golden experiments:
  4,269 values, 0 differences, digests = golden (CI step added).
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
| R1.2 Worker pool | done | [`data/r12/README.md`](data/r12/README.md), [`parity.json`](data/r12/parity.json) |
| R1.3 Builder and results | done | [`data/r13/README.md`](data/r13/README.md), [`a11y.json`](data/r13/a11y/a11y.json) |
| R1.4 Links and verification | done | [`data/r14/README.md`](data/r14/README.md) |
| R1.5 Benchmarks | done | [`data/r15/README.md`](data/r15/README.md), [`bench/`](bench/) |
| R1.6 Exports and notebook | done | [`data/r16/README.md`](data/r16/README.md), [notebook](notebooks/analyse_experiment.ipynb) |
| R1.7 Compare and navigation | done | [`data/r17/README.md`](data/r17/README.md), [`compare_check.json`](data/r17/compare_check.json) |
| R1.8 Performance | done (real phone pending: not connected) | [`data/r18/README.md`](data/r18/README.md) |
| R1.9 Close | pending | |

## Gautham: look at these

- R1.7: [`data/r17/screens/`](data/r17/screens/) — the three-door title, the Learn page, Compare and Recordings (desktop, emulated phone both orientations).
- R1.5–R1.6: [`data/r15/a11y/`](data/r15/a11y/), [`data/r16/a11y/`](data/r16/a11y/) — Benchmarks and Datasets.
- R1.3: [`data/r13/a11y/`](data/r13/a11y/) — the Workbench builder and results, desktop and emulated phone landscape, dark and light.

## Deviations so far

- The before set has no Play shot of a running game: G1's Play opens on its mode select (no canvas), so the shared
  tool's ready condition timed out on `play`; those three shots are kept and labelled. The prompt's four
  surfaces (title, Compare, Research, Learn) are all ready.

## Questions for Gautham

- Plug in the Nothing Phone (1) with USB debugging when convenient: R1.8's phone row is emulated only.
