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
Sketch: a 2D differential-drive robot with a ray-cast LiDAR, on a LabMap.

**Sketch is a model, not the robot.** It exists so a learner can drive,
kidnap and localise without Gazebo, and it is compared with Gazebo at
identical poses (``docs/labs/LAB2_LOCALISE.md``, "Sketch fidelity"). What
it leaves out is stated here, not discovered later:

- **The world is the 2D occupancy map.** A ray stops at the first cell
  that is not FREE (occupied or unknown) or at the map edge. Gazebo's
  LiDAR sees a 3D world: a ramp the map marks occupied may be under the
  beam, and a slope may be hit where the map has no wall.
- **Wheels never slip.** The robot moves exactly as commanded unless the
  move would put its collision circle into a blocked cell, in which case
  it does not move that step. Odometry error is *injected*, by the
  odometry motion model's four alphas (Thrun, Burgard and Fox,
  *Probabilistic Robotics*, table 5.6), not produced by contact physics.
  COCO is a four-wheel skid-steer robot; Gazebo's odometry error comes
  from slip, Sketch's from this model.
- **Range noise is Gaussian** with a configurable sigma, clipped to the
  sensor's range. Gazebo's ``gpu_lidar`` for COCO declares no noise.

**Determinism.** Everything random draws from a ``random.Random`` seeded
by the caller, and nothing reads a clock: the same inputs give the same
run, bit for bit, on the same platform (tested).

**Frames.** Poses are ``(x, y, yaw)`` of ``base_footprint`` in the map's
frame. The LiDAR is mounted at :attr:`LidarSpec.mount` in
``base_footprint``; a scan is cast from there.
"""

from dataclasses import dataclass, field
import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

from .maps import FREE, LabMap, MapError

TWO_PI = 2.0 * math.pi
INF = float('inf')


def wrap(a: float) -> float:
    """Return ``a`` wrapped into ``[-pi, pi)``."""
    return (a + math.pi) % TWO_PI - math.pi


@dataclass(frozen=True)
class LidarSpec:
    """A planar LiDAR: beam angles, range limits and its mount pose."""

    samples: int
    angle_min: float
    angle_max: float
    range_min: float
    range_max: float
    #: ``(x, y, yaw)`` of the sensor in ``base_footprint``
    mount: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def angles(self) -> List[float]:
        """Return every beam's angle in the sensor frame, first to last."""
        if self.samples == 1:
            return [self.angle_min]
        step = (self.angle_max - self.angle_min) / (self.samples - 1)
        return [self.angle_min + i * step for i in range(self.samples)]

    def decimated(self, every: int) -> 'LidarSpec':
        """Return the spec with every ``every``-th beam (first beam kept)."""
        if every < 1:
            raise ValueError(f'every must be >= 1, got {every!r}')
        n = (self.samples - 1) // every + 1
        step = (self.angle_max - self.angle_min) / (self.samples - 1) \
            if self.samples > 1 else 0.0
        return LidarSpec(n, self.angle_min,
                         self.angle_min + (n - 1) * every * step,
                         self.range_min, self.range_max, self.mount)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return {'samples': self.samples, 'angle_min': self.angle_min,
                'angle_max': self.angle_max, 'range_min': self.range_min,
                'range_max': self.range_max, 'mount': list(self.mount)}

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> 'LidarSpec':
        """Inverse of :meth:`to_dict`."""
        return cls(int(d['samples']), float(d['angle_min']),
                   float(d['angle_max']), float(d['range_min']),
                   float(d['range_max']),
                   tuple(float(v) for v in d['mount']))


#: COCO's LiDAR as Gazebo simulates it: ``gazebo_models/urdf/
#: coco_robo2.xacro`` (sensor ``lidar``: 480 samples over +-2.0944 rad,
#: 0.15-12.0 m, no noise element) mounted by ``lidar_joint`` at
#: (-0.09, 0.10) in ``base_link``, which ``base_footprint_joint`` offsets
#: only in z. coco_lab may not import coco_config or read the xacro (no
#: ROS, no package data), so the values are copied here and
#: ``coco_lab_ros/test/test_sketch_constants.py`` pins them to the source.
COCO_LIDAR = LidarSpec(samples=480, angle_min=-2.0944, angle_max=2.0944,
                       range_min=0.15, range_max=12.0,
                       mount=(-0.09, 0.10, 0.0))

#: Sketch's collision circle: half the diagonal of COCO's 0.297 x 0.314 m
#: footprint (Lab 1.1, derived from coco_config), rounded up to 0.22 m.
ROBOT_RADIUS = 0.22

#: AMCL's update thresholds from ``gazebo_models/config/nav2_params.yaml``
#: (``update_min_d``, ``update_min_a``): a filter update happens when
#: odometry has moved this far since the last one.
UPDATE_MIN_D = 0.25
UPDATE_MIN_A = 0.2


def edt(blocked: Sequence[int], width: int, height: int) -> List[float]:
    """
    Exact Euclidean distance transform, in cells, row-major.

    Each value is the distance from the cell's centre to the centre of the
    nearest blocked cell (0 for a blocked cell; ``inf`` if there is none).
    Felzenszwalb and Huttenlocher's linear-time lower-envelope algorithm,
    once along rows and once along columns.
    """
    big = 1e20
    f = [0.0 if b else big for b in blocked]

    def dt1(vals: List[float]) -> List[float]:
        n = len(vals)
        v = [0] * n
        z = [0.0] * (n + 1)
        k = 0
        z[0] = -INF
        z[1] = INF
        for q in range(1, n):
            fq = vals[q] + q * q
            while True:
                p = v[k]
                s = (fq - (vals[p] + p * p)) / (2 * (q - p))
                if s > z[k]:
                    break
                k -= 1  # z[0] is -inf, so k never goes below 0
            k += 1
            v[k] = q
            z[k] = s
            z[k + 1] = INF
        out = [0.0] * n
        k = 0
        for q in range(n):
            while z[k + 1] < q:
                k += 1
            p = v[k]
            out[q] = (q - p) * (q - p) + vals[p]
        return out

    # rows
    for r in range(height):
        row = f[r * width:(r + 1) * width]
        f[r * width:(r + 1) * width] = dt1(row)
    # columns
    for c in range(width):
        col = f[c::width]
        f[c::width] = dt1(col)
    return [math.sqrt(v) if v < big / 2 else INF for v in f]


class SketchMap:
    """
    A LabMap prepared for ray casting and distance queries.

    ``blocked`` is indexed *up-major*: ``iy * width + ix`` with ``iy``
    counting cells up from the map's bottom edge, so that grid coordinates
    and frame coordinates grow the same way.
    """

    def __init__(self, lab_map: LabMap):
        """Precompute the blocked mask and the distance transform."""
        if not lab_map.has_geo:
            raise MapError(f'Sketch needs a placed map; {lab_map.id!r} has '
                           f'no resolution/origin')
        self.lab_map = lab_map
        self.width = w = lab_map.width
        self.height = h = lab_map.height
        self.resolution = lab_map.resolution
        self.origin = lab_map.origin
        occ = lab_map.occupancy
        blocked = bytearray(w * h)
        for iy in range(h):
            row = h - 1 - iy
            for ix in range(w):
                if occ[row * w + ix] != FREE:
                    blocked[iy * w + ix] = 1
        self.blocked = bytes(blocked)
        #: metres from each cell centre to the nearest blocked cell centre
        self.dist = [d * self.resolution for d in edt(self.blocked, w, h)]
        self._free = None

    def grid(self, x: float, y: float) -> Tuple[int, int]:
        """Return ``(ix, iy)`` of the cell containing ``(x, y)``."""
        r = self.resolution
        return (math.floor((x - self.origin[0]) / r),
                math.floor((y - self.origin[1]) / r))

    def is_blocked(self, x: float, y: float) -> bool:
        """Return whether ``(x, y)`` is in a blocked cell or off the map."""
        ix, iy = self.grid(x, y)
        if not (0 <= ix < self.width and 0 <= iy < self.height):
            return True
        return bool(self.blocked[iy * self.width + ix])

    def clearance(self, x: float, y: float) -> float:
        """Return the distance to the nearest blocked cell (0 off the map)."""
        ix, iy = self.grid(x, y)
        if not (0 <= ix < self.width and 0 <= iy < self.height):
            return 0.0
        return self.dist[iy * self.width + ix]

    def free_cells(self, margin: float = 0.0) -> List[Tuple[int, int]]:
        """Return ``(ix, iy)`` of every free cell with ``clearance > margin``."""
        out = []
        w = self.width
        for iy in range(self.height):
            for ix in range(w):
                i = iy * w + ix
                if not self.blocked[i] and self.dist[i] > margin:
                    out.append((ix, iy))
        return out

    def cell_centre(self, ix: int, iy: int) -> Tuple[float, float]:
        """Return the frame coordinates of the centre of ``(ix, iy)``."""
        r = self.resolution
        return (self.origin[0] + (ix + 0.5) * r,
                self.origin[1] + (iy + 0.5) * r)

    def cast(self, x: float, y: float, angle: float,
             max_range: float) -> float:
        """
        Return the range to the first blocked cell along the ray, or ``inf``.

        Amanatides and Woo's grid traversal: the distance is to where the
        ray *enters* the first blocked cell. ``inf`` means no blocked cell
        within ``max_range``. A ray that starts in a blocked cell returns 0.
        """
        r = self.resolution
        w = self.width
        h = self.height
        blocked = self.blocked
        fx = (x - self.origin[0]) / r
        fy = (y - self.origin[1]) / r
        ix = math.floor(fx)
        iy = math.floor(fy)
        if not (0 <= ix < w and 0 <= iy < h) or blocked[iy * w + ix]:
            return 0.0
        dx = math.cos(angle)
        dy = math.sin(angle)
        # a component this small is axis-parallel: 1/dy of a subnormal
        # overflows to inf, and 0 * inf at a cell boundary is NaN (found
        # by test_a_ray_stops_at_the_inner_wall_face, heading -3.4e-309)
        if abs(dx) < 1e-12:
            dx = 0.0
        if abs(dy) < 1e-12:
            dy = 0.0
        if dx > 0:
            sx = 1
            tdx = 1.0 / dx
            tx = (ix + 1 - fx) * tdx
        elif dx < 0:
            sx = -1
            tdx = -1.0 / dx
            tx = (fx - ix) * tdx
        else:
            sx = 0
            tdx = INF
            tx = INF
        if dy > 0:
            sy = 1
            tdy = 1.0 / dy
            ty = (iy + 1 - fy) * tdy
        elif dy < 0:
            sy = -1
            tdy = -1.0 / dy
            ty = (fy - iy) * tdy
        else:
            sy = 0
            tdy = INF
            ty = INF
        tmax = max_range / r
        while True:
            if tx < ty:
                t = tx
                tx += tdx
                ix += sx
            else:
                t = ty
                ty += tdy
                iy += sy
            if t > tmax:
                return INF
            if not (0 <= ix < w and 0 <= iy < h) or blocked[iy * w + ix]:
                return t * r

    def scan(self, pose: Tuple[float, float, float], lidar: LidarSpec,
             angles: Optional[Sequence[float]] = None) -> List[float]:
        """
        Return noise-free ranges from ``pose`` (``base_footprint``).

        A beam with no hit within ``range_max`` returns ``inf``, which is
        what Gazebo's bridged ``LaserScan`` carries for no return. A hit
        nearer than ``range_min`` is returned as found; :func:`observe`
        applies the sensor's limits.
        """
        x, y, th = pose
        mx, my, myaw = lidar.mount
        c, s = math.cos(th), math.sin(th)
        sx = x + c * mx - s * my
        sy = y + s * mx + c * my
        base = th + myaw
        if angles is None:
            angles = lidar.angles()
        return [self.cast(sx, sy, base + a, lidar.range_max) for a in angles]


def observe(true_ranges: Sequence[float], lidar: LidarSpec, sigma: float,
            rng: random.Random) -> List[float]:
    """
    Return measured ranges: Gaussian noise, then the sensor's limits.

    A noisy range below ``range_min`` or a beam with no return becomes
    ``inf`` (no reading); above ``range_max`` also becomes ``inf``. One
    ``rng.gauss`` is drawn per beam *whether or not it returned*, so a
    change in one beam never shifts the noise on the others.
    """
    out = []
    for z in true_ranges:
        n = rng.gauss(0.0, sigma) if sigma > 0 else 0.0
        if z == INF:
            out.append(INF)
            continue
        m = z + n
        out.append(m if lidar.range_min <= m <= lidar.range_max else INF)
    return out


# -- motion -----------------------------------------------------------------

def step_pose(pose: Tuple[float, float, float], v: float, w: float,
              dt: float) -> Tuple[float, float, float]:
    """Integrate a unicycle exactly for ``dt`` at constant ``(v, w)``."""
    x, y, th = pose
    if abs(w) < 1e-12:
        return (x + v * dt * math.cos(th), y + v * dt * math.sin(th), th)
    th2 = th + w * dt
    r = v / w
    return (x + r * (math.sin(th2) - math.sin(th)),
            y - r * (math.cos(th2) - math.cos(th)), wrap(th2))


def odom_delta(a: Tuple[float, float, float],
               b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Return ``(rot1, trans, rot2)`` taking pose ``a`` to pose ``b``.

    The odometry motion model's decomposition (*Probabilistic Robotics*
    5.4). A move shorter than 1 mm has ``rot1 = 0`` so a pure rotation is
    one rotation, not two arbitrary ones.
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    trans = math.hypot(dx, dy)
    rot1 = wrap(math.atan2(dy, dx) - a[2]) if trans > 1e-3 else 0.0
    rot2 = wrap(b[2] - a[2] - rot1)
    return rot1, trans, rot2


def apply_delta(p: Tuple[float, float, float], rot1: float, trans: float,
                rot2: float) -> Tuple[float, float, float]:
    """Return ``p`` moved by ``(rot1, trans, rot2)``."""
    th = p[2] + rot1
    return (p[0] + trans * math.cos(th), p[1] + trans * math.sin(th),
            wrap(th + rot2))


def sample_delta(rot1: float, trans: float, rot2: float,
                 alphas: Sequence[float],
                 rng: random.Random) -> Tuple[float, float, float]:
    """
    Return a noisy ``(rot1, trans, rot2)``: table 5.6's sample_motion_model.

    Exactly three ``rng.gauss`` draws per call, always, so the stream
    stays aligned whatever the alphas are. (Uses the smaller of a rotation
    and its supplement, as AMCL's DifferentialMotionModel does, so driving
    backwards is not treated as two half-turns.)
    """
    a1, a2, a3, a4 = alphas
    r1n = min(abs(rot1), abs(math.pi - abs(rot1)))
    r2n = min(abs(rot2), abs(math.pi - abs(rot2)))
    s1 = math.sqrt(a1 * r1n * r1n + a2 * trans * trans)
    st = math.sqrt(a3 * trans * trans + a4 * (r1n * r1n + r2n * r2n))
    s2 = math.sqrt(a1 * r2n * r2n + a2 * trans * trans)
    n1 = rng.gauss(0.0, 1.0)
    nt = rng.gauss(0.0, 1.0)
    n2 = rng.gauss(0.0, 1.0)
    return rot1 - n1 * s1, trans - nt * st, rot2 - n2 * s2


# -- scenario ---------------------------------------------------------------

@dataclass
class Noise:
    """
    The world's noise: what the Sketch robot's sensors actually suffer.

    ``odom_alphas`` are the motion model's ``(a1, a2, a3, a4)``, the same
    four numbers as AMCL's ``alpha1..alpha4``; ``range_sigma`` is the
    LiDAR's Gaussian range noise in metres.
    """

    odom_alphas: Tuple[float, float, float, float] = (0.02, 0.02, 0.02, 0.02)
    range_sigma: float = 0.02

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return {'odom_alphas': list(self.odom_alphas),
                'range_sigma': self.range_sigma}

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> 'Noise':
        """Inverse of :meth:`to_dict`."""
        a = tuple(float(v) for v in d['odom_alphas'])
        if len(a) != 4 or any(v < 0 for v in a):
            raise ValueError(f'odom_alphas must be four values >= 0: {a}')
        s = float(d['range_sigma'])
        if not (s >= 0 and math.isfinite(s)):
            raise ValueError(f'range_sigma must be finite and >= 0: {s}')
        return cls(a, s)


@dataclass
class Kidnap:
    """At sim time ``t``, the robot is carried to ``to``; odometry is not told."""

    t: float
    to: Tuple[float, float, float]

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return {'t': self.t, 'to': list(self.to)}

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> 'Kidnap':
        """Inverse of :meth:`to_dict`."""
        to = tuple(float(v) for v in d['to'])
        if len(to) != 3:
            raise ValueError(f'kidnap "to" must be (x, y, yaw): {to}')
        return cls(float(d['t']), to)


@dataclass
class Scenario:
    """
    Everything a Sketch run depends on. Same scenario, same run.

    ``route`` is a list of map-frame ``(x, y)`` waypoints the robot is
    driven through, in order, from ``start``. The driver steers by the
    *true* pose -- it plays a teleoperator who can see the robot -- so the
    commands are an input to localisation, never an output of it. After a
    kidnap it carries on to the next waypoint from wherever the robot was
    put, along a path ``coco_lab``'s own A* finds on the map inflated by
    the robot's radius.
    """

    start: Tuple[float, float, float]
    route: List[Tuple[float, float]]
    seed: int = 0
    noise: Noise = field(default_factory=Noise)
    kidnap: Optional[Kidnap] = None
    dt: float = 0.1
    v_max: float = 0.3
    w_max: float = 1.0
    #: the LiDAR the run simulates: COCO's, decimated to 60 beams
    lidar: LidarSpec = field(default_factory=lambda: COCO_LIDAR.decimated(8))
    max_time: float = 600.0

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return {
            'start': list(self.start), 'route': [list(p) for p in self.route],
            'seed': self.seed, 'noise': self.noise.to_dict(),
            'kidnap': None if self.kidnap is None else self.kidnap.to_dict(),
            'dt': self.dt, 'v_max': self.v_max, 'w_max': self.w_max,
            'lidar': self.lidar.to_dict(), 'max_time': self.max_time,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> 'Scenario':
        """Inverse of :meth:`to_dict`, validating as it goes."""
        start = tuple(float(v) for v in d['start'])
        if len(start) != 3:
            raise ValueError(f'start must be (x, y, yaw): {start}')
        route = [tuple(float(v) for v in p) for p in d['route']]
        if not route or any(len(p) != 2 for p in route):
            raise ValueError('route must be a non-empty list of (x, y)')
        if len(route) > 64:
            raise ValueError(f'a route has at most 64 waypoints, not '
                             f'{len(route)}')
        kid = d.get('kidnap')
        sc = cls(start, route, int(d.get('seed', 0)),
                 Noise.from_dict(d['noise']) if 'noise' in d else Noise(),
                 None if kid is None else Kidnap.from_dict(kid),
                 float(d.get('dt', 0.1)), float(d.get('v_max', 0.3)),
                 float(d.get('w_max', 1.0)),
                 LidarSpec.from_dict(d['lidar']) if 'lidar' in d
                 else COCO_LIDAR.decimated(8),
                 float(d.get('max_time', 600.0)))
        if not (0 < sc.dt <= 1.0 and 0 < sc.v_max <= 2.0
                and 0 < sc.w_max <= 4.0 and 0 < sc.max_time <= 3600):
            raise ValueError('dt, v_max, w_max or max_time out of range')
        return sc


@dataclass
class WorldRun:
    """
    One Sketch run: the truth, the odometry and the scans the filters get.

    Rows ``t, gt, odom, cmd`` are every ``dt``. ``updates`` are the row
    indices where odometry had moved ``UPDATE_MIN_D`` / ``UPDATE_MIN_A``
    since the previous update (row 0 is always one), and ``ranges[k]`` is
    the measured scan at ``updates[k]``. A filter sees ``odom`` and
    ``ranges`` at the updates, and nothing else.
    """

    scenario: Scenario
    t: List[float]
    gt: List[Tuple[float, float, float]]
    odom: List[Tuple[float, float, float]]
    cmd: List[Tuple[float, float]]
    updates: List[int]
    ranges: List[List[float]]
    kidnap_row: Optional[int]
    status: str  # 'route_done' | 'timeout' | 'stuck'


def _inflated_grid_map(smap: SketchMap, radius: float) -> LabMap:
    """Return the map with every cell nearer than ``radius`` to a wall blocked."""
    from .maps import OCCUPIED
    w, h = smap.width, smap.height
    occ = bytearray(w * h)
    for iy in range(h):
        row = h - 1 - iy
        for ix in range(w):
            i = iy * w + ix
            if smap.blocked[i] or smap.dist[i] < radius:
                occ[row * w + ix] = OCCUPIED
    m = smap.lab_map
    return LabMap(w, h, bytes(occ), map_id=f'{m.id}+inflated',
                  resolution=m.resolution, origin=m.origin, frame=m.frame)


def plan_path(smap: SketchMap, a: Tuple[float, float],
              b: Tuple[float, float],
              radius: float = ROBOT_RADIUS) -> List[Tuple[float, float]]:
    """
    Return waypoints from ``a`` to ``b`` found by coco_lab's A*.

    On the map inflated by ``radius`` (8-connected, no corner cutting),
    then thinned to the cells where the direction changes. Raises
    ``ValueError`` if there is no path.
    """
    from .search import search
    key = (id(smap), radius)
    cache = _INFLATED.get(key)
    if cache is None or cache[0] is not smap:
        cache = (smap, _inflated_grid_map(smap, radius))
        _INFLATED.clear()
        _INFLATED[key] = cache
    m = cache[1]
    g = m.to_grid(connectivity=8)
    s = m.cell_at(*a)
    t = m.cell_at(*b)
    if s is None or t is None:
        raise ValueError(f'{a} or {b} is off the map')
    snear = _nearest_free(g, s)
    tnear = _nearest_free(g, t)
    if snear is None or tnear is None:
        raise ValueError(f'no free cell near {a} or {b}')
    res = search(g, snear, tnear, 'astar', 'octile')
    if res.path is None:
        raise ValueError(f'no path from {a} to {b} on the inflated map')
    cells = [(c[0], c[1]) for c in res.path]
    pts = []
    for i, c in enumerate(cells):
        if 0 < i < len(cells) - 1:
            p, n = cells[i - 1], cells[i + 1]
            if (c[0] - p[0], c[1] - p[1]) == (n[0] - c[0], n[1] - c[1]):
                continue
        pts.append(m.cell_centre(*c))
    pts[-1] = b
    return pts[1:] if len(pts) > 1 else pts


_INFLATED: Dict[tuple, tuple] = {}


def _nearest_free(g, cell):
    """Return the nearest valid grid state to ``cell`` (BFS, bounded)."""
    from collections import deque
    if g.is_valid(cell):
        return cell
    seen = {cell}
    q = deque([cell])
    while q and len(seen) < 4000:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (r + dr, c + dc)
            if n not in seen:
                seen.add(n)
                if g.is_valid(n):
                    return n
                q.append(n)
    return None


#: The driver reaches a waypoint when it is this close (metres).
WAYPOINT_TOL = 0.12


def drive_command(pose: Tuple[float, float, float],
                  target: Tuple[float, float], v_max: float, w_max: float,
                  dt: float) -> Optional[Tuple[float, float]]:
    """
    Return ``(v, w)`` toward ``target``, or ``None`` once it is reached.

    Turn toward the target at gain 2 (clipped to ``w_max``); drive at
    ``v_max cos(error)`` only once the heading error is under 0.6 rad,
    never overshooting in one ``dt``. The SAME function drives the Gazebo
    robot in ``docs/data/lab2/lab2_probe.py``, so a Sketch drive and a
    Gazebo drive follow one control law.
    """
    dx, dy = target[0] - pose[0], target[1] - pose[1]
    dist = math.hypot(dx, dy)
    if dist < WAYPOINT_TOL:
        return None
    err = wrap(math.atan2(dy, dx) - pose[2])
    w = max(-w_max, min(w_max, 2.0 * err))
    v = v_max * max(0.0, math.cos(err)) if abs(err) < 0.6 else 0.0
    return (min(v, dist / dt), w)


def simulate(smap: SketchMap, sc: Scenario) -> WorldRun:
    """
    Drive ``sc`` on ``smap``; return the truth, odometry and scans.

    Two independent random streams, both from ``sc.seed``: one for
    odometry noise, one for range noise. Changing a filter never changes
    the world, and the world never reads the filter.
    """
    master = random.Random(sc.seed)
    rng_odom = random.Random(master.getrandbits(64))
    rng_range = random.Random(master.getrandbits(64))
    angles = sc.lidar.angles()

    pose = sc.start
    if smap.clearance(pose[0], pose[1]) < ROBOT_RADIUS * 0.5:
        raise ValueError(f'start {pose} is inside or against a wall')
    odom = (0.0, 0.0, 0.0)  # odometry starts at its own origin
    # odometry's frame differs from the map's by the start pose; the
    # filters are given the start (tracking) or not (global) separately.
    t = 0.0
    T, GT, OD, CMD = [0.0], [pose], [odom], [(0.0, 0.0)]
    updates = [0]
    ranges = [observe(smap.scan(pose, sc.lidar, angles), sc.lidar,
                      sc.noise.range_sigma, rng_range)]
    last_upd_odom = odom
    queue: List[Tuple[float, float]] = []
    route = list(sc.route)
    kidnap_row = None
    kidnapped = sc.kidnap is None
    status = 'timeout'
    stuck_for = 0
    n_steps = int(round(sc.max_time / sc.dt))
    for _ in range(n_steps):
        # -- the kidnap: truth jumps, odometry does not
        if not kidnapped and t + 1e-9 >= sc.kidnap.t:
            pose = sc.kidnap.to
            if smap.clearance(pose[0], pose[1]) < ROBOT_RADIUS * 0.5:
                raise ValueError(f'kidnap target {pose} is inside a wall')
            kidnapped = True
            kidnap_row = len(T)
            queue = []
        # -- the driver: next waypoint, by the true pose
        while not queue and route:
            goal = route[0]
            try:
                queue = plan_path(smap, (pose[0], pose[1]), goal)
            except ValueError:
                route.pop(0)  # unreachable waypoint: skip it, say so below
                status = 'stuck'
                continue
        if not queue:
            status = 'route_done' if status != 'stuck' else status
            break
        tx, ty = queue[0]
        cmd = drive_command(pose, (tx, ty), sc.v_max, sc.w_max, sc.dt)
        if cmd is None:
            queue.pop(0)
            if not queue and route:
                route.pop(0)
            cmd = (0.0, 0.0)
        v, w = cmd
        new = step_pose(pose, v, w, sc.dt)
        if smap.clearance(new[0], new[1]) < ROBOT_RADIUS * 0.5:
            new = pose  # blocked: it does not move this step
            stuck_for += 1
            if stuck_for > int(5.0 / sc.dt):
                status = 'stuck'
                break
        else:
            stuck_for = 0
        rot1, trans, rot2 = odom_delta(pose, new)
        n1, nt, n2 = sample_delta(rot1, trans, rot2, sc.noise.odom_alphas,
                                  rng_odom)
        odom = apply_delta(odom, n1, nt, n2)
        pose = new
        t = round(t + sc.dt, 9)
        T.append(t)
        GT.append(pose)
        OD.append(odom)
        CMD.append((v, w))
        r1, tr, r2 = odom_delta(last_upd_odom, odom)
        if tr >= UPDATE_MIN_D or abs(wrap(odom[2] - last_upd_odom[2])) \
                >= UPDATE_MIN_A:
            updates.append(len(T) - 1)
            ranges.append(observe(smap.scan(pose, sc.lidar, angles),
                                  sc.lidar, sc.noise.range_sigma, rng_range))
            last_upd_odom = odom
    return WorldRun(sc, T, GT, OD, CMD, updates, ranges, kidnap_row, status)
