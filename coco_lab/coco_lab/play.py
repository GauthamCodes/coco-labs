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
Play (M3.5): five challenges, each scored by a robotics metric.

One implementation, run three ways: by the page (the Arena worker, in
Pyodide), by ``coco verify`` (Pyodide in Node, lab_web/tools/verify.mjs)
and by the tests (CPython). A **submission** is::

    {'v': 1, 'challenge': ID, 'level': ID, 'level_hash': HEX, 'inputs': [...]}

and :func:`score` is a pure function of the submission, its level and, for
the map challenge, the World Spec: no random draw, no wall time. The
learner's inputs are the whole input log, so a challenge link (spec hash +
input log) reproduces a score exactly.

**Stars come from reference algorithms**, computed once per level by
:func:`references` (lab_web/tools/make_play_levels.py writes them into the
level, docs/v2/CHALLENGES.md publishes them; the tests re-derive them).

=====================  ===============================  ====================================
challenge              score (named metrics)            stars from
=====================  ===============================  ====================================
beat-the-planner       your cost / optimal cost         A* (optimal), weighted A*, greedy
next-node              A*'s next 10 expansions matched  A* itself, min-h and min-g predictors
search-the-bays        E[cost] of your order / optimal  the optimal order, nearest-first and
                       E[cost] -- from the prior, never most-likely-first
                       the sampled outcome
map-the-arena          map F1 and ATE within a          two reference drives: the tour, and
                       path-length budget               out and back
case-file-detective    |your tick - the divergence|     the stated tolerance bands around
                       in seconds                       src/arena/moments.ts's answer
=====================  ===============================  ====================================

**Computation is counted in expansions**, within this one implementation,
never wall time.
"""

import hashlib
import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .grid import Grid
from .search import search_events, collect
from .trace import EXPAND, PUSH, RELAX

SCHEMA = 'coco_lab.play.v1'
LEVELS_SCHEMA = 'coco_lab.play.levels.v1'
CHALLENGES = ('beat-the-planner', 'next-node', 'search-the-bays',
              'map-the-arena', 'case-file-detective')
#: two floats this close are the same number (a sum taken in another order)
EPS = 1e-9
#: a cost-layer digit d costs d * COST_PER_DIGIT: '9' is the cost layer's scale
COST_PER_DIGIT = 28.0
#: Next node: how many expansions the learner predicts
NEXT_N = 10
#: what a map-the-arena input log may hold (no kidnap, no reset, and no
#: config line but the level's own, in order, before the first drive input)
MAP_KINDS = ('goal', 'teleop', 'stop', 'planner')
#: the most cells a drawn path may have, and the most inputs a log may have
MAX_PATH = 4096
MAX_INPUTS = 20000


class PlayError(ValueError):
    """A level or a submission that is not well formed."""


# -- hashing ------------------------------------------------------------------

def canonical(obj) -> bytes:
    """Return the canonical JSON bytes of ``obj`` (sorted keys, no spaces)."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def level_hash(level: Dict[str, object]) -> str:
    """Return the sha256 of a level's canonical bytes: a link names it."""
    return hashlib.sha256(canonical(level)).hexdigest()


def _r(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(float(v), 9)


def _finish(result: Dict[str, object]) -> Dict[str, object]:
    result['hash'] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def _metric(name: str, value, unit: str, meaning: str) -> Dict[str, object]:
    if isinstance(value, float):
        value = _r(value)
    return {'name': name, 'value': value, 'unit': unit, 'meaning': meaning}


def _stars(passed: Sequence[bool]) -> int:
    """Stars = how many of the thresholds, easiest first, were met in a row."""
    n = 0
    for p in passed:
        if not p:
            break
        n += 1
    return n


# -- grid levels (beat the planner, next node) ----------------------------------

def parse_grid(rows: Sequence[str]) -> Tuple[Grid, Dict[str, Tuple[int, int]]]:
    """
    Build a level's grid from its ASCII rows.

    ``#`` is blocked, ``.`` free, a digit ``d`` free with cost
    ``d * COST_PER_DIGIT`` (so ``9`` doubles-plus-one a move's length at the
    default weight), a letter is a free cell it names (``S``, ``G``).
    8-connected, no corner cutting: coco_lab.grid's defaults.
    """
    rows = [str(r) for r in rows]
    if not rows or any(len(r) != len(rows[0]) for r in rows):
        raise PlayError('a level grid has equal-length rows')
    blocked, cost, marks = [], [], {}
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            blocked.append(ch == '#')
            cost.append(int(ch) * COST_PER_DIGIT if ch.isdigit() else 0.0)
            if ch.isalpha():
                if ch in marks:
                    raise PlayError(f'{ch} marks two cells')
                marks[ch] = (r, c)
    has_cost = any(cost)
    return Grid(len(rows[0]), len(rows), blocked,
                cost if has_cost else None), marks


def _plan(grid, s, g, algorithm, weight=None):
    res = collect(search_events(grid, s, g, algorithm, 'octile', weight))
    if res.trace.summary['status'] != 'found':
        raise PlayError('a level whose goal cannot be reached')
    return res.trace.summary


def _cells(inputs) -> List[Tuple[int, int]]:
    out = []
    for c in inputs:
        if not (isinstance(c, (list, tuple)) and len(c) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) for v in c)):
            raise PlayError(f'{c!r} is not a cell [row, col]')
        out.append((c[0], c[1]))
    return out


def beat_references(level) -> Dict[str, object]:
    """A*'s optimal cost and expansions; weighted A*'s and greedy's costs."""
    grid, m = parse_grid(level['grid'])
    a = _plan(grid, m['S'], m['G'], 'astar')
    w = _plan(grid, m['S'], m['G'], 'weighted_astar', level['weight'])
    gr = _plan(grid, m['S'], m['G'], 'greedy')
    opt = a['path_cost']
    return {'optimal_cost': _r(opt), 'astar_expansions': a['expansions'],
            'weighted_astar_ratio': _r(w['path_cost'] / opt),
            'greedy_ratio': _r(gr['path_cost'] / opt)}


def _score_beat(level, inputs):
    grid, m = parse_grid(level['grid'])
    ref = level['reference']
    path = _cells(inputs)
    if len(path) > MAX_PATH:
        raise PlayError('too long a path')
    why = None
    if not path or path[0] != m['S']:
        why = 'the path does not start at S'
    elif path[-1] != m['G']:
        why = 'the path does not reach G'
    else:
        for a, b in zip(path, path[1:]):
            if b not in set(grid.neighbours(a)):
                why = f'{list(a)} -> {list(b)} is not a move the robot can make'
                break
    cost = None if why else math.fsum(grid.edge_cost(a, b) for a, b in zip(path, path[1:]))
    ratio = None if why else cost / ref['optimal_cost']
    stars = 0 if why else _stars([ratio <= ref['greedy_ratio'] + EPS,
                                  ratio <= ref['weighted_astar_ratio'] + EPS,
                                  ratio <= 1.0 + EPS])
    return why, stars, {'name': 'cost ratio', 'value': _r(ratio)}, [
        _metric('your_cost', cost, 'cost', 'the summed move costs of your path'),
        _metric('optimal_cost', ref['optimal_cost'], 'cost', "A*'s path, which is optimal on this grid"),
        _metric('ratio', ratio, '', 'your cost / optimal cost (1 is optimal)'),
        _metric('moves', max(0, len(path) - 1), '', 'moves in your path'),
        _metric('astar_expansions', ref['astar_expansions'], 'expansions',
                'what A* computed to find the optimum (counted, not timed)'),
    ], ['greedy best-first: ratio <= %.4f' % ref['greedy_ratio'],
        'weighted A* (w=%g): ratio <= %.4f' % (level['weight'], ref['weighted_astar_ratio']),
        'A* (optimal): ratio = 1']


def next_node_frames(level) -> List[Dict[str, object]]:
    """
    A*'s search state before each of the NEXT_N expansions the learner predicts.

    Each frame: the closed cells, the open cells with ``g`` and ``h``, the
    cell A* expanded next, and ``tied``: every open cell whose ``(f, h)``
    equals that cell's -- A* orders by f, then low h, then insertion order,
    which the learner cannot see, so any of them is a correct prediction.
    """
    grid, m = parse_grid(level['grid'])
    after = int(level['after'])
    open_, closed, frames = {}, [], []
    expanded = 0
    for row in search_events(grid, m['S'], m['G'], 'astar', 'octile'):
        kind, r, c = row[0], row[1], row[2]
        if kind in (PUSH, RELAX):
            open_[(r, c)] = (row[4], row[5], row[6])
        elif kind == EXPAND:
            if expanded >= after:
                g, h, f = open_[(r, c)]
                tied = sorted(k for k, (gg, hh, ff) in open_.items()
                              if abs(ff - f) <= EPS and abs(hh - h) <= EPS)
                frames.append({
                    'closed': [list(k) for k in closed],
                    'open': [[k[0], k[1], _r(v[0]), _r(v[1])] for k, v in sorted(open_.items())],
                    'expanded': [r, c], 'f': _r(f), 'h': _r(h),
                    'tied': [list(k) for k in tied]})
                if len(frames) == NEXT_N:
                    break
            del open_[(r, c)]
            closed.append((r, c))
            expanded += 1
    if len(frames) != NEXT_N:
        raise PlayError(f'A* expands fewer than {after} + {NEXT_N} cells on this level')
    return frames


def _predictor(frames, key) -> int:
    """How many frames a predictor picking the open cell of least ``key`` matches."""
    n = 0
    for fr in frames:
        best = min(fr['open'], key=lambda o: (key(o), o[0], o[1]))
        n += [best[0], best[1]] in fr['tied']
    return n


def next_references(level) -> Dict[str, object]:
    """The matches of two simple predictors: least g (Dijkstra's), least h (greedy's)."""
    fr = next_node_frames(level)
    return {'min_g_matches': _predictor(fr, lambda o: o[2]),
            'min_h_matches': _predictor(fr, lambda o: o[3])}


def _score_next(level, inputs):
    ref = level['reference']
    guesses = _cells(inputs)
    why = None if len(guesses) == NEXT_N else f'a prediction has {NEXT_N} cells, one per expansion'
    frames = next_node_frames(level)
    hits = [] if why else [list(gc) in fr['tied'] for gc, fr in zip(guesses, frames)]
    n = sum(hits)
    lo, hi = sorted((ref['min_g_matches'], ref['min_h_matches']))
    stars = 0 if why else _stars([n >= lo, n >= hi, n == NEXT_N])
    return why, stars, {'name': 'matches', 'value': n}, [
        _metric('matches', n, f'of {NEXT_N}', 'predictions A* could have expanded next'),
        _metric('per_step', hits, '', 'each prediction, in order'),
        _metric('min_h_predictor', ref['min_h_matches'], f'of {NEXT_N}', 'always the open cell nearest the goal (greedy)'),
        _metric('min_g_predictor', ref['min_g_matches'], f'of {NEXT_N}', 'always the open cell nearest the start (Dijkstra)'),
    ], [f'the weaker predictor: >= {lo}', f'the stronger predictor: >= {hi}',
        f'A* itself: {NEXT_N} of {NEXT_N}']


# -- search the bays -------------------------------------------------------------

def _problem(level):
    from .regionsearch import SearchProblem
    return SearchProblem.from_dict(level['problem'])


def bays_references(level) -> Dict[str, object]:
    """The optimal order and two simple policies' orders, with expected costs."""
    from .regionsearch import optimal_order, plan_cost, policy_plan
    p = _problem(level)
    opt = optimal_order(p, p.prior, p.start, range(p.n))
    e_opt = plan_cost(p, p.prior, p.start, opt)['expected']
    out = {'optimal_order': list(opt), 'optimal_expected': _r(e_opt)}
    for pol in ('nearest', 'most_likely'):
        order = [p.ids.index(i) for i in policy_plan(p, pol)['order']]
        out[f'{pol}_order'] = order
        out[f'{pol}_ratio'] = _r(plan_cost(p, p.prior, p.start, order)['expected'] / e_opt)
    return out


def _score_bays(level, inputs):
    from .regionsearch import plan_cost
    p = _problem(level)
    ref = level['reference']
    order = list(inputs)
    why = None
    if sorted(order) != list(range(p.n)) or any(isinstance(i, bool) for i in order):
        why = f'an order names every bay once: a permutation of 0..{p.n - 1}'
    c = None if why else plan_cost(p, p.prior, p.start, order)
    ratio = None if why else c['expected'] / ref['optimal_expected']
    lo, hi = sorted((ref['nearest_ratio'], ref['most_likely_ratio']), reverse=True)
    stars = 0 if why else _stars([ratio <= lo + EPS, ratio <= hi + EPS, ratio <= 1.0 + EPS])
    return why, stars, {'name': 'expected cost ratio', 'value': _r(ratio)}, [
        _metric('expected_cost', None if why else c['expected'], 'm',
                'the expected distance driven by your order, over where the target might be (the prior)'),
        _metric('optimal_expected_cost', ref['optimal_expected'], 'm', 'the least expected cost of any order'),
        _metric('ratio', ratio, '', 'yours / optimal (1 is optimal); never the sampled outcome'),
        _metric('p_find', None if why else c['p_find'], '', 'the chance the order finds the target'),
    ], ['the worse of nearest-first and most-likely-first: ratio <= %.4f' % lo,
        'the better of them: ratio <= %.4f' % hi, 'the optimal order: ratio = 1']


# -- map the arena ----------------------------------------------------------------

def _spec_hash(spec) -> str:
    from .worldspec import canonical_bytes
    return hashlib.sha256(canonical_bytes(spec)).hexdigest()


class MapBudget:
    """The ground-truth distance driven, against a level's budget."""

    def __init__(self, budget_m: float, pose):
        """Start at ``pose`` with nothing driven."""
        self.budget_m = float(budget_m)
        self.path_m = 0.0
        self._prev = (pose[0], pose[1])

    def update(self, pose) -> bool:
        """Add the step to ``pose``; return whether the budget is spent."""
        self.path_m += math.hypot(pose[0] - self._prev[0], pose[1] - self._prev[1])
        self._prev = (pose[0], pose[1])
        return self.done

    @property
    def done(self) -> bool:
        """Whether the budget is spent."""
        return self.path_m >= self.budget_m


def map_drive(spec, level, inputs, ticks) -> Dict[str, object]:
    """
    Re-simulate a drive from its input log; return its map scores.

    The Arena is stepped exactly as the page steps it (the inputs stamped
    ``tick == k`` go into step ``k``); the drive ends at ``ticks`` or at the
    first tick whose ground-truth distance reaches the budget, whichever is
    first, and the map is scored there (coco_lab.map_arena's ``scores``:
    Lab 3's ATE and F1 against the truth).
    """
    from .arena import Arena, InputEvent
    from . import loc_arena, map_arena, move_arena, mission_arena  # noqa: F401 -- subsystems
    if not isinstance(ticks, int) or isinstance(ticks, bool) or not 0 < ticks <= level['max_ticks']:
        raise PlayError(f"ticks must be 1..{level['max_ticks']}")
    rows = _map_inputs(level, inputs)
    a = Arena(spec, int(level['seed']))
    budget = MapBudget(level['budget_m'], a.pose)
    by_tick: Dict[int, list] = {}
    for r in rows:
        by_tick.setdefault(r['tick'], []).append(InputEvent(**r))
    end = 0
    for k in range(ticks):
        a.step(by_tick.get(k, ()))
        end = k + 1
        if budget.update(a.pose):
            break
    s = a.subsystems['map'].scores()
    return {'ticks': end, 'path_m': budget.path_m, 'f1': s['f1'], 'ate': s['ate']}


def _map_inputs(level, inputs) -> List[Dict[str, object]]:
    if not isinstance(inputs, list) or len(inputs) > MAX_INPUTS:
        raise PlayError('an input log is a list')
    for r in inputs:
        if not isinstance(r, dict) or (r.get('kind') != 'config' and r.get('kind') not in MAP_KINDS):
            raise PlayError(f'{r!r}: a map drive may only drive (goal, teleop, stop, planner)')
    cfg = [r for r in inputs if r.get('kind') == 'config']
    if [r.get('choice') for r in cfg] != list(level['config']):
        raise PlayError("a map drive's only config lines are its level's, in order")
    # the page applies them once their Python pack has loaded, a few ticks in:
    # any tick will do, so long as the robot has not been driven yet
    first = min((r.get('tick', 0) for r in inputs if r.get('kind') in MAP_KINDS), default=None)
    if first is not None and any(r.get('tick', 0) > first for r in cfg):
        raise PlayError("a map drive's config lines come before it drives")
    return inputs


def map_references(spec, level) -> Dict[str, object]:
    """Score the level's two reference drives (input logs in the level)."""
    out = {}
    for name in ('out_and_back', 'tour'):
        d = level['drives'][name]
        r = map_drive(spec, level, d['inputs'], d['ticks'])
        out[name] = {'f1': _r(r['f1']), 'ate': _r(r['ate']), 'path_m': _r(r['path_m'])}
    return out


def _score_map(level, inputs, spec):
    if spec is None or _spec_hash(spec) != level['spec']:
        raise PlayError('the map challenge needs the World Spec it was made for')
    if not isinstance(inputs, dict):
        raise PlayError("a map submission's inputs are {'ticks': N, 'log': [...]}")
    ref = level['reference']
    r = map_drive(spec, level, inputs.get('log'), inputs.get('ticks'))
    f1, ate = r['f1'], r['ate']
    # the references ranked by what they scored, not by their names
    weak, strong = sorted((ref['out_and_back'], ref['tour']), key=lambda d: d['f1'])
    stars = _stars([f1 >= weak['f1'] - EPS, f1 >= strong['f1'] - EPS,
                    f1 >= strong['f1'] - EPS and ate <= strong['ate'] + EPS])
    return None, stars, {'name': 'map F1', 'value': _r(f1)}, [
        _metric('f1', f1, '', "the map's F1 against the truth's visible walls (Lab 3's score)"),
        _metric('ate', ate, 'm', "the trajectory's RMS error against the truth (ATE)"),
        _metric('path_m', r['path_m'], 'm', f"ground-truth distance driven (budget {level['budget_m']:g} m)"),
        _metric('ticks', r['ticks'], '', 'the tick the drive was scored at'),
    ], ['the weaker reference drive: F1 >= %.4f' % weak['f1'],
        'the stronger reference drive: F1 >= %.4f' % strong['f1'],
        'the stronger on both: F1 >= %.4f and ATE <= %.4f m' % (strong['f1'], strong['ate'])]


# -- case file detective -------------------------------------------------------------

def _score_detective(level, inputs):
    if not (isinstance(inputs, list) and len(inputs) == 1 and isinstance(inputs[0], int)
            and not isinstance(inputs[0], bool)):
        raise PlayError('a detective names one tick')
    tick = inputs[0]
    why = None if 1 <= tick <= level['ticks'] else f"the Case File's ticks are 1..{level['ticks']}"
    m = level['moment']
    err = None if why else abs(tick - m['tick']) * level['tick_s']
    bands = level['bands_s']
    stars = 0 if why else _stars([err <= bands[0] + EPS, err <= bands[1] + EPS, err <= bands[2] + EPS])
    return why, stars, {'name': 'error', 'value': _r(err)}, [
        _metric('your_tick', tick, '', 'the tick you marked'),
        _metric('divergence_tick', m['tick'], '', "where the stack's belief first left the truth by more than "
                f"{level['divergence_m']:g} m (src/arena/moments.ts)"),
        _metric('error_s', err, 's', 'how far apart, in recorded time'),
        _metric('found', None if why else err <= level['tolerance_s'] + EPS, '',
                f"within the stated tolerance, {level['tolerance_s']:g} s"),
    ], ['within %g s' % bands[0], 'within %g s' % bands[1], 'within %g s' % bands[2]]


# -- the one entry point ----------------------------------------------------------------

def find_level(levels, challenge: str, level_id: str) -> Dict[str, object]:
    """Return a level from a levels file, or raise."""
    if levels.get('schema') != LEVELS_SCHEMA:
        raise PlayError(f'levels must be {LEVELS_SCHEMA}')
    for lv in levels['challenges'].get(challenge, {}).get('levels', []):
        if lv['id'] == level_id:
            return lv
    raise PlayError(f'no level {challenge}/{level_id}')


def score(levels, submission, spec=None) -> Dict[str, object]:
    """
    Score a submission against its level; return the result, hashed.

    Raises :class:`PlayError` for a submission that is not one (unknown
    challenge or level, a level hash that is not this level's, inputs of
    the wrong shape). A well-formed submission that breaks a rule -- a path
    through a wall, an order that skips a bay -- is a result with
    ``valid: False``, the reason, and no stars.
    """
    if not isinstance(submission, dict) or submission.get('v') != 1:
        raise PlayError('a submission is {v: 1, ...}')
    ch = submission.get('challenge')
    if ch not in CHALLENGES:
        raise PlayError(f'no challenge {ch!r}')
    level = find_level(levels, ch, submission.get('level'))
    if submission.get('level_hash') != level_hash(level):
        raise PlayError('this submission was made for a different version of the level')
    inputs = submission.get('inputs')
    if ch == 'beat-the-planner':
        out = _score_beat(level, inputs)
    elif ch == 'next-node':
        out = _score_next(level, inputs)
    elif ch == 'search-the-bays':
        out = _score_bays(level, inputs)
    elif ch == 'map-the-arena':
        out = _score_map(level, inputs, spec)
    else:
        out = _score_detective(level, inputs)
    why, stars, primary, metrics, thresholds = out
    return _finish({'schema': SCHEMA, 'challenge': ch, 'level': level['id'],
                    'level_hash': submission['level_hash'], 'valid': why is None, 'why': why,
                    'score': primary, 'stars': stars, 'metrics': metrics,
                    'thresholds': thresholds})


def references(level, challenge: str, spec=None) -> Dict[str, object]:
    """A level's reference results, the stars' thresholds (without ``reference``)."""
    lv = {k: v for k, v in level.items() if k != 'reference'}
    if challenge == 'beat-the-planner':
        return beat_references(lv)
    if challenge == 'next-node':
        return next_references(lv)
    if challenge == 'search-the-bays':
        return bays_references(lv)
    if challenge == 'map-the-arena':
        return map_references(spec, lv)
    raise PlayError(f'{challenge} has no computed references')


def view(levels, challenge: str, level_id: str) -> Dict[str, object]:
    """What the page draws for a level (the grid, A*'s frames, the bays)."""
    level = find_level(levels, challenge, level_id)
    out = {'challenge': challenge, 'level': level, 'level_hash': level_hash(level)}
    if challenge in ('beat-the-planner', 'next-node'):
        grid, m = parse_grid(level['grid'])
        out['grid'] = {'width': grid.width, 'height': grid.height,
                       'blocked': [grid.is_blocked((r, c)) for r in range(grid.height) for c in range(grid.width)],
                       'cost': [grid.cost_at((r, c)) for r in range(grid.height) for c in range(grid.width)],
                       'marks': {k: list(v) for k, v in m.items()}}
    if challenge == 'beat-the-planner':
        grid, m = parse_grid(level['grid'])
        res = collect(search_events(grid, m['S'], m['G'], 'astar', 'octile'))
        out['optimal_path'] = [list(c) for c in res.path]
    if challenge == 'next-node':
        out['frames'] = next_node_frames(level)
    return out


__all__ = ['CHALLENGES', 'MapBudget', 'PlayError', 'canonical', 'find_level', 'level_hash',
           'map_drive', 'next_node_frames', 'parse_grid', 'references', 'score', 'view']
