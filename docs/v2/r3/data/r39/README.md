# R3.9 · Close — TESTED / MEASURED (laptop; the phone emulated, the real phone not connected)

Machine: i5-13420H (12 threads), 16 GB, RTX 4050 Laptop GPU (driver 580.178.04), Node 24.21.0, Python 3.12.3
(`~/coco_labs_ws/r1_venv`, CI's pins), Pyodide 314.0.7. **Balanced profile on AC** for every step (each log's header
records it); the laptop's own profile (power-saver) restored afterwards. No simulator ran during the close.

## How it ran (every failure kept)

| Pass | Tree | What happened |
| --- | --- | --- |
| main | `aa601a7` | every suite and check ([`main/close.log`](main/close.log), [`main/suites_final.txt`](main/suites_final.txt)). Two failed: **coco_lab's ament flake8** (two E501 lines in `experiments.py`; all 1321 other coco_lab package tests passed) and **a11y** — the **Leaderboard page crashed** on the entries made from the baselines (no `host`; the page read `e.host.cpu`), so the audit timed out on it; the R3 screenshot step failed the same way. CI does not render the Leaderboard with this data |
| re-check | **`a4b3d95` (final)** | fixed (entries carry their baseline manifest's host; the page tolerates a missing host; a test requires it; the two lines wrapped), then everything the fixes reach on the final tree: ament linters, experiments + suite tests, lab_web/tools, catalog, arena assets, typecheck, vitest, build twice + check_dist, a11y (now with Model vs ROS 2 and About), Studio check, R3 screenshots ([`recheck/close.log`](recheck/close.log)) — all pass |

Found earlier by the PR's CI and fixed in `a4157b9`: the paper job's matplotlib 3.6 needs numpy < 2 (pinned 1.26.4);
the coco_lab venv job passed 1317 tests in 59:38 and was cancelled by its 60-minute limit (now 90; browsers 45 → 60).
Between the main pass and the final tree only those fixes, `R3_RESULTS.md` and the two workflows changed.

## Tests and determinism

| Suite | R2 final | R3 final |
| --- | --- | --- |
| coco_lab, installed (plain venv) | 1303 passed | **1317 passed** ([log](suites/coco_lab_venv.log)) |
| ROS packages (12, `run_all_package_tests.sh`) | all 12 pass | 11 pass + coco_lab 1321 passed / 1 failed (flake8, fixed); ament linters re-run on the final tree: **3 passed** ([log](suites/packages.log), [re-check](recheck/coco_lab_ament.log)) |
| lab_web/tools pytest | 263 | **299 passed** (final tree, [log](recheck/lab_web_tools.log)) |
| typecheck, schemas, vitest, build twice (same tree hash) + check_dist, arena assets, coco verify (18/18), update isolation, v1 site, screenshots, chase HUD, saved view, v1 links (50 forms), replays | pass | **pass** |
| native gate, hash v3 | exact | **exact**: 818,951 planner values, 0 differences ([json](suites/native_gate.json)) |
| determinism v1 (10 sessions × Chromium, Firefox, WebKit, Pyodide-in-Node) | 1,500 each, 0 diff, `9a9d582d03f4` | **1,500 each, 0 diff, `9a9d582d03f4`** |
| terrain (3 sessions × 4 engines) | 2,100, 0 diff, `3a8c227eca45` | **2,100, 0 diff, `3a8c227eca45`** |
| determinism v2 (10 sessions × 4 engines) | 1,500 each, 0 diff, `4597f9417b0b` | **1,500 each, 0 diff, `4597f9417b0b`** ([json](main/determinism_v2.json)) |
| R1 parity / R2 parity (native vs Pyodide) | 0 diff | **0 diff** ([R1](main/r1_parity.json), [R2](main/r2_parity.json)) |
| R1 reference sample (10 % of COCO-Bench v0, 8 sets) | 197/197 | **197/197 match** ([log](main/reference_sample.log)) |
| R3 baseline sample (5 % of 16 v1 baseline sets: all but loc-global/kidnap and the fetch task) | — | **185/185 match** ([log](main/r3_baseline_sample.log)) |
| suites v1 regenerate byte for byte; datasheets current; paper `make check` | — | **pass** ([suites](main/suites_v1_check.log), [paper](main/paper_check.log)) |
| R1 browser checks: links (3 browsers + long), Compare, export = native | pass | **pass** |
| accessibility: 32 pages (8 views incl. Model vs ROS 2 and About × desktop + emulated phone × dark + light) | 24 pass | **all 32 pass**: 0 contrast failures, 0 unfocusable controls ([json](recheck/a11y.json)) |
| escape tests (19 hostile files + 68 lockdown probes) | pass × 3 | **pass in Chromium, Firefox and WebKit** ([chromium](main/escape_chromium.json), [firefox](main/escape_firefox.json), [webkit](main/escape_webkit.json)) |
| Studio check | 12/12 | **pass** ([json](recheck/studio_check.json)) |
| R3 screens + eye checks (control/localisation boards, Contacts, tiers, Submit guide, Model vs ROS 2 tables, Reproduce link; no sideways scroll) | — | **pass** ([json](recheck/r3_screens.json)) |

The held-out hostile tests (ADR 0014) ran in the real container in R3.1 ([`../heldout/`](../heldout/README.md)); the
workflow changes since (nullglob, per-run timeout, paper-link check) do not touch what they test.

## Performance — MEASURED (balanced, AC)

Play fps, `tools/g1/perf_play.mjs`, Fetch Rush 2 min, NVIDIA renderer (ANGLE, RTX 4050), compared with R2's committed
numbers on this laptop ([`../../../r2/data/r29/README.md`](../../../r2/data/r29/README.md)):

| Run | Drawn fps median | min | Frame interval median / p99 / max (ms) | > 50 ms |
| --- | --- | --- | --- | --- |
| R2 final, desktop high | 60.05 | 59.18 | 16.5 / 20.7 / 23.0 | 0 |
| **R3 final, desktop high** | **60.16** | **59.26** | 16.6 / 19.2 / 30.2 | 0 |
| R2 final, emulated phone medium | 60.01 | 56.48 | 16.6 / 19.6 / 35.0 | 0 |
| **R3 final, emulated phone medium** | **60.01** | **56.21** | 16.6 / 21.3 / 44.1 | 0 |

Unchanged (R3 does not touch Play). The R3 runs ran on the main pass's build (`aa601a7`); the fixes after it do not
reach Play. Raw: [`main/play_fps/`](main/play_fps/).

## After screenshots

[`../../screens/r39/`](../../screens/r39/) (checksums: [`after_screens.sha256`](after_screens.sha256)), listed in
[`../../BEFORE_AFTER.md`](../../BEFORE_AFTER.md). Desktop 1440×1000 and the **emulated** Nothing Phone (1).
