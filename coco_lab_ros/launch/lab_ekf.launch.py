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

r"""
lab_ekf.launch.py -- robot_localization beside a running stack, OBSERVE ONLY.

Start the simulator and the lab stack first (``lab_stack.launch.py``),
then::

    ros2 launch coco_lab_ros lab_ekf.launch.py

It starts ``robot_localization``'s ``ekf_node`` on
``config/ekf_odom_imu.yaml`` -- wheel ``vx, vy`` plus the gyro's yaw rate --
and publishes ``/odometry/filtered``. ``publish_tf`` is FALSE in that file
and this launch does not change it, so the ``odom -> base_footprint``
transform AMCL and Nav2 use stays the diff_drive_controller's: the EKF
changes nothing the mission or the wheels depend on (tested:
``test_ekf_config.py``). Feeding it to AMCL would mean turning off the
controller's odometry TF, a production change this lab does not make; the
offline comparison of AMCL on each odometry is
``docs/data/lab2/amcl_replay.py``.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Return the one ekf_node, on the lab config, with sim time."""
    config = os.path.join(get_package_share_directory('coco_lab_ros'),
                          'config', 'ekf_odom_imu.yaml')
    return LaunchDescription([
        Node(package='robot_localization', executable='ekf_node',
             name='ekf_filter_node', output='screen',
             parameters=[config, {'use_sim_time': True}]),
    ])
