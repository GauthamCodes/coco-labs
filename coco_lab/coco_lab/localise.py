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
Localisation: Monte Carlo localisation and EKF localisation, traced.

Both filters read **the same inputs**: a :class:`coco_lab.sketch.WorldRun`'s
odometry and scans at its update rows, the map, and the start (for a
tracking start) -- never the truth, which is used only to score them. That
is what makes the comparison fair (ROADMAP §4 invariant 6), and it is
tested: the filters are handed a view without the truth.

**MCL** (:func:`run_mcl`) is AMCL's algorithm, with AMCL's defaults where
COCO's ``nav2_params.yaml`` sets them:

- motion: the odometry motion model, alphas ``alpha1..alpha4``;
- measurement: the *likelihood field* -- each beam endpoint scores
  ``z_hit * exp(-d^2 / 2 sigma_hit^2) + z_rand / range_max``, ``d`` the
  distance from the endpoint to the nearest obstacle, capped at
  ``laser_likelihood_max_dist`` (exactly AMCL's per-beam term). A
  particle's score is AMCL's, ``1 + sum(pz^3)`` -- nav2_amcl's own comment
  calls it "an ad-hoc weighting scheme for combining beam probs" -- and its
  weight is multiplied by it. ``aggregate='product'`` is the textbook
  product of the ``pz`` instead: far peakier, so a cloud collapses faster
  (measured on the teaching rooms; ``docs/labs/LAB2_LOCALISE.md``);
- resampling: low-variance (systematic), every update by default --
  COCO's ``resample_interval`` is 1;
- **injection**, the parameter COCO's AMCL has switched off: augmented MCL
  (*Probabilistic Robotics* table 8.3) keeps two running averages of the
  measurement likelihood, ``w_slow`` and ``w_fast``, and replaces each
  resampled particle with a uniformly random one with probability
  ``max(0, 1 - w_fast / w_slow)``. ``alpha_slow = alpha_fast = 0`` --
  COCO's setting -- is never; a fixed fraction is also offered.

Fixed particle count (AMCL adapts it with KLD sampling; that is left out
so the particle slider means what it says).

**EKF** (:func:`run_ekf`) is EKF localisation on raw ranges: the state is
one Gaussian over ``(x, y, yaw)``; prediction uses the same odometry
model linearised (*Probabilistic Robotics* table 7.1); each update casts a
subset of beams from the mean, takes the Jacobian by central differences,
gates beams whose normalised innovation squared exceeds a chi-square
bound, and applies the rest in one Joseph-form update
(:mod:`coco_lab.kalman`). It cannot represent two places at once, and
that is the lesson the race shows.

Trace schema ``coco_lab.loc_trace`` 1.0 (``docs/labs/LOC_TRACE_SCHEMA.md``):
one row per filter update, the estimate, its covariance and its error; for
MCL, the weighted particle set at every update.
"""

from dataclasses import asdict, dataclass
import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

from . import kalman
from .sketch import (apply_delta, INF, odom_delta, ROBOT_RADIUS,
                     SketchMap, WorldRun, wrap)

SCHEMA = 'coco_lab.loc_trace'
VERSION = '1.0'
MAJOR = 1

FILTERS = ('mcl', 'ekf')
INITS = ('tracking', 'global')
INJECTIONS = ('none', 'augmented', 'fixed')
RESAMPLES = ('always', 'neff')
AGGREGATES = ('amcl', 'product')

#: Every trace's per-update columns: ``row`` is the world row of the
#: update; the rest are the estimate, its covariance and its error.
COMMON_COLUMNS = ('row', 't', 'est_x', 'est_y', 'est_yaw', 'cov_xx',
                  'cov_xy', 'cov_yy', 'cov_yaw', 'err_xy', 'err_yaw')
FILTER_COLUMNS = {
    'mcl': ('n_eff', 'resampled', 'injected', 'p_inject', 'w_avg',
            'w_slow', 'w_fast', 'cluster_weight'),
    'ekf': ('beams_used', 'beams_gated', 'nis'),
}
INT_COLUMNS = ('row', 'resampled', 'injected', 'beams_used', 'beams_gated')
PARTICLE_COLUMNS = ('x', 'y', 'yaw', 'w')

#: The convergence/recovery definition every summary uses, and the real
#: stack's kidnap A/B uses too: the estimate within 0.5 m and 0.3 rad of
#: the truth, holding for this many consecutive updates.
OK_XY = 0.5
OK_YAW = 0.3
OK_HOLD = 5


class LocError(ValueError):
    """Bad parameters, or a trace that does not conform to the schema."""


@dataclass
class MCLParams:
    """Monte Carlo localisation's knobs. Defaults follow COCO's AMCL."""

    particles: int = 300
    #: the filter's motion model; the world's noise is separate
    alphas: Tuple[float, float, float, float] = (0.02, 0.02, 0.02, 0.02)
    sigma_hit: float = 0.2
    z_hit: float = 0.5
    z_rand: float = 0.5
    max_dist: float = 2.0
    beams: int = 30
    init: str = 'tracking'
    init_sigma: Tuple[float, float, float] = (0.25, 0.25, 0.2)
    injection: str = 'none'
    alpha_slow: float = 0.001
    alpha_fast: float = 0.1
    inject_fraction: float = 0.05
    resample: str = 'always'
    #: ``amcl``: nav2_amcl's score, 1 + sum of cubed per-beam terms;
    #: ``product``: the textbook product of per-beam likelihoods
    aggregate: str = 'amcl'
    seed: int = 0

    def check(self) -> None:
        """Raise :class:`LocError` for values the filter cannot use."""
        if self.aggregate not in AGGREGATES:
            raise LocError(f'aggregate must be one of {AGGREGATES}')
        if not (1 <= self.particles <= 5000):
            raise LocError(f'particles must be 1..5000, not {self.particles}')
        if len(self.alphas) != 4 or any(a < 0 for a in self.alphas):
            raise LocError(f'alphas must be four values >= 0: {self.alphas}')
        if not (self.sigma_hit > 0 and self.max_dist > 0):
            raise LocError('sigma_hit and max_dist must be > 0')
        if not (self.z_hit >= 0 and self.z_rand > 0):
            raise LocError('z_hit must be >= 0 and z_rand > 0')
        if not (1 <= self.beams <= 480):
            raise LocError(f'beams must be 1..480, not {self.beams}')
        if self.init not in INITS:
            raise LocError(f'init must be one of {INITS}')
        if self.injection not in INJECTIONS:
            raise LocError(f'injection must be one of {INJECTIONS}')
        if self.resample not in RESAMPLES:
            raise LocError(f'resample must be one of {RESAMPLES}')
        if not (0 <= self.alpha_slow <= 1 and 0 <= self.alpha_fast <= 1):
            raise LocError('alpha_slow and alpha_fast must be in [0, 1]')
        if not (0 <= self.inject_fraction <= 1):
            raise LocError('inject_fraction must be in [0, 1]')

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        d = asdict(self)
        d['alphas'] = list(self.alphas)
        d['init_sigma'] = list(self.init_sigma)
        return d


@dataclass
class EKFParams:
    """EKF localisation's knobs."""

    alphas: Tuple[float, float, float, float] = (0.02, 0.02, 0.02, 0.02)
    sigma_hit: float = 0.2
    beams: int = 16
    init: str = 'tracking'
    init_sigma: Tuple[float, float, float] = (0.25, 0.25, 0.2)
    #: chi-square(1) bound on a beam's normalised innovation squared;
    #: 9.0 is three standard deviations
    gate: float = 9.0
    #: central-difference steps for the Jacobian: metres, metres, radians
    fd_step: Tuple[float, float, float] = (0.02, 0.02, 0.01)

    def check(self) -> None:
        """Raise :class:`LocError` for values the filter cannot use."""
        if len(self.alphas) != 4 or any(a < 0 for a in self.alphas):
            raise LocError(f'alphas must be four values >= 0: {self.alphas}')
        if not self.sigma_hit > 0:
            raise LocError('sigma_hit must be > 0')
        if not (1 <= self.beams <= 480):
            raise LocError(f'beams must be 1..480, not {self.beams}')
        if self.init not in INITS:
            raise LocError(f'init must be one of {INITS}')
        if not self.gate > 0 or any(s <= 0 for s in self.fd_step):
            raise LocError('gate and fd_step must be > 0')

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        d = asdict(self)
        for k in ('alphas', 'init_sigma', 'fd_step'):
            d[k] = list(d[k])
        return d


@dataclass
class LocTrace:
    """One filter's run: header, per-update columns, particles, summary."""

    header: Dict[str, object]
    columns: Dict[str, List]
    summary: Dict[str, object]
    #: MCL only: ``offset`` (n_updates + 1) and the PARTICLE_COLUMNS
    particles: Optional[Dict[str, List]] = None

    @property
    def kind(self) -> str:
        """Return ``'mcl'`` or ``'ekf'``."""
        return self.header['filter']

    def column_names(self) -> Tuple[str, ...]:
        """Return the per-update column names for this trace's filter."""
        return COMMON_COLUMNS + FILTER_COLUMNS[self.kind]

    def __len__(self) -> int:
        """Return the number of updates."""
        return len(self.columns['row'])

    def validate(self) -> None:
        """Raise :class:`LocError` unless the trace conforms to 1.x."""
        h = self.header
        if h.get('schema') != SCHEMA:
            raise LocError(f'schema is {h.get("schema")!r}, not {SCHEMA!r}')
        try:
            major = int(str(h.get('version', '')).split('.')[0])
        except ValueError:
            raise LocError(f'bad version {h.get("version")!r}') from None
        if major != MAJOR:
            raise LocError(f'loc trace major version {major} is not '
                           f'supported (this reader speaks {MAJOR}.x)')
        if h.get('filter') not in FILTERS:
            raise LocError(f'filter {h.get("filter")!r} not in {FILTERS}')
        names = self.column_names()
        if set(self.columns) != set(names):
            raise LocError(f'columns {sorted(self.columns)} are not '
                           f'{sorted(names)}')
        n = len(self.columns['row'])
        for name in names:
            col = self.columns[name]
            if len(col) != n:
                raise LocError(f'column {name!r} has {len(col)} rows, '
                               f'expected {n}')
            if name in INT_COLUMNS:
                if not all(isinstance(v, int) for v in col):
                    raise LocError(f'column {name!r} must be integers')
            elif not all(isinstance(v, (int, float)) and math.isfinite(v)
                         for v in col):
                raise LocError(f'column {name!r} must be finite numbers')
        rows = self.columns['row']
        if any(b <= a for a, b in zip(rows, rows[1:])):
            raise LocError('rows must strictly increase')
        if self.kind == 'mcl':
            p = self.particles
            if p is None:
                raise LocError('an MCL trace carries its particles')
            off = p['offset']
            if len(off) != n + 1 or off[0] != 0:
                raise LocError('particle offsets must be n_updates + 1, '
                               'starting at 0')
            if any(b < a for a, b in zip(off, off[1:])):
                raise LocError('particle offsets must not decrease')
            for name in PARTICLE_COLUMNS:
                if len(p[name]) != off[-1]:
                    raise LocError(f'particle column {name!r} has '
                                   f'{len(p[name])} values, expected '
                                   f'{off[-1]}')
            w = p['w']
            for k in range(n):
                s = sum(w[off[k]:off[k + 1]])
                if off[k + 1] > off[k] and abs(s - 1.0) > 1e-3:
                    raise LocError(f'update {k}: particle weights sum to '
                                   f'{s}, not 1')
        elif self.particles is not None:
            raise LocError('only an MCL trace carries particles')


# -- helpers ----------------------------------------------------------------

def _beam_subset(n_scan: int, k: int) -> List[int]:
    """``k`` beam indices spread evenly over ``n_scan``, first and last in."""
    if k >= n_scan:
        return list(range(n_scan))
    if k == 1:
        return [n_scan // 2]
    return sorted({round(i * (n_scan - 1) / (k - 1)) for i in range(k)})


def _sensor_pose(pose, mount):
    x, y, th = pose
    mx, my, myaw = mount
    c, s = math.cos(th), math.sin(th)
    return x + c * mx - s * my, y + s * mx + c * my, th + myaw


def _error(est, gt) -> Tuple[float, float]:
    return (math.hypot(est[0] - gt[0], est[1] - gt[1]),
            abs(wrap(est[2] - gt[2])))


class _Inputs:
    """What a filter may see of a WorldRun: no truth."""

    def __init__(self, world: WorldRun):
        sc = world.scenario
        self.lidar = sc.lidar
        self.angles = sc.lidar.angles()
        self.rows = list(world.updates)
        self.t = [world.t[r] for r in world.updates]
        self.odom = [world.odom[r] for r in world.updates]
        self.ranges = world.ranges
        self.start = sc.start  # given to a tracking start, like /initialpose


def _random_free_pose(free, smap: SketchMap, rng: random.Random):
    ix, iy = free[rng.randrange(len(free))]
    r = smap.resolution
    x = smap.origin[0] + (ix + rng.random()) * r
    y = smap.origin[1] + (iy + rng.random()) * r
    return (x, y, wrap(rng.uniform(-math.pi, math.pi)))


def summarise(trace_cols: Dict[str, List], world: WorldRun) -> Dict[str, object]:
    """
    Score a trace against the truth.

    ``converged_s``: sim time of the first update from which the estimate
    holds within ``OK_XY`` / ``OK_YAW`` for ``OK_HOLD`` updates, before
    any kidnap. ``recovered`` / ``recovery_s``: the same after the kidnap,
    measured from the kidnap. ``None`` where it does not apply.
    """
    exy = trace_cols['err_xy']
    eyaw = trace_cols['err_yaw']
    rows = trace_cols['row']
    t = trace_cols['t']
    n = len(rows)
    ok = [exy[i] < OK_XY and eyaw[i] < OK_YAW for i in range(n)]

    def first_hold(lo, hi):
        for i in range(lo, hi):
            j = min(i + OK_HOLD, hi)
            if j - i == OK_HOLD and all(ok[i:j]):
                return i
        return None

    krow = world.kidnap_row
    kidx = n if krow is None else next(
        (i for i in range(n) if rows[i] >= krow), n)
    c = first_hold(0, kidx)
    out = {
        'n_updates': n,
        'mean_err_xy': sum(exy) / n if n else None,
        'max_err_xy': max(exy) if n else None,
        'final_err_xy': exy[-1] if n else None,
        'final_err_yaw': eyaw[-1] if n else None,
        'converged_s': None if c is None else t[c],
        'kidnap_s': None if krow is None else world.t[krow],
        'recovered': None,
        'recovery_s': None,
        'ok_xy': OK_XY, 'ok_yaw': OK_YAW, 'ok_hold': OK_HOLD,
    }
    if krow is not None:
        r = first_hold(kidx, n)
        out['recovered'] = r is not None
        out['recovery_s'] = None if r is None else t[r] - world.t[krow]
    return out


def _header(kind: str, params: Dict[str, object], world: WorldRun):
    return {'schema': SCHEMA, 'version': VERSION, 'filter': kind,
            'params': params, 'n_beams_scan': world.scenario.lidar.samples}


# -- MCL --------------------------------------------------------------------

class LikelihoodField:
    """AMCL's likelihood-field log score, tabulated per map cell."""

    def __init__(self, smap: SketchMap, sigma_hit: float, z_hit: float,
                 z_rand: float, max_dist: float, range_max: float):
        """Tabulate ``pz = z_hit exp(-d^2/2s^2) + z_rand/range_max``."""
        self.smap = smap
        floor = z_rand / range_max
        k = 1.0 / (2.0 * sigma_hit * sigma_hit)
        self.pz = [z_hit * math.exp(-min(d, max_dist) ** 2 * k) + floor
                   for d in smap.dist]
        self.pz_off = z_hit * math.exp(-max_dist ** 2 * k) + floor
        #: AMCL's per-beam term, cubed (its sum is AMCL's score)
        self.cube = [v * v * v for v in self.pz]
        self.cube_off = self.pz_off ** 3
        #: the textbook product's per-beam term, as a log
        self.log = [math.log(v) for v in self.pz]
        self.log_off = math.log(self.pz_off)


def run_mcl(smap: SketchMap, world: WorldRun, params: MCLParams) -> LocTrace:
    """Run Monte Carlo localisation over ``world``'s inputs; trace it."""
    params.check()
    inp = _Inputs(world)
    rng = random.Random(params.seed)
    lidar = inp.lidar
    beams = _beam_subset(lidar.samples, params.beams)
    b_cos = [math.cos(inp.angles[b] + lidar.mount[2]) for b in beams]
    b_sin = [math.sin(inp.angles[b] + lidar.mount[2]) for b in beams]
    mx, my = lidar.mount[0], lidar.mount[1]
    lf = LikelihoodField(smap, params.sigma_hit, params.z_hit, params.z_rand,
                         params.max_dist, lidar.range_max)
    amcl = params.aggregate == 'amcl'
    table, off_map = (lf.cube, lf.cube_off) if amcl else (lf.log, lf.log_off)
    ox, oy = smap.origin
    inv_r = 1.0 / smap.resolution
    W, H = smap.width, smap.height
    free = smap.free_cells(margin=ROBOT_RADIUS * 0.5)
    if not free:
        raise LocError('the map has no free cell to put a particle in')
    N = params.particles

    if params.init == 'tracking':
        sx, sy, sth = params.init_sigma
        x0, y0, th0 = inp.start
        P = [(x0 + rng.gauss(0, sx), y0 + rng.gauss(0, sy),
              wrap(th0 + rng.gauss(0, sth))) for _ in range(N)]
    else:
        P = [_random_free_pose(free, smap, rng) for _ in range(N)]

    cols = {name: [] for name in COMMON_COLUMNS + FILTER_COLUMNS['mcl']}
    parts = {'offset': [0], 'x': [], 'y': [], 'yaw': [], 'w': []}
    w_slow = w_fast = 0.0
    w = [1.0 / N] * N  # normalised; uniform after every resample
    a1, a2, a3, a4 = params.alphas
    gt_rows = world.gt
    prev_odom = inp.odom[0]
    for k in range(len(inp.rows)):
        # -- motion: sample the odometry model per particle
        if k > 0:
            rot1, trans, rot2 = odom_delta(prev_odom, inp.odom[k])
            prev_odom = inp.odom[k]
            r1n = min(abs(rot1), abs(math.pi - abs(rot1)))
            r2n = min(abs(rot2), abs(math.pi - abs(rot2)))
            s1 = math.sqrt(a1 * r1n * r1n + a2 * trans * trans)
            st = math.sqrt(a3 * trans * trans + a4 * (r1n * r1n + r2n * r2n))
            s2 = math.sqrt(a1 * r2n * r2n + a2 * trans * trans)
            gauss = rng.gauss
            moved = []
            for (x, y, th) in P:
                r1 = rot1 - gauss(0.0, 1.0) * s1
                tr = trans - gauss(0.0, 1.0) * st
                r2 = rot2 - gauss(0.0, 1.0) * s2
                h = th + r1
                moved.append((x + tr * math.cos(h), y + tr * math.sin(h),
                              wrap(h + r2)))
            P = moved

        # -- measurement: the likelihood field
        z = inp.ranges[k]
        used = [(z[b], b_cos[i], b_sin[i]) for i, b in enumerate(beams)
                if z[b] != INF]
        n_used = len(used)
        score = []
        for (x, y, th) in P:
            c, s = math.cos(th), math.sin(th)
            sx_ = x + c * mx - s * my
            sy_ = y + s * mx + c * my
            acc = 0.0
            for (r, bc, bs) in used:
                ex = sx_ + r * (c * bc - s * bs)
                ey = sy_ + r * (s * bc + c * bs)
                fx = (ex - ox) * inv_r
                fy = (ey - oy) * inv_r
                if fx < 0 or fy < 0:
                    acc += off_map
                    continue
                ix = int(fx)
                iy = int(fy)
                if ix >= W or iy >= H:
                    acc += off_map
                else:
                    acc += table[iy * W + ix]
            score.append(acc)
        if n_used and amcl:
            # nav2_amcl likelihood_field_model.cpp: p = 1 + sum(pz^3),
            # weight *= p; pf.c: w_avg is the mean UNnormalised weight
            u = [wi * (1.0 + sc) for wi, sc in zip(w, score)]
            tot = sum(u)
            w_avg = tot / N
            w = [v / tot for v in u]
        elif n_used:
            # the textbook product, in logs: log w += sum(log pz)
            logu = [math.log(wi) + sc if wi > 0 else -math.inf
                    for wi, sc in zip(w, score)]
            mlog = max(logu)
            u = [math.exp(v - mlog) for v in logu]
            tot = sum(u)
            w = [v / tot for v in u]
            # a product of n beams underflows: its running average uses
            # the per-beam (geometric-mean) likelihood instead
            w_avg = sum(math.exp(sc / n_used) for sc in score) / N
        else:
            w_avg = 0.0
        n_eff = 1.0 / sum(v * v for v in w)

        # -- estimate: the heaviest cluster's weighted mean
        est, cov, cw = _cluster_estimate(P, w)
        gt = gt_rows[inp.rows[k]]
        exy, eyaw = _error(est, gt)
        for name, val in (('row', inp.rows[k]), ('t', inp.t[k]),
                          ('est_x', est[0]), ('est_y', est[1]),
                          ('est_yaw', est[2]), ('cov_xx', cov[0]),
                          ('cov_xy', cov[1]), ('cov_yy', cov[2]),
                          ('cov_yaw', cov[3]), ('err_xy', exy),
                          ('err_yaw', eyaw), ('n_eff', n_eff),
                          ('cluster_weight', cw)):
            cols[name].append(val)
        for (x, y, th), wi in zip(P, w):
            parts['x'].append(x)
            parts['y'].append(y)
            parts['yaw'].append(th)
            parts['w'].append(wi)
        parts['offset'].append(len(parts['x']))

        # -- injection bookkeeping (augmented MCL)
        p_inject = 0.0
        if n_used and params.injection == 'augmented':
            # nav2_amcl pf.c (jazzy) seeds each average with the first
            # w_avg rather than starting it at 0; from 0, alpha_slow =
            # 0.001 would keep w_fast / w_slow >> 1 for thousands of
            # updates and nothing would ever be injected (measured here
            # before this line existed: 0 injections after a kidnap)
            if w_slow == 0.0:
                w_slow = w_avg
            else:
                w_slow += params.alpha_slow * (w_avg - w_slow)
            if w_fast == 0.0:
                w_fast = w_avg
            else:
                w_fast += params.alpha_fast * (w_avg - w_fast)
            if w_slow > 0:
                p_inject = max(0.0, 1.0 - w_fast / w_slow)
        elif n_used and params.injection == 'fixed':
            p_inject = params.inject_fraction

        # -- resampling: low variance
        do = n_used > 0 and (params.resample == 'always'
                             or n_eff < N / 2.0)
        injected = 0
        if do:
            idx = low_variance_resample(w, rng.random())
            newP = []
            for i in idx:
                if p_inject > 0.0 and rng.random() < p_inject:
                    newP.append(_random_free_pose(free, smap, rng))
                    injected += 1
                else:
                    newP.append(P[i])
            P = newP
            w = [1.0 / N] * N
        cols['resampled'].append(1 if do else 0)
        cols['injected'].append(injected)
        cols['p_inject'].append(p_inject)
        cols['w_avg'].append(w_avg)
        cols['w_slow'].append(w_slow)
        cols['w_fast'].append(w_fast)

    trace = LocTrace(_header('mcl', params.to_dict(), world), cols,
                     summarise(cols, world), parts)
    trace.validate()
    return trace


def low_variance_resample(w: Sequence[float], u: float) -> List[int]:
    """
    Return the indices low-variance (systematic) resampling picks.

    ``w`` are normalised weights, ``u`` one uniform draw in ``[0, 1)``.
    One comb of ``N`` evenly spaced teeth, offset by ``u / N``, is laid
    over the cumulative weights (*Probabilistic Robotics* table 4.4). Its
    defining property, tested: particle ``i`` is copied either
    ``floor(N w_i)`` or ``ceil(N w_i)`` times -- never more, never fewer --
    so resampling adds no variance a weighting did not already have.
    """
    n = len(w)
    step = 1.0 / n
    target = u * step
    c = w[0]
    i = 0
    out = []
    for _ in range(n):
        while target > c and i < n - 1:
            i += 1
            c += w[i]
        out.append(i)
        target += step
    return out


def _cluster_estimate(P, w):
    """
    Return the heaviest cluster's weighted mean, covariance and weight.

    Particles are binned on a 0.5 m grid; the heaviest bin's weighted
    centre seeds the cluster, which is every particle within 1.0 m of it.
    The mean of a multimodal cloud is a point nobody believes in; this is
    the estimate AMCL would report (its pose is its heaviest cluster's).
    """
    bins: Dict[Tuple[int, int], List[float]] = {}
    for (x, y, _), wi in zip(P, w):
        key = (math.floor(x / 0.5), math.floor(y / 0.5))
        b = bins.get(key)
        if b is None:
            bins[key] = [wi, wi * x, wi * y]
        else:
            b[0] += wi
            b[1] += wi * x
            b[2] += wi * y
    best = max(bins.values(), key=lambda b: b[0])
    cx, cy = best[1] / best[0], best[2] / best[0]
    sw = sx = sy = ss = sc = 0.0
    members = []
    for (x, y, th), wi in zip(P, w):
        if (x - cx) ** 2 + (y - cy) ** 2 <= 1.0:
            members.append((x, y, th, wi))
            sw += wi
            sx += wi * x
            sy += wi * y
            ss += wi * math.sin(th)
            sc += wi * math.cos(th)
    mx, my = sx / sw, sy / sw
    myaw = math.atan2(ss, sc)
    cxx = cxy = cyy = cyaw = 0.0
    for x, y, th, wi in members:
        dx, dy, da = x - mx, y - my, wrap(th - myaw)
        cxx += wi * dx * dx
        cxy += wi * dx * dy
        cyy += wi * dy * dy
        cyaw += wi * da * da
    return ((mx, my, myaw), (cxx / sw, cxy / sw, cyy / sw, cyaw / sw), sw)


# -- EKF --------------------------------------------------------------------

def _motion_jacobians(mu, rot1, trans, rot2, alphas):
    th = mu[2] + rot1
    c, s = math.cos(th), math.sin(th)
    G = [[1.0, 0.0, -trans * s], [0.0, 1.0, trans * c], [0.0, 0.0, 1.0]]
    V = [[-trans * s, c, 0.0], [trans * c, s, 0.0], [1.0, 0.0, 1.0]]
    a1, a2, a3, a4 = alphas
    r1n = min(abs(rot1), abs(math.pi - abs(rot1)))
    r2n = min(abs(rot2), abs(math.pi - abs(rot2)))
    M = [[a1 * r1n * r1n + a2 * trans * trans, 0.0, 0.0],
         [0.0, a3 * trans * trans + a4 * (r1n * r1n + r2n * r2n), 0.0],
         [0.0, 0.0, a1 * r2n * r2n + a2 * trans * trans]]
    Q = kalman.matmul(kalman.matmul(V, M), kalman.transpose(V))
    for i in range(3):
        Q[i][i] += 1e-9  # keeps P positive definite on a zero move
    return G, Q


def run_ekf(smap: SketchMap, world: WorldRun, params: EKFParams) -> LocTrace:
    """Run EKF localisation over ``world``'s inputs; trace it."""
    params.check()
    inp = _Inputs(world)
    lidar = inp.lidar
    beams = _beam_subset(lidar.samples, params.beams)
    rmax = lidar.range_max
    R1 = params.sigma_hit ** 2

    def expected(pose, b):
        sx, sy, sth = _sensor_pose(pose, lidar.mount)
        return smap.cast(sx, sy, sth + inp.angles[b], rmax)

    if params.init == 'tracking':
        mu = list(inp.start)
        s = params.init_sigma
        P = [[s[0] ** 2, 0.0, 0.0], [0.0, s[1] ** 2, 0.0],
             [0.0, 0.0, s[2] ** 2]]
    else:
        # an EKF must start somewhere: the middle of the free space,
        # facing +x, with a covariance as wide as the map
        free = smap.free_cells(margin=ROBOT_RADIUS * 0.5)
        cx = sum(smap.cell_centre(*c)[0] for c in free) / len(free)
        cy = sum(smap.cell_centre(*c)[1] for c in free) / len(free)
        mu = [cx, cy, 0.0]
        span = max(smap.width, smap.height) * smap.resolution / 2
        P = [[span ** 2, 0.0, 0.0], [0.0, span ** 2, 0.0],
             [0.0, 0.0, math.pi ** 2]]

    cols = {name: [] for name in COMMON_COLUMNS + FILTER_COLUMNS['ekf']}
    prev_odom = inp.odom[0]
    for k in range(len(inp.rows)):
        if k > 0:
            rot1, trans, rot2 = odom_delta(prev_odom, inp.odom[k])
            prev_odom = inp.odom[k]
            G, Q = _motion_jacobians(mu, rot1, trans, rot2, params.alphas)
            mu, P = kalman.predict(
                mu, P, lambda m: list(apply_delta(m, rot1, trans, rot2)),
                G, Q)
        z = inp.ranges[k]
        rows_H, zs, zhats = [], [], []
        gated = 0
        nis_sum = 0.0
        pose = tuple(mu)
        for b in beams:
            if z[b] == INF:
                continue
            zh = expected(pose, b)
            if zh == INF:
                continue
            Hrow = []
            okj = True
            for j in range(3):
                d = params.fd_step[j]
                plus = list(pose)
                minus = list(pose)
                plus[j] += d
                minus[j] -= d
                zp = expected(tuple(plus), b)
                zm = expected(tuple(minus), b)
                if zp == INF or zm == INF:
                    okj = False
                    break
                Hrow.append((zp - zm) / (2 * d))
            if not okj:
                continue
            S = sum(Hrow[i] * sum(P[i][j] * Hrow[j] for j in range(3))
                    for i in range(3)) + R1
            nu = z[b] - zh
            nis = nu * nu / S
            if nis > params.gate:
                gated += 1
                continue
            nis_sum += nis
            rows_H.append(Hrow)
            zs.append(z[b])
            zhats.append(zh)
        if rows_H:
            m = len(rows_H)
            R = [[R1 if i == j else 0.0 for j in range(m)] for i in range(m)]
            mu, P, _, _ = kalman.update(mu, P, zs, zhats, rows_H, R)
            mu[2] = wrap(mu[2])
        est = (mu[0], mu[1], mu[2])
        gt = world.gt[inp.rows[k]]
        exy, eyaw = _error(est, gt)
        for name, val in (('row', inp.rows[k]), ('t', inp.t[k]),
                          ('est_x', est[0]), ('est_y', est[1]),
                          ('est_yaw', est[2]), ('cov_xx', P[0][0]),
                          ('cov_xy', P[0][1]), ('cov_yy', P[1][1]),
                          ('cov_yaw', P[2][2]), ('err_xy', exy),
                          ('err_yaw', eyaw), ('beams_used', len(rows_H)),
                          ('beams_gated', gated),
                          ('nis', nis_sum / len(rows_H) if rows_H else 0.0)):
            cols[name].append(val)
    trace = LocTrace(_header('ekf', params.to_dict(), world), cols,
                     summarise(cols, world))
    trace.validate()
    return trace
