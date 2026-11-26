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
- CI run 45862342162: build 95 s, 3.80 GB, levels identical, in-container acceptance PASS; the bridge probe could
  not connect: foxglove_bridge 3.x accepts only the subprotocol `foxglove.sdk.v1` (its own handshake error).
- CI run 45866330520 (probe fixed): the probe connected and **caught a bypass**: `client_topic_whitelist` is not
  applied by 3.6.3 (source: parsed, never checked), and a client advertise made `/foxglove_bridge` a second
  publisher on `/diff_drive_controller/cmd_vel`. Nothing was pushed (the push is gated on the probe).
- **R5.1 DONE.** CI run 45867550987 (`831fe48`), the bridge read-only: **PASS** and pushed
  `ghcr.io/gauthamcodes/coco-ros2:sha-831fe4817f2e` (+ `v2-r5-live-ros2`), digest `sha256:797d856d...`.
  Unpacked 3,797,579,707 bytes (budget 4,000,000,000); a pull downloads 1,124,312,927 bytes (17 layers); build
  79 s. **Public**: anonymous `imagetools inspect` after `docker logout` succeeded in CI, and the laptop pulled it
  anonymously (the package is linked to the public repository). Probe: `foxglove.sdk.v1`, capabilities
  `connectionGraph`, `time`; the six topics advertised; /scan /odom /tf flowing; a client advertise of the wheel
  topic adds no publisher (graph and ROS agree: `/cmd_vel_arbiter` only). [data/r51/](data/r51/)
- **Laptop (LIVE, 2026-11-26, AC, balanced):** `tools/r5/preflight_pull.sh` room (need 6.92 GB incl. 2 GB kept
  free); pull took 5.22 GB on disk (12 -> 6.3 GB free); README command (+ `--ulimit core=0`, the laptop's apport
  core trap) healthy after **40 s**; `coco-ros2 check`: Nav2 active, the six topics, wheel publishers
  `['/cmd_vel_arbiter']`, /scan 8.9/s, /odom 44.1/s, RTF 0.88; probe PASS. Container stopped, image removed
  (back to 12 GB). [data/r51/laptop/](data/r51/laptop/)

## Decisions from Gautham, 2026-11-26

1. **R5.2 control path: (a).** The browser publishes only `/cmd_vel_teleop`, `/mission/mode`, `/goal_pose` and
   `/initialpose` through foxglove_bridge (the image's `client_topic_whitelist`); every wheel command stays behind
   `cmd_vel_arbiter` (STOP is the arbiter's). README invariant 2 gets a dated amendment for a visitor's own local
   LIVE container only; COCO Lab's MODEL and the Stack tab keep `coco.v1`.
2. **GHCR:** Gautham makes `ghcr.io/gauthamcodes/coco-ros2` public on its package page after the first green push;
   anonymous access is then re-checked.

### Revised 2026-11-26 (Gautham), after a measured fact

foxglove_bridge 3.6.3 does not apply `client_topic_whitelist` (its source parses it and never checks it;
CI run 45866330520: a client advertising `/diff_drive_controller/cmd_vel` made `/foxglove_bridge` a second
wheel publisher). Decision 1 is replaced: **the bridge is read-only; LIVE control goes through a small COCO
gateway node in the image (its own port) that accepts only four control intents (teleop velocity, STOP/mode,
a Nav2 goal, the initial pose) and publishes only to four hard-coded topics behind `cmd_vel_arbiter`.**
README invariant 2 stays as written (control speaks `coco.v1`-style intents); no amendment.

## R5.2 · LIVE control gateway — image part DONE 2026-11-26/27 (browser part next)

- **Gateway = COCO's own `coco_web` platform_server** in the image (`remote:=true`: `/ws` and `/healthz` only;
  origin allowlist: the Pages site and localhost), port 8766. Found on the way, each measured in CI:
  1. `remote:=true` with `access:=open` is refused by platform_server itself (run 45874005506): the gateway uses
     **code access**; the CSPRNG control code is printed in the container's log (`CONTROL CODE: ...`); STOP needs
     no code. Right for `docker -p`, which publishes on every interface.
  2. Ubuntu's tornado 6.4.0 hung up every connection at its first keepalive ping, 10 s in (run 45876908783, a
     clean close without a code): the image now installs **tornado 6.5.7**, the version ci.yml pins for coco_web.
  3. My probe's blocking `docker exec` froze its own event loop (run 45874896939); made asynchronous.
- **CI run 45877911153 PASS** (`744a9f4`), pushed `ghcr.io/gauthamcodes/coco-ros2:sha-744a9f4ca2a7`, **public**;
  3,943,847,507 bytes unpacked (budget 4,000,000,000: 1.4 % left), 1,176,225,404 bytes per pull.
  `gw_probe` (LIVE, CI runner): driving without the code refused (`spectator`); claim with the code; welcome
  `coco.v1`; teleop moved COCO 0.17 m (Gazebo truth); wheel publishers `[/cmd_vel_arbiter]`, teleop-input
  publishers `[/coco_web_platform]`; STOP latched, arbiter `idle`, 0.000 m moved after; `set_mode auto` released
  the latch; a goal 1 m ahead: NavigateToPose `executing`, plan 21 points; origin `https://evil.example` 403, the
  Pages site 101. [data/r52/ci/](data/r52/ci/)

## R5.2 · Connect to ROS 2 — DONE on the laptop 2026-11-27 (live-site https check after deploy)

- **What was built.** `src/ros/cdr_read.ts` (CDR reader; rclpy goldens 13/13), `src/ros/foxglove.ts` (read-only
  foxglove_bridge client: `foxglove.sdk.v1`, never advertises/publishes; 5/5), `src/ros/live_read.ts` (the topics
  and the tick built from them; topic names stay out of `src/live`, so the invariant-2 guard is unchanged),
  `src/live/live_source.ts` (the two sockets: read = bridge, control = the coco.v1 gateway), Play (Free drive):
  a HUD button, the SIM caption link and the pause menu open "Connect to ROS 2" (bridge URL + control code); while
  LIVE the model pauses, every view and label says LIVE (SIM caption, chip, info sheet, panels, telemetry,
  /rosout-style console: "events from LIVE ticks (not /rosout)"), the ROS 2 graph panel lists the real nodes.
- **Found and fixed on the way (measured):** coco_web's dead-man zeroes a driver whose drive frames stop
  (`DRIVE_TIMEOUT_S` 0.5 s): a held stick is now re-sent at 10 Hz (one frame moved COCO 0.013 m). Headless
  Chromium's default SwiftShader drew Play at one frame per ~1.1 s and starved that timer (timer gaps 2.3 s,
  `tools/r5/frame_gaps.mjs`); on the laptop's GPU 16.7 ms frames, 100 ms timers. A device that slow fails SAFE
  (the gateway zeroes the stick). Words: a failure's text is no longer overwritten by the phase that follows it.
- **Laptop end to end (LIVE; `tools/r5/live_e2e.mjs`; image `sha-744a9f4ca2a7`, AC, balanced; served dist at
  http://127.0.0.1:4184):** Chromium (RTX 4050, ANGLE GL) and Firefox (headless, hardware renderer) **10/10 each**:
  a wrong port is said in words with the docker command, and Play stays MODEL; connect -> chip LIVE; the graph
  panel: 36 nodes, 184 topics, `/diff_drive_controller/cmd_vel` published by `/cmd_vel_arbiter` only; W for 2 s
  moved COCO 0.535 m / 0.600 m (Gazebo truth) with the arbiter in teleop; a goal: Nav2 `succeeded` (6-point plan);
  STOP: latched, arbiter idle, 0.000 m after; R released; SIM caption LIVE; Disconnect -> MODEL; 0 page errors.
  Lost connection (container stopped mid-session, Chromium): "Lost the connection to ROS 2 ... Back to the browser
  model (MODEL)", chip MODEL. Screen recording `chromium_live_session.webm`. [data/r52/laptop/](data/r52/laptop/)
- **Not verified yet:** an https page (the live site) reaching ws://localhost (browsers' local-network rules):
  after deploy, in Chromium and Firefox. Displays/Topic echo/Plot show LIVE values rebuilt in ROS 2 shapes from
  the LIVE ticks (not raw messages): labelled so. Version mismatch is unit-tested (fake server), not run live.

## R5.3 · Model vs LIVE — DONE on the laptop 2026-11-27

- Every LIVE goal (GO or AUTO) is also run in the browser model: one R1 experiment (`coco_lab.experiments`,
  family `control`, an inline scenario: start = where Nav2 believes COCO is (AMCL, the map frame both plan in),
  goal = the goal, controller `rpp`), replayed in Play's own worker, so its numbers are an experiment record's.
  The LIVE leg is followed from the goal to Nav2's verdict for THAT goal (`src/live/model_vs_live.ts`). Both paths
  are drawn (MODEL violet, LIVE amber; colour-blind-distinguishable) with distance driven and sim time.
- **Laptop (LIVE; `tools/r5/live_e2e.mjs`, 11/11 in Chromium and Firefox; image `sha-744a9f4ca2a7`):** a goal
  ~1 m ahead: Chromium MODEL 0.95 m / 3.9 s vs LIVE 0.95 m / 4.2 s; Firefox MODEL 0.94 m / 3.8 s vs LIVE 0.92 m /
  3.9 s; all `succeeded`. One goal each: an example, not a rate. [data/r53/laptop/](data/r53/laptop/)
- Found on the way, each fixed: (1) a LIVE tick said `arrived` while the gateway kept reporting the LAST goal's
  `succeeded`, and Play cleared every new goal at once: arrival is now once per goal (`arrivalOnce`, tested);
  (2) the comparison could take that stale verdict for a new goal: only a verdict for THIS goal counts (tested);
  (3) Nav2's goal status sat in the model's plan-status field and Play's console said "no path" while Nav2 drove:
  the plan is `found`, the verdict travels separately; (4) coco_web's session idle limit (60 s, for shared demos)
  ended a visitor's own session and latched STOP after a minute without input: the image now sets 30 min
  (`session_idle_s`), STOP still ends it -- needs the CI rebuild (next run).
- **UNRESOLVED:** the gateway's `robot.truth` (Gazebo's model odometry) read x = 25.0 with COCO on the start pad
  at x = 23.0 (CI run 45877911153) and later ~1.9 m from AMCL's pose: an offset of that topic's frame, not
  measured AMCL error. Distances driven on it are unaffected (an offset cancels); no truth-vs-belief number is
  shown. Probable cause (not checked): the odometry plugin's origin vs the start teleport.

## R5.4 · Run it in ROS 2 (level packages) — DONE 2026-11-27

- **What:** `coco_lab.level_package` makes a level and its goals a ROS 2 Jazzy `ament_python` package
  `coco_level_<id>`: the level's Gazebo world, Nav2 map and parameters (derivation 5, what the recorded STACK
  runs and the coco-ros2 image use), `scenario.json`, `launch/level.launch.py` (Gazebo; `bringup`: start pose and
  odometry calibration, checked, as the image does; then the arbiter and Nav2, or a Studio export with
  `user_package:=coco_user_<name>`), `run_goals` (NavigateToPose per goal, a JSON result) and a README with the
  exact commands. Reuse: the generation moved from `tools/m6/gen_level.py` into `coco_lab.level_files` (the tool
  now calls it: its outputs are **byte-identical**, the image's three levels still match the committed checksums);
  R2's exporter pattern (templates in the wheel). CLI: `python -m coco_lab.level_package SPEC --goals x,y ...`.
- **In the browser:** Play (Free drive) pause menu "DOWNLOAD AS ROS 2 PACKAGE": this level + the goal set on the
  map, generated by the same function in the worker (a new on-demand pack `level`), zipped. Found and fixed on the
  way: (1) Pyodide has no `xml` package, so `worldgen` (SDF) could not run in the browser, and putting the level
  modules in the game pack **broke Play's boot**: `coco_lab/_xml.py` reproduces the ElementTree subset worldgen
  uses (native keeps the standard library), byte-identical on every World Spec (`test_xml_shim.py`), and the
  modules load only on demand; (2) a JavaScript round trip turned `0.0` into `0` (ROS 2 refuses an integer for a
  double parameter): the templates reach Python as text; (3) the templates' key order is kept.
- **Verified:**
  - Docker (image `sha-cebbcea6a835`, README path A): Depot 2/2 SUCCEEDED (11.2 s, 23.3 s sim; AMCL 0.24 /
    0.26 m from the goals), cluttered Depot 2/2 (11.1 s, 23.0 s; 0.24 / 0.23 m).
  - The laptop's own Jazzy (path B: COCO's overlay from `scripts/build_overlay.sh`, the package in its own
    workspace): Depot 2/2, cluttered Depot 2/2; the Depot with the Studio's particle-filter starter in place of
    AMCL (`user_package:=coco_user_particle_filter`) 2/2. Found: a localiser export needs COCO's start
    (`COCO_INITIAL_POSE`, as tools/r2/ros2_session.sh sets it): the level launch now sets it from scenario.json.
  - Browser: the zip from Chromium = the zip from Firefox = the native package (same goal, the JSON flavour):
    **all 37 files identical**; that browser zip, unchanged, on the laptop's Jazzy: Nav2 active on the JSON-written
    parameters, 1/1 SUCCEEDED. [data/r54/](data/r54/)
  - AMCL-to-goal distances are read from AMCL's last published pose (it publishes on motion thresholds), so they
    can exceed Nav2's 0.25 m tolerance that Nav2's own pose satisfied; Gazebo truth is not used (its frame offset,
    R5.3).
- Limits: the Depot's actors stand still in a package (their scenario script is not part of it); a package needs
  COCO's robot packages (`gazebo_models`, `custom_teleop`), which stock Jazzy does not have (the README says so).

## R5.5 · World editor (first version) — DONE 2026-11-27

- **What:** Workbench › World editor (`?view=workbench&tab=editor`): COCO Lab's kit pieces (wall, door, rack,
  bench, pallet, box) on a 0.5 m grid, the start and goals; place, move, rotate (R), delete, undo/redo
  (`src/editor/model.ts`, tested). Live check in a worker: `coco_lab.level_check` = the World Spec reader's own
  refusals, COCO fitting at its start, every goal reachable (A* on the Arena's own robot-inflated grid). Actions:
  **Play this level** (Free drive on it, its first goal set), **Use in an experiment** (R1's experiments API, A*
  and Dijkstra from the start to each goal, the level registered inline), **Download as ROS 2 package** (R5.4),
  **Copy share link** (`#level=v1.<deflate-raw base64url>`: the spec, the goals and the editor's state; nothing
  else). Plumbing: the worker boots an inline spec and registers an inline experiment world (both validated by the
  Python reader like any spec); shipped worlds unchanged.
- **Found and fixed on the way:** (1) Play's world look needs the lowered spec (boxes, elevation): the check
  returns it and links carry it (the reader accepts it only if it equals what the kit lowers to); (2) **a latent
  glue bug**: a level with no actors sent `clearance: Infinity` in every tick, which `JSON.parse` refuses, so
  Play never ticked on such a level; only a finite clearance is sent now (shipped levels always had one;
  `test_r5_editor_level_glue.py` parses every tick strictly).
- **Verified (`tools/r5/editor_e2e.mjs`, Chromium and Firefox, PASS each):** a small level built from scratch by
  mouse (two rooms, a door, a bench, a rack, the start, two goals): the check passes (goals 10.07 m and 1.91 m);
  the experiment: 4/4 runs found (A* and Dijkstra, the same lengths); Play opens "FREE DRIVE · TWO ROOMS" and GO
  drives in AUTO (0.30 m/s); the package downloads; a box in the doorway is refused in words ("goal 1 (10, 7) is
  not reachable from the start: no path wide enough for COCO's 0.22 m radius"); Undo restores; 0 page errors.
  **The downloaded package in Gazebo (the laptop's Jazzy): 2/2 SUCCEEDED** (32.9 s, 77.9 s sim). [data/r55/](data/r55/)
- Limits (first version): axis-aligned pieces only; no ramps, platforms, objects or actors in the editor; the
  canvas needs scrolling on small screens; keyboard: tools, lists and actions are buttons, the canvas itself is
  pointer-driven (R, Delete, Ctrl+Z work there).

## Questions for Gautham (R5)

1. **Control path for R5.2.** README invariant 2 says browser code that controls COCO's Stack never names a ROS topic and speaks `coco.v1`; R5.2 asks the joystick to publish `/cmd_vel` through the arbiter over a ROS bridge. Options: (a) the browser publishes `/cmd_vel_teleop`, `/mission/mode`, `/goal_pose` through foxglove_bridge (the image's whitelist keeps everything behind the arbiter) and invariant 2 is amended for a visitor's local LIVE container; (b) control stays `coco.v1` (platform_server in the image, a second port; coco_web is frozen and arena-shaped, so it may need changes) and the bridge is read-only. Default until you decide: no browser control code is written.
2. **GHCR package visibility.** A first push creates `ghcr.io/gauthamcodes/coco-ros2`; GitHub documents new packages as private, and only the package settings page makes one public. The one-command promise needs it public. Your call (and any storage cost of a private package).
3. **Permissions for the next session.** R5 needs, without a prompt: docker (build/run/pull/manifest), the test venv's python, node, `git push`, and `gh` (run watch, artifacts, PR, merge, workflow dispatch).

## Next step

With those permissions: run `pytest lab_web/tools/test_r5_coco_ros2_image.py` and the three suites; commit the authored files as `[R5.1]`; push `v2/r5-live-ros2` (the workflow runs on push); watch `coco-ros2 image`; fix until green; record its size.json, check.json and probe.json here; then on the laptop `bash tools/r5/preflight_pull.sh` before any pull, and R5.2 once question 1 is answered. (`chmod` was refused too: the new scripts are committed without the executable bit; the image sets its own modes, and every documented command names its interpreter.)
