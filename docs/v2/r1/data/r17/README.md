# R1.7 Compare and navigation

Evidence class: MODEL / TESTED. Screenshots are regression references; Gautham judges the look.

## Compare

- **Every world**: `?world=v1|v2|depot|depot_colours` (Proving Ground, its terrain version, the Depot, the Depot
  with colour rods).
- **Scenario picker** (`compare/experiment_mode.ts`): the robot's start and a clicked goal (Compare's live mode,
  unchanged), a seeded random pair (seed, Previous/Next), a benchmark-suite pair (suite, Previous/Next through
  its scenarios, panes in sync), or a hand-placed pair. A chosen scenario makes Compare's panes an experiment
  spec and each pane **replays that experiment run** (`arena_glue.experiment_replay`, the search events streamed
  as Compare's plan batches; the Arena runs' ticks as frames), so a pane's numbers are the Workbench's.
- **From the results table**: a run's link (`?view=compare&world=…&xrun=i[&t=fail_tick]#xexp=<spec>`, decoded
  through the bounded decoder) opens that run with the other runs of its scenario beside it, at the failing tick
  for a failed loop run.
- **"Turn this into an experiment"** opens the Workbench builder with the panes' algorithms and parameters over
  20 seeded pairs (or the suite / the hand-placed pair).

[`compare_check.json`](compare_check.json) (`lab_web/tools/r1/compare_check.mjs`, Chromium) — **all pass**:

| Check | Result |
| --- | --- |
| depot-nav-100 pair s001, A* and Dijkstra | expansions 3,035 / 43,585 and path 19.64 m = the committed reference results |
| Next → s002 | 64,447 / 110,839, 48.63 m = reference |
| a table link (Dijkstra on s003) | opens that run first; 71,834 expansions = reference |
| each of the four worlds | opens and compares, no page error |
| control, a seeded pair on the Proving Ground | both panes replay to an outcome (succeeded, succeeded) |
| Turn this into an experiment | the builder opens with family control, DWA + RPP, 20 seeded pairs |

## Navigation, title, Learn

- Top bar: **Play · Learn · Compare · Workbench** (Gautham, 2026-10-31); `?view=research` (the library) is the
  Workbench's Recordings tab, unchanged, with the Workbench tabs above it; old links keep their homes
  (`test/r1_routes.test.ts`, `test/landing.test.ts`).
- Title: three equal doors **Play · Learn · Workbench**; any key still plays; a quiet "Compare algorithms side by
  side" link below.
- **Learn page** (`?view=learn`; `&mission=…` still opens its tour): the seven missions as cards, each with
  its tour and a pre-made experiment (e.g. "Is A* always faster than Dijkstra? Run it on 50 scenarios" →
  arena-nav-50); missions whose subject is not yet an experiment family (mapping, search) ask a related
  question and say so. The graded course is R4.
- The M5 tools that named the old modes (`tools/perf/modes_check.mjs`, `m5_review.mjs`) expect the new ones.

Screenshots ([`screens/`](screens/)): title, Learn, Compare and Recordings at 1440 × 900 and on the emulated
Nothing Phone (1) in landscape and portrait (RTX 4050). Learn audit: [`a11y/a11y.json`](a11y/a11y.json) passes.
vitest: 631 tests, 83 files.
