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

"""The five algorithms: hand-checked results, input refusal, determinism."""

import json
import os
import subprocess
import sys

from coco_lab.grid import Grid
from coco_lab.heuristics import SQRT2
from coco_lab.search import ALGORITHMS, search, TIE_BREAKS
import pytest

ROOM = """
S....
.###.
...#G
"""


def run(algorithm, grid, start, goal, **kw):
    if algorithm == 'weighted_astar':
        kw.setdefault('weight', 1.5)
    return search(grid, start, goal, algorithm, **kw)


def test_exactly_five_algorithms():
    assert ALGORITHMS == ('bfs', 'dijkstra', 'astar', 'greedy',
                          'weighted_astar')


@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_every_algorithm_solves_the_room(algorithm):
    grid, m = Grid.from_ascii(ROOM)
    r = run(algorithm, grid, m['S'], m['G'], heuristic='octile')
    assert r.found
    assert r.path[0] == m['S'] and r.path[-1] == m['G']
    for a, b in zip(r.path, r.path[1:]):
        assert b in list(grid.neighbours(a))
    assert r.cost == pytest.approx(sum(grid.edge_cost(a, b)
                                       for a, b in zip(r.path, r.path[1:])))
    assert r.trace.summary['path_cost'] == r.cost
    assert r.trace.summary['path_steps'] == len(r.path) - 1


def test_known_optimal_costs():
    grid, m = Grid.from_ascii(ROOM)
    assert search(grid, m['S'], m['G'], 'dijkstra').cost == 6.0
    four, m4 = Grid.from_ascii(ROOM, connectivity=4)
    assert search(four, m4['S'], m4['G'], 'dijkstra').cost == 6.0
    open_grid = Grid(4, 4)
    r = search(open_grid, (0, 0), (3, 3), 'astar', heuristic='octile')
    assert r.cost == pytest.approx(3 * SQRT2)
    assert r.trace.summary['path_length'] == pytest.approx(3 * SQRT2)


def test_path_length_is_geometric_not_cost():
    cost = [252.0] * 9
    grid = Grid(3, 3, cost=cost, cost_weight=2.0, connectivity=4)
    r = search(grid, (0, 0), (0, 2), 'dijkstra')
    assert r.trace.summary['path_length'] == 2.0
    assert r.cost == pytest.approx(6.0)


def test_bfs_ignores_costs_and_dijkstra_does_not():
    cost = [0.0] * 9
    cost[1] = 252.0  # (0, 1) is expensive
    grid = Grid(3, 3, cost=cost, connectivity=4, cost_weight=10.0)
    bfs = search(grid, (0, 0), (0, 2), 'bfs')
    dj = search(grid, (0, 0), (0, 2), 'dijkstra')
    assert bfs.path == [(0, 0), (0, 1), (0, 2)]
    assert dj.path != bfs.path and dj.cost < bfs.cost


@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_start_equals_goal(algorithm):
    grid = Grid(3, 3)
    r = run(algorithm, grid, (1, 1), (1, 1))
    assert r.found and r.path == [(1, 1)] and r.cost == 0.0
    assert r.trace.summary['expansions'] == 1
    assert r.trace.summary['path_length'] == 0.0


@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_no_path(algorithm):
    grid, m = Grid.from_ascii("""
        S.#..
        ..#.G
    """)
    r = run(algorithm, grid, m['S'], m['G'], heuristic='euclidean')
    assert r.status == 'no_path' and not r.found
    assert r.path == [] and r.cost is None
    assert r.trace.summary['path_cost'] is None
    assert r.trace.summary['expansions'] == 4  # the start's whole component


@pytest.mark.parametrize('where', ['start', 'goal'])
def test_blocked_start_or_goal_is_refused_not_no_path(where):
    grid, m = Grid.from_ascii("""
        S#
        .G
    """)
    blocked = (0, 1)
    start, goal = (blocked, m['G']) if where == 'start' else (m['S'], blocked)
    with pytest.raises(ValueError, match=f'{where} .* blocked'):
        search(grid, start, goal, 'astar')
    with pytest.raises(ValueError, match=f'{where} .* outside'):
        search(grid, (9, 9) if where == 'start' else m['S'],
               (9, 9) if where == 'goal' else m['G'], 'astar')


@pytest.mark.parametrize('kwargs, match', [
    ({'algorithm': 'jps'}, 'unknown algorithm'),
    ({'algorithm': 'astar', 'heuristic': 'chebyshev'}, 'unknown heuristic'),
    ({'algorithm': 'astar', 'tie_break': 'lifo'}, 'unknown tie_break'),
    ({'algorithm': 'weighted_astar'}, 'needs a finite weight'),
    ({'algorithm': 'weighted_astar', 'weight': -1.0}, 'needs a finite'),
    ({'algorithm': 'weighted_astar', 'weight': float('nan')}, 'finite'),
    ({'algorithm': 'weighted_astar', 'weight': float('inf')}, 'finite'),
    ({'algorithm': 'astar', 'weight': 2.0}, 'only to weighted_astar'),
])
def test_bad_arguments_are_refused(kwargs, match):
    with pytest.raises(ValueError, match=match):
        search(Grid(2, 2), (0, 0), (1, 1), **kwargs)


def test_trace_records_what_was_run():
    grid, m = Grid.from_ascii(ROOM)
    r = search(grid, m['S'], m['G'], 'weighted_astar', heuristic='octile',
               weight=2.5, tie_break='fifo')
    h = r.trace.header
    assert h['schema'] == 'coco_lab.trace' and h['version'] == '1.0'
    assert (h['algorithm'], h['heuristic'], h['weight'], h['tie_break']) \
        == ('weighted_astar', 'octile', 2.5, 'fifo')
    assert h['start'] == [0, 0, 0] and h['goal'] == [2, 4, 0]
    assert h['graph'] == grid.describe()
    assert search(grid, m['S'], m['G'], 'astar').trace.header['weight'] \
        is None


def test_event_semantics_on_a_small_map():
    """Pushes, relaxes and expansions obey the documented rules."""
    grid, m = Grid.from_ascii(ROOM)
    r = search(grid, m['S'], m['G'], 'astar', heuristic='octile')
    t = r.trace
    first = next(t.rows())
    assert first['kind'] == 0 and (first['row'], first['col']) == (0, 0)
    assert (first['parent_row'], first['parent_col']) == (-1, -1)
    expanded = t.cells('expand')
    assert len(expanded) == len(set(expanded)), 'a closed state reopened'
    assert expanded[-1] == (2, 4, 0), 'goal test is on expansion'
    pushed = t.cells('push')
    assert len(pushed) == len(set(pushed)), 'a state was pushed twice'
    for e in t.rows('expand'):
        assert e['f'] == pytest.approx(e['g'] + e['h'])
    path = t.cells('path')
    assert [(r_, c_) for r_, c_, _ in path] == r.path


@pytest.mark.parametrize('algorithm, weight', [
    ('bfs', None), ('dijkstra', None), ('astar', None), ('greedy', None),
    ('weighted_astar', 0.0), ('weighted_astar', 0.5),
    ('weighted_astar', 2.5), ('weighted_astar', 5.0),
])
def test_f_is_exactly_the_documented_priority(algorithm, weight):
    """
    Pin the priority itself, not only the bounds it implies.

    The weighted-A* bound (cost <= w x optimal) is loose on these maps: a
    mutation-check search that used w^2 instead of w still passed all
    1,000 maps of that property. So the priority is pinned here directly,
    on every push, relax and expand event.
    """
    cost = [float((7 * i) % 253) for i in range(64)]
    grid = Grid(8, 8, cost=cost, cost_weight=2.0)
    kw = {} if weight is None else {'weight': weight}
    r = search(grid, (0, 0), (7, 5), algorithm, heuristic='octile', **kw)
    assert r.found
    expected = {
        'dijkstra': lambda g, h: g,
        'astar': lambda g, h: g + h,
        'greedy': lambda g, h: h,
        'weighted_astar': lambda g, h: g + (weight or 0.0) * h,
    }
    depth = {}
    for e in r.trace.rows():
        if e['kind'] == 3:  # path: f == g by definition
            assert e['f'] == e['g']
            continue
        if algorithm == 'bfs':
            here = (e['row'], e['col'])
            parent = (e['parent_row'], e['parent_col'])
            depth.setdefault(here, 0 if parent == (-1, -1)
                             else depth[parent] + 1)
            assert e['f'] == depth[here]
        else:
            assert e['f'] == expected[algorithm](e['g'], e['h']), e


def test_relax_events_happen_and_lower_g():
    """
    A cheaper route found later relaxes an open state.

    The centre of a 3x3 grid is dear to enter (x11). Expanding the corner
    pushes it diagonally at 11 sqrt(2) = 15.56; expanding an edge cell
    then reaches it orthogonally at 1 + 11 = 12 -- a relax.
    """
    cost = [0.0] * 9
    cost[4] = 252.0
    grid = Grid(3, 3, cost=cost, connectivity=8, cost_weight=10.0)
    r = search(grid, (0, 0), (2, 2), 'dijkstra')
    relaxes = [e for e in r.trace.rows('relax')
               if (e['row'], e['col']) == (1, 1)]
    assert len(relaxes) == 1
    pushed = [p for p in r.trace.rows('push')
              if (p['row'], p['col']) == (1, 1)]
    assert pushed[0]['g'] == pytest.approx(11 * SQRT2)
    assert relaxes[0]['g'] == pytest.approx(12.0)
    assert (relaxes[0]['parent_row'], relaxes[0]['parent_col']) in \
        ((0, 1), (1, 0))


def test_tie_break_changes_the_work_not_the_answer():
    grid = Grid(12, 12)
    results = {tie: search(grid, (0, 0), (11, 7), 'astar',
                           heuristic='octile', tie_break=tie)
               for tie in TIE_BREAKS}
    costs = {r.cost for r in results.values()}
    assert len(costs) == 1
    exp = {tie: r.trace.summary['expansions'] for tie, r in results.items()}
    assert exp['low_h'] < exp['fifo'], exp


def test_same_inputs_same_trace():
    grid, m = Grid.from_ascii(ROOM)
    for algorithm in ALGORITHMS:
        a = run(algorithm, grid, m['S'], m['G'], heuristic='octile')
        b = run(algorithm, grid, m['S'], m['G'], heuristic='octile')
        assert a.trace == b.trace


DETERMINISM_SCRIPT = r"""
import hashlib, random
from coco_lab.grid import Grid
from coco_lab.search import search, ALGORITHMS
rng = random.Random(7)
blocked = [rng.random() < 0.3 for _ in range(400)]
blocked[0] = blocked[399] = False
grid = Grid(20, 20, blocked, [float(rng.randrange(253)) for _ in range(400)])
out = []
for a in ALGORITHMS:
    kw = {'weight': 1.7} if a == 'weighted_astar' else {}
    r = search(grid, (0, 0), (19, 19), a, heuristic='octile', **kw)
    out.append(r.trace.to_json())
print(hashlib.sha256('\n'.join(out).encode()).hexdigest())
"""


def test_traces_are_identical_across_processes_and_hash_seeds():
    digests = set()
    for seed in ('0', '1', '12345'):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run([sys.executable, '-c', DETERMINISM_SCRIPT],
                             env=env, capture_output=True, text=True,
                             check=True)
        digests.add(out.stdout.strip())
    assert len(digests) == 1, digests


def test_trace_is_json_without_nan_or_infinity():
    grid, m = Grid.from_ascii("""
        S#G
    """)
    r = search(grid, m['S'], m['G'], 'astar')
    data = json.loads(r.trace.to_json())
    assert data['summary']['path_cost'] is None
