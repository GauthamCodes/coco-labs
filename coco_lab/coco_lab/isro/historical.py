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
Run the ISRO simulator's own search functions on a coco_lab map.

:mod:`coco_lab.isro.upstream_v3_6` holds the historical functions
verbatim. They read module globals -- ``grid``, ``ROWS``, ``COLS``,
``TURN_PENALTY``, ``static_obstacles``, ``dynamic_obstacles`` -- exactly as
they did inside the Pygame program. This harness sets those globals from a
:class:`coco_lab.maps.LabMap` and calls the functions; it never edits them.

Two instruments, both optional and both outside the verbatim code:

- ``mark_cell_explored`` is the hook the historical code calls on every
  counted pop; replacing the module attribute records the expansion ORDER,
  which gives the number of re-expansions (A*, which has no closed set)
  and stale pops (Dijkstra, which re-expands stale queue entries).
- ``heapq`` is looked up as a module global at call time; a counting shim
  gives the number of queue pushes ("generated").

Both slow the search, so :func:`run` times the call with instruments OFF
when ``timed=True``. The historical ``time`` metric is the source's own
``perf_counter`` around its search loop, rounded to 4 decimals by the
source; it is reported, never used for comparison.

This module is not thread-safe: the historical code keeps its state in
module globals, and so does this harness.
"""

from dataclasses import dataclass, field
import heapq as _heapq
import time
from typing import Dict, List, Optional, Tuple

from . import upstream_v3_6 as up

Cell = Tuple[int, int]

ALGORITHMS = ('astar', 'dijkstra', 'bfs')
_FUNCTIONS = {'astar': 'astar', 'dijkstra': 'dijkstra', 'bfs': 'bfs'}


@dataclass
class HistoricalResult:
    """One call of a historical search function, and what it reported."""

    algorithm: str
    found: bool
    path: List[Cell]
    source_metrics: Dict[str, object]
    smoothed: Optional[List[Cell]]
    smoothing_terminates: bool = True
    expansions: Optional[int] = None
    distinct_expanded: Optional[int] = None
    pushes: Optional[int] = None
    expansion_order: List[Cell] = field(default_factory=list)
    seconds: Optional[float] = None

    @property
    def smoothed_steps(self) -> Optional[int]:
        """
        Return the simulator's logged ``Steps``: ``len(smooth_path(path))``.

        The historical path excludes the start cell, and so does this, as
        in ``animate_robot_to_goals`` (upstream l.398, l.413). ``None``
        when there is no path, or when the smoother would never return
        (:func:`smoothing_terminates`).
        """
        return None if self.smoothed is None else len(self.smoothed)


class _CountingHeapq:
    """A stand-in for :mod:`heapq` that counts pushes."""

    def __init__(self):
        self.pushes = 0

    def heappush(self, heap, item):
        self.pushes += 1
        _heapq.heappush(heap, item)

    heappop = staticmethod(_heapq.heappop)


def load(lab_map, turn_penalty: float = 0.1,
         unknown: str = 'blocked') -> None:
    """
    Install ``lab_map`` into the historical module's globals.

    Blocked cells become ``static_obstacles`` AND ``type == 'obstacle'``,
    as ``load_startup_file`` does (upstream l.588-591). There are no
    dynamic obstacles and no robots.
    """
    grid = lab_map.to_grid(unknown=unknown)
    up.ROWS, up.COLS = lab_map.height, lab_map.width
    up.TURN_PENALTY = turn_penalty
    up.grid = [[up.Cell(r, c) for c in range(up.COLS)]
               for r in range(up.ROWS)]
    up.static_obstacles = set()
    up.dynamic_obstacles = []
    up.CURRENT_EXPLORER = None
    for r in range(up.ROWS):
        for c in range(up.COLS):
            if grid.is_blocked((r, c)):
                up.grid[r][c].type = 'obstacle'
                up.static_obstacles.add((r, c))


def run(lab_map, start: Cell, goal: Cell, algorithm: str,
        turn_penalty: float = 0.1, unknown: str = 'blocked',
        instrument: bool = True, timed: bool = False) -> HistoricalResult:
    """
    Call the historical ``astar``, ``dijkstra`` or ``bfs`` once.

    ``found`` is decided here, not by the source: the source returns
    ``[goal]`` when there is no path (its reconstruction loop starts at the
    goal and stops at a missing parent), so the harness checks that the
    parent chain actually reaches the start.
    """
    if algorithm not in ALGORITHMS:
        raise ValueError(f'algorithm must be one of {ALGORITHMS}')
    fn_name = _FUNCTIONS[algorithm]
    seconds = None
    if timed:
        load(lab_map, turn_penalty, unknown)
        fn = getattr(up, fn_name)
        t0 = time.perf_counter()
        fn(tuple(start), tuple(goal))
        seconds = time.perf_counter() - t0

    load(lab_map, turn_penalty, unknown)
    order: List[Cell] = []
    shim = _CountingHeapq()
    saved = (up.mark_cell_explored, up.heapq)
    if instrument:
        up.mark_cell_explored = lambda cell, label: order.append(
            (cell.row, cell.col))
        up.heapq = shim
    try:
        cells, metrics = getattr(up, fn_name)(tuple(start), tuple(goal))
    finally:
        up.mark_cell_explored, up.heapq = saved
    path = [(c.row, c.col) for c in cells]
    found = _reaches_start(tuple(start), tuple(goal))
    terminates = smoothing_terminates(cells) if found else True
    smoothed = [(c.row, c.col) for c in up.smooth_path(cells)] \
        if found and terminates else None
    return HistoricalResult(
        algorithm=algorithm, found=found,
        path=[tuple(start)] + path if found else [],
        source_metrics=dict(metrics), smoothed=smoothed,
        smoothing_terminates=terminates,
        expansions=len(order) if instrument else None,
        distinct_expanded=len(set(order)) if instrument else None,
        pushes=(shim.pushes if algorithm != 'bfs'
                else metrics['explored']) if instrument else None,
        expansion_order=order, seconds=seconds)


def smoothing_terminates(cells) -> bool:
    """
    Return whether the verbatim ``smooth_path(cells)`` would return.

    It does not always. Its outer loop (upstream l.314-321) advances ``i``
    to the farthest ``j`` in line of sight; if NO later waypoint is in
    line of sight, ``j`` falls to ``i``, ``path[i]`` is appended and ``i``
    does not move -- forever, growing a list. ``line_of_sight``'s
    Bresenham walk checks one orthogonal cell of a diagonal step, and
    ``neighbors`` lets a diagonal cut past a blocked corner, so a path the
    searches return can contain such a step (measured: a 3 x 3 map, see
    ``test_isro.py``). This replays the loop's control flow with the
    verbatim ``line_of_sight`` and no list, so the harness never calls the
    smoother on a path it cannot finish.
    """
    i = 0
    while i < len(cells) - 1:
        j = len(cells) - 1
        while j > i:
            if up.line_of_sight(cells[i], cells[j]):
                break
            j -= 1
        if j == i:
            return False
        i = j
    return True


def _reaches_start(start: Cell, goal: Cell) -> bool:
    if start == goal:
        return True
    cell = up.grid[goal[0]][goal[1]]
    seen = set()
    while cell.parent is not None and id(cell) not in seen:
        seen.add(id(cell))
        cell = cell.parent
        if (cell.row, cell.col) == start:
            return True
    return False
