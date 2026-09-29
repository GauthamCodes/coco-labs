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
lab_static_smoke.launch.py -- map_server + planner_server, no simulator.

The static conformance smoke test (``test/test_static_smoke.py``) runs
this on a private ROS domain with a small committed map, and provides the
``map -> base_footprint`` transform itself. It proves the pipeline --
``costmap_raw`` capture, ``ComputePathToPose`` by planner_id, the
``unsmoothed_plan`` subscription -- before any Gazebo run.

``params_file`` is required: the test derives it from the lab-merged
parameters, changing only ``use_sim_time`` (there is no /clock here).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Return map_server, planner_server and their lifecycle manager."""
    params = LaunchConfiguration('params_file')
    return LaunchDescription([
        DeclareLaunchArgument('params_file'),
        DeclareLaunchArgument('map'),
        Node(package='nav2_map_server', executable='map_server',
             name='map_server', output='screen',
             parameters=[params, {'yaml_filename': LaunchConfiguration('map'),
                                  'use_sim_time': False}]),
        Node(package='nav2_planner', executable='planner_server',
             name='planner_server', output='screen', parameters=[params]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_lab_smoke', output='screen',
             parameters=[{'use_sim_time': False, 'autostart': True,
                          'node_names': ['map_server', 'planner_server']}]),
    ])
