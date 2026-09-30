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
The suboptimality bound the UI shows beside the weighted-A* slider.

These pin its values; ``test_properties.py`` property 8 checks that it
holds on 1,000 random maps.
"""

from coco_lab.heuristics import analyse, MoveModel
from coco_lab.search import suboptimality_bound
import pytest


def _report(h, connectivity=8):
    return analyse(h, MoveModel(connectivity))


@pytest.mark.parametrize('w, expected', [(0.0, 1.0), (0.5, 1.0), (1.0, 1.0),
                                         (1.25, 1.25), (2.0, 2.0),
                                         (5.0, 5.0)])
def test_weighted_astar_bound_is_max_1_w_for_a_consistent_heuristic(
        w, expected):
    assert suboptimality_bound('weighted_astar', _report('octile'),
                               weight=w) == expected


def test_no_bound_without_a_consistent_heuristic():
    bad = _report('manhattan', connectivity=8)  # a diagonal: h 2 > sqrt(2)
    assert not bad.consistent
    assert suboptimality_bound('astar', bad) is None
    assert suboptimality_bound('weighted_astar', bad, weight=2.0) is None
    assert suboptimality_bound('dijkstra', bad) == 1.0


def test_greedy_and_bfs_have_no_cost_bound():
    for algorithm in ('greedy', 'bfs'):
        assert suboptimality_bound(algorithm, _report('zero')) is None


def test_astar_and_dijkstra_are_optimal():
    assert suboptimality_bound('astar', _report('euclidean')) == 1.0
    assert suboptimality_bound('dijkstra', _report('euclidean')) == 1.0


@pytest.mark.parametrize('algorithm, kw', [
    ('weighted_astar', {}),
    ('weighted_astar', {'weight': -1.0}),
    ('weighted_astar', {'weight': float('inf')}),
    ('astar', {'weight': 2.0}),
    ('nope', {}),
])
def test_the_bound_refuses_what_search_refuses(algorithm, kw):
    with pytest.raises(ValueError):
        suboptimality_bound(algorithm, _report('octile'), **kw)
