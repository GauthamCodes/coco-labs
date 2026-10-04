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
EKF-SLAM with known correspondences, on the IDEALISED landmark sensor.

One Gaussian over the robot's pose AND every landmark seen so far: the
state is ``(x, y, yaw, l1x, l1y, l2x, l2y, ...)`` and its covariance holds
every correlation between them (*Probabilistic Robotics*, table 10.1, with
landmarks added when first seen rather than preallocated).

- **Prediction** moves only the pose, by the odometry motion model
  linearised exactly as Lab 2's EKF does it (``localise._motion_jacobians``),
  and propagates the pose-landmark cross-covariance through the same
  Jacobian. Landmarks do not move, so their block is untouched (tested).
- **A new landmark** is initialised from its first observation, with the
  covariance the observation's Jacobians give it -- so it inherits the
  robot's uncertainty and is correlated with it.
- **An update** on a known landmark is the standard EKF update. With
  correspondences known (the idealised sensor's ``id``), there is no data
  association step to get wrong.

Two measurement models: ``range_bearing`` (the lab's) and ``relative_xy``
(the landmark in the robot's frame, Cartesian). With the heading known
exactly, ``relative_xy`` is LINEAR in the state, so EKF-SLAM must then
equal the exact Gaussian posterior -- the closed-form check the tests use
(``kalman.batch_posterior``).

The occupancy map shown for EKF-SLAM is the LiDAR placed at its pose
estimates (:mod:`occgrid`): EKF-SLAM itself builds only the landmark map.
"""

from dataclasses import asdict, dataclass
import math
from typing import Dict, List, Optional, Tuple

from . import slam
from .landmarks import LandmarkSensor
from .localise import _motion_jacobians
from .maps import LabMap
from .occgrid import GridParams, OccupancyGrid
from .sketch import apply_delta, odom_delta, wrap

MODELS = ('range_bearing', 'relative_xy')
#: per-update columns this algorithm adds to slam.COMMON_COLUMNS
COLUMNS = ('cov_xx', 'cov_xy', 'cov_yy', 'cov_tt', 'n_landmarks', 'n_obs')
INT_COLUMNS = ('row', 'n_landmarks', 'n_obs')


@dataclass(frozen=True)
class EKFSlamParams:
    """The filter's assumptions (what it BELIEVES about the world)."""

    #: odometry motion model alphas the filter assumes
    alphas: Tuple[float, float, float, float] = (0.02, 0.02, 0.02, 0.02)
    #: measurement noise the filter assumes
    sigma_range: float = 0.05
    sigma_bearing: float = 0.02
    model: str = 'range_bearing'
    #: initial pose covariance (start told, like /initialpose)
    start_sigma_xy: float = 0.01
    start_sigma_yaw: float = 0.01
    snapshots: int = 16

    def check(self) -> None:
        """Raise :class:`slam.SlamError` unless the parameters make sense."""
        if len(self.alphas) != 4 or any(a < 0 for a in self.alphas):
            raise slam.SlamError('alphas: four values >= 0')
        if not (0 < self.sigma_range <= 2 and 0 < self.sigma_bearing <= 1):
            raise slam.SlamError('sigmas out of range')
        if self.model not in MODELS:
            raise slam.SlamError(f'model must be one of {MODELS}')
        if not (0 <= self.snapshots <= 64):
            raise slam.SlamError('snapshots 0..64')

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        d = asdict(self)
        d['alphas'] = list(self.alphas)
        return d


class EKFSlam:
    """The filter's state: a mean list and a dense covariance."""

    def __init__(self, start, params: EKFSlamParams):
        """Start at ``start`` with the stated pose covariance, no landmarks."""
        self.p = params
        self.mu = [float(v) for v in start]
        sxy, syaw = params.start_sigma_xy ** 2, params.start_sigma_yaw ** 2
        self.P = [[sxy, 0.0, 0.0], [0.0, sxy, 0.0], [0.0, 0.0, syaw]]
        self.slot: Dict[int, int] = {}  # landmark id -> state index of lx
        self.R = self._r()

    def _r(self):
        if self.p.model == 'range_bearing':
            return ((self.p.sigma_range ** 2, 0.0),
                    (0.0, self.p.sigma_bearing ** 2))
        # relative_xy: the same sigma on both axes
        s = self.p.sigma_range ** 2
        return ((s, 0.0), (0.0, s))

    @property
    def n(self) -> int:
        """Return the state's dimension."""
        return len(self.mu)

    def predict(self, rot1: float, trans: float, rot2: float) -> None:
        """Move the pose by the odometry increment; landmarks stay put."""
        G, Q = _motion_jacobians(self.mu[:3], rot1, trans, rot2,
                                 self.p.alphas)
        x, y, th = apply_delta(tuple(self.mu[:3]), rot1, trans, rot2)
        self.mu[0], self.mu[1], self.mu[2] = x, y, th
        P, n = self.P, self.n
        # pose block: G P G^T + Q
        Prr = [[P[i][j] for j in range(3)] for i in range(3)]
        GP = [[sum(G[i][k] * Prr[k][j] for k in range(3)) for j in range(3)]
              for i in range(3)]
        for i in range(3):
            for j in range(3):
                P[i][j] = sum(GP[i][k] * G[j][k] for k in range(3)) + Q[i][j]
        # cross blocks: G P_rl, and its transpose
        for j in range(3, n):
            c = [P[0][j], P[1][j], P[2][j]]
            for i in range(3):
                v = G[i][0] * c[0] + G[i][1] * c[1] + G[i][2] * c[2]
                P[i][j] = v
                P[j][i] = v

    # -- measurement model --------------------------------------------------

    def _h(self, j: int):
        """Return ``(zhat, Hr (2x3), Hl (2x2))`` for the landmark at ``j``."""
        x, y, th = self.mu[:3]
        dx, dy = self.mu[j] - x, self.mu[j + 1] - y
        if self.p.model == 'range_bearing':
            q = max(dx * dx + dy * dy, 1e-12)
            sq = math.sqrt(q)
            zhat = (sq, wrap(math.atan2(dy, dx) - th))
            Hr = ((-dx / sq, -dy / sq, 0.0), (dy / q, -dx / q, -1.0))
            Hl = ((dx / sq, dy / sq), (-dy / q, dx / q))
        else:
            c, s = math.cos(th), math.sin(th)
            zhat = (c * dx + s * dy, -s * dx + c * dy)
            Hr = ((-c, -s, -s * dx + c * dy), (s, -c, -c * dx - s * dy))
            Hl = ((c, s), (-s, c))
        return zhat, Hr, Hl

    def _residual(self, z, zhat):
        if self.p.model == 'range_bearing':
            return (z[0] - zhat[0], wrap(z[1] - zhat[1]))
        return (z[0] - zhat[0], z[1] - zhat[1])

    def add_landmark(self, lid: int, z) -> None:
        """Initialise landmark ``lid`` from its first observation ``z``."""
        x, y, th = self.mu[:3]
        if self.p.model == 'range_bearing':
            r, b = z
            a = th + b
            ca, sa = math.cos(a), math.sin(a)
            lx, ly = x + r * ca, y + r * sa
            Gr = ((1.0, 0.0, -r * sa), (0.0, 1.0, r * ca))
            Gz = ((ca, -r * sa), (sa, r * ca))
        else:
            zx, zy = z
            c, s = math.cos(th), math.sin(th)
            lx, ly = x + c * zx - s * zy, y + s * zx + c * zy
            Gr = ((1.0, 0.0, -s * zx - c * zy), (0.0, 1.0, c * zx - s * zy))
            Gz = ((c, -s), (s, c))
        P, n, R = self.P, self.n, self.R
        # cross-covariance with everything already in the state: Gr P_r*
        cross = [[sum(Gr[i][k] * P[k][j] for k in range(3)) for j in range(n)]
                 for i in range(2)]
        # its own block: Gr P_rr Gr^T + Gz R Gz^T
        own = [[0.0, 0.0], [0.0, 0.0]]
        for i in range(2):
            for j in range(2):
                own[i][j] = sum(cross[i][k] * Gr[j][k] for k in range(3)) + \
                    sum(Gz[i][a] * R[a][b] * Gz[j][b]
                        for a in range(2) for b in range(2))
        for i in range(n):
            P[i].extend([cross[0][i], cross[1][i]])
        P.append(cross[0] + own[0])
        P.append(cross[1] + own[1])
        self.mu.extend([lx, ly])
        self.slot[lid] = n

    def update(self, lid: int, z) -> None:
        """EKF update on a known landmark (adds it if new)."""
        if lid not in self.slot:
            self.add_landmark(lid, z)
            return
        j = self.slot[lid]
        zhat, Hr, Hl = self._h(j)
        nu = self._residual(z, zhat)
        P, n = self.P, self.n
        idx = (0, 1, 2, j, j + 1)
        H = [Hr[0] + Hl[0], Hr[1] + Hl[1]]  # 2 x 5 over idx
        # P H^T (n x 2), using only the five columns H touches
        PHt = [[sum(P[i][idx[k]] * H[a][k] for k in range(5))
                for a in range(2)] for i in range(n)]
        S = [[sum(H[a][k] * PHt[idx[k]][b] for k in range(5)) + self.R[a][b]
              for b in range(2)] for a in range(2)]
        det = S[0][0] * S[1][1] - S[0][1] * S[1][0]
        Si = ((S[1][1] / det, -S[0][1] / det), (-S[1][0] / det, S[0][0] / det))
        K = [[PHt[i][0] * Si[0][b] + PHt[i][1] * Si[1][b] for b in range(2)]
             for i in range(n)]
        for i in range(n):
            self.mu[i] += K[i][0] * nu[0] + K[i][1] * nu[1]
        self.mu[2] = wrap(self.mu[2])
        # P <- P - K (P H^T)^T, then symmetrised
        for i in range(n):
            Ki0, Ki1 = K[i]
            Pi = P[i]
            for k in range(n):
                Pi[k] -= Ki0 * PHt[k][0] + Ki1 * PHt[k][1]
        for i in range(n):
            for k in range(i + 1, n):
                v = 0.5 * (P[i][k] + P[k][i])
                P[i][k] = v
                P[k][i] = v

    def to_model(self, obs) -> Tuple[int, Tuple[float, float]]:
        """Return ``(id, z)`` in this filter's model from ``(id, r, b)``."""
        lid, r, b = obs
        if self.p.model == 'range_bearing':
            return lid, (r, b)
        return lid, (r * math.cos(b), r * math.sin(b))

    def landmark_rows(self):
        """Return ``[(id, x, y, cxx, cxy, cyy)]`` by id."""
        out = []
        for lid in sorted(self.slot):
            j = self.slot[lid]
            out.append((lid, self.mu[j], self.mu[j + 1], self.P[j][j],
                        self.P[j][j + 1], self.P[j + 1][j + 1]))
        return out


def run_ekf_slam(inp: slam.SlamInputs, like: LabMap,
                 params: Optional[EKFSlamParams] = None,
                 grid_params: Optional[GridParams] = None) -> slam.SlamTrace:
    """Run EKF-SLAM over ``inp``; return its trace (map: scans at its poses)."""
    p = params or EKFSlamParams()
    p.check()
    if inp.landmarks is None:
        raise slam.SlamError('EKF-SLAM needs the idealised landmark sensor')
    f = EKFSlam(inp.start, p)
    grid = OccupancyGrid.like(like, grid_params)
    angles = inp.angles()
    li = inp.lidar
    cols = {c: [] for c in slam.COMMON_COLUMNS + COLUMNS}
    lm_off, lm = [0], {k: [] for k in ('id', 'x', 'y', 'cxx', 'cxy', 'cyy')}
    snaps = set(slam.snapshot_updates(len(inp), p.snapshots))
    snapshots, maps = [], []
    for k in range(len(inp)):
        if k > 0:
            f.predict(*odom_delta(inp.odom[k - 1], inp.odom[k]))
        for obs in inp.landmarks[k]:
            f.update(*f.to_model(obs))
        pose = tuple(f.mu[:3])
        grid.integrate(pose, inp.ranges[k], angles, li.mount, li.range_min,
                       li.range_max)
        P = f.P
        for name, v in zip(slam.COMMON_COLUMNS + COLUMNS,
                           (inp.rows[k], inp.t[k], pose[0], pose[1], pose[2],
                            P[0][0], P[0][1], P[1][1], P[2][2],
                            len(f.slot), len(inp.landmarks[k]))):
            cols[name].append(v)
        for row in f.landmark_rows():
            for name, v in zip(('id', 'x', 'y', 'cxx', 'cxy', 'cyy'), row):
                lm[name].append(v)
        lm_off.append(len(lm['id']))
        if k in snaps:
            snapshots.append(k)
            maps.append(grid.to_u8())
    arrays = {'lm.offset': ('i32', lm_off), 'lm.id': ('i32', lm['id'])}
    for name in ('x', 'y', 'cxx', 'cxy', 'cyy'):
        arrays[f'lm.{name}'] = ('f64', lm[name])
    hdr = slam.header('ekf_slam', p.to_dict(), slam.grid_header(
        grid.width, grid.height, grid.resolution, grid.origin), inp)
    hdr['grid_params'] = grid.params.to_dict()
    hdr['map_note'] = ('EKF-SLAM builds a LANDMARK map; the occupancy map is '
                       'the LiDAR placed at its pose estimates')
    tr = slam.SlamTrace(hdr, cols, INT_COLUMNS, arrays, snapshots, maps)
    tr.validate()
    return tr
