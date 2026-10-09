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
Mapping and SLAM in the Arena (M2.4): Lab 3's algorithms, live.

The ``map`` subsystem of :class:`coco_lab.arena.Arena`, chosen and tuned by
``config`` inputs (``map.algorithm=occupancy|ekf_slam|fastslam|pose_graph|off``,
``map.poses=truth|odometry|belief`` for plain occupancy mapping,
``map.fastslam.particles=20``, ``map.pose_graph.loop_closure=on|off``). Each
algorithm is the class Lab 3's traces are made by --
:class:`coco_lab.occgrid.OccupancyGrid`, :class:`coco_lab.ekfslam.EKFSlam`,
:class:`coco_lab.fastslam.FastSlam`, :class:`coco_lab.posegraph.PoseGraph`
-- fed the Arena's wheel odometry and LiDAR at Lab 3's update rule.

EKF-SLAM reads the IDEALISED landmark sensor (:mod:`coco_lab.landmarks`):
COCO has none. The sensor's header says so in the data
(``coco.map.slam.header.v1``), and every view shows it.

The map is built on a grid placed like the arena map at 0.10 m (Lab 3's
arena resolution), so it is scored, every ``SCORE_EVERY`` updates, against
the truth the way Lab 3 scored: ATE of the trajectory and F1 of the map
(:mod:`coco_lab.mapeval`), emitted as metrics. The truth is used ONLY for
those scores and for the idealised sensor's observations (Lab 3's rule).
"""

from array import array
from dataclasses import replace
import math
import struct
from typing import Dict, List, Optional, Tuple

from . import landmarks as lmk
from .arena import ArenaError, Q_STATE, SUBSYSTEMS
from .columns import Batch, CLOCKS
from .ekfslam import EKFSlam, EKFSlamParams
from .fastslam import FastSlam, FastSlamParams
from .mapeval import ate, score_map, Truth
from .occgrid import GridParams, OccupancyGrid
from .posegraph import PoseGraph, PoseGraphParams
from .sketch import odom_delta, UPDATE_MIN_A, UPDATE_MIN_D, wrap

ALGORITHMS = ('off', 'occupancy', 'ekf_slam', 'fastslam', 'pose_graph')
POSES = ('truth', 'odometry', 'belief')
#: score the map and trajectory every this many updates
SCORE_EVERY = 10
#: send the whole grid (a keyframe) every this many updates
SNAPSHOT_EVERY = 4
SENSOR_LABEL = ('IDEALISED landmark sensor: obstacle corners with known '
                'identities, no misses, no false detections -- COCO has none')


def _q(v: float) -> int:
    return round(v * Q_STATE)


def _compose(a, b):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            wrap(a[2] + b[2]))


class ArenaMapper:
    """The Arena's ``map`` subsystem: one mapping algorithm, live."""

    def __init__(self, arena):
        """Attach; prepare the 0.10 m truth for scoring and the landmarks."""
        self.arena = arena
        self.rng = arena.rng.split()
        self.obs_rng = arena.rng.split()
        self.like = arena.lab_map.downsample(2, 'arena@0.10')
        self.truth = Truth(self.like, arena.start[:2])
        # Lab 3's arena challenge places its landmarks this way (build_map.py)
        self.marks = lmk.corners(self.like, min_separation=2.0, max_count=64)
        self.sensor = lmk.LandmarkSensor()
        self.algorithm = 'off'
        self.poses_from = 'truth'
        self.grid_params = GridParams()
        self.fs_params = FastSlamParams()
        self.pg_params = PoseGraphParams()
        self.ekf_params = EKFSlamParams()
        self._reset_state()

    def _reset_state(self):
        self.engine = None
        self.grid: Optional[OccupancyGrid] = None
        self.last_odom = None
        self.anchor = self.arena.pose
        self.anchor_odom = self.arena.odom
        self.est_hist: List[Tuple[float, float, float]] = []
        self.true_hist: List[Tuple[float, float, float]] = []
        self.updates = 0

    # -- config ----------------------------------------------------------------

    def config(self, key: str, value: str) -> None:
        """Apply ``map.<key>=<value>``; restart the mapping it changes."""
        if key == 'algorithm':
            if value not in ALGORITHMS:
                raise ArenaError(f'map.algorithm must be one of {ALGORITHMS}')
            self.algorithm = value
        elif key == 'poses':
            if value not in POSES:
                raise ArenaError(f'map.poses must be one of {POSES}')
            self.poses_from = value
        elif key == 'fastslam.particles':
            n = int(value)
            if not 1 <= n <= 200:
                raise ArenaError('map.fastslam.particles must be 1..200')
            self.fs_params = replace(self.fs_params, particles=n)
        elif key == 'pose_graph.loop_closure':
            if value not in ('on', 'off'):
                raise ArenaError('map.pose_graph.loop_closure: on or off')
            self.pg_params = replace(self.pg_params, loop_closure=value == 'on')
        else:
            raise ArenaError(f'unknown map setting {key!r}')
        self._start()

    def _start(self):
        a = self.arena
        self._reset_state()
        start = a.belief()
        self.anchor = start
        self.anchor_odom = a.odom
        if self.algorithm == 'occupancy':
            self.grid = OccupancyGrid.like(self.like, self.grid_params)
        elif self.algorithm == 'ekf_slam':
            self.engine = EKFSlam(start, self.ekf_params)
            self.grid = OccupancyGrid.like(self.like, self.grid_params)
        elif self.algorithm == 'fastslam':
            self.engine = FastSlam(start, a.lidar, self.like, self.fs_params,
                                   self.grid_params, self.rng)
        elif self.algorithm == 'pose_graph':
            self.engine = PoseGraph(start, a.lidar, self.like, self.pg_params,
                                    self.grid_params)
        if self.algorithm == 'off':
            return
        g = self.like
        a.emit_header('coco.map.grid.header.v1', {
            'map_id': self.algorithm, 'width': g.width, 'height': g.height,
            'resolution': g.resolution, 'origin_x': g.origin[0],
            'origin_y': g.origin[1], 'row0_is_bottom': True,
            'model': self.grid_params.to_dict(),
            'estimator': self.poses_from if self.algorithm == 'occupancy'
            else self.algorithm})
        if self.algorithm != 'occupancy':
            params = {'ekf_slam': self.ekf_params, 'fastslam': self.fs_params,
                      'pose_graph': self.pg_params}[self.algorithm].to_dict()
            a.emit_header('coco.map.slam.header.v1', {
                'slam_id': self.algorithm, 'algorithm': self.algorithm,
                'params': params,
                'sensor': 'landmarks' if self.algorithm == 'ekf_slam'
                else 'lidar',
                'sensor_label': SENSOR_LABEL if self.algorithm == 'ekf_slam'
                else "LiDAR (the Arena model's ray-cast scan)"})

    def on_reset(self, arena) -> None:
        """Start the map again (a reset is a new run)."""
        if self.algorithm != 'off':
            self._start()

    # -- per tick --------------------------------------------------------------

    def _dead_reckoned(self, odom):
        base = self.anchor_odom
        c, s = math.cos(-base[2]), math.sin(-base[2])
        dx, dy = odom[0] - base[0], odom[1] - base[1]
        return _compose(self.anchor, (c * dx - s * dy, s * dx + c * dy,
                                      wrap(odom[2] - base[2])))

    def on_tick(self, arena) -> None:
        """Update the map when odometry has moved enough (or first)."""
        if self.algorithm == 'off':
            return
        odom = arena.odom
        if self.last_odom is not None:
            _, tr, _ = odom_delta(self.last_odom, odom)
            if tr < UPDATE_MIN_D and \
                    abs(wrap(odom[2] - self.last_odom[2])) < UPDATE_MIN_A:
                return
        first = self.last_odom is None
        prev = self.last_odom
        self.last_odom = odom
        z, li = arena.ranges, arena.lidar
        tick, t = arena.tick, arena.t_world
        truth = arena.pose
        alg = self.algorithm
        if alg == 'occupancy':
            pose = {'truth': truth, 'odometry': self._dead_reckoned(odom),
                    'belief': arena.belief()}[self.poses_from]
            self.grid.integrate(pose, z, li.angles(), li.mount, li.range_min,
                                li.range_max)
        elif alg == 'ekf_slam':
            f = self.engine
            if not first:
                f.predict(*odom_delta(prev, odom))
            obs = lmk.observe(arena.smap, truth, self.marks, self.sensor,
                              self.obs_rng)
            for o in obs:
                f.update(*f.to_model(o))
            pose = tuple(f.mu[:3])
            self.grid.integrate(pose, z, li.angles(), li.mount, li.range_min,
                                li.range_max)
            lb = Batch('coco.map.v1.LandmarkBatch', update=self.updates,
                       slam_id='ekf_slam')
            for lid, x, y, cxx, cxy, cyy in f.landmark_rows():
                lb.add(tick, t, landmark_id=lid, x=x, y=y, cov_xx=cxx,
                       cov_xy=cxy, cov_yy=cyy)
            arena.emit('coco.map.slam.landmarks.v1', lb)
        elif alg == 'fastslam':
            u = self.engine.update(odom, z)
            pose = u['est']
            pb = Batch('coco.map.v1.SlamParticleBatch', best=u['best'],
                       update=self.updates, slam_id='fastslam')
            for (x, y, th), w in zip(u['poses'], u['weights']):
                pb.add(tick, t, x=x, y=y, theta=th, weight=w)
            arena.emit('coco.map.slam.particles.v1', pb)
        else:  # pose_graph
            u = self.engine.update(odom, z)
            pose = u['est']
            if u['opt'] is not None:
                self._emit_graph(arena, 'raw', u['opt']['poses_before'],
                                 u['opt']['chi2_before'])
                self._emit_graph(arena, 'optimised', self.engine.poses,
                                 u['opt']['chi2_after'])
            elif self.updates % SNAPSHOT_EVERY == 0:
                self._emit_graph(arena, 'raw', self.engine.poses, None)
        eb = Batch('coco.estimate.v1.EstimateBatch',
                   estimator=alg if alg != 'occupancy'
                   else f'map:{self.poses_from}')
        eb.add(tick, t, x=pose[0], y=pose[1], theta=pose[2], cov_xx=0.0,
               cov_xy=0.0, cov_xt=0.0, cov_yy=0.0, cov_yt=0.0, cov_tt=0.0)
        arena.emit('coco.estimate.pose.v1', eb)
        self.est_hist.append(tuple(pose))
        self.true_hist.append(truth)
        if self.updates % SNAPSHOT_EVERY == 0 or (
                alg == 'pose_graph' and u['opt'] is not None):
            self._emit_snapshot(arena)
        if self.updates % SCORE_EVERY == 0 and self.updates > 0:
            self._emit_scores(arena)
        self.updates += 1

    def current_grid(self) -> OccupancyGrid:
        """Return the map as it stands now (the heaviest particle's, ...)."""
        if self.algorithm == 'fastslam':
            return self.engine.heaviest_grid()
        if self.algorithm == 'pose_graph':
            return self.engine.grid()
        return self.grid

    def _emit_snapshot(self, arena):
        if arena.on_family is None:
            return
        g = self.current_grid()
        cols = {n: array(c) for n, c in CLOCKS}
        cols['seq'].append(self.updates)
        cols['tick'].append(arena.tick)
        cols['t_world'].append(arena.t_world)
        cols['logodds_f32'] = array('f', g.logodds)
        arena.on_family('coco.map.grid.snapshot.v1', arena.tick, cols,
                        {'map_id': self.algorithm, 'update': self.updates})

    def _emit_graph(self, arena, stage, poses, chi2):
        tick, t = arena.tick, arena.t_world
        nb = Batch('coco.map.v1.GraphNodeBatch', stage=stage,
                   chi2=chi2 if chi2 is not None else 0.0,
                   slam_id='pose_graph')
        for i, (x, y, th) in enumerate(poses):
            nb.add(tick, t, node_id=i, x=x, y=y, theta=th)
        arena.emit('coco.map.slam.nodes.v1', nb)
        eb = Batch('coco.map.v1.GraphEdgeBatch', stage=stage,
                   slam_id='pose_graph')
        for e in self.engine.edges:
            eb.add(tick, t, from_node=e.i, to_node=e.j, kind=e.kind,
                   dx=e.z[0], dy=e.z[1], dtheta=e.z[2], error=0.0)
        arena.emit('coco.map.slam.edges.v1', eb)

    def scores(self) -> Dict[str, float]:
        """ATE (aligned, m) of the trajectory so far and F1 of the map now."""
        est = self.est_hist
        if self.algorithm == 'pose_graph':
            est = list(self.engine.poses)
        a = ate(est, self.true_hist, align=self.algorithm != 'occupancy')
        s = score_map(self.truth, self.current_grid().to_labmap())
        return {'ate': a['rmse'], 'f1': s['f1'] or 0.0,
                'precision': s['precision'] or 0.0,
                'recall': s['recall'] or 0.0}

    def _emit_scores(self, arena):
        sc = self.scores()
        mb = Batch('coco.metrics.v1.MetricBatch')
        for name, unit in (('ate', 'm'), ('f1', ''), ('precision', ''),
                           ('recall', '')):
            mb.add(arena.tick, arena.t_world, name=name, value=sc[name],
                   unit=unit)
        arena.emit('coco.metrics.values.v1', mb)

    # -- the hash --------------------------------------------------------------

    def state_bytes(self) -> bytes:
        """Return the mapping state, quantized (docs/v2/ARENA_MODEL.md)."""
        out = [struct.pack('<BBI', ALGORITHMS.index(self.algorithm),
                           POSES.index(self.poses_from), self.updates),
               struct.pack('<8Q', *self.rng.state, *self.obs_rng.state)]
        for p in self.est_hist[-1:]:
            out.append(struct.pack('<3q', *(_q(v) for v in p)))
        if self.algorithm == 'fastslam':
            f = self.engine
            out.append(struct.pack(f'<{4 * len(f.poses)}q', *(
                v for (x, y, th), w in zip(f.poses, f.weights)
                for v in (_q(x), _q(y), _q(th), _q(w)))))
        if self.algorithm == 'ekf_slam':
            out.append(struct.pack(f'<{len(self.engine.mu)}q',
                                   *(_q(v) for v in self.engine.mu)))
        if self.algorithm == 'pose_graph':
            out.append(struct.pack('<I', len(self.engine.edges)))
        return b''.join(out)


SUBSYSTEMS['map'] = ArenaMapper
