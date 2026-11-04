"""
Pure pursuit: a starter local controller for COCO Lab (coco.algorithm.v1).

control() is called every tick (0.1 s) with the robot's state (believed pose, current
velocity, goal), the LiDAR scan and the global path. It returns a Twist: linear.x
(m/s) and angular.z (rad/s). The runner checks the goal (0.25 m) and progress for you,
exactly as Nav2's controller server does, and clamps anything COCO cannot do.

The idea: pick the point on the path one "lookahead" ahead of the robot and drive the
circular arc that passes through it. Short lookahead: tight tracking, wobbly; long
lookahead: smooth, cuts corners.
"""
import math

from coco_lab.api import NoValidControl, Pose2D, Twist

LOOKAHEAD = 0.45      # m
SPEED = 0.25          # m/s, cruising
ROTATE_FIRST = 1.0    # rad: turn on the spot when the lookahead is further off than this
STOP_RANGE = 0.30     # m: anything this close in front of the LiDAR stops forward motion


def densify(path, step=0.05):
    """The path as points every ``step`` metres (the plan may give only its corners)."""
    pts = [(path[0].x, path[0].y)]
    for a, b in zip(path, path[1:]):
        n = max(1, int(math.hypot(b.x - a.x, b.y - a.y) / step))
        for k in range(1, n + 1):
            pts.append((a.x + (b.x - a.x) * k / n, a.y + (b.y - a.y) * k / n))
    return [Pose2D(x, y) for x, y in pts]


def control(state, scan, path, ctx):
    p = state.pose
    if not path:
        raise NoValidControl('no path')
    # 1. the nearest path point (never going backwards along the path)
    i = ctx.memory.get('i', 0)
    if ctx.memory.get('path_start') != (path[0].x, path[0].y, len(path)):
        i = 0                                   # a new plan
        ctx.memory['path_start'] = (path[0].x, path[0].y, len(path))
        ctx.memory['dense'] = densify(path)
    path = ctx.memory['dense']
    best = math.inf
    for j in range(i, min(len(path), i + 80)):
        d = math.hypot(path[j].x - p.x, path[j].y - p.y)
        if d < best:
            best, i = d, j
    ctx.memory['i'] = i
    # 2. the lookahead point: the first path point at least LOOKAHEAD away
    target = path[-1]
    for q in path[i:]:
        if math.hypot(q.x - p.x, q.y - p.y) >= LOOKAHEAD:
            target = q
            break
    ctx.emit('lookahead', x=target.x, y=target.y)
    # 3. the target in the robot's frame
    dx, dy = target.x - p.x, target.y - p.y
    c, s = math.cos(-p.theta), math.sin(-p.theta)
    lx, ly = c * dx - s * dy, s * dx + c * dy
    alpha = math.atan2(ly, lx)
    if abs(alpha) > ROTATE_FIRST:
        w = math.copysign(min(ctx.robot.max_angular, 0.8), alpha)
        return Twist.of(0.0, w)
    # 4. the arc through it: curvature k = 2 y / L^2
    L2 = lx * lx + ly * ly
    k = 2.0 * ly / L2 if L2 > 1e-9 else 0.0
    goal_dist = math.hypot(path[-1].x - p.x, path[-1].y - p.y)
    v = min(SPEED, ctx.robot.max_linear, 0.15 + goal_dist)   # slow down near the goal
    w = v * k
    if abs(w) > ctx.robot.max_angular:       # too tight: slow down instead of saturating
        v = v * ctx.robot.max_angular / abs(w)
        w = math.copysign(ctx.robot.max_angular, w)
    # 5. something right in front of the LiDAR: stop going forward
    for r, a in zip(scan.ranges, scan.angles()):
        if scan.range_min < r < STOP_RANGE and abs(a) < 0.5:
            v = 0.0
            break
    # show the arc we chose (one candidate) in the Move lens
    pts, x, y, th = [], p.x, p.y, p.theta
    for _ in range(10):
        x, y, th = x + v * math.cos(th) * 0.1, y + v * math.sin(th) * 0.1, th + w * 0.1
        pts.append((x, y))
    ctx.emit('candidate', points=pts, cost=0.0, valid=True)
    return Twist.of(v, w)
