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
Lab 4's search, proven: Bayes, expected cost, optimality, no truth.

The last is the rule that a policy never sees the truth.

Properties run on :data:`lab_maps.MAPS_PER_PROPERTY` (1,000) seeded random
problems each, checked against brute force: every truth and every
detection outcome enumerated (Bayes, expected cost), every order costed
(optimality, the index rule).
"""

import ast
from dataclasses import fields
import inspect
import itertools
import math
import os
import sys

from coco_lab import regionsearch as rs
from coco_lab.maps import load_nav2
from hypothesis import given, strategies as st
from lab_maps import PROPERTY_SETTINGS
import pytest

HERE = os.path.dirname(__file__)
REPO = os.path.join(HERE, '..', '..')
NAV2_YAML = os.path.join(REPO, 'gazebo_models', 'maps',
                         'coco_navigation.yaml')

# -- random problems ---------------------------------------------------------------


def _region(k):
    return rs.Region(f'r{k}', f'R{k}', (0.0, float(k)),
                     (1.0, 2.0, k - 0.5, k + 0.5), (0.9, float(k), 0.0),
                     (0.0, float(k)), 0.0)


@st.composite
def problems(draw, max_n=5, order_free=False):
    """
    Draw a random problem: costs, detection and prior.

    ``order_free``: every region costs the same to reach from anywhere
    (the index rule's hypothesis).
    """
    n = draw(st.integers(1, max_n))
    regions = tuple(_region(k) for k in range(n))
    ids = [r.id for r in regions]
    cost = st.floats(0.0, 20.0, allow_nan=False)
    if order_free:
        c = [draw(st.floats(0.1, 20.0)) for _ in ids]
        travel = {a: {b: c[j] for j, b in enumerate(ids)}
                  for a in ['home'] + ids}
    else:
        travel = {a: {b: (0.0 if a == b else draw(cost)) for b in ids}
                  for a in ['home'] + ids}
    det = tuple(draw(st.floats(0.05, 1.0)) for _ in ids)
    w = [draw(st.floats(0.0, 1.0)) for _ in ids]
    if sum(w) <= 0:
        w = [1.0] * n
    p = rs.SearchProblem(regions, 'home', (0.0, 0.0), travel, det,
                         rs.normalise(w))
    p.validate()
    return p


def brute_posterior(prior, det, surveyed, i, found):
    """
    P(truth | the surveys so far), by enumerating the joint.

    ``surveyed`` is the earlier misses; then region ``i`` with ``found``.
    """
    joint = []
    for t, p in enumerate(prior):
        like = p
        for j in surveyed:
            like *= (1 - det[j]) if t == j else 1.0
        hit = det[i] if t == i else 0.0
        like *= hit if found else 1 - hit
        joint.append(like)
    s = math.fsum(joint)
    return [x / s for x in joint]


def brute_expected(problem, belief, order):
    """
    E[cost], by enumerating where the target is and what each look sees.

    The search stops at the first find; one that finds nothing drives the
    whole order.
    """
    total_e = 0.0
    legs, at = [], problem.start
    for i in order:
        legs.append(problem.leg(at, i))
        at = problem.ids[i]
    cum = list(itertools.accumulate(legs)) or [0.0]
    for t, p in enumerate(belief):
        if p == 0:
            continue
        if t in order:
            k = order.index(t)
            d = problem.detection[t]
            total_e += p * (d * cum[k] + (1 - d) * cum[-1])
        else:
            total_e += p * cum[-1]
    return total_e


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# -- Bayes -------------------------------------------------------------------------

@PROPERTY_SETTINGS
@given(problems(), st.data())
def test_update_is_bayes_rule_against_the_enumerated_joint(p, data):
    order = data.draw(st.permutations(range(p.n)))
    k = data.draw(st.integers(0, p.n - 1))
    belief = list(p.prior)
    misses = []
    for i in order[:k]:
        if belief[i] * p.detection[i] >= 1.0:
            break
        belief = list(rs.update(belief, i, False, p.detection[i]))
        misses.append(i)
        expect = brute_posterior(p.prior, p.detection, misses[:-1], i,
                                 False)
        assert all(close(a, b, 1e-7) for a, b in zip(belief, expect))
        assert close(math.fsum(belief), 1.0)


@PROPERTY_SETTINGS
@given(problems(), st.data())
def test_a_miss_lowers_the_searched_region_and_keeps_the_others_ratios(
        p, data):
    i = data.draw(st.integers(0, p.n - 1))
    if p.prior[i] * p.detection[i] >= 1.0:
        return
    post = rs.update(p.prior, i, False, p.detection[i])
    assert post[i] <= p.prior[i] + 1e-12
    others = [j for j in range(p.n) if j != i]
    for a, b in itertools.combinations(others, 2):
        assert close(post[a] * p.prior[b], post[b] * p.prior[a], 1e-7)
    if p.detection[i] == 1.0:
        assert post[i] == 0.0


def test_a_find_is_certain_and_a_perfect_miss_is_proof():
    assert rs.update((0.25,) * 4, 2, True, 0.9) == (0.0, 0.0, 1.0, 0.0)
    post = rs.update((0.25,) * 4, 0, False, 1.0)
    assert post[0] == 0.0 and all(close(v, 1 / 3) for v in post[1:])
    # With a camera that can miss, a miss is evidence, not proof.
    post = rs.update((0.25,) * 4, 0, False, 0.9)
    assert close(post[0], 0.025 / 0.775) and post[0] > 0


def test_an_impossible_miss_is_refused_not_repaired():
    with pytest.raises(rs.SearchError):
        rs.update((1.0, 0.0), 0, False, 1.0)


# -- expected cost and optimality --------------------------------------------------

@PROPERTY_SETTINGS
@given(problems(), st.data())
def test_plan_cost_equals_the_enumerated_expectation(p, data):
    order = list(data.draw(st.permutations(range(p.n))))
    k = data.draw(st.integers(1, p.n))
    e = rs.plan_cost(p, p.prior, 'home', order[:k])['expected']
    assert close(e, brute_expected(p, p.prior, order[:k]), 1e-7)


@PROPERTY_SETTINGS
@given(problems())
def test_the_robot_order_is_no_worse_than_any_other_order(p):
    best = rs.optimal_order(p, p.prior, 'home', range(p.n))
    e = rs.plan_cost(p, p.prior, 'home', best)['expected']
    for perm in itertools.permutations(range(p.n)):
        assert e <= rs.plan_cost(p, p.prior, 'home', perm)['expected'] + \
            1e-9 * max(1.0, e)


@PROPERTY_SETTINGS
@given(problems(order_free=True))
def test_index_rule_is_optimal_when_costs_do_not_depend_on_order(p):
    # The classic result: with order-independent costs, surveying by
    # p d / c, largest first, minimises the expected cost.
    by_ratio = rs.ratio_order(p, p.prior, range(p.n))
    best = rs.optimal_order(p, p.prior, 'home', range(p.n))
    a = rs.plan_cost(p, p.prior, 'home', by_ratio)['expected']
    b = rs.plan_cost(p, p.prior, 'home', best)['expected']
    assert close(a, b, 1e-7)


def test_ties_go_to_the_lowest_region_index():
    p = rs.SearchProblem(tuple(_region(k) for k in range(3)), 'home',
                         (0.0, 0.0),
                         {a: {b: 1.0 for b in ('r0', 'r1', 'r2')}
                          for a in ('home', 'r0', 'r1', 'r2')},
                         (1.0, 1.0, 1.0), rs.uniform(3))
    assert rs.optimal_order(p, p.prior, 'home', range(3)) == (0, 1, 2)
    for policy in ('expected_cost', 'nearest', 'most_likely'):
        assert rs.choose(policy, p, rs.SearchView(p.prior, (), 'home')) == 0


@PROPERTY_SETTINGS
@given(problems(), st.data())
def test_candidate_costs_rank_the_policy_choice_first(p, data):
    view = rs.SearchView(p.prior, (), 'home')
    cands = rs.candidate_costs(p, view)
    chosen = rs.choose('expected_cost', p, view)
    best = min(c for c in cands if c is not None)
    assert close(cands[chosen], best, 1e-7)
    assert close(best, rs.plan_cost(
        p, p.prior, 'home',
        rs.optimal_order(p, p.prior, 'home', range(p.n)))['expected'], 1e-7)


# -- the Sketch loop ---------------------------------------------------------------

def line3():
    """Three regions on a line, cheapest first: the policy goes A, B, C."""
    regs = tuple(_region(k) for k in range(3))
    travel = {'home': {'r0': 1.0, 'r1': 2.0, 'r2': 3.0},
              'r0': {'r0': 0.0, 'r1': 1.0, 'r2': 2.0},
              'r1': {'r0': 1.0, 'r1': 0.0, 'r2': 1.0},
              'r2': {'r0': 2.0, 'r1': 1.0, 'r2': 0.0}}
    return rs.SearchProblem(regs, 'home', (0.0, 0.0), travel,
                            (1.0, 1.0, 1.0), rs.uniform(3))


def test_negative_search_finds_it_in_the_last_region_checked():
    p = line3()
    tr = rs.run_search(p, 'expected_cost', truth=2, seed=0)
    s = tr.summary
    assert s['order'] == ['r0', 'r1', 'r2']
    assert s['status'] == 'discovered' and s['discovered'] == 'r2'
    assert s['discovered_at'] == 3 and rs.challenge_passed(tr)
    kinds = [rs.KINDS[k] for k in tr.kind]
    assert kinds == ['select', 'survey', 'mark', 'select', 'survey', 'mark',
                     'select', 'survey', 'discover']
    # Both earlier regions were marked searched BEFORE the discovery.
    marks = [tr.region[e] for e, k in enumerate(kinds) if k == 'mark']
    assert marks == [0, 1]
    assert [tr.outcome[e] for e, k in enumerate(kinds)
            if k == 'survey'] == [0, 0, 1]
    # The belief after each miss: 1/2 each, then all on C.
    n = p.n
    after_a = tr.belief[2 * n:3 * n]
    after_b = tr.belief[5 * n:6 * n]
    assert after_a == pytest.approx([0.0, 0.5, 0.5])
    assert after_b == pytest.approx([0.0, 0.0, 1.0])


def test_giving_up_after_the_first_region_fails_the_challenge():
    p = line3()
    tr = rs.run_search(p, 'expected_cost', truth=2, seed=0, max_surveys=1)
    assert tr.summary['status'] == 'stopped'
    assert tr.summary['order'] == ['r0'] and tr.summary['discovered'] is None
    assert not rs.challenge_passed(tr)


def test_a_learner_order_is_followed_and_scored_on_the_same_problem():
    p = line3()
    # Same problem, same placement (the target in r0): only the order
    # differs, so the cost difference is the order's.
    mine = rs.run_search(p, 'given', truth=0, given_order=(2, 1, 0))
    robot = rs.run_search(p, 'expected_cost', truth=0)
    assert mine.summary['order'] == ['r2', 'r1', 'r0']
    assert mine.summary['cost'] == 3.0 + 1.0 + 1.0
    assert robot.summary['order'] == ['r0'] and robot.summary['cost'] == 1.0
    # With the target in r2 the two orders happen to drive the same 3 m:
    assert rs.run_search(p, 'given', truth=2,
                         given_order=(2, 1, 0)).summary['cost'] == 3.0
    assert rs.run_search(p, 'expected_cost', truth=2).summary['cost'] == 3.0
    # Expected cost is what the robot minimises, not this one outcome:
    e_mine = rs.plan_cost(p, p.prior, 'home', (2, 1, 0))['expected']
    e_robot = rs.plan_cost(p, p.prior, 'home', (0, 1, 2))['expected']
    assert e_robot < e_mine


def test_a_short_learner_order_ends_exhausted_without_the_target():
    p = line3()
    tr = rs.run_search(p, 'given', truth=2, given_order=(0, 1))
    assert tr.summary['status'] == 'exhausted'
    assert not rs.challenge_passed(tr)


@PROPERTY_SETTINGS
@given(problems(), st.integers(0, 2**31 - 1), st.data())
def test_a_seeded_search_replays_exactly(p, seed, data):
    truth = data.draw(st.integers(0, p.n - 1))
    a = rs.run_search(p, 'expected_cost', truth, seed=seed, passes=2)
    b = rs.run_search(p, 'expected_cost', truth, seed=seed, passes=2)
    assert (a.kind, a.region, a.outcome, a.cost, a.belief) == \
        (b.kind, b.region, b.outcome, b.cost, b.belief)
    assert a.summary == b.summary


# -- the anti-cheat rule -----------------------------------------------------------

def test_no_field_a_policy_reads_can_hold_the_truth():
    assert {f.name for f in fields(rs.SearchView)} == {
        'belief', 'searched', 'location', 'given_order'}
    assert {f.name for f in fields(rs.SearchProblem)} == {
        'regions', 'start', 'start_xy', 'travel', 'detection', 'prior',
        'meta'}
    assert list(inspect.signature(rs.choose).parameters) == [
        'policy', 'problem', 'view']


@PROPERTY_SETTINGS
@given(problems(), st.data())
def test_choices_depend_on_observations_not_on_where_the_target_is(p, data):
    """
    Two worlds that produce the same observations get the same choices.

    With the target in region t and every look at t missing (a camera
    that never fires), the robot sees only misses -- exactly what it
    would see with no target at all. Its choices must be identical.
    """
    t = data.draw(st.integers(0, p.n - 1))
    blind = [0.0] * p.n
    a = rs.run_search(p, 'expected_cost', t, true_detection=blind)
    b = rs.run_search(p, 'expected_cost', None, true_detection=blind)
    assert a.summary['order'] == b.summary['order']
    assert (a.kind, a.region, a.belief) == (b.kind, b.region, b.belief)


def test_the_truth_is_read_on_one_line_only():
    src = inspect.getsource(rs.run_search)
    tree = ast.parse(src.strip() if src.startswith(' ') else src)
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Name) and n.id == 'truth'
             and isinstance(n.ctx, ast.Load)]
    lines = sorted({n.lineno for n in reads})
    body = src.splitlines()
    uses = [body[ln - 1].strip() for ln in lines]
    # Validation, the draw, and the summary -- nothing a policy runs.
    assert any('found = truth == nxt' in u for u in uses), uses
    assert all(('found = truth' in u) or ('truth is not None' in u)
               or ('truth is None' in u) or ('problem.ids[truth]' in u)
               or ('out of range' in u) for u in uses), uses
    assert sum('found = truth' in u for u in uses) == 1


def test_regionsearch_imports_nothing_that_knows_the_world():
    tree = ast.parse(open(rs.__file__).read())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add('.' if node.level else node.module.split('.')[0])
    assert mods <= {'dataclasses', 'itertools', 'math', 'random', 'typing',
                    '.'}, mods
    text = open(rs.__file__).read()
    for word in ('manifest', 'episode', 'region_map', 'lane_for_colour',
                 'resolve_lane', 'model/coco/odometry'):
        assert word not in text, word


def test_replay_decisions_recovers_a_recorded_order():
    p = line3()
    tr = rs.run_search(p, 'expected_cost', truth=2)
    outcomes = [('r0', False), ('r1', False), ('r2', True)]
    assert rs.replay_decisions(p, 'expected_cost', outcomes) == \
        tr.summary['order']


# -- COCO's arena ------------------------------------------------------------------

#: coco_lab's A* on gazebo_models/maps/coco_navigation, inflated 0.20 m,
#: between home (SPAWN_XY) and each bay's pre-ramp pose. Derived; pinned so
#: a map or planner change is seen.
ARENA_TRAVEL = {
    'home': {'bay_1': 7.797056, 'bay_2': 3.826346, 'bay_3': 3.767767,
             'bay_4': 7.767767},
    'bay_1': {'bay_1': 0.0, 'bay_2': 6.943503, 'bay_3': 10.943503,
              'bay_4': 14.943503},
    'bay_2': {'bay_1': 6.943503, 'bay_2': 0.0, 'bay_3': 6.972792,
              'bay_4': 10.972792},
    'bay_3': {'bay_1': 10.943503, 'bay_2': 6.972792, 'bay_3': 0.0,
              'bay_4': 6.972792},
    'bay_4': {'bay_1': 14.943503, 'bay_2': 10.972792, 'bay_3': 6.972792,
              'bay_4': 0.0},
}


def _robot():
    sys.path.insert(0, os.path.join(REPO, 'coco_config'))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'coco_robot_for_test', os.path.join(REPO, 'coco_config',
                                                'coco_config', 'robot.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


def arena(d):
    robot = _robot()
    regs = rs.bay_regions(robot.TARGET_REGIONS, robot.CLIMB_END_X)
    return rs.bay_problem(regs, robot.SPAWN_XY, ARENA_TRAVEL, d)


def test_the_arena_travel_table_is_coco_labs_astar_on_the_nav2_map():
    robot = _robot()
    regs = rs.bay_regions(robot.TARGET_REGIONS, robot.CLIMB_END_X)
    m = load_nav2(NAV2_YAML, 'coco_navigation')
    got = rs.travel_costs(m, rs.places_of(regs, robot.SPAWN_XY),
                          [r.id for r in regs], 0.20, offset=(2.0, 0.0))
    assert got == ARENA_TRAVEL


def test_the_bays_are_coco_configs_regions_with_derived_survey_cost():
    p = arena(0.9)
    assert p.ids == ('bay_1', 'bay_2', 'bay_3', 'bay_4')
    assert [r.approach for r in p.regions] == [
        (0.5, -6.0), (0.5, -2.0), (0.5, 2.0), (0.5, 6.0)]
    # Up the ramp to the end of the climb and back: 2 x (2.95 - 0.5).
    assert all(r.survey_cost == pytest.approx(4.9) for r in p.regions)
    assert p.prior == (0.25,) * 4


def test_the_arena_order_with_a_perfect_camera_is_nearest_first():
    p = arena(1.0)
    order = rs.optimal_order(p, p.prior, 'home', range(4))
    assert [p.ids[i] for i in order] == ['bay_3', 'bay_2', 'bay_1', 'bay_4']
    nearest = rs.run_search(p, 'nearest', None)
    assert nearest.summary['order'] == ['bay_3', 'bay_2', 'bay_1', 'bay_4']


def test_the_arena_order_when_the_camera_can_miss_is_not_nearest_first():
    """
    The committed counterexample: at d = 0.9 nearest-first is beaten.

    A miss can leave the target unfound, and a search that finds nothing
    drives the whole tour -- so the tour's length starts to count, and the
    robot swaps bay_2 for bay_4.
    """
    p = arena(0.9)
    order = rs.optimal_order(p, p.prior, 'home', range(4))
    assert [p.ids[i] for i in order] == ['bay_3', 'bay_4', 'bay_2', 'bay_1']
    e_best = rs.plan_cost(p, p.prior, 'home', order)['expected']
    e_near = rs.plan_cost(p, p.prior, 'home', (2, 1, 0, 3))['expected']
    e_likely = rs.plan_cost(p, p.prior, 'home', (0, 1, 2, 3))['expected']
    assert e_best == pytest.approx(30.448354875)
    assert e_near == pytest.approx(30.832245925)
    assert e_likely == pytest.approx(32.264463825)
    assert e_best < e_near < e_likely


def test_the_arena_order_does_not_depend_on_the_colour_asked_for():
    # The problem has no colour in it at all: the order is the same
    # whichever target was requested, and wherever it stands.
    p = arena(0.9)
    orders = {tuple(rs.run_search(p, 'expected_cost', t,
                                  true_detection=[0.0] * 4).summary['order'])
              for t in range(4)}
    assert orders == {('bay_3', 'bay_4', 'bay_2', 'bay_1')}
