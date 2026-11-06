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
One experiment run per family (R1; MODEL): pure functions of their arguments.

Every run computes under state hash version 3's deterministic numerics
(ADR 0010), so CPython and Pyodide give the same counts and the same chain.
Each returns ``{status, success, metrics, chain, fail_tick, [series]}``:

- ``chain``: the run's hash chain, ``sha256(tag || canonical(descriptor) ||
  ...)`` where ``...`` is, for a search, every search event row packed exactly
  (``<4q3d3q``), and, for a run in the Arena, every tick's state hash.
- ``metrics``: counts (expansions, lengths, ticks, contacts, errors) are model
  outputs, the same on every device; ``compute_ms`` is wall time on THIS device
  (:data:`TIMING_METRICS`) and never enters a digest.

Families:

- ``planning``: a Nav2-style costmap (static + inflation layers of
  :mod:`coco_lab.costmap`; no LiDAR layer) on the world's map, the planner run
  once from the start's cell to the goal's (each snapped to the nearest free
  costmap cell, as Compare does; the snap distances are reported).
- ``control``: the Arena (seeded by the scenario) with the robot placed at the
  start, the chosen local controller (``move.controller``) following the
  Arena's global plan to the goal; ends on FollowPath's outcome, a failed
  plan (``no_path``), or ``max_ticks`` (``timeout``).
- ``localisation``: the Arena's builtin driver takes the robot from start to
  goal while the chosen filter localises it; the error between belief and
  truth is sampled every second; ``kidnap_at_s`` teleports the truth back to
  the start (or the scenario's ``kidnap`` point) then, the odometry untold.
- ``fulltask``: the reference bot (:mod:`coco_lab.games`) plays a committed
  round with the chosen planner driving it (the planner input the browser's
  Play sends); Grasp Assist's approach planning stays A*, as in Play.
"""

import copy
import hashlib
import struct
from time import perf_counter
from typing import Dict, List, Optional

from . import numerics
from .arena import Arena, InputEvent, PLANNERS
from .compare_planning import run_planner
from .costmap import build_layers, InflationParams
from .grid import Grid
from .numerics import math
from .search import collect, search_events
from .sketch import _nearest_free, wrap
from .trace import EXPAND, NO_PARENT, PATH, PUSH

#: the run chain's domain tag (experiment hash version 1)
RUN_TAG = b'coco.experiment.run.v1'
#: metrics measured in wall time on the running device (never in a digest)
TIMING_METRICS = ('compute_ms',)
_ROW = struct.Struct('<4q3d3q')
#: sample the localisation error this often (ticks)
LOC_SAMPLE_TICKS = 10


def canonical(obj) -> bytes:
    """Return the canonical JSON bytes (sorted keys, no spaces, integral floats as ints)."""
    import json

    def plain(x):
        if isinstance(x, float) and x.is_integer():
            return int(x)
        if isinstance(x, dict):
            return {k: plain(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [plain(v) for v in x]
        return x
    return json.dumps(plain(obj), sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _chain(descriptor) -> 'hashlib._Hash':
    h = hashlib.sha256(RUN_TAG)
    h.update(canonical(descriptor))
    return h


def _heading_change(points) -> float:
    total, prev = 0.0, None
    for a, b in zip(points, points[1:]):
        if a[0] == b[0] and a[1] == b[1]:
            continue
        hd = math.atan2(b[1] - a[1], b[0] - a[0])
        if prev is not None:
            total += abs(wrap(hd - prev))
        prev = hd
    return total


# -- planning ------------------------------------------------------------------------------------

class CostmapCache:
    """A worker's costmaps by (world, params): built once, reused (pure, so safe)."""

    def __init__(self, size: int = 6):
        """Keep at most ``size`` costmaps (a sweep visits them in order)."""
        self.size, self.items = size, {}

    def get(self, world, params: InflationParams, connectivity: int, cost_weight: float):
        """Return ``(layers, grid)`` for the world under the params."""
        key = (world.id, params.inflation_radius, params.cost_scaling_factor,
               params.robot_radius, connectivity, cost_weight)
        hit = self.items.pop(key, None)
        if hit is None:
            m = world.lab_map
            layers = build_layers(m.width, m.height, m.resolution,
                                  [v != 0 for v in m.occupancy], (), params)
            grid = Grid(m.width, m.height, blocked=[v >= 253 for v in layers.combined],
                        cost=layers.combined, connectivity=connectivity,
                        cost_weight=cost_weight)
            hit = (layers, grid)
            if len(self.items) >= self.size:
                self.items.pop(next(iter(self.items)))
        self.items[key] = hit
        return hit


COSTMAPS = CostmapCache()


def run_planning(world, scenario: Dict, name: str, params: Dict, descriptor: Dict,
                 sink=None, on_event=None) -> Dict:
    """Plan once on the static costmap; return the run record (``sink`` also sees each row)."""
    if name == 'user':
        from . import exp_user
        return run_user_planning(world, scenario, exp_user.load(descriptor['code_sha256']),
                                 params, descriptor, sink, on_event)
    with numerics.version(3):
        ip = InflationParams(params['inflation_radius'], params['cost_scaling_factor'],
                             params['robot_radius'])
        layers, grid = COSTMAPS.get(world, ip, params['connectivity'], params['cost_weight'])
        m = world.lab_map
        sx, sy = scenario['start'][:2]
        gx, gy = scenario['goal'][:2]
        h = _chain(descriptor)
        s0, t0 = m.cell_at(sx, sy), m.cell_at(gx, gy)
        s = _nearest_free(grid, s0) if s0 is not None else None
        t = _nearest_free(grid, t0) if t0 is not None else None
        metrics = {'expansions': None, 'pushes': None, 'path_length_m': None,
                   'path_cost': None, 'path_steps': None, 'min_clearance_m': None,
                   'mean_clearance_m': None, 'heading_change_rad': None,
                   'start_snap_m': None, 'goal_snap_m': None, 'compute_ms': None}
        if s is None or t is None:
            status = 'start_blocked' if s is None else 'goal_blocked'
            h.update(status.encode())
            return {'status': status, 'success': False, 'metrics': metrics,
                    'chain': h.hexdigest(), 'fail_tick': None}
        res = m.resolution
        metrics['start_snap_m'] = math.hypot(s[0] - s0[0], s[1] - s0[1]) * res
        metrics['goal_snap_m'] = math.hypot(t[0] - t0[0], t[1] - t0[1]) * res
        pack, upd = _ROW.pack, h.update

        def rows(row):
            upd(pack(row[0], row[1], row[2], row[3], float(row[4]), float(row[5]),
                     float(row[6]), row[7], row[8], row[9]))
            if sink is not None:
                sink(row)
        started = perf_counter()
        if name == 'dstar_lite':
            r = run_planner(grid, s, t, name, rows)
            status, path, summary = r.status, r.path, r.summary
        else:
            kw = dict(PLANNERS[name])
            if name == 'weighted_astar':
                kw['weight'] = params['heuristic_weight']
            out = collect(search_events(grid, s, t, **kw), rows)
            status, path, summary = out.status, out.path, out.trace.summary
        metrics['compute_ms'] = (perf_counter() - started) * 1000
        metrics['expansions'] = summary['expansions']
        metrics['pushes'] = summary.get('pushes')
        if status == 'found':
            cells = [(c[0], c[1]) for c in path]
            metrics['path_length_m'] = summary['path_length'] * res
            metrics['path_cost'] = summary['path_cost']
            metrics['path_steps'] = summary['path_steps']
            cl = [layers.clearance[r * m.width + c] - ip.robot_radius for r, c in cells]
            metrics['min_clearance_m'] = min(cl)
            metrics['mean_clearance_m'] = math.fsum(cl) / len(cl)
            metrics['heading_change_rad'] = _heading_change([m.cell_centre(r, c)
                                                             for r, c in cells])
        h.update(canonical({k: v for k, v in metrics.items() if k not in TIMING_METRICS}))
        return {'status': status, 'success': status == 'found', 'metrics': metrics,
                'chain': h.hexdigest(), 'fail_tick': None}


# -- planning with an algorithm file (R2) ---------------------------------------------------------

#: a path may have at most this many poses
MAX_PATH = 200_000


def _supercover(r0, c0, r1, c1):
    """Yield every cell the segment between two cell centres touches (both ends included)."""
    dr, dc = r1 - r0, c1 - c0
    n = max(abs(dr), abs(dc))
    seen = set()
    steps = 4 * n
    for i in range(steps + 1):
        t = i / steps
        fr, fc = r0 + dr * t, c0 + dc * t
        for rr in {math.floor(fr + 0.5 - 1e-9), math.floor(fr + 0.5 + 1e-9)}:
            for cc in {math.floor(fc + 0.5 - 1e-9), math.floor(fc + 0.5 + 1e-9)}:
                if (rr, cc) not in seen:
                    seen.add((rr, cc))
                    yield (rr, cc)


def measure_path(m, grid, layers, radius: float, cells: List,
                 summation: str = 'sequential') -> Dict:
    """
    Return ``{collision, length, cost, steps, clearance[], heading}`` for a cell path.

    The same arithmetic, in the same order, as :mod:`coco_lab.search`'s summary and
    the planning family's metrics, so an 8-connected path measures exactly as the
    built-in that found it. ``summation='compensated'`` adds the length and the cost
    with Python's ``sum()``, as :func:`coco_lab.compare_planning.run_planner` does for
    D* Lite; only the built-in D* Lite wrapper asks for it.
    """
    length = 0.0
    cost: Optional[float] = 0.0
    visited = [cells[0]]
    w = m.width
    for a, b in zip(cells, cells[1:]):
        (r0, c0), (r1, c1) = a, b
        if abs(r1 - r0) <= 1 and abs(c1 - c0) <= 1:
            if cost is not None and a != b:
                if b in set(grid.neighbours(a)):
                    cost = cost + grid.edge_cost(a, b)
                else:
                    cost = None
            visited.append(b)
        else:
            cost = None
            visited.extend(c for c in _supercover(r0, c0, r1, c1) if c != a)
        length += math.hypot(r1 - r0, c1 - c0)
    collision = None
    for r, c in visited:
        if not (0 <= r < m.height and 0 <= c < w) or layers.combined[r * w + c] >= 253:
            collision = (r, c)
            break
    if summation == 'compensated':
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(cells, cells[1:]))
        if cost is not None:
            cost = sum(grid.edge_cost(a, b) for a, b in zip(cells, cells[1:]))
    clearance = [layers.clearance[r * w + c] - radius for r, c in
                 (cells if cost is not None else visited)]
    return {'collision': collision, 'length': length, 'cost': cost,
            'steps': len(cells) - 1, 'clearance': clearance}


def run_user_planning(world, scenario: Dict, alg, params: Dict, descriptor: Dict,
                      sink=None, on_event=None) -> Dict:
    """Plan once with an API algorithm on the planning family's costmap; return the record."""
    from . import api
    from .exp_user import _call, _finish_report, _plain, costmap_of, FatalUserError, Report
    from .exp_user import BUDGETS, robot_of
    from .rng import Rng
    report = Report()
    with numerics.version(3):
        ip = InflationParams(params['inflation_radius'], params['cost_scaling_factor'],
                             params['robot_radius'])
        layers, grid = COSTMAPS.get(world, ip, params['connectivity'], params['cost_weight'])
        m = world.lab_map
        sx, sy = scenario['start'][:2]
        gx, gy = scenario['goal'][:2]
        h = _chain(descriptor)
        s0, t0 = m.cell_at(sx, sy), m.cell_at(gx, gy)
        s = _nearest_free(grid, s0) if s0 is not None else None
        t = _nearest_free(grid, t0) if t0 is not None else None
        metrics = {'expansions': None, 'pushes': None, 'path_length_m': None,
                   'path_cost': None, 'path_steps': None, 'min_clearance_m': None,
                   'mean_clearance_m': None, 'heading_change_rad': None,
                   'start_snap_m': None, 'goal_snap_m': None, 'compute_ms': None}
        if s is None or t is None:
            status = 'start_blocked' if s is None else 'goal_blocked'
            h.update(status.encode())
            return {'status': status, 'success': False, 'metrics': metrics,
                    'chain': h.hexdigest(), 'fail_tick': None, 'report': report.to_dict()}
        res = m.resolution
        metrics['start_snap_m'] = math.hypot(s[0] - s0[0], s[1] - s0[1]) * res
        metrics['goal_snap_m'] = math.hypot(t[0] - t0[0], t[1] - t0[1]) * res
        costmap = costmap_of(m, layers)
        sth = scenario['start'][2] if len(scenario['start']) > 2 else 0.0
        gth = scenario['goal'][2] if len(scenario['goal']) > 2 else 0.0
        start = api.Pose2D(*m.cell_centre(*s), sth)
        goal = api.Pose2D(*m.cell_centre(*t), gth)
        counts = {'expand': 0, 'push': 0}

        def on_emit(ev):
            kind, data = ev
            data = {k: _plain(v) for k, v in data.items()}
            h.update(canonical([kind, data]))
            if kind in counts:
                counts[kind] += 1
            if on_event is not None:
                on_event(kind, data)
            if sink is not None and kind in ('expand', 'push', 'frontier'):
                cell = m.cell_at(data['x'], data['y'])
                if cell is not None:
                    code = EXPAND if kind == 'expand' else PUSH
                    sink((code, cell[0], cell[1], 0, -1.0, -1.0, -1.0) + NO_PARENT)
        ctx = api.Context(Rng(scenario.get('seed', 1) % (1 << 64)), robot_of(world.spec),
                          params={k[5:]: v for k, v in params.items() if k.startswith('user.')},
                          budget=BUDGETS['planner'], dt=world.spec['arena']['dt'],
                          sink=on_emit,
                          config={k: v for k, v in params.items() if not k.startswith('user.')})
        ctx._costmap = costmap
        started = perf_counter()
        status, out = None, None
        try:
            out = _call(alg, report, ctx, costmap, start, goal)
        except FatalUserError:
            status = 'budget_exceeded' if (report.error or {}).get('type') == 'BudgetExceeded' \
                else 'error'
        except (api.NoValidControl, api.InvalidPath) as e:
            report.error = {'type': type(e).__name__, 'message': str(e), 'line': None,
                            'frames': []}
            status = 'error'
        metrics['compute_ms'] = (perf_counter() - started) * 1000
        cells = None
        if status is None:
            if out is None:
                status = 'no_path'
            else:
                cells, why = _path_cells(m, out, s, t)
                if why:
                    report.problem(why)
                    status = 'invalid_output'
        # None, not 0, when the algorithm reports none (D* Lite has no pushes)
        metrics['expansions'] = counts['expand'] or None
        metrics['pushes'] = counts['push'] or None
        if status is None:
            from .api_builtins import Builtin
            summation = alg.summation if isinstance(alg, Builtin) else 'sequential'
            mp = measure_path(m, grid, layers, ip.robot_radius, cells, summation)
            h.update(canonical([[c[0], c[1]] for c in cells]))
            if mp['collision'] is not None:
                r, c = mp['collision']
                report.problem(f'the path crosses cell (mx={c}, my={m.height - 1 - r}), '
                               'which is lethal or inscribed (cost >= 253)')
                status = 'collision'
            else:
                status = 'found'
                metrics['path_length_m'] = mp['length'] * res
                metrics['path_cost'] = mp['cost']
                metrics['path_steps'] = mp['steps']
                cl = mp['clearance']
                metrics['min_clearance_m'] = min(cl)
                metrics['mean_clearance_m'] = math.fsum(cl) / len(cl)
                metrics['heading_change_rad'] = _heading_change([m.cell_centre(r, c)
                                                                 for r, c in cells])
                if sink is not None:
                    prev = NO_PARENT
                    for r, c in cells:
                        sink((PATH, r, c, 0, -1.0, -1.0, -1.0) + prev)
                        prev = (r, c, 0)
        h.update(canonical({k: v for k, v in metrics.items() if k not in TIMING_METRICS}))
        return {'status': status, 'success': status == 'found', 'metrics': metrics,
                'chain': h.hexdigest(), 'fail_tick': None,
                'report': _finish_report(alg, report)}


def _path_cells(m, out, s, t):
    """Return ``(cells, None)`` for a valid returned path, else ``(None, why)``."""
    if not isinstance(out, (list, tuple)):
        return None, f'plan() returned {type(out).__name__}; a list of Pose2D (or None) was due'
    if not out:
        return None, 'plan() returned an empty path; return None when there is no path'
    if len(out) > MAX_PATH:
        return None, f'plan() returned {len(out)} poses; at most {MAX_PATH}'
    cells = []
    for i, p in enumerate(out):
        try:
            x, y = float(p.x), float(p.y)
        except (AttributeError, TypeError, ValueError):
            return None, f'path[{i}] is {type(p).__name__}, not a Pose2D'
        if not (math.isfinite(x) and math.isfinite(y)):
            return None, f'path[{i}] is not finite: ({x}, {y})'
        c = m.cell_at(x, y)
        if c is None:
            return None, f'path[{i}] ({x:.3f}, {y:.3f}) is off the map'
        cells.append(c)
    if cells[0] != tuple(s):
        return None, 'the path does not start in the start cell'
    if cells[-1] != tuple(t):
        return None, 'the path does not end in the goal cell'
    return cells, None


# -- runs in the Arena ---------------------------------------------------------------------------

def _arena_at(world, scenario: Dict, planner: str = 'astar') -> Arena:
    spec = copy.deepcopy(world.spec)
    dx, dy = spec['world_to_map']
    x, y, th = scenario['start']
    spec['start'] = {'x': x - dx, 'y': y - dy, 'theta': th}
    return Arena(spec, scenario['seed'] % (1 << 64), planner=planner, hash_version=3)


def _drive_metrics(a: Arena, ticks, t_contact: int, dist: float, cl, heading: float,
                   expansions: int, plans: int, goal) -> Dict:
    return {'time_s': ticks * a.dt, 'ticks': ticks, 'path_length_m': dist,
            'min_clearance_m': min(cl) if cl else None,
            'mean_clearance_m': math.fsum(cl) / len(cl) if cl else None,
            'heading_change_rad': heading, 'contacts': t_contact,
            'expansions': expansions, 'plans': plans,
            'final_goal_distance_m': math.hypot(a.pose[0] - goal[0], a.pose[1] - goal[1])}


class _Drive:
    """Step an Arena, chaining its tick hashes and measuring the drive (truth)."""

    def __init__(self, a: Arena, h, on_tick=None):
        self.a, self.h, self.on_tick = a, h, on_tick
        self.ticks = self.contacts = self.expansions = self.plans = 0
        self.dist = self.heading = 0.0
        self.cl = []
        self.in_contact = False
        self.plan_failed = False

    def step(self, events=()):
        a = self.a
        before = a.pose
        t = a.step(events)
        self.ticks += 1
        self.h.update(t.state_hash.encode())
        self.dist += math.hypot(t.pose[0] - before[0], t.pose[1] - before[1])
        self.heading += abs(wrap(t.pose[2] - before[2]))
        self.cl.append(a.smap.clearance(t.pose[0], t.pose[1]) - a.radius)
        if t.contact and not self.in_contact:
            self.contacts += 1
        self.in_contact = t.contact
        for p in t.plans:
            self.plans += 1
            self.expansions += p.result.trace.summary['expansions']
            self.plan_failed = not p.result.found
        if self.on_tick is not None:
            self.on_tick(a, t)
        return t


def run_control(world, scenario: Dict, name: str, params: Dict, descriptor: Dict,
                max_ticks: int, on_tick=None, on_event=None) -> Dict:
    """Follow the Arena's plan with the chosen controller (``on_tick(arena, tick)`` watches)."""
    with numerics.version(3):
        a = _arena_at(world, scenario, params.get('planner', 'astar'))
        user = _attach(a, name, params, descriptor, on_event)
        h = _chain(descriptor)
        cfg = []
        for key, value in sorted(params.items()):
            if key.startswith(('window.', name + '.')) and not key.startswith('user.'):
                v = ','.join(str(x) for x in value) if isinstance(value, list) else str(value)
                cfg.append(f'move.{key}={v}')
        cfg.append(f'move.controller={name}')
        goal = tuple(scenario['goal'][:2])
        events = [InputEvent(0, 'config', choice=c) for c in cfg]
        events.append(InputEvent(0, 'goal', x=goal[0], y=goal[1]))
        d = _Drive(a, h, on_tick)
        started = perf_counter()
        t = d.step(events)
        mv = a.subsystems['move']
        status, fail_tick = None, None
        while True:
            if user is not None and user.fatal(a):
                status = 'error'
            elif mv.outcome:
                status = mv.outcome
            elif name == 'builtin' and t.arrived:
                status = 'succeeded'
            elif a.mode == 'idle':
                status = 'no_path' if d.plan_failed else 'stopped'
            elif d.ticks >= max_ticks:
                status = 'timeout'
            if status is not None:
                break
            t = d.step()
        elapsed = (perf_counter() - started) * 1000
        if status != 'succeeded':
            fail_tick = d.ticks - 1
        metrics = _drive_metrics(a, d.ticks, d.contacts, d.dist, d.cl, d.heading,
                                 d.expansions, d.plans, goal)
        h.update(canonical(metrics))
        metrics['compute_ms'] = elapsed
        out = {'status': status, 'success': status == 'succeeded', 'metrics': metrics,
               'chain': h.hexdigest(), 'fail_tick': fail_tick}
        if user is not None:
            out['report'] = user.finished(a).get('controller')
        return out


def run_localisation(world, scenario: Dict, name: str, params: Dict, descriptor: Dict,
                     max_ticks: int, kidnap_at_s: Optional[float] = None, on_tick=None,
                     on_event=None) -> Dict:
    """Drive start to goal while the filter localises; return the run record with its series."""
    from .localise import OK_HOLD, OK_XY, OK_YAW
    with numerics.version(3):
        a = _arena_at(world, scenario)
        user = _attach(a, name, params, descriptor, on_event)
        h = _chain(descriptor)
        kind = 'user' if user is not None else 'mcl' if name.startswith('mcl') else 'ekf'
        cfg = []
        for key, value in sorted(params.items()):
            if key.startswith(kind + '.') and kind != 'user':
                v = ','.join(str(x) for x in value) if isinstance(value, list) else str(value)
                cfg.append(f'localise.{key}={v}')
        if kind == 'mcl':
            cfg.append('localise.mcl.injection=' +
                       ('augmented' if name == 'mcl_augmented' else 'none'))
        cfg.append('localise.filter=' + kind)
        goal = tuple(scenario['goal'][:2])
        events = [InputEvent(0, 'config', choice=c) for c in cfg]
        events.append(InputEvent(0, 'goal', x=goal[0], y=goal[1]))
        d = _Drive(a, h, on_tick)
        kidnap_tick = None if kidnap_at_s is None else max(1, round(kidnap_at_s / a.dt))
        series = []
        started = perf_counter()
        t = d.step(events)
        arrived = False
        while True:
            b = a.belief()
            if (d.ticks - 1) % LOC_SAMPLE_TICKS == 0:
                series.append([round((d.ticks - 1) * a.dt, 6),
                               math.hypot(b[0] - t.pose[0], b[1] - t.pose[1]),
                               abs(wrap(b[2] - t.pose[2]))])
            if t.arrived:
                arrived = True
                break
            if d.ticks >= max_ticks or (user is not None and user.fatal(a)):
                break
            ev = []
            if kidnap_tick is not None and d.ticks == kidnap_tick:
                k = scenario.get('kidnap') or scenario['start']
                ev.append(InputEvent(a.tick, 'kidnap', x=k[0], y=k[1]))
                ev.append(InputEvent(a.tick, 'goal', x=goal[0], y=goal[1]))
            elif a.mode == 'idle' and not t.arrived:
                if d.plan_failed:
                    break
            t = d.step(ev)
        elapsed = (perf_counter() - started) * 1000
        b = a.belief()
        err_xy = math.hypot(b[0] - a.pose[0], b[1] - a.pose[1])
        err_yaw = abs(wrap(b[2] - a.pose[2]))
        ok = [e < OK_XY and y < OK_YAW for _, e, y in series]
        kid = None if kidnap_tick is None else kidnap_tick * a.dt

        def first_hold(lo_t, hi_t):
            idx = [i for i, row in enumerate(series) if lo_t <= row[0] < hi_t]
            for j, i in enumerate(idx):
                window = idx[j:j + OK_HOLD]
                if len(window) == OK_HOLD and all(ok[w] for w in window):
                    return series[i][0]
            return None
        conv = first_hold(0.0, kid if kid is not None else math.inf)
        rec = first_hold(kid, math.inf) if kid is not None else None
        errs = [row[1] for row in series]
        metrics = _drive_metrics(a, d.ticks, d.contacts, d.dist, d.cl, d.heading,
                                 d.expansions, d.plans, goal)
        metrics.update({'final_err_xy_m': err_xy, 'final_err_yaw_rad': err_yaw,
                        'mean_err_xy_m': math.fsum(errs) / len(errs) if errs else None,
                        'max_err_xy_m': max(errs) if errs else None,
                        'converged_s': conv, 'recovery_s': None if rec is None else rec - kid,
                        'reached_goal': arrived})
        localised = err_xy < OK_XY and err_yaw < OK_YAW
        status = ('localised' if localised else 'not_localised') if arrived else \
            ('timeout' if d.ticks >= max_ticks else 'no_path')
        if user is not None and user.fatal(a):
            status, arrived = 'error', False
        h.update(canonical({'metrics': metrics, 'series': series}))
        metrics['compute_ms'] = elapsed
        out = {'status': status, 'success': arrived and localised, 'metrics': metrics,
               'chain': h.hexdigest(),
               'fail_tick': None if arrived and localised else d.ticks - 1,
               'series': series}
        if user is not None:
            out['report'] = user.finished(a).get('localiser')
        return out


def _attach(a, name: str, params: Dict, descriptor: Dict, on_event):
    """R2: attach the descriptor's algorithm file to the Arena; return exp_user (or None)."""
    if name != 'user':
        return None
    from . import exp_user
    exp_user.attach(a, exp_user.load(descriptor['code_sha256']), params, on_event)
    return exp_user


def run_fulltask(world, scenario: Dict, name: str, params: Dict, descriptor: Dict) -> Dict:
    """Play the round with the reference bot driven by ``name``; return the run record."""
    from . import games
    with numerics.version(3):
        h = _chain(descriptor)
        started = perf_counter()
        if scenario['game'] == 'fetch_rush':
            rules = games.FetchRushRound(
                scenario['round'], games.round_for(scenario['round'], rules=scenario['rules'],
                                                   mode=scenario['mode']),
                rules=scenario['rules'], mode=scenario['mode'])
            rec, res = games.bot_fetch_rush(world.spec, scenario['round'], arena_seed=1,
                                            rules=rules, hash_version=3, planner=name)
            n_orders = len(rules.orders)
        else:
            rules = games.FetchColour(scenario['colour'], rules=scenario['rules'])
            rec, res = games.bot_fetch_colour(world.spec, scenario['colour'], arena_seed=1,
                                              rules=rules, hash_version=3, planner=name)
            n_orders = len(rules.orders)
        elapsed = (perf_counter() - started) * 1000
        card = res['scorecard']
        h.update(res['hash_chain'].encode())
        done = card['deliveries'] >= n_orders
        metrics = {'deliveries': card['deliveries'], 'orders': n_orders,
                   'contacts': card['contacts'], 'net_deliveries': card['net_deliveries'],
                   'time_to_complete_s': card['time_used'] if done else None,
                   'time_used_s': card['time_used'], 'path_efficiency': card['path_efficiency'],
                   'ticks': rec['ticks'], 'timer_s': card.get('timer')}
        h.update(canonical(metrics))
        metrics['compute_ms'] = elapsed
        return {'status': 'completed' if done else 'incomplete', 'success': done,
                'metrics': metrics, 'chain': h.hexdigest(),
                'fail_tick': None if done else rec['ticks'] - 1,
                'record': rec, 'game_chain': res['hash_chain']}
