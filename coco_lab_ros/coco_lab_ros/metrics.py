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
Path metrics, with the formulas fixed before any measurement (plan §D).

``L`` -- geometric length (m)
    Sum of ``|p[i+1] - p[i]|`` over the path's poses.
``E`` -- grid edge-sum cost (cells)
    Sum of C1 ``edge_cost(a[i] -> a[i+1])`` over the CELL sequence,
    ``coco_lab.grid.Grid.edge_cost`` in float64. Defined only when every
    step is a C1 move between free cells; otherwise ``None`` with the
    reason. Never coerced.
``I`` -- integrated declared cost (m)
    Each polyline segment is split into ``n = max(1, ceil(len / step))``
    equal parts, ``step = resolution / 20`` (2.5 mm at 0.05 m), and each
    part contributes ``(len / n) * (1 + 2.0 * c(mid) / 252)``, ``c`` the
    raw cost of the cell containing the part's midpoint (Nav2's own
    world-to-cell). ``enters_blocked`` is set if any midpoint or vertex
    has ``c >= 253`` or lies outside the map. It applies identically to
    every planner's path, so it is the cross-planner quantity; ``E`` is
    the conformance quantity. ``I != E * resolution`` in general.
``endpoint_ok``
    The last cell equals the goal cell.
``c_max``
    The largest raw cost at any midpoint or vertex (a clearance proxy in
    costmap units).

Tracking statistics use nearest-rank percentiles: ``p95`` of ``n`` sorted
values is the value at 1-based rank ``ceil(0.95 n)``. Distribution
summaries (``min, p25, median, p75, max``) use linear interpolation
between closest ranks (position ``q (n - 1)``), NumPy's default.
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

from .costmap import INSCRIBED, Snapshot

Point = Tuple[float, float]


def path_length(points: Sequence[Point]) -> float:
    """Return ``L``: the polyline's length."""
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(points, points[1:]))


def edge_sum(lab_cells: Sequence[Tuple[int, int]], grid
             ) -> Tuple[Optional[float], Optional[str]]:
    """
    Return ``(E, None)``, or ``(None, reason)`` where E is undefined.

    ``lab_cells`` are LabMap ``(row, col)``; ``grid`` is the C1 grid.
    """
    if not lab_cells:
        return None, 'empty path'
    for c in lab_cells:
        if not grid.is_valid(tuple(c)):
            return None, f'cell {tuple(c)} is blocked or outside the map'
    total = 0.0
    for a, b in zip(lab_cells, lab_cells[1:]):
        a, b = tuple(a), tuple(b)
        if a == b:
            return None, f'repeated cell {a}'
        if b not in set(grid.neighbours(a)):
            return None, f'{a} -> {b} is not a move on this graph'
        total += grid.edge_cost(a, b)
    return total, None


def integrated_cost(points: Sequence[Point], snapshot: Snapshot,
                    cost_weight: float = 2.0, cost_scale: float = 252.0,
                    step: Optional[float] = None) -> Dict[str, object]:
    """Return ``{I, enters_blocked, c_max, samples}`` (see module doc)."""
    if step is None:
        step = snapshot.resolution / 20.0
    total, blocked, cmax, samples = 0.0, False, 0, 0
    for p in points:
        c = snapshot.raw_cost_at_world(*p)
        cmax = max(cmax, c)
        blocked = blocked or c >= INSCRIBED
    for a, b in zip(points, points[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg == 0.0:
            continue
        n = max(1, math.ceil(seg / step))
        part = seg / n
        for k in range(n):
            t = (k + 0.5) / n
            c = snapshot.raw_cost_at_world(a[0] + t * (b[0] - a[0]),
                                           a[1] + t * (b[1] - a[1]))
            samples += 1
            cmax = max(cmax, c)
            blocked = blocked or c >= INSCRIBED
            total += part * (1.0 + cost_weight * c / cost_scale)
    return {'I': total, 'enters_blocked': blocked, 'c_max': cmax,
            'samples': samples}


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Return the distance from ``p`` to segment ``ab``."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    den = dx * dx + dy * dy
    if den == 0.0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / den))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def distance_to_polyline(p: Point, poly: Sequence[Point]) -> float:
    """Return the distance from ``p`` to the nearest point of ``poly``."""
    if len(poly) == 1:
        return math.hypot(p[0] - poly[0][0], p[1] - poly[0][1])
    return min(point_segment_distance(p, a, b)
               for a, b in zip(poly, poly[1:]))


def nearest_rank(values: Sequence[float], q: float) -> float:
    """Return the nearest-rank ``q``-quantile (1-based rank ceil(q n))."""
    if not values:
        raise ValueError('no values')
    s = sorted(values)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def tracking_stats(values: Sequence[float]) -> Dict[str, object]:
    """Return ``{n, mean, p95, max}`` of a list of distances."""
    if not values:
        return {'n': 0, 'mean': None, 'p95': None, 'max': None}
    return {'n': len(values), 'mean': sum(values) / len(values),
            'p95': nearest_rank(values, 0.95), 'max': max(values)}


def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Return the linear-interpolation quantile of pre-sorted values."""
    n = len(sorted_values)
    pos = q * (n - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def distribution(values: Sequence[float]) -> Dict[str, object]:
    """Return ``{n, min, p25, median, p75, max}``."""
    if not values:
        return {'n': 0, 'min': None, 'p25': None, 'median': None,
                'p75': None, 'max': None}
    s = sorted(values)
    return {'n': len(s), 'min': s[0], 'p25': quantile(s, 0.25),
            'median': quantile(s, 0.5), 'p75': quantile(s, 0.75),
            'max': s[-1]}


def relative_gap(value: float, reference: float) -> float:
    """Return ``(value - reference) / reference``."""
    return (value - reference) / reference


def lab_cells_of(nav2_cells: Sequence[Tuple[int, int]], snapshot: Snapshot
                 ) -> List[Tuple[int, int]]:
    """Convert Nav2 ``(mx, my)`` cells to LabMap ``(row, col)``."""
    return [snapshot.to_lab(mx, my) for mx, my in nav2_cells]
