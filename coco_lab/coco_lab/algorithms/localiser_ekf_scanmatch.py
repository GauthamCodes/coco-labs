# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
EKF with scan matching: a COCO Lab built-in localiser (R6.B2, coco.algorithm.v1).

Predict: compose the wheel odometry's motion onto the estimate (x, y, yaw) and grow the covariance by an
odometry noise that scales with the motion. Correct: a CORRELATIVE SCAN MATCH (after Olson 2009) -- every pose on
a small grid around the prediction (+-window_m, +-window_rad) scores how well the scan's beam endpoints land on
the map's walls (a likelihood field: exp(-d^2 / 2 sigma^2), d = the endpoint's distance to the nearest wall);
the best pose is the measurement, and the score-weighted spread of the candidates is its covariance. A
Kalman update fuses the two (the measurement is the pose itself: H = I).

What it is, stated: a TRACKER. It needs a start pose (ctx.initial_pose) and corrects within the search window:
it cannot localise globally, nor recover from a kidnap larger than the window (no multi-hypothesis); its
reported covariance is the filter's own. Deterministic: no randomness at all.

Parameters (ctx.params): beams (36), window_m (0.3), window_rad (0.15), step_m (0.05), step_rad (0.05),
sigma_m (0.15), min_move (0.05), odom_noise (0.05: per metre / radian moved).
"""
import math
from collections import deque

from coco_lab.api import PoseWithCovariance, yaw_of


def wrap(a):
    """Return a in (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def distance_field(grid, max_cells=40):
    """Return the distance (cells; 8-neighbour approximation) from every cell to the nearest wall."""
    w, h = grid.info.width, grid.info.height
    dist = [max_cells] * (w * h)
    q = deque()
    for i, v in enumerate(grid.data):
        if v != 0:
            dist[i] = 0
            q.append(i)
    while q:
        i = q.popleft()
        d = dist[i] + 1
        if d >= max_cells:
            continue
        x, y = i % w, i // w
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if (dx or dy) and 0 <= nx < w and 0 <= ny < h and dist[ny * w + nx] > d:
                    dist[ny * w + nx] = d
                    q.append(ny * w + nx)
    return dist


def score(pose, beams, field, info, sigma):
    """Return how well the beams, cast from pose, land on walls (sum of exp(-d^2 / 2 sigma^2))."""
    x, y, t = pose
    res, w, h = info.resolution, info.width, info.height
    ox, oy = info.origin.position.x, info.origin.position.y
    two_s2 = 2.0 * sigma * sigma
    total = 0.0
    for r, a in beams:
        ex, ey = x + r * math.cos(t + a), y + r * math.sin(t + a)
        cx, cy = int(math.floor((ex - ox) / res)), int(math.floor((ey - oy) / res))
        d = field[cy * w + cx] * res if 0 <= cx < w and 0 <= cy < h else 2.0
        total += math.exp(-(d * d) / two_s2)
    return total


def inv3(m):
    """Return the inverse of a 3 x 3 matrix (rows)."""
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def mul(a, b):
    """Return the product of two 3 x 3 matrices."""
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


def localise(odom, scan, grid, ctx):
    m, p = ctx.memory, ctx.params
    o = odom.pose.pose
    now = (o.position.x, o.position.y, yaw_of(o.orientation))
    if 'mu' not in m:
        p0 = ctx.initial_pose
        m['mu'], m['last'] = [p0.x, p0.y, p0.theta], now
        m['P'] = [[0.01, 0.0, 0.0], [0.0, 0.01, 0.0], [0.0, 0.0, 0.0025]]
        m['field'] = distance_field(grid)
        return PoseWithCovariance.of(p0.x, p0.y, p0.theta, 0.01, 0.01, 0.0025)
    lx, ly, lt = m['last']
    dx, dy = now[0] - lx, now[1] - ly
    trans, rot = math.sqrt(dx * dx + dy * dy), wrap(now[2] - lt)
    mu, P = m['mu'], m['P']
    if trans < float(p.get('min_move', 0.05)) and abs(rot) < float(p.get('min_move', 0.05)):
        return PoseWithCovariance.of(mu[0], mu[1], mu[2], P[0][0], P[1][1], P[2][2], P[0][1])
    m['last'] = now
    # predict: the odometry's motion, in the robot's frame, composed onto the estimate
    c, s = math.cos(-lt), math.sin(-lt)
    fx, fy = c * dx - s * dy, s * dx + c * dy
    c, s = math.cos(mu[2]), math.sin(mu[2])
    mu = [mu[0] + c * fx - s * fy, mu[1] + s * fx + c * fy, wrap(mu[2] + rot)]
    k = float(p.get('odom_noise', 0.05))
    qxy, qt = k * trans + 0.005, k * abs(rot) + k * trans + 0.002
    P = [[P[0][0] + qxy * qxy, P[0][1], P[0][2]], [P[1][0], P[1][1] + qxy * qxy, P[1][2]],
         [P[2][0], P[2][1], P[2][2] + qt * qt]]
    # correct: the correlative scan match around the prediction
    n = int(p.get('beams', 36))
    step = max(1, len(scan.ranges) // n)
    beams = [(r, a) for r, a in list(zip(scan.ranges, scan.angles()))[::step]
             if scan.range_min < r < scan.range_max]
    if len(beams) >= 6:
        wm, wr = float(p.get('window_m', 0.3)), float(p.get('window_rad', 0.15))
        sm, sr = float(p.get('step_m', 0.05)), float(p.get('step_rad', 0.05))
        sigma = float(p.get('sigma_m', 0.15))
        nm, nr = int(round(wm / sm)), int(round(wr / sr))
        cands = []
        for i in range(-nm, nm + 1):
            for j in range(-nm, nm + 1):
                for q in range(-nr, nr + 1):
                    ctx.step()
                    pose = (mu[0] + i * sm, mu[1] + j * sm, wrap(mu[2] + q * sr))
                    cands.append((score(pose, beams, m['field'], grid.info, sigma), pose))
        best = max(cands, key=lambda c_: c_[0])
        # the measurement's covariance: the spread of the candidates, weighted by exp(score - best)
        ws = [(math.exp(sc - best[0]), pz) for sc, pz in cands]
        tw = sum(w for w, _ in ws)
        z = best[1]
        R = [[0.0] * 3 for _ in range(3)]
        for w, pz in ws:
            e = (pz[0] - z[0], pz[1] - z[1], wrap(pz[2] - z[2]))
            for r_ in range(3):
                for c_ in range(3):
                    R[r_][c_] += w * e[r_] * e[c_] / tw
        R = [[R[r_][c_] + (sm * sm / 12 if r_ == c_ and r_ < 2 else (sr * sr / 12 if r_ == c_ else 0.0))
              for c_ in range(3)] for r_ in range(3)]
        S = [[P[r_][c_] + R[r_][c_] for c_ in range(3)] for r_ in range(3)]
        K = mul(P, inv3(S))
        y = (z[0] - mu[0], z[1] - mu[1], wrap(z[2] - mu[2]))
        mu = [mu[0] + sum(K[0][k_] * y[k_] for k_ in range(3)),
              mu[1] + sum(K[1][k_] * y[k_] for k_ in range(3)),
              wrap(mu[2] + sum(K[2][k_] * y[k_] for k_ in range(3)))]
        ik = [[(1.0 if r_ == c_ else 0.0) - K[r_][c_] for c_ in range(3)] for r_ in range(3)]
        P = mul(ik, P)
        P = [[(P[r_][c_] + P[c_][r_]) / 2 for c_ in range(3)] for r_ in range(3)]   # keep it symmetric
        ctx.emit('estimate', x=mu[0], y=mu[1], theta=mu[2])
    m['mu'], m['P'] = mu, P
    return PoseWithCovariance.of(mu[0], mu[1], mu[2], P[0][0], P[1][1], P[2][2], P[0][1])
