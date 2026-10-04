-- Phase 4 (Lab 3): Cartographer on COCO's recorded drives.
--
-- This is the RELEASED 2D single-laser configuration of cartographer_ros
-- (ros-jazzy-cartographer-ros 2.0.9003, configuration_files/revo_lds.lua),
-- copied line for line, with ONLY these changes, each needed to run it on
-- COCO at all or to give it the same inputs slam_toolbox gets:
--
--   tracking_frame / published_frame  -> base_footprint / odom
--                                        (COCO's frames; the bag's TF tree)
--   provide_odom_frame  true  -> false   (odom -> base_footprint is the wheel
--                                        odometry, already on /tf)
--   use_odometry        false -> true    (slam_toolbox uses the wheel
--                                        odometry; identical inputs)
--   min_range / max_range 0.3 / 8 -> 0.15 / 12   (COCO's LiDAR, the
--                                        Revo LDS's are 0.3 / 8)
--
-- Nothing else is tuned. POSE_GRAPH.optimize_every_n_nodes is overridden to
-- 0 by coco_2d_no_loop.lua for the loop-closure-off arm, which is how the
-- Cartographer documentation says to turn global SLAM off.

include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "base_footprint",
  published_frame = "odom",
  odom_frame = "odom",
  provide_odom_frame = false,
  publish_frame_projected_to_2d = false,
  use_pose_extrapolator = true,
  use_odometry = true,
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 0.2,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.,
  odometry_sampling_ratio = 1.,
  fixed_frame_pose_sampling_ratio = 1.,
  imu_sampling_ratio = 1.,
  landmarks_sampling_ratio = 1.,
}

MAP_BUILDER.use_trajectory_builder_2d = true

TRAJECTORY_BUILDER_2D.submaps.num_range_data = 35
TRAJECTORY_BUILDER_2D.min_range = 0.15
TRAJECTORY_BUILDER_2D.max_range = 12.
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 1.
TRAJECTORY_BUILDER_2D.use_imu_data = false
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.linear_search_window = 0.1
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.translation_delta_cost_weight = 10.
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.rotation_delta_cost_weight = 1e-1

POSE_GRAPH.optimization_problem.huber_scale = 1e2
POSE_GRAPH.optimize_every_n_nodes = 35
POSE_GRAPH.constraint_builder.min_score = 0.65

return options
