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

## M6F.8 — Gazebo and Nav2, measured on the laptop (G1.13, 2026-10-23; appended)

STACK evidence (the full ROS 2 stack in Gazebo, headless, `gui:=false`, never `--fast`; no
hardware). Laptop, balanced profile, on AC, ROS 2 Jazzy, ROS_DOMAIN_ID 79, overlay
`~/coco_lab_g1_ws`. Raw logs and bags in `~/coco_lab_runs/m6/` (outside git); per run the
goals, Nav2's result codes and the sha256 of every raw file in
`docs/v2/m6/data/m6f8/smoke_summary.json` and `ghost_summary.json`
(`tools/m6/m6f8_summary.py`). Runner: `tools/m6/m6f8_run.sh` (M6F8_PLAN.md's steps), goals
from the model (`tools/m6/m6f8_goals.py`), NavigateToPose client `tools/m6/m6f8_nav.py`.

- **Generated level:** `tools/m6/gen_level.py worlds/coco_depot_v1.yaml --nav-res 0.05
  --gz-check --verify`: every output **identical** to `coco_depot_v1_outputs.json`; `gz sdf -k`
  Valid on all 20 SDFs. The map is aligned with the world (south and west walls at map
  y/x −0.125…+0.125 against the SDF's walls at 0; racks likewise).
- **Bring-up (5 fresh simulators):** /scan after 6–7 s, all ten Nav2 lifecycle nodes active
  after 19–20 s, AMCL pose 1–2 s later; the wheel topic has **exactly one publisher,
  `cmd_vel_arbiter`**. `full_world_robo.launch.py` also spawns the COCO arena's `ramp` with its
  foot at world (1.0, 0) — the Depot's south-west corner, not in the Nav2 map; no goal passes
  there. Actors parked (as planned: no actor driver).
- **Smoke test, goals chained (runs 1 and 2, the same result twice):** 2 of 9 —
  the loading dock and the dock object SUCCEEDED (truth ends 0.44–0.53 m from the goal; AMCL
  0.43–0.51 m off truth, always to the south); high-bay aisle 1 then failed (run 1:
  FollowPath INVALID_PATH, 103, "Resulting plan has 0 poses"; run 2: START_OCCUPIED, 205)
  with AMCL's pose inside rack cost, and every later goal was refused START_OCCUPIED (205)
  without moving: those zones were not tested by these runs.
- **Smoke test, each goal its own leg from the start (`--reset-each`, run 3):**

  | Goal | Result | Nav2 code | sim s | driven m | truth → goal m | AMCL error m |
  |---|---|---|---|---|---|---|
  | Loading dock (roomiest cell) | SUCCEEDED | 0 | 69.9 | 19.97 | 0.462 | 0.476 |
  | Dock object pre-grasp | SUCCEEDED | 0 | 94.3 | 24.03 | 0.412 | 0.486 |
  | High-bay aisle 1 pre-grasp | SUCCEEDED | 0 | 55.6 | 14.14 | 0.112 | 0.167 |
  | High-bay aisle 3 pre-grasp | ABORTED | 205 START_OCCUPIED | 64.9 | 18.55 | 4.555 | 0.146 |
  | Office block (corridor) | ABORTED | 103 INVALID_PATH | 92.2 | 26.18 | 7.902 | 6.915 |
  | Office NE room pre-grasp | ABORTED | 205 START_OCCUPIED | 81.2 | 22.46 | 6.023 | 0.108 |
  | Workshop maze pre-grasp | SUCCEEDED | 0 | 67.8 | 15.55 | 0.110 | 0.052 |
  | Dispatch floor | SUCCEEDED | 0 | 29.5 | 4.86 | 0.146 | 0.193 |
  | Back to the start | SUCCEEDED (already there: 0 m) | 0 | 0.7 | 0.00 | 0.000 | 0.006 |

  **5 of 8 legs that drove succeeded.** Aisle 3 and the office room failed with AMCL within
  0.15 m of truth (the robot's pose itself in occupied cost mid-leg); the office corridor leg
  failed with AMCL 6.9 m off. **UNRESOLVED:** why AMCL sits ~0.45–0.5 m south of truth after
  the dock legs, and why Nav2 meets occupied cost in aisle 3 and the office where the model's
  plan grid has a route. Not diagnosed here.
- **Ghost of a Fetch Rush phone round (rules 3, seed 1; driving legs only), twice on fresh
  simulators:** start (42.25, 8.45, 337.5°), AMCL seeded there. Leg 1 (to `obj_dock`'s
  pre-grasp pose) SUCCEEDED both times (13.2 s, 3.58–3.59 m, truth 0.405 m from the goal);
  leg 2 (to Dock 1) ABORTED both times — run 1: "Failed to make progress", then
  START_OCCUPIED (205) at truth (40.74, 5.48) after 6.39 m; run 2: START_OCCUPIED at
  (41.50, 5.20) after 5.65 m — and legs 3–4 were refused (205) without moving. **The model's
  lane-free route to Dock 1 passes where Nav2's costmap is occupied (UNRESOLVED).** Both
  recordings converted with `coco_lab_ros.adapter` (summary detail): run 1 1,335,732 bytes,
  3,416 messages, sha256 `25a5ec80285b5627dfa760da224395ca9f51d3ae696b48abb64e9e635d12dc10`;
  run 2 832,554 bytes, 2,111 messages, sha256
  `c165a5e770af1dcde7d1298c6cfe4c544d2ee5fc943df651b9ea8b9234c2fd48`. A complete STACK ghost
  of the round was not recorded.
