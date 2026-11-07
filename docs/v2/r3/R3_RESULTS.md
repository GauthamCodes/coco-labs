# R3 · COCO-Bench v1 and the paper — results (draft: sections fill in as evidence lands)

Prompt: [`R3_PROMPT.md`](R3_PROMPT.md). Progress: [`R3_STATUS.md`](R3_STATUS.md), [`LANDING_STATUS.md`](LANDING_STATUS.md).
Branch `v2/r3-bench-paper`. Evidence classes as in AGENTS.md: **MODEL** (COCO Lab's Python reference, natively
or in the browser), **STACK** (full ROS 2 in Gazebo; simulation, never hardware), TESTED, MEASURED, INFERENCE,
UNRESOLVED.

## Part A · landing R2 — done 2026-11-07

| step | result | evidence |
| --- | --- | --- |
| Gautham's answers | D\* Lite byte-identical through the API (no tolerance); Studio view first on phone landscape; decisions recorded | [R2_RESULTS](../r2/R2_RESULTS.md) |
| CI hardening | ROS setup retried after recovery; exercised for real on PR #32's head | [LANDING_STATUS](LANDING_STATUS.md) |
| merges | #32 (R2) `5df4427`; #33, #34, #35 (three leaderboard CI gaps found landing #31); #31 (Gautham's Lazy Theta\*) `adde736` | self-reviews on each PR |
| deploy | run 42356268133; live smoke PASS; an open tab showed "New version ready" without a reload | [data/deploy1](data/deploy1/README.md) |
| Theta\* 0/5 (answer 2) | STACK re-run: 0/5 again; 29–77 % of received plans had a pose at cost ≥ 253 in the local costmap vs 0–10 % for stock Nav2 (3/5) and the A\* starter (4/5): **supported** (the controller's own decision remains INFERENCE) | [data/a1](data/a1/README.md) |
| stock vs snapped Nav2 (answer 3) | STACK, 3 × 20: stock 42/60, **snapped 60/60**, A\* starter 60/60; s086's goal 7.38 m from free space in Gazebo's costmap: UNRESOLVED | [data/a1](data/a1/README.md) |
| real phone | not connected: pending | |

## B1 · COCO-Bench v1 — MODEL / TESTED

12 frozen suites, 450 scenarios ([datasheets](../../bench/v1/README.md)): planning `arena-nav-50`, `depot-nav-100`,
`depot-narrow-30` (v0 scenarios exactly), `depot-long-50`, `depot-clutter-50` (the cluttered Depot: 24 kit pallets,
real in the browser and in Gazebo); control `ctrl-corridor-30`, `ctrl-corners-30`, `ctrl-dynamic-30` (15 pairs ×
{actors yield, actors keep schedule}: scenario rules); localisation `loc-track-30`, `loc-global-20`, `loc-kidnap-20`;
full task `task-fetch-10` (not 12: the committed rounds are 6 phone + 4 colour; none invented). Tiers from the reference
plan's features (path length, narrowest clearance, bends, zones, actor exposure, kidnap distance); thirds by mean
percentile rank. `make_suites_v1.py --check` regenerates all 12 byte for byte; `test_bench_v1.py`, `test_r3_datasheets.py`.

**Held-out (ADR 0014, accepted):** HMAC(secret, suite | PR head) in the trusted workflow, outside the sandbox; the
container gets only the scenario file; only rounded aggregates leave. Hostile tests in the real container: the secret
found nowhere, no network, leaks not published; the stated residual (one rounded number per metric per push, describing
a set never reused) reproduced. [data/heldout](data/heldout/README.md). The repository secret is set when the workflow
reaches main.

## B2 · Baselines and the gap — pending

- MODEL baselines (`tools/r3/make_baselines.py`, `docs/v2/r3/bench/`): running. Carried suites reproduce R1's v0
  references run for run so far: arena-nav-50 planning 300/300, control 200/200, localisation 150/150; depot-nav-100
  planning 600/600, control 400/400.
- STACK baselines (`tools/r3/ros2_queue_r34.sh`): after the MODEL baselines.
- Gap analysis (`tools/r3/gap.py`, the Workbench "Model vs ROS 2" tab): after the STACK baselines.

## B3 · Leaderboard v1 — in progress

Verifier 2 judges on COCO-Bench v1 (every suite and family; held-out from the suite's own generator); entries carry
success per tier; a Submit guide on the Leaderboard tab; CONTRIBUTING's boards checked against the verifier. Theta\*
re-verified locally on v1: VERIFIED (public 100/100, path ratio 0.978; v1 held-out 20/20); its v1 claim goes in a small
PR after R3 merges. R2's v0 results archived unchanged in `docs/v2/r2/data/r26/results_v0/`. Built-in entries from the
baselines (`leaderboard.py builtin-bench`): after B2.

## B4 · The paper — draft

`docs/paper/`: sections, a checked bibliography (18 entries, each with the record that verified it), 57 macros from
committed data (no typed number: `lint_tex.py`), a generated suite table and tier figure, `make check` in CI, the PDF built
in CI (no TeX here), "Reproduce this paper" (one link, the depot-nav-100 planning baseline spec and its digest), venues
with dates and sources ([VENUES](../../paper/VENUES.md)). Author "Gautham", no affiliation (Gautham, 2026-11-07).

## B5 · Launch kit — drafts

`docs/launch/`: 90-second demo script, LinkedIn post (long and short), résumé bullets with evidence, an architecture
SVG; CITATION.cff and About → Cite; the README front page. Nothing published.
