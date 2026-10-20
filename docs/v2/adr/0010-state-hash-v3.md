# ADR 0010 — State hash v3: deterministic numerics

Date: 2026-10-20. Evidence class MODEL. Scope G1.8 (an M5 carry-over).

## Problem

The Arena model runs in CPython (desktop, CI, the reference) and in Pyodide (the
browser). IEEE 754 fixes `+ - * /` and `sqrt` bit for bit, but not `sin`, `cos`,
`atan2`, `exp`, `log` or `pow`: glibc (with FMA variants chosen at load time) and
musl compiled to WebAssembly may differ in the last bit. Measured:

- M5's review: native and Pyodide Compare arms diverge — a LiDAR endpoint 1 ulp
  apart falls in a different costmap cell (`LocalWindow.index`'s `floor`), DWA picks
  another candidate at tick 47, and the chosen trajectories are 0.446011142799704 m
  apart at tick 48 (`docs/v2/data/m5/closure-20261020/REPORT.md`).
- G1.6: at tick 0 of the Depot, 2 of 480 LiDAR ranges differ in the last bit;
  v2 hashes exact floats, so every tick's hash differs (`docs/v2/g1/data/g16/`).

Pyodide is the same in every browser engine (four-engine v2 contract, unchanged);
the gap is between the reference and the browser.

## Decision

**Hash version 3 = v2's snapshot encoding under its own tag and chain seed
(`coco.arena.state.v3`), computed with deterministic numerics.**

- `coco_lab/numerics.py` implements `sin cos tan atan atan2 acos exp log hypot dist`
  in pure Python from basic IEEE operations, `math.sqrt`, `math.ldexp`, `math.frexp`,
  `math.fmod`, `math.fsum` (all exact or correctly rounded everywhere): Sun's fdlibm
  (`e_rem_pio2`, `k_sin`, `k_cos`, `s_atan`, `e_atan2`, `e_acos`, `e_exp`, `e_log`),
  under one ulp of libm (tan two: `sin/cos`). Arguments beyond 2^19·π/2 are folded by
  `fmod(x, 2π)` instead of Payne–Hanek: deterministic, less accurate, never met.
  `hypot` is `sqrt` of a sequential sum of squares.
- `x ** 2`, `x ** 3`, `x ** 0.5` call C `pow`; the model's uses go through
  `numerics.sq / cube / root` (`x*x`, `x*x*x`, `sqrt` under v3; `**` under v1/v2).
- Every `coco_lab` module takes `math` from `numerics` (one shared namespace).
  `numerics.use(hash_version)` swaps ten entries in place: the real `math` functions
  under v1/v2 — **v1 and v2 are byte for byte what they were** — and the fdlibm ones
  under v3. The Arena calls it on every entry point (constructor, `begin_step`,
  `amend`, `advance`, `finish_step`); the glue's out-of-step queries (game ops,
  planner Compare) and `LoopComparison.advance` call it with their run's version.
- A small memo keeps the last 4,096 `sin`/`cos` answers (the LiDAR asks for each
  beam's direction three times a tick). The functions are pure, so a remembered
  answer is the same bits; zero is never kept (0.0 and −0.0 share a dictionary key).

New runs use v3: the Arena page (`?view=arena`), the game, Compare's arms and
Compare's live Arena. Links and records without `hv` stay v1, links with `hv: 2`
replay under v2, and Compare loop requests without `hash_version` (M5's recorded
ones) stay v2. M5 Play challenge scoring is unchanged.

## Validation

- `coco_lab/test/test_numerics_v3.py`: committed bit vectors
  (`fixtures/v3/numerics_vectors.json`), ulp bounds against libm, special values and
  signed zeros, no module imports the real `math`, no `**` on floats in the model,
  versions interleaved in one process do not leak, and four v3 goldens
  (`fixtures/v3/state_hash_v3.json`: the arena with teleop and a goal, the whole
  loop's MCL with a kidnap, the terrain world, a 1,419-tick Fetch Rush session).
  New files; no v1 or v2 golden is edited, and they all still pass.
- `lab_web/tools/g1/native_gate.mjs`, in CI: CPython vs the shipped Pyodide packs on
  M5's four-arm control and localisation Compare loops, every global planner and
  every tick's hash of a Fetch Rush session. Global families exact, continuous
  families within 1e-9. Under v3 every compared value is identical; run under v2
  the same cases fail with M5's 0.446011142799704 m (kept as the control):
  `docs/v2/g1/data/g18/`.
- Cost: Pyodide-in-Node per model tick on the Depot, same record, same machine:
  `docs/v2/g1/data/g18/README.md`.

## Consequences

The model is slower under v3 (pure-Python transcendentals; measured, not hidden).
A kernel that moves out of Python (M1.10's WebAssembly gate) must reproduce these
functions bit for bit, which a C port of the same fdlibm source does.
