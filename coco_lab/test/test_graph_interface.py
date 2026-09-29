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
The algorithms depend on the graph interface, never on the grid.

A (cell, heading) state space must plug in without touching them. This file
proves it with a toy one defined here, in the test, so no production code
anticipates it: states ``(row, col, heading)``, moves forward along the
heading, and turns in place that cost a penalty. Phase 1B builds the real
one; this only shows the seam is where it should be.
"""

import ast
import inspect
import math

from coco_lab import search as search_module
from coco_lab.search import ALGORITHMS, search
import networkx as nx
import pytest

HEADINGS = ((-1, 0), (0, 1), (1, 0), (0, -1))  # N E S W


class HeadingSpace:
    """A 4-heading lattice over a free ``size x size`` square."""

    def __init__(self, size, turn_cost=0.5):
        self.size = size
        self.turn_cost = turn_cost

    def is_valid(self, s):
        r, c, h = s
        return 0 <= r < self.size and 0 <= c < self.size and 0 <= h < 4

    def neighbours(self, s):
        r, c, h = s
        dr, dc = HEADINGS[h]
        if 0 <= r + dr < self.size and 0 <= c + dc < self.size:
            yield (r + dr, c + dc, h)
        yield (r, c, (h + 1) % 4)
        yield (r, c, (h - 1) % 4)

    def edge_cost(self, a, b):
        return 1.0 if a[:2] != b[:2] else self.turn_cost

    def heuristic(self, name, s, goal):
        dr, dc = abs(goal[0] - s[0]), abs(goal[1] - s[1])
        return {'zero': 0.0, 'manhattan': float(dr + dc),
                'euclidean': math.hypot(dr, dc),
                'octile': max(dr, dc) + (math.sqrt(2) - 1) * min(dr, dc)
                }[name]

    def locate(self, s):
        return s


def nx_cost(space, start, goal):
    g = nx.DiGraph()
    todo, seen = [start], {start}
    while todo:
        s = todo.pop()
        for n in space.neighbours(s):
            g.add_edge(s, n, weight=space.edge_cost(s, n))
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return nx.dijkstra_path_length(g, start, goal, weight='weight')


@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_a_heading_space_plugs_in(algorithm):
    space = HeadingSpace(6)
    start, goal = (0, 0, 1), (5, 5, 2)
    kw = {'weight': 1.5} if algorithm == 'weighted_astar' else {}
    r = search(space, start, goal, algorithm, heuristic='manhattan', **kw)
    assert r.found and r.path[0] == start and r.path[-1] == goal
    assert set(r.trace.events['sub']) <= {0, 1, 2, 3}
    assert r.trace.header['graph'] == {'kind': 'HeadingSpace'}
    optimal = nx_cost(space, start, goal)
    assert r.cost >= optimal - 1e-9
    if algorithm in ('dijkstra', 'astar'):
        assert math.isclose(r.cost, optimal)
        # Ten moves and one turn; the turn has length 0 in the geometry.
        assert optimal == 10.5
        assert r.trace.summary['path_length'] == 10.0


def test_search_never_imports_the_grid():
    tree = ast.parse(inspect.getsource(search_module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert 'grid' not in imported and 'coco_lab.grid' not in imported
    assert not any(n and n.endswith('heuristics') for n in imported)
