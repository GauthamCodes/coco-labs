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

"""Compare adapters retain reference paths, costs and native expansion counts."""
from coco_lab.compare_planning import run_planner
from coco_lab.dstarlite import DStarLite
from coco_lab.grid import Grid
import pytest


@pytest.mark.parametrize('costed', [False, True])
def test_dstar_display_is_the_reference_on_the_same_graph(costed):
    grid = Grid(5, 4, blocked=[False] * 20,
                cost=([0, 60, 100, 60, 0] * 4 if costed else None))
    start, goal = (0, 0), (3, 4)
    native = DStarLite(grid, start, goal)
    assert native.compute()
    rows = []
    result = run_planner(grid, start, goal, 'dstar_lite', rows.append)
    astar = run_planner(grid, start, goal, 'astar', lambda row: None)
    assert result.path == native.path()
    assert result.summary['path_cost'] == pytest.approx(astar.summary['path_cost'])
    assert result.summary['expansions'] == native.expansions
    assert sum(row[0] == 1 for row in rows) == native.expansions
    assert [row[1:3] for row in rows if row[0] == 3] == result.path
    assert all(row[4:] == (-1.0, -1.0, -1.0, -1, -1, -1) for row in rows)
