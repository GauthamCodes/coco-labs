// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.4: the "?" on each panel -- one paragraph on the ROS 2 idea and what it is in COCO's real
 * stack. Claims about the stack are its configuration, read from the repository (src/ros/stack.ts
 * names the files); claims about the browser are about the model, which is not ROS 2.
 */

export type PanelId = 'displays' | 'graph' | 'echo' | 'plot';

export const LEARN: Record<PanelId, { title: string; text: string }> = {
  displays: {
    title: 'Displays (as in RViz)',
    text: 'RViz draws what a ROS 2 robot publishes: each display subscribes to one topic (/scan, /map, /plan) or to the TF frames and draws it in a fixed frame, here "map". In COCO\'s stack RViz shows Nav2\'s global and local costmaps, AMCL\'s pose and the plan. Here the same displays draw the browser model\'s own computation (MODEL): its LiDAR beams, its layered costmap and its planner\'s path, built into the same ROS 2 message shapes. Nothing on this page is RViz; the names teach what a ROS user would look for.',
  },
  graph: {
    title: 'The ROS 2 graph',
    text: 'A ROS 2 system is a graph: nodes (programs) publish and subscribe to named topics, each carrying one message type. COCO\'s stack runs Nav2 (planner_server, controller_server, amcl), a ros2_control diff-drive controller in Gazebo and COCO\'s own cmd_vel_arbiter, the only node allowed to drive the wheels. This panel is a model of that graph: the browser model produces each message shape at the rates shown, by the role names of coco_lab.ros_shapes (M6F.7). The rates are measured here, on the model\'s ticks; no ROS 2 node is running.',
  },
  echo: {
    title: 'Topic echo',
    text: '`ros2 topic echo /scan` prints each message on a topic as YAML: header (stamp, frame_id) and fields. These are the browser model\'s messages, field for field the shapes of sensor_msgs/LaserScan, nav_msgs/Odometry, geometry_msgs/TwistStamped, nav_msgs/Path, nav_msgs/OccupancyGrid and tf2_msgs/TFMessage, stamped with the model\'s sim time. A test checks every field against coco_lab.ros_shapes, which in turn is checked against the real Jazzy message classes and recorded Gazebo bags (docs/v2/m6/ROS_SHAPES.md).',
  },
  plot: {
    title: 'Plot (as in rqt_plot)',
    text: 'rqt_plot draws numeric message fields over time: an engineer\'s first look at a controller. Here: the commanded speed v and turn rate ω (/cmd_vel), the distance left to the goal, and the nearest LiDAR return (the smallest valid range in /scan) -- what a local controller like Nav2\'s DWB keeps away from. All are the browser model\'s values against its sim time.',
  },
};
