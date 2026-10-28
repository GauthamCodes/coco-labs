// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.4: what each node of the model's ROS graph (coco_lab.ros_shapes.ros_graph, M6F.7: role
 * names) is in COCO's real stack, as plain-text references (Gautham, 2026-10-24). Every entry
 * names the repository file it was read from; this is the STACK's configuration, not anything
 * the browser runs.
 */

export interface Counterpart { stack: string; source: string }

export const STACK_NODES: Record<string, Counterpart> = {
  lidar: { stack: "Gazebo's LiDAR sensor, bridged to /scan by ros_gz_bridge (parameter_bridge)", source: 'gazebo_models/config/bridge.yaml' },
  diff_drive: { stack: 'diff_drive_controller (ros2_control, gz_ros2_control): /diff_drive_controller/odom and /tf', source: 'gazebo_models/config/bridge.yaml' },
  map_server: { stack: 'Nav2 map_server', source: 'gazebo_models/config/nav2_params.yaml' },
  global_planner: { stack: 'Nav2 planner_server, SmacPlanner2D (A*)', source: 'gazebo_models/config/nav2_params.yaml' },
  local_controller: { stack: 'Nav2 controller_server, DWB (dwb_core::DWBLocalPlanner)', source: 'gazebo_models/config/nav2_params.yaml' },
  slam_or_amcl: { stack: 'Nav2 amcl (localisation on a saved map), or slam_toolbox (async, mapping)', source: 'gazebo_models/config/nav2_params.yaml, gazebo_models/launch' },
  cmd_vel_arbiter: { stack: "COCO's cmd_vel_arbiter: the only wheel publisher; STOP over teleop over autonomy", source: 'AGENTS.md (integrity invariants)' },
  robot_state_publisher: { stack: "robot_state_publisher (COCO's URDF)", source: 'gazebo_models/launch' },
  teleop: { stack: 'custom_teleop (keyboard / joystick)', source: 'custom_teleop/' },
};

/** The Stack's own topic names where they differ from the model graph's (docs/v2/m6/ROS_SHAPES.md). */
export const STACK_TOPICS: Record<string, string> = {
  '/odom': '/diff_drive_controller/odom',
  '/cmd_vel': '/diff_drive_controller/cmd_vel',
  '/plan': '/plan (Nav2), /lab/plan (COCO Lab recordings)',
};
