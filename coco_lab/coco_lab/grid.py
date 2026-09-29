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
An occupancy grid with an optional cost layer: one :class:`SearchGraph`.

A state is a free cell ``(row, col)``; row 0 is the top row.

**Moves.** 4-connectivity moves N, E, S, W at base cost 1. 8-connectivity
adds NE, SE, SW, NW at base cost ``diagonal_cost`` (``sqrt(2)`` by
default). Neighbours are generated in exactly that order.

**Corner cutting.** By default a diagonal move is allowed only if *both*
orthogonal cells it passes between are free: the robot may not squeeze
through the corner where two obstacles touch diagonally, nor clip the
corner of one. ``corner_cutting=True`` drops that rule and allows any
diagonal between two free cells.

**The declared cost function.** With a cost layer ``cost[cell] >= 0``::

    edge_cost(a -> b) = base_cost(move) * (1 + cost_weight * cost[b] / cost_scale)

The cost of *entering* ``b`` scales the geometric length of the move. With
no cost layer, or ``cost_weight = 0``, it is the geometric length alone.
``cost_scale`` (default 252, the highest non-lethal, non-inscribed value in
a Nav2 costmap) puts the layer in the costmap's own units, so ``cost[b] ==
cost_scale`` makes a move cost ``1 + cost_weight`` times its length. The
multiplier is never below 1, which is what keeps every geometric heuristic
admissible on a costed grid (see :func:`coco_lab.heuristics.analyse`).

Whether and how this differs from SmacPlanner2D's traversal cost is Phase
1C's question, answered by reading Smac's source. Nothing here claims they
are the same.

Occupied cells are not states. Lethal costs are expressed as occupancy,
never as a large cost value.
"""

import math
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from . import heuristics
from .heuristics import MoveModel, SQRT2

Cell = Tuple[int, int]

DEFAULT_COST_SCALE = 252.0
DEFAULT_COST_WEIGHT = 2.0


class Grid:
    """
    A rectangular occupancy grid, searchable by every coco_lab algorithm.

    ``blocked`` and ``cost`` are row-major sequences of length
    ``width * height``. ``cost`` may be ``None`` (no cost layer).
    """

    def __init__(self, width: int, height: int,
                 blocked: Optional[Sequence[bool]] = None,
                 cost: Optional[Sequence[float]] = None,
                 connectivity: int = 8,
                 diagonal_cost: float = SQRT2,
                 corner_cutting: bool = False,
                 cost_weight: float = DEFAULT_COST_WEIGHT,
                 cost_scale: float = DEFAULT_COST_SCALE):
        """Validate and freeze the grid; it is immutable afterwards."""
        if not (isinstance(width, int) and isinstance(height, int)
                and width > 0 and height > 0):
            raise ValueError(
                f'width and height must be positive ints, '
                f'got {width!r} x {height!r}')
        n = width * height
        self.width = width
        self.height = height
        self.move_model = MoveModel(connectivity, diagonal_cost)
        self.corner_cutting = bool(corner_cutting)

        if blocked is None:
            blocked = (False,) * n
        if len(blocked) != n:
            raise ValueError(f'blocked has {len(blocked)} cells, expected {n}')
        self._blocked = tuple(bool(b) for b in blocked)

        if not (math.isfinite(cost_weight) and cost_weight >= 0):
            raise ValueError(
                f'cost_weight must be finite and >= 0, got {cost_weight!r}')
        if not (math.isfinite(cost_scale) and cost_scale > 0):
            raise ValueError(
                f'cost_scale must be finite and > 0, got {cost_scale!r}')
        self.cost_weight = float(cost_weight)
        self.cost_scale = float(cost_scale)
        if cost is not None:
            if len(cost) != n:
                raise ValueError(f'cost has {len(cost)} cells, expected {n}')
            for i, c in enumerate(cost):
                if not (math.isfinite(c) and c >= 0):
                    raise ValueError(
                        f'cost[{i}] must be finite and >= 0, got {c!r}')
            self._cost = tuple(float(c) for c in cost)
        else:
            self._cost = None
        self._moves = self.move_model.moves()

    # -- construction helpers -------------------------------------------

    @classmethod
    def from_ascii(cls, text: str, **kwargs) -> Tuple['Grid', Dict[str, Cell]]:
        """
        Build a grid from ``#`` (blocked) and any other char (free).

        Letters mark cells and are returned as ``{letter: (row, col)}``;
        the conventional ones are ``S`` and ``G``. Blank lines and
        surrounding whitespace are ignored; rows must be equal length.
        """
        rows = [line.strip() for line in text.strip().splitlines()
                if line.strip()]
        if not rows:
            raise ValueError('empty map')
        width = len(rows[0])
        if any(len(r) != width for r in rows):
            raise ValueError('rows must all be the same length')
        blocked: List[bool] = []
        marks: Dict[str, Cell] = {}
        for r, line in enumerate(rows):
            for c, ch in enumerate(line):
                blocked.append(ch == '#')
                if ch.isalpha():
                    if ch in marks:
                        raise ValueError(f'marker {ch!r} appears twice')
                    marks[ch] = (r, c)
        return cls(width, len(rows), blocked, **kwargs), marks

    # -- queries -----------------------------------------------------------

    def in_bounds(self, cell: Cell) -> bool:
        """Return whether ``cell`` is inside the grid."""
        r, c = cell
        return 0 <= r < self.height and 0 <= c < self.width

    def is_blocked(self, cell: Cell) -> bool:
        """Return whether ``cell`` is occupied (it must be in bounds)."""
        r, c = cell
        return self._blocked[r * self.width + c]

    def cost_at(self, cell: Cell) -> float:
        """Return the cost layer's value at ``cell`` (0 without a layer)."""
        if self._cost is None:
            return 0.0
        r, c = cell
        return self._cost[r * self.width + c]

    def states(self) -> Iterator[Cell]:
        """Yield every free cell, row-major."""
        for r in range(self.height):
            for c in range(self.width):
                if not self._blocked[r * self.width + c]:
                    yield (r, c)

    def describe(self) -> Dict[str, object]:
        """Return the graph's parameters, for a trace header."""
        return {
            'kind': 'grid',
            'width': self.width,
            'height': self.height,
            'connectivity': self.move_model.connectivity,
            'diagonal_cost': self.move_model.diagonal_cost,
            'corner_cutting': self.corner_cutting,
            'cost_layer': self._cost is not None,
            'cost_weight': self.cost_weight,
            'cost_scale': self.cost_scale,
        }

    # -- the SearchGraph interface -----------------------------------------

    def is_valid(self, state) -> bool:
        """Return whether ``state`` is an in-bounds, free cell."""
        try:
            r, c = state
        except (TypeError, ValueError):
            return False
        if not (isinstance(r, int) and isinstance(c, int)):
            return False
        return self.in_bounds((r, c)) and not self.is_blocked((r, c))

    def neighbours(self, state: Cell) -> Iterable[Cell]:
        """Yield free neighbours in N, E, S, W, NE, SE, SW, NW order."""
        r, c = state
        for dr, dc, _ in self._moves:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < self.height and 0 <= nc < self.width):
                continue
            if self._blocked[nr * self.width + nc]:
                continue
            if dr and dc and not self.corner_cutting:
                if (self._blocked[(r + dr) * self.width + c]
                        or self._blocked[r * self.width + c + dc]):
                    continue
            yield (nr, nc)

    def move_cost(self, a: Cell, b: Cell) -> float:
        """Return the base (geometric) cost of the move ``a -> b``."""
        dr, dc = b[0] - a[0], b[1] - a[1]
        if abs(dr) + abs(dc) == 1:
            return 1.0
        if abs(dr) == 1 and abs(dc) == 1 and self.move_model.connectivity == 8:
            return float(self.move_model.diagonal_cost)
        raise ValueError(f'{a} -> {b} is not a move on this grid')

    def edge_cost(self, a: Cell, b: Cell) -> float:
        """Return the declared cost of ``a -> b`` (see the module doc)."""
        base = self.move_cost(a, b)
        if self._cost is None or self.cost_weight == 0.0:
            return base
        return base * (1.0 + self.cost_weight * self.cost_at(b)
                       / self.cost_scale)

    def heuristic(self, name: str, state: Cell, goal: Cell) -> float:
        """Return heuristic ``name`` from ``state`` to ``goal``."""
        return heuristics.evaluate(name, goal[0] - state[0],
                                   goal[1] - state[1])

    def locate(self, state: Cell) -> Tuple[int, int, int]:
        """Return ``(row, col, 0)``."""
        return (state[0], state[1], 0)
