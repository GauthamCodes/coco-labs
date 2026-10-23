# The ROS-shaped model (M6F.7)

README §1 ("ROS 2 at its core", first layer) and invariant 2. Code
`coco_lab/coco_lab/ros_shapes.py` (standard library only; never imports ROS); graph
`docs/v2/m6/data/ros_graph.json` (`ros_shapes.ros_graph()`); evidence
`docs/v2/m6/data/ros_shapes_vs_stack.json` (`tools/m6/compare_ros_shapes.py`). Tests:
`coco_lab/test/test_ros_shapes.py` (no ROS) and `coco_lab_ros/test/test_m6f_ros_shapes.py`
(the real Jazzy messages and the recorded bags). No panel here: drawing the graph is M6
UI-phase work.

## The shapes

| Function | ROS 2 message | Frame |
|---|---|---|
| `laser_scan(arena)` | `sensor_msgs/msg/LaserScan` | `lidar_link` |
| `occupancy_grid(lab_map)` | `nav_msgs/msg/OccupancyGrid` (0 free, 100 occupied, −1 unknown; rows from the origin) | `map` |
| `twist(v, w)`, `twist_stamped(v, w, t)` | `geometry_msgs/msg/Twist`, `TwistStamped` (empty `frame_id`, as `cmd_vel_arbiter` publishes) | — |
| `path(points, t)` | `nav_msgs/msg/Path` | `map` |
| `odometry(arena)` | `nav_msgs/msg/Odometry` (zero covariances: the model computes none) | `odom` → `base_footprint` |
| `tf(arena)`, `tf_static(arena)` | `tf2_msgs/msg/TFMessage` | `map → odom → base_footprint → base_link → lidar_link` |

Every shape fills the real message class through `rosidl_runtime_py.set_message_fields`
(which refuses unknown fields) and reads back with exactly the same fields, in the same
order, recursively (tested).

**Frame names.** The M6F prompt names the laser frame `laser`; COCO's URDF and every
recorded Stack bag call it `lidar_link`, reached through `base_link`. The model uses the
Stack's names, so a model message and a recorded one can be compared directly
(deviation, recorded).

## Against the recorded Stack (MODEL vs STACK)

Bags: the committed fixtures `lab2_kidnap_recovery_k1` and `lab5_crossing_dwb_1`
(`coco_lab_ros/test/fixtures/bags/`, provenance in `FIXTURES.json`).

| Shape | Model | Stack (recorded) | Agree? |
|---|---|---|---|
| Scan frame | `lidar_link` | `lidar_link` | yes |
| Scan beams | 480 | 480 | yes |
| angle_min / angle_max | ∓2.0944 | ∓2.0943999 (float32) | yes, to 1e-6 |
| angle_increment | 0.0087448852 | 0.0087448852 (float32) | yes, to 1e-6 |
| range_min / range_max | 0.15 / 12.0 | 0.15 (float32) / 12.0 | yes |
| scan_time, time_increment | 0, 0 | 0, 0 | yes |
| intensities | none (0 values) | 480 values | **no**: the model computes no intensities |
| `base_footprint → base_link` | z 0.0135 | z 0.0135 | yes |
| `base_link → lidar_link` | (−0.09, 0.1, 0.2) | (−0.09, 0.1, 0.2) | yes |
| Odometry frames (`/diff_drive_controller/odom`) | `odom` → `base_footprint` | `odom` → `base_footprint` | yes |
| Command frame (`/diff_drive_controller/cmd_vel`) | `''` | `''` | yes |
| Path frame (`/lab/plan`) | `map` | `map` | yes |

**Values: the scan.** Each of the bag's 30 recorded scans against the model's scan
from the recorded ground-truth pose (`/model/coco/odometry`, Gazebo's world frame shifted
into the map frame) on `worlds/coco_arena_v1.yaml`, beam by beam where both ranges are
finite and within limits: **13,890 beams; median |Δ| 0.0495 m; 90th percentile 0.147 m;
50.1 % within 0.05 m** (MEASURED from committed data, recomputed by the test). The model
scans the 0.05 m saved map, whose rasteriser grows every solid by up to half a cell, and
Gazebo's LiDAR is noisy; this number is a model gap, not a defect.
