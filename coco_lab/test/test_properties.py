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
Lab 1's theorems, tested as properties (docs/ROADMAP.md section 8).

Each property runs on :data:`lab_maps.MAPS_PER_PROPERTY` (1,000) seeded
random maps that vary size (1-30 a side), obstacle density (0-0.6),
connectivity (4/8), the diagonal cost (sqrt(2) or 1), the corner-cutting
rule and a cost layer. The properties about path cost draw the goal from
the start's component, so all 1,000 of their maps have a path; the two
that are about "no path" too (w = 0, and all-five agreement) draw it
anywhere and split a fifth (half, for agreement) of their maps with a
wall. The oracle is networkx's Dijkstra on the identical
graph, and every optimal algorithm must agree with it exactly, within
:data:`lab_maps.REL_TOL`.

Run with ``--hypothesis-show-statistics`` to see how many maps each
property actually ran and how they split across move models and outcomes.
"""

from coco_lab.graph import HEURISTICS
from coco_lab.grid import Grid
from coco_lab.heuristics import analyse
from coco_lab.search import search, TIE_BREAKS
from hypothesis import given, strategies as st
from lab_maps import (cases, close, isclose_or_none, oracle_cost,
                      oracle_graph, PROPERTY_SETTINGS, record_outcome)
import networkx as nx
import pytest

tie_breaks = st.sampled_from(TIE_BREAKS)
any_heuristic = st.sampled_from(HEURISTICS)


def admissible_heuristics(grid):
    """Return the heuristics the analysis certifies for this move model."""
    return [h for h in HEURISTICS
            if analyse(h, grid.move_model).admissible]


def cell(loc):
    """Return ``(row, col)`` of a trace location ``(row, col, sub)``."""
    return (loc[0], loc[1])


# -- 1. A* cost == Dijkstra cost, admissible heuristic ----------------------

@PROPERTY_SETTINGS
@given(case=cases(reachable=True), data=st.data(), tie=tie_breaks)
def test_astar_cost_equals_dijkstra_with_admissible_heuristic(case, data,
                                                              tie):
    h = data.draw(st.sampled_from(admissible_heuristics(case.grid)))
    optimal = oracle_cost(case)
    record_outcome(optimal is not None)
    dj = search(case.grid, case.start, case.goal, 'dijkstra', tie_break=tie)
    a = search(case.grid, case.start, case.goal, 'astar', heuristic=h,
               tie_break=tie)
    assert isclose_or_none(dj.cost, optimal), (dj.cost, optimal)
    assert isclose_or_none(a.cost, optimal), (a.cost, optimal, h)
    assert a.status == dj.status


# -- 2. A*'s expanded set is a subset of Dijkstra's, up to ties -------------

@PROPERTY_SETTINGS
@given(case=cases(reachable=True), data=st.data(), tie=tie_breaks)
def test_astar_expands_a_subset_of_dijkstra_up_to_ties(case, data, tie):
    """
    Define "up to ties" exactly.

    Let ``C*`` be the optimal cost and ``g*(s)`` the optimal cost from the
    start to ``s``. Dijkstra expands every state with ``g*(s) < C*`` before
    the goal, and *some* of those with ``g*(s) == C*``, depending on tie
    order. A* with a consistent heuristic expands only states with
    ``g*(s) + h(s) <= C*``. So the claim is::

        A  is a subset of  D  union  { s : g*(s) == C* }

    with ``==`` meaning equal within REL_TOL. The tie set is the only
    exception allowed. When there is no path, both exhaust the start's
    component and the sets must be equal.
    """
    h = data.draw(st.sampled_from(admissible_heuristics(case.grid)))
    assert analyse(h, case.grid.move_model).consistent
    graph = oracle_graph(case.grid)
    dist = nx.single_source_dijkstra_path_length(graph, case.start,
                                                 weight='weight')
    optimal = dist.get(case.goal)
    record_outcome(optimal is not None)
    dj = search(case.grid, case.start, case.goal, 'dijkstra', tie_break=tie)
    a = search(case.grid, case.start, case.goal, 'astar', heuristic=h,
               tie_break=tie)
    d_set = {cell(x) for x in dj.expanded}
    a_set = {cell(x) for x in a.expanded}
    assert len(a_set) == len(a.expanded), 'A* expanded a state twice'
    if optimal is None:
        assert a_set == d_set
        return
    extra = a_set - d_set
    ties = {s for s in extra if close(dist[s], optimal)}
    assert extra == ties, (
        f'A* expanded {sorted(extra - ties)} which Dijkstra did not, '
        f'and they are not ties at C* = {optimal}')
    for s in a_set:
        bound = dist[s] + case.grid.heuristic(h, s, case.goal)
        assert bound <= optimal or close(bound, optimal), (s, bound, optimal)


# -- 3. weighted A* cost <= w x optimal, w >= 1, admissible heuristic -------

weights_ge_1 = st.one_of(st.sampled_from([1.0, 1.5, 2.0, 3.0, 5.0]),
                         st.floats(min_value=1.0, max_value=5.0))


@PROPERTY_SETTINGS
@given(case=cases(reachable=True), data=st.data(), w=weights_ge_1, tie=tie_breaks)
def test_weighted_astar_is_within_w_of_optimal(case, data, w, tie):
    h = data.draw(st.sampled_from(admissible_heuristics(case.grid)))
    optimal = oracle_cost(case)
    record_outcome(optimal is not None)
    r = search(case.grid, case.start, case.goal, 'weighted_astar',
               heuristic=h, weight=w, tie_break=tie)
    if optimal is None:
        assert not r.found
        return
    assert r.found
    assert r.cost >= optimal or close(r.cost, optimal)
    assert r.cost <= w * optimal or close(r.cost, w * optimal), (
        r.cost, w, optimal, h)


# -- 4. w = 0 reproduces Dijkstra -------------------------------------------

@PROPERTY_SETTINGS
@given(case=cases(), h=any_heuristic, tie=tie_breaks)
def test_weight_zero_reproduces_dijkstra(case, h, tie):
    """Cost, and in fact the whole event stream: f = g + 0*h = g."""
    optimal = oracle_cost(case)
    record_outcome(optimal is not None)
    dj = search(case.grid, case.start, case.goal, 'dijkstra', heuristic=h,
                tie_break=tie)
    w0 = search(case.grid, case.start, case.goal, 'weighted_astar',
                heuristic=h, weight=0.0, tie_break=tie)
    assert isclose_or_none(w0.cost, optimal)
    assert w0.cost == dj.cost
    assert w0.trace.events == dj.trace.events
    assert w0.trace.summary == dj.trace.summary


# -- 5. BFS is optimal under unit edge costs --------------------------------

unit_cost_cases = st.one_of(
    cases(connectivity=4, cost_layer=False, reachable=True),
    cases(connectivity=8, diagonal_cost=1.0, cost_layer=False,
          reachable=True),
)


@PROPERTY_SETTINGS
@given(case=unit_cost_cases, h=any_heuristic)
def test_bfs_is_optimal_under_unit_costs(case, h):
    assert case.unit_costs
    graph = oracle_graph(case.grid)
    optimal = oracle_cost(case, graph)
    record_outcome(optimal is not None)
    r = search(case.grid, case.start, case.goal, 'bfs', heuristic=h)
    assert isclose_or_none(r.cost, optimal)
    if optimal is not None:
        hops = nx.shortest_path_length(graph, case.start, case.goal)
        assert r.trace.summary['path_steps'] == hops


# -- 6. greedy best-first never beats optimal; strictly worse somewhere -----

@PROPERTY_SETTINGS
@given(case=cases(reachable=True), h=any_heuristic, tie=tie_breaks)
def test_greedy_cost_is_never_below_optimal(case, h, tie):
    optimal = oracle_cost(case)
    record_outcome(optimal is not None)
    r = search(case.grid, case.start, case.goal, 'greedy', heuristic=h,
               tie_break=tie)
    if optimal is None:
        assert not r.found
        return
    assert r.found
    assert r.cost >= optimal or close(r.cost, optimal)


#: Committed counterexample: greedy best-first, Manhattan, 4-connected. From
#: S it takes the top row (every step lowers h), walks into the pocket
#: beside the wall, and has to come down and round: 7 moves against 5.
GREEDY_COUNTEREXAMPLE = """
G#...
....S
.....
.....
.....
"""


@pytest.mark.parametrize('tie', TIE_BREAKS)
def test_greedy_is_strictly_worse_on_the_committed_counterexample(tie):
    grid, marks = Grid.from_ascii(GREEDY_COUNTEREXAMPLE, connectivity=4)
    start, goal = marks['S'], marks['G']
    greedy = search(grid, start, goal, 'greedy', heuristic='manhattan',
                    tie_break=tie)
    optimal = search(grid, start, goal, 'dijkstra')
    assert optimal.cost == 5.0
    assert greedy.cost == 7.0
    assert greedy.cost > optimal.cost
    assert greedy.path[:4] == [(1, 4), (0, 4), (0, 3), (0, 2)]


# -- 7. all five agree on "no path" -----------------------------------------

@PROPERTY_SETTINGS
@given(case=cases(wall_probability=0.5), h=any_heuristic,
       w=st.floats(min_value=0.0, max_value=5.0), tie=tie_breaks)
def test_all_five_agree_on_no_path(case, h, w, tie):
    reachable = nx.has_path(oracle_graph(case.grid), case.start, case.goal)
    record_outcome(reachable)
    statuses = {}
    for algorithm in ('bfs', 'dijkstra', 'astar', 'greedy',
                      'weighted_astar'):
        kw = {'weight': w} if algorithm == 'weighted_astar' else {}
        statuses[algorithm] = search(case.grid, case.start, case.goal,
                                     algorithm, heuristic=h, tie_break=tie,
                                     **kw).status
    expected = 'found' if reachable else 'no_path'
    assert set(statuses.values()) == {expected}, statuses
