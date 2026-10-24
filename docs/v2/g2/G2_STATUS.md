# G2 · Sim Identity — status

Prompt: [`G2_PROMPT.md`](G2_PROMPT.md). Starting point: [`../g1/G1_REVIEW.md`](../g1/G1_REVIEW.md) §4–§5.

## Now

- **State (2026-10-24, later):** G2.0–G2.7 done; G2.8 mostly done — suites run, real phone done
  (SIM 60 fps with every display on, after fixing a saved-SIM-view defect the phone found; GAME 10 min
  median 60 with dips; touch-to-motion > 1 s samples UNRESOLVED). Owed: ament lint fix, AUTO-gap
  re-measure, per-round Gazebo gate, after screenshots + BEFORE_AFTER.md, the PR. Results:
  [`G2_RESULTS.md`](G2_RESULTS.md).
- **G2.1** ([`data/g21/README.md`](data/g21/README.md)): rules 4 implemented; both marked crossings are
  the walkers' paths (0 of 600 start times clear), so no route crosses the lane. Phone budget **26 m**
  (no budget 22–81 m meets 5:00; 26 m is the smallest meeting 6:00: 4 distinct rounds, 4:35.9–5:49.1);
  the 5:00 sweep runs on to the longest trip (152.4 m). fps toast done.
- **G2.2–G2.4** ([`data/g22/README.md`](data/g22/README.md)): GAME | SIM, telemetry, /rosout, panels;
  laptop 60 fps in both views (NVIDIA, high); HUD check incl. SIM: 0 failures.
- **G2.5** ([`data/g25/README.md`](data/g25/README.md)): rosbag2 export proven with ros2 bag info/play + RViz.
- **G2.6** ([`data/g26/DIAGNOSIS.md`](data/g26/DIAGNOSIS.md), [`GATE.md`](data/g26/GATE.md)): AMCL updating
  only every 0.25 m / 0.2 rad, and the unmapped `bad_crate`, let a wrong likelihood peak capture AMCL
  (0.35–0.40 m off) → START_OCCUPIED at the pallet gap. Fixed in the generated files (derivation 2);
  gate 5/5 (20/20 legs). Ruled out by measurement: map alignment, SDF collisions, scan stamps, wheel
  odometry (it over-rotates 14.5 % but perfect odometry drifts more). A "COCO sees itself" reading
  was retracted.
- **G2.7** ([`data/g27/`](data/g27/)): env map, SSAO (high), COCO materials, title, results inset,
  Race Nav2 + three-way results; budgets within every tier (incl. SIM).
- **Next step:** finish the ghosts and the suites, G2.8's documents, a draft PR; then the phone checks.

## Setup facts

- PR #27 **is merged** (main `7475896`, 2026-10-23 16:56 UTC; it also carries M5 #25 and the
  M6 foundations) → branched `v2/g2-sim-identity` from `origin/main` `7475896`.
- Worktree `~/coco_labs_ws/worktrees/g2` (outside `.claude/worktrees`). ROS overlay
  `~/coco_lab_g2_ws` (built when needed). Raw Gazebo runs go to `~/coco_lab_runs/g2/` (new
  directory; existing evidence there is read-only).
- Laptop: i5-13420H, RTX 4050 driver 580.178.04, power profile **balanced, on AC**
  (checked 2026-10-24). No simulator running at start. Nothing Phone (1) attached over adb.
- Naming: "G2" also labels an older open question in `docs/STATUS.md` ("G2 priority/batch
  windows"). This milestone is always written "G2 · Sim Identity"; that one "question G2".

## Gautham's decisions, 2026-10-23 (on G1.13's open items; the G2 prompt §1)

Recorded in `docs/STATUS.md`'s plan-change log.

1. **Phone round variety:** Fetch Rush routes may cross a forklift lane only at a marked
   (hazard-striped) crossing, never run along a lane. Then the smallest budget giving at least
   3 distinct rounds with timers ≤ 5:00, or ≤ 6:00 if 5:00 is impossible.
2. **AUTO stall** (119–141 ms vs the 100 ms target) accepted for now, tracked open. No G2 time
   on it unless a G2 change makes it worse (re-measured at G2.8).
3. **Heavy saved settings on phones:** never override silently; if fps stays under 55 for
   10 s, a one-tap "Switch to recommended settings" toast.
4. **Old phone screenshots in git history** (status-bar icons only) accepted; no history rewrite.

## Gautham's answers in planning, 2026-10-24

1. **The crossing rule covers the east–west forklift lane only** (`zone_forklift_lanes`, the
   lane rules 3 already excludes). Routes cross it only at its two striped crossings (where the
   walkers cross, x ≈ 24.2 and x ≈ 40) and never run along it. The north–south lane is unchanged.
2. **/rosout lines use the M6F.7 model graph's node names** (`global_planner`,
   `local_controller`, `slam_or_amcl`, `cmd_vel_arbiter`, …), so `[INFO] [global_planner]: …`
   rather than the prompt's `planner_server` example. The graph panel and Learn show each
   node's Stack counterpart (planner_server, controller_server, amcl, …) as plain text.

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| G2.0 Baseline | done | [`data/g20/README.md`](data/g20/README.md): suites ([`suites.txt`](data/g20/suites.txt)), before shots [`screens/before/`](screens/before/), real phone 1 min 60 fps median |
| G2.1 Decisions | done | [`data/g21/README.md`](data/g21/README.md): rules 4 (crossings measured closed), budget 26 m (6:00 rule), fps toast |
| G2.2 GAME \| SIM switch and SIM view | done; real phone SIM 60 fps | [`data/g22/README.md`](data/g22/README.md), [`screens/g22/`](screens/g22/) |
| G2.3 Telemetry | done | same; `test/g2_telemetry`, `test/g2_rosout` |
| G2.4 Panels | done | same; `test/g2_panels`; panel vs STOP: no overlap |
| G2.5 rosbag2 export | done | [`data/g25/README.md`](data/g25/README.md): ros2 bag info / play + RViz |
| G2.6 Real ROS 2 ghost | done: gate 5/5, 4 ghosts 16/16 legs, Race Nav2 | [`data/g26/DIAGNOSIS.md`](data/g26/DIAGNOSIS.md), [`GATE.md`](data/g26/GATE.md) |
| G2.7 Looks | done; real phone GAME 60 fps median | [`data/g27/`](data/g27/), [`screens/g27/`](screens/g27/) |
| G2.8 Close | in progress | [`G2_RESULTS.md`](G2_RESULTS.md), [`data/g28/`](data/g28/) |

## Gautham: look at these

- Before: [`screens/before/review/`](screens/before/review/) (NVIDIA, 1440 × 900),
  [`screens/before/screens/`](screens/before/screens/) (desktop + emulated phone),
  [`screens/before/real_phone/`](screens/before/real_phone/) (real phone, status bar checked).

## Deviations so far

- The G2 checks serve `dist` on port 4184: a G1-era server (not this session's) still holds 4174.
- Two of G2.0's four real-phone screencaps were not committed (a heads-up alarm notification).
- /rosout node names follow the model graph, not the prompt's Nav2 examples (Gautham's answer,
  2026-10-24).
- SIM view keeps the pause button and the MODEL chip with STOP, the joystick, the primary action and
  the switch (pause holds the menus, incl. the rosbag2 export; the chip is an honesty invariant).
- SIM's "local trajectory candidates": the model's waypoint follower samples none, so SIM draws the
  commanded arc and says so; localisation: Play has no localiser (belief = truth), so no particle
  cloud or ellipse is drawn.
- The Gazebo-style bar is shown on desktop in SIM view (read as "desktop and SIM view only").
- Foxglove was not tried (not installed on the laptop).
- Phone round rule: no route crosses the lane (both marked crossings measured unusable); the budget
  follows the 6:00 fallback (26 m).

## Questions for Gautham

1. The marked crossings are the walkers' own lanes, so COCO can never cross there clear of a walker
   (measured, 0 of 600 start times). Move or widen the crossings, or keep "routes never cross"?
2. Wheel odometry over-counts rotation by 14.5 % (the robot's ros2_control config, frozen). G2 fixed
   the Depot in the generated Nav2 params; should the robot config be corrected in a future milestone?
3. AMCL still ends legs up to 0.28 m off (a residual bias, not explained). Investigate further, or
   accept with the gate passing?
