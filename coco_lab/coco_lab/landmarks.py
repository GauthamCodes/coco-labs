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
Point landmarks and an IDEALISED landmark sensor, for EKF-SLAM.

**This sensor is idealised, and says so wherever it is shown.** COCO has
no landmark sensor: it has a 2D LiDAR (and a camera that finds coloured
targets). EKF-SLAM is taught on landmarks because that is where it is
clean, so this module invents the cleanest sensor that still teaches:

- a landmark is a POINT: a convex corner of an obstacle (:func:`corners`),
  extracted from the map by a fixed rule, so every map has them;
- the sensor returns ``(id, range, bearing)`` for each landmark within
  ``max_range`` and the field of view that is not hidden behind a wall --
  with the landmark's **identity known** (no data association problem,
  the hardest part of real landmark SLAM), Gaussian noise of a stated
  sigma, and nothing else (no false detections, no misses).

A real feature extractor on COCO's LiDAR would have to find those corners
in noisy points, and would sometimes confuse two of them. That gap is
named on the page, not hidden.
"""

from dataclasses import asdict, dataclass
import math
import random
from typing import Dict, List, Sequence, Tuple

from .maps import FREE, LabMap
from .sketch import SketchMap, wrap

#: ``(id, x, y)``
Landmark = Tuple[int, float, float]
#: ``(id, range, bearing)``: bearing from the robot's heading, radians
Observation = Tuple[int, float, float]


@dataclass(frozen=True)
class LandmarkSensor:
    """The idealised sensor's parameters."""

    max_range: float = 4.0
    #: half the field of view (pi = all round)
    half_fov: float = math.pi
    sigma_range: float = 0.05
    sigma_bearing: float = 0.02

    def check(self) -> None:
        """Raise ``ValueError`` unless the parameters make sense."""
        if not (0 < self.max_range <= 30):
            raise ValueError('max_range must be in (0, 30] m')
        if not (0 < self.half_fov <= math.pi):
            raise ValueError('half_fov must be in (0, pi]')
        if not (0 <= self.sigma_range <= 1 and 0 <= self.sigma_bearing <= 1):
            raise ValueError('sigmas must be in [0, 1]')

    def to_dict(self) -> Dict[str, float]:
        """Return a JSON-ready dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d) -> 'LandmarkSensor':
        """Inverse of :meth:`to_dict`."""
        s = cls(**{k: float(d[k]) for k in ('max_range', 'half_fov',
                                            'sigma_range', 'sigma_bearing')})
        s.check()
        return s


def corners(lab_map: LabMap, min_separation: float = 1.0,
            max_count: int = 32) -> List[Landmark]:
    """
    Return the map's convex obstacle corners, thinned, as landmarks.

    A blocked cell (anything not FREE) is a convex corner toward diagonal
    ``(dx, dy)`` if its two orthogonal neighbours that way and the diagonal
    one are all FREE; the landmark is the cell's outer corner point. Cells
    are visited row by row from the south-west, and a corner closer than
    ``min_separation`` to one already kept is dropped, so the result is
    deterministic. Ids are 0, 1, 2 ... in that order.
    """
    w, h = lab_map.width, lab_map.height
    occ = lab_map.occupancy
    res = lab_map.resolution
    ox, oy = lab_map.origin

    def free(ix, iy):
        return 0 <= ix < w and 0 <= iy < h and \
            occ[(h - 1 - iy) * w + ix] == FREE

    kept: List[Landmark] = []
    min2 = min_separation * min_separation
    for iy in range(1, h - 1):
        for ix in range(1, w - 1):
            if free(ix, iy):
                continue
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                if free(ix + dx, iy) and free(ix, iy + dy) and \
                        free(ix + dx, iy + dy):
                    px = ox + (ix + (1 if dx > 0 else 0)) * res
                    py = oy + (iy + (1 if dy > 0 else 0)) * res
                    if all((px - x) ** 2 + (py - y) ** 2 >= min2
                           for _, x, y in kept):
                        kept.append((len(kept), px, py))
                        if len(kept) >= max_count:
                            return kept
    return kept


def visible(smap: SketchMap, pose: Tuple[float, float, float],
            lm: Landmark, sensor: LandmarkSensor) -> bool:
    """
    Return True if the idealised sensor at ``pose`` sees landmark ``lm``.

    In range, in the field of view, and not behind a wall: a ray cast
    toward the corner must travel at least to within one and a half cells
    of it (a corner sits ON a wall, so the ray ends at the wall there).
    """
    x, y, th = pose
    _, lx, ly = lm
    d = math.hypot(lx - x, ly - y)
    if d > sensor.max_range or d < 1e-6:
        return False
    b = wrap(math.atan2(ly - y, lx - x) - th)
    if abs(b) > sensor.half_fov:
        return False
    hit = smap.cast(x, y, th + b, sensor.max_range + 1.0)
    return hit >= d - 1.5 * smap.resolution


def observe(smap: SketchMap, pose: Tuple[float, float, float],
            landmarks: Sequence[Landmark], sensor: LandmarkSensor,
            rng: random.Random) -> List[Observation]:
    """
    Return noisy ``(id, range, bearing)`` for every visible landmark.

    Exactly two ``rng.gauss`` draws per landmark *whether or not it is
    seen*, so one landmark's visibility never shifts another's noise.
    """
    x, y, th = pose
    out = []
    for lm in landmarks:
        nr = rng.gauss(0.0, sensor.sigma_range)
        nb = rng.gauss(0.0, sensor.sigma_bearing)
        if not visible(smap, pose, lm, sensor):
            continue
        _, lx, ly = lm
        r = math.hypot(lx - x, ly - y) + nr
        b = wrap(math.atan2(ly - y, lx - x) - th + nb)
        out.append((lm[0], max(r, 0.0), b))
    return out
