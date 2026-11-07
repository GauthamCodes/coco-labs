# Résumé bullets (draft — numbers only from committed evidence; source after each)

Author line: Gautham (no affiliation). Remove the bracketed sources in the final résumé.

- Built **COCO Lab**, an open-source browser robotics lab (live, deployed through CI with a live
  smoke test [docs/v2/r3/data/deploy1/README.md]): a deterministic Python model of a ROS 2
  differential-drive robot running in Pyodide, with per-tick state hashes identical across
  4 engines (Chromium, Firefox, WebKit, Pyodide/Node; 0 mismatched ticks)
  [docs/v2/r2/data/r29/determinism_v2.json].
- Designed **COCO-Bench v1**: 12 frozen navigation benchmark suites (450 scenarios) for planning,
  control, localisation and a fetch task, with feature-based difficulty tiers, generated
  datasheets and held-out scenarios drawn from a secret outside the sandbox (threat-modelled in an
  ADR and attacked with hostile submissions in the real container)
  [coco_lab/coco_lab/benchmarks/, docs/bench/v1/, docs/v2/adr/0014-held-out-secret-salt.md,
  docs/v2/r3/data/heldout/README.md].
- Built a ROS 2-shaped algorithm API and an in-browser **sandboxed code runner** (19/19 hostile
  files contained, 68/68 escape probes blocked in each of 3 browsers)
  [docs/v2/r2/data/r29/escape_*.json], and a **CI-verified leaderboard** (no-network,
  unprivileged container; separate trusted writer); its first community entry verified at
  100/100 public and 20/20 held-out [leaderboard/results/depot-nav-100/theta_star/result.json].
- Exported user algorithms unchanged to **ROS 2 nodes** and validated them in **Gazebo + Nav2**
  (Jazzy): the A* starter planned 60/60 requests; a pure-pursuit controller completed 40/40
  legs [docs/v2/r2/data/r27/summary.json].
- Diagnosed a **model-vs-ROS 2 gap**: an any-angle planner that wins in the model reached 0/5
  goals under Nav2's controller; costmap logging showed 29–77 % of its received paths entering
  inscribed cost vs ≤ 10 % for the planners that succeeded [docs/v2/r3/data/a1/README.md]; and
  showed that stock Nav2's 42/60 vs 60/60 was a start/goal snapping convention (snapped: 60/60)
  [docs/v2/r3/data/a1/snap_summary.json].
- Wrote a workshop paper whose every number is generated from committed data and checked in CI
  [docs/paper/].

(Update the counts from `docs/paper/generated/numbers.tex` after R3's baselines are final.)
