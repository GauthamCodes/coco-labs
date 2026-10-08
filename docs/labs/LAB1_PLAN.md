# Lab 1 — Plan

> **Correction (2026-10-08, COCO Lab v2 · M0.6).** Where this document says "real robot" or "the real robot", it means **the full ROS 2 stack (simulated)** in Gazebo. No physical robot exists, and nothing here ran on hardware (README §2, corrections 1 and 3). The text below is kept as written.

**Try it:** <https://gauthamcodes.github.io/coco-labs/> · the
exhibit: <https://gauthamcodes.github.io/coco-labs/?view=exhibit>

COCO Lab's first lab teaches graph search for robot path planning, in the
browser, on the same maps and the same Nav2 stack a real robot used. This
document is the lab's write-up:
- what it teaches;
- how each claim it makes is backed;
- every measured number, with how to reproduce it;
- what is not verified;
- its known limitations.

Plan: [`docs/ROADMAP.md`](../ROADMAP.md) §5. History:
[`docs/SESSION_LOG.md`](../SESSION_LOG.md). Every measured number is in
[`docs/RESULTS.md`](../RESULTS.md), in the section named beside it.

## 1. What the lab teaches

1. **Search is an order of expansion.**
   - Five algorithms run on one grid, traced event by event: BFS, Dijkstra,
     A\*, greedy best-first and weighted A\*.
   - You play, scrub and hover the trace (g, h and f as stored).
2. **A heuristic changes the work, not the answer — when it is
   admissible.**
   - The heuristic picker shows coco_lab's verdict (admissible and
     consistent, or not, with the move that breaks it).
   - The guarantee line shows the suboptimality bound for the chosen
     algorithm and weight.
3. **Weighted A\* trades optimality for speed, by a known bound.** The
   weight slider (0–5) shows "cost ≤ w × the optimum" for an admissible
   heuristic. w = 0 is Dijkstra and w = 1 is A\*, event for event.
4. **Greedy best-first can be fast and wrong; BFS counts moves, not cost.**
   Race mode puts two to four algorithms side by side on identical inputs,
   advanced together by expansions, and ends with a table: expansions, cost,
   length, gap to optimal.
5. **Real maps are harder than teaching grids.** The map ladder runs:
   - a 20 × 20 teaching grid;
   - the arena's occupancy map;
   - Nav2's own inflated costmap, from a real run, with COCO's footprint
     swept along the path.
6. **What the robot did with a plan.** Three recorded real runs, each
   planned once by coco_lab and driven by Nav2's `FollowPath`:
   - ground truth, AMCL belief and the published plan, overlaid;
   - a tracking-error plot;
   - full provenance.
7. **"The A\* myth, twice."** Two results once read as "A\* gives different
   paths than Dijkstra", examined: COCO's own 6.2 %, and an internship
   simulator's "4 %".

**Learning by doing.**
- You predict before you run (which expands fewest; does the cost go up),
  and the reveal shows the measured answer.
- You paint walls and erase them.
- You share a link that reproduces your exact trace.

The page never searches.
- Every search runs in `coco_lab` (Python): at site build time, or in your
  browser through Pyodide.
- Every verdict on screen is coco_lab's.
- A test (`lab_web/tools/test_tools.py::test_lab_web_src_has_no_search_implementation`)
  fails if the browser code ever contains a search.

## 2. Modes, as labelled on screen

| label | what it is |
|---|---|
| **Replay — coco_lab computation (glass-box)** | a trace coco_lab computed when the site was built; every input recorded, replay checked event for event |
| **Replay — recorded real run** | a run of the real stack, recorded; shown as it happened, never edited |
| **Replay — computed in your browser by coco_lab** | your edit, settings, race or share link, recomputed by coco_lab under Pyodide |

Sketch (a browser robot model) arrives in Phase 3, and Live (the real
robot) in Phase 2. Neither is in Lab 1.

## 3. Claims and their evidence

Every claim the page shows names its evidence. `test_every_cited_test_exists`
fails if a cited test does not exist.

| claim | backed by | kind |
|---|---|---|
| With an admissible heuristic, A\* returns Dijkstra's cost | `coco_lab/test/test_properties.py::test_astar_cost_equals_dijkstra_with_admissible_heuristic`, 1,000 random maps, against networkx | property |
| A heuristic that overestimates can make A\* suboptimal | `coco_lab/test/test_heuristics.py::test_an_inadmissible_heuristic_makes_astar_suboptimal` | test |
| The admissibility badge is exact | `coco_lab/coco_lab/heuristics.py::analyse` (proof in its docstring); `test_heuristics.py` | proof + tests |
| The guarantee line holds (cost ≤ B × optimum) | `test_properties.py::test_the_reported_suboptimality_bound_holds`, every algorithm and heuristic, 1,000 maps; `coco_lab/test/test_bound.py` | property |
| w = 0 is Dijkstra, w = 1 is A\*, event for event | `test_weight_zero_reproduces_dijkstra`, `test_weight_one_reproduces_astar` | property |
| Greedy can return a costlier path, never a cheaper one | `test_properties.py::test_greedy_cost_is_never_below_optimal` (1,000 maps) and `::test_greedy_is_strictly_worse_on_the_committed_counterexample` (cost 7 against 5) | property + example |
| Smac's raw A\* cost equals coco_lab's optimum on the real costmap | RESULTS "COCO Lab Phase 1C" → "Conformance…": **36 / 36** pairs | measured, 2026-09-29 |
| M3's 6.2 % was planner implementation, not A\* vs Dijkstra; it is **neither reproduced nor refuted** | RESULTS "COCO Lab Phase 1C" → "NavFn and M3 (the 6.2 %)"; README "What the 6.2 % is" | recorded |
| The ISRO "4 %" is 3.5 % in smoothed waypoints, and **not reproduced** on fixed inputs | `docs/labs/ISRO_INVESTIGATION.md` §5–6 (a **reconstruction**) | measured, 2026-09-29 |
| A share link reproduces its exact trace | `lab_web/test/share.test.ts`; `lab_web/tools/test_glue.py::test_share_vectors_reproduce_their_trace_digests` | tests, both languages |
| The tracking-error plot is 1C's series | `lab_web/tools/build_catalog.py::tracking_series` refuses to build unless it reproduces the recorded statistics; `coco_lab_ros/test/test_run_analysis.py::test_tracking_error` | build check + test |
| The footprint is COCO's | `build_catalog.py::robot_footprint`, from `coco_config/robot.py` | **derived** (0.297 × 0.314 m; coco_config has no footprint constant) |

## 4. Measured numbers, and how to reproduce them

"This session" is 2026-10-01 (Lab 1.1). Earlier rows give the phase and the
date they were measured; they were not re-measured.

### Tests (this session; 0 failed, 0 skipped)

| suite | count | reproduce |
|---|---|---|
| `coco_lab` (plain venv / colcon) | 349 / 352 | `cd coco_lab && python3 -P -m pytest` (RESULTS "Phase 1A" → "Reproduce") |
| `coco_lab_ros` | 69 | `scripts/build_overlay.sh` then `cd coco_lab_ros && python3 -P -m pytest` |
| `lab_web/tools` | 72 | `python3 -P -m pytest lab_web/tools` (coco_lab importable) |
| vitest | 180 | `cd lab_web && npm ci && python3 tools/build_catalog.py && npm test` |
| two builds identical | yes | `npm run build && node tools/check_dist.mjs` (twice; `lab.yml` does this) |

### The site (headless Firefox 156; this session; RESULTS "COCO Lab 1.1, Part B")

| measure | target | local | public site, `coco-labs` |
|---|---|---|---|
| full-arena Dijkstra playback (283,378 events) | ≥ 60 fps | 60.01 fps | 59.95 fps, 0 frames > 25 ms (the 60 Hz cap) |
| paint one cell → first frame, warm, 0.10 m arena | ≤ 1.5 s | 1,134–1,145 ms | 1,170–1,195 ms |
| share link → "reproduced the exact trace" | works | 3 of 3, 3.6–3.8 s | 3 of 3, 5.9–6.2 s |
| phone 390 × 844, horizontal scroll | none | `scrollWidth` 378 | 378 |
| initial page weight (Pyodide excluded) | report | 115,555 B | — |
| a real phone (owner-reported) | works | — | Nothing Phone (1), Chrome: page loaded, trace played, a share link reproduced the exact trace |

The `coco-labs` column was measured on 2026-10-01 at
<https://gauthamcodes.github.io/coco-labs/>, built from `3206f1e`
(`docs/data/lab11/part_c/browser_report_coco_labs.json`). Before the move,
the same site measured 60.03 fps, 1,137–1,159 ms and 4.7–5.7 s at
`/coco-robot-jazzy-2.0/` (RESULTS "COCO Lab 1.1, Part B").

Reproduce:

```bash
python3 lab_web/tools/browser/check.py https://gauthamcodes.github.io/coco-labs/ out/
```

This runs eleven scenarios. Timings depend on the machine's load, so record
`_meta.loadavg` with them.

### The real stack (Phase 1C, measured 2026-09-29; needs a live simulator)

| measure | value | where |
|---|---|---|
| Smac raw A\* cost = coco_lab C1 optimum | 36 / 36 pairs (max relative gap 1.08e-15) | RESULTS "COCO Lab Phase 1C" |
| three real runs, A\* / Dijkstra / greedy | succeeded / succeeded / aborted (`FAILED_TO_MAKE_PROGRESS`) | same |
| expansions, A\* / Dijkstra / greedy | 7,100 / 33,374 / 1,251 | same |
| tracking error (mean), A\* / Dijkstra / greedy | 0.072 / 0.064 / 0.052 m | same; plotted on the site |
| present-day analogue: Smac returned / NavFn / C1 optimum | 7.785 / 7.894 / 8.002 m | same, "NavFn and M3" |

Reproduce: `docs/data/lab1c/README.md` (`lab1c_run.sh conformance` and
`lab1c_run.sh run …`, each on a fresh simulator).

### The ISRO investigation (Phase 1B, measured 2026-09-29; no ROS)

| measure | value |
|---|---|
| Steps ratio A\* / Dijkstra on fixed inputs (long / short) | 0.9993 / 0.9966 |
| historical A\* vs Dijkstra cost differs | 148 / 1,198 maps, 82 one way, 66 the other |
| with heading in the state | 0 / 1,198 |

Reproduce: `python3 docs/data/lab1b/isro_experiment.py` (output
`isro_experiment.json`, determinism hash `c97ad0fc…`).

## 5. Not verified

- **A headed desktop browser, Safari, and phones other than one.** Every
  measured browser number is headless Firefox 156 on the development
  machine. One real phone was checked by the owner (a Nothing Phone (1),
  Chrome: the page loaded, the trace played, a share link reproduced the
  exact trace; recorded in `docs/SESSION_LOG.md`); that check reports what
  worked, not timings.
- **M3's 6.2 % itself**, never re-run (its goal no longer exists).
- **The 1C analogue's paths**, whose coordinates were not recorded; the
  exhibit shows their lengths only.
- **Race timing on the 0.10 m arena.**

## 6. Known limitations

- **Three real runs are not a rate.** Greedy's abort is one run.
- **The warm-edit budget:** the margin is about 350 ms locally and on the
  public site at low load. Under heavy load (load average ~30) it was
  missed at the Phase 1 closure, before Part A's cache.
- **The first change pays Pyodide's start-up**, 3–95 s in this lab's
  measurements, set by the CDN download.
- **Settings and races apply to grid maps.** The heading-graph exhibit
  keeps its recorded settings, and recorded runs are read-only.
- **The footprint is a derived rectangle**, not a measured outline. Nav2's
  own costmaps use a circle (`robot_radius`).
- **Share links have no seed**, because no Lab 1 input is random. A link
  names a catalog bundle, so it is only valid while that bundle is served.
- **Deferred to Lab 1.2:** the break-the-planner challenge, beat-the-planner,
  stars and the daily seed (ROADMAP §5).
