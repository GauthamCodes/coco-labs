# G2.2–G2.4 — GAME | SIM, telemetry, panels: evidence

All MODEL: the browser model's state, drawn and named the way ROS 2 tools do; nothing here is ROS 2.

## Tests (CI)

| Test | What it checks |
| --- | --- |
| `lab_web/test/g2_ros_shapes.test.ts` + `lab_web/tools/test_g2_ros_parity.py` | the page's ROS-shaped messages (LaserScan, Odometry, TF, TwistStamped, Path, OccupancyGrid) equal `coco_lab.ros_shapes`'s field by field (1e-12; the scan as the float32 the worker sends) on a Free Drive session played through the glue; the fixture regenerates identically |
| `lab_web/tools/test_g2_ros_parity.py` | a game tick with the new `ros` frames has the plain Arena's state hash (the glue reads, never writes) |
| `lab_web/test/g2_rosout.test.ts` | /rosout lines only from model events; node names from the M6F.7 graph; lengths in metres (cells × resolution) |
| `lab_web/test/g2_telemetry.test.ts` | the strip shows `ros_shapes.odometry`'s pose; the Gazebo-style clock excludes pauses, RTF over a window |
| `lab_web/test/g2_panels.test.ts` | Topic echo prints `ros2 topic echo` YAML; topics count only messages the model produced; every model node has a Stack counterpart with its source file; saved displays validated |
| `lab_web/test/g2_ros_honesty.test.ts` | no shipped text says the browser runs ROS 2; the ROS surfaces say MODEL; no ROS/Gazebo/RViz/Nav2/MoveIt/NVIDIA logo shipped |
| `lab_web/tools/g1/chase_hud_check.mjs` (+ G2 SIM pass) | 20 poses × 3 profiles (emulated phone landscape, desktop, the real phone's 710 × 269 tab): COCO under no HUD element, no HUD overlap; then SIM view: no overlap, STOP visible, the model keeps ticking — [`chase_hud_with_sim.json`](chase_hud_with_sim.json): passed, 0 failed |

## Frame rate on the laptop (MEASURED, NVIDIA RTX 4050, balanced, AC)

`lab_web/tools/g1/perf_play.mjs --profile desktop --tier high --minutes 2 --game fetch_rush --view game|sim`:

| View | frame interval median | p95 | p99 | max (file) |
| --- | --- | --- | --- | --- |
| GAME (high: SSAO, bloom, env map) | 16.6 ms | 18.1 ms | 18.9 ms | 23.2 ms ([`desktop-high-game-nvidia.json`](desktop-high-game-nvidia.json)) |
| SIM (every display on) | 16.6 ms | 18.0 ms | 18.9 ms | 40.5 ms ([`desktop-high-sim-nvidia.json`](desktop-high-sim-nvidia.json)) |

Drawn fps median 60.06 / 60.08, minimum 59.2 / 59.1, 0 frames over 50 ms; headless Chromium caps at 60 fps: both views are at the cap. **The real Nothing Phone (1) in SIM
view is not measured yet** (the phone was disconnected; `real_phone_free.mjs --view sim` is ready).

## Screenshots for review — [`../../screens/g22/`](../../screens/g22/)

`lab_web/tools/g2/sim_shots.mjs` (NVIDIA): desktop and emulated phone landscape — GAME, SIM, the four
panels and a Learn paragraph, then GAME again. Panel vs STOP measured: no overlap on either profile.
