# R5 status

Base c629821. Instructions and acceptance tests are in R5_PROMPT.md.

## Decisions from Gautham, 2026-11-24

Keep localisation v1 frozen. Add loc-global-active-20 and loc-kidnap-active-20 in v1.1 with a time budget, active movement, a localised signal and time-to-localise scoring. Re-run built-ins and MCL. Use one leaderboard verification job per suite and entry with version-based invalidation and a duration below one hour. Hold the paper for faculty review and Gautham's decision. Gautham owns the study and phone. Only test a real phone when adb lists it.

## Existing implementation located before R5.1

- Live Stack UI and coco.v1 transport in lab_web/src/ui/LiveView.tsx and lab_web/src/live/. ROS endpoint in coco_web/coco_web/platform_server.py. The Dockerfile and docs/DOCKER.md describe the local appliance and historical arbiter drive tests.
- World Spec v3 kit in docs/v2/m6/WORLD_SPEC_V3.md. tools/m6/gen_level.py calls coco_lab/coco_lab/worldgen.py to produce the arena, Gazebo SDF and meshes, Nav2 map and derived parameters.
- M6F.7 message definitions and shapes in lab_web/src/ros/msgdefs.json and shapes.ts. SIM rendering in lab_web/src/game/render/simview.ts and Displays in lab_web/src/ros/displays.ts.
- R2 package export in coco_lab/coco_lab/ros2_export.py with test_ros2_export.py.

## Disk preflight

Docker and worktree share /dev/nvme0n1p5. Docker filesystem available 7,554,613,248 bytes after checkout. docs/DOCKER.md records an 8.18 GB October build. Its historical Firefox drive and STOP results apply only to that build. A smaller CI-built R5 image and every R5 runtime acceptance test remain unverified.
