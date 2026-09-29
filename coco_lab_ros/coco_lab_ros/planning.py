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
The two declared move models, and one coco_lab search on a snapshot.

Pre-registered in ``docs/labs/PHASE_1C_PLAN.md`` §D before any
measurement, and never tuned afterwards:

``C0`` -- coco_lab's default
    8-connected, diagonal sqrt(2), corner cutting OFF, cost weight 2.0,
    cost scale 252, unknown blocked.
``C1`` -- "the same graph as Smac"
    C0 with corner cutting ON. Smac 2D's ``Node2D::getNeighbors``
    (``node_2d.cpp`` @1.3.11 :114-153) checks only the neighbour cell, so
    it cuts corners. Every value is a toggle or default that existed at
    Phase 1A's ``c3713dd``.

C1 is what the real runs drive and what conformance compares with Smac.
"""

from dataclasses import dataclass
import time
from typing import Dict, List, Optional, Tuple

from coco_lab.heuristics import SQRT2
from coco_lab.maps import LabMap
from coco_lab.search import search, SearchResult

from .costmap import Snapshot

CONFIGS: Dict[str, Dict[str, object]] = {
    'C0': {'connectivity': 8, 'diagonal_cost': SQRT2,
           'corner_cutting': False, 'cost_weight': 2.0,
           'cost_scale': 252.0, 'unknown': 'blocked'},
    'C1': {'connectivity': 8, 'diagonal_cost': SQRT2,
           'corner_cutting': True, 'cost_weight': 2.0,
           'cost_scale': 252.0, 'unknown': 'blocked'},
}

#: The three algorithms the real runs use, with their heuristics, exactly
#: as plan §E.2 declares them (Dijkstra: zero).
RUN_ALGORITHMS = {
    'astar': 'euclidean',
    'dijkstra': 'zero',
    'greedy': 'euclidean',
}


class PlanError(ValueError):
    """A request that cannot be planned (outside the map, blocked cell)."""


@dataclass
class Plan:
    """One search on one snapshot, with everything needed to record it."""

    snapshot: Snapshot
    lab_map: LabMap
    config: str
    model: Dict[str, object]
    start_nav2: Tuple[int, int]
    goal_nav2: Tuple[int, int]
    start_lab: Tuple[int, int]
    goal_lab: Tuple[int, int]
    result: SearchResult
    plan_seconds: float

    @property
    def found(self) -> bool:
        """Return whether a path was found."""
        return self.result.found

    def cells_nav2(self) -> List[Tuple[int, int]]:
        """Return the path as Nav2 ``(mx, my)`` cells, start first."""
        return [self.snapshot.from_lab(r, c)
                for r, c in (tuple(s) for s in (self.result.path or []))]


class Planner:
    """
    Plan repeatedly on one snapshot.

    The LabMap and each configuration's grid are built once and reused,
    so a conformance sweep over many pairs searches one fixed graph.
    """

    def __init__(self, snapshot: Snapshot, map_id: str = 'costmap_raw'):
        """Convert the snapshot once."""
        self.snapshot = snapshot
        self.lab_map = snapshot.to_labmap(map_id)
        self._grids = {}

    def grid(self, config: str):
        """Return (and cache) the grid of move model ``config``."""
        if config not in CONFIGS:
            raise PlanError(f'unknown config {config!r}; '
                            f'known: {sorted(CONFIGS)}')
        if config not in self._grids:
            self._grids[config] = self.lab_map.to_grid(**CONFIGS[config])
        return self._grids[config]

    def cell_of(self, wx: float, wy: float, what: str) -> Tuple[int, int]:
        """Return Nav2's cell for a world point, or raise PlanError."""
        cell = self.snapshot.world_to_cell(wx, wy)
        if cell is None:
            raise PlanError(f'{what} ({wx}, {wy}) is outside the costmap')
        return cell

    def plan_cells(self, start_nav2: Tuple[int, int],
                   goal_nav2: Tuple[int, int], algorithm: str,
                   heuristic: str, config: str = 'C1',
                   tie_break: str = 'low_h',
                   weight: Optional[float] = None) -> Plan:
        """Search from one Nav2 cell to another under ``config``."""
        grid = self.grid(config)
        s = self.snapshot.to_lab(*start_nav2)
        g = self.snapshot.to_lab(*goal_nav2)
        for what, cell in (('start', s), ('goal', g)):
            if not grid.is_valid(cell):
                raise PlanError(
                    f'{what} cell {self.snapshot.from_lab(*cell)} is '
                    f'blocked (raw cost '
                    f'{self.snapshot.cost(*self.snapshot.from_lab(*cell))})')
        t0 = time.perf_counter()
        result = search(grid, s, g, algorithm, heuristic, weight=weight,
                        tie_break=tie_break)
        dt = time.perf_counter() - t0
        return Plan(self.snapshot, self.lab_map, config,
                    dict(CONFIGS[config]), tuple(start_nav2),
                    tuple(goal_nav2), s, g, result, dt)

    def plan_world(self, start_xy: Tuple[float, float],
                   goal_xy: Tuple[float, float], algorithm: str,
                   heuristic: str, config: str = 'C1',
                   tie_break: str = 'low_h') -> Plan:
        """Search between two world points, converted as Smac 2D does."""
        return self.plan_cells(self.cell_of(*start_xy, 'start'),
                               self.cell_of(*goal_xy, 'goal'),
                               algorithm, heuristic, config, tie_break)
