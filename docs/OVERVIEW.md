# COCO Lab — overview (v2 through R5, plus R6's first fixes)

*Written 2026-11-28. A plain-English summary; every number links to the committed record it comes from.
Labels: **MODEL** = the browser model (Python, also run natively); **STACK** = COCO's full ROS 2 stack in Gazebo,
recorded; **LIVE** = that stack running now in your own Docker container. All of it is simulation: no physical
robot exists.*

## What it is

COCO Lab is a website where you drive, compare and test the planning, control and localisation of **COCO**, a
small warehouse robot, against a faithful model of its ROS 2 + Nav2 stack, and then run the same thing in the real
stack. Live site: **<https://gauthamcodes.github.io/coco-labs/>** · repository:
**<https://github.com/GauthamCodes/coco-labs>** · ROS 2 image: **`ghcr.io/gauthamcodes/coco-ros2`** (public).

## What exists (v2, by milestone)

- **Play** (M1–M5, G1, G2): a 3D Depot with Free drive, Fetch Rush and colour fetches; GAME and RViz-style SIM
  views; telemetry, /rosout and ROS 2 panels — every ROS-looking element labelled MODEL or STACK. Real GPU:
  60 fps on both laptop GPUs ([G1 results](v2/g1/G1_RESULTS.md)). Gazebo's actors yield to COCO by a scenario
  rule, and the odometry is calibrated; the per-round Gazebo gate passed 40/40 ([G2 results](v2/g2/G2_RESULTS.md)).
- **Compare and the Research Workbench** (R1): experiments in the browser with honest statistics, links that
  reproduce exactly in three browser engines and natively, and COCO-Bench v0 (4 suites, 1,970 reference runs)
  ([R1 results](v2/r1/R1_RESULTS.md)).
- **Bring your own algorithm** (R2): the `coco.algorithm.v1` API, a sandboxed Algorithm Studio (escape tests pass
  in Chromium, Firefox and WebKit), native parity, a verified leaderboard — the first community entry is
  Gautham's Lazy Theta\* ([R2 results](v2/r2/R2_RESULTS.md)).
- **COCO-Bench v1 and the paper** (R3): 12 frozen suites (450 scenarios, difficulty tiers, held-out sets drawn
  from a secret), MODEL and STACK baselines, a Model-vs-ROS-2 comparison, and a paper whose numbers are generated
  from the data; "Reproduce this paper" reproduced exactly on the live site ([R3 results](v2/r3/R3_RESULTS.md)).
- **Learn** (R4): ten modules, 20 lessons in three tracks and 39 exercises, graded by one Python grader that runs
  the same in the browser and natively ([R4 results](v2/r4/R4_RESULTS.md)).
- **Live ROS 2, Run it in ROS 2, World editor** (R5): connect Play to the real stack in your own Docker container
  (read-only bridge on 8765, a `coco.v1` control gateway on 8766); every LIVE goal also runs in the model, side by
  side; any level downloads as a ROS 2 Jazzy package; a world editor builds, checks, plays and packages new
  levels. From the public site, LIVE passed 11/11 steps in Chromium and in Firefox once the browser's local-network
  permission was allowed ([R5 results](v2/r5/R5_RESULTS.md)).

## R6 so far (2026-11-28, branch `v2/r6`; not yet merged)

- **Image trimmed 3.80 → 2.68 GB** (target ≤ 3.5 GB), with no feature dropped and every acceptance check passing:
  a `ros-core` runtime, headers, static libraries and docs removed, one flattened layer
  ([CI evidence](v2/r6/data/a_image_run_46109174443/)).
- **The 2 m truth offset was ours**: the gateway used the arena's spawn point as the map origin on every level.
  Fixed; on a test route the gateway's truth now equals Gazebo's own model pose to 0.00004 m at every still stop,
  and LIVE shows truth-vs-AMCL again (up to 0.24 m at the route's stops), only when the gateway says its truth is in the level's
  map frame ([evidence](v2/r6/data/a_image_run_46109174443/truth_route.json)).
- **Actors move** in the image and in level packages, by G2.9's driver, unchanged: in a package on the laptop,
  every actor moved 100–128 m and held 63 times for COCO, with no overlap
  ([evidence](v2/r6/data/a4_package_laptop/judged.json)).
- **foxglove_bridge's ignored allowlist**: reproduced in a clean container on 3.6.3; upstream already has a draft
  fix (foxglove-sdk#1508). A ready-to-paste report is in [UPSTREAM_foxglove_issue.md](v2/r6/UPSTREAM_foxglove_issue.md).

## Key negative results (kept visible)

- MCL cannot globally localise in the Depot's symmetric aisles reliably: the R3/R4 reference managed 1/20 (global)
  and 0/20 (kidnap). In R6's first "active" run it claimed "localised" twice, wrongly ([R4 status](v2/r4/R4_STATUS.md)).
- Lab 5 (v1): DWB stalled on the hairpin 0/5; D\* Lite did 2.9× more work than A\* on the real costmap.

## Open issues

- **Real phone** measurements are not current (not connected); the five-person usability test is Gautham's.
- **The leaderboard re-verify workflow** hits its 6 h limit on main (R6 is splitting it into a matrix).
- **The paper** is ready but not submitted (Gautham's decision).
- **Browsers ask before a website reaches localhost**: LIVE needs the visitor to choose Allow (the site says so).
- WebKit runs in CI only (the laptop's WebKit runner was removed to free disk).

## What's next (R6)

Localisation v1.1 "active" suites (the robot may stop or explore until its filter reports "localised"); the
re-verify matrix; then **fidelity knobs** (LiDAR noise, odometry slip from measured Gazebo values, latency,
acceleration limits — all off by default, hashes unchanged), **more algorithms** (RRT, RRT\*, PRM, Theta\*,
Hybrid-A\*, an EKF with scan matching if it can be done honestly), and **multi-robot** (2–4 COCOs, prioritised
planning and CBS, a `multi-depot-30` suite) — MODEL only. Prompt and progress:
[R6_PROMPT.md](v2/r6/R6_PROMPT.md), [R6_STATUS.md](v2/r6/R6_STATUS.md).
