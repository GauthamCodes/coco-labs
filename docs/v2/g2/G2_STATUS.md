# G2 · Sim Identity — status

Prompt: [`G2_PROMPT.md`](G2_PROMPT.md). Starting point: [`../g1/G1_REVIEW.md`](../g1/G1_REVIEW.md) §4–§5.

## Now

- **Current state (2026-10-24, session paused at the usage limit): WORK IN PROGRESS, commit `[G2.x WIP]`.**
  G2.0 done. G2.1–G2.5 built and unit-tested; G2.6 diagnosis started. Not yet run: the full suites
  after G2.0, the real phone in SIM view, the final rules-4 rounds file.
- **G2.1:** rules 4 implemented (`games.py`, `tools/g2/make_fetch_rush_rounds_r4.py`, tests). Measured
  (`games.crossing_windows`): both marked crossings are the walkers' own paths, paced end to end; 0 of
  600 start times let COCO cross without touching the walker, so both are closed and no route crosses
  (the rule is kept by never crossing). **Question for Gautham:** offset/widen the crossings, or accept
  that routes never cross? The budget sweep (`tools/g2/sweep_phone_budget_r4.py`, 5:00 then 6:00) was
  running when the session stopped; 22–32 m: no budget with every timer <= 5:00. The committed
  `coco_depot_v1.fetch_rush.r4.json` is PROVISIONAL (22 m, written before the crossing windows):
  regenerate with the chosen budget. fps toast done (`fps_watch.ts`).
- **G2.2–G2.4:** GAME | SIM switch, SIM view (grid, TF incl. arm frames, LaserScan, Map, global/local
  costmaps in RViz's palette, plans, footprint, goal, RViz orbit camera), telemetry strip, Gazebo bar,
  /rosout, panels (Displays, ROS 2 graph (model), Topic echo, Plot, Learn). Parity test: TS shapes =
  `coco_lab.ros_shapes` (1e-12). Chase HUD check + SIM pass: 0 failures on 3 profiles. Real phone SIM
  fps: NOT measured yet.
- **G2.5 done on the laptop:** see [`data/g25/README.md`](data/g25/README.md) — CDR bytes equal rclpy's;
  `ros2 bag info` accepts the browser's file; `ros2 bag play` + RViz shows map, scan, TF, plan.
- **G2.6 diagnosis (from M6F.8's recorded bags, offline):** map and world agree (scan fits the truth,
  best offset <= 0.05 m); wheel odometry over-counts rotation by 14.5 % (12.13 vs 10.59 rad; distance
  within 2 %); AMCL inherits the heading error and ends 0.35–0.40 m SW; at the 0.8 m pallet gap that
  puts the believed pose inside the 0.206 m inscribed radius (205 START_OCCUPIED). Unmapped bodies near
  the route: `bad_crate` (44.5, 7.5), the parked walker (40, 8.75), the parked N–S forklift. Offline
  Nav2-AMCL replay (`tools/g2/amcl_replay.py`) reproduces the drift (0.398 m); 12 m range + 240 beams
  alone does not fix it (0.405 m). Next: replay variants (laser weights, update thresholds, map with
  objects), then derivation 2 and the 5/5 Gazebo gate.
- **Next step:** let the sweep finish (or rerun it: `tools/g2/sweep_phone_budget_r4.py --trips-cache …
  --max-timer 300`, then 360), regenerate r4, run `tools/g2/suites.sh`, real-phone SIM fps, then
  commit G2.1–G2.5 properly and continue G2.6.

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
| G2.1 Decisions | pending | |
| G2.2 GAME \| SIM switch and SIM view | pending | |
| G2.3 Telemetry | pending | |
| G2.4 Panels | pending | |
| G2.5 rosbag2 export | pending | |
| G2.6 Real ROS 2 ghost | pending | |
| G2.7 Looks | pending | |
| G2.8 Close | pending | |

## Gautham: look at these

- Before: [`screens/before/review/`](screens/before/review/) (NVIDIA, 1440 × 900),
  [`screens/before/screens/`](screens/before/screens/) (desktop + emulated phone),
  [`screens/before/real_phone/`](screens/before/real_phone/) (real phone, status bar checked).

## Deviations so far

- The G2 checks serve `dist` on port 4184: a G1-era server (not this session's) still holds 4174.
- Two of G2.0's four real-phone screencaps were not committed (a heads-up alarm notification).
- /rosout node names follow the model graph, not the prompt's Nav2 examples (Gautham's answer,
  2026-10-24).

## Questions for Gautham

(none open)
