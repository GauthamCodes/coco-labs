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
The algorithm API, ``coco.algorithm.v1`` (R2; ADR 0013): what your code sees.

Write one of three functions in a module of its own::

    def plan(costmap: Costmap, start: Pose2D, goal: Pose2D, ctx: Context) -> list[Pose2D] | None
    def control(state: RobotState, scan: LaserScan, path: list[Pose2D], ctx: Context) -> Twist
    def localise(odom: Odometry, scan: LaserScan, map: OccupancyGrid,
                 ctx: Context) -> PoseWithCovariance

The types have the fields and nesting of the ROS 2 messages COCO's stack carries
(``nav2_msgs/Costmap`` -- Nav2's ``/global_costmap/costmap_raw``, raw costs 0..255 --
``nav_msgs/OccupancyGrid``, ``sensor_msgs/LaserScan``, ``nav_msgs/Odometry``,
``geometry_msgs/Twist``, ``Pose2D`` and ``PoseWithCovariance``), so the same file runs
in the browser, natively (``coco experiment run --algorithm``) and as a ROS 2 node
(the generated ``coco_user_<name>`` package converts the real messages into these).

``ctx`` (:class:`Context`) gives the seeded random numbers (``ctx.rng``; the only
randomness allowed), the robot (``ctx.robot``: COCO's footprint radius and limits),
the step budget (``ctx.step()``), sim time (``ctx.time``), your parameters
(``ctx.params``), memory kept across the calls of one run (``ctx.memory``) and
``ctx.emit(kind, **data)``, which draws your algorithm's thinking with the same
glass-box layers the built-ins use (event kinds: :data:`EVENT_KINDS`).

Everything here is plain Python (no ROS import, README invariant 1) and evidence
class MODEL in the browser.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from .numerics import math

__all__ = [
    'API_VERSION', 'SCHEMA', 'EVENT_KINDS', 'Time', 'Header', 'Point', 'Vector3', 'Quaternion',
    'Pose', 'Pose2D', 'Twist', 'PoseWithCovariance', 'TwistWithCovariance', 'MapMetaData',
    'OccupancyGrid', 'CostmapMetaData', 'Costmap', 'LaserScan', 'Odometry', 'RobotState',
    'Robot', 'Context', 'Random', 'BudgetExceeded', 'NoValidControl', 'InvalidPath',
    'yaw_of', 'quaternion_from_yaw', 'FREE_SPACE', 'INSCRIBED_INFLATED_OBSTACLE',
    'LETHAL_OBSTACLE', 'NO_INFORMATION', 'GRID_FREE', 'GRID_OCCUPIED', 'GRID_UNKNOWN']

API_VERSION = 1
SCHEMA = 'coco.algorithm.v1'

#: nav2_costmap_2d's cost values (``cost_values.hpp``)
FREE_SPACE = 0
INSCRIBED_INFLATED_OBSTACLE = 253
LETHAL_OBSTACLE = 254
NO_INFORMATION = 255
#: nav_msgs/OccupancyGrid's values (map_server's trinary mode)
GRID_FREE, GRID_OCCUPIED, GRID_UNKNOWN = 0, 100, -1

#: ``ctx.emit`` kinds and their fields (docs/v2/r2/API.md, "Thinking"). Positions are
#: map-frame metres. Each is drawn by the layer the built-ins of that family use.
EVENT_KINDS = {
    # planners: Compare's search layer (expanded cells, the frontier, the path)
    'expand': ('x', 'y'),
    'push': ('x', 'y'),
    'frontier': ('x', 'y'),
    'path': ('points',),
    # controllers: the Move lens's candidate trajectories and the chosen command
    'candidate': ('points', 'cost', 'valid'),
    'lookahead': ('x', 'y'),
    # localisers: the Localise lens's particle cloud and the estimate
    'particles': ('x', 'y', 'theta', 'weight'),
    'estimate': ('x', 'y', 'theta'),
    # any family: a labelled point and a line of text in the console
    'marker': ('x', 'y', 'label'),
    'note': ('text',),
}


class BudgetExceeded(RuntimeError):
    """Raised by :meth:`Context.step` when the call's step budget is used up."""


class NoValidControl(RuntimeError):
    """Raise from ``control()`` when no safe command exists (Nav2's NoValidControl)."""


class InvalidPath(RuntimeError):
    """Raise from ``control()`` when the path cannot be followed (Nav2's InvalidPath)."""


def _f(v, name: str) -> float:
    v = float(v)
    if not math.isfinite(v):
        raise ValueError(f'{name} must be finite, got {v!r}')
    return v


class _Msg:
    """A message: fields set by keyword, compared and printed field by field."""

    __slots__ = ()

    def _fields(self):
        return [k for k in type(self).__slots__ if not k.startswith('_')]

    def __eq__(self, other):
        """Return whether ``other`` is the same type with equal fields."""
        return type(other) is type(self) and all(
            getattr(self, k) == getattr(other, k) for k in self._fields())

    def __repr__(self):
        """Return ``Type(field=value, ...)``."""
        body = ', '.join(f'{k}={getattr(self, k)!r}' for k in self._fields())
        return f'{type(self).__name__}({body})'


class Time(_Msg):
    """builtin_interfaces/Time."""

    __slots__ = ('sec', 'nanosec')

    def __init__(self, sec: int = 0, nanosec: int = 0):
        """Seconds and nanoseconds."""
        self.sec, self.nanosec = int(sec), int(nanosec)

    @classmethod
    def from_sec(cls, t: float) -> 'Time':
        """Return the Time ``t`` seconds after zero."""
        sec = math.floor(t)
        ns = int(round((t - sec) * 1e9))
        if ns >= 1_000_000_000:
            sec, ns = sec + 1, ns - 1_000_000_000
        return cls(int(sec), ns)

    def to_sec(self) -> float:
        """Return the time in seconds."""
        return self.sec + self.nanosec * 1e-9


class Header(_Msg):
    """std_msgs/Header."""

    __slots__ = ('stamp', 'frame_id')

    def __init__(self, stamp: Optional[Time] = None, frame_id: str = ''):
        """Hold a stamp and a frame."""
        self.stamp = stamp if stamp is not None else Time()
        self.frame_id = frame_id


class Point(_Msg):
    """geometry_msgs/Point."""

    __slots__ = ('x', 'y', 'z')

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """Three coordinates (m)."""
        self.x, self.y, self.z = float(x), float(y), float(z)


class Vector3(Point):
    """geometry_msgs/Vector3."""

    __slots__ = ()


class Quaternion(_Msg):
    """geometry_msgs/Quaternion."""

    __slots__ = ('x', 'y', 'z', 'w', '_yaw')

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, w: float = 1.0):
        """Four components; the default is the identity."""
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)
        self._yaw = None


def quaternion_from_yaw(yaw: float) -> Quaternion:
    """Return the Quaternion of a rotation by ``yaw`` about z (REP-103)."""
    q = Quaternion(0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))
    q._yaw = (float(yaw), q.z, q.w)
    return q


def yaw_of(q: Quaternion) -> float:
    """
    Return the yaw (rad) of a Quaternion.

    A quaternion made by :func:`quaternion_from_yaw` (and not changed since) gives
    back exactly the yaw it was made from: no bits lost in the round trip.
    """
    made = getattr(q, '_yaw', None)
    if made is not None and q.x == 0.0 and q.y == 0.0 and made[1] == q.z and made[2] == q.w:
        return made[0]
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class Pose(_Msg):
    """geometry_msgs/Pose."""

    __slots__ = ('position', 'orientation')

    def __init__(self, position: Optional[Point] = None,
                 orientation: Optional[Quaternion] = None):
        """Hold a position and an orientation."""
        self.position = position if position is not None else Point()
        self.orientation = orientation if orientation is not None else Quaternion()

    @classmethod
    def from_2d(cls, x: float, y: float, theta: float = 0.0) -> 'Pose':
        """Return the Pose of a planar pose."""
        return cls(Point(x, y), quaternion_from_yaw(theta))

    def to_2d(self) -> 'Pose2D':
        """Return the planar pose (x, y, yaw)."""
        return Pose2D(self.position.x, self.position.y, yaw_of(self.orientation))


class Pose2D(_Msg):
    """geometry_msgs/Pose2D: a planar pose in the map frame (m, m, rad)."""

    __slots__ = ('x', 'y', 'theta')

    def __init__(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0):
        """Hold a position and a heading."""
        self.x, self.y, self.theta = float(x), float(y), float(theta)


class Twist(_Msg):
    """geometry_msgs/Twist: COCO drives ``linear.x`` (m/s) and ``angular.z`` (rad/s)."""

    __slots__ = ('linear', 'angular')

    def __init__(self, linear: Optional[Vector3] = None, angular: Optional[Vector3] = None):
        """Linear and angular velocity."""
        self.linear = linear if linear is not None else Vector3()
        self.angular = angular if angular is not None else Vector3()

    @classmethod
    def of(cls, v: float, w: float) -> 'Twist':
        """Return the Twist driving forward at ``v`` and turning at ``w``."""
        return cls(Vector3(v, 0.0, 0.0), Vector3(0.0, 0.0, w))


class PoseWithCovariance(_Msg):
    """geometry_msgs/PoseWithCovariance: a pose and its 6x6 row-major covariance."""

    __slots__ = ('pose', 'covariance')

    def __init__(self, pose: Optional[Pose] = None, covariance: Optional[Sequence[float]] = None):
        """Hold a pose and 36 covariance values (x, y, z, roll, pitch, yaw)."""
        self.pose = pose if pose is not None else Pose()
        self.covariance = list(covariance) if covariance is not None else [0.0] * 36

    @classmethod
    def of(cls, x: float, y: float, theta: float, var_x: float = 0.0, var_y: float = 0.0,
           var_theta: float = 0.0, cov_xy: float = 0.0) -> 'PoseWithCovariance':
        """Return a planar estimate with its x, y and yaw variances."""
        c = [0.0] * 36
        c[0], c[7], c[35] = var_x, var_y, var_theta
        c[1] = c[6] = cov_xy
        return cls(Pose.from_2d(x, y, theta), c)


class TwistWithCovariance(_Msg):
    """geometry_msgs/TwistWithCovariance."""

    __slots__ = ('twist', 'covariance')

    def __init__(self, twist: Optional[Twist] = None,
                 covariance: Optional[Sequence[float]] = None):
        """Hold a twist and 36 covariance values."""
        self.twist = twist if twist is not None else Twist()
        self.covariance = list(covariance) if covariance is not None else [0.0] * 36


class _Grid(_Msg):
    """The map helpers both grids share (cell (mx, my): column mx, row my, row 0 at origin)."""

    __slots__ = ()

    def _meta(self):
        raise NotImplementedError

    def world_to_map(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """Return the cell (mx, my) holding the point, or None off the map."""
        res, w, h, ox, oy = self._meta()
        mx, my = math.floor((x - ox) / res), math.floor((y - oy) / res)
        if 0 <= mx < w and 0 <= my < h:
            return (int(mx), int(my))
        return None

    def map_to_world(self, mx: int, my: int) -> Tuple[float, float]:
        """Return the centre (x, y) of cell (mx, my)."""
        res, _, _, ox, oy = self._meta()
        return (ox + (mx + 0.5) * res, oy + (my + 0.5) * res)

    def in_bounds(self, mx: int, my: int) -> bool:
        """Return whether (mx, my) is a cell of the map."""
        _, w, h, _, _ = self._meta()
        return 0 <= mx < w and 0 <= my < h

    def index(self, mx: int, my: int) -> int:
        """Return the index of cell (mx, my) in ``data`` (row-major from the origin)."""
        return my * self._meta()[1] + mx


class MapMetaData(_Msg):
    """nav_msgs/MapMetaData."""

    __slots__ = ('map_load_time', 'resolution', 'width', 'height', 'origin')

    def __init__(self, map_load_time: Optional[Time] = None, resolution: float = 0.05,
                 width: int = 0, height: int = 0, origin: Optional[Pose] = None):
        """Resolution (m/cell), size (cells) and the origin of cell (0, 0)'s corner."""
        self.map_load_time = map_load_time if map_load_time is not None else Time()
        self.resolution, self.width, self.height = float(resolution), int(width), int(height)
        self.origin = origin if origin is not None else Pose()


class OccupancyGrid(_Grid):
    """nav_msgs/OccupancyGrid: ``data`` is -1 (unknown), 0 (free) .. 100 (occupied)."""

    __slots__ = ('header', 'info', 'data')

    def __init__(self, header: Optional[Header] = None, info: Optional[MapMetaData] = None,
                 data: Optional[Sequence[int]] = None):
        """Hold a map: header, metadata and row-major cells."""
        self.header = header if header is not None else Header(frame_id='map')
        self.info = info if info is not None else MapMetaData()
        self.data = data if data is not None else []

    def _meta(self):
        i = self.info
        return (i.resolution, i.width, i.height, i.origin.position.x, i.origin.position.y)

    def value(self, mx: int, my: int) -> int:
        """Return the occupancy of cell (mx, my); off the map is unknown (-1)."""
        if not self.in_bounds(mx, my):
            return GRID_UNKNOWN
        return self.data[self.index(mx, my)]


class CostmapMetaData(_Msg):
    """nav2_msgs/CostmapMetaData."""

    __slots__ = ('map_load_time', 'update_time', 'layer', 'resolution', 'size_x', 'size_y',
                 'origin')

    def __init__(self, map_load_time: Optional[Time] = None,
                 update_time: Optional[Time] = None, layer: str = 'master',
                 resolution: float = 0.05, size_x: int = 0, size_y: int = 0,
                 origin: Optional[Pose] = None):
        """Resolution (m/cell), size (cells) and the origin of cell (0, 0)'s corner."""
        self.map_load_time = map_load_time if map_load_time is not None else Time()
        self.update_time = update_time if update_time is not None else Time()
        self.layer = layer
        self.resolution, self.size_x, self.size_y = float(resolution), int(size_x), int(size_y)
        self.origin = origin if origin is not None else Pose()


class Costmap(_Grid):
    """
    nav2_msgs/Costmap (Nav2's ``/global_costmap/costmap_raw``): raw costs 0..255.

    0 is free, 253 inscribed (the robot's centre there touches an obstacle), 254
    lethal, 255 unknown; 1..252 the inflation's falling cost. ``cost(mx, my)``
    reads one; off the map reads :data:`NO_INFORMATION`.
    """

    __slots__ = ('header', 'metadata', 'data')

    def __init__(self, header: Optional[Header] = None,
                 metadata: Optional[CostmapMetaData] = None,
                 data: Optional[Sequence[int]] = None):
        """Hold a costmap: header, metadata and row-major costs."""
        self.header = header if header is not None else Header(frame_id='map')
        self.metadata = metadata if metadata is not None else CostmapMetaData()
        self.data = data if data is not None else []

    def _meta(self):
        m = self.metadata
        return (m.resolution, m.size_x, m.size_y, m.origin.position.x, m.origin.position.y)

    @property
    def width(self) -> int:
        """Columns (``metadata.size_x``)."""
        return self.metadata.size_x

    @property
    def height(self) -> int:
        """Rows (``metadata.size_y``)."""
        return self.metadata.size_y

    @property
    def resolution(self) -> float:
        """Metres per cell."""
        return self.metadata.resolution

    def cost(self, mx: int, my: int) -> int:
        """Return the raw cost of cell (mx, my); off the map is NO_INFORMATION."""
        if not self.in_bounds(mx, my):
            return NO_INFORMATION
        return self.data[self.index(mx, my)]

    def cost_at(self, x: float, y: float) -> int:
        """Return the raw cost under the point (x, y) (m)."""
        c = self.world_to_map(x, y)
        return NO_INFORMATION if c is None else self.data[self.index(*c)]

    def is_free(self, mx: int, my: int) -> bool:
        """Return whether the robot's centre may be at cell (mx, my) (cost below 253)."""
        return self.cost(mx, my) < INSCRIBED_INFLATED_OBSTACLE


class LaserScan(_Msg):
    """sensor_msgs/LaserScan, in COCO's ``lidar_link`` frame (see ``ctx.robot.lidar_mount``)."""

    __slots__ = ('header', 'angle_min', 'angle_max', 'angle_increment', 'time_increment',
                 'scan_time', 'range_min', 'range_max', 'ranges', 'intensities')

    def __init__(self, header: Optional[Header] = None, angle_min: float = 0.0,
                 angle_max: float = 0.0, angle_increment: float = 0.0,
                 time_increment: float = 0.0, scan_time: float = 0.0, range_min: float = 0.0,
                 range_max: float = 0.0, ranges: Optional[Sequence[float]] = None,
                 intensities: Optional[Sequence[float]] = None):
        """Hold a scan: beam angles (rad), range limits (m), ranges (inf: no return)."""
        self.header = header if header is not None else Header(frame_id='lidar_link')
        self.angle_min, self.angle_max = float(angle_min), float(angle_max)
        self.angle_increment, self.time_increment = float(angle_increment), float(time_increment)
        self.scan_time, self.range_min, self.range_max = (float(scan_time), float(range_min),
                                                          float(range_max))
        self.ranges = ranges if ranges is not None else []
        self.intensities = intensities if intensities is not None else []

    def angles(self) -> List[float]:
        """Return every beam's angle in the scan frame, first to last."""
        return [self.angle_min + i * self.angle_increment for i in range(len(self.ranges))]


class Odometry(_Msg):
    """nav_msgs/Odometry: the wheel odometry, in the ``odom`` frame."""

    __slots__ = ('header', 'child_frame_id', 'pose', 'twist')

    def __init__(self, header: Optional[Header] = None, child_frame_id: str = 'base_footprint',
                 pose: Optional[PoseWithCovariance] = None,
                 twist: Optional[TwistWithCovariance] = None):
        """Hold a pose and a twist with their covariances."""
        self.header = header if header is not None else Header(frame_id='odom')
        self.child_frame_id = child_frame_id
        self.pose = pose if pose is not None else PoseWithCovariance()
        self.twist = twist if twist is not None else TwistWithCovariance()


class RobotState(_Msg):
    """
    What a local controller knows (Nav2's controller_server, from TF and /odom).

    ``pose``: where the robot believes it is (map frame); ``twist``: its current
    velocity; ``goal``: the path's goal (``theta`` is nan when the goal has no heading);
    ``stamp``: sim time.
    """

    __slots__ = ('pose', 'twist', 'goal', 'stamp')

    def __init__(self, pose: Optional[Pose2D] = None, twist: Optional[Twist] = None,
                 goal: Optional[Pose2D] = None, stamp: Optional[Time] = None):
        """Hold the believed pose, the velocity, the goal and the time."""
        self.pose = pose if pose is not None else Pose2D()
        self.twist = twist if twist is not None else Twist()
        self.goal = goal if goal is not None else Pose2D(math.nan, math.nan, math.nan)
        self.stamp = stamp if stamp is not None else Time()


class Robot(_Msg):
    """
    COCO's geometry and limits (World Spec ``robot``, from coco_config and Nav2's caps).

    ``radius`` (m) is the footprint circle; ``max_linear`` (m/s) and ``max_angular``
    (rad/s) the autonomy caps a Twist is clamped to; ``max_linear_accel`` (m/s^2) and
    ``max_angular_accel`` (rad/s^2); ``lidar_mount`` the LiDAR's (x, y) in the robot.
    """

    __slots__ = ('radius', 'max_linear', 'max_angular', 'max_linear_accel', 'max_angular_accel',
                 'wheel_radius', 'wheel_separation', 'lidar_mount')

    def __init__(self, radius: float = 0.22, max_linear: float = 0.3, max_angular: float = 1.0,
                 max_linear_accel: float = 2.0, max_angular_accel: float = 4.0,
                 wheel_radius: float = 0.0585, wheel_separation: float = 0.274,
                 lidar_mount: Tuple[float, float] = (-0.09, 0.1)):
        """Hold COCO's numbers (the defaults are its World Spec's)."""
        self.radius, self.max_linear, self.max_angular = radius, max_linear, max_angular
        self.max_linear_accel, self.max_angular_accel = max_linear_accel, max_angular_accel
        self.wheel_radius, self.wheel_separation = wheel_radius, wheel_separation
        self.lidar_mount = tuple(lidar_mount)

    @classmethod
    def from_spec(cls, rb: Dict) -> 'Robot':
        """Return the Robot of a World Spec's ``robot`` block."""
        lim = rb['limits']
        return cls(rb['radius'], lim['auto_linear'], lim['auto_angular'], lim['linear_accel'],
                   lim['angular_accel'], rb['wheel_radius'], rb['wheel_separation'],
                   (rb['lidar']['mount'][0], rb['lidar']['mount'][1]))


class Random:
    """
    ``ctx.rng``: the run's seeded generator (xoshiro256**, :mod:`coco_lab.rng`).

    The same seed gives the same numbers in the browser, natively and in ROS 2.
    """

    __slots__ = ('_rng',)

    def __init__(self, rng):
        """Wrap a :class:`coco_lab.rng.Rng`."""
        self._rng = rng

    def random(self) -> float:
        """Return a float in [0, 1)."""
        return self._rng.random()

    def uniform(self, a: float, b: float) -> float:
        """Return a float in [a, b)."""
        return self._rng.uniform(a, b)

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        """Return a normal deviate (Box-Muller; two draws)."""
        return self._rng.gauss(mu, sigma)

    def randrange(self, n: int) -> int:
        """Return an integer in [0, n)."""
        return self._rng.randrange(n)

    def randint(self, a: int, b: int) -> int:
        """Return an integer in [a, b]."""
        return a + self._rng.randrange(b - a + 1)

    def choice(self, seq):
        """Return one element of a non-empty sequence."""
        return seq[self._rng.randrange(len(seq))]

    def shuffle(self, items: list) -> None:
        """Shuffle a list in place (Fisher-Yates)."""
        for i in range(len(items) - 1, 0, -1):
            j = self._rng.randrange(i + 1)
            items[i], items[j] = items[j], items[i]

    def sample(self, seq, k: int) -> list:
        """Return ``k`` distinct elements of ``seq``, in draw order."""
        pool = list(seq)
        if not 0 <= k <= len(pool):
            raise ValueError('sample larger than population')
        out = []
        for _ in range(k):
            out.append(pool.pop(self._rng.randrange(len(pool))))
        return out


class Context:
    """
    ``ctx``: everything your algorithm may use besides its inputs.

    ``rng`` the seeded generator; ``robot`` COCO's :class:`Robot`; ``params`` your
    parameters (``user.<name>`` in an experiment, which can sweep them); ``config`` the
    family's own settings (the costmap's inflation, connectivity, ...); ``memory`` a dict kept
    across the calls
    of one run (a controller's or a localiser's state; a planner's is fresh per run);
    ``time`` sim time (s) and ``dt`` the tick (s); ``budget`` the steps one call may
    take (``step()``); ``initial_pose`` where a localiser starts (``/initialpose``);
    ``emit(kind, **data)`` your thinking (:data:`EVENT_KINDS`).
    """

    #: events kept per call for drawing (a planner's all go to the run's chain); more are
    #: counted and dropped (the report says so)
    MAX_EVENTS = 20000

    def __init__(self, rng, robot: Robot, params: Optional[Dict] = None, budget: int = 0,
                 dt: float = 0.1, sink=None, config: Optional[Dict] = None):
        """Built by the runner, never by your code."""
        self.rng = Random(rng)
        self.robot = robot
        self.params = dict(params or {})
        self.config = dict(config or {})
        self.memory: Dict = {}
        self.time = 0.0
        self.dt = dt
        self.budget = budget
        self.initial_pose: Optional[Pose2D] = None
        self.steps = 0
        self.events: List = []
        self.dropped = 0
        self._sink = sink
        self._costmap: Optional[Costmap] = None

    def step(self, n: int = 1) -> None:
        """Count ``n`` steps of work; raise :class:`BudgetExceeded` past ``budget``."""
        self.steps += n
        if self.budget and self.steps > self.budget:
            raise BudgetExceeded(f'step budget {self.budget} used up')

    def emit(self, kind: str, **data) -> None:
        """Record one thinking event, drawn by the family's glass-box layer."""
        fields = EVENT_KINDS.get(kind)
        if fields is None:
            raise ValueError(f'ctx.emit: unknown kind {kind!r}; one of {sorted(EVENT_KINDS)}')
        missing = [f for f in fields if f not in data]
        if missing:
            raise ValueError(f'ctx.emit({kind!r}): missing {missing}')
        ev = (kind, {f: data[f] for f in fields})
        if self._sink is not None:
            self._sink(ev)
        elif len(self.events) < self.MAX_EVENTS:
            self.events.append(ev)
        else:
            self.dropped += 1

    def cost(self, x: float, y: float) -> int:
        """Return the planner's costmap cost under (x, y) (planners only)."""
        if self._costmap is None:
            raise ValueError('ctx.cost: no costmap in this call')
        return self._costmap.cost_at(x, y)

    def world_to_map(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """Return the costmap cell under (x, y), or None (planners only)."""
        if self._costmap is None:
            raise ValueError('ctx.world_to_map: no costmap in this call')
        return self._costmap.world_to_map(x, y)

    def map_to_world(self, mx: int, my: int) -> Tuple[float, float]:
        """Return the centre of costmap cell (mx, my) (planners only)."""
        if self._costmap is None:
            raise ValueError('ctx.map_to_world: no costmap in this call')
        return self._costmap.map_to_world(mx, my)
