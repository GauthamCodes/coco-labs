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
Lab 5's moving actors: where each one is, as a pure function of time.

The design is M7_DESIGN §2.6, "Dynamic obstacles -- apron only":

- an upright grey cylinder, 0.30 m across and 0.60 m tall, so it straddles
  the LiDAR's scan plane (0.2135 m) and gives >= 4 returns anywhere on the
  apron (derived there);
- **kinematic**: its pose is DRIVEN, never simulated, and it has NO
  collision geometry -- the LiDAR (``gpu_lidar``, which renders visuals)
  sees it, the physics engine does not, so it can never push, tip or be
  pushed by the robot. A contact is therefore never *felt*; it is
  *measured*, from ground truth, as a clearance at or below zero
  (``coco_lab.movemetrics``);
- **robot-triggered**, the design's second named pattern: the actor holds
  at its first waypoint until the robot's ground-truth position crosses a
  declared line, then walks its waypoints once at a fixed speed and parks
  at the last. Random walks and Poisson arrivals were rejected there,
  because a stochastic actor makes every run incomparable;
- **on the open apron only**: every waypoint, and the whole swept
  cylinder, must lie inside :data:`APRON` (map frame) -- never on a ramp,
  a platform or in a bay. :func:`validate` refuses anything else.

Everything here is in the MAP frame (``navigation_world.json``'s
``world_to_map`` = (2, 0): map = world + (2, 0)); the node converts to the
world frame only to call Gazebo.

This module is pure (no rclpy, no gz): the tests pin it, and the same
function the node calls reproduces any recorded actor pose from its
trigger time.
"""

import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]

#: The open apron, map frame: between the west spine's corridor landmarks
#: (world x -3.7, their east faces) and the bays' approach walls (world x
#: -1.0), wall to wall in y (world +-8.9). Derived from
#: navigation_world.json's boxes; a test re-derives it.
APRON = {'x': (-1.7, 1.0), 'y': (-8.9, 8.9)}

#: The cylinder (M7_DESIGN §2.6).
RADIUS = 0.15
HEIGHT = 0.60
#: The design's speed range and hard cap, m/s.
SPEED_RANGE = (0.20, 0.30)
SPEED_CAP = 0.35

TRIGGER_AXES = ('x', 'y')
TRIGGER_OPS = ('<', '>')


class ScenarioError(ValueError):
    """A scenario or actor that breaks the design's rules."""


def _finite(*vals) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v)
               for v in vals)


def validate_actor(actor: Dict[str, object]) -> None:
    """Raise :class:`ScenarioError` unless ``actor`` obeys §2.6."""
    wps = actor.get('waypoints')
    if not isinstance(wps, list) or len(wps) < 2:
        raise ScenarioError('an actor needs at least two waypoints')
    for p in wps:
        if not (isinstance(p, list) and len(p) == 2 and _finite(*p)):
            raise ScenarioError(f'bad waypoint {p!r}')
        x, y = p
        if not (APRON['x'][0] + RADIUS <= x <= APRON['x'][1] - RADIUS
                and APRON['y'][0] + RADIUS <= y <= APRON['y'][1] - RADIUS):
            # segments between in-apron points stay in the (convex) apron
            raise ScenarioError(f'waypoint {p} puts the actor off the '
                                f'apron {APRON}')
    for a, b in zip(wps, wps[1:]):
        if a == b:
            raise ScenarioError('repeated waypoint')
    speed = actor.get('speed')
    if not (_finite(speed) and SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]):
        raise ScenarioError(f'speed {speed!r} outside {SPEED_RANGE} m/s '
                            f'(M7_DESIGN §2.6)')
    trig = actor.get('trigger')
    if not (isinstance(trig, dict) and trig.get('axis') in TRIGGER_AXES
            and trig.get('op') in TRIGGER_OPS
            and _finite(trig.get('value'))):
        raise ScenarioError(f'bad trigger {trig!r}')
    if not isinstance(actor.get('id'), str) or not actor['id']:
        raise ScenarioError('an actor needs an id')


def validate(scenario: Dict[str, object]) -> None:
    """Raise :class:`ScenarioError` unless every actor is valid."""
    ids = []
    for a in scenario.get('actors', []):
        validate_actor(a)
        ids.append(a['id'])
    if len(ids) != len(set(ids)):
        raise ScenarioError('duplicate actor id')


def route_length(waypoints: Sequence[Point]) -> float:
    """Return the length of the waypoint polyline (m)."""
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(waypoints, waypoints[1:]))


def position_along(waypoints: Sequence[Point], s: float
                   ) -> Tuple[float, float, float]:
    """
    Return ``(x, y, yaw)`` at arc length ``s`` along the waypoints.

    ``s`` is clamped to ``[0, length]``: before it starts the actor is at
    the first waypoint facing the first segment, after it ends it is
    parked at the last facing the last segment.
    """
    s = max(0.0, s)
    for a, b in zip(waypoints, waypoints[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        yaw = math.atan2(b[1] - a[1], b[0] - a[0])
        if s <= seg:
            f = s / seg
            return a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), yaw
        s -= seg
    a, b = waypoints[-2], waypoints[-1]
    return b[0], b[1], math.atan2(b[1] - a[1], b[0] - a[0])


def triggered(trigger: Dict[str, object], robot_xy: Point) -> bool:
    """Return whether the robot's map-frame position fires ``trigger``."""
    v = robot_xy[0] if trigger['axis'] == 'x' else robot_xy[1]
    return v < trigger['value'] if trigger['op'] == '<' else \
        v > trigger['value']


def actor_pose(actor: Dict[str, object], t_trigger: Optional[float],
               t: float) -> Tuple[float, float, float]:
    """
    Return the actor's map-frame ``(x, y, yaw)`` at sim time ``t``.

    ``t_trigger`` is the sim time its trigger fired, or ``None`` if it has
    not: then the actor holds at its first waypoint.
    """
    if t_trigger is None:
        return position_along(actor['waypoints'], 0.0)
    return position_along(actor['waypoints'],
                          float(actor['speed']) * max(0.0, t - t_trigger))


def walk_duration(actor: Dict[str, object]) -> float:
    """Return how long the actor walks once triggered (s)."""
    return route_length(actor['waypoints']) / float(actor['speed'])


def model_sdf(name: str, radius: float = RADIUS, height: float = HEIGHT
              ) -> str:
    """
    Return the actor's SDF: a visual-only cylinder, gravity off.

    No ``<collision>`` element, by design (module doc): the LiDAR renders
    the visual; the physics engine has nothing to collide with.
    """
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{name}">
    <static>false</static>
    <link name="body">
      <gravity>false</gravity>
      <inertial><mass>10.0</mass>
        <inertia><ixx>1</ixx><iyy>1</iyy><izz>1</izz></inertia>
      </inertial>
      <visual name="visual">
        <pose>0 0 {height / 2:.4f} 0 0 0</pose>
        <geometry><cylinder><radius>{radius:.4f}</radius>
          <length>{height:.4f}</length></cylinder></geometry>
        <material><ambient>0.45 0.45 0.45 1</ambient>
          <diffuse>0.45 0.45 0.45 1</diffuse></material>
      </visual>
    </link>
  </model>
</sdf>
"""


def load_scenarios(path: str) -> Dict[str, Dict[str, object]]:
    """Load and validate a scenarios file; return ``{id: scenario}``."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for sc in data['scenarios']:
        validate(sc)
        if sc['id'] in out:
            raise ScenarioError(f'duplicate scenario {sc["id"]!r}')
        out[sc['id']] = sc
    return out


def schedule(actor: Dict[str, object], t_trigger: float, t_end: float,
             dt: float = 0.05) -> List[Tuple[float, float, float, float]]:
    """
    Return ``[(t, x, y, yaw)]`` from the trigger to ``t_end``, every ``dt``.

    The arc length is ``speed x k x dt`` from the step count, so the poses
    do not depend on the trigger time at all (only the ``t`` column does).
    """
    n = int(math.floor((t_end - t_trigger) / dt + 1e-9))
    return [(t_trigger + k * dt,) + position_along(
        actor['waypoints'], float(actor['speed']) * k * dt)
        for k in range(n + 1)]
