Claude Code prompt — R5 · Real ROS 2 in the browser, Run it in ROS 2, World editor

Run on the laptop: cd ~ && claude, Opus at the highest effort, the lid open, gh auth status logged in. To resume later, paste only: Continue COCO Lab R5: read docs/v2/r5/R5_PROMPT.md and R5_STATUS.md, then carry on.

Continue COCO Lab (repo GauthamCodes/coco-labs, live at https://gauthamcodes.github.io/coco-labs/), starting from main (c629821 or later). Create the worktree ~/coco_labs_ws/worktrees/r5 on branch v2/r5-live-ros2. Save this prompt as docs/v2/r5/R5_PROMPT.md, track progress in R5_STATUS.md, commit [R5.n] per step and push.

All earlier rules and the standing authority still apply:

merge and deploy under the gate, run the live smoke test, revert if it breaks
evidence labels are truthful
never invent numbers
no destructive git commands
never touch the COCO robot repo
one simulator at a time, and only when nothing else runs (Gautham's FR3 internship work comes first)
The goal

Today the browser shows a model shaped like ROS 2, and real ROS 2 appears only as recordings. R5 adds three things:

LIVE ROS 2. The website connects to a real ROS 2 stack running in Docker, and draws its real topics.
Run it in ROS 2. Any level and scenario downloads as a package that runs on stock ROS 2 Jazzy.
A world editor. Build a level in the browser; it becomes a browser world, a Gazebo world and a Nav2 map.
Rules against guessing (read before writing code)
Find and reuse what already exists before building anything new:
the Live Stack tab, platform_server and its Docker quickstart (the coco.v1 protocol)
the World Spec v3 kit and validator
gen_level and the generators (SDF, Nav2 map and params)
the M6F.7 ROS message shapes
the R2 ROS 2 package exporter
SIM view and its Displays panel
List what you found in R5_STATUS.md before step R5.1.
Verify every package, image, API and command by actually installing or running it. If something doesn't exist or doesn't work, say so and pick a verified alternative; never write code against an assumed API.
A feature counts as done only if a test or a recorded run shows it working. Anything unverified is listed as "not verified" in the report.
Label every data source: MODEL (the browser model), STACK (a recording), LIVE (a real ROS 2 stack running now). Never call a model "ROS 2".
Disk: only about 7.5 GB is free. Build Docker images in CI and push them to GHCR; locally, pull only what's needed and remove old images afterwards. Never delete ~/coco_lab_runs/ or the browser test cache.
Gautham's answers to the R4 questions (record them in STATUS, dated 2026-11-24)
Localisation suites: keep v1 frozen. Add v1.1 suites loc-global-active-20 and loc-kidnap-active-20. In these, the robot may stop, rotate or explore within a time budget until it reports "localised", and the score includes time-to-localise. Re-run the built-ins and the MCL reference, and report the numbers honestly.
Leaderboard re-verify: split it into a matrix of jobs (one per suite × entry), and re-verify only entries whose suite, model, API or verifier version changed. Each job must finish in under 1 hour.
The paper: don't submit anything. Gautham will decide after a faculty member reviews it.
The phone and the study: these are Gautham's. Skip the real-phone check unless adb devices lists the phone.
Steps
R5.1 Docker image ghcr.io/gauthamcodes/coco-ros2
ROS 2 Jazzy, headless Gazebo Harmonic, Nav2, COCO's stack (built from the version COCO Lab already uses), a ROS websocket bridge (foxglove_bridge or rosbridge_suite, whichever you verify works), and COCO Lab's generated worlds.
One command starts it: docker run --rm -p 8765:8765 ghcr.io/gauthamcodes/coco-ros2 --level depot.
Built in CI and pushed to GHCR. Write a README section.
Test: the container starts, Nav2 reaches "active", and the topics /scan, /odom, /tf, /map, /plan and /cmd_vel exist.
R5.2 "Connect to ROS 2" on the website
A menu option in Play and in SIM view to connect to ws://localhost:8765 (or a URL you type). Once connected, the data source becomes LIVE.
SIM view and the panels (Displays, ROS graph, Topic echo, Plot) draw the real topics. The ROS graph shows the real nodes.
Driving: the joystick publishes /cmd_vel through COCO's cmd_vel_arbiter, never around it. STOP must work. Setting a goal sends a real Nav2 NavigateToPose.
Clear errors for: no container running, the wrong port, a version mismatch, a lost connection. Disconnecting returns to MODEL.
Note for the report: browsers may block ws://localhost from an https page in some cases. Test it in Chromium and Firefox, and document what works, with a verified workaround if needed.
Test on the laptop: connect, drive, send a goal, press STOP, disconnect. Record a short screen capture.
R5.3 Model vs LIVE side by side

Send the same goal to the browser model and to live Nav2, and draw both paths together (MODEL in one colour, LIVE in another), with path length and time for each. Reuse the R3 comparison code if it fits.

R5.4 Run it in ROS 2 (level packages)
"Download as ROS 2 package" for any level and scenario: the generated SDF, the Nav2 map and params, a launch file, the scenario goals, and a README with the exact commands.
Reuse the generators and the R2 exporter. Both a COCO Lab user algorithm and stock Nav2 can be selected.
Test: a downloaded package runs in the Docker image and on the laptop's own Jazzy install, and reaches its goals in Gazebo, on at least 2 levels.
R5.5 World editor (first version, kept simple)
A grid-snapped editor in Workbench, using the existing kit pieces (walls, doors, racks, ramps, obstacles, spawn points, goals). Place, move, rotate and delete; undo and redo.
The existing validator checks the level live, with clear errors (the robot doesn't fit, a goal is unreachable, and so on).
"Play this level" opens it in Free Drive. "Use in an experiment" works too, as does "Download as ROS 2 package". A share link encodes the level.
Test: build a small level from scratch, then play it, run an experiment on it, and run the downloaded package in Gazebo.
R5.6 Close
Verify: all suites; determinism and parity unchanged (no golden or model hash changes); Play fps unchanged; the security tests still pass.
Ship: R5_RESULTS.md and before/after screenshots. Then the PR "R5 · Live ROS 2", a self-review, merge under the gate, deploy, and the live smoke test.
Stop and report if
A golden or model hash changes.
LIVE driving can't go through cmd_vel_arbiter.
The image can't be built or kept within disk limits.
Any feature would need the COCO robot repo changed.
Final report
Steps done:
What existed and was reused:
Docker image: tag, size, CI run, topics verified
Connect to ROS 2: browsers tested, drive/goal/STOP results, localhost workaround
Model vs LIVE: example result
Level packages: levels tested, Docker and laptop results
World editor: features, test level result
Localisation v1.1 and leaderboard matrix results:
Not verified (honest list):
Tests, determinism, fps:
PRs, merges, deploys, live smoke:
Questions for Gautham:
