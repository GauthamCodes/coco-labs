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
Compare adapters around existing global planners, without changing Arena.

D* Lite's display projection retains expansion/raise locations and its path.
Unknown forward-search g/h/f and parents are -1, never fabricated. Native
D* Lite remains the reference; this adapter does not implement search.
"""
from dataclasses import dataclass

from .arena import PLANNERS
from .dstarlite import DStarLite, EXPAND, PATH, RAISE
from .numerics import math
from .search import collect, search_events

COMPARE_PLANNERS = tuple(PLANNERS) + ('dstar_lite',)


@dataclass
class ComparedSearch:
    status: str
    path: list
    summary: dict


def run_planner(grid, start, goal, name, sink):
    """Run one existing reference, projecting only what the display needs."""
    if name != 'dstar_lite':
        result = collect(search_events(grid, start, goal, **PLANNERS[name]), sink)
        return ComparedSearch(result.status, result.path, result.trace.summary)
    engine = DStarLite(grid, start, goal, heuristic='octile')
    found = engine.compute()
    columns = engine.trace.columns
    for i, kind in enumerate(columns['kind']):
        if kind not in (EXPAND, RAISE, PATH):
            continue
        sink((3 if kind == PATH else 1, columns['row'][i], columns['col'][i],
              columns['sub'][i], -1.0, -1.0, -1.0, -1, -1, -1))
    path = engine.path()
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                 for a, b in zip(path, path[1:]))
    summary = {'expansions': engine.expansions, 'path_length': length,
               'path_cost': engine.path_cost(path) if found else None,
               'path_steps': max(0, len(path) - 1)}
    return ComparedSearch('found' if found else 'no_path', path, summary)
