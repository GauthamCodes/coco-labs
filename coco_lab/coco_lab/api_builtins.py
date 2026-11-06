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
The built-in algorithms behind the algorithm API (R2; ADR 0013; MODEL).

Each wrapper has the signature a user's file has (``plan``, ``control`` or
``localise``) and sees only what a user's file sees: the ROS-shaped inputs and
``ctx``. Inside, it calls the very reference implementation the native families
run (:mod:`coco_lab.search`, :mod:`coco_lab.dstarlite`, :mod:`coco_lab.control`,
:mod:`coco_lab.localise`), rebuilding from the API inputs exactly the structures the
native subsystem builds. Run through :mod:`coco_lab.exp_user` they reproduce the
native built-ins' statuses, metrics and trajectories bit for bit
(``test/test_api_equivalence.py``): that is the proof that user code and built-ins
are measured identically.

Wrapped: the six planners, DWA, Regulated Pure Pursuit and MPPI, MCL (with and
without augmented injection) and the EKF. Not wrapped: the waypoint driver
(``builtin``), which is not a separate controller but the Arena's own M1 driving
loop -- there is no function to wrap.
"""

from dataclasses import replace
from typing import Dict

from . import api
from .numerics import math

PLANNERS = ('bfs', 'dijkstra', 'astar', 'greedy', 'weighted_astar', 'dstar_lite')
CONTROLLERS = ('dwa', 'rpp', 'mppi')
LOCALISERS = ('mcl', 'mcl_augmented', 'ekf')


class Builtin:
    """A wrapped reference algorithm: ``kind``, ``name`` and ``call(ctx, *args)``."""

    filename = 'builtin'

    def __init__(self, kind: str, name: str, fn):
        """``fn`` has the API signature."""
        self.kind, self.name, self.fn = kind, name, fn
        self.sha256 = 'builtin:' + name
        # how the native built-in adds up a path's length and cost, so the API's
        # measurement adds them in the same order: D* Lite's native summary uses
        # Python's compensated ``sum()``, the search planners add one edge at a time
        self.summation = 'compensated' if name == 'dstar_lite' else 'sequential'

    def call(self, ctx, *args):
        """Call the wrapper."""
        return self.fn(*args, ctx)


def algorithm(name: str) -> Builtin:
    """Return the wrapper of a built-in by its experiment name."""
    if name in PLANNERS:
        return Builtin('planner', name, lambda c, s, g, ctx: _plan(name, c, s, g, ctx))
    if name in CONTROLLERS:
        return Builtin('controller', name, lambda st, sc, p, ctx: _control(name, st, sc, p, ctx))
    if name in LOCALISERS:
        return Builtin('localiser', name, lambda o, sc, m, ctx: _localise(name, o, sc, m, ctx))
    raise ValueError(f'no built-in {name!r} behind the API')


# -- planners -------------------------------------------------------------------------------------

def _grid(costmap: api.Costmap, config: Dict):
    """Rebuild the planning family's Grid (rows from the top, as the native one) from the API."""
    from .grid import Grid
    w, h = costmap.width, costmap.height
    data = costmap.data
    combined = []
    for row in range(h):
        my = h - 1 - row
        combined.extend(data[my * w:(my + 1) * w])
    return Grid(w, h, blocked=[v >= 253 for v in combined], cost=combined,
                connectivity=config['connectivity'], cost_weight=config['cost_weight'])


def _plan(name, costmap, start, goal, ctx):
    from .arena import PLANNERS as ARENA_PLANNERS
    from .dstarlite import DStarLite, EXPAND as D_EXPAND, RAISE as D_RAISE
    from .search import collect, search_events
    from .trace import EXPAND, PUSH
    grid = _grid(costmap, ctx.config)
    h = costmap.height

    def cell(p):
        mx, my = costmap.world_to_map(p.x, p.y)
        return (h - 1 - my, mx)

    def centre(r, c):
        x, y = costmap.map_to_world(c, h - 1 - r)
        return x, y

    s, t = cell(start), cell(goal)
    if name == 'dstar_lite':
        engine = DStarLite(grid, s, t, heuristic='octile')
        found = engine.compute()
        cols = engine.trace.columns
        for i, kind in enumerate(cols['kind']):
            if kind in (D_EXPAND, D_RAISE):
                x, y = centre(cols['row'][i], cols['col'][i])
                ctx.emit('expand', x=x, y=y)
        path = engine.path() if found else None
    else:
        kw = dict(ARENA_PLANNERS[name])
        if name == 'weighted_astar':
            kw['weight'] = ctx.config['heuristic_weight']

        def rows(row):
            if row[0] == EXPAND:
                x, y = centre(row[1], row[2])
                ctx.emit('expand', x=x, y=y)
            elif row[0] == PUSH:
                x, y = centre(row[1], row[2])
                ctx.emit('push', x=x, y=y)
        out = collect(search_events(grid, s, t, **kw), rows)
        path = out.path if out.status == 'found' else None
    if path is None:
        return None
    return [api.Pose2D(*centre(c[0], c[1]), 0.0) for c in path]


# -- controllers ----------------------------------------------------------------------------------

def _control(name, state, scan, path, ctx):
    from .control import (DWA, DWAParams, LocalWindow, MPPI, MPPIParams, PathTracker, RPP,
                          RPPParams, WindowParams)
    mem = ctx.memory
    if 'engine' not in mem:
        cls = {'dwa': DWAParams, 'rpp': RPPParams, 'mppi': MPPIParams}[name]
        over = {k.partition('.')[2]: v for k, v in ctx.config.items()
                if k.startswith(name + '.')}
        over = {k: tuple(v) if isinstance(v, list) else v for k, v in over.items()}
        if not over:
            # exactly the native construction (the same default parameter objects)
            mem['engine'] = {'dwa': DWA, 'rpp': RPP}[name]() if name != 'mppi' \
                else MPPI(ctx.rng._rng)
        elif name == 'mppi':
            mem['engine'] = MPPI(ctx.rng._rng, replace(MPPIParams(), **over))
        else:
            mem['engine'] = {'dwa': DWA, 'rpp': RPP}[name](replace(cls(), **over))
        wover = {k.partition('.')[2]: v for k, v in ctx.config.items()
                 if k.startswith('window.')}
        mem['window'] = replace(WindowParams(), **wover) if wover else WindowParams()
    key = [(p.x, p.y) for p in path]
    if mem.get('path') != key:
        mem['path'] = key
        mem['tracker'] = PathTracker(key)
    tr = mem['tracker']
    b = (state.pose.x, state.pose.y, state.pose.theta)
    mount = (ctx.robot.lidar_mount[0], ctx.robot.lidar_mount[1], 0.0)
    win = LocalWindow(b, scan.ranges, scan.angles(), mount, tr.path[tr.i:tr.i + 200],
                      mem['window'])
    local = tr.local(b, win)
    e = mem['engine']
    v0, w0 = state.twist.linear.x, state.twist.angular.z
    gd = math.hypot(b[0] - tr.goal[0], b[1] - tr.goal[1])
    if e.kind == 'dwa':
        cy = e.compute(b, v0, w0, win, local, ctx.dt)
    elif e.kind == 'rpp':
        cy = e.compute(b, v0, w0, win, local, ctx.dt, goal_dist=gd)
    else:
        cy = e.compute(b, v0, w0, win, local, ctx.dt, goal=tr.goal, goal_yaw=tr.goal_yaw,
                       goal_dist=gd)
    for c in cy.candidates[:64]:
        ctx.emit('candidate', points=c.traj[2::3] or c.traj, cost=c.cost, valid=c.valid)
    if cy.lookahead:
        ctx.emit('lookahead', x=cy.lookahead[0], y=cy.lookahead[1])
    if cy.status == 'invalid_path':
        raise api.InvalidPath('no pose of the path is in the local window')
    if cy.status != 'ok':
        raise api.NoValidControl(cy.status)
    return api.Twist.of(cy.v, cy.w)


# -- localisers -----------------------------------------------------------------------------------

def _sketch(grid: api.OccupancyGrid):
    """Rebuild the Arena's SketchMap from the OccupancyGrid (rows from the top again)."""
    from .maps import FREE, LabMap, OCCUPIED, UNKNOWN
    from .sketch import SketchMap
    i = grid.info
    w, h = i.width, i.height
    occ = bytearray(w * h)
    for row in range(h):
        my = h - 1 - row
        for mx in range(w):
            v = grid.data[my * w + mx]
            occ[row * w + mx] = FREE if v == 0 else OCCUPIED if v == 100 else UNKNOWN
    return SketchMap(LabMap(w, h, bytes(occ), resolution=i.resolution,
                            origin=(i.origin.position.x, i.origin.position.y)))


def _localise(name, odom, scan, grid, ctx):
    from .localise import EKF, EKFParams, MCL, MCLParams
    from .sketch import LidarSpec, odom_delta, UPDATE_MIN_A, UPDATE_MIN_D, wrap
    mem = ctx.memory
    if 'filter' not in mem:
        smap = _sketch(grid)
        lidar = LidarSpec(len(scan.ranges), scan.angle_min, scan.angle_max, scan.range_min,
                          scan.range_max, (ctx.robot.lidar_mount[0], ctx.robot.lidar_mount[1],
                                           0.0))
        p0 = ctx.initial_pose
        start = (p0.x, p0.y, p0.theta)
        if name.startswith('mcl'):
            params = MCLParams()
            for k, v in ctx.config.items():
                if k.startswith('mcl.'):
                    setattr(params, k[4:], tuple(v) if isinstance(v, list) else v)
            params.injection = 'augmented' if name == 'mcl_augmented' else 'none'
            params.seed = 0
            mem['filter'] = MCL(smap, lidar, params, start, ctx.rng._rng)
        else:
            params = EKFParams()
            for k, v in ctx.config.items():
                if k.startswith('ekf.'):
                    setattr(params, k[4:], tuple(v) if isinstance(v, list) else v)
            mem['filter'] = EKF(smap, lidar, params, start)
        mem['last_odom'] = None
        mem['out'] = None
    q = odom.pose.pose
    o = (q.position.x, q.position.y, api.yaw_of(q.orientation))
    last = mem['last_odom']
    if last is not None:
        _, tr, _ = odom_delta(last, o)
        if tr < UPDATE_MIN_D and abs(wrap(o[2] - last[2])) < UPDATE_MIN_A:
            return mem['out']
    mem['last_odom'] = o
    f = mem['filter']
    u = f.update(o, list(scan.ranges))
    if isinstance(f, MCL):
        est, cov = u['est'], u['cov']
        P, w = u['particles']
        ctx.emit('particles', x=[p[0] for p in P], y=[p[1] for p in P],
                 theta=[p[2] for p in P], weight=list(w))
        out = api.PoseWithCovariance.of(est[0], est[1], est[2], cov[0], cov[2], cov[3], cov[1])
    else:
        est, P = u['est'], u['P']
        out = api.PoseWithCovariance.of(est[0], est[1], est[2], P[0][0], P[1][1], P[2][2],
                                        P[0][1])
        out.covariance[5] = out.covariance[30] = P[0][2]
        out.covariance[11] = out.covariance[31] = P[1][2]
    ctx.emit('estimate', x=est[0], y=est[1], theta=est[2])
    mem['out'] = out
    return out
