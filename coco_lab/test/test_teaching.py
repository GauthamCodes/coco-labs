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

"""Every teaching fixture's claim, checked, with networkx as the oracle."""

from coco_lab import teaching
from coco_lab.search import ALGORITHMS, search
from lab_maps import Case, close, oracle_cost
import pytest


def run(name, algorithm, **model):
    fx = teaching.FIXTURES[name]
    m, s, g = fx.load()
    grid = m.to_grid(**dict(fx.run, **model))
    heuristic = 'zero' if algorithm in ('bfs', 'dijkstra') else 'octile'
    weight = 2.0 if algorithm == 'weighted_astar' else None
    return search(grid, s, g, algorithm, heuristic, weight=weight), grid, s, g


def test_the_set_is_the_documented_one():
    assert sorted(teaching.FIXTURES) == sorted([
        'open', 'corridor', 'wall_one_gap', 'two_routes', 'greedy_trap',
        'diagonal_leak', 'no_path', 'cost_field', 'turn_trap'])


@pytest.mark.parametrize('name', sorted(teaching.FIXTURES))
def test_every_fixture_is_20x20_described_and_optimal(name):
    fx = teaching.FIXTURES[name]
    m, s, g = fx.load()
    assert (m.width, m.height) == (20, 20)
    assert m.id == f'teaching/{name}'
    assert fx.purpose and fx.claim
    assert m.content_hash() == fx.load()[0].content_hash()
    if name == 'turn_trap':
        return  # a heading-space fixture; test_isro.py checks its claim
    r, grid, s, g = run(name, 'dijkstra')
    expected = oracle_cost(Case(grid, s, g, 0))
    if expected is None:
        assert r.status == 'no_path'
    else:
        assert close(r.cost, expected)
        assert close(run(name, 'astar')[0].cost, expected)


def test_open():
    a, d = run('open', 'astar')[0], run('open', 'dijkstra')[0]
    assert close(a.cost, d.cost)
    assert a.trace.summary['expansions'] * 5 < d.trace.summary['expansions']


def test_corridor():
    paths = {tuple(run('corridor', alg)[0].path) for alg in ALGORITHMS}
    assert len(paths) == 1


def test_wall_one_gap():
    a, d = run('wall_one_gap', 'astar')[0], run('wall_one_gap',
                                                'dijkstra')[0]
    assert close(a.cost, d.cost)
    assert a.trace.summary['expansions'] * 2 > d.trace.summary['expansions']


def test_two_routes():
    r, grid, s, g = run('two_routes', 'dijkstra')
    block_cols = range(8, 12)
    assert all(row > 13 for row, col in r.path if col in block_cols)
    assert close(run('two_routes', 'astar')[0].cost, r.cost)


def test_greedy_trap():
    greedy = run('greedy_trap', 'greedy')[0]
    astar = run('greedy_trap', 'astar')[0]
    optimum = run('greedy_trap', 'dijkstra')[0]
    assert close(astar.cost, optimum.cost)
    assert greedy.cost > optimum.cost + 1e-9


def test_diagonal_leak():
    around = run('diagonal_leak', 'dijkstra', corner_cutting=False)[0]
    through = run('diagonal_leak', 'dijkstra', corner_cutting=True)[0]
    four = run('diagonal_leak', 'dijkstra', connectivity=4)[0]
    assert through.cost + 1e-9 < around.cost < four.cost - 1e-9


def test_no_path():
    for alg in ALGORITHMS:
        r = run('no_path', alg)[0]
        assert r.status == 'no_path' and r.path == [] and r.cost is None


def test_cost_field():
    band = range(6, 14)
    weighted, grid, s, g = run('cost_field', 'dijkstra', cost_weight=2.0)
    plain = run('cost_field', 'dijkstra', cost_weight=0.0)[0]
    gap = range(8, 11)
    assert all(row in gap for row, col in weighted.path if col in band)
    assert any(row not in gap for row, col in plain.path if col in band)
    plain_under_layer = sum(grid.edge_cost(a, b)
                            for a, b in zip(plain.path, plain.path[1:]))
    assert weighted.cost + 1e-9 < plain_under_layer


def test_unknown_fixture_names_are_refused():
    with pytest.raises(KeyError, match='no teaching fixture'):
        teaching.load('nope')
