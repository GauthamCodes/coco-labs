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
lab_actors: drive Lab 5's moving actors in Gazebo, deterministically.

One node per run. For a scenario from ``config/lab5_scenarios.json`` it

1. spawns each actor (``actors.model_sdf``: a visual-only grey cylinder,
   no collision geometry) through Gazebo's own ``/world/<w>/create``;
2. holds it at its first waypoint until the robot's GROUND-TRUTH position
   (``/model/coco/odometry``, world frame, shifted into the map frame)
   crosses the actor's trigger line;
3. from then on teleports it, every ``rate_hz`` tick of SIM time, to
   ``actors.actor_pose(actor, t_trigger, t_now)`` through Gazebo's own
   ``/world/<w>/set_pose`` -- a driven (kinematic) pose, never simulated;
4. publishes, for the record, one JSON line per tick on ``/lab/actors``:
   sim time, trigger time and each actor's commanded map-frame pose.

It never touches the robot: no velocity publisher of any kind, no
``/mission/mode``, no Nav2 input (``safety.ACTOR_TOPICS``, tested on a
constructed node). Gazebo is reached through gz-transport, not a ROS
bridge, so nothing new appears on the ROS graph but ``/lab/actors``.
"""

import json
import os
import threading

from ament_index_python.packages import get_package_share_directory
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)
from std_msgs.msg import String

from . import actors

STATUS_QOS = QoSProfile(depth=50, history=QoSHistoryPolicy.KEEP_LAST,
                        reliability=QoSReliabilityPolicy.RELIABLE,
                        durability=QoSDurabilityPolicy.VOLATILE)


def default_scenarios_file():
    """Return the installed scenarios file."""
    return os.path.join(get_package_share_directory('coco_lab_ros'),
                        'config', 'lab5_scenarios.json')


class GzWorld:
    """Gazebo's create and set_pose services, over gz-transport."""

    def __init__(self, world: str):
        """Import gz-transport lazily (tests construct the node without it)."""
        from gz.msgs10.boolean_pb2 import Boolean
        from gz.msgs10.entity_factory_pb2 import EntityFactory
        from gz.msgs10.pose_pb2 import Pose
        from gz.transport13 import Node as GzNode
        self._types = (Boolean, EntityFactory, Pose)
        self._node = GzNode()
        self.world = world

    def create(self, sdf: str, x: float = 0.0, y: float = 0.0,
               timeout_ms: int = 5000) -> bool:
        """Spawn a model from an SDF string at a world-frame ``(x, y)``."""
        Boolean, EntityFactory, _ = self._types
        req = EntityFactory()
        req.sdf = sdf
        req.pose.position.x, req.pose.position.y = x, y
        ok, rep = self._node.request(f'/world/{self.world}/create', req,
                                     EntityFactory, Boolean, timeout_ms)
        return bool(ok and rep.data)

    def set_pose(self, name: str, x: float, y: float, yaw: float,
                 timeout_ms: int = 200) -> bool:
        """Teleport model ``name`` to a world-frame planar pose."""
        import math
        Boolean, _, Pose = self._types
        req = Pose()
        req.name = name
        req.position.x, req.position.y, req.position.z = x, y, 0.0
        req.orientation.z = math.sin(yaw / 2.0)
        req.orientation.w = math.cos(yaw / 2.0)
        ok, rep = self._node.request(f'/world/{self.world}/set_pose', req,
                                     Pose, Boolean, timeout_ms)
        return bool(ok and rep.data)


class LabActors(Node):
    """The actor driver (see the module doc)."""

    def __init__(self, gz=None, **kwargs):
        """Load the scenario; subscribe ground truth; start the timer."""
        super().__init__('lab_actors', **kwargs)
        d = self.declare_parameter
        d('scenarios_file', '')
        d('scenario', '')
        d('world', 'coco_world')
        d('world_to_map', [2.0, 0.0])
        d('rate_hz', 20.0)
        d('odom_topic', '/model/coco/odometry')
        d('spawn', True)
        p = {n: self.get_parameter(n).value for n in (
            'scenarios_file', 'scenario', 'world', 'world_to_map',
            'rate_hz', 'odom_topic', 'spawn')}
        self.p = p
        path = p['scenarios_file'] or default_scenarios_file()
        scenarios = actors.load_scenarios(path)
        if p['scenario'] not in scenarios:
            raise ValueError(f'unknown scenario {p["scenario"]!r}; '
                             f'have {sorted(scenarios)}')
        self.scenario = scenarios[p['scenario']]
        self.actors = list(self.scenario.get('actors', []))
        self.offset = (float(p['world_to_map'][0]),
                       float(p['world_to_map'][1]))
        self.t_trigger = {a['id']: None for a in self.actors}
        self._lock = threading.Lock()
        self._robot = None
        self._gz = gz
        self._spawned = False
        self._pub = self.create_publisher(String, '/lab/actors', STATUS_QOS)
        self.create_subscription(Odometry, p['odom_topic'], self._on_odom,
                                 QoSProfile(depth=10))
        self._timer = self.create_timer(1.0 / float(p['rate_hz']),
                                        self._tick)

    def model_name(self, actor) -> str:
        """Return the Gazebo model name of ``actor``."""
        return f'lab_{actor["id"]}'

    def _on_odom(self, msg):
        x = msg.pose.pose.position.x + self.offset[0]
        y = msg.pose.pose.position.y + self.offset[1]
        with self._lock:
            self._robot = (x, y)

    def _spawn(self):
        if self._gz is None:
            self._gz = GzWorld(self.p['world'])
        ok = True
        for a in self.actors:
            x, y, _ = actors.actor_pose(a, None, 0.0)
            ok = self._gz.create(actors.model_sdf(self.model_name(a)),
                                 x - self.offset[0], y - self.offset[1]) and ok
        self._spawned = True
        self.get_logger().info(f'spawned {len(self.actors)} actor(s): '
                               f'{"ok" if ok else "FAILED"}')
        return ok

    def poses_at(self, t):
        """Return ``{id: (x, y, yaw)}``, map frame, at sim time ``t``."""
        return {a['id']: actors.actor_pose(a, self.t_trigger[a['id']], t)
                for a in self.actors}

    def _tick(self):
        if not self.actors:
            return
        if not self._spawned:
            if not self.p['spawn']:
                self._spawned = True
            elif not self._spawn():
                return
        t = self.get_clock().now().nanoseconds * 1e-9
        with self._lock:
            robot = self._robot
        if robot is not None:
            for a in self.actors:
                if (self.t_trigger[a['id']] is None
                        and actors.triggered(a['trigger'], robot)):
                    self.t_trigger[a['id']] = t
                    self.get_logger().info(f'{a["id"]} triggered at t={t:.3f}'
                                           f' robot={robot}')
        poses = self.poses_at(t)
        sent = {}
        for a in self.actors:
            x, y, yaw = poses[a['id']]
            sent[a['id']] = self._gz.set_pose(
                self.model_name(a), x - self.offset[0], y - self.offset[1],
                yaw) if self._gz is not None else None
        self._pub.publish(String(data=json.dumps({
            't': t, 'robot': robot, 'trigger': self.t_trigger,
            'poses': {k: list(v) for k, v in poses.items()}, 'set': sent},
            sort_keys=True, separators=(',', ':'))))


def main(args=None):
    """Run the node until shutdown."""
    rclpy.init(args=args)
    node = LabActors()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
