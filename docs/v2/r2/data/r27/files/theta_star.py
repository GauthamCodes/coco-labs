"""
Lazy Theta*: any-angle A* on Nav2's costmap (coco.algorithm.v1), for COCO-Bench.

A* on the 8-connected grid finds paths that zig-zag at 45 degrees. Theta* (Nash, Daniel,
Koenig and Felner, AAAI 2007) lets a cell's parent be ANY earlier cell it can see in a
straight line, so its path is a few long straight segments. Lazy Theta* (Nash, Koenig and
Tovey, AAAI 2010) checks that line of sight once, when a cell is expanded, not for every
neighbour: the same paths for a fraction of the work.

Line of sight: every cell the straight segment between two cell centres crosses (its
supercover, Dedu's walk, which includes both cells where it passes exactly through a corner)
costs less than 253 -- a superset of the cells the runner's collision check samples, so a path
this planner calls clear is clear. A segment costs its length times (1 + cost_weight x the mean
cost of the cells it crosses / 252), as the grid planners price each step.

Licence: MIT. Author: Gautham Anil (written through the API with Claude Code as the
leaderboard's first submission).
"""
import heapq
import math

from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D

LETHAL = INSCRIBED_INFLATED_OBSTACLE


def crossed(a, b):
    """The cells the segment between cell centres a and b crosses (Dedu's supercover)."""
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


def plan(costmap, start, goal, ctx):
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)
    weight = ctx.params.get('cost_weight', ctx.config.get('cost_weight', 2.0))
    cost = costmap.cost

    def segment(a, b):
        """(clear, cost) of driving straight from a to b."""
        cells = crossed(a, b)
        total = 0
        for c in cells:
            v = cost(*c)
            if v >= LETHAL:
                return False, math.inf
            total += v
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        return True, length * (1.0 + weight * total / len(cells) / 252.0)

    def step(a, b):
        """The cost of one 8-connected step (the grid planners' price)."""
        return math.hypot(b[0] - a[0], b[1] - a[1]) * (1.0 + weight * (cost(*a) + cost(*b))
                                                       / 2.0 / 252.0)

    def h(c):
        return math.hypot(c[0] - g[0], c[1] - g[1])

    gc = {s: 0.0}
    parent = {s: s}
    heap = [(h(s), 0, s)]
    seq = 1
    closed = set()
    while heap:
        _, _, cell = heapq.heappop(heap)
        if cell in closed:
            continue
        # Lazy Theta*: make the assumed line of sight from the parent true, or fall back
        p = parent[cell]
        if p != cell and max(abs(p[0] - cell[0]), abs(p[1] - cell[1])) > 1:
            clear, c = segment(p, cell)
            if clear:
                gc[cell] = gc[p] + c
            else:
                best, via = math.inf, None
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        n = (cell[0] + dx, cell[1] + dy)
                        if (dx or dy) and n in closed:
                            v = gc[n] + step(n, cell)
                            if v < best:
                                best, via = v, n
                if via is None:
                    continue
                gc[cell], parent[cell] = best, via
        closed.add(cell)
        x, y = costmap.map_to_world(*cell)
        ctx.emit('expand', x=x, y=y)
        ctx.step()
        if cell == g:
            break
        p = parent[cell]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (cell[0] + dx, cell[1] + dy)
                if not (dx or dy) or n in closed or cost(*n) >= LETHAL:
                    continue
                if dx and dy and (cost(cell[0] + dx, cell[1]) >= LETHAL
                                  or cost(cell[0], cell[1] + dy) >= LETHAL):
                    continue
                # assume the parent sees n (checked when n is expanded); price it by length
                v = gc[p] + math.hypot(n[0] - p[0], n[1] - p[1]) * (
                    1.0 + weight * (cost(*p) + cost(*n)) / 2.0 / 252.0)
                if v < gc.get(n, math.inf):
                    gc[n], parent[n] = v, p
                    heapq.heappush(heap, (v + h(n), seq, n))
                    seq += 1
    if g not in closed:
        return None
    cells = [g]
    while cells[-1] != s:
        cells.append(parent[cells[-1]])
    cells.reverse()
    return [Pose2D(*costmap.map_to_world(*c)) for c in cells]
