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
RRT* (Karaman and Frazzoli 2011): a COCO Lab built-in planner (R6.B2, coco.algorithm.v1).

RRT, plus two steps that make it asymptotically optimal: each new node takes the cheapest clear parent within
`radius_m` (not just the nearest), and then each node within that radius is rewired through the new node if that
is cheaper. It keeps refining for `refine` iterations after the first path, then returns the cheapest path found.
Cost = path length. Same collision rule and seeding as RRT (see planner_rrt): clear = the segment's supercover
(`crossed`, from Gautham Anil's Lazy Theta* entry, MIT) under INSCRIBED_INFLATED_OBSTACLE; every draw is ctx.rng.

Parameters (ctx.params): iterations (20000), refine (3000), step_m (0.75), radius_m (1.5), goal_bias (0.1).
"""
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


class Buckets:
    """Cells in square buckets of `size` cells: the nearest node without scanning them all."""

    def __init__(self, size):
        self.size, self.cells = max(1, int(size)), {}

    def add(self, i, c):
        self.cells.setdefault((c[0] // self.size, c[1] // self.size), []).append((i, c))

    def nearest(self, q, nodes):
        bx, by = q[0] // self.size, q[1] // self.size
        best, best_d, r = None, math.inf, 0
        while r <= 4096:
            for x in range(bx - r, bx + r + 1):
                for y in range(by - r, by + r + 1):
                    if max(abs(x - bx), abs(y - by)) != r:
                        continue                     # this ring only
                    for i, c in self.cells.get((x, y), ()):
                        d = dist(c, q)
                        if d < best_d or (d == best_d and i < best):
                            best, best_d = i, d
            if best is not None and best_d <= r * self.size:
                return best                          # nothing in a further ring can be nearer
            r += 1
        return best


def within(index, q, radius):
    """Return the nodes (index, cell) within `radius` cells of q, nearest first (ties: lower index)."""
    r = int(math.ceil(radius / index.size))
    bx, by = q[0] // index.size, q[1] // index.size
    out = [(dist(c, q), i, c) for x in range(bx - r, bx + r + 1) for y in range(by - r, by + r + 1)
           for i, c in index.cells.get((x, y), ()) if dist(c, q) <= radius]
    return [(i, c) for _, i, c in sorted(out)]


def poses(costmap, cells):
    return [Pose2D(*costmap.map_to_world(*c), 0.0) for c in cells]


def plan(costmap, start, goal, ctx):
    iterations = int(ctx.params.get('iterations', 20000))
    refine = int(ctx.params.get('refine', 3000))
    res = costmap.metadata.resolution
    step = float(ctx.params.get('step_m', 0.75)) / res
    radius = float(ctx.params.get('radius_m', 1.5)) / res
    bias = float(ctx.params.get('goal_bias', 0.1))
    nx_, ny_ = costmap.metadata.size_x, costmap.metadata.size_y
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)
    nodes, parent, cost, seen = [s], [-1], [0.0], {s}
    index = Buckets(step)
    index.add(0, s)
    best, best_cost, left = None, math.inf, None   # the node that reaches the goal most cheaply
    for _ in range(iterations):
        ctx.step()
        if left is not None:
            left -= 1
            if left < 0:
                break
        q = g if ctx.rng.random() < bias else (ctx.rng.randrange(nx_), ctx.rng.randrange(ny_))
        a = nodes[index.nearest(q, nodes)]
        d = dist(a, q)
        if d < 0.5:
            continue
        f = min(1.0, step / d)
        new = (int(round(a[0] + f * (q[0] - a[0]))), int(round(a[1] + f * (q[1] - a[1]))))
        if new in seen:
            continue
        near = [(i, c) for i, c in within(index, new, radius) if clear(costmap, c, new)]
        if not near:
            continue
        p, c_new = min(((i, cost[i] + dist(c, new)) for i, c in near), key=lambda t: (t[1], t[0]))
        seen.add(new)
        nodes.append(new)
        parent.append(p)
        cost.append(c_new)
        k = len(nodes) - 1
        index.add(k, new)
        wx, wy = costmap.map_to_world(*new)
        ctx.emit('push', x=wx, y=wy)
        for i, c in near:                 # rewire through the new node where that is cheaper
            through = c_new + dist(new, c)
            if through < cost[i] - 1e-9:
                parent[i], cost[i] = k, through
        if dist(new, g) <= step and clear(costmap, new, g) and c_new + dist(new, g) < best_cost:
            best, best_cost = k, c_new + dist(new, g)
            if left is None:
                left = refine
    if best is None:
        return None
    path, i = [g], best
    while i >= 0:
        path.append(nodes[i])
        i = parent[i]
    path.reverse()
    return poses(costmap, path)
