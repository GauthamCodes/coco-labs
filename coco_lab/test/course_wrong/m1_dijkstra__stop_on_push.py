# R4.7 wrong solution for m1-dijkstra: stops when the goal is first pushed, not when it is popped
"""
Builder exercise: implement Dijkstra's algorithm. (Reference solution.)

Dijkstra keeps a priority queue of cells ordered by g, the cheapest cost found so far from
the start. It always takes out the cheapest cell, marks it done, and "relaxes" its
neighbours: if going through this cell makes a neighbour cheaper, remember the new cost and
the parent, and push the neighbour.

Costs here are geometric: a straight step costs 1 cell, a diagonal step sqrt(2). A cell with
cost >= 253 (inscribed or lethal) cannot hold the robot's centre, and a diagonal step may
not cut a blocked corner.
"""
import heapq
import math

from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D

MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0)),
         (-1, 1, math.sqrt(2.0)), (-1, -1, math.sqrt(2.0))]


def blocked(costmap, cell):
    return costmap.cost(*cell) >= INSCRIBED_INFLATED_OBSTACLE


def neighbours(costmap, cell):
    """The free neighbours of a cell and the length of the step to each."""
    for dx, dy, length in MOVES:
        nxt = (cell[0] + dx, cell[1] + dy)
        if blocked(costmap, nxt):
            continue
        if dx and dy and (blocked(costmap, (cell[0] + dx, cell[1]))
                          or blocked(costmap, (cell[0], cell[1] + dy))):
            continue
        yield nxt, length


def plan(costmap, start, goal, ctx):
    s = costmap.world_to_map(start.x, start.y)
    g = costmap.world_to_map(goal.x, goal.y)
    heap = [(0.0, s)]
    best = {s: 0.0}
    parent = {s: None}
    done = set()
    while heap:
        gc, cell = heapq.heappop(heap)
        if cell in done:
            continue
        done.add(cell)
        x, y = costmap.map_to_world(*cell)
        ctx.emit('expand', x=x, y=y)
        ctx.step()
        if cell == g:
            break
        for nxt, length in neighbours(costmap, cell):
            ng = gc + length
            if ng < best.get(nxt, math.inf):
                best[nxt] = ng
                parent[nxt] = cell
                heapq.heappush(heap, (ng, nxt))
                if nxt == g:
                    heap = []
                    break
    if g not in parent:
        return None
    cells = []
    while g is not None:
        cells.append(g)
        g = parent[g]
    return [Pose2D(*costmap.map_to_world(*c)) for c in reversed(cells)]
