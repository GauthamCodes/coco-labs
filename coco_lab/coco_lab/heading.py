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
A *(cell, incoming heading)* state space with a turn penalty.

When the cost of the next move depends on how the robot arrived, the cell
alone is not a state: two arrivals at one cell with different headings
have different futures, and a search that keeps only the cheaper arrival
can throw away the one that finishes cheaper. The remedy is to make the
heading part of the state. This module is that remedy, for the cost model
of the ISRO simulator (``docs/labs/ISRO_INVESTIGATION.md``):

- 8-connected moves over free cells, orthogonal cost 1, diagonal
  ``sqrt(2)``;
- a flat ``turn_penalty`` whenever a move's direction differs from the
  direction of the move that entered the cell -- any change of the
  direction vector, 45 degrees or 180, costs the same;
- no penalty on the first move, which has no incoming direction.

**States.** ``(row, col, h)``. ``h`` in ``0..7`` is the index in
:data:`ISRO_DIRS` of the move that ENTERED the cell. The start is
``(row, col, START)``: no heading yet. The goal is the sink
``(row, col, GOAL)``, entered from any arrival at the goal cell at cost 0,
so a search to it finds the cheapest arrival over every heading -- which
lets the unchanged :func:`coco_lab.search.search` run here, since it
stops at one goal state.

A search on this graph emits an ordinary v1 trace whose ``sub`` column is
``h``. It is a production :class:`coco_lab.graph.SearchGraph`, kept apart
from the historical reproduction in :mod:`coco_lab.isro`.
"""

import math
from typing import Dict, Iterator, Optional, Sequence, Tuple

from . import heuristics
from .heuristics import SQRT2

#: The ISRO simulator's move directions, in its order: N, S, W, E, NW, NE,
#: SW, SE as ``(drow, dcol)`` (``astar_simulator_final_v3_6.py`` l.107).
ISRO_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1),
             (-1, -1), (-1, 1), (1, -1), (1, 1))

#: ``h`` of the start state (no incoming heading) and of the goal sink.
START = 8
GOAL = 9

State = Tuple[int, int, int]


class HeadingGrid:
    """
    The (cell, incoming heading) graph of one start and goal.

    ``blocked`` is row-major, ``width * height``. ``corner_cutting``
    defaults to ``True`` because the ISRO simulator never checks the two
    cells a diagonal passes between; ``False`` applies
    :class:`coco_lab.grid.Grid`'s rule.
    """

    def __init__(self, width: int, height: int, blocked: Sequence[bool],
                 start: Tuple[int, int], goal: Tuple[int, int],
                 turn_penalty: float = 0.1, corner_cutting: bool = True):
        """Validate and freeze the graph."""
        if not (isinstance(width, int) and isinstance(height, int)
                and width > 0 and height > 0):
            raise ValueError(f'bad size {width!r} x {height!r}')
        if len(blocked) != width * height:
            raise ValueError('blocked has the wrong length')
        if not (isinstance(turn_penalty, (int, float))
                and math.isfinite(turn_penalty) and turn_penalty >= 0):
            raise ValueError(f'turn_penalty must be finite and >= 0, '
                             f'got {turn_penalty!r}')
        self.width, self.height = width, height
        self._blocked = tuple(bool(b) for b in blocked)
        self.turn_penalty = float(turn_penalty)
        self.corner_cutting = bool(corner_cutting)
        self.start = (int(start[0]), int(start[1]))
        self.goal = (int(goal[0]), int(goal[1]))

    @classmethod
    def from_map(cls, lab_map, start, goal, turn_penalty: float = 0.1,
                 corner_cutting: bool = True,
                 unknown: str = 'blocked') -> 'HeadingGrid':
        """Build from a :class:`coco_lab.maps.LabMap` (move model = args)."""
        grid = lab_map.to_grid(unknown=unknown)
        blocked = [grid.is_blocked((r, c)) for r in range(grid.height)
                   for c in range(grid.width)]
        return cls(lab_map.width, lab_map.height, blocked, tuple(start),
                   tuple(goal), turn_penalty, corner_cutting)

    # -- cells -------------------------------------------------------------

    def free(self, r: int, c: int) -> bool:
        """Return whether ``(r, c)`` is in bounds and not blocked."""
        return (0 <= r < self.height and 0 <= c < self.width
                and not self._blocked[r * self.width + c])

    def cell_moves(self, r: int, c: int) -> Iterator[Tuple[int, int, int]]:
        """Yield ``(nr, nc, dir_index)`` for every legal move from a cell."""
        for i, (dr, dc) in enumerate(ISRO_DIRS):
            nr, nc = r + dr, c + dc
            if not self.free(nr, nc):
                continue
            if dr and dc and not self.corner_cutting and not (
                    self.free(r + dr, c) and self.free(r, c + dc)):
                continue
            yield nr, nc, i

    # -- the SearchGraph interface -------------------------------------------

    def start_state(self, cell) -> State:
        """Return the start state of ``cell`` (it must be the start)."""
        return (cell[0], cell[1], START)

    def goal_state(self, cell) -> State:
        """Return the goal sink of ``cell`` (it must be the goal)."""
        return (cell[0], cell[1], GOAL)

    def is_valid(self, s) -> bool:
        """Return whether ``s`` is a state of this graph."""
        try:
            r, c, h = s
        except (TypeError, ValueError):
            return False
        if not all(isinstance(v, int) for v in s) or not self.free(r, c):
            return False
        if h == START:
            return (r, c) == self.start
        if h == GOAL:
            return (r, c) == self.goal
        return 0 <= h < len(ISRO_DIRS)

    def neighbours(self, s: State) -> Iterator[State]:
        """Yield the goal sink (from the goal cell), then the moves."""
        r, c, h = s
        if h == GOAL:
            return
        if (r, c) == self.goal:
            yield (r, c, GOAL)
        for nr, nc, i in self.cell_moves(r, c):
            yield (nr, nc, i)

    def edge_cost(self, a: State, b: State) -> float:
        """Return move cost plus ``turn_penalty`` on a change of heading."""
        if b[2] == GOAL:
            return 0.0
        dr, dc = ISRO_DIRS[b[2]]
        cost = SQRT2 if dr and dc else 1.0
        if a[2] != START and a[2] != b[2]:
            cost += self.turn_penalty
        return cost

    def heuristic(self, name: str, s: State, goal: State) -> float:
        """Return heuristic ``name`` on the cell offset (heading ignored)."""
        return heuristics.evaluate(name, goal[0] - s[0], goal[1] - s[1])

    def locate(self, s: State) -> Tuple[int, int, int]:
        """Return ``(row, col, h)``: ``sub`` is the heading index."""
        return (s[0], s[1], s[2])

    def state_at(self, loc) -> Optional[State]:
        """Return the state drawn at ``(row, col, sub)``, or ``None``."""
        s = (int(loc[0]), int(loc[1]), int(loc[2]))
        return s if self.is_valid(s) else None

    def describe(self) -> Dict[str, object]:
        """Return the graph's parameters, for a trace header."""
        return {
            'kind': 'heading_grid',
            'width': self.width,
            'height': self.height,
            'moves': 'isro_v3_6',
            'diagonal_cost': SQRT2,
            'turn_penalty': self.turn_penalty,
            'corner_cutting': self.corner_cutting,
            'start_sub': START,
            'goal_sub': GOAL,
        }

    # -- costing a cell path -------------------------------------------------

    def path_cost(self, cells: Sequence[Tuple[int, int]]) -> float:
        """
        Return the true cost of a cell path under this model.

        Used to price a path found by a cell-only search, whose own ``g``
        may not be the path's cost. Raises ``ValueError`` for a path that
        is not a sequence of legal moves.
        """
        total, prev_dir = 0.0, None
        for (r0, c0), (r1, c1) in zip(cells, cells[1:]):
            d = (r1 - r0, c1 - c0)
            if d not in ISRO_DIRS or not self.free(r1, c1) or not any(
                    (nr, nc) == (r1, c1) for nr, nc, _ in
                    self.cell_moves(r0, c0)):
                raise ValueError(f'{(r0, c0)} -> {(r1, c1)} is not a move')
            total += SQRT2 if d[0] and d[1] else 1.0
            if prev_dir is not None and d != prev_dir:
                total += self.turn_penalty
            prev_dir = d
        return total
