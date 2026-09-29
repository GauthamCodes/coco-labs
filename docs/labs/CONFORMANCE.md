# coco_lab vs Nav2's planners — conformance (Phase 1C)

What `coco_lab`'s declared cost function is, what SmacPlanner2D and NavFn
actually compute in the Nav2 this repository runs, where they are the same
and where they differ, and what was measured on the live stack.

Labels: **FACT** (read from source, with file, lines and hash), **MEASURED**
(a run in this repository, with its JSON), **DERIVED** (computed from
measured values by a stated formula), **HYPOTHESIS**, **UNKNOWN**.

The design was fixed before any measurement in
[`PHASE_1C_PLAN.md`](PHASE_1C_PLAN.md) §D, with two execution amendments
recorded in `docs/SESSION_LOG.md` "1C-3 pre-registration" before the Gazebo
run. `coco_lab` was **not** tuned to match anything.

## 1. The source that was read

Installed: `ros-jazzy-nav2-smac-planner`, `-navfn-planner`, `-costmap-2d`,
`-planner` all **1.3.11-1noble.20260412** (FACT, `dpkg`). Only headers are
installed, so the sources were fetched at upstream tag **`1.3.11`** =
commit `6e0958affab9bc6c2367aa68c3bead164c2bc697` (FACT, `git ls-remote`)
into `~/coco_lab_runs/lab1c/nav2_src_1.3.11/` (outside git).

**Tie to the deployed binary (FACT, measured at 1C-0):** all ten fetched
headers are byte-identical to the installed ones under
`/opt/ros/jazzy/include`, and both fetched `package.xml` files equal the
installed ones. The static smoke test (§4) is the behavioural cross-check.

| file @1.3.11 | lines | SHA-256 |
|---|---|---|
| `nav2_smac_planner/src/node_2d.cpp` | 175 | `7262bea9fb096cba83a5516b575efa04c257ed66f49e5eea927246cf2e317526` |
| `nav2_smac_planner/src/a_star.cpp` | 501 | `5e33a489ff3eb77ff607326d7552798a1155023b7d82b669988b61d786fa9126` |
| `nav2_smac_planner/src/smac_planner_2d.cpp` | 446 | `e1a59440163259b558d3d34b6a12a87df3e07558dec69b8a2521fa60112f4836` |
| `nav2_smac_planner/src/collision_checker.cpp` | 196 | `de383f6e993ffdf1470025618f04ee06e7e18e690a3a5654569faab32713f509` |
| `nav2_smac_planner/src/smoother.cpp` | 513 | `eb971009c1ceebf2f625dea989b4ff48bfb73e2a98b909ee50cbcdff316ba011` |
| `nav2_smac_planner/include/nav2_smac_planner/node_2d.hpp` | 285 | `ce2cb7f4f8cb5d2419667ab0f8e969ec49d04a76680d892cafe305fb938ce64f` |
| `nav2_smac_planner/include/nav2_smac_planner/a_star.hpp` | 284 | `0011c2f0ddea1529362a1117674be3325d07b4022c3af71dee1eeed928f01f18` |
| `nav2_smac_planner/include/nav2_smac_planner/smac_planner_2d.hpp` | 131 | `b2166494271e9d9ce89413891ddf08f59a0afa7ecb129492ba47260dd91c9e94` |
| `nav2_smac_planner/include/nav2_smac_planner/constants.hpp` | 70 | `9f72ad67bd9c44211717f0a28a0349ea027c4e301929e535b503191e4e8a88c8` |
| `nav2_smac_planner/include/nav2_smac_planner/collision_checker.hpp` | 139 | `75bbb37f3364cd53cbc53483b6032552e568d01fcb1baa7176779cfeff5b22ed` |
| `nav2_smac_planner/include/nav2_smac_planner/types.hpp` | 196 | `eb28aeda350c7f1e2621d6f54a6e58588035424094a14a9ae706ceabf5595cee` |
| `nav2_smac_planner/package.xml` | 43 | `eaeb092fb684e393e66c6d0b4903190aa3d7975904648cf67b026c9f41b4b145` |
| `nav2_costmap_2d/src/costmap_2d_publisher.cpp` | 306 | `2e090a228515ecd3795a31e2706be23c682e6d04e270ab4fab7d1952f31eb343` |
| `nav2_costmap_2d/src/costmap_2d.cpp` | 569 | `ce221510cc609a43c1c984f0b0ef93fe5ff4bed006f5622bb314c19c5ad85e83` |
| `nav2_costmap_2d/include/nav2_costmap_2d/cost_values.hpp` | 76 | `65466e2018aa443d8f4949a8a2d69ec44907bfafd0486f4e8b493061f146c9d4` |
| `nav2_costmap_2d/include/nav2_costmap_2d/costmap_2d_publisher.hpp` | 186 | `a35ad5b798eceeca4f797453d12efa611a618b6bf52e7c108416a28b043be315` |
| `nav2_navfn_planner/src/navfn.cpp` | 1039 | `f3dcf705a6c180ec856ddfe77e4ffb8a1b172eb4169e5532db57c976dc571599` |
| `nav2_navfn_planner/src/navfn_planner.cpp` | 555 | `aac6f5f1be9098e707855d0fbe29e55ff7df057ddfe25cda63e47a61a959b208` |
| `nav2_navfn_planner/include/nav2_navfn_planner/navfn.hpp` | 290 | `9e0c0d6c18f869f93c87161cf87a23de8291433430d0e4b160ee75013f0dfc3a` |
| `nav2_navfn_planner/include/nav2_navfn_planner/navfn_planner.hpp` | 239 | `cdae8e8dbf4f1030cafc67b7d58e8f4da1a86cfb48138021c242ada087d11838` |
| `nav2_navfn_planner/package.xml` | 37 | `55cf9bbb4f9e78de57161d253cb704d041dc7ee59e6b3e6564c80b673f080752` |
| `nav2_planner/src/planner_server.cpp` | 774 | `82d49ac45f478ff8c12faef8f86a5c3ee5f86244a967762bf413b02c28a90b12` |

`nav2_smac_planner/utils.hpp` (`getWorldCoords`) was read from the
INSTALLED header, `/opt/ros/jazzy/include/nav2_smac_planner/utils.hpp`.

## 2. The deployed configuration (FACT)

`gazebo_models/config/nav2_params.yaml` (SHA-256 `06c308af…`, unchanged
since Phase 1B's `e06dc94`) plus the lab-only overlay
`coco_lab_ros/config/nav2_lab_overlay.yaml`, which adds only `NavFnAStar`
(NavFn's block with `use_astar: true`); a test proves the merged file
differs from the mission's in exactly those keys, and the runner read 67
live planner_server/global_costmap parameters back per session.

- `GridBased`: `nav2_smac_planner::SmacPlanner2D`, `tolerance 0.25`,
  `allow_unknown false`, `max_iterations 1000000`,
  `max_on_approach_iterations 1000`, `max_planning_time 2.0`,
  `cost_travel_multiplier 2.0`, `use_final_approach_orientation false`,
  `downsample_costmap false`; no smoother block, so smoother defaults.
- `NavFn`: `tolerance 0.5`, `use_astar false`, `allow_unknown false`.
  `NavFnAStar`: the same with `use_astar true`.
- Global costmap: 0.05 m, `track_unknown_space true`, layers static,
  obstacle (scan), voxel (scan), inflation (radius 0.5, csf 5.0),
  `robot_radius 0.20`.

## 3. The traversal-cost models, side by side

`coco_lab`'s declared cost (`coco_lab/coco_lab/grid.py`, Phase 1A):
`edge_cost(a → b) = base(move) · (1 + cost_weight · cost[b] / cost_scale)`,
defaults 2.0 and 252. Two configurations were pre-registered (plan §D):
**C0** = coco_lab's default (corner cutting OFF) and **C1** = C0 with corner
cutting ON.

| # | coco_lab | SmacPlanner2D @1.3.11 | relation | label |
|---|---|---|---|---|
| 1 | `base · (1 + 2.0 · c[b] / 252)` | `len · (1 + ctm · c[child] / 252)`, `ctm = cost_travel_multiplier = 2.0` (`node_2d.cpp:68-84`; `smac_planner_2d.cpp:73-75`; `node_2d.cpp:109`) | same form, same constants; Smac in float32, coco_lab in float64 | FACT |
| 2 | diagonal √2 | √2 when `dx² + dy² > 1.05` (`node_2d.cpp:75-80`) | same | FACT |
| 3 | 8-connected | 8 offsets, always (`node_2d.cpp:110-111`) | same | FACT |
| 4 | corner cutting OFF (C0) / ON (C1) | no corner check: only the neighbour cell is tested (`node_2d.cpp:138-152`) | C0 differs, declared; C1 matches | FACT |
| 5 | raw ≥ 253 blocked; 255 unknown, blocked | `inCollision(index)`: `cost >= INSCRIBED (253)`; UNKNOWN blocked unless `traverse_unknown` (`collision_checker.cpp:172-183`) | same after the adapter's mapping (tested) | FACT |
| 6 | heuristic `euclidean`, cells | `hypot(dx, dy)` in cells (`node_2d.cpp:86-95`), but to the goal's CONTINUOUS map coordinates (`a_star.cpp:425-437`, `smac_planner_2d.cpp:237-247`), so h(goal cell) ≤ √2/2, not 0. Still consistent (1-Lipschitz), so a popped goal is optimal | differs in the constant, not in optimality | FACT |
| 7 | goal test on expansion; closed never reopened; strict `<` relax | goal test after pop; `wasVisited` skip; `g < g_old` relax (`a_star.cpp:320-378`) | same semantics | FACT |
| 8 | tie-break `low_h` | priority queue on f only (`a_star.hpp:64-72`); ties in heap order | not matchable: compare costs, never cell sequences | FACT |
| 9 | exact goal cell | once the best pushed h < `tolerance / resolution` (5 cells), counts approach iterations and after `max_on_approach_iterations` (1000) returns the best-h node's CURRENT parent chain (`a_star.cpp:350-355`, `:381-384`) | differs: Smac may end off the goal, or on it before the goal is final | FACT |
| 10 | start/goal cell = Nav2's own conversion | `worldToMapContinuous` (`costmap_2d.cpp:300-313`, float32 cast) then `static_cast<unsigned>` (`a_star.cpp:137-151, 191-207`) | the adapter emulates the float32 step (tested at a boundary) | FACT |
| 11 | the start must be free | the start is never collision-checked (`a_star.cpp:256-257`) | differs; the sweep draws free starts only | FACT |
| 12 | poses at cell CENTRES (the path handed to FollowPath) | poses at `origin + mx · res` with integer `mx` (`utils.hpp:44-53`): cell CORNERS, half a cell toward −x, −y | differs by a constant 0.025 m offset | FACT; measured live (§4) |
| 13 | raw cell path | the returned path is SMOOTHED; the smoother is constructed and called on every non-trivial plan with no parameter to skip it (`smac_planner_2d.cpp:131-136, 323`); the raw A\* path is published on `unsmoothed_plan` only while that topic has a subscriber (`:146, :307-310`) | raw ↔ raw is the conformance comparison; smoothed is separate | FACT |

**Nav2 1.3.11 does not provide a smoothing-disable configuration in the
deployed SmacPlanner2D setup (row 13). This experiment therefore uses the
planner's own published `unsmoothed_plan` — its pre-smoothing A\* path —
where available. It is not a run with smoothing disabled** (owner decision
D-3).

**The costmap snapshot is `/global_costmap/costmap_raw`** (owner decision
D-2): `costmap_2d_publisher.cpp:91-103` translates the OccupancyGrid topic
`/global_costmap/costmap` 0 → 0, 1..252 → `1 + 97(i−1)/251`, 253 → 99,
254 → 100, 255 → −1, which folds 252 raw values onto 98. `costmap_raw`
carries the uint8 master costs, `KeepLast(1).transient_local().reliable()`
(`:70-82`); its origin is `mapToWorld(0,0) − res/2` (`:178-181`), i.e.
Nav2's origin up to one rounding.

**NavFn** is a different cost model, compared by L and I only:
- cost per cell `COST_NEUTRAL + COST_FACTOR · c = 50 + 0.8 c` for
  `c < 253`, capped at 253; 253/254 → 254 (obstacle); 255 → 254 unless
  `allow_unknown` (`navfn.hpp:52-67`, `navfn.cpp:250-271`);
- the path comes from gradient descent over a propagated potential, not
  from a parent chain; its propagation was not source-read here beyond
  the entry points (UNKNOWN in detail);
- **it writes into the costmap it plans on**: `NavfnPlanner::makePlan`
  calls `clearRobotCell(mx, my)`, which sets the START cell of every
  request to FREE_SPACE in the global costmap that planner_server shares
  with Smac (`navfn_planner.cpp:241-242, 519-524`). Measured at 1C-2 on
  the static stack: the costmap hash changed after every NavFn request
  and never after Smac's. The write persists until something rewrites
  that cell.

## 4. The static smoke test (MEASURED, real binaries, no simulator)

`coco_lab_ros/test/test_static_smoke.py`: map_server + planner_server on
the lab-merged parameters over a committed 80 × 60 map. It asserts the
pipeline and two source facts, and it does not presume the hypothesis.

- All three planner ids answer `ComputePathToPose`; `/unsmoothed_plan` is
  the live topic name and is published for GridBased only.
- Smac's raw poses sit on cell corners: largest residual **1.0e-6 cells**
  (float32).
- Smac's raw path is 8-connected over free C1 cells, and
  E(Smac raw) ≥ E\*(C1) — a theorem when the graphs are the same.
- On that map E(Smac raw) = **101.76678228093724** and E\*(C1) =
  **101.7667822809372** (relative gap 2.8e-16). One smoke pair, not the
  experiment.

## 5. The live sweep

Filled in from `docs/data/lab1c/conformance.json` after the run — see
`docs/RESULTS.md` "COCO Lab Phase 1C" until then.
