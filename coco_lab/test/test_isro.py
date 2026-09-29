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
The ISRO reconstruction, checked three ways.

The vendored code is intact, the harness is faithful, and the
heading-aware model agrees with an independent oracle.

The oracle here is built from the cost RULE -- 8 moves in the simulator's
order, sqrt(2) diagonals, a flat penalty on any change of direction, none
on the first move -- written out again in this file. It does not call
:class:`coco_lab.heading.HeadingGrid`, so agreement is evidence that the
graph implements the rule, not that it agrees with itself.
"""

import hashlib
import inspect
import math
import random
import re
import subprocess
import sys

from coco_lab import heading, teaching
from coco_lab.heading import GOAL, HeadingGrid, START
from coco_lab.isro import historical, upstream_v3_6 as up
from coco_lab.maps import LabMap
from coco_lab.search import search
from hypothesis import event, given, settings, strategies as st
from lab_maps import close, MAPS_PER_PROPERTY, PROPERTY_SETTINGS
import networkx as nx
import pytest

RULE_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1),
             (-1, -1), (-1, 1), (1, -1), (1, 1)]


# -- the vendored code ---------------------------------------------------------

BLOCK = re.compile(r'^# >>> upstream l\.(\d+)-(\d+):[^\n]*\n(.*?)'
                   r'^# <<< upstream l\.\1-\2\n', re.S | re.M)


def vendored_blocks():
    with open(up.__file__, encoding='utf-8') as f:
        text = f.read()
    blocks = {(int(a), int(b)): body for a, b, body in BLOCK.findall(text)}
    assert text.count('# >>> upstream l.') == len(blocks), 'unterminated'
    return blocks


def test_every_vendored_block_is_byte_identical_to_upstream():
    blocks = vendored_blocks()
    assert set(blocks) == set(up.UPSTREAM_SEGMENTS)
    for span, body in blocks.items():
        digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
        assert digest == up.UPSTREAM_SEGMENTS[span], (
            f'upstream l.{span[0]}-{span[1]} was edited after vendoring')


def test_the_pin_is_recorded():
    assert up.UPSTREAM_COMMIT == '5aad7b3e1b461ccb464667edc9cee59fa1d5a01b'
    assert up.UPSTREAM_PATH == 'astar_simulator_final_v3_6.py'
    assert len(up.UPSTREAM_FILE_SHA256) == 64


def test_the_vendored_constants_are_the_sources():
    assert up.DIRS == RULE_DIRS == list(heading.ISRO_DIRS)
    source = inspect.getsource(up)
    assert 'TURN_PENALTY = 0.1' in source
    assert 'import pygame' not in source and 'pygame.' not in source


# -- the harness ---------------------------------------------------------------

def lab(text):
    return LabMap.from_ascii(text)


def test_a_straight_run_has_no_turns():
    m, marks = lab('S...G')
    for alg in historical.ALGORITHMS:
        r = historical.run(m, marks['S'], marks['G'], alg)
        assert r.found and r.path == [(0, c) for c in range(5)]
        if alg != 'bfs':
            assert r.source_metrics['length'] == 4
            assert r.source_metrics['turns'] == 0
        # smooth_path keeps path[0] (the first step, the start being
        # excluded) and then the goal, in sight: two waypoints.
        assert r.smoothed == [(0, 1), (0, 4)] and r.smoothed_steps == 2


def test_the_source_invents_a_path_when_there_is_none():
    m, marks = lab('S#G')
    for alg in historical.ALGORITHMS:
        r = historical.run(m, marks['S'], marks['G'], alg)
        assert not r.found and r.path == []
        # The source itself returns [goal] (upstream l.183-196, l.270-275):
        # the reconstruction starts at the goal and stops at no parent.
        # A* and Dijkstra report length 0 for it; BFS reports len(path), 1.
        assert r.source_metrics['length'] == (1 if alg == 'bfs' else 0)


def test_the_first_move_is_free_and_every_change_costs_the_penalty():
    m, marks = lab("""
        S..
        ...
        ..G
    """)
    g = HeadingGrid.from_map(m, marks['S'], marks['G'], turn_penalty=0.1)
    assert g.path_cost([(0, 0), (1, 1), (2, 2)]) == pytest.approx(
        2 * math.sqrt(2))
    assert g.path_cost([(0, 0), (0, 1), (1, 2), (2, 2)]) == pytest.approx(
        2 + math.sqrt(2) + 0.2)
    assert g.path_cost([(0, 0), (0, 1), (0, 0)]) == pytest.approx(2.1)


def test_dijkstra_counts_stale_pops_and_astar_can_reopen():
    rng = random.Random(3)
    seen_stale = seen_reopen = False
    for _ in range(60):
        blocked = [rng.random() < 0.25 for _ in range(144)]
        blocked[0] = blocked[-1] = False
        m = LabMap(12, 12, bytes(blocked))
        d = historical.run(m, (0, 0), (11, 11), 'dijkstra')
        a = historical.run(m, (0, 0), (11, 11), 'astar')
        # The source's own 'explored' counts exactly the instrumented pops.
        assert d.source_metrics['explored'] == d.expansions
        assert a.source_metrics['explored'] == a.expansions
        seen_stale |= d.expansions > d.distinct_expanded
        seen_reopen |= a.expansions > a.distinct_expanded
    assert seen_stale, 'no stale Dijkstra pop in 60 maps'
    assert seen_reopen, 'no A* re-expansion in 60 maps'


def test_instrumenting_does_not_change_the_result():
    m, s, g = teaching.load('wall_one_gap')
    for alg in historical.ALGORITHMS:
        a = historical.run(m, s, g, alg, instrument=True)
        b = historical.run(m, s, g, alg, instrument=False)
        assert a.path == b.path and a.smoothed == b.smoothed
        assert {k: v for k, v in a.source_metrics.items() if k != 'time'} \
            == {k: v for k, v in b.source_metrics.items() if k != 'time'}


HANG_MAP = """
    S..
    ...
    .#G
"""


def test_the_historical_smoother_can_loop_forever():
    # A* returns [(1,1), (2,2)]: a legal corner-cutting diagonal, whose
    # Bresenham line-of-sight check visits the blocked (2,1). No waypoint
    # after (1,1) is then in sight, and smooth_path appends (1,1) forever.
    m, marks = lab(HANG_MAP)
    r = historical.run(m, marks['S'], marks['G'], 'astar')
    assert r.found and r.path == [(0, 0), (1, 1), (2, 2)]
    assert not r.smoothing_terminates
    assert r.smoothed is None and r.smoothed_steps is None
    # And the verbatim function really does not return.
    assert not verbatim_smoother_returns(m, 'astar', marks['S'], marks['G'])


def verbatim_smoother_returns(m, algorithm, start, goal, timeout=2.0):
    """Run the verbatim search + smooth_path in a capped child process."""
    child = (
        'import resource, sys\n'
        'resource.setrlimit(resource.RLIMIT_AS, (1 << 29, 1 << 29))\n'
        f'sys.path[:0] = {sys.path!r}\n'
        'from coco_lab.maps import LabMap\n'
        'from coco_lab.isro import historical, upstream_v3_6 as up\n'
        f'm = LabMap({m.width}, {m.height}, bytes({list(m.occupancy)!r}))\n'
        'historical.load(m)\n'
        f'cells, _ = up.{algorithm}({tuple(start)!r}, {tuple(goal)!r})\n'
        'up.smooth_path(cells)\n'
        "print('returned')\n")
    try:
        p = subprocess.run([sys.executable, '-c', child],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return 'returned' in p.stdout


def test_the_termination_check_agrees_with_the_smoother():
    # Three predicted hangs and three predicted returns, each checked
    # against the verbatim smoother in a child process.
    rng = random.Random(11)
    want = {True: 3, False: 3}
    while any(want.values()):
        blocked = [rng.random() < 0.2 for _ in range(100)]
        blocked[0] = blocked[-1] = False
        m = LabMap(10, 10, bytes(blocked))
        r = historical.run(m, (0, 0), (9, 9), 'dijkstra')
        if not r.found or not want[r.smoothing_terminates]:
            continue
        want[r.smoothing_terminates] -= 1
        assert verbatim_smoother_returns(m, 'dijkstra', (0, 0),
                                         (9, 9)) == r.smoothing_terminates
        if r.smoothing_terminates:
            assert r.smoothed[-1] == (9, 9)


def test_the_harness_restores_the_module():
    m, marks = lab('S.G')
    before = (up.mark_cell_explored, up.heapq)
    historical.run(m, marks['S'], marks['G'], 'astar')
    assert (up.mark_cell_explored, up.heapq) == before


# -- the independent oracle ------------------------------------------------------

def rule_oracle(free, width, height, start, goal, penalty, corner):
    """Optimal cost under the rule, from a graph built here, or None."""
    g = nx.DiGraph()

    def ok(r, c):
        return 0 <= r < height and 0 <= c < width and free[r][c]

    for r in range(height):
        for c in range(width):
            if not ok(r, c):
                continue
            arrivals = list(range(8)) + (['first'] if (r, c) == start
                                         else [])
            for into in arrivals:
                if (r, c) == goal:
                    g.add_edge((r, c, into), 'goal', weight=0.0)
                for k, (dr, dc) in enumerate(RULE_DIRS):
                    nr, nc = r + dr, c + dc
                    if not ok(nr, nc):
                        continue
                    if dr and dc and not corner and not (
                            ok(r + dr, c) and ok(r, c + dc)):
                        continue
                    w = math.hypot(dr, dc)
                    if into != 'first' and into != k:
                        w += penalty
                    g.add_edge((r, c, into), (nr, nc, k), weight=w)
    try:
        return nx.dijkstra_path_length(g, (start[0], start[1], 'first'),
                                       'goal')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


@st.composite
def heading_cases(draw, max_side=12):
    # Every parameter comes from the seed, not from hypothesis directly:
    # hypothesis biases integers small, and that left most maps 2 x 2.
    # From the seed, sizes are uniform on 2..max_side.
    seed = draw(st.integers(0, 2 ** 32 - 1))
    rng = random.Random(seed)
    width = rng.randint(2, max_side)
    height = rng.randint(2, max_side)
    density = rng.choice([0.0, 0.1, 0.2, 0.3, 0.4])
    penalty = rng.choice([0.1, 0.1, 0.5, 1.0, 0.0])
    corner = rng.random() < 0.5
    event(f'side {"<=6" if max(width, height) <= 6 else ">6"}')
    free = [[rng.random() >= density for _ in range(width)]
            for _ in range(height)]
    start = goal = (rng.randrange(height), rng.randrange(width))
    while goal == start:  # a zero-move case tests nothing
        goal = (rng.randrange(height), rng.randrange(width))
    free[start[0]][start[1]] = free[goal[0]][goal[1]] = True
    m = LabMap(width, height, bytes(0 if f else 1 for row in free
                                    for f in row))
    return m, free, start, goal, penalty, corner


@PROPERTY_SETTINGS
@given(heading_cases())
def test_heading_grid_is_optimal_against_the_rule_oracle(case):
    m, free, start, goal, penalty, corner = case
    graph = HeadingGrid.from_map(m, start, goal, penalty, corner)
    expected = rule_oracle(free, m.width, m.height, start, goal, penalty,
                           corner)
    s, g = graph.start_state(start), graph.goal_state(goal)
    event('outcome: ' + ('no path' if expected is None else
                         'start is goal' if start == goal else 'path'))
    for alg, h in (('dijkstra', 'zero'), ('astar', 'octile')):
        r = search(graph, s, g, alg, h)
        if expected is None:
            assert r.status == 'no_path'
        else:
            assert r.status == 'found' and close(r.cost, expected), (
                alg, r.cost, expected)
            cells = [st_[:2] for st_ in r.path if st_[2] != GOAL]
            assert close(graph.path_cost(cells), r.cost)


def test_the_property_runs_the_roadmap_floor():
    assert MAPS_PER_PROPERTY >= 1000


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(heading_cases(max_side=8))
def test_octile_is_consistent_and_zero_at_the_goal(case):
    m, free, start, goal, penalty, corner = case
    graph = HeadingGrid.from_map(m, start, goal, penalty, corner)
    gs = graph.goal_state(goal)
    assert graph.heuristic('octile', gs, gs) == 0.0
    states = [graph.start_state(start), gs] + [
        (r, c, h) for r in range(m.height) for c in range(m.width)
        for h in range(8) if graph.is_valid((r, c, h))]
    for a in states:
        ha = graph.heuristic('octile', a, gs)
        for b in graph.neighbours(a):
            assert ha <= graph.edge_cost(a, b) + graph.heuristic(
                'octile', b, gs) + 1e-12, (a, b)


@settings(max_examples=300, derandomize=True, database=None, deadline=None)
@given(heading_cases())
def test_ablation_zero_penalty_is_the_plain_grid(case):
    m, free, start, goal, _, corner = case
    graph = HeadingGrid.from_map(m, start, goal, 0.0, corner)
    plain = m.to_grid(connectivity=8, corner_cutting=corner)
    a = search(graph, graph.start_state(start), graph.goal_state(goal),
               'dijkstra')
    b = search(plain, start, goal, 'dijkstra')
    assert a.status == b.status
    if a.found:
        assert close(a.cost, b.cost)


def test_the_heading_graph_rejects_foreign_states():
    m, marks = lab('S.G')
    g = HeadingGrid.from_map(m, marks['S'], marks['G'])
    assert g.is_valid((0, 0, START)) and g.is_valid((0, 2, GOAL))
    assert not g.is_valid((0, 1, START)) and not g.is_valid((0, 1, GOAL))
    assert not g.is_valid((0, 1, 8 + 5)) and not g.is_valid((0, 1))
    assert g.state_at((0, 1, 3)) == (0, 1, 3)
    with pytest.raises(ValueError):
        HeadingGrid(2, 1, [False, False], (0, 0), (0, 1), turn_penalty=-1)
    with pytest.raises(ValueError, match='not a move'):
        g.path_cost([(0, 0), (0, 2)])


# -- the lesson's fixture ---------------------------------------------------------

def test_turn_trap_cell_only_search_loses_optimality():
    fx = teaching.FIXTURES['turn_trap']
    m, s, g = fx.load()
    graph = HeadingGrid.from_map(m, s, g, **fx.run)
    optimum = search(graph, graph.start_state(s), graph.goal_state(g),
                     'dijkstra').cost
    free = [[m.at((r, c)) == 0 for c in range(m.width)]
            for r in range(m.height)]
    assert close(optimum, rule_oracle(free, m.width, m.height, s, g,
                                      fx.run['turn_penalty'],
                                      fx.run['corner_cutting']))
    assert close(optimum, 6 + 3 * math.sqrt(2) + 0.1)
    for alg in ('dijkstra', 'astar'):
        hist = historical.run(m, s, g, alg,
                              turn_penalty=fx.run['turn_penalty'])
        assert hist.found
        assert graph.path_cost(hist.path) == pytest.approx(optimum + 0.1)
        # The mechanism, as the fixture's claim states it: (6, 2) kept the
        # north-west arrival ...
        assert up.grid[6][2].direction == (-1, -1)
    # ... although the north arrival ties with it in the heading space.
    ties = {heading.ISRO_DIRS[e['sub']]: e['g'] for e in search(
        graph, graph.start_state(s), graph.goal_state(g),
        'dijkstra').trace.rows() if e['kind'] in (0, 2)
        and (e['row'], e['col']) == (6, 2)}
    assert close(ties[(-1, -1)], ties[(-1, 0)])
    astar = search(graph, graph.start_state(s), graph.goal_state(g),
                   'astar', 'octile')
    assert close(astar.cost, optimum)
