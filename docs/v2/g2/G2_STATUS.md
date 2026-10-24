# G2 · Sim Identity — status

Prompt: [`G2_PROMPT.md`](G2_PROMPT.md). Starting point: [`../g1/G1_REVIEW.md`](../g1/G1_REVIEW.md) §4–§5.

## Now

- **Current checkpoint:** G2.0 Baseline done (2026-10-24): every suite green on main `7475896`;
  before screenshots on the laptop (NVIDIA), the emulated phone and the real phone.
- **Next step:** G2.1 — Fetch Rush rules 4 (the crossing rule), the budget sweep, the fps toast.

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
