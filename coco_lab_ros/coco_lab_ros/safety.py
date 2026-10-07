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
What the lab may never publish (COCO Lab platform rule 3).

The lab moves the robot ONLY by sending a path to controller_server's
``FollowPath`` action. The command chain below it is (nav.launch.py,
``arbiter:=true``)::

    controller_server -> /cmd_vel_nav -> velocity_smoother
      -> /cmd_vel_smoothed -> collision_monitor -> /cmd_vel
      -> cmd_vel_relay -> /cmd_vel_gated -> cmd_vel_arbiter
      -> /diff_drive_controller/cmd_vel

A publisher on any link of that chain, on any other arbiter input, or on
the wheel topic would bypass part of the safety chain or the arbiter's
position as the wheel topic's sole publisher (CLAUDE.md rule 4). So would
the mode topic: the arbiter's mode is set by its ``initial_mode``
parameter at launch, never by the lab.

This module is pure. The tests check it three ways: against the
arbiter's own declared defaults, against the node's source (AST), and
against a constructed node's live publisher list.
"""

WHEEL_TOPIC = '/diff_drive_controller/cmd_vel'

#: cmd_vel_arbiter's inputs, as its parameters default them and as
#: arbiter.launch.py sets them (nav_topic := /cmd_vel_gated).
ARBITER_INPUTS = ('/cmd_vel_teleop', '/cmd_vel_gated', '/cmd_vel_rl',
                  '/cmd_vel_approach', '/mission/mode')

#: The links above the relay, between controller_server and the arbiter.
COMMAND_CHAIN = ('/cmd_vel_nav', '/cmd_vel_smoothed', '/cmd_vel')

FORBIDDEN_TOPICS = (WHEEL_TOPIC,) + ARBITER_INPUTS + COMMAND_CHAIN

#: No lab publisher may carry a velocity command on ANY topic.
VELOCITY_TYPES = ('geometry_msgs/msg/Twist', 'geometry_msgs/msg/TwistStamped')

#: Everything the planner node publishes, and nothing else.
LAB_TOPICS = {
    '/lab/plan': 'nav_msgs/msg/Path',
    '/lab/status': 'std_msgs/msg/String',
    '/lab/costmap_snapshot': 'nav2_msgs/msg/Costmap',
    '/lab/trace_gz': 'std_msgs/msg/UInt8MultiArray',
}

#: Everything the Lab 5 actor driver publishes, and nothing else. It moves
#: Gazebo models through gz-transport, never through ROS.
ACTOR_TOPICS = {
    '/lab/actors': 'std_msgs/msg/String',
}

#: ROS infrastructure topics every rclpy node publishes on its own.
INFRASTRUCTURE_TOPICS = ('/rosout', '/parameter_events')


def violations(names_and_types, allowed=None):
    """
    Return every forbidden publisher in ``[(topic, [types])]``.

    ``names_and_types`` is what ``get_publisher_names_and_types_by_node``
    returns. ``allowed`` is the node's declared topics (default
    :data:`LAB_TOPICS`, the planner's). An empty list means the node is
    safe.
    """
    allowed = LAB_TOPICS if allowed is None else allowed
    bad = []
    for topic, types in names_and_types:
        if topic in FORBIDDEN_TOPICS:
            bad.append(f'{topic}: a command-chain, arbiter-input or wheel '
                       f'topic')
        for t in types:
            if t in VELOCITY_TYPES:
                bad.append(f'{topic}: carries {t}')
        if topic not in allowed and topic not in INFRASTRUCTURE_TOPICS:
            bad.append(f'{topic}: not a declared lab topic')
    return bad
