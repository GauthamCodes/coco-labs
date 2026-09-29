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
The grid's move generation and declared cost function, hand-checked.

The property tests build their oracle from the grid's own ``neighbours``,
so they cannot catch a wrong move model. These cases can.
"""

import math

from coco_lab.grid import Grid
from coco_lab.heuristics import SQRT2
import pytest

N, E, S, W = (-1, 0), (0, 1), (1, 0), (0, -1)
NE, SE, SW, NW = (-1, 1), (1, 1), (1, -1), (-1, -1)


def offsets(grid, cell):
    return [(r - cell[0], c - cell[1]) for r, c in grid.neighbours(cell)]


def test_four_connectivity_order():
    g = Grid(3, 3, connectivity=4)
    assert offsets(g, (1, 1)) == [N, E, S, W]


def test_eight_connectivity_order():
    g = Grid(3, 3, connectivity=8)
    assert offsets(g, (1, 1)) == [N, E, S, W, NE, SE, SW, NW]


def test_edges_of_the_map_are_respected():
    g = Grid(3, 3, connectivity=8)
    assert offsets(g, (0, 0)) == [E, S, SE]
    assert offsets(g, (2, 2)) == [N, W, NW]


def test_one_by_one_map_has_no_moves():
    assert list(Grid(1, 1).neighbours((0, 0))) == []


def test_blocked_cells_are_not_neighbours_or_states():
    g, _ = Grid.from_ascii("""
        .#.
        ...
        ...
    """, connectivity=4)
    assert (0, 1) not in list(g.neighbours((1, 1)))
    assert (0, 1) not in set(g.states())
    assert len(list(g.states())) == 8
    assert not g.is_valid((0, 1))
    assert not g.is_valid((3, 0))
    assert not g.is_valid('nonsense')


def test_no_corner_cutting_by_default():
    """A diagonal needs both orthogonal cells it passes between free."""
    g, _ = Grid.from_ascii("""
        .#.
        ...
        ...
    """)
    # From (1,0), NE to (0,1) is blocked; from (1,1), NE to (0,2) clips
    # the blocked (0,1) and is refused; NW to (0,0) clips it too.
    assert NE not in offsets(g, (1, 1))
    assert NW not in offsets(g, (1, 1))
    assert SE in offsets(g, (1, 1))


def test_squeezing_between_diagonal_obstacles_is_refused():
    g, _ = Grid.from_ascii("""
        .#
        #.
    """)
    assert list(g.neighbours((0, 0))) == []
    g2, _ = Grid.from_ascii("""
        .#
        #.
    """, corner_cutting=True)
    assert list(g2.neighbours((0, 0))) == [(1, 1)]


def test_corner_cutting_toggle_allows_clipping():
    text = """
        .#.
        ...
    """
    strict, _ = Grid.from_ascii(text)
    loose, _ = Grid.from_ascii(text, corner_cutting=True)
    assert offsets(strict, (1, 1)) == [E, W]
    assert offsets(loose, (1, 1)) == [E, W, NE, NW]


def test_move_costs():
    g = Grid(3, 3)
    assert g.edge_cost((1, 1), (0, 1)) == 1.0
    assert g.edge_cost((1, 1), (0, 2)) == SQRT2
    king = Grid(3, 3, diagonal_cost=1.0)
    assert king.edge_cost((1, 1), (0, 2)) == 1.0
    with pytest.raises(ValueError, match='not a move'):
        g.edge_cost((0, 0), (2, 2))
    with pytest.raises(ValueError, match='not a move'):
        Grid(3, 3, connectivity=4).edge_cost((1, 1), (0, 2))


def test_declared_cost_function():
    """edge_cost = base * (1 + cost_weight * cost[b] / cost_scale)."""
    cost = [0.0] * 9
    cost[0 * 3 + 1] = 126.0   # (0,1): half of 252
    cost[0 * 3 + 2] = 252.0   # (0,2): the full scale
    g = Grid(3, 3, cost=cost, cost_weight=2.0)
    assert g.edge_cost((1, 1), (0, 1)) == pytest.approx(1.0 * (1 + 1.0))
    assert g.edge_cost((1, 1), (0, 2)) == pytest.approx(SQRT2 * (1 + 2.0))
    assert g.edge_cost((0, 1), (1, 1)) == 1.0   # entering a zero-cost cell
    # The cost is that of ENTERING b: the edge is not symmetric.
    assert g.edge_cost((1, 1), (0, 1)) != g.edge_cost((0, 1), (1, 1))
    off = Grid(3, 3, cost=cost, cost_weight=0.0)
    assert off.edge_cost((1, 1), (0, 2)) == SQRT2


def test_cost_multiplier_is_never_below_one():
    cost = [float(v) for v in range(9)]
    g = Grid(3, 3, cost=cost, cost_weight=0.5, cost_scale=4.0)
    for a in g.states():
        for b in g.neighbours(a):
            assert g.edge_cost(a, b) >= g.move_cost(a, b)


@pytest.mark.parametrize('kwargs, match', [
    ({'width': 0, 'height': 3}, 'positive'),
    ({'width': 3, 'height': 3, 'blocked': [False] * 8}, 'blocked has 8'),
    ({'width': 3, 'height': 3, 'cost': [0.0] * 10}, 'cost has 10'),
    ({'width': 2, 'height': 1, 'cost': [0.0, -1.0]}, 'cost\\[1\\]'),
    ({'width': 2, 'height': 1, 'cost': [0.0, math.inf]}, 'cost\\[1\\]'),
    ({'width': 2, 'height': 1, 'cost_weight': -0.5}, 'cost_weight'),
    ({'width': 2, 'height': 1, 'cost_scale': 0.0}, 'cost_scale'),
    ({'width': 2, 'height': 1, 'connectivity': 6}, 'connectivity'),
    ({'width': 2, 'height': 1, 'diagonal_cost': 0.0}, 'diagonal_cost'),
])
def test_invalid_grids_are_refused(kwargs, match):
    with pytest.raises(ValueError, match=match):
        Grid(**kwargs)


def test_from_ascii_markers_and_errors():
    g, marks = Grid.from_ascii("""
        S.#
        ..G
    """)
    assert (g.width, g.height) == (3, 2)
    assert marks == {'S': (0, 0), 'G': (1, 2)}
    assert g.is_blocked((0, 2))
    with pytest.raises(ValueError, match='same length'):
        Grid.from_ascii('...\n..')
    with pytest.raises(ValueError, match='twice'):
        Grid.from_ascii('S.S')
    with pytest.raises(ValueError, match='empty'):
        Grid.from_ascii('   ')


def test_describe_names_every_parameter():
    d = Grid(4, 2, connectivity=4).describe()
    assert d == {'kind': 'grid', 'width': 4, 'height': 2,
                 'connectivity': 4, 'diagonal_cost': SQRT2,
                 'corner_cutting': False, 'cost_layer': False,
                 'cost_weight': 2.0, 'cost_scale': 252.0}
