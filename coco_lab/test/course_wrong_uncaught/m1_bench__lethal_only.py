# R4.7 NOT caught by m1-bench: blocks only lethal cells (254), so paths clip inscribed ones
"""
A* on Nav2's costmap: a starter planner for COCO Lab (coco.algorithm.v1).

plan() gets the global costmap (nav2_msgs/Costmap: raw costs 0..255), the start and
the goal (map-frame poses, already at the centres of free cells) and ctx. It returns
the path as a list of Pose2D from start to goal, or None when there is none.

Run it in the Studio, then change something -- the heuristic, the cost term, the
neighbours -- and watch the expansions change.
"""
import heapq
import math

from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, LETHAL_OBSTACLE, Pose2D

# the 8 moves: (dx, dy, length in cells)
MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0)),
         (-1, 1, math.sqrt(2.0)), (-1, -1, math.sqrt(2.0))]


def heuristic(a, b):
    """Octile distance between two cells: exact on an empty 8-connected grid."""
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2.0) - 1.0) * min(dx, dy)


def plan(costmap, start, goal, ctx):
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)
    # how much a cell's inflation cost adds to stepping into it (ctx.params can change it)
    weight = ctx.params.get('cost_weight', 2.0)

    open_heap = [(heuristic(s, g), 0.0, s)]   # (f, g, cell)
    g_cost = {s: 0.0}
    parent = {s: None}
    closed = set()
    while open_heap:
        f, gc, cell = heapq.heappop(open_heap)
        if cell in closed:
            continue                     # a stale entry: this cell was reached more cheaply
        closed.add(cell)
        x, y = costmap.map_to_world(*cell)
        ctx.emit('expand', x=x, y=y)     # drawn by the glass-box search layer
        ctx.step()                       # counts against the call's step budget
        if cell == g:
            break
        for dx, dy, length in MOVES:
            nxt = (cell[0] + dx, cell[1] + dy)
            cost = costmap.cost(*nxt)    # off the map reads as unknown (255)
            if cost >= LETHAL_OBSTACLE:
                continue                 # the robot's centre cannot be there
            if dx and dy and (costmap.cost(cell[0] + dx, cell[1]) >= INSCRIBED_INFLATED_OBSTACLE
                              or costmap.cost(cell[0], cell[1] + dy) >= INSCRIBED_INFLATED_OBSTACLE):
                continue                 # no cutting a blocked corner
            new_g = gc + length * (1.0 + weight * cost / 252.0)
            if new_g < g_cost.get(nxt, math.inf):
                g_cost[nxt] = new_g
                parent[nxt] = cell
                heapq.heappush(open_heap, (new_g + heuristic(nxt, g), new_g, nxt))
                px, py = costmap.map_to_world(*nxt)
                ctx.emit('push', x=px, y=py)
    if g not in parent:
        return None
    # walk back from the goal, then turn the cells into poses
    cells = []
    cell = g
    while cell is not None:
        cells.append(cell)
        cell = parent[cell]
    cells.reverse()
    return [Pose2D(*costmap.map_to_world(*c)) for c in cells]
