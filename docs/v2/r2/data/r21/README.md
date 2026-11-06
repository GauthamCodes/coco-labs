# R2.1 · The algorithm API and the security design — MODEL / TESTED

[ADR 0013](../../../adr/0013-algorithm-api-v1.md) (the API), [ADR 0012](../../../adr/0012-running-strangers-code.md)
(the threat model). Code: `coco_lab/coco_lab/api.py` (the types, `Context`), `user_code.py` (the guard),
`exp_user.py` (running files through the API; the Arena hooks), `api_builtins.py` (the built-ins behind the same
three signatures), additive wiring in `experiments.py`, `exp_families.py`, `move_arena.py`, `loc_arena.py`.

## Built-ins unchanged (the stop condition) — MODEL

| Check | Result |
| --- | --- |
| COCO-Bench v0 references, a 10% sample re-run with the R2 code (`python -m coco_lab.experiments verify DIR --sample 0.1`, the same sample R1.5 drew) | **197 / 197 match** (every chain and count): [`reference_sample.txt`](reference_sample.txt) |
| every v1, v2 and v3 golden, the golden experiment, the native gate's unit tests | the full coco_lab suite on the R2 tree (plain venv, CI's pins): **1298 passed, 0 failed** (R1.9: 1192): [`coco_lab_full.txt`](coco_lab_full.txt) |
| a built-in spec's id and run descriptors | unchanged by construction: only a `user` entry carries `api` / `code_sha256` (`test_exp_user.py::test_user_spec_is_additive`) |
| v2/v3 state of a built-in run | unchanged: the user controller's and localiser's runtime lives outside the Arena (a weak map), its engine is plain data, and `user` is not appended to `CONTROLLERS`/`FILTERS` (so every built-in keeps its index in the v1 state bytes) |

## Built-ins through the API, measured as user code is — MODEL

`test/test_api_equivalence.py`: each built-in run natively and through its `api_builtins` wrapper exactly as a user's
file is run (`name: user`), on COCO-Bench v0 scenarios. Status, every metric except wall time, the expanded cells in
order, the path cell for cell and (Arena families) the truth pose at every tick:

| Algorithm | Result |
| --- | --- |
| BFS, Dijkstra, A*, greedy, weighted A* (arena-nav-50 × 4, depot-narrow-30 × 2; smoke: depot-nav-100 × 3) | **identical** |
| DWA, Regulated Pure Pursuit (400 ticks), MPPI (40 ticks), arena-nav-50 × 2 | **identical** (every tick's pose) |
| MCL, MCL + augmented injection, EKF (arena-nav-50; smoke: 2 scenarios to the goal) | **identical** (poses, series, every metric) |
| **D\* Lite** | status, path, expansions, steps, clearance, heading **identical**; `path_length_m` and `path_cost` differ by ≤ 3 × 10⁻¹⁵ relative |

**The D\* Lite finding.** Its native adapter (`compare_planning.run_planner`, M5) sums the path's length and cost with
Python's built-in `sum()`, which since Python 3.12 is compensated (Neumaier); `coco_lab.search` (the other five
planners) and the API's measurement add in order. One measurement cannot reproduce both conventions bit for bit, so
D\* Lite through the API reads 19.635028842544436 m where natively it reads 19.635028842544404 m. **No native result,
hash or golden changes** (the 10% sample and the goldens above). Raised as a question for Gautham: accept as
recorded, make the API's measurement compensated (then the five search planners differ by an ulp instead), or give
D\* Lite's adapter sequential addition under a new experiment version.

The waypoint driver (`builtin`) is not wrapped: it is the Arena's own M1 driving loop, not a controller function.

## The guard and the user runs — TESTED

`test/test_user_code.py` (imports refused — `js`, `pyodide`, `pyodide.ffi`, `os`, `sys`, `time`, `importlib`,
`builtins`, `ctypes`, `socket`, `gc`, `inspect`, `operator`, `numpy` …; escape syntax refused — `__class__`,
`__globals__`, `__subclasses__`, `_private`, `gi_frame`, `f_globals`, `tb_frame`, `mro`, `format_map`; missing builtins;
guarded `getattr`; shims public-only; deterministic `math`; exact `**`; `random` follows `ctx.rng`; bounded console;
tracebacks mapped to lines; every template passes), `test/test_api.py` (message shapes field for field, exact yaw
round trip, ROS-ordered grids, COCO's robot from its World Spec, `emit`, the step budget, PSD), `test/test_exp_user.py`
(specs, `user.*` parameters and sweeps, contract statuses, exceptions with line numbers, `budget_exceeded`, the
determinism flag catching an address-ordered set, Twist clamping logged, controller and localiser contract errors,
the CLI's `--algorithm` with export and `verify`). The ament lint (flake8, pep257, copyright): **correction** — this
line first said it was clean on every new file; the `coco_lab` package suite (`run_all_package_tests.sh`, R2 overlay,
[`packages_coco_lab.log`](packages_coco_lab.log): 1305 passed, 3 failed) showed it was not: `ros2_export.py` had long
lines, and the starter files in `coco_lab/templates/` failed style and copyright checks. Fixed: `ros2_export.py`
restyled (its generated package text checked byte-identical before and after), and the lint tests exclude
`coco_lab/templates/` (user algorithm files, never imported, named by their exact bytes' sha256 in parity CI and the
ROS 2 runs; restyling them would change those hashes). The three lint tests and `test_ros2_export.py`: 8 passed. The
whole package suite is re-run at R2.9.

Found and fixed while running the R2.0 baseline: R2's `user_code.py` used `**` on its integer branch, which
`test_numerics_v3.py` forbids in the model (C `pow`); it now calls `pow()` for integers (exact).

**Update 2026-11-06 (R3 Part A, Gautham: exactness first).** Resolved: the wrapper declares its native summation (`Builtin.summation`) and the measurement adds in that order, so D\* Lite through the API is now **identical** in every metric, including `path_length_m` and `path_cost` (exact-equality test on arena-nav-50 × 4 and depot-narrow-30 × 2). The finding above is kept as found. See ADR 0013 and R2_RESULTS "Gautham's answers".
