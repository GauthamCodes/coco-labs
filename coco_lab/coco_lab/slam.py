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
Mapping and SLAM: what every algorithm reads, and the trace it writes.

Lab 3 runs five things on ONE world (ROADMAP §4 invariant 6, identical
inputs by construction):

``known``      occupancy mapping with the TRUE poses (:mod:`occgrid`) --
               what the map would be if localisation were solved;
``odometry``   the same mapping with dead-reckoned poses -- why SLAM exists;
``ekf_slam``   EKF-SLAM on the IDEALISED landmark sensor (:mod:`ekfslam`);
``fastslam``   grid-based FastSLAM, a Rao-Blackwellised particle filter
               (:mod:`fastslam`);
``pose_graph`` scan matching, loop closure and a Gauss-Newton optimiser
               (:mod:`posegraph`).

Every SLAM reads :class:`SlamInputs` -- odometry, scans, the idealised
landmark observations and the start pose, at the world's update rows --
and **never the truth**, which is kept apart and used only to score them
(and, by definition, by ``known``). That is tested.

Trace schema ``coco_lab.slam_trace`` 1.0 (``docs/labs/SLAM_FORMAT.md``):
one row per update with the estimate; per-algorithm columns and
variable-length arrays (particles, landmarks, pose-graph edges); map
snapshots as ``nav_msgs/OccupancyGrid`` bytes; and, for the algorithms
that revise the past, the final trajectory.
"""

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .landmarks import LandmarkSensor, Observation
from .sketch import apply_delta, LidarSpec, odom_delta

SCHEMA = 'coco_lab.slam_trace'
VERSION = '1.0'
MAJOR = 1

ALGORITHMS = ('known', 'odometry', 'ekf_slam', 'fastslam', 'pose_graph')
COMMON_COLUMNS = ('row', 't', 'est_x', 'est_y', 'est_yaw')
#: wire dtypes the trace's arrays may use
ARRAY_DTYPES = ('u8', 'i32', 'f32', 'f64')

Pose = Tuple[float, float, float]


class SlamError(ValueError):
    """A SLAM input, parameter or trace that does not conform."""


@dataclass
class SlamInputs:
    """
    Everything a SLAM algorithm may read. The truth is not in here.

    Lists are per UPDATE (the world's update rows): ``odom[k]`` is the
    odometry pose (odometry's own frame), ``ranges[k]`` the measured scan,
    ``landmarks[k]`` the idealised sensor's observations (or ``None`` when
    the world has no landmark sensor). ``start`` is the robot's start pose
    in the map frame -- told, as ``/initialpose`` would be.
    """

    rows: List[int]
    t: List[float]
    odom: List[Pose]
    ranges: List[List[float]]
    lidar: LidarSpec
    start: Pose
    landmarks: Optional[List[List[Observation]]] = None
    landmark_sensor: Optional[LandmarkSensor] = None

    def __post_init__(self):
        n = len(self.rows)
        if not n:
            raise SlamError('no updates')
        for name in ('t', 'odom', 'ranges'):
            if len(getattr(self, name)) != n:
                raise SlamError(f'{name} has {len(getattr(self, name))} '
                                f'entries, expected {n}')
        if self.landmarks is not None and len(self.landmarks) != n:
            raise SlamError('landmarks must have one list per update')

    def __len__(self) -> int:
        """Return the number of updates."""
        return len(self.rows)

    def angles(self) -> List[float]:
        """Return the LiDAR's beam angles in the sensor frame."""
        return self.lidar.angles()


def dead_reckon(inp: SlamInputs) -> List[Pose]:
    """
    Return the odometry poses carried into the map frame from ``start``.

    Pose ``k`` is the start composed with odometry's motion from update 0
    to update ``k`` (the rigid composition :func:`odom_delta` /
    :func:`apply_delta` implement exactly).
    """
    out = [tuple(inp.start)]
    for k in range(1, len(inp)):
        d = odom_delta(inp.odom[k - 1], inp.odom[k])
        out.append(apply_delta(out[-1], *d))
    return out


def snapshot_updates(n: int, count: int) -> List[int]:
    """Return ``count`` update indices spread over ``0..n-1``, last included."""
    if n <= 0 or count <= 0:
        return []
    if count >= n:
        return list(range(n))
    return sorted({round(i * (n - 1) / (count - 1)) for i in range(count)}) \
        if count > 1 else [n - 1]


@dataclass
class SlamTrace:
    """
    One algorithm's run: header, per-update columns, arrays, map snapshots.

    ``columns`` hold :data:`COMMON_COLUMNS` plus the algorithm's own, one
    value per update; ``int_columns`` names the integer ones. ``arrays``
    are ``name -> (dtype, values)`` of any length (particles, landmarks,
    graph edges). ``snapshots`` are update indices and ``maps`` the
    OccupancyGrid bytes (north row first) at each, on the grid the header
    places. ``summary`` is filled by scoring against the truth.
    """

    header: Dict[str, object]
    columns: Dict[str, List]
    int_columns: Tuple[str, ...]
    arrays: Dict[str, Tuple[str, List]] = field(default_factory=dict)
    snapshots: List[int] = field(default_factory=list)
    maps: List[bytes] = field(default_factory=list)
    summary: Dict[str, object] = field(default_factory=dict)

    @property
    def algorithm(self) -> str:
        """Return the algorithm's name."""
        return self.header['algorithm']

    def __len__(self) -> int:
        """Return the number of updates."""
        return len(self.columns['row'])

    def estimates(self) -> List[Pose]:
        """Return the online estimate at every update."""
        c = self.columns
        return list(zip(c['est_x'], c['est_y'], c['est_yaw']))

    def final_trajectory(self) -> List[Pose]:
        """Return the final trajectory: revised if the algorithm revises."""
        a = self.arrays
        if 'final.x' in a:
            return list(zip(a['final.x'][1], a['final.y'][1],
                            a['final.yaw'][1]))
        return self.estimates()

    def validate(self) -> None:
        """Raise :class:`SlamError` unless the trace conforms to 1.x."""
        h = self.header
        if h.get('schema') != SCHEMA:
            raise SlamError(f'schema is {h.get("schema")!r}, not {SCHEMA!r}')
        try:
            major = int(str(h.get('version', '')).split('.')[0])
        except ValueError:
            raise SlamError(f'bad version {h.get("version")!r}') from None
        if major != MAJOR:
            raise SlamError(f'slam trace major version {major} is not '
                            f'supported (this reader speaks {MAJOR}.x)')
        if h.get('algorithm') not in ALGORITHMS:
            raise SlamError(f'algorithm {h.get("algorithm")!r}')
        g = h.get('grid')
        if not (isinstance(g, dict) and isinstance(g.get('width'), int)
                and isinstance(g.get('height'), int)):
            raise SlamError('header.grid must give width and height')
        for name in COMMON_COLUMNS:
            if name not in self.columns:
                raise SlamError(f'missing column {name!r}')
        n = len(self.columns['row'])
        for name, col in self.columns.items():
            if len(col) != n:
                raise SlamError(f'column {name!r} has {len(col)} rows, '
                                f'expected {n}')
            if name in self.int_columns:
                if not all(isinstance(v, int) for v in col):
                    raise SlamError(f'column {name!r} must be integers')
            elif not all(isinstance(v, (int, float)) and math.isfinite(v)
                         for v in col):
                raise SlamError(f'column {name!r} must be finite numbers')
        if any(b <= a for a, b in zip(self.columns['row'],
                                      self.columns['row'][1:])):
            raise SlamError('rows must strictly increase')
        for name, (dtype, vals) in self.arrays.items():
            if dtype not in ARRAY_DTYPES:
                raise SlamError(f'array {name!r}: dtype {dtype!r}')
            ints = dtype in ('u8', 'i32')
            if ints and not all(isinstance(v, int) for v in vals):
                raise SlamError(f'array {name!r} must be integers')
            if dtype == 'u8' and not all(0 <= v <= 255 for v in vals):
                raise SlamError(f'array {name!r}: u8 out of range')
            if not ints and not all(math.isfinite(v) for v in vals):
                raise SlamError(f'array {name!r} must be finite')
        if 'final.x' in self.arrays and len(self.arrays['final.x'][1]) != n:
            raise SlamError('the final trajectory has one pose per update')
        if len(self.snapshots) != len(self.maps):
            raise SlamError('one map per snapshot')
        if any(not 0 <= k < n for k in self.snapshots) or any(
                b <= a for a, b in zip(self.snapshots, self.snapshots[1:])):
            raise SlamError('snapshots must be increasing update indices')
        cells = g['width'] * g['height']
        if any(len(m) != cells for m in self.maps):
            raise SlamError('every snapshot map covers the whole grid')


def header(algorithm: str, params: Dict[str, object],
           grid: Dict[str, object], inputs: SlamInputs) -> Dict[str, object]:
    """Return a trace header."""
    return {'schema': SCHEMA, 'version': VERSION, 'algorithm': algorithm,
            'params': params, 'grid': grid, 'n_updates': len(inputs),
            'n_beams': inputs.lidar.samples}


def grid_header(width: int, height: int, resolution: float,
                origin: Sequence[float]) -> Dict[str, object]:
    """Return the ``grid`` block of a header."""
    return {'width': width, 'height': height, 'resolution': resolution,
            'origin': [float(origin[0]), float(origin[1])]}
