# R4.7 wrong solution for m1-heuristic: h = 0 (Dijkstra: optimal but no saving)
"""
Try it yourself: write A*'s heuristic.

A* expands cells in order of f = g + h: g is the cost so far, h your guess of the
cost still to go. Everything else is written. Your heuristic decides how many cells
A* expands -- and whether the path it finds is the shortest.

  h = 0                     A* becomes Dijkstra: correct, but expands everything nearby
  h = straight-line         never overestimates on this grid: still optimal, fewer expansions
  h = octile                the exact cost on an empty 8-connected grid: fewer still
  h = 3 x octile            overestimates: very few expansions, but the path may be longer

Run it on one scenario, look at the expansions, then run an experiment against the
built-in A* and Dijkstra.
"""
import heapq
import math

from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D


def heuristic(cell, goal):
    """Your guess of the cost from cell (mx, my) to goal (mx, my), in cells."""
    dx, dy = abs(cell[0] - goal[0]), abs(cell[1] - goal[1])
    # TODO: replace 0.0 with a better guess (dx and dy are ready for you)
    return 0.0


def plan(costmap, start, goal, ctx):
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)
    heap = [(heuristic(s, g), 0.0, s)]
    best = {s: 0.0}
    parent = {s: None}
    done = set()
    while heap:
        _, gc, cell = heapq.heappop(heap)
        if cell in done:
            continue
        done.add(cell)
        x, y = costmap.map_to_world(*cell)
        ctx.emit('expand', x=x, y=y)
        ctx.step()
        if cell == g:
            break
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                nxt = (cell[0] + dx, cell[1] + dy)
                if costmap.cost(*nxt) >= INSCRIBED_INFLATED_OBSTACLE:
                    continue
                if dx and dy and (costmap.cost(cell[0] + dx, cell[1]) >= INSCRIBED_INFLATED_OBSTACLE
                                  or costmap.cost(cell[0], cell[1] + dy) >= INSCRIBED_INFLATED_OBSTACLE):
                    continue
                ng = gc + (math.sqrt(2.0) if dx and dy else 1.0)
                if ng < best.get(nxt, math.inf):
                    best[nxt] = ng
                    parent[nxt] = cell
                    heapq.heappush(heap, (ng + heuristic(nxt, g), ng, nxt))
    if g not in parent:
        return None
    cells = []
    while g is not None:
        cells.append(g)
        g = parent[g]
    return [Pose2D(*costmap.map_to_world(*c)) for c in reversed(cells)]
