# M6 foundations — results (to append to docs/RESULTS.md at merge)

Branch `v2/m6-foundations`, 2026-10-17. Machine: i5-13420H (12 threads), RTX 4050 Laptop
GPU (driver 580.178.04, unused here), 16 GB, Ubuntu 24.04, ROS 2 Jazzy; **AC online,
profile balanced**. **Codex was running the whole session** (`codex resume` plus seven to
eight `lab_web/tools/perf/serve_dist.mjs` servers), so every job here ran under
`nice -n 19` and **no timing in this file is a benchmark**. No Gazebo, Isaac or ROS
launch ran. Every number below is from committed data or a test that recomputes it;
"derived" means computed from existing constants, not measured.

## Tests (counts at the end of each checkpoint)

| Suite | Before (`0254dea`) | After | Notes |
|---|---|---|---|
| `coco_lab` | 824 / 0 / 0 | 1,001 / 0 / 0 | +177 new tests; every existing test passed unedited |
| `coco_schemas` | 232 / 0 / 0 | 241 / 0 / 0 | +9 parametrisations from the registered `manip.grasp` channels |
| `coco_lab_ros` | not run before | 158 passed / 4 failed | the 4 need packages in the ament index (`gazebo_models`, `custom_teleop`, `coco_lab_ros`): no colcon overlay of this worktree exists yet; +17 new M6 tests, all passing |
| `lab_web` vitest, build-tool tests | not run | not run | no `lab_web` code changed; `coco_schemas/scripts/generate.py --check` reproduces every committed generated file, TypeScript included, with the pinned protoc-gen-es 2.15.0 |

## M6F.1 — World Spec v3 (MODEL)

- v1 and v2 unchanged: the pre-change fixture (`coco_lab/test/fixtures/m6f/prechange_v1v2.json`,
  made at `0d1f37f` before any v3 code): 2 specs' canonical bytes and maps, 12 seeded
  sessions × 150 ticks (hash v1 and v2) replay byte for byte through the v3 reader; the
  first 10 committed M1 determinism sessions × 150 ticks reproduce their committed
  Pyodide-in-Node hashes (`docs/v2/data/m1/determinism/`).
- `from_v2(coco_arena_v2)` lowers to the same 70 boxes and 12 elevation solids, the same
  maps, and the same per-tick hashes under hash v1 for 6 sessions; under hash v2 the
  spelling is (correctly) a different world.

## M6F.2 — the generators on the Proving Ground (MODEL)

- Nav2 map for the v1 and v2 arena specs: **byte-identical** to
  `gazebo_models/maps/coco_navigation.pgm`; the YAML identical but for the image name.
- SDF: all 70 boxes identical to `coco_navigation.world` (names, poses, sizes);
  physics, systems, lights, scene and ground plane identical; the 12 ramp/platform models
  match the launch file's spawns, names differ, rise differs by 3.4 × 10⁻¹³ m; the wedge
  STL's vertex set equals `ramp_wedge_18.stl`'s to 6 decimals. `gz sdf -k`: Valid.
- Checksums: `docs/v2/m6/data/coco_arena_v2_outputs.json`. Report: `docs/v2/m6/PROVING_GROUND.md`.

## M6F.3 — the COCO Depot (MODEL)

- `worlds/coco_depot_v1.yaml`: 48 × 32 m, 72 boxes, 2 elevation solids (ramp + deck at
  2·tan 18° = 0.6498 m), 18 objects, 4 actors, 6 zones; a 490 × 330 grid at 0.1 m.
- Outputs: 27 files; `gz sdf -k` Valid on all 19 SDFs; checksums in
  `docs/v2/m6/data/coco_depot_v1_outputs.json` (reproduced by a test).
- No two actors' boxes meet in 600 s (sampled every 0.05 s by the generator, 0.1 s by
  the test). A planner reaches every zone from the start (A*, tested).
- Derived: Grasp Assist's reach band (grasp-band heights the arm reaches at both window
  ends and at the hover) **0.099–0.128 m**; the Stack's 0.128 m is its top edge.

## M6F.4 — Depot planning at 0.1 m

**Pending, machine busy.** Harness `tools/m6/bench_planning.py` and
`tools/m6/bench_planning_pyodide.mjs`; budget stated: 300 ms warm per plan. No number.

## M6F.5 — Grasp Assist (MODEL)

- 13 Depot scenarios with golden traces (`coco_lab/test/fixtures/m6f/grasp_golden.json`):
  every refusal reason produced as designed; every pick's final position is **0.15375 m
  or 0.154 m ahead**, inside the Stack's 0.151–0.1565 m window, with |left| ≤ 10 mm.
- Detection range used: 1.40 m, the measured first-detection distance of the 20 mm
  target (STACK, `docs/data/p03c_episode_gazebo/README.md`), not a new measurement.

## M6F.6 — the games (MODEL; references in `docs/v2/m6/data/games_reference.json`)

| Run | Result |
|---|---|
| Fetch Rush seed 1 | 1 delivery, 0 contacts, 136.7 s used, path efficiency 0.987 |
| Fetch Rush seed 2 | 1 delivery, 0 contacts, 136.7 s used, path efficiency 0.987 (same first order as seed 1) |
| Fetch Rush seed 3 | 0 deliveries, 0 contacts (first order's ghost 77.9 m, ~260 s at 0.3 m/s) |
| Rush Hour `aisle_to_dispatch` | delivered in 102.2 s, 0 contacts, min clearance 0.573 m, jerk RMS 3.95 m/s³, peak 39.98 m/s³ |

All four records replay to identical results through `games.verify` (M5's link limits).
Before the reference bot yielded to actors, the same seed-1 run had 2 actor contacts (the
east–west forklift, t ≈ 174 s): the yield rule is why the reference is clean.

## M6F.7 — the ROS-shaped model vs recorded Stack bags (MODEL vs STACK)

- Shapes against `lab2_kidnap_recovery_k1` and `lab5_crossing_dwb_1`: frames, scan
  geometry (480 beams, ∓2.0944 rad, 0.15–12 m, scan_time 0), static transforms
  (`base_footprint→base_link` z 0.0135, `base_link→lidar_link` (−0.09, 0.1, 0.2)),
  odometry, command and path frames all agree; **intensities differ** (model none, Stack 480).
- Scan values, 30 recorded scans vs the model from the recorded ground-truth pose on
  World Spec v1: **13,890 beams, median |Δ| 0.0495 m, 90th percentile 0.147 m, 50.1 %
  within 0.05 m** (`docs/v2/m6/data/ros_shapes_vs_stack.json`).

## M6F.8 — Gazebo and Nav2

**Pending, machine busy** (`docs/v2/m6/M6F8_PLAN.md`). No STACK evidence was produced on
this branch.
