# COCO-Bench v1 baselines (MODEL)

Every built-in on every v1 suite, public scenarios and a held-out reference draw, made by
[`tools/r3/make_baselines.py`](../../../../tools/r3/make_baselines.py) (its docstring states the profiles).
Evidence class **MODEL**: COCO Lab's Python reference, run natively (CPython 3.12); the same runs
reproduce in the browser (hash chains, `chain` in every run).

Layout: `<suite>/<family>/{public,held_out}/` is the export set of `coco experiment run`
(`spec.json`, `runs.jsonl`, `results.csv`, `summary.json`, `manifest.json`); `tiers.json` gives
success (Wilson 95 %) and metric medians per tier and algorithm; `DONE` marks a finished set.
A set is committed only when finished. Re-run one: `coco experiment run <set>/spec.json` and
compare the summary digest.

Carried suites (v0 scenarios) were checked run for run against R1's v0 references with
[`tools/r3/check_carried.py`](../../../../tools/r3/check_carried.py): identical chains and metrics.

Held-out here is a *reference* draw from a public seed (`leaderboard.held_out_seed(suite,
'reference-v1')`), not an ADR 0014 secret set; submissions' held-out sets come from the secret.

Interruptions: the laptop rebooted on 2026-11-08 during depot-nav-100/localisation; that set was
re-run from the start (see [R3_STATUS](../R3_STATUS.md)).
