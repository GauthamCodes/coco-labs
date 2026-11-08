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

## B2 · Baselines and the gap

**MODEL baselines — done** ([`bench/`](bench/README.md), 19 suite/family sets, every built-in, public + a held-out
reference draw, all runs with hash chains; generated tables in the paper). Carried suites reproduce R1's v0 references
run for run: arena-nav-50 planning/control/localisation 300/200/150, depot-nav-100 planning/control 600/400,
depot-narrow-30 planning/control 180/120 — **2,350 of 2,350 identical**. The laptop rebooted once
(2026-11-08 ~00:42); the set in progress re-ran from its start.

| family | what the baselines show (MODEL) | evidence |
| --- | --- | --- |
| planning (5 suites) | every built-in planner reaches every goal, public and held-out (30 of 30 rows full): success does not separate them; path ratio and expansions do. Cost-aware A*/Dijkstra/D* Lite return longer paths than BFS | `bench/*/planning/`, paper Table "baselines, planning" |
| control (7 suites) | the Waypoint driver (the model's plan follower: no local costmap, no collision check, no Nav2 failure outcomes) is a **plan reference**, not a controller result; among DWA/RPP/MPPI, MPPI is the most reliable and slowest, RPP the fastest and least reliable (e.g. ctrl-corridor-30: MPPI 29/30, DWA 18/30, RPP 9/30) | `bench/*/control/` |
| control, moving actors | ctrl-dynamic-30: the Waypoint driver wins 15/15 with scheduled actors (10 of them with contact) but 9/15 with yielding actors (6 timeouts; a mutual wait — INFERENCE, not traced); DWA/RPP/MPPI nearly insensitive to the rule. The Leaderboard now shows **Contacts** beside success | `bench/ctrl-dynamic-30/`, `a9e0bb9` |
| localisation (5 suites) | EKF most reliable on tracking (depot-nav-100 92/100, loc-track-30 28/30); MCL fails far more on hard tiers; MCL + injection is worse than MCL on depot-nav-100 (34 vs 50 /100) and loc-track-30 (15 vs 23 /30), slightly better on arena-nav-50 (28 vs 25 /50), at 60 particles | `bench/*/localisation/` |
| localisation, negative | **loc-global-20: 0/40** (no MCL variant converged; EKF cannot start) and **loc-kidnap-20: 0/60** (no recovery, augmented MCL included) at the teaching profile. Kept as negative baselines; larger particle sets UNRESOLVED (question for Gautham) | `0df82ee`, `247315e` |
| full task | task-fetch-10: 50/50 rounds completed by the five fetch planners, 0 contacts | `bench/task-fetch-10/` |

**STACK baselines (Gazebo + Nav2)** — `tools/r3/ros2_queue_r34.sh`, started 2026-11-08 20:01. Time budget (the laptop
until 2026-11-09 ~14:00): repeat 1 of everything, planning repeats 2–3 (`tools/r3/ros2_queue_r34_plan.sh`).
**Control and localisation have n = 1 repeat: the prompt's "× 3 repeats" is NOT MET for them.** Results and the gap
analysis: below, once the sessions are committed.

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
