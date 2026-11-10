"""
Your planner (coco.algorithm.v1).

plan(costmap, start, goal, ctx) -> list[Pose2D] | None

  costmap  nav2_msgs/Costmap: costmap.width, .height, .resolution, .data (raw costs
           0..255; 253 inscribed, 254 lethal, 255 unknown); costmap.cost(mx, my),
           costmap.world_to_map(x, y) -> (mx, my) or None, costmap.map_to_world(mx, my)
  start    Pose2D (x, y, theta) at the centre of a free cell, map frame (m)
  goal     Pose2D at the centre of a free cell
  ctx      ctx.rng (seeded), ctx.robot (radius, limits), ctx.params, ctx.step(),
           ctx.emit('expand', x=..., y=...) to show your thinking

Return the poses from the start cell to the goal cell, every one on a cell with cost
below 253 (the path between two non-adjacent poses must be clear too), or None.
The full reference: docs/v2/r2/API.md.
"""
from coco_lab.api import Pose2D


def plan(costmap, start, goal, ctx):
    # a straight line works only when nothing is in the way: replace this
    return [Pose2D(start.x, start.y), Pose2D(goal.x, goal.y)]
