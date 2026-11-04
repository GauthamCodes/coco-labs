"""
Try it yourself: tune DWA (the Dynamic Window Approach).

Every tick DWA tries a fan of (speed, turn) pairs the motors can reach within one tick,
imagines driving each for HORIZON seconds, throws away those that hit something, and
scores the rest with weighted critics. The weights ARE the behaviour:

  heading    face the point ahead on the path
  clearance  stay away from what the LiDAR sees
  speed      prefer driving fast
  path       end close to the path ahead

Change WEIGHTS (or set them as experiment parameters user.heading, user.clearance, ...),
run, and watch the candidate fan in the Move lens. Too little clearance: it scrapes
walls. Too much: it refuses doorways. Too little heading: it wanders.
"""
import math

from coco_lab.api import NoValidControl, Twist

WEIGHTS = {'heading': 0.8, 'clearance': 0.6, 'speed': 0.4, 'path': 1.0}
HORIZON = 1.5        # s of imagined driving
V_SAMPLES = 6
W_SAMPLES = 11
LOOKAHEAD = 0.8      # m along the path


def control(state, scan, path, ctx):
    wts = {k: float(ctx.params.get(k, v)) for k, v in WEIGHTS.items()}
    r = ctx.robot
    p = state.pose
    v0, w0 = state.twist.linear.x, state.twist.angular.z
    # the dynamic window: what the motors can reach in one tick
    dv, dw = r.max_linear_accel * ctx.dt, r.max_angular_accel * ctx.dt
    v_lo, v_hi = max(0.0, v0 - dv), min(r.max_linear, v0 + dv)
    w_lo, w_hi = max(-r.max_angular, w0 - dw), min(r.max_angular, w0 + dw)
    # obstacles: scan end points in the map frame, near the robot only
    c, s = math.cos(p.theta), math.sin(p.theta)
    mx, my = r.lidar_mount
    sx, sy = p.x + c * mx - s * my, p.y + s * mx + c * my
    pts = []
    for k, (rng_, a) in enumerate(zip(scan.ranges, scan.angles())):
        if k % 4 == 0 and scan.range_min < rng_ < 1.6:
            pts.append((sx + rng_ * math.cos(p.theta + a), sy + rng_ * math.sin(p.theta + a)))
    # the point to head for: LOOKAHEAD along the path past its nearest point
    if ctx.memory.get('plan') != (path[0].x, path[0].y, len(path)):
        ctx.memory['plan'] = (path[0].x, path[0].y, len(path))
        dense = [(path[0].x, path[0].y)]
        for a, b in zip(path, path[1:]):
            n = max(1, int(math.hypot(b.x - a.x, b.y - a.y) / 0.05))
            dense += [(a.x + (b.x - a.x) * k / n, a.y + (b.y - a.y) * k / n)
                      for k in range(1, n + 1)]
        ctx.memory['dense'], ctx.memory['i'] = dense, 0
    dense, i0 = ctx.memory['dense'], ctx.memory['i']
    i = min(range(i0, min(len(dense), i0 + 80)),
            key=lambda j: math.hypot(dense[j][0] - p.x, dense[j][1] - p.y))
    ctx.memory['i'] = i
    tx, ty = dense[-1]
    for qx, qy in dense[i:]:
        if math.hypot(qx - p.x, qy - p.y) >= LOOKAHEAD:
            tx, ty = qx, qy
            break
    best, choice = -math.inf, None
    steps = int(HORIZON / 0.1)
    for a in range(V_SAMPLES):
        v = v_lo + (v_hi - v_lo) * a / (V_SAMPLES - 1)
        for b in range(W_SAMPLES):
            w = w_lo + (w_hi - w_lo) * b / (W_SAMPLES - 1)
            x, y, th, traj, clear = p.x, p.y, p.theta, [], math.inf
            for t in range(steps):
                x, y, th = x + v * math.cos(th) * 0.1, y + v * math.sin(th) * 0.1, th + w * 0.1
                traj.append((x, y))
                if t % 3 == 2:
                    for ox, oy in pts:
                        d = math.hypot(ox - x, oy - y)
                        if d < clear:
                            clear = d
            valid = clear > r.radius
            score = -math.inf
            if valid:
                bearing = math.atan2(ty - y, tx - x)
                head = 1.0 - abs(math.atan2(math.sin(bearing - th), math.cos(bearing - th))) / math.pi
                score = (wts['heading'] * head + wts['clearance'] * min(clear - r.radius, 1.0)
                         + wts['speed'] * v / r.max_linear
                         - wts['path'] * math.hypot(tx - x, ty - y))
                if score > best:
                    best, choice = score, (v, w)
            ctx.emit('candidate', points=traj[2::3], cost=-score if valid else 0.0, valid=valid)
    if choice is None:
        raise NoValidControl('every trajectory hits something')
    return Twist.of(*choice)
