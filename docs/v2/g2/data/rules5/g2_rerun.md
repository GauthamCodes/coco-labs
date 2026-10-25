# Rules 5 on `v2/g2-sim-identity`: the re-run (2026-10-25)

Rules 5 was built on `v2/g2-actor-yield` (from `c695cd5`) and carried onto `v2/g2-sim-identity`,
where Fetch by colour already existed and now adopts rules 5's actors (its rules 2). Everything
below was re-run on the g2 tree (`62b66e0` + the Rules 5 changes), CPython 3.12.3, laptop
(balanced, AC). Evidence class **MODEL**. Logs in [`g2_rerun/`](g2_rerun/).

| Check | Result | Log |
|---|---|---|
| Fetch Rush references replay to their committed card and hash chain (`tools/g2/replay_references.py`) | rules 2: 4 identical (2 rounds have no reference, as before); rules 3: 12/12; rules 4: 12/12; rules 5: 12/12; 0 different | `r2.log` … `r5.log` |
| Fetch by colour rules 2 rounds regenerate byte-identical (`tools/g2/make_fetch_colour_rounds.py --check`) | `coco_depot_colours_v1.fetch_colour.r2.json current` | `colour_check.log` |
| v3 goldens (`tools/g1/make_v3_goldens.py --check`) | `numerics_vectors.json`, `state_hash_v3.json` identical | `v3_goldens_check.log` |
| Game references, rules 1 and Rush Hour (`tools/m6/make_game_references.py --check`) | all reproduce | `game_references_check.log` |
| Focused tests: `test_fetch_colour.py` (both rules' references replay), `test_fetch_rush_r5.py`, `test_g2_fetch_colour_glue.py` | 53 passed | — |
| vitest `g2_fetch_colour`, `g2_planners` | 8 passed | — |

Fetch by colour rules 2 against rules 1: the same rounds (start, orders, routes, timers
83.6–102.2 s) and every reference scorecard identical apart from `rules` (55.7–68.1 s, 0 contacts):
on these routes the actors never meet COCO. Rules 1's rounds file is unchanged, so rules-1
records keep replaying.

## Browser (built `dist`, headless Chromium, RTX 4050 / ANGLE OpenGL ES 3.2)

| Check | Result | Files |
|---|---|---|
| Forklift check, Fetch Rush Full shift seed 2 (`lab_web/tools/g2/forklift_check.mjs`) | 1235 ticks, **0 overlap ticks**, 0 blocked, min clearance 0.105 m, an actor held for COCO 385 ticks, legs A, B, C arrived, no page error (actor-yield build: 1233 / 0 / 0 / 0.105 m / 380; rules 4: 114 overlap ticks) | `forklift/` |
| Four colours (`lab_web/tools/g2/fetch_colour_check.mjs`, desktop 1440 × 900) | red 72.8 s, green 66.0 s, blue 64.6 s, yellow 60.6 s: each delivered its own rod, 0 contacts, ★★, planner links ok, no page error | `colour_browser/desktop-check.json` |
| Those four browser records (rules 2) replayed in CPython | 4 of 4 identical hash chain and scorecard | `colour_browser/cpython_replay.json` |

## Suites (`tools/g2/suites.sh`, [`g2_rerun/suites.txt`](g2_rerun/suites.txt))

coco_lab (CI venv route) 1158 passed; gz 2; `pytest lab_web/tools` 244; catalog, schemas, typecheck,
arena-assets; vitest 604; native gate exact (818,951 planner and 1,436 Fetch Rush comparisons);
coco verify 18 of 18; build twice identical; v1 site fetched; determinism v1 (1500 steps) and terrain
(2100) identical in Chromium, Firefox, WebKit and Pyodide; screenshots; chase HUD 0 failures;
saved view; v1 links; replays; ROS packages 11 of 12 passed.

Two failures, both handled:
- `coco_lab`'s ament flake8 (colcon route only): two lines over 99 characters added by Rules 5
  (`games.py`, `test/test_fetch_colour.py`). Wrapped; flake8, pep257 and copyright then 3 passed.
- `update_isolation` timed out on `page.reload` (90 s) while the forklift and colour checks shared
  the laptop; run alone it passed all 9 checks.

The suite run began at 06:40 UTC. The laptop was suspended part of that time, and the run was paused
(SIGSTOP) while another agent's Gazebo simulation ran, per the one-simulator rule. The wall times in
`suites.txt` include both.
