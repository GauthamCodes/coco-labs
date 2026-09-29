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
The four grid heuristics, and whether each is admissible and consistent.

Every heuristic here is a function of the cell offset ``(dr, dc)`` to the
goal, in cell units, where an orthogonal move has base cost 1:

========== ===============================================
zero       ``0``
manhattan  ``|dr| + |dc|``
euclidean  ``sqrt(dr^2 + dc^2)``
octile     ``(max - min) + sqrt(2) * min`` of ``|dr|, |dc|``
========== ===============================================

Octile's diagonal coefficient is fixed at ``sqrt(2)``. It is *not* taken
from the move model, and that is deliberate: it is what makes octile
overestimate on a grid whose diagonal moves cost 1, which is one of the
two hypotheses Lab 1's ISRO exhibit tests.

:func:`analyse` is where the UI's admissibility and consistency badge comes
from. The TypeScript never recomputes it.
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple

from .graph import HEURISTICS

SQRT2 = math.sqrt(2.0)

#: Slack for comparing a heuristic value with a move cost. It absorbs
#: rounding only, e.g. ``hypot(1, 1)`` against ``sqrt(2)``; no heuristic
#: here is within 1e-9 of a move cost without being equal to it.
TOLERANCE = 1e-9


def zero(dr: int, dc: int) -> float:
    """Return 0: the heuristic that makes A* into Dijkstra."""
    return 0.0


def manhattan(dr: int, dc: int) -> float:
    """Return ``|dr| + |dc|``."""
    return float(abs(dr) + abs(dc))


def euclidean(dr: int, dc: int) -> float:
    """Return the straight-line distance."""
    return math.hypot(dr, dc)


def octile(dr: int, dc: int) -> float:
    """Return the octile distance, with diagonals priced at sqrt(2)."""
    a, b = abs(dr), abs(dc)
    lo, hi = (a, b) if a < b else (b, a)
    return (hi - lo) + SQRT2 * lo


FUNCTIONS = {
    'zero': zero,
    'manhattan': manhattan,
    'euclidean': euclidean,
    'octile': octile,
}
assert tuple(FUNCTIONS) == HEURISTICS


def evaluate(name: str, dr: int, dc: int) -> float:
    """Return heuristic ``name`` at offset ``(dr, dc)``."""
    try:
        fn = FUNCTIONS[name]
    except KeyError:
        raise ValueError(
            f'unknown heuristic {name!r}; expected one of {HEURISTICS}'
        ) from None
    return fn(dr, dc)


@dataclass(frozen=True)
class MoveModel:
    """
    The moves a grid allows, and their base costs.

    ``connectivity`` is 4 or 8. ``diagonal_cost`` is the base cost of a
    diagonal move on an 8-connected grid (``sqrt(2)`` by default; ``1`` is
    the "king's move" model). Orthogonal moves always cost 1.
    """

    connectivity: int = 8
    diagonal_cost: float = SQRT2

    def __post_init__(self):
        """Refuse a move model the analysis cannot speak for."""
        if self.connectivity not in (4, 8):
            raise ValueError(
                f'connectivity must be 4 or 8, got {self.connectivity!r}')
        if not (math.isfinite(self.diagonal_cost)
                and self.diagonal_cost > 0):
            raise ValueError(
                f'diagonal_cost must be finite and > 0, '
                f'got {self.diagonal_cost!r}')

    def moves(self) -> Tuple[Tuple[int, int, float], ...]:
        """
        Return ``(dr, dc, base_cost)`` per move, in neighbour order.

        The order is N, E, S, W, then NE, SE, SW, NW. It is part of the
        grid's definition, because it decides push order among ties.
        """
        orth = ((-1, 0, 1.0), (0, 1, 1.0), (1, 0, 1.0), (0, -1, 1.0))
        if self.connectivity == 4:
            return orth
        d = float(self.diagonal_cost)
        return orth + ((-1, 1, d), (1, 1, d), (1, -1, d), (-1, -1, d))


@dataclass(frozen=True)
class HeuristicReport:
    """
    Whether a heuristic is admissible and consistent under a move model.

    The verdict quantifies over **every** map on that move model: any
    occupancy, any start and goal, and any cost layer whose weight is
    ``>= 0`` (see :class:`coco_lab.grid.Grid`). When it is ``False``,
    ``witness`` is a single move ``(dr, dc, base_cost, h)`` on which the
    heuristic overestimates, which is also a complete counterexample: on
    an empty grid, a state one such move from the goal has true cost
    ``base_cost`` and heuristic ``h > base_cost``.
    """

    heuristic: str
    move_model: MoveModel
    admissible: bool
    consistent: bool
    witness: Optional[Tuple[int, int, float, float]]
    reason: str


def analyse(name: str, move_model: MoveModel) -> HeuristicReport:
    """
    Report whether heuristic ``name`` is admissible and consistent.

    **Why checking single moves is enough.** Each heuristic here is
    ``N(goal - s)`` for a norm ``N`` (``zero`` trivially; Manhattan is L1,
    Euclidean L2, and octile is ``max(|x| + k|y|, |y| + k|x|)`` with
    ``k = sqrt(2) - 1``, a maximum of two norms). A norm obeys the triangle
    inequality, so for an edge ``a -> b`` taken by move ``v``::

        h(a) <= h(b) + N(v) <= h(b) + base_cost(v) <= h(b) + c(a, b)

    whenever ``N(v) <= base_cost(v)`` for every move ``v``, because the cost
    layer only ever multiplies a base cost by a factor ``>= 1``. That is
    consistency, and consistency with ``h(goal) = 0`` implies
    admissibility.

    Conversely, if some move ``v`` has ``N(v) > base_cost(v)``, the state
    one move ``v`` away from the goal on an empty grid has true cost at
    most ``base_cost(v)`` but heuristic ``N(v)``: neither admissible nor
    consistent. So for these four, the two properties coincide and the
    single-move check decides both exactly.
    """
    if name not in FUNCTIONS:
        raise ValueError(
            f'unknown heuristic {name!r}; expected one of {HEURISTICS}')
    for dr, dc, cost in move_model.moves():
        h = evaluate(name, dr, dc)
        if h > cost + TOLERANCE:
            return HeuristicReport(
                heuristic=name, move_model=move_model,
                admissible=False, consistent=False,
                witness=(dr, dc, cost, h),
                reason=(f'{name} overestimates the move ({dr:+d}, {dc:+d}): '
                        f'h = {h:.6g} > cost {cost:.6g}'))
    return HeuristicReport(
        heuristic=name, move_model=move_model,
        admissible=True, consistent=True, witness=None,
        reason=(f'{name} never exceeds the cost of any single move, '
                f'so it is consistent, hence admissible'))
