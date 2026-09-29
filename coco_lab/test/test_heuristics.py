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
The heuristics, and the admissibility/consistency analysis behind the badge.

The badge is a claim shown to learners, so it is tested three ways: the
full verdict table by hand, the octile-with-unit-diagonals case the ISRO
exhibit depends on, and a property on 1,000 random maps that no
"admissible" verdict is ever contradicted by a true cost-to-go.
"""

import math

from coco_lab.graph import HEURISTICS
from coco_lab.grid import Grid
from coco_lab.heuristics import analyse, evaluate, MoveModel, SQRT2
from coco_lab.search import search, TIE_BREAKS
from hypothesis import event, given, strategies as st
from lab_maps import cases, close, oracle_graph, PROPERTY_SETTINGS
import networkx as nx
import pytest

KING = MoveModel(8, 1.0)       # diagonals cost 1
OCTILE = MoveModel(8, SQRT2)   # diagonals cost sqrt(2)
FOUR = MoveModel(4)
EIGHT_TWO = MoveModel(8, 2.0)  # diagonals cost 2: never worth taking


@pytest.mark.parametrize('dr, dc, expected', [
    (0, 0, (0.0, 0.0, 0.0, 0.0)),
    (3, 0, (0.0, 3.0, 3.0, 3.0)),
    (0, -4, (0.0, 4.0, 4.0, 4.0)),
    (3, 4, (0.0, 7.0, 5.0, 1.0 + 3 * SQRT2)),
    (-2, 2, (0.0, 4.0, 2 * SQRT2, 2 * SQRT2)),
])
def test_values(dr, dc, expected):
    got = tuple(evaluate(h, dr, dc) for h in HEURISTICS)
    assert all(math.isclose(a, b) for a, b in zip(got, expected)), got


def test_unknown_heuristic_is_refused():
    with pytest.raises(ValueError, match='unknown heuristic'):
        evaluate('chebyshev', 1, 1)
    with pytest.raises(ValueError, match='unknown heuristic'):
        analyse('chebyshev', OCTILE)


# (move model, heuristic) -> admissible (== consistent for these four)
VERDICTS = {
    (FOUR, 'zero'): True, (FOUR, 'manhattan'): True,
    (FOUR, 'euclidean'): True, (FOUR, 'octile'): True,
    (OCTILE, 'zero'): True, (OCTILE, 'manhattan'): False,
    (OCTILE, 'euclidean'): True, (OCTILE, 'octile'): True,
    (KING, 'zero'): True, (KING, 'manhattan'): False,
    (KING, 'euclidean'): False, (KING, 'octile'): False,
    (EIGHT_TWO, 'zero'): True, (EIGHT_TWO, 'manhattan'): True,
    (EIGHT_TWO, 'euclidean'): True, (EIGHT_TWO, 'octile'): True,
}


@pytest.mark.parametrize('model, name', sorted(VERDICTS, key=str))
def test_verdict_table(model, name):
    report = analyse(name, model)
    assert report.admissible is VERDICTS[(model, name)]
    assert report.consistent is report.admissible
    assert (report.witness is None) is report.admissible


def test_octile_overestimates_when_diagonals_cost_one():
    """The ISRO hypothesis (b) case, pinned exactly."""
    report = analyse('octile', KING)
    assert not report.admissible and not report.consistent
    dr, dc, cost, h = report.witness
    assert (abs(dr), abs(dc)) == (1, 1)
    assert cost == 1.0
    assert h == pytest.approx(SQRT2)
    assert 'overestimates' in report.reason


@pytest.mark.parametrize('model, name',
                         [k for k, v in sorted(VERDICTS.items(), key=str)
                          if not v])
def test_every_witness_is_a_real_counterexample(model, name):
    """On an empty 3x3 grid, the witness state's true cost is below h."""
    dr, dc, cost, h = analyse(name, model).witness
    grid = Grid(3, 3, connectivity=model.connectivity,
                diagonal_cost=model.diagonal_cost)
    goal = (1, 1)
    state = (1 - dr, 1 - dc)  # one witness move away from the goal
    true = search(grid, state, goal, 'dijkstra').cost
    assert true <= cost
    assert grid.heuristic(name, state, goal) == h > true


@pytest.mark.parametrize('tie', TIE_BREAKS)
def test_an_inadmissible_heuristic_makes_astar_suboptimal(tie):
    """
    The check has teeth: the analysis flags it, and A* really loses.

    Manhattan on an 8-connected grid with sqrt(2) diagonals is flagged
    inadmissible. On this committed map A* with it returns 5 + sqrt(2)
    (6.414) where the optimum is 3 + 2 sqrt(2) (5.828); with octile, which
    is admissible here, it finds the optimum. On an EMPTY grid Manhattan
    happens to stay optimal, which is why the map needs its obstacles.
    """
    grid, m = Grid.from_ascii("""
        G....#
        ...#..
        .....S
    """)
    assert not analyse('manhattan', grid.move_model).admissible
    best = search(grid, m['S'], m['G'], 'dijkstra').cost
    bad = search(grid, m['S'], m['G'], 'astar', heuristic='manhattan',
                 tie_break=tie).cost
    good = search(grid, m['S'], m['G'], 'astar', heuristic='octile',
                  tie_break=tie).cost
    assert best == pytest.approx(3 + 2 * SQRT2)
    assert good == pytest.approx(best)
    assert bad == pytest.approx(5 + SQRT2)


@PROPERTY_SETTINGS
@given(case=cases(), name=st.sampled_from(HEURISTICS))
def test_no_admissible_verdict_is_ever_contradicted(case, name):
    """
    On 1,000 random maps, compare the badge with the true cost-to-go.

    If the analysis says admissible and consistent, then for every state
    h(s) <= h*(s), and for every edge h(a) <= c(a, b) + h(b). An
    inadmissible verdict cannot be refuted on an arbitrary map (the
    obstacles may hide the overestimate), so those examples only record
    whether this map exposed it; the witness test above proves them.
    """
    grid, goal = case.grid, case.goal
    report = analyse(name, grid.move_model)
    graph = oracle_graph(grid)
    to_goal = nx.single_source_dijkstra_path_length(
        graph.reverse(copy=False), goal, weight='weight')
    over = [s for s, d in to_goal.items()
            if grid.heuristic(name, s, goal) > d
            and not close(grid.heuristic(name, s, goal), d)]
    if report.admissible:
        assert not over, (name, over[:3])
        for a, b, c in graph.edges(data='weight'):
            ha = grid.heuristic(name, a, goal)
            hb = grid.heuristic(name, b, goal)
            assert ha <= c + hb or close(ha, c + hb), (a, b)
        event('verdict: admissible, held')
    else:
        event('verdict: inadmissible, '
              + ('exposed on this map' if over else 'hidden on this map'))
