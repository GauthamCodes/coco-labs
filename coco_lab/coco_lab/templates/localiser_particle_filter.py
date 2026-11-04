"""
A minimal particle filter (Monte Carlo localisation) for COCO Lab (coco.algorithm.v1).

localise() is called every tick with the wheel odometry (odom frame), the LiDAR scan
and the map. It returns where it thinks the robot is (map frame) with a covariance.
The estimate becomes COCO's belief: the planner and controller drive from it.

Each particle is a guess of the pose. When the wheels have moved, every particle
moves the same way (plus noise), then is weighed by how well the scan, cast from it,
lands on the map's walls; then the cloud is resampled towards the good guesses.
"""
import math
from collections import deque

from coco_lab.api import PoseWithCovariance, yaw_of

N = 200              # particles (ctx.params['particles'] overrides)
BEAMS = 24           # beams used per update
SIGMA = 0.2          # m: how far a beam end may miss a wall and still count
MIN_MOVE = 0.10      # m / rad of odometry between updates
NOISE = (0.05, 0.05, 0.02)   # per update: x, y (m), yaw (rad)


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def distance_field(grid, max_cells=20):
    """Distance (cells, 8-neighbour approximation) from every cell to the nearest wall."""
    w, h = grid.info.width, grid.info.height
    dist = [max_cells] * (w * h)
    q = deque()
    for i, v in enumerate(grid.data):
        if v != 0:                       # occupied or unknown
            dist[i] = 0
            q.append(i)
    while q:
        i = q.popleft()
        d = dist[i] + 1
        if d >= max_cells:
            continue
        x, y = i % w, i // w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and dist[ny * w + nx] > d:
                dist[ny * w + nx] = d
                q.append(ny * w + nx)
    return dist


def localise(odom, scan, grid, ctx):
    m = ctx.memory
    o = odom.pose.pose
    now = (o.position.x, o.position.y, yaw_of(o.orientation))
    if 'particles' not in m:                       # the first call: start at /initialpose
        p0 = ctx.initial_pose
        n = int(ctx.params.get('particles', N))
        m['particles'] = [(p0.x + ctx.rng.gauss(0, 0.1), p0.y + ctx.rng.gauss(0, 0.1),
                           p0.theta + ctx.rng.gauss(0, 0.05)) for _ in range(n)]
        m['field'] = distance_field(grid)
        m['last'] = now
        m['estimate'] = PoseWithCovariance.of(p0.x, p0.y, p0.theta, 0.01, 0.01, 0.0025)
        return m['estimate']
    # 1. has the robot moved enough? (as AMCL: update only on motion)
    lx, ly, lth = m['last']
    dx, dy = now[0] - lx, now[1] - ly
    trans = math.hypot(dx, dy)
    if trans < MIN_MOVE and abs(wrap(now[2] - lth)) < MIN_MOVE:
        return m['estimate']
    m['last'] = now
    rot1 = wrap(math.atan2(dy, dx) - lth) if trans > 1e-6 else 0.0
    rot2 = wrap(now[2] - lth - rot1)
    # 2. motion: move every particle by the odometry, plus noise
    moved = []
    for x, y, th in m['particles']:
        r1 = rot1 + ctx.rng.gauss(0, NOISE[2])
        t = trans + ctx.rng.gauss(0, NOISE[0])
        th1 = th + r1
        moved.append((x + t * math.cos(th1), y + t * math.sin(th1),
                      wrap(th1 + rot2 + ctx.rng.gauss(0, NOISE[2]))))
    # 3. measurement: where would each beam end, and how close is that to a wall?
    info = grid.info
    res, ox, oy, w = info.resolution, info.origin.position.x, info.origin.position.y, info.width
    field = m['field']
    mx_, my_ = ctx.robot.lidar_mount
    step = max(1, len(scan.ranges) // BEAMS)
    beams = [(r, a) for r, a in list(zip(scan.ranges, scan.angles()))[::step]
             if scan.range_min < r < scan.range_max]
    logw = []
    for x, y, th in moved:
        c, s = math.cos(th), math.sin(th)
        sx, sy = x + c * mx_ - s * my_, y + s * mx_ + c * my_
        total = 0.0
        for r, a in beams:
            ex, ey = sx + r * math.cos(th + a), sy + r * math.sin(th + a)
            cx, cy = int((ex - ox) / res), int((ey - oy) / res)
            if 0 <= cx < w and 0 <= cy < info.height:
                d = field[cy * w + cx] * res
            else:
                d = 1.0
            total += math.log(0.9 * math.exp(-d * d / (2 * SIGMA * SIGMA)) + 0.1)
        logw.append(total)
    top = max(logw)
    wts = [math.exp(v - top) for v in logw]
    s = sum(wts)
    wts = [v / s for v in wts]
    ctx.emit('particles', x=[p[0] for p in moved], y=[p[1] for p in moved],
             theta=[p[2] for p in moved], weight=wts)
    # 4. resample (low variance): keep good guesses, drop bad ones
    n = len(moved)
    out, r, c, i = [], ctx.rng.random() / n, wts[0], 0
    for k in range(n):
        u = r + k / n
        while u > c and i < n - 1:
            i += 1
            c += wts[i]
        out.append(moved[i])
    m['particles'] = out
    # 5. the estimate: the mean (and the spread) of the weighted cloud
    mx = sum(wi * p[0] for wi, p in zip(wts, moved))
    my = sum(wi * p[1] for wi, p in zip(wts, moved))
    mt = math.atan2(sum(wi * math.sin(p[2]) for wi, p in zip(wts, moved)),
                    sum(wi * math.cos(p[2]) for wi, p in zip(wts, moved)))
    vx = sum(wi * (p[0] - mx) ** 2 for wi, p in zip(wts, moved)) + 1e-6
    vy = sum(wi * (p[1] - my) ** 2 for wi, p in zip(wts, moved)) + 1e-6
    cxy = sum(wi * (p[0] - mx) * (p[1] - my) for wi, p in zip(wts, moved))
    cxy = max(-0.99 * math.sqrt(vx * vy), min(0.99 * math.sqrt(vx * vy), cxy))
    vt = sum(wi * wrap(p[2] - mt) ** 2 for wi, p in zip(wts, moved)) + 1e-6
    ctx.emit('estimate', x=mx, y=my, theta=mt)
    m['estimate'] = PoseWithCovariance.of(mx, my, mt, vx, vy, vt, cxy)
    return m['estimate']
