# The ROS-to-event adapter (M3.1)

`coco_lab_ros/coco_lab_ros/adapter.py` reads a rosbag2 recording of the full
ROS 2 stack in Gazebo and writes the same run as COCO events. The output is a
coco run file: MCAP, protobuf, the families of `coco_schemas`. The Arena
viewer replays it as a **Case File**, with evidence class **STACK**.

```
python3 -m coco_lab_ros.adapter BAG OUT.mcap --case CASE.json [--detail summary|full] [--window START END]
```

## It is a conversion, not a computation

Every value written is a value the stack recorded, re-expressed in different
units, frames or layout. Nothing is computed: no filter, planner,
controller, smoothing or estimate.

`test_adapter.py::test_the_adapter_runs_no_algorithm` checks this. It fails
if `adapter.py` imports anything beyond the standard library, rosbag2 and
rclpy's deserialiser, `yaml` and `coco_schemas`. In particular nothing of
`coco_lab` may be imported, so a Case File cannot quietly contain the
model's answer.

## The mapping

`t_world` is the recording's simulation time. "map" is the Arena's map
frame.

| Recorded topic | ROS type | COCO channel (message) | What is written |
|---|---|---|---|
| `/model/coco/odometry` | `nav_msgs/Odometry` | `coco.truth.pose.v1` (`TruthPoseBatch`) | The simulator's ground truth: the pose plus the run's `world_to_map` offset. **The only source of `truth`.** |
| `/lab/actors` | `std_msgs/String` (JSON) | `coco.truth.actors.v1` (`ActorPoseBatch`) | Each actor's recorded pose plus `world_to_map`. The radius is the Case File spec's `actor_radius`, else NaN, because the bag does not carry it. |
| `/amcl_pose` | `PoseWithCovarianceStamped` | `coco.estimate.pose.v1`, estimator `amcl` | The pose and the covariance entries (x x, x y, x θ, y y, y θ, θ θ) = indices 0, 1, 5, 7, 11, 35. |
| `/amcl_pose` | same | `coco.robot.state.v1` | The pose the stack drove by (v, ω NaN), as the Lab 5 converter does. |
| `/odometry/filtered` | `nav_msgs/Odometry` | `coco.estimate.pose.v1`, estimator `robot_localization@<frame>` | The pose and covariance. In `map` when a `map → odom` transform was recorded, else tagged `@odom`. |
| `/diff_drive_controller/odom` | `nav_msgs/Odometry` | `coco.estimate.pose.v1`, estimator `wheel_odometry@<frame>` | As above. |
| `/scan` | `sensor_msgs/LaserScan` | `coco.sensor.scan.lidar.v1` (`ScanBatch`) | `angle_min`, `angle_increment`, `range_min`, `range_max` and every range, float32 as recorded. |
| `/lab/plan` | `nav_msgs/Path` | `coco.plan.path.poses.v1`, `search_id` 1 | The lab's own planned path. |
| `/received_global_plan` | `nav_msgs/Path` | `coco.plan.path.poses.v1`, `search_id` 2 | Nav2's global plan as the controller received it. |
| `/plan` | `nav_msgs/Path` | `coco.plan.path.poses.v1`, `search_id` 3 | Nav2's planner output. |
| `/local_plan` | `nav_msgs/Path` (`odom`) | `coco.control.local.candidates.v1`, `controller_id FollowPath/local_plan` | The trajectory the controller chose, put in `map` by the latest recorded `map → odom`, as candidate 0 with v, w and cost NaN. |
| `/optimal_trajectory` | `nav_msgs/Path` | `coco.control.local.candidates.v1`, `controller_id FollowPath/optimal_trajectory` | MPPI's optimal trajectory, the same way. |
| (whenever either of the above is present) | — | `coco.control.local.header.v1` | `controller_id FollowPath`, `kind` = the spec's `controller`, `evidence STACK`. |
| `/cmd_vel_nav` | `TwistStamped` | `coco.control.local.command.v1` | The controller's command: v = `linear.x`, w = `angular.z`, status `cmd_vel_nav`. |
| `/diff_drive_controller/cmd_vel` | `TwistStamped` | `coco.metrics.values.v1` `wheels.cmd.v` / `wheels.cmd.w` | What reached the wheels, after the arbiter. |
| `/cmd_vel_teleop` | `TwistStamped` | `coco.metrics.values.v1` `teleop.cmd.v` / `teleop.cmd.w` | The driver's teleop command. |
| `/collision_monitor_state` | `nav2_msgs/CollisionMonitorState` | `coco.metrics.values.v1` `collision_monitor.action_type` | The action type as a number. |
| `/mission/state` | `std_msgs/String` (`key=value`) | `coco.mission.fsm.transition.v1` + `coco.mission.fsm.header.v1` | One transition per change of `state`: from-state, to-state, event, reason, result (`--` reads as empty). The header lists the states seen, in order. |
| `/lab/status`, `/mission/search`, `/mission/search_region`, `/perception/status`, `/approach/status`, `/grasp/status`, `/ramp/status`, `/cmd_vel_arbiter/status` | `std_msgs/String` | `coco.annotation.text.v1`, source = the topic | The text, verbatim. |
| `/tf` | `tf2_msgs/TFMessage` | (none) | Only its `map → odom` transforms are read, to place `odom`-frame paths and poses. |

**Not converted**, and recorded only in the bag:
- `/local_costmap/costmap` and `/local_costmap/published_footprint`
- `/transformed_global_plan`
- `/follow_path/_action/*`
- `/clock`
- `/imu`
- Lab 1C's `/lab/costmap_snapshot` and `/lab/trace_gz` (Lab 1's search trace is already in the M1 converters)
- the heavy bags' `/evaluation` and `/trajectories`

A Case File that needs one of these says so, and the Case File's text cites
the bag.

## Re-expressions, all of them

- **Clock.** `t_world` is the message's header stamp when it has one. A
  message without one (the String topics) takes its bag log time, mapped
  onto simulation time through `/model/coco/odometry`. That map is header
  stamp against log time, piecewise linear, and extends at slope 1 past its
  ends (`SimClock`).
  - Recordings made with `--use-sim-time` (Labs 1, 2, 3, 5) make that map
    the identity.
  - Lab 4's bags were logged in wall time and need it. The fixture test
    checks the transitions land on the simulator's clock, not 1.79 × 10⁹ s.
- **Ticks.** `tick` = floor((`t_world` − t0) / 0.1 s), where t0 is the
  window's start, else the first message converted.
- **Sequence numbers.** `seq` counts rows per channel. One batch is written
  per channel per tick (per estimator for `estimate`; one per path).
  Records are in log-time order.
- **Frames.**
  - Gazebo's world frame becomes the map frame by the run's own
    `world_to_map` offset. It comes from the run directory's `meta.json`,
    else the spec. A run with neither is refused.
  - `odom`-frame data is put in `map` by the latest `map → odom` from `/tf`.
    Data before any such transform is dropped for paths and tagged `@odom`
    for poses.
- **Detail.**
  - `full` keeps every message.
  - `summary`, used for the site's Case Files, keeps a recorded message no
    more often than its topic's interval: odometry, commands and actors
    0.1 s; scans and local plans 0.5 s; the global plan 1 s
    (`adapter.DETAIL`). It is always the first message in each interval
    and never an interpolated one.
  - A string topic is kept in `summary` when its text changes, else at
    most once a second.
  - The test checks every summary row is one of the full rows.
- **Window.** `--window START END` keeps messages with `t_world` in the
  window, in simulation seconds. `/tf` is read from the start, so the frame
  is right at the window's start.
- **Log window.** `--log-window START_NS END_NS` acts first. It keeps
  messages, and the clock's reference pairs, whose bag log time is in the
  window. A Lab 4 recorder could outlive its run by a few seconds and catch
  the next run's fresh simulator, whose clock restarts near 0
  (`docs/data/p05_bagtimes.py`). Cutting by log time keeps that run out
  even where its simulation times overlap this run's. Each Case File's log
  window is chosen from the run's own recorded `/mission/state` (M3.3) and
  is written into the manifest.

## Citation

The manifest's `spec` (canonical JSON) carries:
- `case`: the Case File's own spec, as given
- `source.bag`: the bag directory relative to `~/coco_lab_runs`
- `source.files`: every file in it with its **sha256** and size
- `adapter`: name, version, detail, the topics used, `world_to_map`, the
  window, t0 and the clock rule

`run_id` is `coco_schemas.runid.run_id(spec, 0, [(adapter, version),
('ros', 'jazzy')])`, so the same bag, spec and adapter give the same file,
byte for byte (tested).

## Tests

`coco_lab_ros/test/test_adapter.py` runs on four short slices of real
recordings in `coco_lab_ros/test/fixtures/bags/`, about 1.3 MB in all. They
were cut byte for byte, without re-encoding, by `fixtures/make_case_bags.py`.
`FIXTURES.json` records each source bag's sha256.

| Fixture | Recording | What it exercises |
|---|---|---|
| `lab5_crossing_dwb_1` | 2 s of a Lab 5 crossing run | truth, scans beam for beam, AMCL with covariance, plans, the local plan put in `map`, commands, actors, strings, metrics, the citation, reproducibility, summary thinning, the window |
| `lab4_a1_fixed_red` | 2 s of a Lab 4 run | wall-clock log time onto simulation time; four state transitions; a log window cutting after the second |
| `lab2_kidnap_recovery_k1` | 3 s of a Lab 2 kidnap run | wheel odometry with its frame |
| `lab2_rl_fidelity_s1` | 2 s of a robot_localization replay | an `odom`-frame estimate with no transform |

The run-file writer it uses is `coco_schemas/coco_schemas/mcap_write.py`. It
writes uncompressed MCAP and round-trips through `mcap_read`
(`test_mcap_write.py`). The site's Case Files are those files re-chunked
with zstd, the same messages byte for byte (M3.2, M3.3).
