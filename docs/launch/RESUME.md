# Résumé bullets (draft — numbers only from committed evidence; source after each)

- Built **COCO Lab**, an open-source browser robotics lab: a deterministic Python model of a ROS 2
  differential-drive robot running in Pyodide, with per-tick state hashes identical across
  4 engines (Chromium, Firefox, WebKit, Pyodide/Node; 0 mismatched ticks)
  [docs/v2/r2/data/r29/determinism_v2.json].
- Designed **COCO-Bench v1**: 12 frozen navigation benchmark suites (450 scenarios) for planning,
  control and localisation, with feature-based difficulty tiers, generated datasheets and
  held-out scenarios drawn from a secret outside a sandbox [coco_lab/coco_lab/benchmarks/,
  docs/bench/v1/, docs/v2/adr/0014-held-out-secret-salt.md].
- Built a ROS 2-shaped algorithm API and an in-browser **sandboxed code runner** (19/19 hostile
  files contained, 68/68 escape probes blocked in each of 3 browsers)
  [docs/v2/r2/data/r29/escape_*.json], and a **CI-verified leaderboard** (no-network,
  unprivileged container; separate trusted writer).
- Exported user algorithms unchanged to **ROS 2 nodes** and validated them in **Gazebo + Nav2**
  (Jazzy): the A* starter planned 60/60 requests; a pure-pursuit controller completed 40/40
  legs [docs/v2/r2/data/r27/summary.json].
- Wrote a workshop paper whose every number is generated from committed data and checked in CI
  [docs/paper/].

(Update the counts from `docs/paper/generated/numbers.tex` after R3's baselines are final.)
