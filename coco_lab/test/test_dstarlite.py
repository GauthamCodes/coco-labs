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
D* Lite (coco_lab.dstarlite): hand-checked cases, then properties.

The properties run on :data:`lab_maps.MAPS_PER_PROPERTY` (1,000) seeded
random maps (Lab 1's generator: size, density, 4/8 connectivity, diagonal
cost, corner rule, cost layer) and, on each, a seeded sequence of world
changes and robot moves. After EVERY replan D* Lite's ``g(start)`` must
equal networkx's Dijkstra on the CURRENT graph from the CURRENT start,
and the path it returns must be a sequence of real moves costing exactly
that.
"""

import math
import random

from coco_lab.dstarlite import (DStarLite, EVENT_KINDS, grid_changes,
                                INF_SENTINEL, key_less, ReplanError)
from coco_lab.graph import HEURISTICS
from coco_lab.grid import Grid
from coco_lab.heuristics import analyse
from coco_lab.search import search
from hypothesis import given, strategies as st
from lab_maps import (cases, isclose_or_none, oracle_graph,
                      PROPERTY_SETTINGS, record_outcome)
import networkx as nx
import pytest

EXPAND, RAISE, UPDATE, CHANGE, PATH, MOVE = range(len(EVENT_KINDS))


def consistent(grid):
    """Return the heuristics analyse() certifies consistent here."""
    return [h for h in HEURISTICS if analyse(h, grid.move_model).consistent]


def oracle(grid, start, goal):
    """Return networkx's optimal cost, or None."""
    try:
        return nx.dijkstra_path_length(oracle_graph(grid), start, goal,
                                       weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def check_path(grid, path, start, goal, cost):
    """Assert the path is real moves from start to goal, of ``cost``."""
    assert path[0] == start and path[-1] == goal
    total = 0.0
    for a, b in zip(path, path[1:]):
        assert b in list(grid.neighbours(a)), (a, b)
        total += grid.edge_cost(a, b)
    assert math.isclose(total, cost, rel_tol=1e-9, abs_tol=1e-9)


# -- hand-checked ---------------------------------------------------------------

MAZE = """
S..#....
.#.#.##.
.#...#..
.####.#.
......#G
"""


def test_a_known_graph_has_its_known_optimal_cost():
    # 4-connected, unit costs. The bottom row dead-ends at (4, 6) and
    # (2, 5) walls off the middle, so the only route is over the top:
    # (0,0) (0,1) (0,2) (1,2) (2,2) (2,3) (2,4) (1,4) (0,4) (0,5) (0,6)
    # (0,7) (1,7) (2,7) (3,7) (4,7) -- 15 moves, counted by hand.
    grid, m = Grid.from_ascii(MAZE, connectivity=4)
    d = DStarLite(grid, m['S'], m['G'], 'manhattan')
    assert d.compute()
    assert d.g_of(m['S']) == 15.0
    assert d.path() == [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (2, 3),
                        (2, 4), (1, 4), (0, 4), (0, 5), (0, 6), (0, 7),
                        (1, 7), (2, 7), (3, 7), (4, 7)]
    assert oracle(grid, m['S'], m['G']) == 15.0


def test_eight_connected_known_cost():
    # an open 5 x 5 with sqrt(2) diagonals: corner to corner is 4 sqrt(2)
    grid = Grid(5, 5, connectivity=8)
    d = DStarLite(grid, (0, 0), (4, 4), 'octile')
    assert d.compute()
    assert math.isclose(d.g_of((0, 0)), 4 * math.sqrt(2))


def test_blocking_the_route_forces_the_detour_and_the_cost_rises():
    grid, m = Grid.from_ascii("""
S....
.###.
.....
.###.
....G
""", connectivity=4)
    d = DStarLite(grid, m['S'], m['G'], 'manhattan')
    assert d.compute() and d.g_of(m['S']) == 8.0
    # close the middle row's both ends: only the outer ring remains
    blocked = [grid.is_blocked((r, c)) for r in range(5) for c in range(5)]
    for r, c in ((2, 0), (2, 1)):
        blocked[r * 5 + c] = True
    new = Grid(5, 5, blocked, connectivity=4)
    _, aff = grid_changes(grid, new)
    d.apply_changes(new, aff)
    assert d.compute()
    assert d.g_of(m['S']) == 8.0          # the right-hand route is as short
    for r, c in ((2, 4), (2, 3)):
        blocked[r * 5 + c] = True
    newer = Grid(5, 5, blocked, connectivity=4)
    _, aff = grid_changes(new, newer)
    d.apply_changes(newer, aff)
    assert not d.compute()                # both routes now cut
    assert d.path() == []


def test_a_new_opening_lowers_the_cost():
    grid, m = Grid.from_ascii("""
S#G
.#.
...
""", connectivity=4)
    d = DStarLite(grid, m['S'], m['G'], 'manhattan')
    assert d.compute() and d.g_of(m['S']) == 6.0
    new = Grid(3, 3, [False] * 9, connectivity=4)
    _, aff = grid_changes(grid, new)
    d.apply_changes(new, aff)
    assert d.compute() and d.g_of(m['S']) == 2.0


def test_inconsistent_heuristic_is_refused():
    grid = Grid(4, 4, connectivity=8, diagonal_cost=1.0)
    with pytest.raises(ReplanError, match='consistent'):
        DStarLite(grid, (0, 0), (3, 3), 'octile')


def test_blocked_start_or_goal_is_refused():
    grid, m = Grid.from_ascii('S#G', connectivity=4)
    with pytest.raises(ReplanError):
        DStarLite(grid, (0, 1), m['G'])
    d = DStarLite(grid, m['S'], m['G'], 'manhattan')
    new = Grid(3, 1, [False, True, True], connectivity=4)
    _, aff = grid_changes(grid, new)
    with pytest.raises(ReplanError, match='goal'):
        d.apply_changes(new, aff)


def test_grid_changes_marks_each_change_and_its_neighbourhood():
    a = Grid(5, 5)
    b = Grid(5, 5, [i == 12 for i in range(25)])
    changed, affected = grid_changes(a, b)
    assert changed == [(2, 2)]
    assert affected == [(r, c) for r in range(1, 4) for c in range(1, 4)]
    with pytest.raises(ReplanError):
        grid_changes(a, Grid(4, 5))


def test_key_comparison_treats_last_bit_differences_as_equal():
    # the measured failure: equal sums formed in a different order
    assert not key_less((7.242640687119286, 2.0), (7.242640687119285, 1.0))
    assert key_less((7.242640687119286, 1.0), (7.242640687119285, 2.0))
    assert key_less((1.0, 0.0), (2.0, 0.0))
    assert not key_less((math.inf, math.inf), (math.inf, math.inf))
    assert key_less((5.0, 1.0), (math.inf, math.inf))


def test_the_trace_counts_agree_and_encode_infinity():
    grid, m = Grid.from_ascii(MAZE, connectivity=4)
    d = DStarLite(grid, m['S'], m['G'], 'manhattan')
    d.compute()
    cols = d.trace.columns
    pops = sum(1 for k in cols['kind'] if k in (EXPAND, RAISE))
    assert pops == d.expansions == sum(d.round_expansions)
    assert d.trace.count(PATH) == len(d.path())
    assert all(v == INF_SENTINEL or v >= 0 for v in cols['g'] + cols['rhs'])
    assert {len(v) for v in cols.values()} == {len(d.trace)}


def test_grid_adjacency_is_symmetric_so_neighbours_are_predecessors():
    # D* Lite uses neighbours() as pred() on graphs without predecessors()
    rng = random.Random(7)
    for _ in range(200):
        w, h = rng.randint(1, 12), rng.randint(1, 12)
        g = Grid(w, h, [rng.random() < 0.3 for _ in range(w * h)],
                 connectivity=rng.choice([4, 8]),
                 corner_cutting=rng.random() < 0.5)
        for s in g.states():
            for n in g.neighbours(s):
                assert s in list(g.neighbours(n))


def test_same_inputs_same_trace():
    def run():
        grid, m = Grid.from_ascii(MAZE, connectivity=8)
        d = DStarLite(grid, m['S'], m['G'], 'octile')
        d.compute()
        d.move_to(d.path()[1])
        blocked = [grid.is_blocked((r, c)) for r in range(5)
                   for c in range(8)]
        blocked[2 * 8 + 4] = True
        new = Grid(8, 5, blocked, connectivity=8)
        d.apply_changes(new, grid_changes(grid, new)[1])
        d.compute()
        return d.trace.columns
    assert run() == run()


# -- properties: 1,000 seeded maps, each with a change sequence ----------------

def mutate(grid, rng, keep):
    """Return a grid with 1-4 random cells toggled / re-costed."""
    w, h = grid.width, grid.height
    blocked = [grid.is_blocked((r, c)) for r in range(h) for c in range(w)]
    layer = grid.describe()['cost_layer']
    cost = [grid.cost_at((r, c)) for r in range(h) for c in range(w)] \
        if layer else None
    for _ in range(rng.randint(1, 4)):
        r, c = rng.randrange(h), rng.randrange(w)
        if (r, c) in keep:
            continue
        if cost is not None and rng.random() < 0.5:
            cost[r * w + c] = float(rng.randrange(0, 253))
        else:
            blocked[r * w + c] = not blocked[r * w + c]
    return Grid(w, h, blocked, cost,
                connectivity=grid.move_model.connectivity,
                diagonal_cost=grid.move_model.diagonal_cost,
                corner_cutting=grid.corner_cutting,
                cost_weight=grid.cost_weight)


@PROPERTY_SETTINGS
@given(case=cases(), data=st.data(),
       seed=st.integers(min_value=0, max_value=2 ** 31))
def test_dstar_lite_is_optimal_after_every_change_and_move(case, data, seed):
    grid = case.grid
    h = data.draw(st.sampled_from(consistent(grid)))
    d = DStarLite(grid, case.start, case.goal, h)
    rng = random.Random(seed)
    for _ in range(5):
        found = d.compute()
        want = oracle(grid, d.start, case.goal)
        record_outcome(want is not None)
        assert found == (want is not None)
        assert isclose_or_none(d.g_of(d.start) if found else None, want)
        if found:
            check_path(grid, d.path(), d.start, case.goal, want)
            path = d.path()
            if len(path) > 1 and rng.random() < 0.7:
                d.move_to(path[1])
        if d.start == case.goal:
            break
        new = mutate(grid, rng, {d.start, case.goal})
        d.apply_changes(new, grid_changes(grid, new)[1])
        grid = new


@PROPERTY_SETTINGS
@given(case=cases(reachable=True), data=st.data())
def test_the_first_plan_costs_what_astar_costs(case, data):
    h = data.draw(st.sampled_from(consistent(case.grid)))
    d = DStarLite(case.grid, case.start, case.goal, h)
    assert d.compute()
    a = search(case.grid, case.start, case.goal, 'astar', heuristic=h)
    assert isclose_or_none(d.g_of(case.start), a.cost)
