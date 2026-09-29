# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
COCO Lab's hook into the real stack.

``coco_lab`` is pure and never imports ROS. Everything that touches a
running stack lives here, above controller_server: the lab plans, and
Nav2's ``FollowPath`` action drives, through the existing chain into
``cmd_vel_arbiter``. Nothing here publishes velocity (:mod:`.safety`).

Pure modules (no rclpy at import, unit-testable without a graph):

- :mod:`coco_lab_ros.costmap` -- a ``nav2_msgs/Costmap`` snapshot, its
  identity, Nav2's world/cell conversion, and the LabMap adapter
- :mod:`coco_lab_ros.planning` -- the two declared move models (C0, C1)
  and one search on a snapshot
- :mod:`coco_lab_ros.metrics` -- L, E, I, endpoint, c_max, tracking error
- :mod:`coco_lab_ros.pathing` -- cells to the poses handed to FollowPath
- :mod:`coco_lab_ros.params` -- the lab-only Nav2 parameter overlay merge
- :mod:`coco_lab_ros.safety` -- the topics the lab may never publish

ROS modules: :mod:`coco_lab_ros.planner_node` (the node) and
:mod:`coco_lab_ros.export` (rosbag2 to a recorded-run bundle).
"""

__version__ = '0.1.0'
