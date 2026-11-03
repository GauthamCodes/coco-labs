# ADR 0011 — Experiments v1: spec, run chain, digest, statistics

Date: 2026-10-31. Evidence class MODEL. Scope R1 · Research Workbench (R1.1–R1.2).

## Problem

Research could only replay recordings; Compare ran one start, one goal and one seed. R1 makes
experiments — many runs of several algorithms over seeded scenarios — that anyone can re-run from
a link, in any browser or natively, and get the same numbers.

## Decision

**An experiment is a `coco.experiment.v1` spec**, validated and filled by
`coco_lab.experiments.plan` (the only authority; the page draws a form from
`lab_web/src/workbench/meta.json`, generated from the same tables):

- `world` (a World Spec id; its canonical sha256 is filled in as `world_sha256`), `family`
  (`planning`, `control`, `localisation`, `fulltask`), `algorithms` (name, optional unique id
  and parameters; every parameter that applies is filled with its default), `scenarios`
  (`sampled` with its own seed, a frozen `suite`, hand-placed `pairs`, or committed Fetch
  `rounds`), an optional `sweep` of one or two parameters, `limits`, `options`, `metrics`
  to show, and `model: {hash_version: 3, experiment: 1}`. A build refuses another `model`.
- The experiment id is the first 16 hex digits of the sha256 of the filled spec's canonical
  JSON (sorted keys, integral floats as ints: `play.canonical`'s rule).
- Runs are ordered sweep point × algorithm × scenario. **A run is a pure function of the spec
  and its index**, computed under state hash version 3 (ADR 0010), so CPython and Pyodide
  agree bit for bit and the worker that runs it does not matter.
- Scenario seeds are 53-bit (`Rng.next_u64() >> 11`), so a JavaScript number carries them
  exactly; every algorithm runs a scenario with the same seed (comparisons hold it fixed).

**Run chain** (`coco.experiment.run.v1`): `sha256(tag ‖ canonical(descriptor) ‖ …)`, where `…`
is, for a search, every search event row packed exactly (`<4q3d3q`) and its counts; for a run in
the Arena, every tick's state hash (v3) and its counts; for a full task, the game's own hash
chain and the scorecard counts. **Digest** (`coco.experiment.digest.v1`): sha256 over every
run's `[index, status, chain, counts]` in index order. Timings (`compute_ms`) never enter a
chain or a digest; they are labelled as wall time on the named device.

**Additive model inputs** (no existing hash changes): `move.<dwa|rpp|mppi>.<field>=` and
`move.window.<field>=` set controller and local-costmap parameters; the subsystem's
`overrides` attribute exists only once one is set (v2/v3 hash every attribute), and with none
the engines are constructed exactly as before. The reference bots take an optional
`planner=`, appending the tick-0 planner input Play sends; `None` is the reference unchanged.

**Statistics** (`coco_lab.exp_stats`, standard library only, deterministic): Wilson 95%
intervals; type-7 quantiles (median, IQR) over the runs where a metric is defined; the Wilcoxon
signed-rank test (zeros dropped, midranks; exact conditional p by integer DP up to 50 non-zero
pairs, normal approximation with tie and continuity corrections above; erfc from fdlibm `exp`),
rank-biserial r and Hodges-Lehmann shift with every p-value; McNemar exact for paired success;
Holm across algorithm pairs; a test that cannot be computed returns its reason, not a number.

## Validation

- `coco_lab/test/test_exp_stats.py` (hand values, brute-force enumeration with ties),
  `test_experiments.py` (validation, determinism, defaults unchanged, the golden experiment
  `fixtures/r1/golden_experiment.json`, never edited, and the CLI).
- `lab_web/tools/r1/parity.mjs`, in CI: the golden experiments in CPython and in Pyodide-in-Node;
  every count, status, chain, digest, results.csv row and summary.json number identical.
- Every v1, v2 and v3 golden passes unchanged.

## Consequences

A future model change that alters a run changes its chain and the experiment's digest: old links
then report DIFFERS, which is the point. Such a change must come with a new `experiment`
version (and, for state, a new hash version), never a silent edit of v1.
