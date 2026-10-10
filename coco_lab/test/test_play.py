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
coco_lab.play (M3.5): every challenge's scorer, on levels built here.

The committed levels (lab_web/play/levels.json) and the map challenge's
re-simulation are tested in lab_web/tools/test_play_levels.py.
"""

import copy
import itertools

import pytest

from coco_lab import play
from coco_lab.fetch_problem import PROBLEM

GRID = ["................",
        "..S.............",
        "...9999.........",
        "...9999...4444..",
        "...9999...4444..",
        "..........4444..",
        "..........4444..",
        "................",
        "............G...",
        "................"]
UTRAP = ["..................",
         "..................",
         "....##########....",
         ".............#....",
         "..S..........#..G.",
         ".............#....",
         "....##########....",
         "..................",
         ".................."]


def _levels(**extra):
    beat = {'id': 'b', 'title': 'b', 'weight': 2.0, 'grid': GRID}
    beat['reference'] = play.references(beat, 'beat-the-planner')
    nxt = {'id': 'n', 'title': 'n', 'after': 30, 'grid': UTRAP}
    nxt['reference'] = play.references(nxt, 'next-node')
    p = copy.deepcopy(PROBLEM)
    p['prior'] = [0.15, 0.15, 0.30, 0.40]
    bays = {'id': 's', 'title': 's', 'problem': p}
    bays['reference'] = play.references(bays, 'search-the-bays')
    det = {'id': 'd', 'title': 'd', 'casefile': 'x', 'ticks': 100, 'tick_s': 0.1, 'tolerance_s': 1.0,
           'bands_s': [2.0, 1.0, 0.5], 'divergence_m': 1.0,
           'moment': {'tick': 40, 't_world': 4.0, 'error_m': 3.4, 'source': 'amcl'}}
    lv = {'beat-the-planner': beat, 'next-node': nxt, 'search-the-bays': bays, 'case-file-detective': det}
    lv.update(extra)
    return {'schema': play.LEVELS_SCHEMA,
            'challenges': {c: {'levels': [v]} for c, v in lv.items()}}


LEVELS = _levels()


def _sub(challenge, inputs, levels=LEVELS):
    lv = levels['challenges'][challenge]['levels'][0]
    return {'v': 1, 'challenge': challenge, 'level': lv['id'], 'level_hash': play.level_hash(lv), 'inputs': inputs}


def _score(challenge, inputs):
    return play.score(LEVELS, _sub(challenge, inputs))


def _value(res, name):
    return next(m['value'] for m in res['metrics'] if m['name'] == name)


# -- beat the planner -----------------------------------------------------------

def test_astars_own_path_is_optimal_and_three_stars():
    path = play.view(LEVELS, 'beat-the-planner', 'b')['optimal_path']
    r = _score('beat-the-planner', path)
    assert r['valid'] and r['stars'] == 3
    assert _value(r, 'ratio') == 1.0


@pytest.mark.parametrize('algorithm, weight, stars', [('greedy', None, 1), ('weighted_astar', 2.0, 2)])
def test_a_reference_planners_path_earns_exactly_its_star(algorithm, weight, stars):
    from coco_lab.search import collect, search_events
    grid, m = play.parse_grid(GRID)
    res = collect(search_events(grid, m['S'], m['G'], algorithm, 'octile', weight))
    r = _score('beat-the-planner', [list(c) for c in res.path])
    assert r['stars'] == stars


def test_a_path_through_mud_and_a_wall_is_refused_not_scored():
    grid, m = play.parse_grid(GRID)
    (sr, sc), (gr, gc) = m['S'], m['G']
    jump = [[sr, sc], [gr, gc]]
    r = _score('beat-the-planner', jump)
    assert not r['valid'] and r['stars'] == 0 and 'not a move' in r['why']
    assert not _score('beat-the-planner', [[gr, gc]])['valid']           # does not start at S
    assert not _score('beat-the-planner', [[sr, sc], [sr, sc + 1]])['valid']   # does not reach G


def test_a_cell_must_be_a_pair_of_ints():
    with pytest.raises(play.PlayError):
        _score('beat-the-planner', [[1.5, 2]])


# -- next node -------------------------------------------------------------------

def test_predicting_what_astar_expands_scores_ten_and_three_stars():
    frames = play.next_node_frames(LEVELS['challenges']['next-node']['levels'][0])
    r = _score('next-node', [f['expanded'] for f in frames])
    assert _value(r, 'matches') == 10 and r['stars'] == 3


def test_a_tied_cell_counts_so_insertion_order_is_never_luck():
    frames = play.next_node_frames(LEVELS['challenges']['next-node']['levels'][0])
    tied = [i for i, f in enumerate(frames) if len(f['tied']) > 1]
    assert tied, 'this level has frames whose (f, h) ties: the rule needs one'
    guesses = [f['expanded'] for f in frames]
    for i in tied:
        guesses[i] = next(c for c in frames[i]['tied'] if c != frames[i]['expanded'])
    assert _value(_score('next-node', guesses), 'matches') == 10


def test_every_tied_cell_has_the_expanded_cells_f_and_h_and_is_open():
    for f in play.next_node_frames(LEVELS['challenges']['next-node']['levels'][0]):
        opened = {(o[0], o[1]): o for o in f['open']}
        assert tuple(f['expanded']) in opened
        for c in f['tied']:
            o = opened[tuple(c)]
            assert abs(o[2] + o[3] - f['f']) <= 1e-6 and abs(o[3] - f['h']) <= 1e-6


def test_the_predictors_references_are_what_they_score():
    lv = LEVELS['challenges']['next-node']['levels'][0]
    frames = play.next_node_frames(lv)
    for key, name in ((2, 'min_g_matches'), (3, 'min_h_matches')):
        guesses = [list(min(f['open'], key=lambda o, k=key: (o[k], o[0], o[1]))[:2]) for f in frames]
        assert _value(_score('next-node', guesses), 'matches') == lv['reference'][name]


def test_a_prediction_has_ten_cells():
    assert not _score('next-node', [[0, 0]])['valid']


# -- search the bays -----------------------------------------------------------------

def test_the_score_is_the_expected_cost_never_an_outcome():
    from coco_lab.regionsearch import SearchProblem, plan_cost
    lv = LEVELS['challenges']['search-the-bays']['levels'][0]
    p = SearchProblem.from_dict(lv['problem'])
    best = min(plan_cost(p, p.prior, p.start, o)['expected'] for o in itertools.permutations(range(4)))
    ratios = []
    for o in itertools.permutations(range(4)):
        r = _score('search-the-bays', list(o))
        assert _value(r, 'expected_cost') == round(plan_cost(p, p.prior, p.start, o)['expected'], 9)
        ratios.append(_value(r, 'ratio'))
    assert min(ratios) == 1.0 and lv['reference']['optimal_expected'] == round(best, 9)


def test_the_optimal_order_gets_three_stars_and_the_simple_policies_theirs():
    ref = LEVELS['challenges']['search-the-bays']['levels'][0]['reference']
    assert _score('search-the-bays', ref['optimal_order'])['stars'] == 3
    better = min(('nearest', 'most_likely'), key=lambda k: ref[f'{k}_ratio'])
    worse = ({'nearest', 'most_likely'} - {better}).pop()
    assert _score('search-the-bays', ref[f'{better}_order'])['stars'] == 2
    assert _score('search-the-bays', ref[f'{worse}_order'])['stars'] == 1


@pytest.mark.parametrize('order', [[0, 1, 2], [0, 1, 2, 2], [0, 1, 2, 7], [True, 1, 2, 3]])
def test_an_order_names_every_bay_once(order):
    assert not _score('search-the-bays', order)['valid']


# -- case file detective --------------------------------------------------------------

@pytest.mark.parametrize('tick, err, stars', [(40, 0.0, 3), (45, 0.5, 3), (46, 0.6, 2), (50, 1.0, 2),
                                              (60, 2.0, 1), (61, 2.1, 0), (20, 2.0, 1)])
def test_the_detective_is_scored_by_seconds_from_the_divergence(tick, err, stars):
    r = _score('case-file-detective', [tick])
    assert _value(r, 'error_s') == err and r['stars'] == stars
    assert _value(r, 'found') == (err <= 1.0)


def test_a_tick_outside_the_case_file_is_refused():
    assert not _score('case-file-detective', [101])['valid']
    with pytest.raises(play.PlayError):
        _score('case-file-detective', [4.0])


# -- the submission ----------------------------------------------------------------------

def test_a_submission_for_another_version_of_the_level_is_refused():
    s = _sub('search-the-bays', [0, 1, 2, 3])
    s['level_hash'] = '0' * 64
    with pytest.raises(play.PlayError, match='different version'):
        play.score(LEVELS, s)


@pytest.mark.parametrize('edit', [lambda s: s.update(v=2), lambda s: s.update(challenge='lost-robot'),
                                  lambda s: s.update(level='nope')])
def test_what_is_not_a_submission_is_refused(edit):
    s = _sub('search-the-bays', [0, 1, 2, 3])
    edit(s)
    with pytest.raises(play.PlayError):
        play.score(LEVELS, s)


def test_a_result_is_hashed_and_the_same_every_time():
    a = _score('beat-the-planner', play.view(LEVELS, 'beat-the-planner', 'b')['optimal_path'])
    b = _score('beat-the-planner', play.view(LEVELS, 'beat-the-planner', 'b')['optimal_path'])
    assert a == b and len(a['hash']) == 64
    c = dict(a)
    h = c.pop('hash')
    assert play.canonical(c) and h == __import__('hashlib').sha256(play.canonical(c)).hexdigest()


def test_the_map_budget_counts_ground_truth_distance():
    b = play.MapBudget(1.0, (0.0, 0.0, 0.0))
    assert not b.update((0.6, 0.0)) and b.update((0.6, 0.4)) and b.path_m == pytest.approx(1.0)


def test_every_score_names_its_metrics_and_thresholds():
    for c, inputs in (('beat-the-planner', play.view(LEVELS, 'beat-the-planner', 'b')['optimal_path']),
                      ('search-the-bays', [0, 1, 2, 3]), ('case-file-detective', [40])):
        r = _score(c, inputs)
        assert len(r['thresholds']) == 3 and all({'name', 'value', 'unit', 'meaning'} <= set(m) for m in r['metrics'])
