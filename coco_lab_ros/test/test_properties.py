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
Properties of the two move models on random RAW costmaps (plan §G).

Each map is a random ``nav2_msgs/Costmap``-shaped snapshot -- raw values
0..255, with 253/254/255 blocked -- generated from ``random.Random(seed)``
and pushed through the same adapter the node uses, so the adapter is
exercised on every example too.

1. ``E*(C0) >= E*(C1)``: C0's graph is a subgraph of C1's (it only removes
   corner-cutting diagonals), so its optimum can never be cheaper, and
   where C1 has no path C0 has none.
2. The C1 optimum (coco_lab Dijkstra and A*) equals networkx's Dijkstra on
   the corner-cutting graph built from the same neighbours and edge costs.

Each property runs 1,000 maps on which a path of at least one move exists
(maps without one are rejected by ``assume`` and do not count).
"""

import math
import random

from coco_lab.search import search
from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.metrics import edge_sum
from coco_lab_ros.planning import CONFIGS
from hypothesis import assume, HealthCheck, settings, strategies as st
from hypothesis import given
import networkx as nx

MAPS = 1000
SETTINGS = settings(max_examples=MAPS, derandomize=True, database=None,
                    deadline=None,
                    suppress_health_check=[HealthCheck.too_slow,
                                           HealthCheck.filter_too_much])
REL = 1e-9


def random_snapshot(seed):
    rng = random.Random(seed)
    w, h = rng.randint(2, 12), rng.randint(2, 12)
    density = rng.choice((0.0, 0.1, 0.2, 0.3, 0.4))
    data = bytearray()
    for _ in range(w * h):
        if rng.random() < density:
            data.append(rng.choice((253, 254, 255)))
        else:
            data.append(rng.choice((0, rng.randint(0, 252), 252)))
    return Snapshot(width=w, height=h, resolution=0.05, origin=(0.0, 0.0),
                    frame_id='map', data=bytes(data))


def reachable_pair(grid, seed):
    """Pick a start and a goal >= 1 move away that the C1 graph connects."""
    rng = random.Random(seed ^ 0x5eed)
    free = list(grid.states())
    if len(free) < 2:
        return None
    start = rng.choice(free)
    seen, stack = {start}, [start]
    while stack:
        for n in grid.neighbours(stack.pop()):
            if n not in seen:
                seen.add(n)
                stack.append(n)
    others = sorted(seen - {start})
    return (start, rng.choice(others)) if others else None


def close(a, b):
    return abs(a - b) <= REL * max(1.0, abs(a), abs(b))


@SETTINGS
@given(st.integers(0, 2**32 - 1))
def test_c0_is_never_cheaper_than_c1(seed):
    lab = random_snapshot(seed).to_labmap()
    g0, g1 = lab.to_grid(**CONFIGS['C0']), lab.to_grid(**CONFIGS['C1'])
    pair = reachable_pair(g1, seed)
    assume(pair is not None)
    s, g = pair
    r1 = search(g1, s, g, 'dijkstra', 'zero')
    r0 = search(g0, s, g, 'dijkstra', 'zero')
    assert r1.found
    if r0.found:
        assert r0.cost >= r1.cost - REL * max(1.0, r1.cost)
        e0, _ = edge_sum(r0.path, g1)       # a C0 path is a C1 path
        assert close(e0, r0.cost)


@SETTINGS
@given(st.integers(0, 2**32 - 1))
def test_c1_optimum_equals_networkx(seed):
    lab = random_snapshot(seed).to_labmap()
    grid = lab.to_grid(**CONFIGS['C1'])
    pair = reachable_pair(grid, seed)
    assume(pair is not None)
    s, g = pair
    graph = nx.DiGraph()
    for a in grid.states():
        for b in grid.neighbours(a):
            graph.add_edge(a, b, weight=grid.edge_cost(a, b))
    oracle = nx.dijkstra_path_length(graph, s, g)
    for algo, h in (('dijkstra', 'zero'), ('astar', 'euclidean')):
        r = search(grid, s, g, algo, h)
        assert r.found and close(r.cost, oracle), (algo, r.cost, oracle)
        e, why = edge_sum(r.path, grid)
        assert why is None and close(e, oracle)
    assert math.isfinite(oracle)
