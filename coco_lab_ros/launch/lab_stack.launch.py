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
lab_stack.launch.py -- the lightest stack the lab plans and drives on.

Start the simulator first, fresh, in its own terminal (CLAUDE.md §5)::

    ros2 launch gazebo_models full_world_robo.launch.py gui:=false \\
        traverse:=true

then::

    ros2 launch coco_lab_ros lab_stack.launch.py [planner:=true \\
        algorithm:=astar goal_x:=2.5 goal_y:=6.0 out_dir:=...]

It composes exactly what ``mission.launch.py`` composes for navigation and
nothing else -- no executive, perception, MoveIt, web layer or RViz:

- ``custom_teleop arbiter.launch.py initial_mode:=nav``. The arbiter's mode
  is set through its existing launch parameter, so nothing publishes
  ``/mission/mode`` (a publisher there would be a new arbiter input);
- ``gazebo_models nav.launch.py arbiter:=true params_file:=<merged>``:
  Nav2 with its command chain routed through ``/cmd_vel_gated`` into the
  arbiter, on the mission's parameters merged with the lab-only overlay
  (``config/nav2_lab_overlay.yaml``: one extra planner, NavFnAStar);
- optionally ``lab_planner``, which plans once and sends one FollowPath.

``params_file:=`` overrides the merged file (the runners pass one they
merged and hashed themselves). Goals are in the MAP frame.
"""

import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            OpaqueFunction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

PLANNER_ARGS = {
    'algorithm': 'astar', 'heuristic': 'euclidean', 'graph': 'C1',
    'goal_x': '0.0', 'goal_y': '0.0', 'goal_yaw': '0.0', 'out_dir': '',
    'run_id': '', 'follow': 'true', 'settle_count': '2',
}


def merged_params(context):
    """Return the params file to use, merging the overlay if none given."""
    given = LaunchConfiguration('params_file').perform(context)
    if given:
        return given
    from coco_lab_ros.params import merge_files
    base = os.path.join(get_package_share_directory('gazebo_models'),
                        'config', 'nav2_params.yaml')
    overlay = os.path.join(get_package_share_directory('coco_lab_ros'),
                           'config', 'nav2_lab_overlay.yaml')
    out = os.path.join(tempfile.mkdtemp(prefix='coco_lab_'),
                       'nav2_lab_params.yaml')
    merge_files(base, overlay, out)
    return out


def stack(context, *args, **kwargs):
    """Build the included launch files and the optional planner node."""
    params = merged_params(context)
    arbiter = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('custom_teleop'), 'launch',
            'arbiter.launch.py')),
        launch_arguments={'initial_mode': 'nav',
                          'use_sim_time': 'true'}.items())
    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('gazebo_models'), 'launch',
            'nav.launch.py')),
        launch_arguments={'arbiter': 'true', 'params_file': params,
                          'use_sim_time': 'true'}.items())
    cfg = {k: LaunchConfiguration(k).perform(context) for k in PLANNER_ARGS}
    planner = Node(
        package='coco_lab_ros', executable='lab_planner', name='lab_planner',
        output='screen', condition=IfCondition(LaunchConfiguration('planner')),
        parameters=[{
            'use_sim_time': True,
            'algorithm': cfg['algorithm'], 'heuristic': cfg['heuristic'],
            'graph': cfg['graph'],
            'goal_x': float(cfg['goal_x']), 'goal_y': float(cfg['goal_y']),
            'goal_yaw': float(cfg['goal_yaw']), 'out_dir': cfg['out_dir'],
            'run_id': cfg['run_id'],
            'follow': cfg['follow'].lower() == 'true',
            'settle_count': int(cfg['settle_count']),
        }])
    return [arbiter, nav, planner]


def generate_launch_description():
    """Return the lab stack's launch description."""
    return LaunchDescription(
        [DeclareLaunchArgument('params_file', default_value=''),
         DeclareLaunchArgument('planner', default_value='false')]
        + [DeclareLaunchArgument(k, default_value=v)
           for k, v in PLANNER_ARGS.items()]
        + [OpaqueFunction(function=stack)])
