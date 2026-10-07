# Lab 5 bundle formats 1.0: replan bundle and drive bundle

Normative. The reference implementation is `coco_lab/coco_lab/movebundle.py`
(with `coco_lab/coco_lab/replan.py`, `dstarlite.py` and `movemetrics.py`);
`coco_lab/test/test_movebundle.py` tests it, including that the committed
golden bundles (`coco_lab/test/fixtures/move_bundles/`) are byte-identical to
what the writer writes. The TypeScript reader is `lab_web/src/move/decode.ts`,
pinned to the Python writer by `lab_web/test/golden/move_expected.json`
(`lab_web/tools/make_move_expectations.py`) and `lab_web/test/movedecode.test.ts`.

Both formats follow bundle format v1's rules exactly (`coco_lab.bundle`): a
directory holding `manifest.json` and `arrays.bin` (or `arrays.bin.gz`, gzip
mtime 0); canonical JSON; little-endian arrays at contiguous offsets, in the
order the table lists them; `content_hash` = SHA-256 over the canonical
manifest (without `content_hash`, `encoding` and `provenance.created_utc`), a
newline, and the uncompressed arrays; every size bounded before allocation;
refused, never repaired. A reader refuses any MAJOR other than 1, any array the
manifest does not account for, and any array it needs that is missing.

## Replan bundle (`coco_lab.replan_bundle`)

One `replan.ReplanWorld` and the episode `replan.run_replan` drove in it.

| manifest key | meaning |
|---|---|
| `schema`, `version` | `coco_lab.replan_bundle`, `1.0` |
| `provenance` | bundle v1 provenance; `source_kind` `sketch` (a seeded teaching world, or a learner's edit in the browser, `tool` `lab_web/pyodide`) or `glass-box` (a world built from two recorded Nav2 costmaps, Experiment C, with `title` and `inputs`) |
| `world` | `width`, `height`, `start`, `goal` (`[row, col]`, row 0 at the top), `sense_radius` (cells, Euclidean; `null` = every change is learned at once), `connectivity`, `heuristic`, `has_cost`, `has_truth_cost`, `first_sense_step` (0 or 1), `schedule` (`[[step, [[row, col, blocked], ...]], ...]`), `max_steps` |
| `status` | `reached`, `no_path` or `step_limit` |
| `summary` | `status`, `steps`, `replans`, `dstar_expansions`, `astar_expansions`, `reexpansions`, `first_cost`, `walked_length`, `costs_agree` |
| `rounds` | one entry per plan: `step`, `robot`, `changed` (cells the robot's map changed in, sensed then), `found`, `cost` (D* Lite's `g(robot)`, `null` iff not found), `path_offset`, `path_len`, `dstar_expansions`, `dstar_reexpansions`, `astar_expansions` (Lab 1's A* from scratch on the same map), `astar_cost` |
| `n_events` | rows in the trace |

| array | dtype | contents |
|---|---|---|
| `known` | u8 | the robot's map before it moves (1 = blocked), row-major |
| `truth` | u8 | the world before any scheduled change |
| `known_final` | u8 | the robot's map when the episode ended |
| `cost` | f64 | only if `has_cost`: the map's cost layer (`grid.Grid` units) |
| `truth_cost` | f64 | only if `has_truth_cost`: the world's cost layer |
| `walk` | i32 | the robot's cells, `row, col` interleaved, start first |
| `paths` | i32 | every round's path, `row, col` interleaved, at the round's `path_offset` (in cells) |
| `trace.kind`, `.row`, `.col`, `.sub`, `.round` | i32 | D* Lite's events; `kind` indexes `expand, raise, update, change, path, move` |
| `trace.g`, `trace.rhs` | f64 | the state's values at the event; `-1` means infinity |

`movebundle.replay_replan` rebuilds the world from the manifest and the three
world arrays, runs the episode again and refuses unless every array and the
summary, rounds and world are identical.

## Drive bundle (`coco_lab.drive_bundle`)

One Lab 5 scenario and the controller runs recorded on it in Gazebo.

| manifest key | meaning |
|---|---|
| `schema`, `version` | `coco_lab.drive_bundle`, `1.0` |
| `provenance` | `source_kind` `recorded-run`; `rosbag.sha256` is the SHA-256 of the newline-joined sorted per-run bag hashes (Lab 4's convention), the sim-time span the union of the windows |
| `scenario` | `id`, `title`, `path_sha256` (the frozen path file), `path_len`, `start`, `goal`, `boxes` (the arena's boxes in the map frame, `[cx, cy, sx, sy]`), `actor_radius`, `actors_spec`, `inject` |
| `runs` | 1 to 64: `id` (`<controller>_<k>`), `controller` (`DWB`, `MPPI`, `RPP`), `outcome` (`succeeded`, `follow_failed`, `failed`, `error`), `window` (`[t0, t1]`, sim s), `record` (provenance of the run: run id, source commit, bag and heavy-bag hashes, error code, runner checks, actor visibility, injection), `metrics` (below), `has_rollouts`, `actors` (ids), `monitor` (`[t, action, polygon]`), `actor_trigger`, `n` (row counts) |

| array | dtype | contents |
|---|---|---|
| `path` | f64 | the frozen path, `x, y, yaw` rows, map frame |
| `run.<id>.gt` | f64 | ground truth `t, x, y, yaw`, full rate, map frame, the window plus 1 s each side |
| `run.<id>.amcl` | f64 | AMCL's belief `t, x, y, yaw` |
| `run.<id>.cmd` | f64 | the controller's output (`/cmd_vel_nav`) `t, v, w` |
| `run.<id>.wheel` | f64 | what reached the wheels (`/diff_drive_controller/cmd_vel`) `t, v, w` |
| `run.<id>.actor.<aid>` | f64 | the actor's commanded pose `t, x, y, yaw` |
| `run.<id>.chosen.t`, `.off` (i32), `.pts` | f64 | the controller's own chosen trajectory (DWB `/local_plan`, MPPI `/optimal_trajectory`, RPP `/lookahead_collision_arc`) every fifth message, points through map → odom as AMCL had it |
| `run.<id>.eval` | f64 | DWB only: every control cycle's `t, n, n_valid` |
| `run.<id>.roll.*` | | only if `has_rollouts`: frames `t` (f64), `n` (i32 pairs `n, n_valid`, `-1` unknown), candidate offsets `coff` (i32), point offsets `poff` (i32), `pts` (f64), `flags` (u8: bit 0 valid, 2 = unknown, bit 2 best), `total` (f64, NaN when the controller publishes no score) |

`metrics` is `movemetrics.evaluate(path, gt, window, cmd, boxes, actors)` and
`movebundle.replay_drive` recomputes it from the bundle's own arrays, refusing
any difference.

### The four metrics (`coco_lab.movemetrics`)

- **Tracking error** (m): for every ground-truth sample in the window, its
  distance to the nearest point of the path polyline; `n`, `mean`, `p95`
  (nearest rank), `max`. Phase 1C's definition, unchanged.
- **Travel time** (s): `t1 - t0`, simulator seconds; a travel time only when
  the run succeeded.
- **Smoothness**: RMS of the controller's commanded `dv/dt` (m/s²) and `dw/dt`
  (rad/s²) between consecutive commands in the window.
- **Minimum clearance** (m): the smallest distance, over ground-truth samples
  in the window, between the footprint rectangle (0.297 × 0.314 m, centred,
  from `coco_config`) and any box, and separately any actor cylinder; 0 and
  `contact` when they overlap.
