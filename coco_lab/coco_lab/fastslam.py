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
Grid-based FastSLAM: a Rao-Blackwellised particle filter.

SLAM's posterior over (trajectory, map) factors as p(trajectory) times
p(map | trajectory), and the second factor is EXACT occupancy mapping with
known poses (:mod:`occgrid`). So sample trajectories with a particle
filter, and give every particle its own map built from its own trajectory
-- the Rao-Blackwellisation (Murphy 1999; Montemerlo et al. 2002). With a
grid map per particle it is the algorithm behind GMapping (Grisetti et al.
2007).

This one is plain FastSLAM: every particle's motion is SAMPLED from the
odometry model. GMapping adds an "improved proposal" (each sampled pose
corrected by scan matching before it is weighted) and is not reproduced
here. A greedy hill-climbing version of it was tried in Phase 4 and made
things WORSE on COCO's recorded tour: in the corridor between the bays the
scan's likelihood is flat along the corridor, and greedy steps slid the
particles along it (measured; ``docs/RESULTS.md`` "COCO Lab Phase 4"). What
the tour showed instead is that FastSLAM lives or dies by its MOTION
MODEL: with COCO's AMCL alphas (0.2 each, deliberately loose) it depleted
and diverged; with alphas calibrated on a different drive it tracked.

Per update:

1. **Sample** each particle's motion from the odometry motion model
   (``sketch.sample_delta``, the filter's ``alphas``).
2. **Weight** each particle by how well the scan fits ITS map: every used
   beam's endpoint scores ``z_hit * p + z_rand``, ``p`` the highest
   occupancy probability among the OBSERVED cells of the endpoint's 3 x 3
   neighbourhood in the particle's map, and 0 where it has observed none
   -- an endpoint in unexplored space is no evidence of a wall, as in
   GMapping, where a beam that matches nothing gets a fixed low
   likelihood. (Scoring unexplored cells 0.5 would make "my scan lands
   where I have never looked" score higher than "my scan lands where I
   saw free space", favouring particles that wander off the map.)
   Log-likelihoods are summed and scaled by ``temperature`` before
   exponentiating.
3. **Resample** (low variance, Lab 2's ``low_variance_resample``) only
   when the effective sample size ``1 / sum(w^2)`` falls below
   ``neff_fraction * N`` -- Doucet's selective resampling, which GMapping
   uses too. A resampled particle copies its parent's MAP.
4. **Map**: each particle integrates the scan at its own pose.

The online estimate is the heaviest particle's pose; the FINAL trajectory
is that particle's ANCESTRY, traced back through every resampling -- a
particle filter over trajectories revises the past by choosing which
history survived (tested).
"""

from dataclasses import asdict, dataclass
import math
import random
from typing import Dict, List, Optional, Tuple

from . import slam
from .localise import low_variance_resample
from .maps import LabMap
from .occgrid import GridParams, OccupancyGrid, sensor_pose
from .sketch import apply_delta, odom_delta, sample_delta

COLUMNS = ('neff', 'resampled', 'best')
INT_COLUMNS = ('row', 'resampled', 'best')
PARTICLE_ARRAYS = ('x', 'y', 'yaw', 'w')


@dataclass(frozen=True)
class FastSlamParams:
    """The filter's settings; every field documented in the module."""

    particles: int = 20
    alphas: Tuple[float, float, float, float] = (0.02, 0.02, 0.02, 0.02)
    #: weight with every ``beam_step``-th beam (the map uses every beam)
    beam_step: int = 2
    z_hit: float = 0.9
    z_rand: float = 0.1
    #: scale on the summed log-likelihood (1 = the plain product)
    temperature: float = 1.0
    neff_fraction: float = 0.5
    seed: int = 0
    snapshots: int = 16

    def check(self) -> None:
        """Raise :class:`slam.SlamError` unless the parameters make sense."""
        if not (1 <= self.particles <= 500):
            raise slam.SlamError('particles 1..500')
        if len(self.alphas) != 4 or any(a < 0 for a in self.alphas):
            raise slam.SlamError('alphas: four values >= 0')
        if not (1 <= self.beam_step <= 64):
            raise slam.SlamError('beam_step 1..64')
        if not (0 < self.z_hit and 0 < self.z_rand):
            raise slam.SlamError('z_hit and z_rand must be > 0')
        if not (0 < self.temperature <= 1):
            raise slam.SlamError('temperature in (0, 1]')
        if not (0 <= self.neff_fraction <= 1):
            raise slam.SlamError('neff_fraction in [0, 1]')
        if not (0 <= self.snapshots <= 64):
            raise slam.SlamError('snapshots 0..64')

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        d = asdict(self)
        d['alphas'] = list(self.alphas)
        return d


def scan_log_likelihood(grid: OccupancyGrid, pose, ranges, angles, mount,
                        range_min, range_max, z_hit, z_rand) -> float:
    """
    Return the log-likelihood of a scan's endpoints in ``grid`` from ``pose``.

    Beams with no return, or outside the sensor's limits, carry no
    evidence and are skipped.
    """
    sx, sy, sth = sensor_pose(pose, mount)
    r = grid.resolution
    ox, oy = grid.origin
    w, h = grid.width, grid.height
    lg, seen = grid.logodds, grid.seen
    total = 0.0
    exp = math.exp
    log = math.log
    for z, a in zip(ranges, angles):
        if not (range_min <= z < range_max):
            continue
        ang = sth + a
        ix = math.floor((sx + z * math.cos(ang) - ox) / r)
        iy = math.floor((sy + z * math.sin(ang) - oy) / r)
        best = -1.0
        anyseen = False
        for jy in (iy - 1, iy, iy + 1):
            if not 0 <= jy < h:
                continue
            base = jy * w
            for jx in (ix - 1, ix, ix + 1):
                if 0 <= jx < w and seen[base + jx]:
                    anyseen = True
                    v = lg[base + jx]
                    if v > best:
                        best = v
        p = 1.0 - 1.0 / (1.0 + exp(best)) if anyseen else 0.0
        total += log(z_hit * p + z_rand)
    return total


class FastSlam:
    """
    Grid FastSLAM, one update at a time (M2.4).

    Exactly :func:`run_fastslam`'s filter -- which is this class run over a
    world's updates -- so the Arena maps with the same algorithm, draw for
    draw, as Lab 3 did. ``rng``: ``random.Random(params.seed)`` for Lab 3's
    traces, the Arena's own stream in the Arena.
    """

    def __init__(self, start, lidar, like: LabMap, params: FastSlamParams,
                 grid_params: Optional[GridParams], rng):
        """Prepare; the first update builds every particle's first map."""
        params.check()
        self.p, self.lidar, self.like, self.rng = params, lidar, like, rng
        self.grid_params = grid_params
        self.start = tuple(start)
        self.angles = lidar.angles()
        self.w_angles = self.angles[::params.beam_step]
        n = params.particles
        self.poses = [self.start] * n
        self.grids: List[OccupancyGrid] = []
        self.weights = [1.0 / n] * n
        self.parent_of = list(range(n))
        self.prev_odom = None
        self.k = 0

    def update(self, odom, ranges) -> Dict[str, object]:
        """
        Run one update: motion, weighting, record, resampling, mapping.

        Returns the estimate (the heaviest particle's pose), n_eff, the best
        index, whether it resampled, and the weighted set as recorded
        (before resampling) with each particle's parent in the previous set.
        """
        p, rng, li = self.p, self.rng, self.lidar
        n = p.particles
        k = self.k
        if k == 0:
            first = OccupancyGrid.like(self.like, self.grid_params)
            first.integrate(self.start, ranges, self.angles, li.mount,
                            li.range_min, li.range_max)
            self.grids = [first] + [first.copy() for _ in range(n - 1)]
        else:
            d = odom_delta(self.prev_odom, odom)
            self.poses = [apply_delta(q, *sample_delta(*d, p.alphas, rng))
                          for q in self.poses]
            w_scan = ranges[::p.beam_step]
            logl = [scan_log_likelihood(self.grids[i], self.poses[i], w_scan,
                                        self.w_angles, li.mount, li.range_min,
                                        li.range_max, p.z_hit, p.z_rand)
                    for i in range(n)]
            m = max(logl)
            raw = [self.weights[i] * math.exp(p.temperature * (logl[i] - m))
                   for i in range(n)]
            sm = sum(raw)
            self.weights = [v / sm for v in raw] if sm > 0 else [1.0 / n] * n
        weights = self.weights
        neff = 1.0 / sum(v * v for v in weights)
        best = max(range(n), key=lambda i: weights[i])
        out = {'est': self.poses[best], 'neff': neff, 'best': best,
               'poses': list(self.poses), 'weights': list(weights),
               'parents': list(self.parent_of), 'resampled': 0}
        if k > 0 and neff < p.neff_fraction * n:
            idx = low_variance_resample(weights, rng.random())
            copies = {}
            new_grids = []
            for i in idx:
                # the first child of a parent takes its map; others copy it
                if i in copies:
                    new_grids.append(self.grids[i].copy())
                else:
                    copies[i] = True
                    new_grids.append(self.grids[i])
            self.grids = new_grids
            self.poses = [self.poses[i] for i in idx]
            self.weights = [1.0 / n] * n
            self.parent_of = idx
            out['resampled'] = 1
        else:
            self.parent_of = list(range(n))
        if k > 0:
            for i in range(n):
                self.grids[i].integrate(self.poses[i], ranges, self.angles,
                                        li.mount, li.range_min, li.range_max)
        self.prev_odom = odom
        self.k += 1
        return out

    def heaviest_grid(self) -> OccupancyGrid:
        """Return the map of the heaviest particle now."""
        return self.grids[max(range(len(self.weights)),
                              key=lambda i: self.weights[i])]


def run_fastslam(inp: slam.SlamInputs, like: LabMap,
                 params: Optional[FastSlamParams] = None,
                 grid_params: Optional[GridParams] = None) -> slam.SlamTrace:
    """Run grid FastSLAM over ``inp``; return its trace."""
    p = params or FastSlamParams()
    p.check()
    f = FastSlam(inp.start, inp.lidar, like, p, grid_params,
                 random.Random(p.seed))
    cols = {c: [] for c in slam.COMMON_COLUMNS + COLUMNS}
    parts = {c: [] for c in PARTICLE_ARRAYS}
    offset = [0]
    parents: List[List[int]] = []
    recorded: List[List[Tuple[float, float, float]]] = []
    snaps = set(slam.snapshot_updates(len(inp), p.snapshots))
    snapshots, maps = [], []
    for k in range(len(inp)):
        u = f.update(inp.odom[k], inp.ranges[k])
        for q, wv in zip(u['poses'], u['weights']):
            parts['x'].append(q[0])
            parts['y'].append(q[1])
            parts['yaw'].append(q[2])
            parts['w'].append(wv)
        offset.append(len(parts['x']))
        parents.append(u['parents'])
        recorded.append(u['poses'])
        est = u['est']
        for name, v in zip(slam.COMMON_COLUMNS + COLUMNS,
                           (inp.rows[k], inp.t[k], est[0], est[1], est[2],
                            u['neff'], u['resampled'], u['best'])):
            cols[name].append(v)
        if k in snaps:
            snapshots.append(k)
            maps.append(f.heaviest_grid().to_u8())
    # the final trajectory: the heaviest particle's ancestry
    j = cols['best'][-1]
    final = [None] * len(inp)
    for k in range(len(inp) - 1, -1, -1):
        final[k] = recorded[k][j]
        j = parents[k][j]
    arrays = {'particles.offset': ('i32', offset)}
    for c in PARTICLE_ARRAYS:
        arrays[f'particles.{c}'] = ('f32', parts[c])
    for c, i in (('x', 0), ('y', 1), ('yaw', 2)):
        arrays[f'final.{c}'] = ('f64', [q[i] for q in final])
    g = f.grids[0]
    hdr = slam.header('fastslam', p.to_dict(), slam.grid_header(
        g.width, g.height, g.resolution, g.origin), inp)
    hdr['grid_params'] = g.params.to_dict()
    tr = slam.SlamTrace(hdr, cols, INT_COLUMNS, arrays, snapshots, maps)
    tr.validate()
    return tr
