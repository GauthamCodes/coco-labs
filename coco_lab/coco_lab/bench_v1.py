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
COCO-Bench v1 (R3.1; MODEL): the suites, their difficulty tiers and their generators.

Every v1 suite is a frozen file ``benchmarks/<id>.v1.json`` (``coco.bench.suite.v1``) written
once by ``tools/r3/make_suites_v1.py`` from :data:`SUITES` here, and checked by it ever after.
The same generators draw a suite's **held-out** scenarios from another seed (ADR 0014), so the
held-out set comes from exactly the public set's distribution.

**Reference path.** A scenario's features come from one reference plan: A* on the planning
family's default costmap (static + inflation layers; inflation 0.5 m, scaling 10, robot radius
0.25 m, 8-connected, cost weight 2), start and goal snapped to the nearest free cell, exactly as
the planning family runs it.

**Features** (all from the reference path, the world, and the scenario's conditions):

- ``path_length_m``: the path's length;
- ``min_clearance_m``: the smallest (clearance - robot radius) over its cells;
- ``narrow_run_m``: the longest stretch of the path with (clearance - radius) < 0.6 m;
- ``turns``: bends of 45 degrees or more (8-connected direction changes, a bend within 3 cells
  of the previous one counted once);
- ``zones``: how many region zones the path passes through (Depot worlds);
- ``actor_exposure_m``: path length within 1.5 m of an actor lane (worlds with actors);
- ``kidnap_m``: (kidnap suites) the distance the robot is carried.

**Tiers.** Within a suite each tier feature is turned into a percentile rank (ties share the
mean rank; for ``min_clearance_m`` the narrowest ranks highest), the ranks are averaged into a
``difficulty`` score, and the scenarios sorted by (score, id) are cut into thirds: easy, medium,
hard (sizes differ by at most one, the larger tiers first). The features used are the suite's
``tier_features``; the cut scores are recorded in the suite.

**Conditions** a scenario may carry (only v1 scenarios do, so no earlier run changes):
``config`` (Arena config choices sent at tick 0, e.g. ``actors.on=1``, ``actors.yield=1``,
``localise.mcl.init=global``) and ``kidnap_at_s`` / ``kidnap`` (localisation).
"""

from typing import Callable, Dict, List, Optional

from . import numerics
from .numerics import math
from .rng import Rng

SCHEMA = 'coco.bench.suite.v1'
TOOL = 'tools/r3/make_suites_v1.py'
TIERS = ('easy', 'medium', 'hard')
NARROW_M = 0.6
ACTOR_NEAR_M = 1.5
#: features where a smaller value is harder
SMALLER_IS_HARDER = ('min_clearance_m',)


# -- the reference path and features ----------------------------------------------------------

def reference(world, start, goal):
    """The reference A* path's cells (None if unreachable), the costmap layers and the grid."""
    from .arena import PLANNERS
    from .costmap import InflationParams
    from .exp_families import COSTMAPS
    from .search import search
    from .sketch import _nearest_free
    with numerics.version(3):
        ip = InflationParams()
        layers, grid = COSTMAPS.get(world, ip, 8, 2.0)
        m = world.lab_map
        s0, t0 = m.cell_at(*start[:2]), m.cell_at(*goal[:2])
        if s0 is None or t0 is None:
            return None, layers, ip
        a, b = _nearest_free(grid, s0), _nearest_free(grid, t0)
        if a is None or b is None:
            return None, layers, ip
        r = search(grid, a, b, **PLANNERS['astar'])
        return (list(r.path) if r.found else None), layers, ip


def _turns(cells) -> int:
    turns, last, prev = 0, -10, None
    for i in range(1, len(cells)):
        d = (cells[i][0] - cells[i - 1][0], cells[i][1] - cells[i - 1][1])
        if prev is not None and d != prev:
            a = math.atan2(d[0], d[1]) - math.atan2(prev[0], prev[1])
            a = abs((a + math.pi) % (2 * math.pi) - math.pi)
            if a >= math.pi / 4 - 1e-9 and i - last > 3:
                turns += 1
                last = i
        prev = d
    return turns


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def actor_lanes(world) -> List[tuple]:
    """Each actor's lane as segments in map coordinates."""
    dx, dy = world.spec.get('world_to_map', [0, 0])
    out = []
    for k in world.spec.get('kit', []):
        if k.get('kind') == 'actor':
            pts = [(p[0] + dx, p[1] + dy) for p in k['path']]
            out += list(zip(pts, pts[1:]))
    return out


def features(world, scenario: Dict) -> Optional[Dict]:
    """The scenario's features (None when the reference plan finds no path)."""
    cells, layers, ip = reference(world, scenario['start'], scenario['goal'])
    if cells is None:
        return None
    m = world.lab_map
    res = m.resolution
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(cells, cells[1:])) * res
    cl = [layers.clearance[r * m.width + c] - ip.robot_radius for r, c in cells]
    run = best = 0.0
    for i, v in enumerate(cl):
        step = 0.0 if i == 0 else math.hypot(cells[i][0] - cells[i - 1][0],
                                             cells[i][1] - cells[i - 1][1]) * res
        run = run + step if v < NARROW_M else 0.0
        best = max(best, run)
    pts = [m.cell_centre(r, c) for r, c in cells]
    out = {'path_length_m': round(length, 4), 'min_clearance_m': round(min(cl), 4),
           'narrow_run_m': round(best, 4), 'turns': _turns(cells)}
    if world.regions:
        zs, last = 0, None
        for p in pts:
            z = world.zone_of(*p)
            if z is not None and z != last:
                zs += 1
                last = z
        out['zones'] = zs
    lanes = actor_lanes(world)
    if lanes:
        exp = 0.0
        for i in range(1, len(pts)):
            if min(_seg_dist(pts[i], a, b) for a, b in lanes) <= ACTOR_NEAR_M:
                exp += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        out['actor_exposure_m'] = round(exp, 4)
    if 'kidnap' in scenario:
        k = scenario['kidnap']
        out['kidnap_m'] = round(math.hypot(k[0] - scenario['start'][0],
                                           k[1] - scenario['start'][1]), 4)
    return out


# -- tiers ---------------------------------------------------------------------------------------

def _ranks(values: List[float]) -> List[float]:
    """Percentile ranks in [0, 1], ties sharing their mean rank."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j) / 2 / (n - 1) if n > 1 else 0.5
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def assign_tiers(scenarios: List[Dict], keys: List[str]) -> Dict:
    """Set each scenario's ``difficulty`` and ``tier``; return the suite's tier record."""
    per = []
    for k in keys:
        vals = [s['features'][k] for s in scenarios]
        if k in SMALLER_IS_HARDER:
            vals = [-v for v in vals]
        per.append(_ranks(vals))
    for i, s in enumerate(scenarios):
        s['difficulty'] = round(sum(p[i] for p in per) / len(per), 6)
    order = sorted(range(len(scenarios)),
                   key=lambda i: (scenarios[i]['difficulty'], scenarios[i]['id']))
    n = len(order)
    sizes = [n // 3 + (1 if t < n % 3 else 0) for t in range(3)]
    cuts, at = [], 0
    for t, size in enumerate(sizes):
        for i in order[at:at + size]:
            scenarios[i]['tier'] = TIERS[t]
        at += size
        if t < 2 and at < n:
            cuts.append(scenarios[order[at - 1]]['difficulty'])
    return {'method': 'mean percentile rank of the tier features; thirds by (difficulty, id)',
            'features': list(keys), 'counts': dict(zip(TIERS, sizes)), 'cut_difficulty': cuts}


# -- generators ----------------------------------------------------------------------------------

def _pool(world, n, seed, min_sep, stratify='none'):
    from .exp_scenarios import sample_pairs
    return sample_pairs(world, n, seed, min_sep, 0.35, None, stratify, True)['scenarios']


def _filtered(world, n, seed, pool, min_sep, keep: Callable[[Dict], bool], prefix):
    """Draw a seeded pool; keep, in draw order, the first ``n`` whose features pass ``keep``."""
    out = []
    for s in _pool(world, pool, seed, min_sep):
        f = features(world, s)
        if f is None or not keep(f):
            continue
        out.append(dict(s, id=f'{prefix}{len(out) + 1:03d}', features=f))
        if len(out) == n:
            return out
    raise ValueError(f'only {len(out)} of {n} scenarios pass the filter in a pool of {pool}')


def _kidnap_point(world, rng, s, min_m):
    cands = world.candidates(0.35)
    comp = world.component(*s['start'][:2])
    for _ in range(5000):
        p = cands[rng.randrange(len(cands))]
        if world.component(*p) != comp:
            continue
        if math.hypot(p[0] - s['start'][0], p[1] - s['start'][1]) >= min_m and \
                math.hypot(p[0] - s['goal'][0], p[1] - s['goal'][1]) >= min_m:
            return [p[0], p[1]]
    raise ValueError('no kidnap point')


def generate(suite_id: str, seed: Optional[int] = None, n: Optional[int] = None) -> List[Dict]:
    """
    The suite's scenarios (with features), drawn by its own generator.

    ``seed``/``n`` default to the suite's public ones; the held-out sets (ADR 0014) pass another
    seed and their own ``n``. A carried-over suite's public scenarios are its v0 scenarios
    exactly; its held-out ones are drawn by its v0 generator settings.
    """
    from . import experiments as ex
    d = SUITES[suite_id]
    g = d['generator']
    public = seed is None
    seed = g['seed'] if public else seed
    n = d['n'] if n is None else n
    w = ex.world(d['world'])
    kind = g['kind']
    if kind == 'carried':
        v0 = ex.suite(d.get('from', suite_id), 0)
        if public:
            scen = [dict(s) for s in v0['scenarios']]
        elif v0['generator']['kind'] == 'sampled':
            v = v0['generator']
            scen = _pool(w, n, seed, v['min_separation_m'], v['stratify'])
        else:   # depot-narrow-30: its filter, again, from another seed
            scen = _narrow(w, n, seed)
        for s in scen:
            s['features'] = features(w, s)
        return scen
    if kind == 'filtered':
        return _filtered(w, n, seed, g['pool'], g['min_separation_m'], d['keep'], d['prefix'])
    if kind == 'paired_rules':   # each pair twice: the actors yielding, and not
        pairs = _filtered(w, n // 2, seed, g['pool'], g['min_separation_m'], d['keep'],
                          d['prefix'])
        out = []
        for rule in ('yield', 'no_yield'):
            cfg = ['actors.on=1'] + (['actors.yield=1'] if rule == 'yield' else [])
            for p in pairs:
                out.append(dict(p, id=f'{p["id"]}_{rule}', pair=p['id'], actor_rule=rule,
                                config=cfg))
        return out
    if kind == 'localisation':
        rng = Rng(seed ^ 0x5DEECE66D)
        scen = _pool(w, n, seed, g['min_separation_m'])
        for i, s in enumerate(scen):
            s['id'] = f'{d["prefix"]}{i + 1:03d}'
            if d.get('init') == 'global':
                s['config'] = ['localise.mcl.init=global']
            if d.get('kidnap_at_s'):
                s['kidnap_at_s'] = d['kidnap_at_s']
                s['kidnap'] = _kidnap_point(w, rng, s, g['kidnap_min_m'])
            s['features'] = features(w, s)
        return scen
    raise ValueError(f'no generator {kind!r}')


def _narrow(w, n, seed):
    """R1's depot-narrow-30 selection (tools/r1/make_suites.py), for its held-out draws."""
    half = n // 2
    picked = {'zone_workshop': [], 'zone_high_bay': []}
    need = {'zone_workshop': n - half, 'zone_high_bay': half}
    m = w.lab_map
    for s in _pool(w, 600, seed, 4.0):
        if all(len(picked[z]) >= need[z] for z in picked):
            break
        cells, _, _ = reference(w, s['start'], s['goal'])
        if cells is None:
            continue
        for z in picked:
            rr = w.regions[z]
            n_in = sum(1 for c in cells if rr[0] <= m.cell_centre(*c)[0] <= rr[1]
                       and rr[2] <= m.cell_centre(*c)[1] <= rr[3])
            through = s['start_zone'] != z and s['goal_zone'] != z
            ok = n_in * m.resolution >= 5.0 and (through if z == 'zone_high_bay' else True)
            if ok and len(picked[z]) < need[z]:
                picked[z].append(dict(s, passes=z))
                break
    out = picked['zone_workshop'] + picked['zone_high_bay']
    for i, s in enumerate(out):
        s['id'] = f'n{i + 1:03d}'
    return out


# -- the suites ----------------------------------------------------------------------------------

NAV_TIER = ['path_length_m', 'min_clearance_m', 'turns']

SUITES: Dict[str, Dict] = {
    # global planning
    'arena-nav-50': dict(
        world='coco_arena_v1', n=50, families=['planning', 'control', 'localisation'],
        generator={'kind': 'carried', 'seed': 5001}, heldout_n=15, tier_features=NAV_TIER,
        title='Proving Ground: 50 start/goal pairs (v0 scenarios, now tiered)'),
    'depot-nav-100': dict(
        world='coco_depot_v1', n=100, families=['planning', 'control', 'localisation'],
        generator={'kind': 'carried', 'seed': 1001}, heldout_n=20,
        tier_features=NAV_TIER + ['zones'],
        title='Depot: 100 pairs across its six zones (v0 scenarios, now tiered)'),
    'depot-narrow-30': dict(
        world='coco_depot_v1', n=30, families=['planning', 'control'],
        generator={'kind': 'carried', 'seed': 3001}, heldout_n=10,
        tier_features=NAV_TIER + ['narrow_run_m'],
        title='Depot: the workshop maze and the rack aisles (v0 scenarios, now tiered)'),
    'depot-long-50': dict(
        world='coco_depot_v1', n=50, families=['planning', 'control'], prefix='l',
        generator={'kind': 'filtered', 'seed': 7001, 'pool': 1500, 'min_separation_m': 20.0,
                   'rule': 'reference path >= 35 m through >= 3 zones'},
        keep=lambda f: f['path_length_m'] >= 35.0 and f['zones'] >= 3,
        heldout_n=15, tier_features=NAV_TIER + ['zones'],
        title='Depot: long routes across three or more zones'),
    'depot-clutter-50': dict(
        world='coco_depot_clutter_v1', n=50, families=['planning', 'control'], prefix='c',
        generator={'kind': 'filtered', 'seed': 7101, 'pool': 600, 'min_separation_m': 6.0,
                   'rule': 'reference path passes within 0.6 m clearance for >= 1 m'},
        keep=lambda f: f['narrow_run_m'] >= 1.0,
        heldout_n=15, tier_features=NAV_TIER + ['narrow_run_m'],
        title='Cluttered Depot: the Depot plus 24 kit pallets, routes that pass them'),
    # local control
    'ctrl-corridor-30': dict(
        world='coco_depot_v1', n=30, families=['control'], prefix='k',
        generator={'kind': 'filtered', 'seed': 7201, 'pool': 1500, 'min_separation_m': 4.0,
                   'rule': '>= 4 m of the reference path with clearance < 0.6 m'},
        keep=lambda f: f['narrow_run_m'] >= 4.0,
        heldout_n=10, tier_features=['narrow_run_m', 'min_clearance_m', 'path_length_m'],
        title='Control: long narrow passages'),
    'ctrl-corners-30': dict(
        world='coco_depot_v1', n=30, families=['control'], prefix='t',
        generator={'kind': 'filtered', 'seed': 7301, 'pool': 1500, 'min_separation_m': 4.0,
                   'rule': '>= 5 bends of 45 deg or more, reference path 8-30 m'},
        keep=lambda f: f['turns'] >= 5 and 8.0 <= f['path_length_m'] <= 30.0,
        heldout_n=10, tier_features=['turns', 'min_clearance_m', 'path_length_m'],
        title='Control: routes with many corners'),
    'ctrl-dynamic-30': dict(
        world='coco_depot_v1', n=30, families=['control'], prefix='d',
        generator={'kind': 'paired_rules', 'seed': 7401, 'pool': 1500, 'min_separation_m': 6.0,
                   'rule': '>= 3 m of the reference path within 1.5 m of an actor lane; each '
                           'pair run with the actors yielding (scenario rule: Fetch Rush rules '
                           '5) and not yielding (rules 4)'},
        keep=lambda f: f['actor_exposure_m'] >= 3.0,
        heldout_n=10, tier_features=['actor_exposure_m', 'path_length_m', 'min_clearance_m'],
        title='Control: moving forklifts and walkers, yielding and not (scenario rules)'),
    # localisation
    'loc-track-30': dict(
        world='coco_depot_v1', n=30, families=['localisation'], prefix='p',
        generator={'kind': 'localisation', 'seed': 7501, 'min_separation_m': 6.0},
        heldout_n=10, tier_features=['path_length_m', 'turns', 'min_clearance_m'],
        title='Localisation: tracking from a known start'),
    'loc-global-20': dict(
        world='coco_depot_v1', n=20, families=['localisation'], prefix='g', init='global',
        generator={'kind': 'localisation', 'seed': 7601, 'min_separation_m': 6.0},
        heldout_n=6, tier_features=['path_length_m', 'turns', 'min_clearance_m'],
        algorithms=['mcl', 'mcl_augmented', 'user'],
        title='Localisation: global, from an unknown start (MCL family; an EKF cannot)'),
    'loc-kidnap-20': dict(
        world='coco_depot_v1', n=20, families=['localisation'], prefix='q', kidnap_at_s=12.0,
        generator={'kind': 'localisation', 'seed': 7701, 'min_separation_m': 6.0,
                   'kidnap_min_m': 5.0},
        heldout_n=6, tier_features=['kidnap_m', 'path_length_m', 'turns'],
        title='Localisation: the kidnapped robot (carried >= 5 m at 12 s, odometry untold)'),
}

#: the full task: committed rounds only (R1 rule), so neither tiers by generator nor held-out
TASK_SUITE = 'task-fetch-10'
