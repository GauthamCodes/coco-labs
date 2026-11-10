# R4.7 wrong solution for m1-dijkstra: ignores the costmap: geometric length only
"""
Builder exercise: implement Dijkstra's algorithm. (Reference solution.)

Dijkstra keeps a priority queue of cells ordered by g, the cheapest cost found so far from
the start. It always takes out the cheapest cell, marks it done, and "relaxes" its
neighbours: if going through this cell makes a neighbour cheaper, remember the new cost and
the parent, and push the neighbour.

Costs come from the costmap, as in Nav2: stepping into a cell costs the step's length (1 cell
straight, sqrt(2) diagonal) times (1 + WEIGHT x the cell's cost / 252), so a step beside a wall
costs more than one in the open. step_cost() computes it. A cell with cost >= 253 (inscribed or
lethal) cannot hold the robot's centre, and a diagonal step may not cut a blocked corner.
"""
import heapq
import math

from coco_lab.api import INSCRIBED_INFLATED_OBSTACLE, Pose2D

MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0)),
         (-1, 1, math.sqrt(2.0)), (-1, -1, math.sqrt(2.0))]


WEIGHT = 2.0     # how much a cell's inflation cost adds to stepping into it


def step_cost(costmap, nxt, length):
    """What stepping into cell nxt costs: its length, made dearer near obstacles."""
    return length * (1.0 + WEIGHT * costmap.cost(*nxt) / 252.0)


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
    if g not in parent:
        return None
    cells = []
    while g is not None:
        cells.append(g)
        g = parent[g]
    return [Pose2D(*costmap.map_to_world(*c)) for c in reversed(cells)]
