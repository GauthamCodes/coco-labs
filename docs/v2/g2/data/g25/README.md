# G2.5 rosbag2 export — evidence (laptop, ROS 2 Jazzy, 2026-10-24)

**MODEL.** The bag holds the browser model's messages (ROS 2 message shapes of COCO's stack,
built by `lab_web/src/ros/shapes.ts`, parity-tested against `coco_lab.ros_shapes`), written in
the browser by `lab_web/src/ros/bag.ts`. No ROS 2 ran in the browser. Inside the file a `coco`
metadata record says `evidence: MODEL` and "no ROS 2 ran"; every stamp is the model's sim time.

## 1. Exported from a real browser run

`lab_web/tools/g2/bag_proof.mjs` (Chromium, NVIDIA RTX 4050, laptop): Fetch Rush seed 1, drive,
AUTO, 45 s, pause, **SAVE AS ROSBAG2 (MCAP)** — the download is
[`coco_lab_fetch_rush_phone_seed1.mcap`](coco_lab_fetch_rush_phone_seed1.mcap)
(1.8 MB, sha256 `8560503e6569ed8dec5ef8668f5e3e3830df7ad631ce36b7ef720032b22f8cb5`; the page said
"Saved … (1.8 MB) · MODEL", [`…mcap.json`](coco_lab_fetch_rush_phone_seed1.mcap.json)). The rounds
file in that build was G2.1's provisional rules-4 file (the browser plays whatever round it has;
the bag's content does not depend on it).

## 2. `ros2 bag info` — [`bag_info.txt`](bag_info.txt)

Accepted as a single file: storage `mcap`, ROS distro `jazzy`, 48.7 s, 1,955 messages:
`/scan` (LaserScan) 488, `/odom` (Odometry) 488, `/tf` 488, `/cmd_vel` (TwistStamped) 488,
`/plan` (Path) 1, `/map` (OccupancyGrid) 1, `/tf_static` 1, `/joint_states` 0 (the arm did not
move in this run; the channel is declared, empty), all `cdr`.

## 3. `ros2 bag play` while RViz shows it — [`play_log.txt`](play_log.txt), [`rviz_bag_play.png`](rviz_bag_play.png)

`tools/g2/bag_proof.sh`: `rviz2 -d tools/g2/coco_model_bag.rviz` with `use_sim_time`, then
`ros2 bag play BAG --clock 100` (ROS domain 82, nothing else on the machine touched; every
process stopped by PID):

- `ros2 topic hz /scan` while playing: **average rate 10.000** (min = max = 0.100 s);
- `/map` echoed by a subscriber that joined ~12 s after the player started, with transient-local
  QoS: received (490 × 330 cells, 0.1 m, origin (−0.5, −0.5)) — the bag's `/map` and
  `/tf_static` are offered transient local, so `ros2 bag play` re-offers them as a map server would;
- `/scan`'s header: frame `lidar_link`, sim-time stamp;
- RViz (fixed frame `map`): **Global Status: Ok, TF: Ok**; the Map, the LaserScan on the walls
  and pallets, the TF frames at the robot and the plan drawn — the screenshot is RViz's own window
  only (`gnome-screenshot -w`). A second capture 9 s later was byte-identical and was not kept.

`ros2 bag info`'s "Start: Jan 1 1970 …(0.1)" is sim time from the run's start, as stamped.

## 4. Tests (CI and package suite)

| Test | Checks |
| --- | --- |
| `lab_web/test/g2_cdr.test.ts` | the browser's CDR bytes equal `rclpy.serialization.serialize_message`'s (ROS 2 Jazzy) for all 7 types, 9 samples (`tools/g2/gen_msgdefs.py` goldens) |
| `lab_web/test/g2_bag.test.ts` | the export is deterministic and equals the committed fixture bag; profile `ros2`, `ros2msg` schemas, `cdr` channels with QoS and RIHS01 type hashes, stamps = log times, `coco` metadata `evidence: MODEL` |
| `coco_lab_ros/test/test_g2_bag_export.py` | `rosbag2_py` opens the fixture bag (mcap plugin); every message deserialises into the Jazzy class; frames and stamps; `/map`, `/tf_static` transient local, others volatile |

Foxglove: not installed on this laptop, so not tried (the file is the same MCAP `ros2` profile
`ros2 bag record -s mcap` writes, compared with the committed Stack bags).
