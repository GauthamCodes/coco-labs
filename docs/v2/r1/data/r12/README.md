# R1.2 Worker pool and native-vs-browser parity

Evidence class: MODEL / TESTED.

## What was added

- `lab_web/src/workbench/pool.ts` — `ExperimentPool`: N Arena workers (Pyodide + coco_lab), each warmed like
  the title's interpreter, one run at a time through `arena_glue.experiment`; records stream in as they finish
  and are keyed by run index (order-independent); **pause** stops handing out runs (in-flight runs finish),
  **cancel** terminates busy workers and keeps every record received; an ETA from the median of recent run
  times; size = cores − 1 capped at 6, at most 2 on phones or devices reporting ≤ 4 GB.
- Worker protocol (`protocol.ts`, `arena.worker.ts`, `client.ts`): `experiment` requests (`plan`, `run`,
  `summary`, `export`, `digest`, plus `replay` and `trace` used by R1.6–R1.7); the worker fetches the shipped
  World Spec once and loads the `experiments` pack (which requires localise, move and game).
- `arena_glue.py`: `experiment`, `experiment_world`, `experiment_replay` — the glue computes nothing; it calls
  `coco_lab.experiments`.
- `lab_web/tools/r1/parity.mjs` + `parity_cases.py`, and a CI step in the `lab-web` job (its limit 30 → 45 min).

## Results

| Check | Result |
| --- | --- |
| `test/r1_pool.test.ts` (fake workers finishing out of order; pause/resume; cancel keeps partial; sizing; ETA) | 4 passed |
| typecheck | pass |
| **parity** (`node tools/r1/parity.mjs`, [`parity.json`](parity.json)): the four golden experiments (planning 32 runs, control 6, localisation 2, full task 1) in CPython 3.12.3 and Pyodide 314.0.7 | **4,269 values compared, 0 differences**; every digest equals the committed golden digest |

Every count, status, per-run hash chain, digest, `results.csv` row and `summary.json` number is compared;
`compute_ms` (wall time) is excluded. Wall time of the check on this laptop (balanced, AC; MODEL work only,
not a budget): CPython 207 s, Pyodide-in-Node 405 s (`parity.json`).
