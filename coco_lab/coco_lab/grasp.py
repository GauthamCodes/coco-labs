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
The gated grasp (M4.3; README §5.1), behind the Stack's proximity gate.

A kinematic action; MODEL, SIMPLIFIED: no contact, no forces.

**The gate is the Stack's**: a target can be picked only when its axis is
inside the approach window in ``base_footprint`` -- 0.151 to 0.1565 m ahead,
the same for every colour (``coco_config.robot.approach_window``: the
forearm's self-collision bound and the arm's reach at the hover height) --
and within ``GRASP_MAX_LATERAL`` = 10 mm of the centreline. Those numbers
are copied here (coco_lab never imports coco_config: no ROS in the browser)
and pinned by ``coco_lab_ros/test/test_sketch_constants.py``.

A person cannot drive a robot into a 5.5 mm window with a keyboard, and
neither does the Stack: its ``approach_server`` aligns on the target and
creeps the last stretch. So the ``grasp`` input (the 3D Arena's E):

- with the target already in the window: grasps;
- with a target in the approach zone (up to ``APPROACH_RANGE`` ahead,
  within ``APPROACH_BEARING``): approaches it -- turns to face it, creeps
  forward at ``CREEP`` to the window's centre -- and then the gate decides;
- otherwise: refuses, and says why;
- while carrying: releases the target in front of the robot.

The pick itself is the arm's kinematic script (``coco_lab.arm``); the target
then rides with the robot: the magnet holds it (two fingers and a magnet;
the magnet does the holding, README §2 correction 2). Where the targets
stand is the frozen layout (``coco_lab.fetch_problem``), on the platforms,
so the grasp exists only on a World Spec v2 (terrain) session.
"""

import math
import struct
from typing import Dict, List, Optional, Tuple

from . import arm
from .fetch_problem import LAYOUT, TARGET_NOMINAL

#: coco_config.robot.approach_window(colour): identical for all four colours
WINDOW = (0.151, 0.1565)
#: coco_config.robot.GRASP_MAX_LATERAL
MAX_LATERAL = 0.010
#: the approach: how far ahead and how far off the nose a target may be (m, rad)
APPROACH_RANGE = 0.6
APPROACH_BEARING = math.radians(30.0)
#: the approach's speeds: turning (rad/s), creeping (m/s; custom_teleop.approach_server's
#: CREEP_SPEED, which stops on a 20 Hz tick, 1.5 mm; the model's is 10 Hz, 3 mm, wider than
#: half the window, so its last step is proportional); heading tolerance (rad)
TURN = 0.4
CREEP = 0.03
ALIGNED = math.radians(1.0)
#: the creep ends this close to the window's centre (m), or after this many ticks
SETTLED = 0.0005
MAX_CREEPS = 400
PHASES = ('idle', 'approach', 'pick', 'carry', 'release')
#: coco_config.robot.TARGETS: each cylinder's diameter, and their height (m); for drawing
TARGET_DIAMETER = {'red': 0.020, 'green': 0.024, 'blue': 0.028, 'yellow': 0.032}
TARGET_HEIGHT = 0.158
LAYOUT_TAG = b'coco.arena.grasp.v1\x00'


class Grasp:
    """The targets and the grasp's state; owned by the Arena once a grasp input arrives."""

    def __init__(self, world_to_map: Tuple[float, float]):
        dx, dy = world_to_map
        colour_of = {bay: colour for colour, bay in LAYOUT.items()}
        #: colour -> [x, y] in the MAP frame (where it stands, or where it was put down)
        self.targets: Dict[str, List[float]] = {
            colour_of[bay]: [p[0] + dx, p[1] + dy] for bay, p in sorted(TARGET_NOMINAL.items())}
        self.phase = 'idle'
        self.target: Optional[str] = None
        self.t0 = 0.0
        self.reason = ''
        #: ticks the approach has crept (it gives up after MAX_CREEPS)
        self.creeps = 0

    @staticmethod
    def in_base(pose, xy) -> Tuple[float, float]:
        """Return a map-frame point in base_footprint: (ahead, left)."""
        x, y, th = pose
        dx, dy = xy[0] - x, xy[1] - y
        c, s = math.cos(th), math.sin(th)
        return (c * dx + s * dy, -s * dx + c * dy)

    def gate(self, pose, colour) -> bool:
        """Return whether the target's axis is in the approach window (the Stack's gate)."""
        ax, ay = self.in_base(pose, self.targets[colour])
        return WINDOW[0] <= ax <= WINDOW[1] and abs(ay) <= MAX_LATERAL

    def nearest(self, pose) -> Optional[str]:
        """Return the target in the approach zone nearest the gripper, if any."""
        best = None
        for colour in sorted(self.targets):
            ax, ay = self.in_base(pose, self.targets[colour])
            if 0.0 < ax <= APPROACH_RANGE and abs(math.atan2(ay, ax)) <= APPROACH_BEARING:
                d = math.hypot(ax, ay)
                if best is None or d < best[0]:
                    best = (d, colour)
        return best[1] if best else None

    def press(self, a) -> None:
        """Take the grasp input: grasp, approach, refuse, or release (module doc)."""
        if self.phase == 'carry':
            self.phase, self.t0 = 'release', a.t_world
            self.reason = f'releasing the {self.target} target'
            return
        if self.phase != 'idle':
            return
        colour = self.nearest(a.pose)
        if colour is None:
            self.reason = (f'no target within {APPROACH_RANGE:.1f} m ahead: drive to one, '
                           'facing it, then grasp')
            return
        self.target = colour
        self.creeps = 0
        if self.gate(a.pose, colour):
            self.phase, self.t0 = 'pick', a.t_world
            self.reason = f'in the window: picking the {colour} target'
        else:
            self.phase = 'approach'
            self.reason = f'approaching the {colour} target'

    def command(self, a) -> Optional[Tuple[float, float]]:
        """Return the approach's (v, w), or None when the approach is over."""
        if self.phase != 'approach':
            return None
        ax, ay = self.in_base(a.pose, self.targets[self.target])
        bearing = math.atan2(ay, ax)
        if abs(bearing) > ALIGNED:
            return (0.0, max(-TURN, min(TURN, bearing / a.dt)))
        mid = (WINDOW[0] + WINDOW[1]) / 2
        if ax - mid > SETTLED and self.creeps < MAX_CREEPS:
            # proportional in the last step: a 3 mm creep step would jump a 5.5 mm window
            self.creeps += 1
            return (min(CREEP, (ax - mid) / a.dt), 0.0)
        if self.gate(a.pose, self.target):
            self.phase, self.t0 = 'pick', a.t_world
            self.reason = f'in the window: picking the {self.target} target'
        else:
            self.phase = 'idle'
            self.reason = (f'the {self.target} target is not in the window (ahead '
                           f'{ax * 1000:.1f} mm, left {ay * 1000:.1f} mm): not picked')
            self.target = None
        return (0.0, 0.0)

    def step(self, a) -> None:
        """Run the pick or release script after the robot moved; a carried target rides."""
        if self.phase in ('pick', 'release') and a.t_world - self.t0 >= arm.script_seconds():
            if self.phase == 'pick':
                self.phase, self.reason = 'carry', f'the magnet holds the {self.target} target'
            else:
                self.phase, self.target, self.reason = 'idle', None, 'released'
        if self.phase in ('carry', 'release') and self.target is not None:
            x, y, th = a.pose
            mid = (WINDOW[0] + WINDOW[1]) / 2
            self.targets[self.target] = [x + math.cos(th) * mid, y + math.sin(th) * mid]

    def arm_state(self, a) -> Optional[Dict[str, object]]:
        """Return the arm's joints during a pick (its script), else None."""
        if self.phase == 'pick':
            return arm.script_state(min(a.t_world - self.t0, arm.script_seconds() - 1e-6))
        return None

    def state_bytes(self, q) -> bytes:
        """Return phase, target and every target's position (coco.arena.grasp.v1)."""
        which = 0 if self.target is None else 1 + sorted(self.targets).index(self.target)
        parts = [LAYOUT_TAG, struct.pack('<BB', PHASES.index(self.phase), which),
                 struct.pack('<qI', q(self.t0), self.creeps)]
        for colour in sorted(self.targets):
            x, y = self.targets[colour]
            parts.append(struct.pack('<2q', q(x), q(y)))
        return b''.join(parts)
