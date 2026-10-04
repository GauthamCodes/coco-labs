# Localisation trace 1.0 and localisation bundle 1.0

Lab 2 (Localise) adds two versioned formats beside Lab 1's trace schema v1
and bundle format v1. They follow the same rules (ROADMAP §4 invariant 7):
additive changes bump MINOR and a reader ignores what it does not know;
anything that changes a meaning bumps MAJOR and a reader refuses a MAJOR it
does not know.

- Reference implementations: `coco_lab/coco_lab/localise.py` (trace) and
  `coco_lab/coco_lab/locbundle.py` (bundle)
- Browser decoder: `lab_web/src/loc/decode.ts`, pinned to Python by
  `lab_web/test/locdecode.test.ts` (every array's bytes hash-equal) against
  `coco_lab/test/fixtures/loc_bundles/`
- This document is pinned by
  `coco_lab/test/test_locbundle.py::test_the_doc_matches_the_implementation`.

## Localisation trace (`coco_lab.loc_trace` 1.0)

One filter's run over one Sketch world: a **header**, **columns** (one row
per filter update), a **summary**, and for MCL the **particles**.

### Header

| field | meaning |
|---|---|
| `schema` | `coco_lab.loc_trace` |
| `version` | `"1.0"` |
| `filter` | `mcl` or `ekf` |
| `params` | every parameter the filter ran with (`MCLParams` / `EKFParams`) |
| `n_beams_scan` | beams in the world's scan |

### Columns

Every trace has these, one value per filter update, in order:

| column | type | meaning |
|---|---|---|
| `row` | i32 | the world row of the update (strictly increasing; equal to the world's `updates`) |
| `t` | f64 | sim time, s |
| `est_x`, `est_y`, `est_yaw` | f64 | the estimate (map frame, m and rad) |
| `cov_xx`, `cov_xy`, `cov_yy` | f64 | its position covariance, m² |
| `cov_yaw` | f64 | its heading variance, rad² |
| `err_xy`, `err_yaw` | f64 | distance and absolute heading error to the TRUTH |

MCL adds:

| column | type | meaning |
|---|---|---|
| `n_eff` | f64 | effective sample size before resampling |
| `resampled` | i32 | 1 if the update resampled |
| `injected` | i32 | random particles injected at this update |
| `p_inject` | f64 | the injection probability used |
| `w_avg`, `w_slow`, `w_fast` | f64 | augmented MCL's averages (AMCL's `pf.c`) |
| `cluster_weight` | f64 | weight of the heaviest cluster (the estimate's) |

EKF adds:

| column | type | meaning |
|---|---|---|
| `beams_used` | i32 | beams in the update |
| `beams_gated` | i32 | beams refused by the innovation gate |
| `nis` | f64 | mean normalised innovation squared of the used beams |

The **estimate** of MCL is the weighted mean of its heaviest cluster
(particles within 1 m of the heaviest 0.5 m bin), as AMCL reports its
heaviest cluster; the EKF's is its mean. `err_*` are the only columns that
read the truth: the filters never do (tested).

### Particles (MCL only)

`offset` (i32, n_updates + 1, from 0, non-decreasing) and `x`, `y`, `yaw`,
`w` (f32): update `k`'s particles are rows `offset[k] .. offset[k+1]`, the
WEIGHTED set after the measurement and before resampling; weights sum to 1
per update.

### Summary

`n_updates`, `mean_err_xy`, `max_err_xy`, `final_err_xy`, `final_err_yaw`,
`converged_s` (first update from which the estimate holds within
`ok_xy` 0.5 m and `ok_yaw` 0.3 rad for `ok_hold` 5 updates, before any kidnap),
`kidnap_s`, `recovered`, `recovery_s` (the same, after the kidnap, timed
from it).

## Localisation bundle (`coco_lab.loc_bundle` 1.0)

A directory with exactly `manifest.json` and `arrays.bin` (or
`arrays.bin.gz`, gzip `mtime` 0). Bundle v1's rules hold unchanged:
canonical JSON, little-endian arrays at contiguous offsets, a content hash
over the canonical manifest (without `content_hash`, `encoding` and
`provenance.created_utc`) plus a newline plus the raw arrays, every size
bounded before allocation, refused rather than repaired.
`provenance.source_kind` is `sketch`.

### Manifest

| member | meaning |
|---|---|
| `schema`, `version` | `coco_lab.loc_bundle`, `"1.0"` |
| `provenance` | bundle v1's provenance block |
| `map` | `id`, `content_hash`, `width`, `height`, `geo`, `meta` (a placed map) |
| `scenario` | the `Scenario`: start, route, seed, noise, kidnap, dt, speeds, LiDAR, max time |
| `world` | `status`, `n_rows`, `n_updates`, `kidnap_row` |
| `runs` | one to four `{id, header, summary}`, ids unique short words |
| `arrays`, `encoding`, `content_hash` | as bundle v1 |

### Arrays, in wire order

| array | dtype | length |
|---|---|---|
| `map.occupancy` | u8 | width × height |
| `world.t`, `world.gt_x`, `world.gt_y`, `world.gt_yaw`, `world.odom_x`, `world.odom_y`, `world.odom_yaw`, `world.cmd_v`, `world.cmd_w` | f64 | n_rows |
| `world.updates` | i32 | n_updates |
| `world.ranges` | f64 | n_updates × n_beams (`inf` = no return) |
| `run.<id>.<column>` | i32 or f64 (as above) | n_updates |
| `run.<id>.particles.offset` | i32 | n_updates + 1 |
| `run.<id>.particles.{x,y,yaw,w}` | f32 | offset[-1] |

`f32` exists only in this format, never in bundle v1 (so Lab 1's decoder
keeps refusing it).

### Identical inputs, and replay

Every run in a bundle reads the SAME world (its rows equal the world's
`updates`), so a race is on identical inputs by construction.
`locbundle.replay_check` simulates the world again from `scenario` and runs
every filter again from its `header.params`; the arrays must come out byte
for byte. `lab_web/tools/build_localise.py` refuses to serve a bundle that
does not.
