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
Hybrid-A* (Dolgov, Thrun, Montemerlo and Diebel 2008), a simple DUBINS-STYLE version: a COCO Lab built-in planner
(R6.B2, coco.algorithm.v1).

A* over continuous poses (x, y, heading): from each pose it drives three forward arcs of length step_m -- turn left
at the minimum radius, straight, turn right -- and keeps the cheapest arrival per (square of step_m, heading bin
of 360/bins degrees). The path it returns is every sampled point of its arcs, so the runner checks exactly the
chords the planner did. Cost = arc length, plus turn_penalty x length on a turning arc; heuristic = straight-line distance to the
goal (admissible). Done when a pose is within goal_tol_m of the goal and sees it. What it is NOT, stated: Dubins
only (forward, no reversing: not Reeds-Shepp); no analytic Dubins expansion to the goal; no non-holonomic heuristic.
COCO turns in place, so this models a car-like constraint COCO does not have: a teaching comparison, not COCO's
planner. Collision: every cell each arc's sampled chords cross (the supercover, `crossed`, from Gautham Anil's
Lazy Theta* entry, MIT) under INSCRIBED_INFLATED_OBSTACLE.

Parameters (ctx.params): turn_radius_m (0.5), step_m (0.25), bins (16), turn_penalty (0.1), goal_tol_m (0.2).
"""
import heapq
import math

from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D

LETHAL = INSCRIBED_INFLATED_OBSTACLE


def crossed(a, b):
    """Return the cells the segment between cell centres a and b crosses (Dedu's supercover)."""
    x, y = a
    dx, dy = b[0] - x, b[1] - y
    sx, sy = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
    dx, dy = abs(dx), abs(dy)
    out = [(x, y)]
    if dx >= dy:
        err = prev = dx
        for _ in range(dx):
            x += sx
            err += 2 * dy
            if err > 2 * dx:
                y += sy
                err -= 2 * dx
                if err + prev < 2 * dx:
                    out.append((x, y - sy))
                elif err + prev > 2 * dx:
                    out.append((x - sx, y))
                else:
                    out.append((x, y - sy))
                    out.append((x - sx, y))
            out.append((x, y))
            prev = err
    else:
        err = prev = dy
        for _ in range(dy):
            y += sy
            err += 2 * dx
            if err > 2 * dy:
                x += sx
                err -= 2 * dy
                if err + prev < 2 * dy:
                    out.append((x - sx, y))
                elif err + prev > 2 * dy:
                    out.append((x, y - sy))
                else:
                    out.append((x - sx, y))
                    out.append((x, y - sy))
            out.append((x, y))
            prev = err
    return out


def clear(costmap, a, b):
    """Return whether the segment between cells a and b is clear."""
    return all(costmap.cost(*c) < LETHAL for c in crossed(a, b))


def dist(a, b):
    """Return the distance between two cells (in cells)."""
    dx, dy = a[0] - b[0], a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


def cell_of(x, y):
    return (int(math.floor(x + 0.5)), int(math.floor(y + 0.5)))


def arc(x, y, th, length, curvature, n):
    """Return n+1 points along an arc from (x, y, th) (cells, rad), and the end heading."""
    pts = [(x, y)]
    for i in range(1, n + 1):
        s = length * i / n
        if curvature == 0.0:
            pts.append((x + s * math.cos(th), y + s * math.sin(th)))
        else:
            r = 1.0 / curvature
            pts.append((x + r * (math.sin(th + s * curvature) - math.sin(th)),
                        y - r * (math.cos(th + s * curvature) - math.cos(th))))
    return pts, th + length * curvature


def plan(costmap, start, goal, ctx):
    res = costmap.metadata.resolution
    radius = float(ctx.params.get('turn_radius_m', 0.5)) / res
    step = float(ctx.params.get('step_m', 0.25)) / res
    bins = int(ctx.params.get('bins', 16))
    penalty = float(ctx.params.get('turn_penalty', 0.1))
    tol = float(ctx.params.get('goal_tol_m', 0.2)) / res
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)
    two_pi = 2.0 * math.pi

    def key(x, y, th):   # Hybrid-A*'s coarse grid: squares of one step, not costmap cells
        return (int(math.floor(x / step)), int(math.floor(y / step)),
                int(math.floor((th % two_pi) / two_pi * bins + 0.5)) % bins)

    n = max(2, int(math.ceil(step)))                   # chord samples per arc: about one per cell
    states = [(float(s[0]), float(s[1]), start.theta)]
    parent, gcost, via = [-1], [0.0], [[s]]   # via: the cells of the arc that reached each state
    best = {key(*states[0]): 0.0}
    heap = [(dist(s, g), 0.0, 0)]
    while heap:
        f, gc, i = heapq.heappop(heap)
        if gc > gcost[i]:
            continue
        ctx.step()
        x, y, th = states[i]
        here = cell_of(x, y)
        wx, wy = costmap.map_to_world(*here)
        ctx.emit('expand', x=wx, y=wy)
        if dist(here, g) <= tol and clear(costmap, here, g):
            cells, j = [g], i
            while j >= 0:
                cells.extend(reversed(via[j]))
                j = parent[j]
            cells.reverse()
            path = [c for k, c in enumerate(cells) if k == 0 or c != cells[k - 1]]
            return [Pose2D(*costmap.map_to_world(*c), 0.0) for c in path]
        for curvature, turn in ((1.0 / radius, True), (0.0, False), (-1.0 / radius, True)):
            pts, nth = arc(x, y, th, step, curvature, n)
            cells = [cell_of(px, py) for px, py in pts]
            if not all(clear(costmap, a, b) for a, b in zip(cells, cells[1:])):
                continue
            nx_, ny_ = pts[-1]
            k = key(nx_, ny_, nth)
            ng = gc + step * (1.0 + (penalty if turn else 0.0))
            if ng < best.get(k, math.inf) - 1e-9:
                best[k] = ng
                states.append((nx_, ny_, nth))
                parent.append(i)
                gcost.append(ng)
                via.append(cells[1:])
                heapq.heappush(heap, (ng + dist(cell_of(nx_, ny_), g), ng, len(states) - 1))
    return None
