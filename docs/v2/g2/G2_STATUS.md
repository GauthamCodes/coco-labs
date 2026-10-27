# G2 · Sim Identity — status

Prompt: [`G2_PROMPT.md`](G2_PROMPT.md). Starting point: [`../g1/G1_REVIEW.md`](../g1/G1_REVIEW.md) §4–§5.

## Now

- **State (2026-10-28): G2.9 "Polish before deploy" done** (PR #28, not merged, not deployed). Results:
  [`G2_RESULTS.md`](G2_RESULTS.md) § G2.9; looks: [`BEFORE_AFTER.md`](BEFORE_AFTER.md) § G2.9.
  - Item 1: touch-to-motion > 1 s was a `?perf` artefact present at G1.13 (fixed, 8e66c6d) plus a real ≤ 0.1 s
    wait for an input amended late into a tick (pacing, 2977762). Real phone, final build: 0 samples over 1 s;
    GAME medians 142 / 149 / 184 ms (≤ 150 in 2 of 3; not the hot 10-minute run); SIM pooled 134 ms.
  - Items 2–3: RViz-style SIM (dark, grey map, costmaps off on phones, TF labels with leader lines) and every
    "Looks wrong" item; real phone 60 fps median in every GAME and SIM run.
  - Item 4: derivation 5 (actors' scenario rule, odometry multiplier 1.10 → 1.323). Gate 40/40; turn scale
    1.2029 → 0.9986; AMCL residual unchanged (~0.15 m, ~8.6 cm south); park-in-lane check: actors stop,
    0 overlap. Driver defect in 5 runs fixed (0aa17e4); its 5 replacement runs 5/5.
- **State (2026-10-27): G2 · Sim Identity CLOSED, PR #28 ready for review (not merged, not deployed).**
  G2.0–G2.8 done; Rules 5, Fetch by colour, the no-WebGL hotfix and the per-round Gazebo gate (every
  round 5/5 on derivation 4) folded in. Final suites green ([`data/g28/close/`](data/g28/close/)); real
  phone 60 fps median in GAME and SIM; AUTO gap re-measured on a quiet laptop (106 / 110 ms). Results:
  [`G2_RESULTS.md`](G2_RESULTS.md). Next: Gautham's review of PR #28 and of BEFORE_AFTER.md's "Looks wrong".
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
- **Fetch by colour** (owner request 2026-10-24, branch `v2/g2-fetch-colour` from `c695cd5`):
  four rods (red 20 / green 24 / blue 28 / yellow 32 mm) in a row on a derived level
  `coco_depot_colours_v1`; game `fetch_colour`, one order to Dispatch, timers 83.6–102.2 s;
  all four colours delivered in the browser (desktop RTX 4050; one emulated phone run), records
  replay in CPython; Depot bytes and goldens unchanged. [`data/fetch_colour/README.md`](data/fetch_colour/README.md),
  [`screens/fetch_colour/`](screens/fetch_colour/).

- **Rules 5 (owner report 2026-10-24; first built on branch `v2/g2-actor-yield`)** ([`data/rules5/README.md`](data/rules5/README.md)):
  in AUTO the forklift drove through a stopped COCO (actors are a schedule; nothing checked an actor
  moving onto COCO). Fetch Rush rules 5: the actors stop for COCO (`actors.yield=1`) and AUTO waits,
  re-plans around a stopped actor or backs off (`avoid.on=1`); Free Drive on the Depot too. Rules 1–4
  unchanged (every reference replays to its chain; v3 goldens identical). Rounds = rules 4's draw;
  phone timers unchanged (≤ 6:00). Browser check: before 114 overlap ticks, after 0. The Gazebo
  stack's actors still never yield (STACK comparisons say so).
  **Carried onto `v2/g2-sim-identity` 2026-10-25** (the session was cleared mid-work; backup
  `~/g2-wip-2026-10-25.patch`): `v2/g2-actor-yield` (fe210ef, 7 commits from `c695cd5`, never pushed,
  worktree `~/coco_labs_ws/worktrees/g2-yield`) is the same work done standalone; the g2 copy holds all
  of it (25 files byte-identical; `games.py` takes the yield set-up as a parameter) **plus Fetch by
  colour rules 2** (rules 5's actors through the same helper; rounds `…fetch_colour.r2.json`; rules 1
  kept for its records). The branch is folded in by a merge that keeps its history and changes no
  file, so it is retired, not deleted. **Re-run on the g2 tree** ([`data/rules5/g2_rerun.md`](data/rules5/g2_rerun.md)):
  every reference replays (r2 4/4, r3–r5 12/12 each), goldens and game references unchanged, colour r2
  rounds regenerate identical; forklift check 0 overlap ticks; four colours delivered (each record
  replays in CPython); suites green after wrapping two long lines (flake8) and re-running
  update_isolation alone.
- **Fetch by colour merged again 2026-10-25** (its last three commits: toast hidden through the
  results, results fit a phone, colours level compiled for Gazebo/Nav2, tactical map can no longer go
  black, GPU-lost notice): conflicts in a telemetry comment (G2's wording kept) and its README;
  vitest 607, tools 68, check_dist clean; four colours + phone delivered under rules 2, records replay.
- **Hotfix (no WebGL)**: `v2/hotfix-webgl-fallback` (PR #29 into main), b745ceb: the message page
  says what to try and links to Compare and Recordings; Compare runs without 3D (results listed, map
  replaced by a note). `webgl_fallback_check.mjs` 10/10 pages with WebGL refused and working.
  Evidence `docs/v2/hotfix_webgl/`. **Merged into G2 2026-10-25** (it replaced the first form,
  d43115d); the check on the G2 build: 10/10 pages.
- **Per-round Gazebo gate (3b), RUNNING since 2026-10-25 18:4x UTC:** `tools/g2/round_gate.sh
  ~/coco_lab_runs/g2/round_gate 5 colour:red colour:green colour:blue colour:yellow phone:2 phone:6
  phone:1 phone:3` (COCO_WS `~/coco_lab_g2_ws`; output `~/coco_lab_runs/g2/round_gate.out`, per-run
  lines in `round_gate/gate_rounds.jsonl`). Depot: `gen_d2v2` (G2.6's gate files); colours level:
  `gen_colours_d2_gate` (same flags, map 0.05 m; checksums committed). Smoke (first Gazebo run of the
  four-rod level, yellow): both legs SUCCEEDED. If the session is cleared mid-gate: read
  `round_gate.out`, and re-run only the rounds without 5 counted runs (a void/refused run is retried, not
  counted). Then convert one passing run per round (`tools/g2/make_ghost.py`), extend
  `tools/g2/ghost_index.py`, write `data/g28/round_gate/` (README + per-run legs).
- **Gate so far (2026-10-25/26):** red, green, blue, yellow 5/5 each; phone seed 2 5/5; **phone seed 6
  0/2 → cannot pass** (run 1: maze leg 104 PATIENCE_EXCEEDED; run 2: maze-exit leg 105
  FAILED_TO_MAKE_PROGRESS). Diagnosed from run 2's bag (scripts in the job's tmp, to be committed with the
  write-up): the global plan is clear (>= 0.615 m from mapped walls), no unmapped body near, wheels follow
  commands; **DWB commands ~0 (v 0, w ~±0.03) for ~40 s at a time beside obj_maze_2's pre-grasp pose**,
  collision-monitor PolygonSlow (0.3) shrinks it further; only recovery spins move it. G2.6's single
  runs already took 159-178 s on this leg. All gate runs at RTF 0.41-0.50 (CPU 91 °C, browsers busy; G2.6
  ran at 0.80). **Next:** let seeds 6, 1, 3 finish (baseline); then derivation 3 = derivation 2 + Nav2's
  RotationShimController around DWB (installed, never tried; C2-NAV.21's DWB tweaks made standing still
  more attractive); A/B on the maze round; if better, re-gate every round 5/5 (params change).
- **Gate fix (2026-10-26):** derivation 3 (RotationShim around DWB, 53a23f9): seed 6 **1 of 2**, stopped
  (DWB still stood still at the maze corner, already facing the path). **Derivation 4 (Regulated Pure
  Pursuit in place of DWB, c1afe72): seed 6 5 of 5** (maze entry 39.3-39.8 s, exit 70.4-71.8 s; legs end
  0.22-0.41 m from the goal by truth). **Re-gate on derivation 4 RUNNING:** `GEN_DEPOT=…/gen_d4/coco_depot_v1
  GEN_COLOURS=…/gen_d4/coco_depot_colours_v1 tools/g2/round_gate.sh ~/coco_lab_runs/g2/round_gate_d4 5
  colour:red colour:green colour:blue colour:yellow phone:2 phone:1 phone:3` (output appended to
  `round_gate_d4.out`; seed 6's 5 runs are in the same dir). If cleared: count what is in
  `round_gate_d4/gate_rounds.jsonl`, re-run only rounds without 5 counted runs. Derivation-2 results
  (colours 5/5, seed 2 5/5, seed 6 1/5) stay as the baseline in `round_gate/`.
- **Per-round gate DONE 2026-10-26 ([`data/g28/round_gate/README.md`](data/g28/round_gate/README.md)): derivation 4
  (Regulated Pure Pursuit), all 8 rounds 5 of 5 (40/40 runs, 160/160 legs, 0 void)**; ghosts from run 1 of
  each round (4 colours + rules-5 phone seeds 1, 2, 3, 6). Cost, measured: legs end 0.34-0.37 m (median)
  from the goal by truth vs derivation 2's 0.20-0.27 m. Next: G2.8 close.
- **Real phone done 2026-10-25** ([`data/g28/real_phone_final/`](data/g28/real_phone_final/)): GAME 10 min 60 fps
  median, SIM 60; it found and the fix closed two /rosout layout defects (12aa0ab).
- **PAUSED 2026-10-26 ~21:45 IST on Gautham's request** (he needs Gazebo/RViz for other work; resume only when he
  says so). Nothing of mine is running. **G2.8 close, what is left:** (1) final suites: done up to saved_view
  ([`data/g28/close/suites_partial.txt`](data/g28/close/suites_partial.txt): coco_lab 1158, tools 244, vitest,
  native gate exact, coco verify 18/18, build twice, update isolation, det v1 and terrain identical, screenshots,
  saved view) — **chase_hud FAILED at the real phone's 803 × 361**: the collapsed /rosout (now narrowed to stop
  before the telemetry strip) wraps to 2 lines and its box overlaps the joystick's
  ([`…/chase_hud_failed_803x361.json`](data/g28/close/chase_hud_failed_803x361.json)). Planned fix: on short
  screens (max-height 420 px) clamp the collapsed line to 1 line (the prompt: "on phones it shows the last line
  only"); then re-run chase_hud, rosout_room_check, vitest, and the steps not run (v1_links, replays, packages).
  (2) after screenshots (`tools/g1/screens.mjs`, `review_shots.mjs`, as BEFORE_AFTER.md §1–2) + BEFORE_AFTER.md;
  (3) quiet-laptop AUTO-gap re-measure (`tools/g1/fetch_timing.mjs`); (4) G2_RESULTS.md tests table (sections for
  the gate, Rules 5, colour, hotfix, phone are written); (5) mark PR #28 ready for review. Never merge.
- **Next (owner's order, 2026-10-25):** (1) Rules 5 committed + pushed → (2) merge
  `v2/g2-fetch-colour` (abc039f; its last three commits are not in G2) → (3a) merge the hotfix →
  (3b) Gazebo per-round gate, 5/5 for each distinct phone round (seeds 1, 2, 3, 6) and each colour
  round, a ghost per passing round, the four-rod level's first Gazebo run → (3c) G2.8 close; PR #28
  (already open as a draft) marked ready for review. Never merge or deploy.

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

## Gautham's decisions, 2026-10-27 (G2.9, after reviewing PR #28)

Recorded in `docs/STATUS.md`'s plan-change log.

1. **Keep Regulated Pure Pursuit** in the generated Nav2 params for driving recordings. A precise grasp
   approach is later M6 work.
2. **Gazebo actors yield to COCO like Rules 5**, scripted in the generated world and labelled as a scenario
   rule. Re-run the 5/5 round gate after the change.
3. **Calibrate the odometry turn scale in the generated Gazebo files only** (never COCO's robot repo), to
   remove the 14.5 % over-rotation. Then re-measure AMCL's residual error and report it.
4. **Title tagline** becomes "Drive COCO, a ROS 2 robot, modelled in your browser."

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
| G2.8 Close | **done 2026-10-27** | [`G2_RESULTS.md`](G2_RESULTS.md), [`BEFORE_AFTER.md`](BEFORE_AFTER.md), [`data/g28/`](data/g28/) |
| G2.9 Polish before deploy | **done 2026-10-28** | [`G2_RESULTS.md`](G2_RESULTS.md) § G2.9, [`data/g29/`](data/g29/), [`BEFORE_AFTER.md`](BEFORE_AFTER.md) § G2.9 |

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

1. The marked crossings are the walkers' own paths, so COCO can never cross there clear of a walker
   (0 of 600 start times). Move or widen them, or keep "routes never cross"? (open since G2.1)
2. *(Answered 2026-10-27: calibrate in the generated files; done in derivation 5.)*
3. AMCL's residual (~0.15 m at leg ends, a ~8.6 cm southward mean offset) is **unchanged** by the odometry
   calibration. Investigate in a later milestone, or accept with the gate passing?
4. *(Answered 2026-10-27: keep RPP for driving recordings.)*
5. *(Answered 2026-10-27: Gazebo's actors yield by a scenario rule; done.)*
6. Touch-to-motion on a hot phone (battery ≥ 41 °C) is 184 ms in GAME; the remaining cost is the model's own
   step (65–96 ms on the phone). Accept, or make the model's per-tick Python cheaper (results unchanged) in a
   later milestone?
