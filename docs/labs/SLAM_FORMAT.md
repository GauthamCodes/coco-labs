# SLAM trace 1.0 and map bundle 1.0

Lab 3 (Map) adds two versioned formats beside Lab 1's trace and bundle v1
and Lab 2's localisation formats. They follow the same rules (ROADMAP §4
invariant 7): additive changes bump MINOR and a reader ignores what it does
not know; anything that changes a meaning bumps MAJOR and a reader refuses a
MAJOR it does not know.

- Reference implementations: `coco_lab/coco_lab/slam.py` (trace) and
  `coco_lab/coco_lab/slambundle.py` (bundle); the world is
  `coco_lab/coco_lab/mapworld.py`, the scores `coco_lab/coco_lab/mapeval.py`
- Browser decoder: `lab_web/src/map/decode.ts`, pinned to Python by
  `lab_web/test/slamdecode.test.ts` (every array's bytes hash-equal) against
  `coco_lab/test/fixtures/slam_bundles/`
- This document is pinned by
  `coco_lab/test/test_slambundle.py::test_the_doc_matches_the_implementation`.

## SLAM trace (`coco_lab.slam_trace` 1.0)

One algorithm's run over one world: a **header**, **columns** (one row per
update), **arrays** of any length, **map snapshots**, and a **summary**
filled by scoring.

### Header

| field | meaning |
|---|---|
| `schema` | `coco_lab.slam_trace` |
| `version` | `"1.0"` |
| `algorithm` | `known`, `odometry`, `ekf_slam`, `fastslam` or `pose_graph` |
| `params` | every parameter the run used (`GivenPoseParams`, `EKFSlamParams`, `FastSlamParams`, `PoseGraphParams`) |
| `grid` | `{width, height, resolution, origin}` of the run's occupancy grid |
| `grid_params` | the inverse sensor model and thresholds (`occgrid.GridParams`) |
| `n_updates`, `n_beams` | the world's update count and beams per scan |

### Columns (one value per update)

Every trace has:

| column | type | meaning |
|---|---|---|
| `row` | i32 | the world row of the update (equal to the world's `updates`) |
| `t` | f64 | time, s |
| `est_x`, `est_y`, `est_yaw` | f64 | the ONLINE estimate: what the algorithm believed at that update |

`ekf_slam` adds `cov_xx`, `cov_xy`, `cov_yy`, `cov_tt` (f64: the pose
covariance) and `n_landmarks`, `n_obs` (i32). `fastslam` adds `neff` (f64),
`resampled` and `best` (i32: the heaviest particle). `pose_graph` adds
`icp_ok`, `loops`, `optimised` (i32). Which columns are integers is listed
in the bundle's `int_columns`.

### Arrays

| array | dtype | meaning |
|---|---|---|
| `final.x`, `final.y`, `final.yaw` | f64 | the FINAL trajectory, one pose per update (`fastslam`: the surviving particle's ancestry; `pose_graph`: the optimised graph). Absent: the final trajectory is the online one |
| `lm.offset`, `lm.id` | i32 | `ekf_slam`: landmarks known at each update (`offset` has n_updates + 1 entries) |
| `lm.x`, `lm.y`, `lm.cxx`, `lm.cxy`, `lm.cyy` | f64 | their means and 2 x 2 covariances |
| `particles.offset` | i32 | `fastslam`: particles per update |
| `particles.x`, `particles.y`, `particles.yaw`, `particles.w` | f32 | the weighted set BEFORE resampling |
| `edges.i`, `edges.j`, `edges.kind` | i32 | `pose_graph`: every edge; kind 0 odometry, 1 ICP, 2 loop |
| `loops.k`, `loops.j` | i32 | each accepted loop closure: at update k, to node j |
| `opt.k`, `opt.iterations` | i32 | each optimisation and its Gauss-Newton iterations |
| `opt.chi2_before`, `opt.chi2_after` | f64 | its chi-squared before and after |
| `score.err_online`, `score.err_final` | f64 | per-update position error to the truth (after the score's alignment) |
| `score.diff` | u8 | one class per TRUTH cell: 1 a mapped wall within tolerance, 2 a mapped wall that is not there, 3 a visible true wall missed, 0 otherwise (`mapeval.diff_raster`) |

### Map snapshots

`snapshots` are update indices (increasing); `maps` are the occupancy grid at
each, as `nav_msgs/OccupancyGrid` bytes: one byte per cell, NORTH row first,
`0..100` = P(occupied) in percent, `255` = never observed.

### Summary (scoring, `coco_lab.mapeval`)

`ate_online` and `ate_final`: `{n, aligned, alignment [tx, ty, theta], rmse,
mean, max, final}`, metres. `map`: `{tol_m, precision, recall, f1, coverage,
occupied_cells, visible_wall_cells, reachable_free_cells, exact}` where
`exact` is `maps.compare_occupied`. The definitions are `mapeval`'s module
docstring and are not repeated here.

## Map bundle (`coco_lab.slam_bundle` 1.0)

Bundle format v1's rules exactly: a directory holding `manifest.json` and
`arrays.bin` (or `arrays.bin.gz`, gzip mtime 0); canonical JSON;
little-endian arrays at contiguous offsets; `content_hash` = SHA-256 over
the canonical manifest (without `content_hash`, `encoding` and
`provenance.created_utc`), a newline and the uncompressed arrays.

### Manifest

| key | meaning |
|---|---|
| `schema`, `version` | `coco_lab.slam_bundle`, `"1.0"` |
| `provenance` | bundle v1 provenance; `source_kind` `sketch` for a Sketch world, `recorded-run` (with `rosbag`) for a recorded drive |
| `map` | the TRUTH map, as bundle v1's `map` block |
| `world` | `source` (`sketch` / `recorded`), `status`, `n_rows`, `n_updates`, `lidar`, `start`, `landmark_spec`, `landmarks` (`[[id, x, y]]`), `scenario` (Sketch) or `recorded` (provenance of the recording) |
| `scoring` | `{align, tol_m, definitions: "coco_lab.mapeval"}` |
| `runs` | 1..6 `{id, header, int_columns, arrays: {name: dtype}, summary}` |
| `external` | 0..4 `{id, backend, arm, grid, source, summary}` -- ROS backends' measured runs on a RECORDED drive |
| `arrays` | the table: `{name, dtype, count, offset, byte_length}` |
| `encoding` | `{byte_order: little, compression: none / gzip}` |
| `content_hash` | as above |

### Arrays

| array | dtype | meaning |
|---|---|---|
| `map.occupancy` | u8 | the truth map |
| `world.t`, `world.gt_x`, `world.gt_y`, `world.gt_yaw`, `world.odom_x`, `world.odom_y`, `world.odom_yaw` | f64 | per ROW |
| `world.updates` | i32 | the update rows |
| `world.ranges` | f64 | n_updates x n_beams, `inf` = no return |
| `world.obs.offset`, `world.obs.id` | i32 | the IDEALISED landmark observations per update |
| `world.obs.r`, `world.obs.b` | f64 | their range and bearing |
| `run.<id>.col.<column>` | i32 / f64 | a run's columns |
| `run.<id>.arr.<array>` | as listed | a run's arrays |
| `run.<id>.snap.k` | i32 | its snapshot update indices |
| `run.<id>.snap.cells` | u8 | its snapshots, back to back |
| `ext.<id>.est_x`, `ext.<id>.est_y`, `ext.<id>.est_yaw` | f64 | an external run's online belief at each update, in ITS map frame |
| `ext.<id>.cells` | u8 | its final map (OccupancyGrid bytes, north row first) |
| `ext.<id>.err_online` | f64 | its per-update error after the alignment |
| `ext.<id>.diff` | u8 | its map-vs-truth classes |

### Replay

`slambundle.replay_check` simulates a Sketch world again from its scenario
(a recorded world is taken as recorded), reruns every coco_lab run with its
recorded parameters, re-scores every run including the external ones, and
refuses unless every array and summary is identical. The site build refuses
a bundle that does not replay; the browser never replays (rule 8).
