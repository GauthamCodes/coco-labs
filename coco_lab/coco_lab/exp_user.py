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
Running an algorithm through the API (R2; ADR 0013; MODEL): user code and wrapped built-ins.

An *algorithm* here is anything with ``kind`` (``planner``, ``controller``,
``localiser``) and ``call(ctx, *args)``: a file loaded by :mod:`coco_lab.user_code`
or one of :mod:`coco_lab.api_builtins`' wrappers of the reference algorithms. Both
are measured by the same code below, so a wrapped built-in reproduces the native
built-in's metrics exactly (``test/test_api_equivalence.py``).

- **planning** (:func:`coco_lab.exp_families.run_user_planning`): the same costmap as the native
  planning
  family (static + inflation layers), handed over as a ``nav2_msgs/Costmap``; the
  start and goal are the centres of the snapped cells, as the built-ins get them.
  The returned poses are measured at the centres of the cells they fall in: length
  ``sum(hypot(d_row, d_col)) * resolution``, cost the grid's edge costs along an
  8-connected path (none for an any-angle path), clearance over every cell the path
  crosses. A path off the map, not starting in the start cell or ending in the goal
  cell is a contract error; one through a lethal or inscribed cell is a collision.
- **control** and **localisation** run in the Arena: ``move.controller=user`` and
  ``localise.filter=user`` hand the tick to :func:`control_cycle` and
  :func:`localise_tick`; everything around them (the goal and progress checkers,
  the driver, the error sampling) is the native families' own.

Run chains (``coco.experiment.run.v1``) hash the descriptor, then every thinking
event and the path (planning) or every tick's state hash (Arena), then the counts:
a different algorithm is a different chain by design. Wall time (``compute_ms``, the
per-call times) never enters a chain.
"""

from time import perf_counter
from typing import Dict, List, Optional
import weakref

from . import api, loc_arena, move_arena
from .numerics import math

#: steps a call may count with ``ctx.step()`` (0: unlimited); per family
BUDGETS = {'planner': 20_000_000, 'controller': 200_000, 'localiser': 2_000_000}
#: contract problems kept per run (the rest are counted)
MAX_PROBLEMS = 20

# -- the code registry ----------------------------------------------------------------------------

_CODE: Dict[str, str] = {}


def register(source: str) -> str:
    """Remember a file's source under its sha256 (a spec names it so); return the sha256."""
    from .user_code import code_sha256
    sha = code_sha256(source)
    _CODE[sha] = source
    return sha


def source(sha: str) -> str:
    """Return a registered file's source."""
    try:
        return _CODE[sha]
    except KeyError:
        raise ValueError(f'no algorithm file with sha256 {sha[:12]}... was given') from None


def load(sha: str):
    """Load a registered file afresh (module-level state never crosses runs)."""
    if sha.startswith('builtin:'):
        from . import api_builtins
        return api_builtins.algorithm(sha.partition(':')[2])
    from .user_code import load as load_file
    return load_file(source(sha))


# -- a run's report -------------------------------------------------------------------------------

class Report:
    """What the validation report shows for one run (never part of a chain)."""

    def __init__(self):
        """Empty."""
        self.problems: List[Dict] = []
        self.n_problems = 0
        self.clamped = 0
        self.clamp_examples: List[str] = []
        self.calls = 0
        self.call_ms_max = 0.0
        self.call_ms_total = 0.0
        self.max_call_index = -1
        self.dropped_events = 0
        self.error: Optional[Dict] = None
        self.console = ''

    def problem(self, message: str, tick: Optional[int] = None) -> None:
        """Record a contract problem."""
        self.n_problems += 1
        if len(self.problems) < MAX_PROBLEMS:
            self.problems.append({'message': message, 'tick': tick})

    def clamp(self, message: str) -> None:
        """Record an output the runner clamped."""
        self.clamped += 1
        if len(self.clamp_examples) < MAX_PROBLEMS:
            self.clamp_examples.append(message)

    def timed(self, ms: float) -> None:
        """Count one call of ``ms`` milliseconds (wall time, this device)."""
        if ms > self.call_ms_max:
            self.call_ms_max, self.max_call_index = ms, self.calls
        self.calls += 1
        self.call_ms_total += ms

    def to_dict(self) -> Dict:
        """Return the report as plain data."""
        return {'problems': self.problems, 'n_problems': self.n_problems,
                'clamped': self.clamped, 'clamp_examples': self.clamp_examples,
                'calls': self.calls, 'call_ms_max': self.call_ms_max,
                'call_ms_total': self.call_ms_total, 'max_call_index': self.max_call_index,
                'dropped_events': self.dropped_events, 'error': self.error,
                'console': self.console}


#: called with each call's wall time (ms) after every call of user code: the browser's
#: user-code worker posts a heartbeat from it (its time limit counts the silence between)
ON_CALL = None
#: candidates (and points per candidate) a controller call keeps in the Arena's state
MAX_CANDIDATES = 64
MAX_CANDIDATE_POINTS = 64


class FatalUserError(Exception):
    """User code broke the contract or raised: the run ends with status ``error``."""


def _call(alg, report: Report, ctx: api.Context, *args):
    """Call ``alg`` once, timing it; user exceptions become FatalUserError (with the report)."""
    from .user_code import describe_error
    ctx.events = []
    ctx.steps = 0
    t0 = perf_counter()
    try:
        out = alg.call(ctx, *args)
    except (api.NoValidControl, api.InvalidPath):
        report.timed((perf_counter() - t0) * 1000)
        report.dropped_events += ctx.dropped
        ctx.dropped = 0
        raise
    except Exception as e:  # the file's own exception: reported, never re-raised raw
        report.timed((perf_counter() - t0) * 1000)
        report.error = describe_error(e, getattr(alg, 'filename', 'algorithm.py'))
        raise FatalUserError(f'{type(e).__name__}: {e}') from None
    ms = (perf_counter() - t0) * 1000
    report.timed(ms)
    report.dropped_events += ctx.dropped
    ctx.dropped = 0
    if ON_CALL is not None:
        ON_CALL(ms)
    return out


def _finish_report(alg, report: Report) -> Dict:
    console = getattr(alg, 'console', None)
    if console is not None:
        report.console = console.text()
    return report.to_dict()


def _plain(v, depth=0):
    """Return an event value as canonical-JSON-able plain data (numbers, text, lists)."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (list, tuple)) and depth < 3:
        if len(v) > 100_000:
            raise ValueError('ctx.emit: a list of more than 100000 items')
        return [_plain(x, depth + 1) for x in v]
    if hasattr(v, 'x') and hasattr(v, 'y') and depth < 3:
        return [_plain(float(v.x), depth + 1), _plain(float(v.y), depth + 1)]
    return _plain(float(v), depth)


# -- ROS-shaped inputs from the model -------------------------------------------------------------

_COSTMAPS: Dict = {}
_GRIDS: Dict = {}


def robot_of(spec: Dict) -> api.Robot:
    """Return COCO's Robot from a World Spec."""
    return api.Robot.from_spec(spec['robot'])


def costmap_of(lab_map, layers) -> api.Costmap:
    """Return ``layers.combined`` as a nav2_msgs/Costmap (rows from the origin up; immutable)."""
    key = id(layers)
    hit = _COSTMAPS.get(key)
    if hit is not None and hit[0] is layers:
        return hit[1]
    w, h = lab_map.width, lab_map.height
    comb = layers.combined
    data = []
    for my in range(h):
        row = h - 1 - my
        data.extend(comb[row * w:(row + 1) * w])
    md = api.CostmapMetaData(resolution=lab_map.resolution, size_x=w, size_y=h,
                             origin=api.Pose.from_2d(lab_map.origin[0], lab_map.origin[1]))
    cm = api.Costmap(api.Header(frame_id='map'), md, tuple(int(v) for v in data))
    if len(_COSTMAPS) > 8:
        _COSTMAPS.clear()
    _COSTMAPS[key] = (layers, cm)
    return cm


def occupancy_of(lab_map) -> api.OccupancyGrid:
    """Return the world's map as a nav_msgs/OccupancyGrid (0 free, 100 occupied, -1 unknown)."""
    from .maps import FREE, OCCUPIED
    key = id(lab_map)
    hit = _GRIDS.get(key)
    if hit is not None and hit[0] is lab_map:
        return hit[1]
    w, h = lab_map.width, lab_map.height
    occ = lab_map.occupancy
    data = []
    for my in range(h):
        row = h - 1 - my
        data.extend(api.GRID_FREE if v == FREE else
                    api.GRID_OCCUPIED if v == OCCUPIED else api.GRID_UNKNOWN
                    for v in occ[row * w:(row + 1) * w])
    info = api.MapMetaData(resolution=lab_map.resolution, width=w, height=h,
                           origin=api.Pose.from_2d(lab_map.origin[0], lab_map.origin[1]))
    g = api.OccupancyGrid(api.Header(frame_id='map'), info, tuple(data))
    if len(_GRIDS) > 8:
        _GRIDS.clear()
    _GRIDS[key] = (lab_map, g)
    return g


def laser_scan_of(arena) -> api.LaserScan:
    """Return the Arena's current scan as a sensor_msgs/LaserScan (lidar_link frame)."""
    li = arena.lidar
    n = li.samples
    inc = (li.angle_max - li.angle_min) / (n - 1) if n > 1 else 0.0
    return api.LaserScan(api.Header(api.Time.from_sec(arena.t_world), 'lidar_link'),
                         li.angle_min, li.angle_max, inc, 0.0, arena.dt, li.range_min,
                         li.range_max, tuple(arena.ranges))


def odometry_of(arena) -> api.Odometry:
    """Return the Arena's wheel odometry as a nav_msgs/Odometry (odom frame)."""
    x, y, th = arena.odom
    return api.Odometry(api.Header(api.Time.from_sec(arena.t_world), 'odom'), 'base_footprint',
                        api.PoseWithCovariance(api.Pose.from_2d(x, y, th)),
                        api.TwistWithCovariance(api.Twist.of(arena.v, arena.w)))


def _config(params: Dict) -> Dict:
    """Return the family's own parameters (everything but ``user.*``)."""
    return {k: v for k, v in params.items() if not k.startswith('user.')}


# -- the Arena: who runs there --------------------------------------------------------------------

class Runtime:
    """An algorithm attached to one Arena: its context, report and display hook."""

    def __init__(self, arena, alg, kind: str, params: Dict, seed_rng):
        """``seed_rng``: the subsystem's own stream (the native filter would draw from it)."""
        self.alg, self.kind = alg, kind
        self.report = Report()
        self.ctx = api.Context(seed_rng, robot_of(arena.spec),
                               params={k[5:]: v for k, v in params.items()
                                       if k.startswith('user.')},
                               budget=BUDGETS[kind], dt=arena.dt, config=_config(params))
        self.wp_ref = None
        self.path: List[api.Pose2D] = []
        self.fatal: Optional[str] = None
        self.on_event = None
        self.est = None


_ATTACHED: 'weakref.WeakKeyDictionary' = weakref.WeakKeyDictionary()


def attach(arena, alg, params: Optional[Dict] = None, on_event=None) -> None:
    """Hand ``alg`` to ``arena`` (before ``move.controller=user`` or ``localise.filter=user``)."""
    slot = _ATTACHED.setdefault(arena, {})
    slot[alg.kind] = {'alg': alg, 'params': dict(params or {}), 'on_event': on_event,
                      'rt': None}


def runtime(arena, kind: str, rng=None) -> Runtime:
    """Return the Arena's runtime for ``kind`` (created on first use from ``rng``)."""
    slot = _ATTACHED.get(arena, {}).get(kind)
    if slot is None:
        raise ValueError(f'no {kind} algorithm is attached to this Arena')
    if slot['rt'] is None:
        slot['rt'] = Runtime(arena, slot['alg'], kind, slot['params'], rng)
        slot['rt'].on_event = slot['on_event']
    return slot['rt']


def has(arena, kind: str) -> bool:
    """Return whether an algorithm of ``kind`` is attached to ``arena``."""
    return kind in _ATTACHED.get(arena, {})


def finished(arena) -> Dict:
    """Return ``{kind: report}`` for every runtime the Arena used (with the console)."""
    out = {}
    for kind, slot in _ATTACHED.get(arena, {}).items():
        if slot['rt'] is not None:
            out[kind] = _finish_report(slot['alg'], slot['rt'].report)
    return out


def fatal(arena) -> Optional[str]:
    """Return why an attached algorithm ended the run, or None."""
    for slot in _ATTACHED.get(arena, {}).values():
        if slot['rt'] is not None and slot['rt'].fatal:
            return slot['rt'].fatal
    return None


class UserEngine:
    """``move.controller=user``'s engine: plain data only (the v2/v3 hash snapshots it)."""

    kind = 'user'
    critics = ()

    class Params:
        """No parameters of its own (``user.*`` parameters go to ``ctx.params``)."""

        @staticmethod
        def to_dict():
            """Return ``{}``."""
            return {}

    def __init__(self):
        """Nothing to hold."""
        self.params = UserEngine.Params()

    @staticmethod
    def state_values():
        """Return no values for the v1 state bytes."""
        return []


def _events_into(rt: Runtime, tick: int):
    for kind, data in rt.ctx.events:
        if rt.on_event is not None:
            rt.on_event(kind, {k: _plain(v) for k, v in data.items()})


def control_cycle(arena, b, tr, gd, rng):
    """One controller call for ``ArenaMover.command``: return a :class:`control.Cycle`."""
    from .control import Candidate, Cycle
    rt = runtime(arena, 'controller', rng)
    if rt.fatal:
        return Cycle('no_valid')
    if arena.waypoints is not rt.wp_ref:
        rt.wp_ref = arena.waypoints
        pts = [(b[0], b[1])] + [(p[0], p[1]) for p in arena.waypoints]
        path = []
        for i, p in enumerate(pts):
            q = pts[i + 1] if i + 1 < len(pts) else None
            if q is not None and (q[0] != p[0] or q[1] != p[1]):
                th = math.atan2(q[1] - p[1], q[0] - p[0])
            else:
                th = path[-1].theta if path else b[2]
            path.append(api.Pose2D(p[0], p[1], th))
        rt.path = path
    goal_th = tr.goal_yaw if tr.goal_yaw is not None else math.nan
    state = api.RobotState(api.Pose2D(b[0], b[1], b[2]), api.Twist.of(arena.v, arena.w),
                           api.Pose2D(tr.goal[0], tr.goal[1], goal_th),
                           api.Time.from_sec(arena.t_world))
    ctx = rt.ctx
    ctx.time = arena.t_world
    try:
        out = _call(rt.alg, rt.report, ctx, state, laser_scan_of(arena), list(rt.path))
    except api.NoValidControl as e:
        rt.report.problem(f'NoValidControl: {e}', arena.tick)
        return Cycle('no_valid')
    except api.InvalidPath as e:
        rt.report.problem(f'InvalidPath: {e}', arena.tick)
        return Cycle('invalid_path')
    except FatalUserError as e:
        rt.fatal = str(e)
        return Cycle('no_valid')
    cands, look = [], None
    for kind, data in ctx.events:
        if kind == 'candidate' and len(cands) < MAX_CANDIDATES:
            pts = [tuple(p[:2]) for p in _plain(data['points']) if p]
            step = max(1, len(pts) // MAX_CANDIDATE_POINTS)
            cands.append(Candidate(math.nan, math.nan, bool(data['valid']), '',
                                   float(_plain(data['cost']) or 0.0), [], pts[::step]))
        elif kind == 'lookahead':
            look = (float(data['x']), float(data['y']))
    _events_into(rt, arena.tick)
    v, w = _twist(rt, out, arena.tick)
    if rt.fatal:
        return Cycle('no_valid')
    return Cycle('ok', v, w, -1, cands, len(cands), look, sum(1 for c in cands if c.valid))


def _twist(rt: Runtime, out, tick):
    """Validate a Twist; clamp (and log) what COCO cannot do; contract errors are fatal."""
    try:
        lx, ly, lz = float(out.linear.x), float(out.linear.y), float(out.linear.z)
        ax, ay, az = float(out.angular.x), float(out.angular.y), float(out.angular.z)
    except (AttributeError, TypeError, ValueError):
        rt.report.problem(f'control() returned {type(out).__name__}, not a Twist', tick)
        rt.fatal = 'control() did not return a Twist'
        return 0.0, 0.0
    if not all(math.isfinite(v) for v in (lx, ly, lz, ax, ay, az)):
        rt.report.problem('control() returned a Twist that is not finite', tick)
        rt.fatal = 'control() returned a non-finite Twist'
        return 0.0, 0.0
    r = rt.ctx.robot
    if ly or lz or ax or ay:
        rt.report.clamp(f'tick {tick}: linear.y/z and angular.x/y set to 0 '
                        '(COCO is differential drive: no strafing)')
    v, w = lx, az
    if abs(v) > r.max_linear:
        rt.report.clamp(f'tick {tick}: linear.x {v:.4f} clamped to +-{r.max_linear} m/s')
        v = math.copysign(r.max_linear, v)
    if abs(w) > r.max_angular:
        rt.report.clamp(f'tick {tick}: angular.z {w:.4f} clamped to +-{r.max_angular} rad/s')
        w = math.copysign(r.max_angular, w)
    return v, w


def localise_start(arena, start, rng) -> None:
    """``localise.filter=user`` started (or restarted) at ``start``."""
    rt = runtime(arena, 'localiser', rng)
    rt.ctx.initial_pose = api.Pose2D(*start)
    rt.ctx.memory = {}
    rt.est = None


def localise_tick(arena, rng):
    """One localiser call: return ``(est, (cov_xx, cov_yy))`` or None (nothing to say)."""
    rt = runtime(arena, 'localiser', rng)
    if rt.fatal:
        return None
    ctx = rt.ctx
    ctx.time = arena.t_world
    try:
        out = _call(rt.alg, rt.report, ctx, odometry_of(arena), laser_scan_of(arena),
                    occupancy_of(arena.lab_map))
    except (FatalUserError, api.NoValidControl, api.InvalidPath) as e:
        rt.fatal = str(e)
        return None
    _events_into(rt, arena.tick)
    got = _pose_cov(rt, out, arena.tick)
    if got is not None:
        rt.est = got
    return got


def _pose_cov(rt: Runtime, out, tick):
    """Validate a PoseWithCovariance (finite, symmetric, positive semi-definite)."""
    try:
        p = out.pose
        x, y = float(p.position.x), float(p.position.y)
        q = p.orientation
        qs = [float(q.x), float(q.y), float(q.z), float(q.w)]
        cov = [float(v) for v in out.covariance]
    except (AttributeError, TypeError, ValueError):
        rt.report.problem(f'localise() returned {type(out).__name__}, '
                          'not a PoseWithCovariance', tick)
        rt.fatal = 'localise() did not return a PoseWithCovariance'
        return None
    if len(cov) != 36:
        rt.report.problem(f'covariance has {len(cov)} values; 36 (6x6) were due', tick)
        rt.fatal = 'the covariance is not 6x6'
        return None
    if not all(math.isfinite(v) for v in [x, y] + qs + cov):
        rt.report.problem('localise() returned values that are not finite', tick)
        rt.fatal = 'localise() returned a non-finite estimate'
        return None
    n = math.sqrt(math.fsum(v * v for v in qs))
    if not abs(n - 1.0) < 1e-6:
        rt.report.problem(f'the orientation quaternion has norm {n:.6f}; 1 was due', tick)
        rt.fatal = 'the orientation is not a unit quaternion'
        return None
    why = psd_problem(cov)
    if why:
        rt.report.problem(f'covariance: {why}', tick)
        rt.fatal = f'the covariance is not positive semi-definite ({why})'
        return None
    th = api.yaw_of(q)
    return (x, y, th), (cov[0], cov[7])


def psd_problem(cov: List[float], n: int = 6) -> Optional[str]:
    """Return why a row-major ``n`` x ``n`` matrix is not symmetric PSD, or None."""
    scale = max(1.0, max(abs(v) for v in cov))
    tol = 1e-9 * scale
    for i in range(n):
        for j in range(i + 1, n):
            if abs(cov[i * n + j] - cov[j * n + i]) > tol:
                return f'not symmetric at ({i}, {j})'
    # LDL^T without pivoting, with a tolerance: a negative pivot means not PSD
    a = [[cov[i * n + j] for j in range(n)] for i in range(n)]
    for k in range(n):
        d = a[k][k]
        if d < -tol:
            return f'negative pivot {d:.3g} at {k}'
        if d <= tol:
            for i in range(k + 1, n):
                if abs(a[i][k]) > math.sqrt(tol) * 10:
                    return f'zero pivot with a non-zero column at {k}'
            continue
        for i in range(k + 1, n):
            f = a[i][k] / d
            for j in range(k + 1, n):
                a[i][j] -= f * a[k][j]
    return None


move_arena.USER_HOOKS.update(has=has, engine=UserEngine, control_cycle=control_cycle)
loc_arena.USER_HOOKS.update(has=has, localise_start=localise_start, localise_tick=localise_tick)
