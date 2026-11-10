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
R4 · the Learn course's grader (coco_lab.course; ADR 0015) and R4.7's grading integrity.

For every code exercise: the reference solution passes; every committed plausible wrong
solution (test/course_wrong/) fails with a message; and a file that hard-codes the public
scenarios' answers fails the hidden ones, because the hidden draw is seeded by the file itself.
"""
import json
import os
from pathlib import Path

from coco_lab import course as C
import pytest

os.environ.setdefault('COCO_WORLDS', str(Path(__file__).resolve().parents[2] / 'worlds'))

HERE = Path(__file__).parent
WRONG = sorted((HERE / 'course_wrong').glob('*.py'))
CODE = sorted(i for i, e in C.exercises().items() if e['type'] in ('code', 'benchmark'))


def _ex_of(path: Path) -> str:
    return path.stem.split('__')[0].replace('_', '-')


def test_the_exercise_file_loads_and_validates():
    ex = C.exercises()
    assert len(ex) >= 30
    for e in ex.values():
        C.validate(e)
    kinds = {t: sum(1 for e in ex.values() if e['type'] == t) for t in C.TYPES}
    assert all(kinds[t] >= 1 for t in C.TYPES), kinds
    assert sum(1 for e in ex.values() if e['type'] == 'code') >= 7


def test_every_predict_explains_every_wrong_option():
    for e in C.exercises().values():
        if e['type'] == 'predict' and 'options' in e:
            wrong = set(range(len(e['options']))) - {e['answer']}
            assert {int(k) for k in e['misconceptions']} == wrong, e['id']
            assert all(len(v) > 20 for v in e['misconceptions'].values()), e['id']


def test_a_predict_grades_its_answer_and_explains_a_wrong_one():
    e = C.exercise('p1-astar-cost')
    assert C.grade('p1-astar-cost', {'choice': e['answer']})['passed']
    g = C.grade('p1-astar-cost', {'choice': 0})
    assert not g['passed'] and g['results'][0]['message'] == e['misconceptions']['0']


@pytest.mark.parametrize('ex_id', CODE)
def test_every_code_exercise_reference_passes(ex_id):
    e = C.exercise(ex_id)
    g = C.grade(ex_id, {'code': C.file_text(e['solution'])})
    assert g['passed'], [r['message'] for r in g['results'] if not r['passed']]
    assert any(r['which'] == 'hidden' for r in g['results']) or e['type'] == 'benchmark'


@pytest.mark.parametrize('ex_id', [i for i in CODE if i != 'm10-export'])
def test_every_starter_fails(ex_id):
    e = C.exercise(ex_id)
    assert not C.grade(ex_id, {'code': C.file_text(e['starter'])})['passed']


def test_every_code_exercise_has_three_wrong_solutions():
    by = {}
    for p in WRONG:
        by.setdefault(_ex_of(p), []).append(p.name)
    for ex_id in CODE:
        assert len(by.get(ex_id, [])) >= 3, (ex_id, by.get(ex_id))


@pytest.mark.parametrize('path', WRONG, ids=[p.stem for p in WRONG])
def test_wrong_solutions_fail_with_a_message(path):
    g = C.grade(_ex_of(path), {'code': path.read_text()})
    assert not g['passed'], path.name
    failed = [r for r in g['results'] if not r['passed']]
    assert failed and all(len(r['message']) > 10 for r in failed), failed


def test_grading_is_deterministic():
    e = C.exercise('m1-dijkstra')
    a = C.grade('m1-dijkstra', {'code': C.file_text(e['solution'])})
    b = C.grade('m1-dijkstra', {'code': C.file_text(e['solution'])})
    assert a['digest'] == b['digest']


def test_hidden_scenarios_change_with_the_file_and_public_ones_do_not():
    e = C.exercise('m1-heuristic')
    a, b = {'code': 'x = 1\n'}, {'code': 'x = 2\n'}
    assert C.scenarios(e, 'public', a) == C.scenarios(e, 'public', b)
    ha, hb = C.scenarios(e, 'hidden', a), C.scenarios(e, 'hidden', b)
    assert [s['start'] for s in ha] != [s['start'] for s in hb]
    pub = {tuple(s['start'][:2]) for s in C.scenarios(e, 'public', a)}
    assert not pub & {tuple(s['start'][:2]) for s in ha}


def test_a_slider_value_is_the_same_answer_as_an_integer_or_a_float():
    # R4.7: the browser's JSON says 3 where Python says 3.0; the grade must not differ
    assert C.answer_digest({'params': {'heuristic_weight': 3}}) == \
        C.answer_digest({'params': {'heuristic_weight': 3.0}})


def test_a_tune_exercise_keeps_one_hidden_set():
    e = C.exercise('m1-tune-weight')
    assert C.scenarios(e, 'hidden', {'params': {'heuristic_weight': 1.5}}) == \
        C.scenarios(e, 'hidden', {'params': {'heuristic_weight': 2.0}})


def _memoriser(ex_id: str) -> str:
    """Return a planner that knows the reference's paths on the PUBLIC scenarios only."""
    from coco_lab import experiments as ex
    e = C.exercise(ex_id)
    scen = C.scenarios(e, 'public', {})
    ref = C.run_set(e, C._user_algo(C.file_text(e['solution'])), scen)
    m = ex.world(e['world']).lab_map
    table = {}
    for r in ref:
        # plan() receives the start snapped to its free cell's centre: key on that
        x, y = m.cell_centre(*r['path_cells'][0])
        table[f'{x:.2f},{y:.2f}'] = [list(m.cell_centre(*c)) for c in r['path_cells']]
    return (
        'from coco_lab.api import Pose2D\n'
        f'PATHS = {json.dumps(table)}\n\n\n'
        'def plan(costmap, start, goal, ctx):\n'
        "    p = PATHS.get(f'{start.x:.2f},{start.y:.2f}')\n"
        '    if p is None:\n'
        '        return [Pose2D(start.x, start.y), Pose2D(goal.x, goal.y)]\n'
        '    return [Pose2D(x, y) for x, y in p]\n')


@pytest.mark.parametrize('ex_id', ['m1-heuristic', 'm1-dijkstra', 'm3-nogo', 'm1-bench'])
def test_hard_coding_the_public_scenarios_fails_the_hidden_ones(ex_id):
    g = C.grade(ex_id, {'code': _memoriser(ex_id)})
    assert not g['passed']
    hidden = [r for r in g['results'] if r['which'] == 'hidden']
    if C.exercise(ex_id)['type'] != 'benchmark':
        public = [r for r in g['results'] if r['which'] == 'public']
        assert public and all(r['passed'] for r in public
                              if r['check'] != 'sum_ratio_max'), ex_id
    assert hidden and not all(r['passed'] for r in hidden)


@pytest.mark.parametrize('ex_id', ['m2-inflation', 'm4-goal', 'm6-logodds'])
def test_a_lookup_table_of_the_public_cases_fails_the_hidden_ones(ex_id):
    e = C.exercise(ex_id)
    fn = e['functions'][0]
    ref = C._load(C.file_text(e['solution']), [fn])[0]
    table = {repr(list(a)): ref(*a) for a in C._cases(e, 'public', {})}
    src = (f'TABLE = {table!r}\n\n\n'
           f'def {fn}(*args):\n'
           '    return TABLE.get(repr(list(args)), 0)\n')
    g = C.grade(ex_id, {'code': src})
    public = [r for r in g['results'] if r['which'] == 'public']
    hidden = [r for r in g['results'] if r['which'] == 'hidden']
    assert all(r['passed'] for r in public), public
    assert hidden and not any(r['passed'] for r in hidden)


def test_inflation_solution_is_coco_labs_costmap_function():
    from coco_lab.costmap import InflationParams, inflation_cost
    e = C.exercise('m2-inflation')
    f = C._load(C.file_text(e['solution']), ['inflation_cost'])[0]
    for which in ('public', 'hidden'):
        for d, r, infl, k in C._cases(e, which, {'code': which}):
            assert f(d, r, infl, k) == inflation_cost(d, InflationParams(infl, k, r))


def test_logodds_solution_is_coco_labs_grid():
    from coco_lab.occgrid import GridParams, OccupancyGrid
    e = C.exercise('m6-logodds')
    f = C._load(C.file_text(e['solution']), ['update'])[0]
    p = GridParams()
    for l0, hits in C._cases(e, 'public', {}) + C._cases(e, 'hidden', {'code': 'x'}):
        g = OccupancyGrid(1, 1, 0.1, (0.0, 0.0), p)
        g.logodds[0] = l0
        for h in hits:
            g.add(0, 0, p.l_occ if h else p.l_free)
        assert f(l0, hits) == pytest.approx(g.logodds[0], abs=1e-12)


def test_resample_reference_is_the_filters_own_low_variance_step():
    from coco_lab.localise import low_variance_resample
    from coco_lab.rng import Rng
    from coco_lab import api
    e = C.exercise('m5-resample')
    f = C._load(C.file_text(e['solution']), ['resample'])[0]
    parts, w, seed = C._cases(e, 'public', {})[1]
    u = Rng(seed).random()
    out = f(parts, w, api.Random(Rng(seed)))
    assert out == [parts[i] for i in low_variance_resample(w, u)]


def test_the_failure_exercises_have_a_true_tick_and_grade_it():
    for ex_id in ('m7-failure-contact', 'm9-failure-stuck'):
        e = C.exercise(ex_id)
        t = C._truth_tick(e)
        assert t is not None and t > 10, ex_id
        assert C.grade(ex_id, {'tick': t})['passed']
        assert not C.grade(ex_id, {'tick': t + 5 * e['checks'][0]['window']})['passed']


def test_stall_start():
    poses = [(0, 0.0, 0.0), (1, 1.0, 0.0), (2, 2.0, 0.0), (3, 2.1, 0.0), (4, 2.05, 0.1)]
    assert C.stall_start(poses) == 2


def test_a_tune_exercise_has_a_passing_setting_and_its_default_fails():
    assert not C.grade('m1-tune-weight', {'params': {}})['passed']
    assert C.grade('m1-tune-weight', {'params': {'heuristic_weight': 3.0}})['passed']
    assert not C.grade('m2-tune-clearance', {'params': {}})['passed']
    good = {'cost_weight': 5.0, 'cost_scaling_factor': 5.0}
    assert C.grade('m2-tune-clearance', {'params': good})['passed']


def test_an_export_carries_the_file():
    e = C.exercise('m10-export')
    g = C.grade('m10-export', {'code': C.file_text(e['solution'])})
    assert [r for r in g['results'] if r['check'] == 'exports'][0]['passed']


def test_a_broken_answer_is_graded_not_raised():
    g = C.grade('m1-heuristic', {'code': 'def plan(:\n'})
    assert not g['passed'] and g['results'][0]['check'] == 'load'
    g = C.grade('m2-inflation', {'code': 'import os\n'})
    assert not g['passed'] and 'os' in g['results'][0]['message']
