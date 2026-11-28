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
PRM (probabilistic roadmap; Kavraki, Svestka, Latombe and Overmars 1996): a COCO Lab built-in planner (R6.B2,
coco.algorithm.v1).

Samples `samples` free cells (seeded by ctx.rng), adds the start and the goal, connects every node to the nodes
within `connect_m` that it can see (at most `k` of them, nearest first), and searches the roadmap with Dijkstra
(cost = length). Same collision rule as RRT (see planner_rrt): the segment's supercover (`crossed`, from Gautham
Anil's Lazy Theta* entry, MIT) under INSCRIBED_INFLATED_OBSTACLE. A single-query PRM here: the roadmap is built
for each call (the API gives no memory across plans).

Parameters (ctx.params): samples (1500), connect_m (2.0), k (12).
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
    samples = int(ctx.params.get('samples', 1500))
    radius = float(ctx.params.get('connect_m', 2.0)) / costmap.metadata.resolution
    k = int(ctx.params.get('k', 12))
    nx_, ny_ = costmap.metadata.size_x, costmap.metadata.size_y
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)
    nodes, seen = [s, g], {s, g}
    tries = 0
    while len(nodes) < samples + 2 and tries < samples * 20:
        tries += 1
        ctx.step()
        c = (ctx.rng.randrange(nx_), ctx.rng.randrange(ny_))
        if c not in seen and costmap.cost(*c) < LETHAL:
            seen.add(c)
            nodes.append(c)
    index = Buckets(radius)
    for i, c in enumerate(nodes):
        index.add(i, c)
    edges = {i: [] for i in range(len(nodes))}
    for i, c in enumerate(nodes):
        ctx.step()
        for j, d_ in [(j, d_) for j, d_ in within(index, c, radius) if j != i][:k]:
            if j > i and clear(costmap, c, d_):
                w = dist(c, d_)
                edges[i].append((j, w))
                edges[j].append((i, w))
    best, prev, heap = {0: 0.0}, {0: -1}, [(0.0, 0)]
    while heap:
        d0, i = heapq.heappop(heap)
        if d0 > best.get(i, math.inf):
            continue
        wx, wy = costmap.map_to_world(*nodes[i])
        ctx.emit('expand', x=wx, y=wy)
        if i == 1:
            break
        for j, w in edges[i]:
            if d0 + w < best.get(j, math.inf):
                best[j], prev[j] = d0 + w, i
                heapq.heappush(heap, (d0 + w, j))
    if 1 not in prev:
        return None
    path, i = [], 1
    while i >= 0:
        path.append(nodes[i])
        i = prev[i]
    path.reverse()
    return poses(costmap, path)
