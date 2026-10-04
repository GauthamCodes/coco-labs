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
Occupancy mapping with given poses, and one entry point for every run.

``known`` places each scan at the TRUE pose: the map localisation-solved
would give, and the reference the SLAMs are compared with. ``odometry``
places each scan at the dead-reckoned pose (:func:`slam.dead_reckon`):
the map a robot that trusts its wheels draws -- smeared and bent, which is
the whole reason SLAM exists. Both are :mod:`occgrid`'s log-odds mapping;
only the poses differ.

:func:`run` dispatches by name. Every algorithm receives the same
:class:`slam.SlamInputs`; only ``known`` additionally receives the true
poses, because that is what it means.
"""

from dataclasses import asdict, dataclass
from typing import Dict, Optional, Sequence

from . import slam
from .ekfslam import EKFSlamParams, run_ekf_slam
from .fastslam import FastSlamParams, run_fastslam
from .maps import LabMap
from .occgrid import GridParams, OccupancyGrid
from .posegraph import PoseGraphParams, run_pose_graph


@dataclass(frozen=True)
class GivenPoseParams:
    """Settings for mapping with given poses."""

    snapshots: int = 16

    def check(self) -> None:
        """Raise :class:`slam.SlamError` unless the parameters make sense."""
        if not (0 <= self.snapshots <= 64):
            raise slam.SlamError('snapshots 0..64')

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return asdict(self)


def run_given_poses(algorithm: str, inp: slam.SlamInputs, like: LabMap,
                    poses: Sequence[slam.Pose],
                    params: Optional[GivenPoseParams] = None,
                    grid_params: Optional[GridParams] = None
                    ) -> slam.SlamTrace:
    """Map with ``poses`` (one per update); trace it as ``algorithm``."""
    p = params or GivenPoseParams()
    p.check()
    if len(poses) != len(inp):
        raise slam.SlamError('one pose per update')
    grid = OccupancyGrid.like(like, grid_params)
    angles = inp.angles()
    li = inp.lidar
    cols = {c: [] for c in slam.COMMON_COLUMNS}
    snaps = set(slam.snapshot_updates(len(inp), p.snapshots))
    snapshots, maps = [], []
    for k, pose in enumerate(poses):
        grid.integrate(pose, inp.ranges[k], angles, li.mount, li.range_min,
                       li.range_max)
        for name, v in zip(slam.COMMON_COLUMNS,
                           (inp.rows[k], inp.t[k], pose[0], pose[1],
                            pose[2])):
            cols[name].append(v)
        if k in snaps:
            snapshots.append(k)
            maps.append(grid.to_u8())
    hdr = slam.header(algorithm, p.to_dict(), slam.grid_header(
        grid.width, grid.height, grid.resolution, grid.origin), inp)
    hdr['grid_params'] = grid.params.to_dict()
    hdr['poses'] = ('the TRUE poses (localisation solved)'
                    if algorithm == 'known' else
                    'odometry, dead-reckoned from the start')
    tr = slam.SlamTrace(hdr, cols, ('row',), {}, snapshots, maps)
    tr.validate()
    return tr


PARAMS = {
    'known': GivenPoseParams,
    'odometry': GivenPoseParams,
    'ekf_slam': EKFSlamParams,
    'fastslam': FastSlamParams,
    'pose_graph': PoseGraphParams,
}


def params_from_dict(algorithm: str, d: Dict[str, object]):
    """Rebuild an algorithm's parameters from its header's ``params``."""
    if algorithm not in PARAMS:
        raise slam.SlamError(f'unknown algorithm {algorithm!r}')
    cls = PARAMS[algorithm]
    p = cls(**{k: (tuple(v) if isinstance(v, list) else v)
               for k, v in d.items()})
    p.check()
    return p


def run(algorithm: str, inp: slam.SlamInputs, like: LabMap, params=None,
        grid_params: Optional[GridParams] = None,
        true_poses: Optional[Sequence[slam.Pose]] = None) -> slam.SlamTrace:
    """Run one algorithm by name on ``inp``; ``like`` places the grid."""
    if algorithm == 'known':
        if true_poses is None:
            raise slam.SlamError('known-pose mapping needs the true poses')
        return run_given_poses('known', inp, like, true_poses, params,
                               grid_params)
    if algorithm == 'odometry':
        return run_given_poses('odometry', inp, like, slam.dead_reckon(inp),
                               params, grid_params)
    if algorithm == 'ekf_slam':
        return run_ekf_slam(inp, like, params, grid_params)
    if algorithm == 'fastslam':
        return run_fastslam(inp, like, params, grid_params)
    if algorithm == 'pose_graph':
        return run_pose_graph(inp, like, params, grid_params)
    raise slam.SlamError(f'unknown algorithm {algorithm!r}')
