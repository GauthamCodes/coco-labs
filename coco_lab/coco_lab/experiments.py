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
Reproducible experiments (R1 · Research Workbench; MODEL).

An experiment is a small spec (``coco.experiment.v1``): a world, a family, one
or more algorithms with parameters, a scenario generator and its seed, an
optional sweep of one or two parameters, and the metrics to show. The same spec
gives the same runs, the same counts and the same per-run hash chains in
CPython (``python -m coco_lab.experiments run spec.json --out dir/``) and in
the browser's Pyodide workers, because every run is a pure function of the
spec and its index, computed under state hash version 3 (ADR 0010).

- :func:`plan` validates a spec, fills its defaults and resolves its scenarios
  and run list (sweep point x algorithm x scenario).
- :func:`run_one` runs one entry of that list (:mod:`coco_lab.exp_families`).
- :func:`digest` hashes every run's index, status, chain and counts (never a
  wall-clock time): two hosts agree exactly when their digests do.
- :func:`summarise` gives per-algorithm N, Wilson 95% success intervals,
  medians and IQRs, and paired comparisons on shared scenarios (Wilcoxon
  signed-rank with effect sizes, McNemar for success, Holm across pairs)
  (:mod:`coco_lab.exp_stats`).
- :func:`results_csv`, :func:`manifest`: the export set.

Timings (``compute_ms``) are measured on the running device and labelled so;
counts need no device.
"""

import copy
from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from . import exp_stats, loc_arena, move_arena  # noqa: F401 -- register subsystems
from .arena import PLANNERS
from .compare_planning import COMPARE_PLANNERS
from .control import DWAParams, MPPIParams, RPPParams, WindowParams
from .exp_families import (canonical, run_control, run_fulltask, run_localisation,
                           run_planning, TIMING_METRICS)
from .exp_scenarios import hand_pairs, sample_pairs, ScenarioError, World
from .localise import EKFParams, MCLParams
from .numerics import math

SCHEMA = 'coco.experiment.v1'
#: what a spec's ``model`` block must say for this build to run it
MODEL = {'hash_version': 3, 'experiment': 1}
DIGEST_TAG = b'coco.experiment.digest.v1'
FAMILIES = ('planning', 'control', 'localisation', 'fulltask')
ALGORITHMS = {
    'planning': tuple(COMPARE_PLANNERS),
    'control': tuple(move_arena.CONTROLLERS),
    'localisation': ('mcl', 'mcl_augmented', 'ekf'),
    'fulltask': tuple(PLANNERS),
}
#: R2: an algorithm file (coco_lab.api, ``coco.algorithm.v1``): ``{"name": "user", "api": 1,
#: "code_sha256": ...}``; its source travels beside the spec (a link, ``--algorithm``)
USER = 'user'
USER_FAMILIES = ('planning', 'control', 'localisation')
API_VERSION = 1
LABELS = {'user': 'Your algorithm',
          'bfs': 'BFS', 'dijkstra': 'Dijkstra', 'astar': 'A*', 'greedy': 'Greedy best-first',
          'weighted_astar': 'Weighted A*', 'dstar_lite': 'D* Lite', 'builtin': 'Waypoint driver',
          'dwa': 'DWA', 'rpp': 'Regulated Pure Pursuit', 'mppi': 'MPPI', 'mcl': 'MCL',
          'mcl_augmented': 'MCL + augmented injection', 'ekf': 'EKF'}
#: the worlds the browser ships; the CLI also accepts any World Spec in worlds/
WORLDS = ('coco_arena_v1', 'coco_arena_v2', 'coco_depot_v1', 'coco_depot_colours_v1',
          'coco_depot_clutter_v1')
BENCHMARKS = Path(__file__).parent / 'benchmarks'
LIMITS = {'algorithms': 8, 'scenarios': 1000, 'sweep_params': 2, 'sweep_values': 12,
          'sweep_points': 64, 'runs': 20000, 'max_ticks': 12000}
FETCH_RUSH_RULES, FETCH_RUSH_SEEDS, FETCH_RUSH_MODES = 5, (1, 2, 3, 4, 5, 6), ('phone', 'full')
FETCH_COLOUR_RULES, FETCH_COLOURS = 2, ('red', 'green', 'blue', 'yellow')
GAME_WORLDS = {'fetch_rush': 'coco_depot_v1', 'fetch_colour': 'coco_depot_colours_v1'}


class SpecError(ValueError):
    """An experiment spec this build cannot run as written."""


# -- parameters ----------------------------------------------------------------------------------

def _num(kind, default, lo=0.0, hi=math.inf, choices=None, doc=''):
    return {'type': kind, 'default': default, 'min': lo, 'max': hi, 'choices': choices,
            'doc': doc}


def _from_dataclass(prefix, dc, skip=()):
    out = {}
    for f in fields(dc):
        if f.name in skip:
            continue
        v = getattr(dc(), f.name)
        if isinstance(v, bool):
            continue
        if isinstance(v, tuple):
            out[f'{prefix}.{f.name}'] = _num('list', list(v), doc=f'{f.name} (list)')
        elif isinstance(v, int):
            out[f'{prefix}.{f.name}'] = _num('int', v, 1, 100000)
        elif isinstance(v, float):
            out[f'{prefix}.{f.name}'] = _num('float', v, -1e6, 1e6)
        elif isinstance(v, str):
            out[f'{prefix}.{f.name}'] = _num('str', v)
    return out


PARAMS = {
    'planning': {
        'inflation_radius': _num('float', 0.5, 0.0, 3.0, doc='Nav2 inflation radius (m)'),
        'cost_scaling_factor': _num('float', 10.0, 0.0, 100.0, doc='Nav2 cost scaling factor'),
        'robot_radius': _num('float', 0.25, 0.0, 1.0, doc='inscribed robot radius (m)'),
        'heuristic_weight': _num('float', 2.0, 1.0, 10.0, doc='weighted A* only'),
        'cost_weight': _num('float', 2.0, 0.0, 20.0,
                            doc='edge cost = base x (1 + cost_weight x cell cost / 252)'),
        'connectivity': _num('int', 8, 4, 8, choices=[4, 8], doc='grid moves'),
    },
    'control': dict({
        'planner': _num('str', 'astar', choices=list(PLANNERS), doc='global planner'),
        'window.robot_radius': _num('float', WindowParams().robot_radius, 0.0, 1.0),
        'window.inflation_radius': _num('float', WindowParams().inflation_radius, 0.0, 3.0),
        'window.cost_scaling_factor': _num('float', WindowParams().cost_scaling_factor, 0.0,
                                           200.0),
    }, **_from_dataclass('dwa', DWAParams), **_from_dataclass('rpp', RPPParams),
        **_from_dataclass('mppi', MPPIParams, skip=('emit',))),
    'localisation': dict(
        **{k: v for k, v in _from_dataclass('mcl', MCLParams).items()
           if k.split('.')[1] in loc_arena.MCL_KEYS and k != 'mcl.injection'},
        **{k: v for k, v in _from_dataclass('ekf', EKFParams).items()
           if k.split('.')[1] in loc_arena.EKF_KEYS}),
    'fulltask': {},
}
for _k, _v in PARAMS['localisation'].items():
    if _k.endswith('.init'):
        _v['choices'] = ['tracking', 'global']


def _applies(family: str, algo: str, key: str) -> bool:
    """Whether parameter ``key`` does anything for ``algo`` (others are refused)."""
    if key.startswith('user.'):
        return algo == USER
    if family == 'planning':
        return key != 'heuristic_weight' or algo == 'weighted_astar'
    if family == 'control':
        head = key.split('.')[0]
        return head in ('planner', 'window') or head == algo
    if family == 'localisation':
        if algo == USER:
            return False
        return key.startswith(('mcl.' if algo.startswith('mcl') else 'ekf.'))
    return False


def _check_user_param(key: str, value):
    """``user.<name>``: a parameter of the algorithm file (``ctx.params[name]``)."""
    name = key[5:]
    if not (name[:1].isalpha() and all(c.isalnum() or c == '_' for c in name)
            and len(name) <= 40):
        raise SpecError(f'{key}: user parameters are user.<letters, digits, _>')
    if isinstance(value, bool) or (isinstance(value, str) and len(value) <= 200):
        return value
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    if isinstance(value, list) and len(value) <= 64 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in value):
        return value
    raise SpecError(f'{key}: a number, a short string, true/false or a list of numbers')


def _check_param(family: str, algo: str, key: str, value):
    table = PARAMS[family]
    if key.startswith('user.') and algo == USER:
        return _check_user_param(key, value)
    if key not in table:
        raise SpecError(f'{family} has no parameter {key!r}')
    if not _applies(family, algo, key):
        raise SpecError(f'parameter {key!r} does nothing for {algo!r}')
    p = table[key]
    t = p['type']
    if t == 'list':
        if not isinstance(value, list) or len(value) != len(p['default']) or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in value):
            raise SpecError(f'{key} is a list of {len(p["default"])} finite numbers')
        return [float(v) for v in value]
    if t == 'str':
        if not isinstance(value, str):
            raise SpecError(f'{key} is a string')
        if p['choices'] and value not in p['choices']:
            raise SpecError(f'{key} is one of {p["choices"]}')
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SpecError(f'{key} must be a finite number')
    if t == 'int':
        if int(value) != value:
            raise SpecError(f'{key} must be an integer')
        value = int(value)
    else:
        value = float(value)
    if p['choices'] and value not in p['choices']:
        raise SpecError(f'{key} is one of {p["choices"]}')
    if not p['min'] <= value <= p['max']:
        raise SpecError(f'{key} must be in [{p["min"]}, {p["max"]}]')
    return value


def resolved_params(family: str, algo: str, given: Dict) -> Dict:
    """Return every parameter that applies to ``algo``: defaults, then ``given``."""
    out = {k: copy.deepcopy(p['default']) for k, p in PARAMS[family].items()
           if _applies(family, algo, k)}
    for k, v in given.items():
        out[k] = _check_param(family, algo, k, v)
    if family == 'planning' and out['inflation_radius'] < out['robot_radius']:
        raise SpecError('inflation_radius must cover robot_radius (Nav2)')
    return out


# -- metrics -------------------------------------------------------------------------------------

def _m(mid, label, unit, better, test=True, timing=False):
    return {'id': mid, 'label': label, 'unit': unit, 'better': better, 'test': test,
            'timing': timing}


METRICS = {
    'planning': [
        _m('expansions', 'Expansions', 'count', 'lower'),
        _m('pushes', 'Pushes', 'count', 'lower', test=False),
        _m('path_length_m', 'Path length', 'm', 'lower'),
        _m('path_cost', 'Path cost', 'cost', 'lower'),
        _m('path_steps', 'Path steps', 'cells', 'lower', test=False),
        _m('min_clearance_m', 'Minimum clearance', 'm', 'higher'),
        _m('mean_clearance_m', 'Mean clearance', 'm', 'higher'),
        _m('heading_change_rad', 'Total heading change', 'rad', 'lower'),
        _m('start_snap_m', 'Start snap', 'm', 'lower', test=False),
        _m('goal_snap_m', 'Goal snap', 'm', 'lower', test=False),
        _m('compute_ms', 'Compute time', 'ms', 'lower', timing=True),
    ],
    'control': [
        _m('time_s', 'Time to goal or end', 's', 'lower'),
        _m('ticks', 'Ticks', 'count', 'lower', test=False),
        _m('path_length_m', 'Distance driven', 'm', 'lower'),
        _m('min_clearance_m', 'Minimum clearance', 'm', 'higher'),
        _m('mean_clearance_m', 'Mean clearance', 'm', 'higher'),
        _m('heading_change_rad', 'Total heading change', 'rad', 'lower'),
        _m('contacts', 'Contacts', 'count', 'lower'),
        _m('expansions', 'Global planner expansions', 'count', 'lower', test=False),
        _m('plans', 'Plans made', 'count', 'lower', test=False),
        _m('final_goal_distance_m', 'Final distance to goal', 'm', 'lower'),
        _m('compute_ms', 'Compute time', 'ms', 'lower', timing=True),
    ],
    'fulltask': [
        _m('deliveries', 'Deliveries', 'count', 'higher'),
        _m('orders', 'Orders', 'count', 'higher', test=False),
        _m('contacts', 'Contacts', 'count', 'lower'),
        _m('net_deliveries', 'Net deliveries', 'count', 'higher'),
        _m('time_to_complete_s', 'Time to complete', 's', 'lower'),
        _m('time_used_s', 'Time used', 's', 'lower', test=False),
        _m('path_efficiency', 'Path efficiency', 'ratio', 'higher'),
        _m('ticks', 'Ticks', 'count', 'lower', test=False),
        _m('timer_s', 'Round timer', 's', 'lower', test=False),
        _m('compute_ms', 'Compute time', 'ms', 'lower', timing=True),
    ],
}
METRICS['localisation'] = METRICS['control'][:-1] + [
    _m('final_err_xy_m', 'Final position error', 'm', 'lower'),
    _m('final_err_yaw_rad', 'Final heading error', 'rad', 'lower'),
    _m('mean_err_xy_m', 'Mean position error', 'm', 'lower'),
    _m('max_err_xy_m', 'Maximum position error', 'm', 'lower'),
    _m('converged_s', 'Convergence time', 's', 'lower'),
    _m('recovery_s', 'Recovery time after kidnap', 's', 'lower'),
    _m('compute_ms', 'Compute time', 'ms', 'lower', timing=True),
]
STATUSES = {
    'planning': ('found', 'no_path', 'start_blocked', 'goal_blocked', 'collision',
                 'invalid_output', 'budget_exceeded', 'error'),
    'control': ('succeeded', 'no_path', 'invalid_path', 'no_valid_control',
                'failed_to_make_progress', 'timeout', 'stopped', 'error'),
    'localisation': ('localised', 'not_localised', 'timeout', 'no_path', 'error'),
    'fulltask': ('completed', 'incomplete', 'error'),
}


# -- worlds and suites ---------------------------------------------------------------------------

_WORLD_SPECS: Dict[str, Dict] = {}
_WORLDS: Dict[str, World] = {}


def register_world(world_id: str, spec: Dict) -> None:
    """Make a World Spec available by id (the browser passes the shipped files in)."""
    _WORLD_SPECS[world_id] = spec
    _WORLDS.pop(world_id, None)


def _world_dirs() -> List[Path]:
    dirs = []
    if os.environ.get('COCO_WORLDS'):
        dirs.append(Path(os.environ['COCO_WORLDS']))
    dirs.append(Path(__file__).resolve().parents[2] / 'worlds')
    dirs.append(Path.cwd() / 'worlds')
    return dirs


def world_spec(world_id: str) -> Dict:
    """Return a World Spec by id: registered, else ``worlds/<id>.json``."""
    if world_id not in _WORLD_SPECS:
        if not isinstance(world_id, str) or not world_id.replace('_', '').isalnum():
            raise SpecError(f'bad world id {world_id!r}')
        for d in _world_dirs():
            p = d / f'{world_id}.json'
            if p.is_file():
                _WORLD_SPECS[world_id] = json.loads(p.read_text(encoding='utf-8'))
                break
        else:
            raise SpecError(f'world {world_id!r} not found (set COCO_WORLDS to the worlds/ '
                            'directory)')
    return _WORLD_SPECS[world_id]


def world(world_id: str) -> World:
    """Return the shared :class:`World` for an id (built once)."""
    if world_id not in _WORLDS:
        _WORLDS[world_id] = World(world_spec(world_id))
    return _WORLDS[world_id]


def world_sha256(world_id: str) -> str:
    """Return the canonical sha256 of the world's normalized spec."""
    return hashlib.sha256(canonical(world(world_id).spec)).hexdigest()


def suites() -> List[str]:
    """Return the benchmark suite ids shipped with this build."""
    return sorted(p.name[:-len('.v0.json')] for p in BENCHMARKS.glob('*.v0.json'))


def suite(suite_id: str, version: int = 0) -> Dict:
    """Load a benchmark suite from ``benchmarks/<id>.v<version>.json``."""
    p = BENCHMARKS / f'{suite_id}.v{version}.json'
    if not suite_id.replace('-', '').isalnum() or not p.is_file():
        raise SpecError(f'no benchmark suite {suite_id!r} v{version}; have {suites()}')
    return json.loads(p.read_text(encoding='utf-8'))


# -- the spec ------------------------------------------------------------------------------------

def spec_id(spec: Dict) -> str:
    """Return the experiment's id: the sha256 of its canonical spec (first 16 hex digits)."""
    return hashlib.sha256(canonical(spec)).hexdigest()[:16]


#: what an inline scenario may hold (ADR 0014; COCO-Bench v1's conditions included)
INLINE_KEYS = {'id', 'start', 'goal', 'seed', 'config', 'kidnap_at_s', 'kidnap'}


def _inline(w, scen) -> List[Dict]:
    """Check explicit scenarios (``scenarios.kind == 'inline'``); return them as given."""
    if not isinstance(scen, list) or not 1 <= len(scen) <= LIMITS['scenarios']:
        raise SpecError(f'inline scenarios: a list of 1 to {LIMITS["scenarios"]}')
    out, ids = [], set()

    def point(v, n):
        return (isinstance(v, list) and len(v) == n and
                all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                    for x in v))
    for i, s in enumerate(scen):
        if not isinstance(s, dict) or set(s) - INLINE_KEYS:
            raise SpecError(f'inline scenario {i}: only {sorted(INLINE_KEYS)}')
        sid = s.get('id')
        if not (isinstance(sid, str) and 1 <= len(sid) <= 40 and sid not in ids):
            raise SpecError(f'inline scenario {i}: a unique id of 1 to 40 characters')
        ids.add(sid)
        if not (point(s.get('start'), 3) and point(s.get('goal'), 2)):
            raise SpecError(f'inline scenario {sid}: start [x, y, theta] and goal [x, y]')
        seed = s.get('seed')
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < (1 << 63):
            raise SpecError(f'inline scenario {sid}: seed is an integer in [0, 2**63)')
        for name in ('start', 'goal'):
            if w.lab_map.cell_at(*s[name][:2]) is None:
                raise SpecError(f'inline scenario {sid}: {name} is off the map')
        if 'kidnap' in s and not point(s['kidnap'], 2):
            raise SpecError(f'inline scenario {sid}: kidnap [x, y]')
        if 'kidnap_at_s' in s and not (point([s['kidnap_at_s']], 1) and 0.1 <= s['kidnap_at_s'] <= 1000):
            raise SpecError(f'inline scenario {sid}: kidnap_at_s is 0.1 to 1000 s')
        cfg = s.get('config', [])
        if not (isinstance(cfg, list) and len(cfg) <= 8 and
                all(isinstance(c, str) and 1 <= len(c) <= 80 for c in cfg)):
            raise SpecError(f'inline scenario {sid}: config is up to 8 strings of 1 to 80 characters')
        out.append(dict(s))
    return out


def _rounds(sc: Dict) -> List[Dict]:
    game = sc.get('game')
    if game == 'fetch_rush':
        rounds = sc.get('rounds') or [{'seed': s, 'mode': m}
                                      for m in FETCH_RUSH_MODES for s in FETCH_RUSH_SEEDS]
        out = []
        for r in rounds:
            if r.get('seed') not in FETCH_RUSH_SEEDS or r.get('mode') not in FETCH_RUSH_MODES:
                raise SpecError('Fetch Rush rounds exist for seeds 1-6 in phone and full mode '
                                '(the committed rounds, R1 v0)')
            out.append({'id': f'fr_{r["mode"]}_{r["seed"]}', 'game': game, 'round': r['seed'],
                        'mode': r['mode'], 'rules': FETCH_RUSH_RULES})
        return out
    if game == 'fetch_colour':
        colours = sc.get('colours') or list(FETCH_COLOURS)
        if any(c not in FETCH_COLOURS for c in colours):
            raise SpecError(f'Fetch by colour has rods {list(FETCH_COLOURS)}')
        return [{'id': f'colour_{c}', 'game': game, 'colour': c, 'rules': FETCH_COLOUR_RULES}
                for c in colours]
    raise SpecError("rounds need game 'fetch_rush' or 'fetch_colour'")


def plan(spec: Dict) -> Dict:
    """
    Validate ``spec`` and return ``{spec, id, world_sha256, scenarios, scenario_info, runs}``.

    ``spec`` comes back with its defaults filled (the canonical form a link and
    an export carry); ``runs`` is the ordered list of run descriptors.
    """
    if not isinstance(spec, dict) or spec.get('schema') != SCHEMA:
        raise SpecError(f'an experiment spec has schema {SCHEMA!r}')
    model = spec.get('model', MODEL)
    if model != MODEL:
        raise SpecError(f'this build runs experiments under {MODEL}, not {model}')
    family = spec.get('family')
    if family not in FAMILIES:
        raise SpecError(f'family is one of {FAMILIES}')
    sc = dict(spec.get('scenarios') or {})
    kind = sc.get('kind')
    world_id = spec.get('world')
    if family == 'fulltask':
        if kind == 'suite':
            st = suite(sc['id'], sc.get('version', 0))
            sc = dict(st['scenarios_spec'], kind='rounds')
        if kind not in ('rounds', 'suite'):
            raise SpecError('a full-task experiment plays rounds (or the colour-fetch suite)')
        world_id = world_id or GAME_WORLDS.get(sc.get('game'))
        if world_id != GAME_WORLDS.get(sc.get('game')):
            raise SpecError(f'{sc.get("game")} is played on {GAME_WORLDS.get(sc.get("game"))}')
    if not isinstance(world_id, str):
        raise SpecError('world is a World Spec id, e.g. coco_depot_v1')
    w = world(world_id)
    algos = spec.get('algorithms') or []
    if not 1 <= len(algos) <= LIMITS['algorithms']:
        raise SpecError(f'1 to {LIMITS["algorithms"]} algorithms')
    sweep = spec.get('sweep') or {'params': []}
    sp = sweep.get('params') or []
    if len(sp) > LIMITS['sweep_params']:
        raise SpecError('a sweep varies one or two parameters')
    points = [{}]
    for p in sp:
        vals = p.get('values') or []
        if not 1 <= len(vals) <= LIMITS['sweep_values']:
            raise SpecError(f'a swept parameter has 1 to {LIMITS["sweep_values"]} values')
        points = [dict(pt, **{p['name']: v}) for pt in points for v in vals]
    if len(points) > LIMITS['sweep_points']:
        raise SpecError(f'at most {LIMITS["sweep_points"]} sweep points')
    ids, resolved_algos = set(), []
    for a in algos:
        name = a.get('name')
        user = {}
        if name == USER:
            if family not in USER_FAMILIES:
                raise SpecError(f'a {family} experiment runs the built-ins only '
                                f'(algorithm files: {", ".join(USER_FAMILIES)})')
            sha = a.get('code_sha256')
            if not (isinstance(sha, str) and len(sha) == 64
                    and all(c in '0123456789abcdef' for c in sha)):
                raise SpecError('an algorithm file is named by its code_sha256 (64 hex digits)')
            if a.get('api', API_VERSION) != API_VERSION:
                raise SpecError(f'this build runs algorithm API {API_VERSION}, '
                                f'not {a.get("api")}')
            user = {'api': API_VERSION, 'code_sha256': sha}
        elif name not in ALGORITHMS[family]:
            raise SpecError(f'{family} algorithms: {list(ALGORITHMS[family])}')
        aid = a.get('id') or name
        if aid in ids:
            raise SpecError(f'two algorithms are called {aid!r}: give each an id')
        ids.add(aid)
        given = dict(a.get('params') or {})
        per_point = []
        for pt in points:
            merged = dict(given)
            for k, v in pt.items():
                if _applies(family, name, k):
                    merged[k] = v
                elif k not in PARAMS[family] and not k.startswith('user.'):
                    raise SpecError(f'{family} has no parameter {k!r} to sweep')
            per_point.append(resolved_params(family, name, merged))
        resolved_algos.append(dict({'id': aid, 'name': name,
                                    'label': a.get('label') or LABELS[name],
                                    'params': per_point[0] if not sp else given,
                                    '_per_point': per_point}, **user))
    seed = spec.get('seed', 1)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < (1 << 63):
        raise SpecError('seed is an integer in [0, 2**63)')
    info = {'kind': kind}
    try:
        if family == 'fulltask':
            scenarios = _rounds(sc)
        elif kind == 'sampled':
            n = sc.get('n', 20)
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= LIMITS['scenarios']:
                raise SpecError(f'n is 1 to {LIMITS["scenarios"]}')
            got = sample_pairs(w, n, sc.get('seed', seed), sc.get('min_separation_m', 2.0),
                               sc.get('min_clearance_m', 0.35), sc.get('zones'),
                               sc.get('stratify', 'none'), sc.get('require_reachable', True))
            scenarios = got['scenarios']
            info.update(rejected_unreachable=got['rejected_unreachable'],
                        rejected_separation=got['rejected_separation'])
        elif kind == 'suite':
            st = suite(sc['id'], sc.get('version', 0))
            if st['world'] != world_id:
                raise SpecError(f'suite {sc["id"]} is on {st["world"]}, not {world_id}')
            if family not in st['families']:
                raise SpecError(f'suite {sc["id"]} is for {st["families"]}, not {family}')
            scenarios = st['scenarios']
            info.update(suite=st['id'], suite_version=st['version'])
        elif kind == 'pairs':
            pairs = sc.get('pairs') or []
            if not 1 <= len(pairs) <= LIMITS['scenarios']:
                raise SpecError(f'1 to {LIMITS["scenarios"]} hand-placed pairs')
            scenarios = hand_pairs(w, pairs, sc.get('seed', seed))
        elif kind == 'inline':
            # R3 (ADR 0014): explicit scenarios -- a held-out file, run exactly as written
            scenarios = _inline(w, sc.get('scenarios'))
        else:
            raise SpecError("scenarios.kind is 'sampled', 'suite', 'pairs' or 'inline'")
    except ScenarioError as e:
        raise SpecError(str(e)) from None
    max_ticks = (spec.get('limits') or {}).get('max_ticks', 3000)
    if isinstance(max_ticks, bool) or not isinstance(max_ticks, int) or \
            not 10 <= max_ticks <= LIMITS['max_ticks']:
        raise SpecError(f'limits.max_ticks is 10 to {LIMITS["max_ticks"]}')
    options = dict(spec.get('options') or {})
    if family == 'localisation' and options.get('kidnap_at_s') is not None:
        k = options['kidnap_at_s']
        if isinstance(k, bool) or not isinstance(k, (int, float)) or not 0.1 <= k <= 1000:
            raise SpecError('options.kidnap_at_s is 0.1 to 1000 s')
    n_runs = len(points) * len(resolved_algos) * len(scenarios)
    if n_runs > LIMITS['runs']:
        raise SpecError(f'{n_runs} runs: at most {LIMITS["runs"]}')
    metric_ids = [m['id'] for m in METRICS[family]]
    shown = spec.get('metrics') or metric_ids
    if any(m not in metric_ids for m in shown):
        raise SpecError(f'{family} metrics: {metric_ids}')
    sc_full = dict(spec.get('scenarios') or {})
    if kind == 'sampled':
        sc_full = {'kind': 'sampled', 'n': sc.get('n', 20), 'seed': sc.get('seed', seed),
                   'min_separation_m': sc.get('min_separation_m', 2.0),
                   'min_clearance_m': sc.get('min_clearance_m', 0.35),
                   'zones': sc.get('zones'), 'stratify': sc.get('stratify', 'none'),
                   'require_reachable': sc.get('require_reachable', True)}
    full = {'schema': SCHEMA, 'title': spec.get('title', ''), 'world': world_id,
            'family': family, 'seed': seed, 'model': dict(MODEL),
            'algorithms': [{k: v for k, v in a.items() if k != '_per_point'}
                           for a in resolved_algos],
            'scenarios': sc_full, 'sweep': {'params': sp},
            'limits': {'max_ticks': max_ticks}, 'options': options, 'metrics': shown}
    if spec.get('notes'):
        full['notes'] = spec['notes']
    wsha = world_sha256(world_id)
    if spec.get('world_sha256') not in (None, wsha):
        raise SpecError(f'world {world_id} differs from the one this experiment was made on')
    full['world_sha256'] = wsha
    eid = spec_id(full)
    runs = []
    for pi, pt in enumerate(points):
        for ai, a in enumerate(resolved_algos):
            for si, s in enumerate(scenarios):
                d = {'experiment': eid, 'index': len(runs), 'world': world_id,
                     'world_sha256': wsha, 'family': family, 'sweep_index': pi,
                     'sweep': pt, 'algorithm': a['id'], 'name': a['name'],
                     'params': a['_per_point'][pi], 'scenario_index': si,
                     'scenario': s, 'max_ticks': max_ticks, 'options': options}
                if a['name'] == USER:
                    # only a user's descriptor carries these: every built-in's chain is unchanged
                    d['api'], d['code_sha256'] = a['api'], a['code_sha256']
                runs.append(d)
    return {'spec': full, 'id': eid, 'world_sha256': wsha, 'scenarios': scenarios,
            'scenario_info': info, 'sweep_points': points, 'runs': runs}


# -- running -------------------------------------------------------------------------------------

def _run(desc: Dict, sink=None, on_tick=None, on_event=None) -> Dict:
    w = world(desc['world'])
    fam, name, params, sc = desc['family'], desc['name'], desc['params'], desc['scenario']
    if fam == 'planning':
        return run_planning(w, sc, name, params, desc, sink, on_event)
    if fam == 'control':
        return run_control(w, sc, name, params, desc, desc['max_ticks'], on_tick, on_event)
    if fam == 'localisation':
        kid = desc['options'].get('kidnap_at_s')
        if kid is None:   # R3: a v1 kidnap scenario carries its own
            kid = sc.get('kidnap_at_s')
        return run_localisation(w, sc, name, params, desc, desc['max_ticks'], kid, on_tick,
                                on_event)
    return run_fulltask(w, sc, name, params, desc)


def run_one(desc: Dict, sink=None, on_tick=None, on_event=None, twice: bool = True) -> Dict:
    """
    Run one descriptor from :func:`plan`; return its record (an error is a recorded result).

    ``sink`` (planning) sees every search event row and ``on_tick(arena, tick)`` (control,
    localisation) every tick, for Compare's replay of the run; neither changes the run.
    ``on_event(kind, data)`` sees an algorithm file's ``ctx.emit`` thinking. An algorithm
    file's run is run ``twice`` (unless told not to) and its record says whether the two
    chains agree (``deterministic``): ADR 0012's determinism check.
    """
    fam, name, sc = desc['family'], desc['name'], desc['scenario']
    try:
        r = _run(desc, sink, on_tick, on_event)
        if name == USER and twice:
            again = _run(desc)
            r['deterministic'] = again['chain'] == r['chain'] and \
                again['status'] == r['status']
    except (ValueError, KeyError) as e:
        h = hashlib.sha256(b'coco.experiment.run.v1')
        h.update(canonical(desc))
        h.update(f'error: {e}'.encode())
        r = {'status': 'error', 'success': False,
             'metrics': {m['id']: None for m in METRICS[fam]}, 'chain': h.hexdigest(),
             'fail_tick': None, 'error': str(e)}
    out = {'index': desc['index'], 'sweep_index': desc['sweep_index'], 'sweep': desc['sweep'],
           'algorithm': desc['algorithm'], 'name': name, 'scenario': sc['id'],
           'scenario_index': desc['scenario_index']}
    out.update(r)
    return out


def counts(record: Dict) -> Dict:
    """Return a record's device-independent metrics (everything but the timings)."""
    return {k: v for k, v in record['metrics'].items() if k not in TIMING_METRICS}


def digest(records: List[Dict]) -> str:
    """Return the experiment digest: sha256 over every run's index, status, chain and counts."""
    h = hashlib.sha256(DIGEST_TAG)
    for r in sorted(records, key=lambda r: r['index']):
        h.update(canonical([r['index'], r['status'], r['chain'], counts(r)]))
    return h.hexdigest()


def run_all(p: Dict, progress=None) -> List[Dict]:
    """Run every descriptor of a plan in order, in this process."""
    out = []
    for d in p['runs']:
        out.append(run_one(d))
        if progress is not None:
            progress(len(out), len(p['runs']))
    return out


# -- summaries -----------------------------------------------------------------------------------

def summarise(p: Dict, records: List[Dict]) -> Dict:
    """
    Return per-group statistics and paired comparisons (see the module).

    Groups are (sweep point, algorithm). Pairs are formed on scenarios both
    algorithms ran at the same sweep point; a metric undefined in either run of
    a pair (e.g. path length when no path was found) excludes that pair, and
    the exclusions are counted. Holm's adjustment runs over the algorithm pairs
    of one metric at one sweep point.
    """
    fam = p['spec']['family']
    mdefs = METRICS[fam]
    algos = [a['id'] for a in p['spec']['algorithms']]
    by = {}
    for r in records:
        by.setdefault((r['sweep_index'], r['algorithm']), {})[r['scenario_index']] = r
    groups = []
    for pi, pt in enumerate(p['sweep_points']):
        for aid in algos:
            rs = [by.get((pi, aid), {})[k] for k in sorted(by.get((pi, aid), {}))]
            n = len(rs)
            k = sum(1 for r in rs if r['success'])
            status = {}
            for r in rs:
                status[r['status']] = status.get(r['status'], 0) + 1
            metrics = {m['id']: dict(exp_stats.describe([r['metrics'].get(m['id']) for r in rs]),
                                     timing=m['timing']) for m in mdefs}
            groups.append({'sweep_index': pi, 'sweep': pt, 'algorithm': aid, 'n': n,
                           'successes': k, 'success': exp_stats.wilson(k, n),
                           'status': status, 'metrics': metrics})
    paired = []
    if len(algos) >= 2:
        for pi in range(len(p['sweep_points'])):
            pairs = [(algos[i], algos[j]) for i in range(len(algos))
                     for j in range(i + 1, len(algos))]
            block = []
            for a, b in pairs:
                ra, rb = by.get((pi, a), {}), by.get((pi, b), {})
                shared = sorted(set(ra) & set(rb))
                if not shared:
                    continue
                row = {'sweep_index': pi, 'a': a, 'b': b, 'n_shared': len(shared),
                       'success': exp_stats.mcnemar([ra[s]['success'] for s in shared],
                                                    [rb[s]['success'] for s in shared]),
                       'metrics': {}}
                for m in mdefs:
                    if not m['test']:
                        continue
                    row['metrics'][m['id']] = dict(
                        exp_stats.wilcoxon([ra[s]['metrics'].get(m['id']) for s in shared],
                                           [rb[s]['metrics'].get(m['id']) for s in shared]),
                        timing=m['timing'])
                block.append(row)
            keys = ['success'] + [m['id'] for m in mdefs if m['test']]
            for key in keys:
                tests = [row['success'] if key == 'success' else row['metrics'][key]
                         for row in block]
                adj = exp_stats.holm([t['p'] for t in tests])
                for t, q in zip(tests, adj):
                    t['p_holm'] = q if len(block) > 1 else t['p']
                    t['verdict'] = exp_stats.verdict(t['p_holm'])
            paired.extend(block)
    complete = len(records) == len(p['runs'])
    return {'schema': 'coco.experiment.summary.v1', 'experiment': p['id'],
            'family': fam, 'n_runs': len(records), 'n_planned': len(p['runs']),
            'complete': complete, 'digest': digest(records), 'alpha': exp_stats.ALPHA,
            'metrics': mdefs, 'groups': groups, 'paired': paired,
            'scenario_info': p['scenario_info'],
            'notes': ['Counts are model outputs and need no device; compute_ms is wall time on '
                      'the device named in the manifest.',
                      'Success rates: Wilson 95% intervals. Metrics: median and IQR (type-7 '
                      'quantiles) over the runs where the metric is defined.',
                      'Paired tests on shared scenarios: Wilcoxon signed-rank (exact up to 50 '
                      'non-zero pairs) with rank-biserial r and Hodges-Lehmann shift; McNemar '
                      'exact for success; Holm-adjusted across algorithm pairs.']}


# -- exports -------------------------------------------------------------------------------------

def plain(x):
    """
    Write integral floats as ints, everywhere in ``x`` (as :func:`canonical` does).

    A record that crossed JavaScript (the browser's workers) comes back with ``2.0``
    as ``2`` and ``-0.0`` as ``0``; exporting the plain form makes every host's files
    byte-identical.
    """
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    return x


def _cell(v) -> str:
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    s = repr(v) if isinstance(v, float) else str(v)
    if any(c in s for c in ',"\n\r'):
        s = '"' + s.replace('"', '""') + '"'
    return s


def results_csv(p: Dict, records: List[Dict]) -> str:
    """Return results.csv: one row per run (failures and timeouts included), every metric."""
    fam = p['spec']['family']
    sweep_names = [x['name'] for x in p['spec']['sweep']['params']]
    mids = [m['id'] for m in METRICS[fam]]
    head = (['run', 'sweep_index'] + sweep_names + ['algorithm', 'name', 'scenario'])
    if fam == 'fulltask':
        head += ['game', 'round']
    else:
        head += ['start_x', 'start_y', 'start_theta', 'goal_x', 'goal_y', 'start_zone',
                 'goal_zone', 'seed']
    head += ['status', 'success'] + mids + ['fail_tick', 'chain']
    rows = [','.join(head)]
    for r in sorted(records, key=lambda r: r['index']):
        sc = p['scenarios'][r['scenario_index']]
        row = [r['index'], r['sweep_index']] + [r['sweep'].get(n) for n in sweep_names]
        row += [r['algorithm'], r['name'], r['scenario']]
        if fam == 'fulltask':
            row += [sc['game'], sc.get('round', sc.get('colour'))]
            if 'mode' in sc:
                row[-1] = f'{sc["mode"]}_{sc["round"]}'
        else:
            row += [sc['start'][0], sc['start'][1], sc['start'][2], sc['goal'][0], sc['goal'][1],
                    sc.get('start_zone'), sc.get('goal_zone'), sc['seed']]
        row += [r['status'], r['success']] + [r['metrics'].get(m) for m in mids]
        row += [r.get('fail_tick'), r['chain']]
        rows.append(','.join(_cell(v) for v in row))
    return '\n'.join(rows) + '\n'


def manifest(p: Dict, records: List[Dict], files: Dict[str, bytes], host: Dict) -> Dict:
    """Return manifest.json: versions, hashes, checksums of the files, device and conditions."""
    return {'schema': 'coco.experiment.manifest.v1', 'experiment': p['id'],
            'spec_sha256': hashlib.sha256(canonical(p['spec'])).hexdigest(),
            'digest': digest(records), 'model': dict(MODEL), 'evidence': 'MODEL',
            'world': p['spec']['world'], 'world_sha256': p['world_sha256'],
            'n_runs': len(records), 'n_planned': len(p['runs']),
            'complete': len(records) == len(p['runs']),
            'files': {k: {'sha256': hashlib.sha256(v).hexdigest(), 'bytes': len(v)}
                      for k, v in sorted(files.items())},
            'host': host,
            'timing_note': 'compute_ms is wall time on this host; counts are device-independent'}


def export(p: Dict, records: List[Dict], host: Dict) -> Dict[str, bytes]:
    """Return the export set ``{name: bytes}`` (results, summary, spec, runs, manifest)."""
    records = plain([dict(r, report=_portable_report(r['report'])) if r.get('report') else r
                     for r in records])
    files = {
        'spec.json': (json.dumps(plain(p['spec']), indent=1, sort_keys=True) + '\n').encode(),
        'results.csv': results_csv(p, records).encode(),
        'summary.json': (json.dumps(plain(summarise(p, records)), indent=1, sort_keys=True,
                                    allow_nan=False) + '\n').encode(),
        'runs.jsonl': ''.join(
            json.dumps({k: v for k, v in r.items() if k != 'record'}, sort_keys=True,
                       separators=(',', ':')) + '\n'
            for r in sorted(records, key=lambda r: r['index'])).encode(),
    }
    for a in p['spec']['algorithms']:
        if a['name'] == USER:
            from . import exp_user
            files[f'algorithms/{a["id"]}.py'] = exp_user.source(a['code_sha256']).encode()
    files['manifest.json'] = (json.dumps(plain(manifest(p, records, files, host)), indent=1,
                                         sort_keys=True) + '\n').encode()
    return files


def _portable_report(report: Dict) -> Dict:
    """Return a run's validation report without its wall times (an export is the same anywhere)."""
    return {k: v for k, v in report.items()
            if k not in ('call_ms_max', 'call_ms_total', 'max_call_index')}


# -- the command line ----------------------------------------------------------------------------

def _load_spec(path: str) -> Dict:
    if path.endswith(('.yaml', '.yml')):
        # coco_lab is standard library only: `coco experiment run` (lab_web/tools/coco.mjs)
        # and the Workbench read YAML and hand this JSON
        raise SystemExit('give the spec as JSON here; `coco experiment run spec.yaml` (the '
                         'Node command) and the Workbench accept YAML')
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _host(workers: int) -> Dict:
    import platform
    import subprocess
    try:
        sha = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True,
                             cwd=Path(__file__).parent, timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        sha = None
    cpu = platform.processor() or platform.machine()
    try:
        with open('/proc/cpuinfo', encoding='utf-8') as f:
            cpu = next((ln.split(':', 1)[1].strip() for ln in f if ln.startswith('model name')),
                       cpu)
    except OSError:
        pass
    return {'runner': 'cpython', 'python': platform.python_version(), 'platform':
            platform.platform(), 'cpu': cpu, 'workers': workers, 'git': sha}


def add_algorithms(spec: Dict, files: List[str]) -> Dict[str, str]:
    """
    Register algorithm files for ``spec``; return ``{sha256: source}``.

    A file whose sha256 a ``user`` entry already names fills it; any other file is
    appended as a new ``user`` entry (its id the file's name). Every ``user`` entry
    must then have its file.
    """
    from . import exp_user
    codes = {}
    algos = spec.setdefault('algorithms', [])
    named = {a.get('code_sha256') for a in algos if a.get('name') == USER}
    for f in files:
        src = Path(f).read_text(encoding='utf-8')
        sha = exp_user.register(src)
        codes[sha] = src
        if sha not in named:
            algos.append({'name': USER, 'id': Path(f).stem, 'label': Path(f).stem, 'api':
                          API_VERSION, 'code_sha256': sha})
    missing = [a.get('id') for a in algos
               if a.get('name') == USER and a.get('code_sha256') not in codes]
    if missing:
        raise SpecError(f'no --algorithm file for {missing} (matched by code_sha256)')
    return codes


def _pool_run(p: Dict, workers: int, codes: Optional[Dict[str, str]] = None) -> List[Dict]:
    codes = codes or {}
    if codes:
        # user code: str hashes (set order) must not depend on the process (ADR 0012)
        os.environ['PYTHONHASHSEED'] = '0'
        workers = max(1, workers)
    elif workers <= 1:
        return run_all(p, lambda i, n: print(f'\r{i}/{n}', end='', flush=True))
    import multiprocessing as mp
    out = []
    ctx = mp.get_context('spawn')
    with ctx.Pool(workers, initializer=_init_worker,
                  initargs=(dict(_WORLD_SPECS), codes)) as pool:
        for r in pool.imap_unordered(run_one, p['runs'], chunksize=1):
            out.append(r)
            print(f'\r{len(out)}/{len(p["runs"])}', end='', flush=True)
    print()
    return sorted(out, key=lambda r: r['index'])


def _init_worker(specs, codes=None):
    for k, v in specs.items():
        register_world(k, v)
    if codes:
        from . import exp_user
        for src in codes.values():
            exp_user.register(src)


def main(argv: Optional[List[str]] = None) -> int:
    """``python -m coco_lab.experiments run|verify|summarise ...``."""
    import argparse
    import time
    ap = argparse.ArgumentParser(prog='coco experiment',
                                 description='Run COCO Lab experiments natively (R1).')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run', help='run a spec; write the export set to --out')
    r.add_argument('spec')
    r.add_argument('--algorithm', action='append', default=[], metavar='FILE.py',
                   help='an algorithm file (coco_lab.api): added to the spec as "user" '
                        '(or matched to a "user" entry by its code_sha256)')
    r.add_argument('--out', required=True)
    r.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    r.add_argument('--worlds', help="the worlds/ directory (default: the repository's)")
    v = sub.add_parser('verify', help="re-run an export's runs and compare chains and counts")
    v.add_argument('dir')
    v.add_argument('--sample', type=float, default=1.0, help='fraction of runs (default all)')
    v.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    v.add_argument('--worlds')
    s = sub.add_parser('summarise', help="print an export's summary")
    s.add_argument('dir')
    a = ap.parse_args(argv)
    if getattr(a, 'worlds', None):
        os.environ['COCO_WORLDS'] = a.worlds
    if a.cmd == 'summarise':
        summ = json.loads((Path(a.dir) / 'summary.json').read_text())
        for g in summ['groups']:
            sr = g['success']
            print(f"{g['algorithm']:>16} sweep {g['sweep_index']} N={g['n']} success "
                  f"{g['successes']}/{g['n']}" + (f" [{sr['low']:.3f}, {sr['high']:.3f}]"
                                                  if sr else ''))
        print('digest', summ['digest'])
        return 0
    if a.cmd == 'run':
        spec = _load_spec(a.spec)
        codes = add_algorithms(spec, a.algorithm)
        p = plan(spec)
        for wid in {p['spec']['world']}:
            world_spec(wid)
        print(f'experiment {p["id"]}: {len(p["runs"])} runs, {a.workers} worker(s)')
        t0 = time.time()
        records = _pool_run(p, a.workers, codes)
        host = dict(_host(a.workers), wall_s=round(time.time() - t0, 3))
        files = export(p, records, host)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (out / name).parent.mkdir(parents=True, exist_ok=True)
            (out / name).write_bytes(data)
        print(f'digest {digest(records)}  ({host["wall_s"]} s)  -> {out}')
        return 0
    d = Path(a.dir)
    spec = json.loads((d / 'spec.json').read_text())
    codes = {}
    for f in sorted(d.glob('algorithms/*.py')):
        from . import exp_user
        src = f.read_text(encoding='utf-8')
        codes[exp_user.register(src)] = src
    p = plan(spec)
    want = {}
    for ln in (d / 'runs.jsonl').read_text().splitlines():
        rec = json.loads(ln)
        want[rec['index']] = rec
    idx = sorted(want)
    if a.sample < 1.0:
        from .rng import Rng
        rng = Rng(int(spec.get('seed', 1)))
        k = max(1, round(len(idx) * a.sample))
        pool = list(idx)
        idx = sorted(pool.pop(rng.randrange(len(pool))) for _ in range(k))
    sub_plan = dict(p, runs=[p['runs'][i] for i in idx])
    got = _pool_run(sub_plan, a.workers, codes)
    bad = [g['index'] for g in got
           if g['chain'] != want[g['index']]['chain'] or counts(g) != counts(want[g['index']])]
    print(f'verified {len(got)} run(s): {len(got) - len(bad)} match, {len(bad)} differ'
          + (f' {bad[:10]}' if bad else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
