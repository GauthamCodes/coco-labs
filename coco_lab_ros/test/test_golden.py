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
The golden costmap: a committed costmap_raw fixture with pinned results.

The values were computed once by this code (Phase 1C-1) and are pinned so
that any change to the adapter, the move models or the search shows up as
a changed cost or trace hash. Correctness is the property tests' job
(networkx); this test is about drift.
"""

import hashlib
import json

from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.planning import Planner
import golden_costmap
import pytest

HASH = ('sha256:'
        'a23d8bb63334413991a827d7ee002c1e7989162ddae920a4998c5e379266af0e')
START, GOAL = (2, 2), (36, 26)

#: (algorithm, heuristic, config) -> (cost, path cells, trace JSON SHA-256)
PINNED = {
    ('dijkstra', 'zero', 'C1'): (
        78.7278184116706, 55,
        'e786164b1ae597b5754efdd44846250c9b027a2774f7426c7ec357cd40045fee'),
    ('astar', 'euclidean', 'C1'): (
        78.7278184116706, 55,
        '325d297145e9615bff9c65d4bec6a15f33689cdfbfbe66b4191067c5eb1b6c6f'),
    ('dijkstra', 'zero', 'C0'): (
        79.11499860630038, 56,
        '0c5dd30371b8b1a20f73131030333d43366e4c45a30a2aa88b863fbd7b42fbbd'),
    ('greedy', 'euclidean', 'C1'): (
        105.4365124539541, 46,
        '140889568659df187b5432e290c85d62e826a5cc4041611c465fb9d1a8620526'),
}


@pytest.fixture(scope='module')
def snapshot():
    with open(golden_costmap.PATH, encoding='utf-8') as f:
        text = f.read()
    assert text == golden_costmap.text(), 'fixture drifted from its maker'
    d = json.loads(text)
    return Snapshot(width=d['width'], height=d['height'],
                    resolution=d['resolution'], origin=tuple(d['origin']),
                    frame_id=d['frame_id'], data=bytes(d['data']))


def test_the_fixture_hash(snapshot):
    assert snapshot.content_hash() == HASH
    raw = set(snapshot.data)
    assert {253, 254, 255} <= raw
    assert 0 < max(v for v in raw if v < 253) < 253


@pytest.mark.parametrize('key', sorted(PINNED))
def test_pinned_results(snapshot, key):
    algo, h, cfg = key
    cost, cells, sha = PINNED[key]
    p = Planner(snapshot).plan_cells(START, GOAL, algo, h, cfg)
    assert p.found
    assert p.result.cost == cost
    assert len(p.result.path) == cells
    assert hashlib.sha256(
        p.result.trace.to_json().encode()).hexdigest() == sha
    assert p.cells_nav2()[0] == START and p.cells_nav2()[-1] == GOAL
