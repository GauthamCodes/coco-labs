# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R4 · the Learn course's grader (``coco.lesson.v1``; ADR 0015).

Every exercise is DATA (``course/exercises.v1.json``); this module grades an answer to one, the
same way in the browser (Pyodide, the Studio's sandbox worker: ``sandbox_glue`` op ``grade``) and
natively (``python -m coco_lab.course grade EXERCISE ANSWER.json``), so the two agree exactly.

Exercise types and what an answer is:

- ``predict``: ``{"choice": i}`` (multiple choice) or ``{"tick": n}`` / ``{"cell": [x, y]}``.
- ``tune``: ``{"params": {...}}``, a built-in run with the learner's parameters.
- ``failure``: ``{"tick": n}``, the tick where a recorded MODEL run went wrong.
- ``code``: ``{"code": "..."}``, an algorithm file (``coco.algorithm.v1``) run through the guard.
- ``benchmark``: ``{"code": "..."}`` on a mini-suite, against a target.

**Exact grading.** The model is deterministic, so a check compares counts and properties (path
length, expansions, clearance, success, error, a function's return values) against a reference
run or the reference solution on the same scenarios -- never text. Every check names what it
measured, the target and the scenario, so the page can open the failing scenario in Compare.

**Hidden checks.** Each run/function exercise has public scenarios (from the exercise's seed:
the learner sees them) and hidden ones drawn from ``sha256(exercise seed, the answer)``: a new
answer gets a new hidden draw, so a file that hard-codes the public scenarios -- or any draw it
has seen -- meets scenarios it has never seen. Anyone can recompute both (no secret: the course is
self-verified, not proctored), which is what lets a completion link be re-verified exactly.
"""

import hashlib
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .numerics import math

SCHEMA = 'coco.lesson.v1'
GRADE_SCHEMA = 'coco.lesson.grade.v1'
HIDDEN_TAG = 'coco.lesson.v1.hidden'
HERE = Path(__file__).parent / 'course'
TYPES = ('predict', 'tune', 'failure', 'code', 'benchmark')
#: answers kept small: a completion link carries them
MAX_CODE_BYTES = 64 * 1024
LENGTH_EPS = 1e-6

_DATA: Optional[Dict] = None


class CourseError(ValueError):
    """An exercise or an answer this grader cannot take as written."""


# -- data ----------------------------------------------------------------------------------------

def data() -> Dict:
    """Return the exercise file (``course/exercises.v1.json``), checked once."""
    global _DATA
    if _DATA is None:
        d = json.loads((HERE / 'exercises.v1.json').read_text())
        if d.get('schema') != SCHEMA:
            raise CourseError(f'exercises: schema {d.get("schema")!r}, not {SCHEMA}')
        ids = [e['id'] for e in d['exercises']]
        if len(ids) != len(set(ids)):
            raise CourseError('exercises: duplicate ids')
        for e in d['exercises']:
            validate(e)
        _DATA = d
    return _DATA


def exercises() -> Dict[str, Dict]:
    """Return every exercise by id."""
    return {e['id']: e for e in data()['exercises']}


def exercise(ex_id: str) -> Dict:
    """Return one exercise or raise :class:`CourseError`."""
    e = exercises().get(ex_id)
    if e is None:
        raise CourseError(f'no exercise {ex_id!r}')
    return e


def file_text(name: str) -> str:
    """Return a course file's source (``course/files/<name>.py``): a starter or a solution."""
    if not name.replace('_', '').isalnum():
        raise CourseError(f'bad file name {name!r}')
    return (HERE / 'files' / f'{name}.py').read_text()


def validate(e: Dict) -> None:
    """Refuse an exercise whose definition is incomplete (the build and the tests call this)."""
    t = e.get('type')
    if t not in TYPES:
        raise CourseError(f'{e.get("id")}: type {t!r}')
    if not isinstance(e.get('seed'), int):
        raise CourseError(f'{e["id"]}: an integer seed')
    if t == 'predict':
        if 'options' in e:
            if not (isinstance(e.get('answer'), int) and 0 <= e['answer'] < len(e['options'])):
                raise CourseError(f'{e["id"]}: answer indexes options')
            wrong = {int(k) for k in e.get('misconceptions', {})}
            if wrong != set(range(len(e['options']))) - {e['answer']}:
                raise CourseError(f'{e["id"]}: a misconception note for every wrong option')
        elif e.get('mode') not in ('cell', 'tick'):
            raise CourseError(f'{e["id"]}: options, or mode cell/tick')
        return
    if len(e.get('hints', [])) != 3:
        raise CourseError(f'{e["id"]}: three hints (nudge, concept, nearly the answer)')
    if t in ('code', 'benchmark'):
        file_text(e['starter'])
        file_text(e['solution'])
    if not e.get('checks'):
        raise CourseError(f'{e["id"]}: at least one check')
    for c in e['checks']:
        if c['kind'] not in CHECKS:
            raise CourseError(f'{e["id"]}: unknown check {c["kind"]!r}')


# -- canonical, hashing, seeds -------------------------------------------------------------------

def canonical(obj) -> bytes:
    """Return the canonical JSON bytes (sorted keys, no spaces): what digests hash."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def answer_digest(answer: Dict) -> str:
    """Return sha256 of the canonical answer (code by its sha256, the rest as given)."""
    a = dict(answer)
    if 'code' in a:
        a['code'] = hashlib.sha256(a['code'].encode('utf-8')).hexdigest()
    return hashlib.sha256(canonical(a)).hexdigest()


def hidden_seed(e: Dict, answer: Dict) -> int:
    """Return the hidden draw's seed: 52 bits of sha256(tag, exercise, seed, answer digest)."""
    msg = f'{HIDDEN_TAG}|{e["id"]}|{e["seed"]}|{answer_digest(answer)}'.encode()
    return int(hashlib.sha256(msg).hexdigest()[:13], 16)


# -- scenarios -----------------------------------------------------------------------------------

def _keep(f: Dict, rules: Dict) -> bool:
    for key, (lo, hi) in rules.items():
        v = f.get(key)
        if v is None or not lo <= v <= hi:
            return False
    return True


def scenarios(e: Dict, which: str, answer: Optional[Dict] = None) -> List[Dict]:
    """
    Return an exercise's ``public`` or ``hidden`` scenarios (inline experiment scenarios).

    Drawn by COCO-Bench's generator (``bench_v1``'s pool and features) from the exercise's
    seed (public) or :func:`hidden_seed` (hidden), keeping the first ``n`` whose features pass
    the exercise's ``keep`` rules; a ``suite`` source takes the suite's own first scenarios
    (public) and a held-out-style draw from the same generator (hidden).
    """
    from . import bench_v1 as B
    from . import experiments as ex
    g = e['scenarios']
    n = g['public'] if which == 'public' else g['hidden']
    seed = e['seed'] if which == 'public' else hidden_seed(e, answer or {})
    if 'suite' in g:
        if which == 'public':
            scen = B.generate(g['suite'])[:n]
        else:
            scen = B.generate(g['suite'], seed=seed % (1 << 31), n=n)
    else:
        w = ex.world(e['world'])
        scen, pool_seed = [], seed % (1 << 31)
        for attempt in range(4):
            for s in B._pool(w, g.get('pool', 60), pool_seed + attempt, g['min_separation_m']):
                f = B.features(w, s)
                if f is None or not _keep(f, g.get('keep', {})):
                    continue
                scen.append(dict(s, features=f))
                if len(scen) == n:
                    break
            if len(scen) == n:
                break
        if len(scen) < n:
            raise CourseError(f'{e["id"]}: only {len(scen)} of {n} {which} scenarios pass')
    out = []
    keep = ('start', 'goal', 'seed', 'config', 'kidnap', 'kidnap_at_s')
    for i, s in enumerate(scen):
        d = {k: s[k] for k in keep if k in s}
        d['id'] = f'{which[0]}{i + 1}'
        d['start'] = [round(v, 6) for v in d['start']]
        d['goal'] = [round(v, 6) for v in d['goal'][:2]]
        out.append(d)
    if e.get('zones'):
        out = [dict(s, zone=_zone(e, s)) for s in out]
    return out


def _zone(e: Dict, s: Dict) -> List[float]:
    """A no-go rectangle across the reference path's middle (the no-go zone exercise)."""
    from . import experiments as ex
    w = ex.world(e['world'])
    cells = _reference_cells(e, s)
    m = w.lab_map
    mid = m.cell_centre(*cells[len(cells) // 2])
    half = e['zones']['half_m']
    return [round(mid[0] - half, 3), round(mid[1] - half, 3),
            round(mid[0] + half, 3), round(mid[1] + half, 3)]


def _reference_cells(e: Dict, s: Dict) -> List:
    from . import experiments as ex
    spec = _spec(e, [{'name': 'astar'}], [dict(s, zone=None)])
    p = ex.plan(spec)
    cells: List = []
    ex.run_one(p['runs'][0], sink=lambda row: cells.append((row[1], row[2])) if row[0] == 3
               else None)
    if not cells:
        raise CourseError(f'{e["id"]}: the reference found no path for a zone')
    return cells


# -- running -------------------------------------------------------------------------------------

def _spec(e: Dict, algorithms: List[Dict], scen: List[Dict]) -> Dict:
    from . import experiments as ex
    inline = [{k: v for k, v in s.items() if k not in ('zone', 'features')} for s in scen]
    spec = {'schema': ex.SCHEMA, 'title': f'course {e["id"]}', 'family': e['family'], 'seed': 1,
            'world': e['world'], 'algorithms': algorithms,
            'scenarios': {'kind': 'inline', 'scenarios': inline}}
    if e['family'] in ('control', 'localisation'):
        spec['limits'] = {'max_ticks': e.get('max_ticks', 1500)}
    return spec


def _user_algo(code: str, params: Optional[Dict] = None) -> Dict:
    from . import exp_user
    if len(code.encode('utf-8')) > MAX_CODE_BYTES:
        raise CourseError(f'the file is larger than {MAX_CODE_BYTES // 1024} KB')
    sha = exp_user.register(code)
    a = {'name': 'user', 'api': 1, 'code_sha256': sha}
    if params:
        a['params'] = params
    return a


def run_set(e: Dict, algo: Dict, scen: List[Dict]) -> List[Dict]:
    """Run one algorithm on every scenario (a no-go zone travels as ``user.nogo``); records."""
    from . import experiments as ex
    out = []
    for s in scen:
        a = dict(algo)
        if s.get('zone') is not None and a['name'] == 'user':
            a['params'] = dict(a.get('params', {}), **{'user.nogo': s['zone']})
        p = ex.plan(_spec(e, [a], [s]))
        cells: List = []
        sink = (lambda row: cells.append(list(row[1:3])) if row[0] == 3 else None) \
            if e['family'] == 'planning' else None
        r = ex.run_one(p['runs'][0], sink=sink, twice=False)
        r = ex.plain(r)
        r['scenario'] = s['id']
        if sink is not None:
            r['path_cells'] = cells
        out.append(r)
    return out


# -- checks --------------------------------------------------------------------------------------

def _m(r: Dict, metric: str):
    if metric == 'success':
        return r['success']
    return r['metrics'].get(metric)


def _fmt(v) -> str:
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, float):
        return f'{v:.4g}'
    return str(v)


def _result(c: Dict, passed: bool, which: str, scenario: Optional[str], measured, target,
            message: str) -> Dict:
    return {'check': c['kind'], 'label': c.get('label', c['kind']), 'passed': bool(passed),
            'which': which, 'scenario': scenario, 'measured': measured, 'target': target,
            'message': message}


def check_success_all(c, runs, which, **_):
    """Every run reached its goal (planning: found a valid path)."""
    out = []
    for r in runs['user']:
        ok = r['success']
        why = '' if ok else (r.get('error') or (r.get('report') or {}).get('error') or {})
        if isinstance(why, dict):
            why = why.get('message', '')
        out.append(_result(c, ok, which, r['scenario'], r['status'], c.get('want', 'success'),
                           'reached the goal' if ok else
                           f'did not succeed: status {r["status"]}' + (f' ({why})' if why else '')))
    return out


def check_metric_max(c, runs, which, **_):
    """Per scenario: the learner's metric is at most ``value``."""
    out = []
    for r in runs['user']:
        v = _m(r, c['metric'])
        ok = v is not None and v <= c['value']
        out.append(_result(c, ok, which, r['scenario'], v, c['value'],
                           f'{c["metric"]} {_fmt(v)} (at most {_fmt(c["value"])})'))
    return out


def check_metric_min(c, runs, which, **_):
    """Per scenario: the learner's metric is at least ``value``."""
    out = []
    for r in runs['user']:
        v = _m(r, c['metric'])
        ok = v is not None and v >= c['value']
        out.append(_result(c, ok, which, r['scenario'], v, c['value'],
                           f'{c["metric"]} {_fmt(v)} (at least {_fmt(c["value"])})'))
    return out


def check_ratio_max(c, runs, which, **_):
    """Per scenario: learner metric / ``vs`` run's metric is at most ``value`` (+ a tiny eps)."""
    out = []
    for r, ref in zip(runs['user'], runs[c['vs']]):
        a, b = _m(r, c['metric']), _m(ref, c['metric'])
        if a is None or b is None or b <= 0:
            out.append(_result(c, False, which, r['scenario'], a, c['value'],
                               f'no {c["metric"]} to compare (status {r["status"]})'))
            continue
        q = a / b
        ok = a <= b * c['value'] + LENGTH_EPS
        out.append(_result(c, ok, which, r['scenario'], round(q, 6), c['value'],
                           f'{c["metric"]} {_fmt(a)} is {q:.4f}x the {c["vs"]}\'s {_fmt(b)} '
                           f'(at most {c["value"]}x)'))
    return out


def check_sum_ratio_max(c, runs, which, **_):
    """Over all scenarios: sum(learner metric) / sum(``vs`` metric) is at most ``value``."""
    a = [_m(r, c['metric']) for r in runs['user']]
    b = [_m(r, c['metric']) for r in runs[c['vs']]]
    if any(v is None for v in a + b) or sum(b) <= 0:
        return [_result(c, False, which, None, None, c['value'],
                        f'{c["metric"]} missing on a run: fix the failing runs first')]
    q = sum(a) / sum(b)
    ok = q <= c['value']
    return [_result(c, ok, which, None, round(q, 6), c['value'],
                    f'{c["metric"]}: {sum(a)} in total, {q:.3f}x the {c["vs"]}\'s {sum(b)} '
                    f'(at most {c["value"]}x)')]


def check_zone_avoid(c, runs, which, scen=None, **_):
    """Planning: no cell of the path has its centre inside the scenario's no-go rectangle."""
    from . import experiments as ex
    out = []
    zones = {s['id']: s['zone'] for s in scen}
    for r in runs['user']:
        z = zones[r['scenario']]
        m = ex.world(r['_world']).lab_map
        inside = 0
        for cell in r.get('path_cells') or []:
            x, y = m.cell_centre(*cell)
            if z[0] <= x <= z[2] and z[1] <= y <= z[3]:
                inside += 1
        ok = r['success'] and inside == 0
        out.append(_result(c, ok, which, r['scenario'], inside, 0,
                           'the path stays out of the zone' if ok else
                           (f'{inside} path cells inside the no-go zone' if r['success']
                            else f'no path (status {r["status"]})')))
    return out


def check_success_rate_min(c, runs, which, **_):
    """Benchmark: successes / runs is at least ``value``."""
    k = sum(1 for r in runs['user'] if r['success'])
    n = len(runs['user'])
    ok = n > 0 and k / n >= c['value']
    return [_result(c, ok, which, None, f'{k}/{n}', c['value'],
                    f'{k} of {n} succeeded (at least {c["value"]:.0%})')]


def check_median_ratio_max(c, runs, which, **_):
    """Benchmark: the median of per-scenario learner/``vs`` metric ratios is at most ``value``."""
    qs = []
    for r, ref in zip(runs['user'], runs[c['vs']]):
        a, b = _m(r, c['metric']), _m(ref, c['metric'])
        if a is not None and b:
            qs.append(a / b)
    if not qs:
        return [_result(c, False, which, None, None, c['value'], 'no successful run to compare')]
    qs.sort()
    med = qs[len(qs) // 2] if len(qs) % 2 else (qs[len(qs) // 2 - 1] + qs[len(qs) // 2]) / 2
    ok = med <= c['value']
    return [_result(c, ok, which, None, round(med, 6), c['value'],
                    f'median {c["metric"]} ratio {med:.4f} (at most {c["value"]})')]


def check_function_cases(c, runs, which, fns=None, cases=None, **_):
    """A function's return values equal the reference solution's on every case (exact or tol)."""
    user, ref = fns
    tol = c.get('tol', 0.0)
    bad = []
    for args in cases:
        want = ref(*args)
        try:
            got = user(*args)
        except Exception as e:  # the learner's function raised: that is the answer to grade
            return [_result(c, False, which, None, None, None,
                            f'your {c["function"]}{_args(args)} raised {type(e).__name__}: '
                            f'{str(e)[:160]}')]
        if not _same(got, want, tol):
            bad.append((args, got, want))
    if bad:
        args, got, want = bad[0]
        return [_result(c, False, which, None, f'{len(cases) - len(bad)}/{len(cases)}',
                        len(cases),
                        f'{len(bad)} of {len(cases)} cases differ; first: {c["function"]}'
                        f'{_args(args)} returned {_fmt_v(got)}, expected {_fmt_v(want)}')]
    return [_result(c, True, which, None, f'{len(cases)}/{len(cases)}', len(cases),
                    f'all {len(cases)} cases match')]


def check_resample(c, runs, which, fns=None, cases=None, **_):
    """
    Resampling, by properties (any correct resampler passes, a deterministic rng):

    the same number of particles; each one of the inputs; never a zero-weight particle; and
    each particle's count within ``N w +- (4 sqrt(N w (1 - w)) + 1)`` (a 4-sigma band that
    multinomial, systematic and stratified resampling all meet at these sizes).
    """
    from .rng import Rng
    from . import api
    user = fns[0]
    for k, (parts, wts, seed) in enumerate(cases):
        rng = api.Random(Rng(seed))
        try:
            out = user(list(parts), list(wts), rng)
        except Exception as e:  # graded, not raised
            return [_result(c, False, which, None, None, None,
                            f'case {k + 1}: resample raised {type(e).__name__}: {str(e)[:160]}')]
        n = len(parts)
        if not isinstance(out, (list, tuple)) or len(out) != n:
            return [_result(c, False, which, None, None, n,
                            f'case {k + 1}: returned {len(out) if hasattr(out, "__len__") else out}'
                            f' particles, expected {n} (resampling keeps the count)')]
        index = {tuple(p): i for i, p in enumerate(parts)}
        counts = [0] * n
        for p in out:
            i = index.get(tuple(p))
            if i is None:
                return [_result(c, False, which, None, None, None,
                                f'case {k + 1}: returned a particle that was not one of the inputs')]
            counts[i] += 1
        for i, (wi, ci) in enumerate(zip(wts, counts)):
            if wi == 0 and ci:
                return [_result(c, False, which, None, ci, 0,
                                f'case {k + 1}: particle {i} has weight 0 but was copied {ci} '
                                'times (a zero-weight guess must die)')]
            band = 4 * math.sqrt(n * wi * (1 - wi)) + 1
            if abs(ci - n * wi) > band:
                return [_result(c, False, which, None, ci, round(n * wi, 2),
                                f'case {k + 1}: particle {i} (weight {wi:.3f}) was copied {ci} '
                                f'times; about {n * wi:.1f} expected (copies follow the weights)')]
    return [_result(c, True, which, None, f'{len(cases)}/{len(cases)}', len(cases),
                    f'all {len(cases)} weight sets resampled correctly')]


def check_choice(c, runs, which, e=None, answer=None, **_):
    """Predict: the chosen option is the answer."""
    ch = answer.get('choice')
    ok = ch == e['answer']
    msg = 'right' if ok else e['misconceptions'].get(str(ch), 'not this one')
    return [_result(c, ok, which, None, ch, e['answer'], msg)]


def check_tick_within(c, runs, which, answer=None, truth=None, **_):
    """Failure / predict-tick: the picked tick is within ``window`` ticks of the true one."""
    t = answer.get('tick')
    ok = isinstance(t, int) and truth is not None and abs(t - truth) <= c['window']
    if t is None:
        return [_result(c, False, which, None, None, truth, 'pick a tick')]
    off = t - truth
    return [_result(c, ok, which, None, t, truth,
                    'that is the moment' if ok else
                    ('too early: ' if off < 0 else 'too late: ') +
                    f'{abs(off)} ticks ({abs(off) * 0.1:.1f} s) from it (within '
                    f'{c["window"]} ticks counts)')]


def check_cell_within(c, runs, which, e=None, answer=None, **_):
    """Predict-cell: the clicked point is within ``radius_m`` of the answer point."""
    p = answer.get('cell')
    ok = isinstance(p, list) and len(p) == 2 and \
        math.hypot(p[0] - e['answer_xy'][0], p[1] - e['answer_xy'][1]) <= c['radius_m']
    return [_result(c, ok, which, None, p, e['answer_xy'],
                    'right there' if ok else e.get('miss', 'not there'))]


def check_exports(c, runs, which, answer=None, **_):
    """The file exports to a ROS 2 package (``coco_lab.ros2_export``, the Studio's own export)."""
    if which != 'public':
        return []
    from . import ros2_export, user_code
    try:
        files = ros2_export.export(answer.get('code', ''), 'course_planner')
    except (ros2_export.ExportError, user_code.GuardError, ValueError) as e:
        return [_result(c, False, which, None, None, None, f'the export refused the file: {e}')]
    sha = user_code.code_sha256(answer.get('code', ''))
    need = ['package.xml', 'setup.py']
    missing = [n for n in need if not any(k.endswith(n) for k in files)]
    carries = any(sha in v for v in files.values())
    ok = not missing and carries
    return [_result(c, ok, which, None, len(files), None,
                    f'a package of {len(files)} files that runs your file (sha256 {sha[:12]}...)'
                    if ok else f'the package is missing {missing or "your file"}')]


CHECKS: Dict[str, Callable] = {
    'success_all': check_success_all, 'metric_max': check_metric_max,
    'metric_min': check_metric_min, 'ratio_max': check_ratio_max,
    'sum_ratio_max': check_sum_ratio_max, 'zone_avoid': check_zone_avoid,
    'success_rate_min': check_success_rate_min, 'median_ratio_max': check_median_ratio_max,
    'function_cases': check_function_cases, 'resample': check_resample,
    'choice': check_choice, 'tick_within': check_tick_within, 'cell_within': check_cell_within,
    'exports': check_exports,
}


def _args(args) -> str:
    return '(' + ', '.join(_fmt_v(a) for a in args) + ')'


def _fmt_v(v) -> str:
    if isinstance(v, float):
        return repr(round(v, 6))
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(_fmt_v(x) for x in v[:6]) + (', ...' if len(v) > 6 else '') + ']'
    return repr(v)


def _same(a, b, tol) -> bool:
    if isinstance(b, bool) or b is None:
        return a is b or a == b and type(a) is type(b)
    if isinstance(b, (int, float)) and isinstance(a, (int, float)) and not isinstance(a, bool):
        if isinstance(b, int) and not tol:
            return a == b
        return abs(a - b) <= tol if tol else a == b
    if isinstance(b, (list, tuple)) and isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y, tol) for x, y in zip(a, b))
    return a == b


# -- function cases ------------------------------------------------------------------------------

def _cases(e: Dict, which: str, answer: Dict) -> List:
    """The arguments a function exercise is called with (public from the seed, hidden drawn)."""
    from .rng import Rng
    seed = e['seed'] if which == 'public' else hidden_seed(e, answer)
    rng = Rng(seed % (1 << 63))
    n = e['cases'][which]
    gen = e['cases']['generator']
    out = [list(a) for a in e['cases'].get('fixed', [])] if which == 'public' else []
    for _ in range(n):
        out.append(GENERATORS[gen](rng))
    return out


def _gen_inflation(rng) -> list:
    robot = round(rng.uniform(0.15, 0.3), 3)
    infl = round(robot + rng.uniform(0.1, 0.8), 3)
    scaling = round(rng.uniform(1.0, 12.0), 2)
    r = rng.random()
    if r < 0.1:
        d = 0.0
    elif r < 0.2:
        d = robot           # exactly the inscribed radius: 253
    elif r < 0.3:
        d = infl            # exactly the inflation radius: still inflated
    else:
        d = round(rng.uniform(0.0, infl + 0.3), 3)
    return [d, robot, infl, scaling]


def _gen_goal(rng) -> list:
    gx, gy, gth = round(rng.uniform(-5, 5), 3), round(rng.uniform(-5, 5), 3), \
        round(rng.uniform(-3.1, 3.1), 3)
    r = rng.random()
    if r < 0.25:   # around the angle wrap: goal near +pi, robot near -pi
        gth = round(3.1 + rng.uniform(0, 0.04), 3)
        th = round(-3.1 - rng.uniform(0, 0.04), 3)
    else:
        th = round(gth + rng.uniform(-0.6, 0.6), 3)
    d = rng.uniform(0.0, 0.5)
    a = rng.uniform(-3.14, 3.14)
    return [[round(gx + d * math.cos(a), 3), round(gy + d * math.sin(a), 3), th], [gx, gy, gth],
            0.25, 0.25]


def _gen_logodds(rng) -> list:
    n = 1 + int(rng.random() * 12)
    hits = [rng.random() < 0.6 for _ in range(n)]
    return [round(rng.uniform(-4.0, 4.0), 3), hits]


def _gen_weights(rng) -> list:
    n = (60, 200, 500)[int(rng.random() * 3)]
    kind = rng.random()
    if kind < 0.2:      # one-hot
        k = int(rng.random() * n)
        w = [0.0] * n
        w[k] = 1.0
    else:
        raw = [rng.random() ** 3 if rng.random() > 0.3 else 0.0 for _ in range(n)]
        if not any(raw):
            raw[0] = 1.0
        s = math.fsum(raw)
        w = [v / s for v in raw]
    parts = [[round(rng.uniform(0, 10), 4), round(rng.uniform(0, 10), 4),
              round(rng.uniform(-3, 3), 4)] for _ in range(n)]
    return [parts, w, int(rng.random() * (1 << 40))]


GENERATORS = {'inflation': _gen_inflation, 'goal': _gen_goal, 'logodds': _gen_logodds,
              'weights': _gen_weights}


# -- grading -------------------------------------------------------------------------------------

def _load(code: str, entries: List[str]):
    """Load a file through the guard; return its named functions (``user_code.UserModule``)."""
    from . import user_code
    m = user_code.UserModule(code, entry=entries[0])
    fns = []
    for name in entries:
        f = m.namespace.get(name)
        if not callable(f):
            raise CourseError(f'the file has no function {name}()')
        fns.append(f)
    return fns


#: a stall: from this tick on the robot never moves more than this far from where it was
STALL_RADIUS_M = 0.25


def _truth_tick(e: Dict) -> Optional[int]:
    """
    The failure exercise's true tick, by its rule: ``first_contact`` (the first tick in
    contact), ``stall_start`` (the first tick after which the robot stays within
    :data:`STALL_RADIUS_M` of where it was) or ``fail_tick`` (the record's own).
    """
    from . import experiments as ex
    p = ex.plan(_spec(e, [e['run']], [e['scenario']]))
    contacts: List[int] = []
    poses: List = []

    def on_tick(a, t):
        if t.contact and not contacts:
            contacts.append(t.tick)
        poses.append((t.tick, t.pose[0], t.pose[1]))
    r = ex.run_one(p['runs'][0], on_tick=on_tick, twice=False)
    rule = e.get('truth', 'fail_tick')
    if rule == 'first_contact':
        return contacts[0] if contacts else None
    if rule == 'stall_start':
        return stall_start(poses)
    return r['fail_tick']


def stall_start(poses: List) -> Optional[int]:
    """The first tick after which every later position is within STALL_RADIUS_M of it."""
    for i, (tick, x, y) in enumerate(poses):
        if all(math.hypot(x2 - x, y2 - y) <= STALL_RADIUS_M for _, x2, y2 in poses[i:]):
            return tick if i < len(poses) - 1 else None
    return None


def grade(ex_id: str, answer: Dict) -> Dict:
    """
    Grade ``answer`` to exercise ``ex_id``; return the grade (``coco.lesson.grade.v1``).

    ``passed`` is true only when every check passes, on the public and the hidden set. A file
    that fails to load is graded (passed false, the guard's or Python's message), never raised.
    """
    e = exercise(ex_id)
    if not isinstance(answer, dict):
        raise CourseError('an answer is an object')
    results: List[Dict] = []
    info: Dict = {}
    t = e['type']
    try:
        if t == 'predict':
            kind = {'cell': 'cell_within', 'tick': 'tick_within'}.get(e.get('mode'), 'choice')
            c = dict(e['checks'][0]) if e.get('checks') else {'kind': kind}
            truth = e.get('answer_tick')
            results += CHECKS[c['kind']](c, None, 'public', e=e, answer=answer, truth=truth)
        elif t == 'failure':
            truth = _truth_tick(e)
            info['truth_known'] = truth is not None
            for c in e['checks']:
                results += CHECKS[c['kind']](c, None, 'public', answer=answer, truth=truth)
        elif 'cases' in e:
            fns_user = _load(answer.get('code', ''), e['functions'])
            fns_ref = _load(file_text(e['solution']), e['functions'])
            for which in ('public', 'hidden'):
                cases = _cases(e, which, answer)
                for c in e['checks']:
                    f = (fns_user[0], fns_ref[0])
                    results += CHECKS[c['kind']](c, None, which, fns=f, cases=cases)
        else:
            results += _grade_runs(e, answer, info)
    except Exception as err:  # noqa: B902 -- a broken answer is a graded answer
        from . import user_code
        msg = '; '.join(f'line {p["line"]}: {p["message"]}' for p in err.problems) \
            if isinstance(err, user_code.GuardError) else f'{type(err).__name__}: {err}'
        results.append({'check': 'load', 'label': 'the file loads', 'passed': False,
                        'which': 'public', 'scenario': None, 'measured': None, 'target': None,
                        'message': msg[:600]})
    passed = bool(results) and all(r['passed'] for r in results)
    out = {'schema': GRADE_SCHEMA, 'exercise': ex_id, 'type': t,
           'answer_sha256': answer_digest(answer), 'passed': passed,
           'checks_passed': sum(1 for r in results if r['passed']), 'checks': len(results),
           'results': results}
    out.update(info)
    out['digest'] = hashlib.sha256(canonical({k: v for k, v in out.items()
                                               if k != 'digest'})).hexdigest()
    return out


def _grade_runs(e: Dict, answer: Dict, info: Dict) -> List[Dict]:
    """Code, tune and benchmark: run the answer and its comparisons on both scenario sets."""
    results: List[Dict] = []
    if e['type'] == 'tune':
        params = _tune_params(e, answer.get('params', {}))
        user = {'name': e['algorithm'], 'params': params}
    else:
        code = answer.get('code', '')
        _load(code, [e['entry']])          # a file that does not load fails here, with its line
        user = _user_algo(code)
    others = {}
    for name, how in e.get('compare', {}).items():
        if how.get('solution'):
            others[name] = _user_algo(file_text(e['solution']))
        elif how.get('starter'):
            others[name] = _user_algo(file_text(e['starter']))
        else:
            others[name] = {'name': how['algorithm'], 'params': how.get('params', {})}
    shown = {}
    for which in ('public', 'hidden'):
        scen = scenarios(e, which, answer)
        runs = {'user': run_set(e, user, scen)}
        for name, algo in others.items():
            runs[name] = run_set(e, algo, scen)
        for r in runs['user']:
            r['_world'] = e['world']
        for c in e['checks']:
            results += CHECKS[c['kind']](c, runs, which, scen=scen, answer=answer)
        shown[which] = scen
    info['scenarios'] = shown
    return results


def _tune_params(e: Dict, given: Dict) -> Dict:
    out = dict(e.get('fixed_params', {}))
    for key, rng in e['params'].items():
        v = given.get(key, rng['default'])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or \
                not rng['min'] <= v <= rng['max']:
            raise CourseError(f'{key} must be a number from {rng["min"]} to {rng["max"]}')
        out[key] = v
    return out


def inspect(ex_id: str) -> Dict:
    """A failure exercise's run as a timeline for the page (no answer in it): sampled series."""
    from . import experiments as ex
    e = exercise(ex_id)
    if e['type'] != 'failure':
        raise CourseError('only a failure exercise has a timeline')
    p = ex.plan(_spec(e, [e['run']], [e['scenario']]))
    series = []

    def on_tick(a, t):
        b = a.belief()
        series.append([t.tick, round(t.pose[0], 3), round(t.pose[1], 3), round(t.v, 3),
                       round(a.smap.clearance(t.pose[0], t.pose[1]) - a.radius, 3),
                       1 if t.contact else 0,
                       round(math.hypot(b[0] - t.pose[0], b[1] - t.pose[1]), 3)])
    r = ex.run_one(p['runs'][0], on_tick=on_tick, twice=False)
    return {'exercise': ex_id, 'status': r['status'], 'ticks': len(series),
            'columns': ['tick', 'x', 'y', 'v', 'clearance_m', 'contact', 'belief_err_m'],
            'series': series}


def main(argv=None) -> int:
    """``grade EXERCISE ANSWER.json`` | ``list`` | ``inspect EXERCISE``: JSON on stdout."""
    import argparse
    ap = argparse.ArgumentParser(prog='python -m coco_lab.course')
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('grade')
    g.add_argument('exercise')
    g.add_argument('answer', help='a JSON file: {"code": ...} | {"choice": i} | ...')
    g.add_argument('--code', help='take the answer\'s code from this .py file')
    sub.add_parser('list')
    i = sub.add_parser('inspect')
    i.add_argument('exercise')
    o = ap.parse_args(argv)
    if o.cmd == 'list':
        print(json.dumps(sorted(exercises()), indent=1))
        return 0
    if o.cmd == 'inspect':
        print(json.dumps(inspect(o.exercise)))
        return 0
    answer = json.loads(Path(o.answer).read_text()) if o.answer != '-' else {}
    if o.code:
        answer['code'] = Path(o.code).read_text()
    out = grade(o.exercise, answer)
    print(json.dumps(out, sort_keys=True))
    return 0 if out['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
