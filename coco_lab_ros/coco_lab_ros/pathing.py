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
Between cell paths and pose lists.

**To FollowPath** (:func:`path_poses`): one pose per cell, at the cell
CENTRE, in the costmap's frame. Each pose faces the next one (direction of
travel); the last pose takes the goal's yaw, which mirrors Smac 2D with
``use_final_approach_orientation: false`` (``smac_planner_2d.cpp``
@1.3.11 :344-346). The path is NOT smoothed: the learner's path is the one
driven.

**From Smac** (:func:`cells_from_poses`): Smac 2D publishes each cell at
``origin + mx * resolution`` with integer ``mx`` (``getWorldCoords``,
``nav2_smac_planner/utils.hpp`` @1.3.11 :44-53) -- the cell's lower-left
CORNER, not its centre. Mapping those back with ``floor`` would put a
corner that float error nudged below the edge into the wrong cell, so
they are mapped with ``round`` instead, and the residual is reported so a
caller can prove every pose sat on a corner.
"""

import math
from typing import List, Sequence, Tuple

from .costmap import Snapshot

Pose2D = Tuple[float, float, float]


def yaw_to_quaternion(yaw: float) -> Tuple[float, float, float, float]:
    """Return ``(x, y, z, w)`` for a rotation of ``yaw`` about z."""
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """Return the yaw of a quaternion."""
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def path_poses(cells: Sequence[Tuple[int, int]], snapshot: Snapshot,
               goal_yaw: float) -> List[Pose2D]:
    """Return ``(x, y, yaw)`` at each Nav2 cell's centre (see module doc)."""
    pts = [snapshot.cell_centre(mx, my) for mx, my in cells]
    out = []
    for i, (x, y) in enumerate(pts):
        if i + 1 < len(pts):
            nx, ny = pts[i + 1]
            yaw = math.atan2(ny - y, nx - x)
        else:
            yaw = goal_yaw
        out.append((x, y, yaw))
    return out


def cells_from_poses(points: Sequence[Tuple[float, float]],
                     snapshot: Snapshot, anchor: str = 'corner'
                     ) -> Tuple[List[Tuple[int, int]], float]:
    """
    Map published poses back to Nav2 cells.

    ``anchor='corner'`` for Smac 2D's poses (cell = round((w - o) / r)),
    ``'centre'`` for poses at cell centres (cell = round((w - o) / r -
    0.5)). Returns the cells and the largest distance, in cells, between
    a pose and its anchor -- 0 up to float error when every pose really
    sat on an anchor.
    """
    if anchor not in ('corner', 'centre'):
        raise ValueError(f'anchor must be corner or centre, got {anchor!r}')
    shift = 0.0 if anchor == 'corner' else 0.5
    ox, oy = snapshot.origin
    r = snapshot.resolution
    cells, worst = [], 0.0
    for x, y in points:
        fx, fy = (x - ox) / r - shift, (y - oy) / r - shift
        mx, my = round(fx), round(fy)
        worst = max(worst, abs(fx - mx), abs(fy - my))
        cells.append((int(mx), int(my)))
    return cells, worst
