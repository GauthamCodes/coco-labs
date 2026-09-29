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
The interface every coco_lab algorithm searches.

The algorithms in :mod:`coco_lab.search` know nothing about grids. They see
a graph through five methods, and that is the whole contract:

``neighbours(state)``
    The successors of ``state``, in a fixed, deterministic order. The order
    is part of the graph's definition: it decides which of several
    equal-priority states is pushed first.
``edge_cost(a, b)``
    The cost of the edge ``a -> b``, finite and ``>= 0``. Only called for
    ``b`` in ``neighbours(a)``.
``heuristic(name, state, goal)``
    The named heuristic's estimate of the cost from ``state`` to ``goal``.
    ``name`` is one of :data:`HEURISTICS`.
``locate(state)``
    ``(row, col, sub)``: where ``state`` is drawn. ``sub`` is ``0`` for a
    plain cell and distinguishes several states in one cell otherwise --
    a heading index in a *(cell, heading)* space. Traces carry this triple.
``is_valid(state)``
    Whether ``state`` exists and is traversable. Searches refuse an
    invalid start or goal rather than returning "no path".

A state is any hashable value. A grid uses ``(row, col)``; a *(cell,
heading)* space uses ``(row, col, heading)`` and plugs in without touching
the algorithms, which is what Phase 1B and, later, Hybrid A* need.
"""

from typing import Hashable, Iterable, Protocol, Tuple

State = Hashable
Location = Tuple[int, int, int]

#: The heuristic names every graph must understand.
HEURISTICS = ('zero', 'manhattan', 'euclidean', 'octile')


class SearchGraph(Protocol):
    """What :func:`coco_lab.search.search` needs from a graph."""

    def neighbours(self, state: State) -> Iterable[State]:
        """Return the successors of ``state`` in a fixed order."""

    def edge_cost(self, a: State, b: State) -> float:
        """Return the cost of the edge ``a -> b`` (finite, ``>= 0``)."""

    def heuristic(self, name: str, state: State, goal: State) -> float:
        """Return heuristic ``name``'s estimate from ``state`` to ``goal``."""

    def locate(self, state: State) -> Location:
        """Return ``(row, col, sub)`` for drawing and tracing ``state``."""

    def is_valid(self, state: State) -> bool:
        """Return whether ``state`` exists and is traversable."""
