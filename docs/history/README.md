# docs/history

Archived documents, kept byte-for-byte as they were when superseded. Do not
edit them; put corrections in this file instead.

| File | Archived | Superseded by |
|---|---|---|
| `ROADMAP_COCO2.md` | 2026-09-29 (Phase 0, Milestone 0B), unchanged from `main` `442bca0` | `docs/ROADMAP.md` (COCO Lab) |

## Corrections to archived text

**`ROADMAP_COCO2.md`, Track 1, row M3 — "A\* global planner
(`SmacPlanner2D`) … 3.165 m / 5.5 ms / 62 poses vs NavFn 3.373 / 5.6 /
134".** The numbers are correct and stay as measured. The framing is not:
elsewhere the 6.2 % difference was read as A\* beating Dijkstra. The
comparison is `SmacPlanner2D` against `NavfnPlanner` with
`use_astar: false` — two implementations. With an admissible heuristic and
identical edge costs, A\* and Dijkstra return equal-cost paths; the gap
comes from how each planner extracts and costs its path (NavFn's `calcPath`
gradient descent, recorded in `docs/DESIGN_DECISIONS.md`). Corrected in
`README.md` and `docs/RESULTS.md` on 2026-09-29; COCO Lab's Plan lab is
scoped to measure the split (`docs/ROADMAP.md`, Lab 1).

**`ROADMAP_COCO2.md` section names** ("Track 3", "Track 4", "P1.0") live in
this archive, not in the new `docs/ROADMAP.md`. On 2026-09-29 the citations
in `docs/PRODUCT_ARCHITECTURE.md` and `PROJECT_STATE.md` were repointed here.
These still say plain `docs/ROADMAP.md` and mean this file:
`docs/STATE_PROTOCOL.md` (itself history), `CLAUDE.md` (user-owned,
additive edits only), and code comments in `coco_rl/coco_rl/baselines.py`,
`coco_rl/coco_rl/terrain_benchmark.py` and
`coco_web/coco_web/platform_server.py`.
