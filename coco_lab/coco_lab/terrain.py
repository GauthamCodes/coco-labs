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
Kinematic terrain following (M4.3; README §5.1, invariant 10).

The Arena stays planar kinematics: the robot moves in (x, y, theta) exactly
as on the flat floor. Terrain adds only what the ramp geometry implies, read
from World Spec v2's ``elevation`` (docs/v2/adr/0007-world-spec-elevation.md):
the height under the robot and the pitch and roll its wheel base would take
standing on the surface. Nothing here simulates tipping, slip, friction,
traction or contact forces; those lessons come from Gazebo (README §2
correction 5). Everything is a few arithmetic operations on fixed geometry,
so it is identical in CPython and Pyodide.

Conventions: map frame, z up; ROS (REP-103) angles -- pitch positive when
the nose goes DOWN, roll positive when the left side goes UP.
"""

import math
from typing import List, Optional, Tuple

#: a height difference larger than this across a solid's edge is a drop the
#: robot cannot drive over (m): the side of a wedge or of a platform. The
#: wheels are 0.0585 m in radius; the ramps' feet meet the floor at 0.
STEP = 0.02
#: yaw within this of 0 or pi is axis-aligned (every solid in COCO's arena is)
_AXIS_EPS = 1e-6


class TerrainError(ValueError):
    """Elevation this module does not handle."""


class Terrain:
    """The elevated solids of a World Spec v2, in the MAP frame."""

    def __init__(self, spec):
        dx, dy = spec['world_to_map']
        self.solids = []
        for e in spec['elevation']:
            if e['kind'] == 'wedge':
                c, s = math.cos(e['yaw']), math.sin(e['yaw'])
                if abs(s) > _AXIS_EPS:
                    raise TerrainError(f'{e["id"]}: only axis-aligned wedges (yaw 0 or pi)')
                self.solids.append(('wedge', e['foot'][0] + dx, e['foot'][1] + dy,
                                    1.0 if c > 0 else -1.0, e['run'], e['rise'], e['width'],
                                    e['id']))
            else:
                (cx, cy), (sx, sy, sz) = e['center'], e['size']
                self.solids.append(('platform', cx + dx, cy + dy, sx, sy, sz, e['id']))

    def height(self, x: float, y: float) -> float:
        """Return the surface height at (x, y): the highest solid top there, else 0."""
        h = 0.0
        for s in self.solids:
            if s[0] == 'wedge':
                _, fx, fy, d, run, rise, width, _ = s
                u = (x - fx) * d
                if 0.0 <= u <= run and abs(y - fy) <= width / 2:
                    h = max(h, rise * u / run)
            else:
                _, cx, cy, sx, sy, sz, _ = s
                if abs(x - cx) <= sx / 2 and abs(y - cy) <= sy / 2:
                    h = max(h, sz)
        return h

    def pose(self, x: float, y: float, theta: float, half_length: float,
             half_track: float) -> Tuple[float, float, float]:
        """
        ``(z, pitch, roll)`` of a wheel base centred at (x, y), heading theta.

        z is the surface height under the centre; pitch and roll are the
        slopes between the surface heights under the front and back, and
        the left and right, of the wheel base (``half_length``,
        ``half_track`` from its centre).
        """
        c, s = math.cos(theta), math.sin(theta)
        hf = self.height(x + c * half_length, y + s * half_length)
        hb = self.height(x - c * half_length, y - s * half_length)
        hl = self.height(x - s * half_track, y + c * half_track)
        hr = self.height(x + s * half_track, y - c * half_track)
        return (self.height(x, y), math.atan2(hb - hf, 2 * half_length),
                math.atan2(hl - hr, 2 * half_track))

    def rects_above(self, z: float) -> List[Tuple[float, float, float, float]]:
        """
        Return where the surface stands at or above height ``z``.

        Axis-aligned rectangles ``(x0, x1, y0, y1)``. A horizontal LiDAR beam at height
        ``z`` stops at the first of them it meets (the scan-height
        silhouette, as World Spec v1's ramp rectangles are on the flat floor).
        """
        out = []
        for s in self.solids:
            if s[0] == 'wedge':
                _, fx, fy, d, run, rise, width, _ = s
                if z > rise:
                    continue
                u0 = max(0.0, z / rise * run)
                a, b = fx + d * u0, fx + d * run
                out.append((min(a, b), max(a, b), fy - width / 2, fy + width / 2))
            else:
                _, cx, cy, sx, sy, sz, _ = s
                if sz >= z:
                    out.append((cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2))
        return out

    def drop_threshold(self, spacing: float) -> float:
        """
        Return the height step no slope here explains, ``spacing`` apart.

        More than the steepest wedge rises over ``spacing``, plus STEP.
        """
        grades = [s[5] / s[4] for s in self.solids if s[0] == 'wedge']
        return STEP + spacing * max(grades, default=0.0)

    def bounds(self) -> List[Tuple[float, float, float, float]]:
        """Each solid's footprint ``(x0, x1, y0, y1)``."""
        return self.rects_above(0.0)


def ray_rect(ox: float, oy: float, dx: float, dy: float,
             r: Tuple[float, float, float, float]) -> Optional[float]:
    """
    Return the distance along the unit ray (o, d) to rectangle r, or None.

    A ray starting inside the rectangle gives None: the beam is above the
    surface where the robot stands (its own height), so it only meets the
    surface where it rises ahead.
    """
    x0, x1, y0, y1 = r
    if x0 <= ox <= x1 and y0 <= oy <= y1:
        return None
    t0, t1 = -math.inf, math.inf
    for o, d, lo, hi in ((ox, dx, x0, x1), (oy, dy, y0, y1)):
        if abs(d) < 1e-15:
            if o < lo or o > hi:
                return None
            continue
        a, b = (lo - o) / d, (hi - o) / d
        if a > b:
            a, b = b, a
        t0, t1 = max(t0, a), min(t1, b)
        if t0 > t1:
            return None
    return t0 if t0 >= 0 else None
