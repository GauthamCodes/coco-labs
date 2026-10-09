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
Localisation in the Arena (M2.3): Lab 2's filters, live, in the whole loop.

The ``localise`` subsystem of :class:`coco_lab.arena.Arena`, switched on
and tuned by ``config`` inputs (``localise.filter=mcl|ekf|both|off``,
``localise.mcl.particles=500``, ``localise.mcl.injection=augmented``,
...). It runs :class:`coco_lab.localise.MCL` and :class:`coco_lab.localise.EKF`
-- the very classes Lab 2's traces are made by -- on the Arena's wheel
odometry and LiDAR, updating when odometry has moved ``UPDATE_MIN_D`` /
``UPDATE_MIN_A`` since the last update (Lab 2's and AMCL's rule). It never
reads the truth, except to score itself: the error metrics compare the
estimate with the Arena's true pose, as Lab 2's traces did.

Its estimate is the robot's BELIEF (MCL's when both run): the Arena plans
and drives from it, so a localisation error reaches the planner and the
controller. Every update is emitted as the M2.1 families: the particle set
and MCL's bookkeeping, the EKF's prediction and update, each estimator's
pose (and dead reckoning's), and the errors as metrics.
"""

import math
import struct
from typing import Dict, Optional, Tuple

from .arena import ArenaError, Q_STATE, SUBSYSTEMS
from .columns import Batch
from .localise import EKF, EKFParams, MCL, MCLParams
from .sketch import odom_delta, UPDATE_MIN_A, UPDATE_MIN_D, wrap

FILTERS = ('off', 'mcl', 'ekf', 'both')
MCL_KEYS = {'particles': int, 'injection': str, 'alpha_slow': float,
            'alpha_fast': float, 'inject_fraction': float,
            'sigma_hit': float, 'beams': int, 'alphas': 'alphas',
            'init': str, 'aggregate': str, 'resample': str}
EKF_KEYS = {'sigma_hit': float, 'beams': int, 'alphas': 'alphas',
            'init': str, 'gate': float}


def _q(v: float) -> int:
    return round(v * Q_STATE)


def _compose(a, b):
    """Return pose ``b`` (in ``a``'s frame) in the frame ``a`` is in."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            wrap(a[2] + b[2]))


class ArenaLocaliser:
    """The Arena's ``localise`` subsystem: MCL and/or EKF, live."""

    def __init__(self, arena):
        """Attach to ``arena``; nothing runs until a filter is chosen."""
        self.arena = arena
        self.rng = arena.rng.split()
        self.filter = 'off'
        self.mcl_params = MCLParams()
        self.ekf_params = EKFParams()
        self.mcl: Optional[MCL] = None
        self.ekf: Optional[EKF] = None
        self.last_odom: Optional[Tuple[float, float, float]] = None
        # dead reckoning shown in the map frame: odometry composed onto the
        # pose the filters were started from
        self.anchor: Tuple[float, float, float] = arena.pose
        self.anchor_odom: Tuple[float, float, float] = arena.odom
        self.updates = 0

    # -- config ----------------------------------------------------------------

    def config(self, key: str, value: str) -> None:
        """Apply ``localise.<key>=<value>``; (re)start the filters it touches."""
        if key == 'filter':
            if value not in FILTERS:
                raise ArenaError(f'localise.filter must be one of {FILTERS}')
            self.filter = value
            self._start()
            return
        kind, _, name = key.partition('.')
        table = {'mcl': MCL_KEYS, 'ekf': EKF_KEYS}.get(kind)
        if table is None or name not in table:
            raise ArenaError(f'unknown localise setting {key!r}')
        params = self.mcl_params if kind == 'mcl' else self.ekf_params
        conv = table[name]
        try:
            if conv == 'alphas':
                v = tuple(float(x) for x in value.split(','))
            else:
                v = conv(value)
        except ValueError:
            raise ArenaError(f'bad value for localise.{key}: {value!r}') from None
        old = getattr(params, name)
        setattr(params, name, v)
        try:
            params.check()
        except Exception as e:
            setattr(params, name, old)
            raise ArenaError(f'localise.{key}: {e}') from None
        self._start()

    def _start(self):
        """(Re)start the chosen filters at the current belief (a tracking start)."""
        a = self.arena
        start = self.belief() or a.pose
        self.mcl = self.ekf = None
        if self.filter in ('mcl', 'both'):
            self.mcl_params.seed = 0  # the Arena's own stream draws, not seed
            self.mcl = MCL(a.smap, a.lidar, self.mcl_params, start, self.rng)
            a.emit_header('coco.localise.particles.header.v1', {
                'filter_id': 'mcl', 'kind': 'mcl',
                'params': self.mcl_params.to_dict()})
        if self.filter in ('ekf', 'both'):
            self.ekf = EKF(a.smap, a.lidar, self.ekf_params, start)
            a.emit_header('coco.localise.ekf.header.v1', {
                'filter_id': 'ekf', 'kind': 'ekf',
                'params': self.ekf_params.to_dict()})
        self.anchor, self.anchor_odom = start, a.odom
        self.last_odom = None
        self._est: Dict[str, Tuple[float, float, float]] = {}
        self._cov: Dict[str, Tuple[float, float]] = {}

    def on_reset(self, arena) -> None:
        """Restart the filters at the start pose (a reset is a new run)."""
        if self.filter != 'off':
            self._start()

    # -- per tick --------------------------------------------------------------

    def quality(self) -> Optional[Dict[str, float]]:
        """
        Return what the robot knows of its own uncertainty, or None.

        ``sigma_xy`` (m): the square root of the trace of the position
        covariance of the estimate the belief comes from (MCL's, else the
        EKF's); ``filter``: which. None before the first update.
        """
        cov = getattr(self, '_cov', {})
        for who in ('mcl', 'ekf'):
            if who in cov:
                xx, yy = cov[who]
                return {'sigma_xy': math.sqrt(max(0.0, xx + yy)),
                        'filter': who}
        return None

    def belief(self) -> Optional[Tuple[float, float, float]]:
        """Return the estimate (MCL's, else the EKF's), once one has updated."""
        est = getattr(self, '_est', {})
        return est.get('mcl') or est.get('ekf')

    def on_tick(self, arena) -> None:
        """Update the filters when odometry has moved enough (or first)."""
        if self.mcl is None and self.ekf is None:
            return
        odom = arena.odom
        if self.last_odom is not None:
            _, tr, _ = odom_delta(self.last_odom, odom)
            if tr < UPDATE_MIN_D and \
                    abs(wrap(odom[2] - self.last_odom[2])) < UPDATE_MIN_A:
                return
        self.last_odom = odom
        z = arena.ranges
        tick, t = arena.tick, arena.t_world
        truth = arena.pose
        metrics = Batch('coco.metrics.v1.MetricBatch')
        if self.mcl is not None:
            u = self.mcl.update(odom, z)
            est, cov = u['est'], u['cov']
            self._est['mcl'] = est
            self._cov['mcl'] = (cov[0], cov[2])
            P, w = u['particles']
            ps = Batch('coco.localise.v1.ParticleSetBatch',
                       update=self.mcl.updates - 1, filter_id='mcl')
            for (x, y, th), wi in zip(P, w):
                ps.add(tick, t, x=x, y=y, theta=th, weight=wi)
            arena.emit('coco.localise.particles.set.v1', ps)
            ub = Batch('coco.localise.v1.ParticleUpdateBatch', filter_id='mcl')
            ub.add(tick, t, update=self.mcl.updates - 1, n_eff=u['n_eff'],
                   resampled=u['resampled'], injected=u['injected'],
                   p_inject=u['p_inject'], w_avg=u['w_avg'],
                   w_slow=u['w_slow'], w_fast=u['w_fast'],
                   cluster_weight=u['cluster_weight'])
            arena.emit('coco.localise.particles.update.v1', ub)
            eb = Batch('coco.estimate.v1.EstimateBatch', estimator='mcl')
            eb.add(tick, t, x=est[0], y=est[1], theta=est[2],
                   cov_xx=cov[0], cov_xy=cov[1], cov_xt=0.0, cov_yy=cov[2],
                   cov_yt=0.0, cov_tt=cov[3])
            arena.emit('coco.estimate.pose.v1', eb)
            self._metrics(metrics, tick, t, 'mcl', est, truth)
            metrics.add(tick, t, name='n_eff', value=u['n_eff'], unit='')
        if self.ekf is not None:
            u = self.ekf.update(odom, z)
            est, P = u['est'], u['P']
            self._est['ekf'] = est
            self._cov['ekf'] = (P[0][0], P[1][1])
            pm, pP = u['pred_mu'], u['pred_P']
            kb = Batch('coco.localise.v1.EkfUpdateBatch', filter_id='ekf')
            kb.add(tick, t, update=self.ekf.updates - 1,
                   pred_x=pm[0], pred_y=pm[1], pred_theta=pm[2],
                   pred_cov_xx=pP[0][0], pred_cov_xy=pP[0][1],
                   pred_cov_xt=pP[0][2], pred_cov_yy=pP[1][1],
                   pred_cov_yt=pP[1][2], pred_cov_tt=pP[2][2],
                   post_x=est[0], post_y=est[1], post_theta=est[2],
                   post_cov_xx=P[0][0], post_cov_xy=P[0][1],
                   post_cov_xt=P[0][2], post_cov_yy=P[1][1],
                   post_cov_yt=P[1][2], post_cov_tt=P[2][2],
                   beams_used=u['beams_used'], beams_gated=u['beams_gated'],
                   nis=u['nis'])
            arena.emit('coco.localise.ekf.update.v1', kb)
            eb = Batch('coco.estimate.v1.EstimateBatch', estimator='ekf')
            eb.add(tick, t, x=est[0], y=est[1], theta=est[2],
                   cov_xx=P[0][0], cov_xy=P[0][1], cov_xt=P[0][2],
                   cov_yy=P[1][1], cov_yt=P[1][2], cov_tt=P[2][2])
            arena.emit('coco.estimate.pose.v1', eb)
            self._metrics(metrics, tick, t, 'ekf', est, truth)
        # dead reckoning: odometry alone, from where the filters started
        base = self.anchor_odom
        c, s = math.cos(-base[2]), math.sin(-base[2])
        dx, dy = odom[0] - base[0], odom[1] - base[1]
        local = (c * dx - s * dy, s * dx + c * dy, wrap(odom[2] - base[2]))
        dr = _compose(self.anchor, local)
        est_b = Batch('coco.estimate.v1.EstimateBatch', estimator='odometry')
        est_b.add(tick, t, x=dr[0], y=dr[1], theta=dr[2], cov_xx=0.0,
                  cov_xy=0.0, cov_xt=0.0, cov_yy=0.0, cov_yt=0.0, cov_tt=0.0)
        arena.emit('coco.estimate.pose.v1', est_b)
        self._metrics(metrics, tick, t, 'odometry', dr, truth)
        arena.emit('coco.metrics.values.v1', metrics)
        self.updates += 1

    @staticmethod
    def _metrics(b, tick, t, who, est, truth):
        b.add(tick, t, name=f'err_xy.{who}', unit='m',
              value=math.hypot(est[0] - truth[0], est[1] - truth[1]))
        b.add(tick, t, name=f'err_yaw.{who}', unit='rad',
              value=abs(wrap(est[2] - truth[2])))

    # -- the hash --------------------------------------------------------------

    def state_bytes(self) -> bytes:
        """Return the filters' state, quantized (docs/v2/ARENA_MODEL.md)."""
        out = [struct.pack('<B', FILTERS.index(self.filter)),
               struct.pack('<4Q', *self.rng.state)]
        if self.mcl is not None:
            m = self.mcl
            out.append(struct.pack('<I2q', len(m.P), _q(m.w_slow * 1e6),
                                   _q(m.w_fast * 1e6)))
            out.append(struct.pack(f'<{4 * len(m.P)}q', *(
                v for (x, y, th), wi in zip(m.P, m.w)
                for v in (_q(x), _q(y), _q(th), _q(wi)))))
        if self.ekf is not None:
            e = self.ekf
            out.append(struct.pack('<12q', *(_q(v) for v in e.mu),
                                   *(_q(e.P[i][j]) for i in range(3)
                                     for j in range(3))))
        lo = self.last_odom or (0.0, 0.0, 0.0)
        out.append(struct.pack('<3qI', *(_q(v) for v in lo), self.updates))
        return b''.join(out)


SUBSYSTEMS['localise'] = ArenaLocaliser
