# M6F.4 — Depot planning at 0.1 m (measured on the laptop, G1.13, 2026-10-23)

`tools/m6/bench_planning.py --spec worlds/coco_depot_v1.yaml --repeats 5` (CPython 3.12.3, the
CI-style venv) and `tools/m6/bench_planning_pyodide.mjs --pyodide lab_web/node_modules/pyodide
--repeats 5` (Pyodide 314.0.7 in Node 24.21.0), the same spec JSON (sha256
`ae285a7a3a148ef86307986d198a93182f2ff2d376b49d926e7a6fcb56f1245a`, written by the first). One run
after the other on a quiet laptop (no simulator, no browser measurement): i5-13420H, balanced, on
AC ([`machine_start.json`](machine_start.json), [`machine_end.json`](machine_end.json); Gautham's
Brave browser was open). Raw: [`cpython.json`](cpython.json), [`pyodide.json`](pyodide.json)
(each with its own conditions before and after). MODEL; timings are this machine's.

Plan grid 490 × 330 cells at 0.1 m; Arena build 485 ms (CPython), 819 ms (Pyodide). Budget (stated): **300 ms warm per plan in Pyodide**.

| Pair | Planner | Expanded | Path m | CPython warm median ms | Pyodide warm median ms | Pyodide warm max ms | Pyodide vs 300 ms |
|---|---|---|---|---|---|---|---|
| start_to_dock | bfs | 85,004 | 23.71 | 610.3 | 859.9 | 1001.1 | **over** |
| start_to_dock | dijkstra | 71,126 | 23.71 | 713.7 | 1087.3 | 1136.4 | **over** |
| start_to_dock | astar | 236 | 23.71 | 4.0 | 6.1 | 6.3 | within |
| start_to_dock | greedy | 236 | 23.71 | 4.2 | 6.2 | 6.4 | within |
| start_to_dock | weighted_astar | 236 | 23.71 | 4.3 | 6.2 | 6.4 | within |
| start_to_office_sw | bfs | 116,636 | 37.55 | 792.6 | 1315.7 | 1434.4 | **over** |
| start_to_office_sw | dijkstra | 115,399 | 37.55 | 1148.1 | 1599.0 | 1774.2 | **over** |
| start_to_office_sw | astar | 36,023 | 37.55 | 458.2 | 653.2 | 730.9 | **over** |
| start_to_office_sw | greedy | 10,741 | 39.02 | 132.8 | 180.1 | 180.7 | within |
| start_to_office_sw | weighted_astar | 11,313 | 37.80 | 140.9 | 199.2 | 201.3 | within |
| start_to_maze_dead_end | bfs | 47,977 | 17.46 | 305.0 | 485.0 | 490.2 | **over** |
| start_to_maze_dead_end | dijkstra | 47,038 | 17.46 | 469.0 | 669.9 | 786.2 | **over** |
| start_to_maze_dead_end | astar | 10,931 | 17.46 | 148.8 | 258.9 | 260.3 | within |
| start_to_maze_dead_end | greedy | 587 | 18.61 | 8.0 | 14.1 | 14.3 | within |
| start_to_maze_dead_end | weighted_astar | 2,033 | 17.79 | 29.5 | 53.6 | 57.1 | within |
| start_to_mezzanine_deck | bfs | 107,565 | 34.47 | 786.4 | 1270.6 | 1291.5 | **over** |
| start_to_mezzanine_deck | dijkstra | 108,760 | 34.47 | 1092.7 | 1720.2 | 1753.1 | **over** |
| start_to_mezzanine_deck | astar | 23,453 | 34.47 | 349.9 | 512.0 | 526.1 | **over** |
| start_to_mezzanine_deck | greedy | 3,319 | 42.38 | 44.7 | 61.4 | 61.8 | within |
| start_to_mezzanine_deck | weighted_astar | 5,967 | 36.30 | 87.6 | 120.1 | 121.1 | within |
| dock_to_office_ne | bfs | 95,632 | 46.82 | 726.3 | 977.7 | 1162.7 | **over** |
| dock_to_office_ne | dijkstra | 98,824 | 46.82 | 977.5 | 1377.2 | 1451.5 | **over** |
| dock_to_office_ne | astar | 28,642 | 46.82 | 412.0 | 691.6 | 743.2 | **over** |
| dock_to_office_ne | greedy | 565 | 49.47 | 8.3 | 14.1 | 14.4 | within |
| dock_to_office_ne | weighted_astar | 605 | 47.73 | 9.0 | 15.4 | 15.7 | within |
| aisle_1_to_aisle_3 | bfs | 33,832 | 14.97 | 209.8 | 331.5 | 337.7 | **over** |
| aisle_1_to_aisle_3 | dijkstra | 32,546 | 14.97 | 298.2 | 457.0 | 515.2 | **over** |
| aisle_1_to_aisle_3 | astar | 3,101 | 14.97 | 31.7 | 65.3 | 66.5 | within |
| aisle_1_to_aisle_3 | greedy | 509 | 19.88 | 6.1 | 12.6 | 13.1 | within |
| aisle_1_to_aisle_3 | weighted_astar | 784 | 15.71 | 9.8 | 19.7 | 19.9 | within |
| maze_entrance_to_dead_end | bfs | 29,457 | 14.96 | 198.3 | 284.1 | 290.2 | within |
| maze_entrance_to_dead_end | dijkstra | 26,022 | 14.96 | 220.9 | 341.6 | 360.0 | **over** |
| maze_entrance_to_dead_end | astar | 204 | 14.96 | 2.8 | 4.3 | 4.4 | within |
| maze_entrance_to_dead_end | greedy | 145 | 15.05 | 1.9 | 3.1 | 3.2 | within |
| maze_entrance_to_dead_end | weighted_astar | 146 | 15.05 | 2.0 | 3.2 | 3.3 | within |

- **CPython and Pyodide expand the same nodes and find the same path length in all 35 cases.**
- **Over the 300 ms budget in Pyodide: 16 of 35** — BFS 6/7, Dijkstra 7/7, A* 3/7 (the long routes: start → office SW, start → mezzanine deck, dock → office NE); greedy and weighted A* within everywhere.
- Per the harness (and README invariant 9): an over-budget planner goes to the WebAssembly gate as an ADR; nothing is ported here. Interactive play does not plan in a tick (G1.11–G1.12: precomputed rounds, AUTO's search run ahead between ticks).

