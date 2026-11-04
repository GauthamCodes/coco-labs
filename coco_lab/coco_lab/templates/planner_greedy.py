"""
Greedy best-first search: always expand the cell that looks closest to the goal.

Fast, few expansions -- and not optimal: watch it hug walls and take the long way
round an obstacle the heuristic cannot see. Compare it with A* in the Studio.
"""
import heapq
import math

from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D


def plan(costmap, start, goal, ctx):
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)

    def h(c):
        return math.hypot(c[0] - g[0], c[1] - g[1])

    heap = [(h(s), s)]
    parent = {s: None}
    while heap:
        _, cell = heapq.heappop(heap)
        x, y = costmap.map_to_world(*cell)
        ctx.emit('expand', x=x, y=y)
        ctx.step()
        if cell == g:
            break
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt in parent or costmap.cost(*nxt) >= INSCRIBED_INFLATED_OBSTACLE:
                    continue
                if dx and dy and (costmap.cost(cell[0] + dx, cell[1]) >= INSCRIBED_INFLATED_OBSTACLE
                                  or costmap.cost(cell[0], cell[1] + dy) >= INSCRIBED_INFLATED_OBSTACLE):
                    continue
                parent[nxt] = cell
                heapq.heappush(heap, (h(nxt), nxt))
    if g not in parent:
        return None
    cells = []
    while g is not None:
        cells.append(g)
        g = parent[g]
    return [Pose2D(*costmap.map_to_world(*c)) for c in reversed(cells)]
