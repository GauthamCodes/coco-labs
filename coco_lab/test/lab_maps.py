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
Seeded random maps for the property tests, and the networkx oracle.

A map is drawn by hypothesis as a handful of parameters -- size, density,
move model, corner rule, cost layer, a "wall" switch and an integer seed --
and then *generated* from ``random.Random(seed)``. Every map is therefore
reproducible from the parameters hypothesis prints on failure.

The oracle is networkx's Dijkstra on a DiGraph built from the same
``neighbours`` and ``edge_cost`` the algorithms see. That checks the
algorithms against an independent shortest-path implementation on the
identical graph; the grid's own move generation is pinned separately, by
hand-checked cases in ``test_grid.py``.
"""

from dataclasses import dataclass
import random
from typing import Optional, Tuple

from coco_lab.grid import Grid
from coco_lab.heuristics import SQRT2
from hypothesis import assume, event, HealthCheck, settings, strategies as st
import networkx as nx

#: Examples per property. The roadmap's floor is 1,000 maps per property.
MAPS_PER_PROPERTY = 1000

#: Property-test settings: derandomized (the same maps every run, so the
#: suite is a fixed, seeded set), no example database, no deadline.
PROPERTY_SETTINGS = settings(
    max_examples=MAPS_PER_PROPERTY,
    derandomize=True,
    database=None,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

#: "Exact within float tolerance": path costs are sums of 1, sqrt(2) and
#: cost-layer factors added in different orders by different algorithms,
#: so they may differ in the last bits. Nothing else is tolerated.
REL_TOL = 1e-9


def close(a: float, b: float) -> bool:
    """Return whether two path costs agree within :data:`REL_TOL`."""
    return abs(a - b) <= REL_TOL * max(1.0, abs(a), abs(b))


@dataclass
class Case:
    """One seeded random map with a start and a goal."""

    grid: Grid
    start: Tuple[int, int]
    goal: Tuple[int, int]
    seed: int

    @property
    def unit_costs(self) -> bool:
        """Return whether every edge costs exactly 1."""
        mm = self.grid.move_model
        no_layer = (not self.grid.describe()['cost_layer']
                    or self.grid.cost_weight == 0.0)
        return no_layer and (mm.connectivity == 4 or mm.diagonal_cost == 1.0)


@st.composite
def cases(draw, connectivity: Optional[int] = None,
          diagonal_cost: Optional[float] = None,
          cost_layer: Optional[bool] = None,
          wall_probability: float = 0.2,
          reachable: bool = False):
    """
    Draw a seeded random map: size, density, move model and costs vary.

    With probability ``wall_probability`` a full blocked column separates
    start from goal, so "no path" cases are common rather than accidental.

    With ``reachable=True`` there is no wall and the goal is drawn
    uniformly from the start's connected component instead, so EVERY map
    has a path. The properties about path cost use this: on a no-path map
    "A* cost == Dijkstra cost" is only ``None == None`` and tests nothing.
    An isolated start is re-drawn among the free cells that have a
    neighbour, and the goal is never the start. A map where no free cell
    has any neighbour (1 x 1, say) is discarded with ``assume`` and shows
    in the statistics as an invalid example, so every VALID example has a
    path of at least one move.
    """
    seed = draw(st.integers(min_value=0, max_value=2 ** 32 - 1))
    width = draw(st.integers(min_value=1, max_value=30))
    height = draw(st.integers(min_value=1, max_value=30))
    density = draw(st.sampled_from([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]))
    conn = connectivity or draw(st.sampled_from([4, 8]))
    if diagonal_cost is not None:
        diag = diagonal_cost
    else:
        diag = draw(st.sampled_from([SQRT2, 1.0])) if conn == 8 else SQRT2
    corner = draw(st.booleans())
    layer = cost_layer if cost_layer is not None else draw(st.booleans())
    weight = draw(st.sampled_from([0.5, 2.0, 10.0])) if layer else 0.0
    wall = (not reachable and width >= 3
            and draw(st.floats(0, 1)) < wall_probability)

    rng = random.Random(seed)
    blocked = [rng.random() < density for _ in range(width * height)]
    cost = [float(rng.randrange(0, 253)) for _ in range(width * height)] \
        if layer else None
    if wall:
        wc = rng.randrange(1, width - 1)
        for r in range(height):
            blocked[r * width + wc] = True
        start = (rng.randrange(height), rng.randrange(0, wc))
        goal = (rng.randrange(height), rng.randrange(wc + 1, width))
    else:
        start = (rng.randrange(height), rng.randrange(width))
        goal = (rng.randrange(height), rng.randrange(width))
    for r, c in ((start,) if reachable else (start, goal)):
        blocked[r * width + c] = False

    grid = Grid(width, height, blocked, cost, connectivity=conn,
                diagonal_cost=diag, corner_cutting=corner,
                cost_weight=weight)
    if reachable:
        if not any(True for _ in grid.neighbours(start)):
            # An isolated start tests nothing: re-pick among free cells
            # that have a neighbour, if the map has any.
            movable = [c for c in grid.states()
                       if any(True for _ in grid.neighbours(c))]
            if movable:
                start = movable[rng.randrange(len(movable))]
        component, frontier = [start], [start]
        seen = {start}
        while frontier:
            nxt = []
            for s in frontier:
                for n in grid.neighbours(s):
                    if n not in seen:
                        seen.add(n)
                        component.append(n)
                        nxt.append(n)
            frontier = nxt
        others = component[1:] or component  # never the start, if able
        goal = others[rng.randrange(len(others))]
        # A zero-length path tests nothing: discard it, so every one of
        # the MAPS_PER_PROPERTY valid examples has start != goal.
        assume(goal != start)
    event(f'move model: {conn}-connected'
          + (f', diagonal {diag:.3f}' if conn == 8 else ''))
    event(f'cost layer: {"yes" if layer and weight else "no"}')
    side = max(width, height)
    event('size: ' + ('<=10' if side <= 10 else '11-20' if side <= 20
                      else '21-30'))
    return Case(grid, start, goal, seed)


def oracle_graph(grid: Grid) -> nx.DiGraph:
    """Build the identical graph for networkx."""
    g = nx.DiGraph()
    for s in grid.states():
        g.add_node(s)
        for n in grid.neighbours(s):
            g.add_edge(s, n, weight=grid.edge_cost(s, n))
    return g


def oracle_cost(case: Case, graph: Optional[nx.DiGraph] = None
                ) -> Optional[float]:
    """Return networkx's optimal cost from start to goal, or None."""
    g = graph if graph is not None else oracle_graph(case.grid)
    try:
        return nx.dijkstra_path_length(g, case.start, case.goal,
                                       weight='weight')
    except nx.NetworkXNoPath:
        return None


def record_outcome(found: bool) -> None:
    """Tag the example with its outcome, for the statistics report."""
    event('outcome: path' if found else 'outcome: no path')


def isclose_or_none(a, b) -> bool:
    """Return whether two optional costs agree (both None, or close)."""
    if a is None or b is None:
        return a is None and b is None
    return close(a, b)


__all__ = ['Case', 'cases', 'close', 'isclose_or_none',
           'MAPS_PER_PROPERTY', 'oracle_cost', 'oracle_graph',
           'PROPERTY_SETTINGS', 'record_outcome', 'REL_TOL']
