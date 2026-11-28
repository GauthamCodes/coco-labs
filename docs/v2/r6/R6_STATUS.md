# R6 status — R5 follow-ups, then Fidelity, more algorithms, multi-robot

Prompt: [R6_PROMPT.md](R6_PROMPT.md). Worktree `~/coco_labs_ws/worktrees/r6`, branch `v2/r6` (from main `63a97f6`).
Resume: *Continue COCO Lab R6: read docs/v2/r6/R6_PROMPT.md and R6_STATUS.md, then carry on.*

## Gautham's decisions, 2026-11-28 (R5 follow-ups)

1. Image size: trim first (multi-stage, no build tools or docs in the final layer, only the levels it needs), target
   ≤ 3.5 GB; if it can't get under 4.0 GB without dropping a feature, report each part's cost and keep the 4.0 GB budget.
2. foxglove_bridge 3.6.3 ignoring `client_topic_whitelist`: file nothing; write a minimal reproduction and a
   ready-to-paste issue (`UPSTREAM_foxglove_issue.md`), linking an existing upstream report if there is one.
   Gautham files it.
3. The ~2 m gateway truth offset: investigate; fix if ours; show true-vs-estimated distance only when they agree
   within 0.05 m on a test route.
4. Actors must move in the image and in level packages (the G2.9 scenario-rule driver); test move + yield in one
   Depot round.
5. Rewrite `~/Downloads/COCO_Lab_STATUS.md` as a 1–2 page summary of v2 through R5; commit it as `docs/OVERVIEW.md`.
6. WebKit: rely on CI; no local rebuild.
7. Carry-overs: localisation v1.1 suites (`loc-global-active-20`, `loc-kidnap-active-20`) and the leaderboard
   re-verify matrix.

## Machine and disk (2026-11-28)

- Laptop: balanced, AC; no simulator, Isaac or FR3 process; `gh` logged in.
- Disk: 11 GB free before the worktree, **9.7 GB after** (floor 8 GB). So: **no local Docker build or pull of
  coco-ros2** (the pulled image takes 5.42 GB on this Docker's containerd store, measured in R5). Every image build,
  size measurement and container run happens in CI (`.github/workflows/coco-ros2-image.yml`, which now also triggers
  on `v2/r6*` pushes). Nothing reclaimable without touching Gautham's own caches (browser caches 1.3 GB) or the
  Playwright browsers the tests need.

## Steps

| step | state | evidence |
| --- | --- | --- |
| R6.0 prompt, status, worktree | done | this file |
| A1 image trim | **done**: 3.80 → 2.68 GB, every check passing | CI 46108505274, 46109174443, 46113778162; [data](data/a_image_run_46113778162/) |
| A2 foxglove issue draft | **done**: reproduced on 3.6.3 in a clean container; upstream draft PR exists | [UPSTREAM_foxglove_issue.md](UPSTREAM_foxglove_issue.md), CI 46108355151 |
| A3 2 m offset | **fixed** (ours): truth = Gazebo within 0.00004 m on a test route; LIVE shows truth↔AMCL only for `level_map` | [truth_route.json](data/a_image_run_46109174443/truth_route.json) |
| A4 moving actors | **done** in the image (CI) and in level packages (laptop) | [image](data/a_image_run_46109174443/actors_round.json), [package](data/a4_package_laptop/judged.json) |
| A5 OVERVIEW.md | **done**; `~/Downloads/COCO_Lab_STATUS.md` rewritten from it | [OVERVIEW.md](../../OVERVIEW.md) |
| **Part A (1/2) shipped** | PR #47 merged `f440e7e` (exact head `6498caf`: CI green on rerun — attempt 1's only failure the known live-graph timing flake in gazebo_models, 9 < 10 messages; local suites all green, 12/12 packages); deploy run 46142265207; live smoke **PASS 9/9** | [data/a_smoke/](data/a_smoke/) |
| A6 loc v1.1 suites | in progress: suites frozen, runner + report rule written, baselines to run | below |
| A7 re-verify matrix | pending | — |
| B1 fidelity knobs | pending | — |
| B2 algorithms | pending | — |
| B3 multi-robot | pending | — |

## A1 · image size

What exists (reused): `docker/coco-ros2/Dockerfile` is already three stages (levels → overlay → runtime);
the workflow measures `docker image inspect` and `du /` against `MAX_IMAGE_BYTES` and records `docker history`.

Before (main `78b662b`, CI run 45956389403, `history.txt`): 3,797,579,707 bytes (inspect). Layers: the runtime
stage's one `apt-get install` **3.01 GB**; the `ros:jazzy-ros-base` base underneath it: ros-core 413 MB, **build
tools 303 MB** (build-essential, git, colcon, rosdep: the prompt's "no build tools in the final layer"), ros-base
84 MB; our overlay 21.5 MB and levels 7.5 MB. Per-package breakdown: `docker/coco-ros2/size_breakdown.sh`, run by CI
inside the image (`size_breakdown.json` in the artifact).

After (`6c80456`, CI run 46108505274): **2,669,575,866 bytes** (inspect), every acceptance check passing (Nav2
active, the six topics, the bridge probe, the gateway probe). Headers, static libraries and docs: 0 bytes. With
A4's gz-transport binding (OSRF's `python3-gz-transport13`): 2,677,605,236 bytes (run 46109174443). One flattened
layer: a pull downloads it in one piece (no layer sharing with other images).

What is left, and why (`size_breakdown.json` → `why_installed`, from dpkg's own dependency data): three LLVMs —
LLVM 20 for Mesa's software renderer (needed: `libglx-mesa0`), LLVM 18 via `ros-jazzy-nav2-mppi-controller` →
`libomp-dev`, LLVM 17 via ROCm libraries (`libamd-comgr2`) pulled by `ros-jazzy-nav2-bringup` → `slam_toolbox` →
`libboost-all-dev` → OpenMPI; GDAL/ffmpeg development packages via `gz_common_vendor`; OpenCV and VTK via
`cv_bridge` ← `nav2_waypoint_follower`; gcc/gfortran via `ompl` ← `nav2_smac_planner`; TurtleBot 4 sim assets via
`nav2_bringup`. Further cuts would mean replacing ROS's metapackages with a hand-picked list (possible, not
needed: 2.68 GB is under the 3.5 GB target).

## A2 · foxglove_bridge allowlist

Searched GitHub issues and PRs for `client_topic_whitelist` (and "whitelist" in foxglove/foxglove-sdk and
foxglove/ros-foxglove-bridge): **draft PR foxglove/foxglove-sdk#1508** (a maintainer's, "enforce
client_topic_whitelist", unmerged since 2026-10-14) describes the same defect; no public ROS 2 issue. Minimal
reproduction (`foxglove_repro/`): stock `ros:jazzy-ros-base`, `ros-jazzy-foxglove-bridge
3.6.3-1noble.20261105.114855`, allowlist `['^/allowed$']`: `/not_allowed` got a bridge publisher and the message
(CI run 46108355151). Draft: [UPSTREAM_foxglove_issue.md](UPSTREAM_foxglove_issue.md). Nothing filed.

## A3 · the 2 m offset

Cause (ours): coco_web's platform_server put Gazebo's model pose (`/model/coco/odometry`, world frame) into the map
frame by subtracting `coco_config.robot.SPAWN_XY` = (-2, 0) — the arena's convention — on every level. A World Spec
level's map = world + `world_to_map`, which is [0, 0] on the Depot, so every truth pose read 2.0 m high in x (25.0
on the start pad at 23.0). Checked: Gazebo's pose source (OdometryPublisher = world pose), the generated SDF (world
coordinates), the Depot map YAML (map frame = world). Fix: gateway parameters `map_offset_x/y` (default NaN = the
arena, unchanged; the arena's own `world_to_map` [2, 0] equals −SPAWN_XY, tested); the image passes each level's
`world_to_map`. Test route in CI (`truth_route.mjs`: three Nav2 legs, Gazebo's `gz model -p` read independently):
truth − Gazebo ≤ 0.000043 m at 11 stationary samples over 4 stops; truth − AMCL up to 0.238 m. The gateway now says
`welcome.config.truth_frame = 'level_map'`, and only then does Play's LIVE strip show `truth↔AMCL`.

## A4 · moving actors

The image: the entrypoint starts G2.9's driver (unchanged) with coco_lab beside it, untracked by the hold loop.
ROS's vendored Gazebo has no gz-transport Python binding, so the image adds OSRF's `python3-gz-transport13` (8 MB).
One Depot round in CI (G2.9's park-in-lane goal, `actors_round.mjs`): every actor moved 181–238 m, 96 holds, 0
overlap (run 46109174443); a later run's crossing was aborted by Nav2 among the forklifts (46110329900: actors still
moved and held 7 times, 0 overlap), so the round re-sends an aborted goal up to 3 times, as a mission does.
Level packages: the package carries the driver and the 22 coco_lab modules it imports (+ `link_limits.json`), and
its launch starts it after Nav2 (`actors:=false` to keep them still). Laptop Jazzy: 3/3 goals; actors moved
100–128 m, 63 holds (walker_dock 15), 0 overlap. The browser's zip equals the CLI's (59 identical files, 2 YAML
parsed-equal). Not verified: a level package inside the image (README path A) with actors.

## B1 · fidelity knobs — design (before code)

What exists (reused): `arena.range_sigma` (LiDAR range noise, Gaussian), `arena.slip=on` (the body turns
`SLIP_TURN` = 56.2/72.5 of the commanded turn: Lab 2's fit), `arena.odom_alphas` (odometry noise),
acceleration limits (`limits.linear_accel` / `angular_accel`, constants), all set by `config` inputs (so they are
in every run's input log and experiment spec). New, as `config` keys of the same kind:

- `arena.lidar_dropout=p`: each beam independently returns no echo (max range) with probability p, from its own
  seeded stream (`rng.split()` made only when the knob is set);
- `arena.odom_preset=<name>`: wheel odometry over/under-reports the body's motion by measured factors —
  `stack_uncalibrated` (turn 1.2029x, distance 0.9909x: G2.9's derivation-4 gate, 40 STACK runs,
  `docs/v2/g2/data/g29/odom/turn_scale_d4_gate.json`, the installed multiplier 1.10), `stack_calibrated` (0.9986x,
  0.9913x: derivation 5, `turn_scale_d5_gate.json`); `lab2_fit` = today's `arena.slip=on`;
- `arena.cmd_latency=ticks`: the drive command reaches the wheels k ticks late (a FIFO);
- `arena.linear_accel=a`, `arena.angular_accel=a`: override the acceleration limits.

**Off = byte-identical** (the stop condition): `state_v2.snapshot` hashes every Arena attribute, so a knob's
state exists only once it is configured (as `plan_clearance` already does) — an unset knob adds no attribute,
draws nothing from any random stream and changes no arithmetic. Checked by the v1/v2/v3 goldens and the
determinism records, unchanged.

## A6 · localisation v1.1 active suites — first results (MODEL)

Built-in baselines (`tools/r3/make_baselines.py`, R3.2's profile: MCL 60 particles and 12 beams, EKF 12 beams,
max 3,000 ticks; each run twice, deterministic), public sets (`docs/v2/r3/bench/loc-*-active-20/`):

| suite | algorithm | success | "localised" reports (false) | first report correct | re-localised after kidnap |
| --- | --- | --- | --- | --- | --- |
| loc-global-active-20 | mcl | 0/20 | 2 (2) | 0 | — |
| loc-global-active-20 | mcl_augmented | 0/20 | 13 (13) | 0 | — |
| loc-kidnap-active-20 | ekf | 0/20 | 21 (1) | 20 (median 1.8 s) | 0 |
| loc-kidnap-active-20 | mcl | 0/20 | 46 (36) | 10 (median 5.7 s) | 0 |
| loc-kidnap-active-20 | mcl_augmented | 0/20 | 18 (5) | 11 (median 5.8 s) | 1 |

Read: being allowed to stop and turn does not rescue the 60-particle filters. Globally, MCL's every report was
wrong (the Depot's symmetric aisles: a tight cluster in the wrong aisle, holding 90 % of the weight); after a
kidnap, the EKF never re-localises (it cannot), MCL re-localised once in 20. Negative, kept.

**A defect found in the held-out half, fixed:** inline scenarios (how held-out sets travel) kept only a fixed list
of keys and dropped `active`, so the first held-out runs were the passive v1 behaviour (they showed no reports at
all). `active` is now an inline key, validated (`experiments._active_ok`), in every list that copies scenarios
(`experiments.INLINE_KEYS`, `tools/r3/make_baselines.py`, `tools/r2/leaderboard.py`, `tools/r3/heldout.py`);
those held-out parts were deleted and rerun. Suites without `active` are unchanged.

Held-out (the reference draw, 6 scenarios each), rerun with `active`: loc-global-active-20 — mcl 0/6 (2 reports,
2 false), mcl_augmented 0/6 (1, 1); loc-kidnap-active-20 — ekf 0/6 (7 reports, 1 false; first report right 6/6,
median 1.7 s; re-localised 0), mcl 0/6 (16, 10 false; re-localised 0), mcl_augmented 0/6 (9, 3 false;
re-localised 0). The held-out set agrees with the public one.
