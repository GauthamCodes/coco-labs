# M4.3 terrain determinism (100 sessions, four engines)

Criterion (README §7 M4, Determinism): terrain sessions identical across Chromium, Firefox, WebKit and
Pyodide-in-Node, 100 sessions. **Result: `determinism.json` — pass, 70,000 ticks per engine, 0 mismatched.**

- `sessions.json`: `tools/perf/determinism.mjs make --terrain 1` (generator mulberry32(20261011); World
  Spec v2; 700 ticks each; inputs: goal 185, grasp 269, teleop 221, autonomy 142, stop 84, planner 51).
- `coverage_cpython.json`: what the sessions exercise, run in **CPython** (`m43_coverage.py`): 53 reach a
  platform, 69 climb, 37 grasps reach carry, 33 release, 20 sessions with a contact, every command source.
  CPython is not one of the four engines; its final hash agrees with Pyodide's in 84 of 100 sessions
  (different `libm`, as `docs/v2/ARENA_MODEL.md` says it may), so these counts describe the CPython runs of
  the same inputs.
- `hashes_<engine>.json.gz`: every tick's state hash and each session's chain, per engine.
- `run_node.log`: the first run (`m43_det.sh`). Pyodide-in-Node completed on 2026-10-11 (20:37 start; the
  laptop was on battery for most of it, which slows a run and changes no hash). Its Chromium pass then died
  when the laptop suspended overnight, and was stopped.
- `run_browsers.log`: the three browsers re-run on 2026-10-12 on AC, balanced (`m43_det_browsers.sh`),
  against the same built site, then `compare`.

CI replays the first 3 sessions in all three browsers against `hashes_pyodide-node.json.gz` on every pull
request (`.github/workflows/lab.yml`).
