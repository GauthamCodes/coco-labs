# R2.9 · Close — TESTED / MEASURED (laptop; the phone emulated, the real phone not connected)

Machine: i5-13420H (12 threads), 16 GB, RTX 4050 Laptop GPU (driver 580.178.04), Node 24.21.0, Python 3.12.3
(`~/coco_labs_ws/r1_venv`, CI's pins), Pyodide 314.0.7. **Balanced profile on AC** for every measurement (each file
records it); the laptop's own profile (power-saver) restored afterwards.

## How it ran (three passes, every failure kept)

| Pass | Tree | What happened |
| --- | --- | --- |
| attempt 1 | `0eeb140` | `coco_lab` against the **installed** package: **29 failed**, 1274 passed — R2's `test_exp_user.py` and `test_api_equivalence.py` had no `COCO_WORLDS` fixture (R1's tests do), so an installed `coco_lab` (as CI runs it) found no worlds. The earlier full run (1298 passed) resolved `worlds/` from the tree and missed it. Stopped; fixed in `86a28e1` ([`failures/attempt1_coco_lab_venv.txt`](failures/attempt1_coco_lab_venv.txt)) |
| attempt 2 | `86a28e1` | every suite and check ([`suites_final.txt`](suites_final.txt), [`close_attempt2.log`](close_attempt2.log)). Three things failed and were fixed in `7eaa7b6`: **lab_web/tools 1 failed** (a test required Gautham's Theta* submission in the tree; it is PR #31) ([`failures/attempt2_lab_web_tools.txt`](failures/attempt2_lab_web_tools.txt)); **a11y**: the Studio on the **light theme** had 92 text nodes under AA contrast (the editor's syntax colours were the dark theme's: 1.1–1.9:1) ([`failures/attempt2_a11y.json`](failures/attempt2_a11y.json)); the new Studio timing tool waited on the wrong element (a tool bug, no measurement) ([`failures/`](failures/)). The laptop suspended for 30 h mid-run (lid closed, 2026-11-05 02:46Z → 2026-11-06 09:11Z) and resumed where it was; the steps run after resuming were correctness checks, AC was back before any measurement |
| re-check | **`7eaa7b6` (final)** | everything the fixes touch: lab_web/tools, typecheck, vitest, build twice, a11y, escape × 3, the Studio check and after-screenshots, the Studio timings, Play fps ([`recheck_final.log`](recheck_final.log)) |

**Found afterwards by the R2 PR's CI** (lab run 42213656796, "Build twice"): `tools/check_dist.mjs` rejected
external URLs in the build — R1's Datasets hyperlinks and Colab link (main has failed this step since the R1 merge,
run 41897972116) and R2's lockdown probe URL. `tools/g2/suites.sh` piped the check into `tail` and so reported it as
passing locally. Fixed (narrow allow-list entries with reasons; `pipefail` in the runner); build twice + check_dist
re-run on the fixed tree: identical, 0 failures; vitest 640/640.

Between attempt 2 and the final tree only `lab_web/src/studio/{editor.ts,studio.css}` (colours), one test and one tool
changed; every suite those files can reach was re-run on the final tree.

## Tests and determinism

| Suite | R1.9 (= R2's base) | R2 final |
| --- | --- | --- |
| coco_lab, installed (plain venv) | 1192 passed | **1303 passed**, 0 failed (`86a28e1`; [log](suites/coco_lab_venv.log)) |
| coco_lab gz | 2 | 2 |
| lab_web/tools pytest | 248 | **263 passed** ([log](final_lab_web_tools.log)) |
| vitest | 631 (83 files) | **640 (84 files)** ([log](final_vitest.log)) |
| typecheck, schemas check, build twice (same tree hash), arena assets, coco verify (18/18), update isolation, v1 site (pinned, tree `6857ff56…`), screenshots, chase HUD, saved view, v1 links (50 forms, 6 archive views), replays | pass | pass |
| ROS packages (12, `run_all_package_tests.sh`, R2 overlay) | all pass | **all 12 pass** (coco_lab 1308 incl. ament flake8/pep257/copyright) ([log](suites/packages.log)) |
| native gate, hash v3 | exact | **exact**: 818,951 planner values, 1,436 Fetch Rush values, 0 differences ([json](suites/native_gate.json)) |
| determinism v1 (10 sessions × Chromium, Firefox, WebKit, Pyodide-in-Node) | 1,500 each, 0 diff, `9a9d582d03f4` | **1,500 each, 0 diff, `9a9d582d03f4`** |
| terrain (3 sessions × 4 engines) | 2,100, 0 diff, `3a8c227eca45` | **2,100, 0 diff, `3a8c227eca45`** |
| determinism v2 (10 sessions × 4 engines vs M5's committed v2 hashes) | 1,500 each, 0 diff, `4597f9417b0b` | **1,500 each, 0 diff, `4597f9417b0b`** ([json](determinism_v2.json)) |
| v3: goldens (in coco_lab), native gate, R1 parity | unchanged | **unchanged** |
| R1 parity (golden experiments, native vs Pyodide) | 4,269 values, 0 diff | **4,269, 0 diff** ([json](r1_parity.json)) |
| R2 parity (every starter, native vs Pyodide) | — | **850 values, 0 diff** ([json](r2_parity.json)) |
| R1 reference sample (10% of COCO-Bench v0, re-run with the final code) | 197/197 | **197/197 match** ([log](reference_sample.txt)) |
| R1 browser checks: link → fresh context (Chromium, Firefox, WebKit, long form), Compare, export = native | pass | **pass** |
| accessibility (now with the Studio and the Leaderboard): 24 pages, desktop + emulated phone, dark + light | 16 pages pass | **24 pass**: 0 contrast failures, 0 unfocusable controls ([json](a11y.json)) |
| **escape tests** (19 hostile files + 68 lockdown probes) | — | **pass in Chromium, Firefox and WebKit**: every escape failed safely ([chromium](escape_chromium.json), [firefox](escape_firefox.json), [webkit](escape_webkit.json)) |
| Studio check (run, determinism, Compare, controller, ROS 2 export, consent link, Learn, emulated phone ×2) | — | **12/12** ([json](studio_check.json)) |

## Performance — MEASURED (balanced, AC)

Play fps, `tools/g1/perf_play.mjs`, Fetch Rush 2 min, NVIDIA renderer (ANGLE, RTX 4050); baseline = main's tree
(`worktrees/r1`, byte-identical to R2's base) served beside the R2 build:

| Run | Drawn fps median | min | Frame interval median / p99 / max (ms) | > 50 ms | Frame JS median (ms) |
| --- | --- | --- | --- | --- | --- |
| baseline, desktop high | 60.05 | 59.18 | 16.5 / 20.7 / 23.0 | 0 | 3.5 |
| **R2 final, desktop high** | **60.10** | **59.17** | 16.6 / 20.4 / 22.3 | 0 | 2.7 |
| baseline, emulated phone medium | 59.99 | 56.29 | 16.6 / 19.4 / 42.3 | 0 | 6.5 |
| **R2 final, emulated phone medium** | **60.01** | **56.48** | 16.6 / 19.6 / 35.0 | 0 | 6.3 |

Unchanged (the stop condition did not fire); attempt 2's R2 runs on `86a28e1` agree (60.07 / 60.03): [`play_fps/`](play_fps/).

The Studio, `tools/r2/perf_studio.mjs` (wall time on the named device; never a ranking metric):

| Device | One run of the A* starter (arena-nav-50 s001, incl. the sandbox's first boot) | Benchmark it: the starter + the built-in A* on all 50 arena-nav-50 scenarios (100 runs; each of the starter's run twice) |
| --- | --- | --- |
| laptop (4 sandboxes) | **5.7 s** (the planning call 1.71 s) | **29.1 s**, 50/50 and 50/50 ([json](perf_studio_laptop.json)) |
| **emulated** Nothing Phone (1), 4× CPU throttle (1 sandbox) | 5.9 s | 95.9 s, 50/50 and 50/50 ([json](perf_studio_phone.json)) |
| real Nothing Phone (1) | **not measured: not connected** (`adb devices` empty) | — |

## After screenshots

[`../../screens/r29/`](../../screens/r29/) (checksums: [`after_screens.sha256`](after_screens.sha256)), listed in
[`../../BEFORE_AFTER.md`](../../BEFORE_AFTER.md) for Gautham.
