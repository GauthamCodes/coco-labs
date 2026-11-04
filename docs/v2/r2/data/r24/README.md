# R2.4 · Compare, experiments and native — MODEL / TESTED

- **Native CLI:** `coco experiment run spec.json --algorithm my_planner.py --out DIR` (`python -m coco_lab.experiments`)
  registers the file, fills (or appends) its `user` entry by sha256, runs it under the same guard in worker processes
  with `PYTHONHASHSEED=0`, and exports it as `algorithms/<id>.py` beside the results; `verify DIR` re-runs an export,
  algorithm files included (`test_exp_user.py::test_cli_algorithm`).
- **Experiments in the browser:** the Studio's "Benchmark it" runs a COCO-Bench suite with the file and any built-ins in a
  pool of user-code sandboxes (every run of that experiment, the built-ins' too: one runtime measures them all), then
  R1's results (N, Wilson, medians and IQRs, paired tests).
- **Compare:** "Compare with <built-in>" runs the file and the built-in on the same scenario in the sandbox and draws
  them side by side (GAME or SIM), with both columns of metrics.

## Parity: every starter template, browser vs native — CI (`lab_web/tools/r2/parity.mjs`)

Each template beside a built-in on the first scenarios of arena-nav-50, in CPython 3.12.3 and in Pyodide 314.0.7
(Python 3.14) in Node, `PYTHONHASHSEED=0` in both: [`parity.json`](parity.json) — **850 values compared, 0 differences**
(statuses, hash chains, counts, determinism flags, validation reports; wall times excluded).

| Template | Runs | Determinism | Differences |
| --- | --- | --- | --- |
| planner_astar | 8 | all deterministic | 0 |
| planner_greedy | 8 | all deterministic | 0 |
| planner_empty | 6 | all deterministic | 0 |
| teach_heuristic | 6 | all deterministic | 0 |
| controller_pure_pursuit | 4 | all deterministic | 0 |
| controller_empty | 4 | all deterministic | 0 |
| teach_tune_dwa | 2 | all deterministic | 0 |
| localiser_particle_filter | 2 | all deterministic | 0 |
| localiser_empty | 2 | all deterministic | 0 |

Timing (this laptop, power-saver on AC, Gazebo idle): native 216 s, Pyodide-in-Node 413 s. CI runs it beside R1's parity
check (`lab.yml`, timeout 45 → 70 min).
