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
Occupancy-grid mapping with known poses, in log-odds.

The textbook algorithm (*Probabilistic Robotics*, table 9.1): every cell
holds the log-odds ``l = log(p / (1 - p))`` that it is occupied, starting
at 0 (p = 0.5, "no idea"). A LiDAR beam is an *inverse sensor model*: the
cell its range ends in gets ``+l_occ`` and every cell the beam passed
through on the way gets ``l_free`` (negative). Adding log-odds is Bayes'
rule for a binary cell with independent measurements, so -- until the
clamp engages -- the order of the updates does not matter (tested).
Clamping to ``[l_min, l_max]`` keeps a cell able to change its mind, at
the price of that order independence.

Cells a beam crosses are found with Bresenham's line algorithm between the
sensor's cell and the endpoint's cell -- the same traversal ROS's costmap
uses for clearing. A beam with no return (``inf``) clears up to
``miss_range`` if that is set, and marks nothing occupied.

**What leaves this module** is the ROS ``nav_msgs/OccupancyGrid``
convention, one byte per cell: ``0..100`` = probability of occupancy in
percent, ``255`` = never observed (ROS's -1). Thresholded at
``occupied_thresh`` / ``free_thresh`` (nav2 map_saver's defaults, 0.65 and
0.25), the same bytes become a :class:`coco_lab.maps.LabMap`
(FREE / OCCUPIED / UNKNOWN) that :mod:`coco_lab.mapeval` scores.

Grid cells are indexed ``ix + iy * width`` with ``iy`` growing NORTH (as
:class:`coco_lab.sketch.SketchMap`); a LabMap's row 0 is the NORTH row,
and :meth:`OccupancyGrid.to_u8` / :meth:`to_labmap` do that flip.
"""

from array import array
from dataclasses import asdict, dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .maps import FREE, LabMap, OCCUPIED, UNKNOWN

#: ``nav_msgs/OccupancyGrid``'s "unknown" (-1), as an unsigned byte.
U8_UNKNOWN = 255


class GridError(ValueError):
    """A grid parameter or input out of range."""


@dataclass(frozen=True)
class GridParams:
    """The inverse sensor model and the thresholds; every field documented."""

    #: log-odds added to the cell a beam ENDS in: p = 0.7 -> 0.847
    l_occ: float = 0.85
    #: log-odds added to every cell a beam passed through: p = 0.4 -> -0.405
    l_free: float = -0.4
    #: clamp, so a cell seen occupied a thousand times can still be cleared
    l_min: float = -4.0
    l_max: float = 4.0
    #: a beam with no return clears this far (metres); 0 = clears nothing
    miss_range: float = 0.0
    #: nav2 map_saver's thresholds, for the FREE / OCCUPIED / UNKNOWN map
    occupied_thresh: float = 0.65
    free_thresh: float = 0.25

    def check(self) -> None:
        """Raise :class:`GridError` unless the parameters make sense."""
        if not (self.l_occ > 0 and self.l_free < 0):
            raise GridError('l_occ must be > 0 and l_free < 0')
        if not (self.l_min < 0 < self.l_max):
            raise GridError('need l_min < 0 < l_max')
        if not (0 <= self.miss_range <= 100):
            raise GridError('miss_range must be 0..100 m')
        if not (0 < self.free_thresh < 0.5 < self.occupied_thresh < 1):
            raise GridError('need 0 < free_thresh < 0.5 < occupied_thresh < 1')

    def to_dict(self) -> Dict[str, float]:
        """Return a JSON-ready dict."""
        return asdict(self)


def bresenham(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """
    Return the cells of the line from ``(x0, y0)`` to ``(x1, y1)``, inclusive.

    Integer Bresenham, every octant: consecutive cells are 8-neighbours and
    the first and last cells are the end points (tested).
    """
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    out = []
    x, y = x0, y0
    while True:
        out.append((x, y))
        if x == x1 and y == y1:
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def sensor_pose(pose: Tuple[float, float, float],
                mount: Tuple[float, float, float]
                ) -> Tuple[float, float, float]:
    """Return the sensor's pose in the map for a ``base_footprint`` pose."""
    x, y, th = pose
    mx, my, myaw = mount
    c, s = math.cos(th), math.sin(th)
    return (x + c * mx - s * my, y + s * mx + c * my, th + myaw)


class OccupancyGrid:
    """A log-odds occupancy grid over a fixed, placed rectangle."""

    def __init__(self, width: int, height: int, resolution: float,
                 origin: Tuple[float, float],
                 params: Optional[GridParams] = None):
        """Start an all-unknown ``width x height`` grid at ``origin``."""
        if not (0 < width <= 4096 and 0 < height <= 4096):
            raise GridError(f'grid {width} x {height} out of range')
        if not (0 < resolution <= 10 and math.isfinite(resolution)):
            raise GridError(f'resolution {resolution!r} out of range')
        self.width = int(width)
        self.height = int(height)
        self.resolution = float(resolution)
        self.origin = (float(origin[0]), float(origin[1]))
        self.params = params or GridParams()
        self.params.check()
        self.logodds = array('d', bytes(8 * self.width * self.height))
        self.seen = bytearray(self.width * self.height)

    @classmethod
    def like(cls, lab_map: LabMap,
             params: Optional[GridParams] = None) -> 'OccupancyGrid':
        """Return an empty grid with ``lab_map``'s size and placement."""
        return cls(lab_map.width, lab_map.height, lab_map.resolution,
                   lab_map.origin, params)

    def copy(self) -> 'OccupancyGrid':
        """Return an independent copy (FastSLAM copies maps on resampling)."""
        g = OccupancyGrid.__new__(OccupancyGrid)
        g.width, g.height = self.width, self.height
        g.resolution, g.origin, g.params = (self.resolution, self.origin,
                                            self.params)
        g.logodds = array('d', self.logodds)
        g.seen = bytearray(self.seen)
        return g

    def cell(self, x: float, y: float) -> Tuple[int, int]:
        """Return the (possibly out-of-grid) ``(ix, iy)`` containing a point."""
        r = self.resolution
        return (math.floor((x - self.origin[0]) / r),
                math.floor((y - self.origin[1]) / r))

    def inside(self, ix: int, iy: int) -> bool:
        """Return True if ``(ix, iy)`` is a cell of the grid."""
        return 0 <= ix < self.width and 0 <= iy < self.height

    def prob(self, ix: int, iy: int) -> float:
        """Return P(occupied) of a cell; 0.5 outside the grid."""
        if not self.inside(ix, iy):
            return 0.5
        return 1.0 - 1.0 / (1.0 + math.exp(self.logodds[ix + iy *
                                                          self.width]))

    def add(self, ix: int, iy: int, dl: float) -> None:
        """Add ``dl`` to a cell's log-odds, clamped (ignores outside cells)."""
        if 0 <= ix < self.width and 0 <= iy < self.height:
            i = ix + iy * self.width
            p = self.params
            v = self.logodds[i] + dl
            self.logodds[i] = p.l_max if v > p.l_max else \
                (p.l_min if v < p.l_min else v)
            self.seen[i] = 1

    def integrate(self, pose: Tuple[float, float, float],
                  ranges: Sequence[float], angles: Sequence[float],
                  mount: Tuple[float, float, float], range_min: float,
                  range_max: float) -> int:
        """
        Add one scan taken from ``pose`` (``base_footprint``); return beams used.

        ``angles[i]`` is beam i's angle in the sensor frame. A range below
        ``range_min`` is skipped; ``inf`` (no return) or one at or beyond
        ``range_max`` clears up to ``miss_range`` and marks nothing.
        """
        sx, sy, sth = sensor_pose(pose, mount)
        r = self.resolution
        ox, oy = self.origin
        x0 = math.floor((sx - ox) / r)
        y0 = math.floor((sy - oy) / r)
        p = self.params
        lf, lo, lmin, lmax = p.l_free, p.l_occ, p.l_min, p.l_max
        w, h = self.width, self.height
        lg, seen = self.logodds, self.seen
        used = 0
        for z, a in zip(ranges, angles):
            hit = True
            if not (z >= range_min):  # NaN-safe
                continue
            if z == math.inf or z >= range_max:
                if p.miss_range <= 0:
                    continue
                z = min(p.miss_range, range_max)
                hit = False
            ang = sth + a
            ex = sx + z * math.cos(ang)
            ey = sy + z * math.sin(ang)
            x1 = math.floor((ex - ox) / r)
            y1 = math.floor((ey - oy) / r)
            cells = bresenham(x0, y0, x1, y1)
            last = len(cells) - 1
            for j, (ix, iy) in enumerate(cells):
                if not (0 <= ix < w and 0 <= iy < h):
                    continue
                i = ix + iy * w
                if j == last and hit:
                    v = lg[i] + lo
                else:
                    v = lg[i] + lf
                lg[i] = lmax if v > lmax else (lmin if v < lmin else v)
                seen[i] = 1
            used += 1
        return used

    def to_u8(self) -> bytes:
        """
        Return the grid as ``nav_msgs/OccupancyGrid`` bytes, NORTH row first.

        ``0..100`` = round(100 * P(occupied)); ``255`` = never observed.
        """
        w, h = self.width, self.height
        out = bytearray(w * h)
        lg, seen = self.logodds, self.seen
        for iy in range(h):
            row = (h - 1 - iy) * w
            base = iy * w
            for ix in range(w):
                i = base + ix
                if not seen[i]:
                    out[row + ix] = U8_UNKNOWN
                else:
                    out[row + ix] = int(round(
                        100.0 - 100.0 / (1.0 + math.exp(lg[i]))))
        return bytes(out)

    def to_labmap(self, map_id: str = 'occupancy',
                  frame: Optional[str] = 'map') -> LabMap:
        """Threshold :meth:`to_u8` into a FREE / OCCUPIED / UNKNOWN LabMap."""
        return u8_to_labmap(self.to_u8(), self.width, self.height,
                            self.resolution, self.origin, self.params,
                            map_id, frame)


def u8_to_labmap(cells: bytes, width: int, height: int, resolution: float,
                 origin: Tuple[float, float],
                 params: Optional[GridParams] = None,
                 map_id: str = 'occupancy',
                 frame: Optional[str] = 'map') -> LabMap:
    """Threshold OccupancyGrid bytes (north row first) into a LabMap."""
    p = params or GridParams()
    occ_pct = 100.0 * p.occupied_thresh
    free_pct = 100.0 * p.free_thresh
    out = bytearray(len(cells))
    for i, v in enumerate(cells):
        if v == U8_UNKNOWN:
            out[i] = UNKNOWN
        elif v >= occ_pct:
            out[i] = OCCUPIED
        elif v <= free_pct:
            out[i] = FREE
        else:
            out[i] = UNKNOWN
    return LabMap(width, height, bytes(out), map_id=map_id,
                  resolution=resolution, origin=origin, frame=frame,
                  meta={'thresholds': [p.free_thresh, p.occupied_thresh]})


def map_from_poses(like: LabMap, poses: Sequence[Tuple[float, float, float]],
                   scans: Sequence[Sequence[float]], angles: Sequence[float],
                   mount: Tuple[float, float, float], range_min: float,
                   range_max: float,
                   params: Optional[GridParams] = None) -> OccupancyGrid:
    """Return the grid every ``(pose, scan)`` pair builds, in order."""
    g = OccupancyGrid.like(like, params)
    for pose, z in zip(poses, scans):
        g.integrate(pose, z, angles, mount, range_min, range_max)
    return g
