"""
Your localiser (coco.algorithm.v1).

localise(odom, scan, map, ctx) -> PoseWithCovariance       (called every tick)

  odom  nav_msgs/Odometry: odom.pose.pose (wheel odometry in the odom frame; it drifts),
        odom.twist.twist (velocity)
  scan  sensor_msgs/LaserScan (the LiDAR's frame; mount at ctx.robot.lidar_mount)
  map   nav_msgs/OccupancyGrid: map.info (resolution, width, height, origin),
        map.data (0 free, 100 occupied, -1 unknown), map.world_to_map(x, y)
  ctx   ctx.initial_pose (where the robot starts, map frame), ctx.memory, ctx.rng,
        ctx.emit('particles', x=[...], y=[...], theta=[...], weight=[...])

Return PoseWithCovariance.of(x, y, theta, var_x, var_y, var_theta) in the map frame.
This start is dead reckoning: odometry alone, so its error only grows. Use the scan.
The full reference: docs/v2/r2/API.md.
"""
import math

from coco_lab.api import PoseWithCovariance, yaw_of


def localise(odom, scan, map, ctx):
    o = odom.pose.pose
    x, y, th = o.position.x, o.position.y, yaw_of(o.orientation)
    if 'odom0' not in ctx.memory:
        ctx.memory['odom0'] = (x, y, th)
    x0, y0, th0 = ctx.memory['odom0']
    p0 = ctx.initial_pose
    # odometry since the start, turned into the map frame at the initial pose
    c, s = math.cos(p0.theta - th0), math.sin(p0.theta - th0)
    dx, dy = x - x0, y - y0
    mx, my = p0.x + c * dx - s * dy, p0.y + s * dx + c * dy
    travelled = math.hypot(dx, dy)
    var = 0.01 + 0.05 * travelled          # an honest guess: it grows with distance
    return PoseWithCovariance.of(mx, my, p0.theta + th - th0, var, var, 0.01 + 0.02 * travelled)
