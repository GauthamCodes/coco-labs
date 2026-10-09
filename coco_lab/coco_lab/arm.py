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
COCO's arm, kinematically (M2.6; MODEL): two revolute joints in the side view.

The geometry is ``coco_moveit_config/scripts/arm_ik.py``'s (derived there
from the URDF chain; ``test_arm.py`` pins every constant to that file): a
shoulder and an elbow rotating about the base y axis, so the arm lives in
the robot's x-z plane, and "the pinch" is the midpoint between the closed
fingertips. The gripper has **two fingers and a magnet; the magnet does
the holding** -- the fingers only centre the target (``GRIP_OPEN`` /
``GRIP_CLOSED``, ``coco_moveit_config/scripts/arm_control.py``).

:data:`GRASP_SCRIPT` is the pick the real grasp runs, as joint-space
waypoints (``pick_place.py``'s verified poses: home, up, hover above the
target, the grasp, raise, lift), each reached by linear interpolation in
joint space over its duration. SIMPLIFIED: no dynamics, no collision, no
MoveIt plan between the poses, and the target is assumed where the grasp
pose puts the pinch (``pick_place.py``'s pedestal-top target, (0.152,
0.128) in base_footprint).
"""

import math
from typing import Dict, List, Optional, Tuple

S_X = -0.075
S_Z = 0.1485
L1 = 0.150000
L2 = 0.086739
PHI1 = 0.007576
GAMMA0 = -0.021274
SHOULDER_LIMITS = (-3.84, 1.0)
ELBOW_LIMITS = (-1.6, 1.6)
GRIP_OPEN = (0.5, -0.5)
GRIP_CLOSED = (0.02, -0.02)
#: pick_place.py's verified joint poses (shoulder, elbow)
POSES = {
    'home': (0.0, 0.0),
    'up': (-1.2, -0.5),
    'grasp': (0.30, 0.58),
    'raise': (0.10, 0.45),
    'lift': (-0.3, 0.2),
}
#: the pedestal-top target pick_place.py grasps, base_footprint (x, z)
TARGET_XZ = (0.152, 0.128)
#: coco_config.robot.GRASP_HOVER_CLEARANCE
HOVER_CLEARANCE = 0.07


def fk(q_shoulder: float, q_elbow: float) -> Tuple[float, float]:
    """Return the pinch point (x, z) in base_footprint."""
    alpha = PHI1 - q_shoulder
    beta = alpha + GAMMA0 + q_elbow
    return (S_X + L1 * math.cos(alpha) + L2 * math.cos(beta),
            S_Z + L1 * math.sin(alpha) + L2 * math.sin(beta))


def elbow_point(q_shoulder: float) -> Tuple[float, float]:
    """Return the elbow joint (x, z) in base_footprint, for drawing."""
    alpha = PHI1 - q_shoulder
    return (S_X + L1 * math.cos(alpha), S_Z + L1 * math.sin(alpha))


def ik(x: float, z: float) -> List[Tuple[float, float]]:
    """Return every within-limits (shoulder, elbow) reaching (x, z)."""
    rx, rz = x - S_X, z - S_Z
    cos_g = (rx * rx + rz * rz - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    if abs(cos_g) > 1.0:
        return []
    out = []
    for sign in (1.0, -1.0):
        gamma = sign * math.acos(max(-1.0, min(1.0, cos_g)))
        q_elbow = gamma - GAMMA0
        alpha = math.atan2(rz, rx) - math.atan2(
            L2 * math.sin(gamma), L1 + L2 * math.cos(gamma))
        if not ELBOW_LIMITS[0] <= q_elbow <= ELBOW_LIMITS[1]:
            continue
        q_p = math.atan2(math.sin(PHI1 - alpha), math.cos(PHI1 - alpha))
        for q_s in (q_p, q_p - 2 * math.pi, q_p + 2 * math.pi):
            if SHOULDER_LIMITS[0] <= q_s <= SHOULDER_LIMITS[1]:
                out.append((q_s, q_elbow))
                break
    return out


def hover_pose() -> Tuple[float, float]:
    """Return the pose straight above the target (pick_place.py's 'hover')."""
    return ik(TARGET_XZ[0], TARGET_XZ[1] + HOVER_CLEARANCE)[0]


#: (phase, to pose, seconds, fingers, magnet on) -- the pick, in order
GRASP_SCRIPT = (
    ('unfold', 'up', 1.0, GRIP_CLOSED, False),
    ('hover', 'hover', 1.0, GRIP_OPEN, False),
    ('descend', 'grasp', 1.0, GRIP_OPEN, False),
    ('magnet', 'grasp', 0.5, GRIP_CLOSED, True),
    ('raise', 'raise', 0.5, GRIP_CLOSED, True),
    ('lift', 'lift', 1.0, GRIP_CLOSED, True),
    ('stow', 'home', 1.0, GRIP_CLOSED, True),
)


def pose_named(name: str) -> Tuple[float, float]:
    """Return a named joint pose ('hover' is solved by IK)."""
    return hover_pose() if name == 'hover' else POSES[name]


def script_state(t: float) -> Optional[Dict[str, object]]:
    """
    Return the arm at ``t`` seconds into the pick, or None once it is over.

    Joints move linearly from the previous phase's pose; the fingers and
    the magnet take the phase's value at its start. ``holding`` is the
    magnet's: True from the magnet phase on.
    """
    q = POSES['home']
    start = 0.0
    for phase, to, dur, fingers, magnet in GRASP_SCRIPT:
        goal = pose_named(to)
        if t < start + dur - 1e-9:
            f = (t - start) / dur
            j1 = q[0] + (goal[0] - q[0]) * f
            j2 = q[1] + (goal[1] - q[1]) * f
            x, z = fk(j1, j2)
            return {'joint1': j1, 'joint2': j2, 'ee_x': x, 'ee_z': z,
                    'finger_left': fingers[0], 'finger_right': fingers[1],
                    'magnet_on': magnet, 'holding': magnet, 'phase': phase}
        q, start = goal, start + dur
    return None


def script_seconds() -> float:
    """Return the pick's whole duration."""
    return sum(d for _, _, d, _, _ in GRASP_SCRIPT)
