# R1 · Research Workbench — results

[Prompt](R1_PROMPT.md) · [status](R1_STATUS.md) · [before/after](BEFORE_AFTER.md) · [ADR 0011](../adr/0011-experiments-v1.md) ·
branch `v2/r1-workbench` from main `7bbb430`. Evidence: **MODEL** (coco_lab, in the browser and natively),
**STACK** (Gazebo + Nav2 recordings, simulation), **MEASURED** (timed on this laptop, conditions stated),
**EMULATED** (the emulated Nothing Phone (1); never a phone). No physical robot exists.

## Checkpoints

| Checkpoint | Result | Evidence |
| --- | --- | --- |
| R1.0 Baseline | every suite green on main + paperwork; before screenshots | [`data/r10/`](data/r10/README.md) |
| R1.1 Model side | `coco_lab.experiments`: spec, scenarios, four families, statistics, runner, exports, CLI; golden experiment | [`data/r11/`](data/r11/README.md) |
| R1.2 Worker pool | pool with streaming, pause, cancel, ETA; native-vs-Pyodide parity 4,269 values, 0 differences (CI) | [`data/r12/`](data/r12/README.md) |
| R1.3 Builder and results | form ⇄ JSON/YAML; N, Wilson, median/IQR, five chart forms, paired tests, every run, failures filter; a11y 12 pages pass | [`data/r13/`](data/r13/README.md) |
| R1.4 Links and Verify | link → fresh context → "Reproduced exactly" in Chromium, Firefox, WebKit; fragment form; native digest identical (CI) | [`data/r14/`](data/r14/README.md) |
| R1.5 Benchmarks | COCO-Bench v0: 4 frozen suites, 1,970 reference runs committed, 10% re-run 197/197 match | [`data/r15/`](data/r15/README.md), [`bench/`](bench/) |
| R1.6 Exports and notebook | browser export = native export byte for byte (wall time removed); MCAP traces; notebook executed; Datasets tab | [`data/r16/`](data/r16/README.md) |
| R1.7 Compare and navigation | every world; scenario picker replaying the experiments' own runs; table links; hand-off; three doors; Learn page (CI) | [`data/r17/`](data/r17/README.md) |
| R1.8 Performance | 400 Depot runs in 54.3 s in the browser (6 workers); emulated phone 2 × 20 in 18.0 s; Play fps unchanged | [`data/r18/`](data/r18/README.md) |
| R1.9 Close | after screenshots; all suites; determinism v1/v2/v3; this file; the PR | [`data/r19/`](data/r19/) |

## Experiments — MODEL

- **Families:** global planning (BFS, Dijkstra, A*, greedy, weighted A*, D* Lite), local control (waypoint driver,
  DWA, Regulated Pure Pursuit, MPPI), localisation (MCL, MCL with augmented injection, EKF), full task (Fetch Rush
  rules 5 and Fetch by colour, the reference bot driven by a chosen planner; committed rounds only — Gautham's
  planning answer).
- **Parameters:** every one each algorithm exposes (costmap inflation, cost scaling, robot radius, heuristic weight,
  edge-cost weight, connectivity; every DWA/RPP/MPPI field and the local window; MCL/EKF settings), each
  sweepable (one parameter → line with IQR band, two → heatmap).
- **Scenarios:** seeded pairs in free space (minimum separation and clearance, zones, stratification, reachability
  — rejections counted and reported), a benchmark suite, hand-placed pairs, or committed rounds.
- **Statistics** (standard library, deterministic): N everywhere; Wilson 95%; type-7 medians and IQRs over the runs
  where a metric is defined; paired Wilcoxon signed-rank (exact up to 50 non-zero pairs) with rank-biserial r and
  Hodges–Lehmann shift beside every p; McNemar exact for success; Holm across algorithm pairs; "no significant
  difference" said plainly; a test that cannot be computed shows why (all differences zero, too few pairs, no
  discordant pairs) instead of a number. Every run is in the table and the export, failures and timeouts included.
- **Largest experiment tested in the browser:** 400 runs (4 planners × depot-nav-100); natively, the reference
  sets up to 600 runs (depot-nav-100 planning) and 400 control runs.
- **Workers:** cores − 1 capped at 6 (6 on this laptop); 2 on phones (and on devices reporting ≤ 4 GB).

## Reproducibility — MODEL / TESTED

| Check | Result |
| --- | --- |
| native vs Pyodide, the four golden experiments (`tools/r1/parity.mjs`, CI) | 4,269 values, **0 differences**; digests = committed golden |
| link → fresh browser context (`tools/r1/link_e2e.mjs`, CI) | "Reproduced exactly", identical tables, Verify 2/2 — Chromium, Firefox, WebKit; the `#expz=` fragment form in Chromium |
| the same spec natively (`coco experiment run`) | digest `2554d51e9df9d757…` = all three browsers |
| 400-run Depot experiment, browser vs native | digest `6060a0d2bf3896a9…` both |
| browser export vs native export (`tools/r1/export_check.mjs`) | results.csv, summary.json byte-identical (wall time removed); digest equal |
| committed references re-run with the final code (10%) | 197/197 match |
| Compare replay vs reference results (`tools/r1/compare_check.mjs`, CI) | expansions and lengths equal for every pane checked |

## COCO-Bench v0 — MODEL (references) / STACK (links)

| Suite | Scenarios | Reference runs | Headline (successes / N) |
| --- | --- | --- | --- |
| arena-nav-50 | 50 | 650 (planning, control, localisation) | every planner 50/50; waypoint driver 50, DWA 31, RPP 41, MPPI 49; MCL 25, MCL + injection 28, EKF 47 |
| depot-nav-100 | 100 (stratified over 6 zones) | 1,000 (planning, control) | every planner 100/100; waypoint driver 100, DWA 64, RPP 37, MPPI 83 |
| depot-narrow-30 | 30 (workshop maze, rack aisles) | 300 (planning, control) | every planner 30/30; waypoint driver 30, DWA 12, RPP 8, MPPI 23 |
| colour-fetch-4 | 4 (the rods) | 20 (full task) | every planner 4/4 |

Gazebo + Nav2 recordings exist for colour-fetch-4's four rounds (G2's STACK ghosts; linked to Race Nav2); none for
the navigation suites (stated on their pages). The teaching local controllers' failures stay in the results.

## Exports and notebook

Every export: results.csv, summary.json, spec.json, runs.jsonl, manifest.json (versions, hashes, checksums, host and
conditions), optionally one MCAP trace per Arena run (valid; one message per tick; checked against its chain) and
full-task game records. The notebook (`notebooks/analyse_experiment.ipynb`, executed, outputs kept) reproduces
summary.json from results.csv on the depot-nav-100 planning reference (largest relative difference 2.0e-16) and
draws the plots; "Open in Colab" goes live with the merge. Datasets tab: 11 checksummed datasets (8 references;
3 MODEL ↔ STACK pairs: Fetch by colour, Fetch Rush rules 5 phone rounds, Lab 5).

## Performance — MEASURED (balanced, AC, RTX 4050 driver 580.178.04, i5-13420H; original power-saver restored)

| Case | Result |
| --- | --- |
| Laptop: 4 × depot-nav-100 = 400 runs, browser | **54.3 s**, 6 workers (native, 6 processes: 30.3 s) |
| Phone: 2 × 20 = 40 runs, **emulated** Nothing Phone (1) | **18.0 s**, 2 workers |
| Real Nothing Phone (1) | **not measured: not connected** (pending) |
| Play fps (`tools/g1/perf_play.mjs`, Fetch Rush, 2 min), baseline → R1 | desktop high 60.07 → 60.07 (min 59.17 → 59.18); emulated phone medium 60.02 → 60.02 (min 58.12 → 58.21); 0 frames over 50 ms in all four |

## Tests and determinism

| Suite | Before (R1.0, `3a03f48`) | After (R1.9) |
| --- | --- | --- |
| coco_lab plain venv | 1161 passed | 1192 passed ([log](data/r19/suites_final.txt)) |
| coco_lab gz | 2 passed | 2 passed |
| lab_web/tools pytest | 244 | 248 |
| vitest | 619 (80 files) | 631 (83 files) |
| packages (12) | all pass | 11 pass; coco_lab's ament **flake8 and pep257 failed** on R1's new code (11 style findings: import order, two long lines, quotes, a docstring) — fixed, lint 2/2 pass, coco_lab package re-run on the fixed tree: **1197 passed** ([log](data/r19/packages_coco_lab_rerun.log)) — so all 12 pass |
| native gate (hash v3) | exact | exact (818,951 planner values, 1,436 Fetch Rush values) |
| R1 parity (hash v3, experiments) | — | 4,269 values, 0 differences |
| determinism v1 (10 sessions × 4 engines) | 1,500 hashes, 0 diff | 1,500, 0 diff |
| terrain (3 sessions × 4 engines) | 2,100, 0 diff | 2,100, 0 diff |
| determinism v2 (10 sessions × Chromium, Firefox, WebKit, Pyodide-in-Node vs M5's committed v2 hashes) | — | 1,500 each, 0 diff ([json](data/r19/determinism_v2.json)) |
| coco verify, build twice, update isolation, screenshots, chase HUD, saved view, v1 links, replays | pass | pass |
| golden experiment / v1 golden traces / v3 goldens | — | unchanged |
| R1 browser checks (links ×4, Compare, export, a11y 16 pages) | — | pass ([`data/r19/`](data/r19/)) |

## Stop conditions

None fired: no model or golden hash changed (every v1/v2/v3 golden and the native gate unchanged; the one draft
that would have changed v2/v3 move hashes was caught and fixed before any commit, R1.1); browser and native agree
on every count; every statistic is computed or says why it cannot be; Play's frame rate is unchanged.

## Questions for Gautham

1. The title's three doors have equal weight as asked; PLAY no longer dominates (any key still plays). Keep?
2. Plug in the Nothing Phone (1) with USB debugging when convenient: the phone experiment row is emulated only.
3. COCO-Bench v0's control references show the teaching controllers failing often in the Depot (RPP 37/100,
   8/30 in the narrow suite). Keep them as the v0 baseline, or tune the controllers' defaults (a new experiment
   version) before R3?
