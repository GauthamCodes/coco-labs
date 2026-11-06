"""
Your local controller (coco.algorithm.v1).

control(state, scan, path, ctx) -> Twist          (called every tick, ctx.dt = 0.1 s)

  state  state.pose (Pose2D: where the robot believes it is, map frame),
         state.twist (current velocity), state.goal (Pose2D), state.stamp
  scan   sensor_msgs/LaserScan in the LiDAR's frame: scan.ranges, scan.angles(),
         scan.range_min / range_max; the LiDAR sits at ctx.robot.lidar_mount
  path   the global plan: a list of Pose2D from where the robot was to the goal
  ctx    ctx.robot.max_linear / max_angular, ctx.memory (kept between ticks),
         ctx.emit('candidate', points=[(x, y), ...], cost=..., valid=True)

Return Twist.of(v, w). Raise NoValidControl when nothing is safe. The runner stops
the robot at the goal for you. The full reference: docs/v2/r2/API.md.
"""
import math

from coco_lab.api import Twist


def control(state, scan, path, ctx):
    # a start: turn towards the goal, then drive at it (it ignores the path and the walls)
    p, g = state.pose, path[-1]
    bearing = math.atan2(g.y - p.y, g.x - p.x)
    err = math.atan2(math.sin(bearing - p.theta), math.cos(bearing - p.theta))
    v = 0.2 if abs(err) < 0.5 else 0.0
    return Twist.of(v, 1.5 * err)
