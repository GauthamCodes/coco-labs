# R1.1 Model side — `coco_lab.experiments`

Evidence class: MODEL / TESTED. Format: [ADR 0011](../../../adr/0011-experiments-v1.md).

## What was added

- `coco_lab/coco_lab/experiments.py`: the `coco.experiment.v1` spec (validation, defaults, bounds, the
  parameter and metric tables), `plan` (scenarios and the ordered run list), `run_one`, `digest`,
  `summarise`, the export set (`results.csv`, `summary.json`, `spec.json`, `runs.jsonl`,
  `manifest.json`) and the CLI `python -m coco_lab.experiments run|verify|summarise`.
- `exp_scenarios.py` (seeded start/goal pairs on the planning grid's components; zones, stratification,
  hand-placed pairs; rejections counted), `exp_families.py` (planning, control, localisation, full task;
  per-run hash chains), `exp_stats.py` (Wilson, type-7 quantiles, Wilcoxon signed-rank exact/normal with
  rank-biserial and Hodges–Lehmann, McNemar exact, Holm).
- `move_arena.py`: `move.<dwa|rpp|mppi>.<field>=` and `move.window.<field>=` (additive; no attribute and the
  same engine construction when none is set, so v2/v3 hashes of every existing session are unchanged).
- `games.py`: the reference bots' optional `planner=` (the tick-0 input Play sends; `None` = unchanged).
- `lab_web/tools/coco.mjs`: `coco experiment run spec.json|yaml --out dir/` (YAML read in Node with `yaml`
  2.8.1, ISC; CPython does the work).
- Golden experiment `coco_lab/test/fixtures/r1/golden_experiment.json` (`tools/r1/make_golden_experiment.py`;
  never rewritten): one experiment per family — planning (4 planners × 4 pairs × an inflation sweep of 2:
  32 runs, all found), control (builtin, RPP, MPPI × 2 pairs: succeeded, timeout, no_valid_control),
  localisation (EKF and a 30-particle MCL with a kidnap: timeout, not_localised), full task (Fetch by colour,
  red, A*: completed in 68.1 s, the documented reference time).

## Checks (on this tree, R1 test venv, coco_lab installed from the tree as CI does)

| Check | Result |
| --- | --- |
| `test_exp_stats.py`, `test_experiments.py`, `test_numerics_v3.py`, `test_stdlib_only.py`, `test_move_arena.py`, `test_games.py`, `test_golden_traces.py`, `test_no_ros.py` | 112 passed |
| `tools/r1/make_golden_experiment.py --check` | golden unchanged |
| v1 golden traces, v3 goldens (state hash, numerics vectors) | unchanged (in the run above) |
| `coco experiment run tiny.yaml --out …` (Node → CPython) | 6 runs, digest written |

Found and fixed before commit (drafts only, never in a commit): the first draft added an `overrides`
attribute to the move subsystem unconditionally — v2/v3 hash every attribute, so that would have changed
every existing move session's hash (a stop condition); it now exists only once an override is set.
