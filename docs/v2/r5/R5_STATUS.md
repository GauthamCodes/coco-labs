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

Re-check at the start of the R5.1 session (2026-11-24): `df -B1 /` 7,552,487,424 bytes available; `docker images` lists only `coco-verifier:latest` (208 MB); `ps aux` shows `dockerd` and no Gazebo, Isaac or ROS 2 process.

Also reused for R5.1 (found in this session): tools/m6/m6f8_run.sh, the Gazebo + Nav2 bring-up of every recorded Depot STACK run (teleport, derivation-5 odometry calibration, `arbiter.launch.py initial_mode:=nav`, `nav.launch.py arbiter:=true`, the ten Nav2 lifecycle nodes); the committed derivation-5 checksums (docs/v2/g2/data/g29/*_outputs_d5.json, whose spec_sha256 equal today's specs) and R3.4's recorded clutter world and map sha256s; setup_env.sh's DDS and gz settings; tools/r2/verifier.Dockerfile's interpreter and PyYAML pins.

## R5.1 · ghcr.io/gauthamcodes/coco-ros2 — authored 2026-11-24, NOT built, NOT verified

Authored: docker/coco-ros2/ (Dockerfile; entrypoint `coco-ros2 --level depot`; gen_levels.py and levels.json; check.py; ws_probe.mjs; odom_relay.py; foxglove_bridge.yaml; level_env.py), .github/workflows/coco-ros2-image.yml, tools/r5/preflight_pull.sh, lab_web/tools/test_r5_coco_ros2_image.py, a README section and docs/DOCKER.md "coco-ros2 (R5.1)".

- Slim and headless: `ros:jazzy-ros-base-noble`, Gazebo server only with Xvfb software OpenGL (COCO's URDF has a `gpu_lidar` and an `rgbd_camera`), Nav2, CycloneDDS, foxglove_bridge. No desktop, MoveIt, torch, mission, perception, coco_web or web_video_server.
- Levels depot, depot_colours, depot_clutter (generated at build time; the build fails unless byte-identical to the committed records) and arena (COCO's own world, stock).
- The bridge whitelists only `/cmd_vel_teleop`, `/mission/mode`, `/goal_pose` and `/initialpose` for client publishing and drops the `parameters` and `services` capabilities.
- CI gates in order: build; unpacked size ≤ 4,000,000,000 bytes (a budget chosen from the free bytes above, not a measurement) and every level verified; start with the README command; in-container acceptance (Nav2 active; /scan /odom /tf /map /plan /cmd_vel exist; arbiter the only wheel publisher; /scan, /odom, /clock arriving); the bridge probed from outside (wheel topic gains no publisher). Only then push (`sha-<12>`, the branch name; `latest` from main), then the registry's compressed size and anonymous access.
- `/odom` is a relay of `/diff_drive_controller/odom` (COCO's topic). The Depot's actors are not driven in the image (actor_scenario.py not started).

**Not verified — nothing above has been executed.** This session's permission mode refused, without prompting, every command that runs code or reaches the network: `python3 -c`, the test venv's python, node, `docker manifest inspect`, `apt-cache policy`, `dpkg-query`, `git fetch`, `git push --dry-run`, `gh auth status`, `gh run list`, `chmod`, `git add`. File edits were allowed, so **this work is uncommitted** in the worktree (branch still at 06edc9c). So: no test run (not even the new tests), no CI run, no image, no push, no size measured, no laptop measurement, no apt package or foxglove_bridge parameter checked. Assumed and unverified: the apt package names, `ros:jazzy-ros-base-noble`, foxglove_bridge's `capabilities` and `client_topic_whitelist` parameters and its protocol fields, Xvfb + llvmpipe being enough for `gpu_lidar`, `docker buildx imagetools` on the runner, GHCR accepting the first push with GITHUB_TOKEN.

R5.2–R5.6, the localisation v1.1 suites and the leaderboard matrix: not started (each needs code to be run and measured).

## R5.1 · verified 2026-11-26 (a session that can run code)

- Disk: 6.2 GB free at the start; a cleanup of caches and unused versions freed 5.52 GB -> 12 GB
  (`~/CLEANUP_LOG_2026-11-26.tsv`; `~/coco_lab_runs` untouched). Deviation: two **unpinned** Playwright builds
  (`chromium-1255`, `chromium_headless_shell-1255`) were removed from the browser test cache; the pinned ones
  (playwright 1.64.0: chromium-1248, its headless shell, firefox-1555) stay. Cause of `/var/log` 6.6 GB: an NVIDIA
  driver flood 2026-11-15..21 (`NVRM: dmaAllocMapping: can't alloc VA space`), stopped; sudo items are Gautham's.
- **apt (packages.ros.org, laptop's index):** all 18 runtime packages exist (e.g. `ros-jazzy-foxglove-bridge`
  3.6.3, `ros-jazzy-navigation2` 1.3.14, `ros-jazzy-gz-ros2-control` 1.2.20, `xvfb`, `tini`); the image gets a newer
  ROS sync than the laptop (laptop navigation2 1.3.12).
- **Base image:** `ros:jazzy-ros-base-noble` exists (`docker manifest inspect`: amd64, arm64).
- **foxglove_bridge 3.6.3** (its .deb, unpacked, not installed): `capabilities`, `client_topic_whitelist`,
  `topic_whitelist` are real parameters; `clientPublish`, `connectionGraph`, `parameters`, `parametersSubscribe`,
  `services`, `assets` are its capability names; the launch default enables all six (the image's YAML keeps two);
  `remote_access` defaults to false. The entrypoint starts it with `ros2 run ... --params-file`, so the YAML applies.
- `pytest lab_web/tools/test_r5_coco_ros2_image.py`: **16 passed**.
- `docker/coco-ros2/gen_levels.py` run locally: depot, depot_colours, depot_clutter **identical** to the committed
  checksums; arena stock (7.5 MB).
- Still NOT verified: the image build, its size, the in-container acceptance and the bridge probe (CI, next).

## Decisions from Gautham, 2026-11-26

1. **R5.2 control path: (a).** The browser publishes only `/cmd_vel_teleop`, `/mission/mode`, `/goal_pose` and
   `/initialpose` through foxglove_bridge (the image's `client_topic_whitelist`); every wheel command stays behind
   `cmd_vel_arbiter` (STOP is the arbiter's). README invariant 2 gets a dated amendment for a visitor's own local
   LIVE container only; COCO Lab's MODEL and the Stack tab keep `coco.v1`.
2. **GHCR:** Gautham makes `ghcr.io/gauthamcodes/coco-ros2` public on its package page after the first green push;
   anonymous access is then re-checked.

## Questions for Gautham (R5)

1. **Control path for R5.2.** README invariant 2 says browser code that controls COCO's Stack never names a ROS topic and speaks `coco.v1`; R5.2 asks the joystick to publish `/cmd_vel` through the arbiter over a ROS bridge. Options: (a) the browser publishes `/cmd_vel_teleop`, `/mission/mode`, `/goal_pose` through foxglove_bridge (the image's whitelist keeps everything behind the arbiter) and invariant 2 is amended for a visitor's local LIVE container; (b) control stays `coco.v1` (platform_server in the image, a second port; coco_web is frozen and arena-shaped, so it may need changes) and the bridge is read-only. Default until you decide: no browser control code is written.
2. **GHCR package visibility.** A first push creates `ghcr.io/gauthamcodes/coco-ros2`; GitHub documents new packages as private, and only the package settings page makes one public. The one-command promise needs it public. Your call (and any storage cost of a private package).
3. **Permissions for the next session.** R5 needs, without a prompt: docker (build/run/pull/manifest), the test venv's python, node, `git push`, and `gh` (run watch, artifacts, PR, merge, workflow dispatch).

## Next step

With those permissions: run `pytest lab_web/tools/test_r5_coco_ros2_image.py` and the three suites; commit the authored files as `[R5.1]`; push `v2/r5-live-ros2` (the workflow runs on push); watch `coco-ros2 image`; fix until green; record its size.json, check.json and probe.json here; then on the laptop `bash tools/r5/preflight_pull.sh` before any pull, and R5.2 once question 1 is answered. (`chmod` was refused too: the new scripts are committed without the executable bit; the image sets its own modes, and every documented command names its interpreter.)
