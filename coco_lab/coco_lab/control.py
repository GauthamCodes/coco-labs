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
Local control: three TEACHING implementations (M2.5; evidence class MODEL).

None of these is Nav2's code. Each is written after the controller Lab 5
measured in Gazebo, with Lab 5's configuration where the model has the
same knob (``coco_lab_ros/config/nav2_move_overlay.yaml`` and the mission's
``gazebo_models/config/nav2_params.yaml``), and each is labelled MODEL
wherever it is shown. What each one simplifies is listed here and nowhere
hidden.

**The local window** (:class:`LocalWindow`) is the mission's local
costmap as the model has it: a 3 x 3 m window at 0.05 m centred on the
robot's BELIEVED pose, marked only from the current LiDAR scan (the
mission's local costmap has obstacle layers and no static layer) within
2.5 m, inflated as Nav2 inflates -- lethal at a mark, inscribed (253)
within (robot_radius + padding) cos(pi/16) = 0.255 m, then
252 exp(-65 (d - 0.255)) out to 0.5 m. Simplified: it is rebuilt from
each scan (Nav2 keeps marks until a ray clears them), so what the LiDAR's
240 degrees do not see behind the robot is free.

**The path in the window** (:class:`PathTracker`): Nav2 finds the path
pose nearest the robot (searching forward from the last one) and keeps the
following poses while they lie in the local costmap. If none does -- the
robot believes itself far from its path -- the controller is given an
empty path and FollowPath fails with INVALID_PATH (103). That is Lab 5's
run-15 mechanism (``docs/labs/LAB5_MOVE.md`` 4.3).

**DWA** (:class:`DWA`, after DWB): samples (v, w) over the window of
velocities reachable in one 0.1 s period (DWB's accelerations 3.0 / -2.5
m/s^2, 3.2 rad/s^2), rolls each out for DWB's 1.5 s, refuses a trajectory
that touches an inscribed or lethal cell ("collision") or leaves the
window ("outside_window"), and scores the rest with DWB's critics and
scales (BaseObstacle 8, PathDist 32, GoalDist 24, PathAlign 32, GoalAlign
24; distances in cells, as DWB measures them). Simplified: 11 x 21
samples (DWB: 20 x 40, 819 measured), no RotateToGoal, Oscillation or
twirling critics, BaseObstacle as the trajectory's highest cost.

**RPP** (:class:`RPP`, after Regulated Pure Pursuit): Lab 5's parameters
-- lookahead 0.6 m, 0.3 m/s, rotate to heading beyond 0.785 rad at 1.0
rad/s, curvature regulation below a 0.9 m radius (not below 0.25 m/s),
approach scaling inside 0.6 m, and collision detection along the
commanded arc for up to 1.0 s or the carrot, whichever is nearer: a
collision ahead is "collision_ahead", no valid control. One candidate per
cycle (the arc it would drive).

**MPPI** (:class:`MPPI`): samples control sequences around the last
optimum (vx sigma 0.2, wz sigma 0.4), 28 steps of 0.1 s, softmax-weights
them at temperature 0.3, applies the first control and shifts. Critics
after Lab 5's (weights as configured): CostCritic 3.81 (any inscribed or
lethal point, or one outside the window, costs 1e6), GoalCritic 5 within
1.4 m, GoalAngleCritic 3 within 0.5 m, PathFollowCritic 5 and
PathAlignCritic 14 and PathAngleCritic 2 farther out. Simplified: 128
samples (Lab 5: 2,000), no gamma term, ConstraintCritic and
PreferForwardCritic omitted (the samples are clipped to the limits and
never reverse, so both would be 0). No valid control when every sample
collides.
"""

from dataclasses import asdict, dataclass, field
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .sketch import edt, step_pose, wrap

LETHAL = 254
INSCRIBED = 253
#: off the window: a trajectory point the local costmap cannot price
OFF = -1
#: MPPI's collision cost (Lab 5's ``collision_cost``)
COLLISION_COST = 1e6

Pose = Tuple[float, float, float]
Point = Tuple[float, float]


@dataclass(frozen=True)
class WindowParams:
    """The local costmap the model builds; every field after the mission's."""

    size: float = 3.0
    resolution: float = 0.05
    robot_radius: float = 0.25
    footprint_padding: float = 0.01
    inflation_radius: float = 0.5
    cost_scaling_factor: float = 65.0
    #: obstacle layer marking range (m)
    mark_range: float = 2.5

    @property
    def inscribed(self) -> float:
        """Nav2's inscribed radius: the apothem of a padded 16-gon."""
        return (self.robot_radius + self.footprint_padding) * \
            math.cos(math.pi / 16)


class LocalWindow:
    """The rolling local costmap at one cycle, plus a path-distance field."""

    def __init__(self, belief: Pose, ranges: Sequence[float],
                 angles: Sequence[float], mount: Tuple[float, float, float],
                 path: Sequence[Point], params: WindowParams = WindowParams()):
        """Mark the scan, inflate, and measure every cell's path distance."""
        p = self.params = params
        r = p.resolution
        self.n = n = int(round(p.size / r))
        self.ox = math.floor((belief[0] - p.size / 2) / r) * r
        self.oy = math.floor((belief[1] - p.size / 2) / r) * r
        c, s = math.cos(belief[2]), math.sin(belief[2])
        sx = belief[0] + c * mount[0] - s * mount[1]
        sy = belief[1] + s * mount[0] + c * mount[1]
        sth = belief[2] + mount[2]
        marks = [False] * (n * n)
        self.marks = 0
        for a, z in zip(angles, ranges):
            if not (z <= p.mark_range):
                continue
            i = self.index(sx + z * math.cos(sth + a), sy + z * math.sin(sth + a))
            if i >= 0 and not marks[i]:
                marks[i] = True
                self.marks += 1
        ins, infl, k = p.inscribed, p.inflation_radius, p.cost_scaling_factor
        cost = bytearray(n * n)
        for i, d in enumerate(edt(marks, n, n)):
            d *= r
            if d == 0.0:
                cost[i] = LETHAL
            elif d <= ins:
                cost[i] = INSCRIBED
            elif d <= infl:
                cost[i] = int((INSCRIBED - 1) * math.exp(-k * (d - ins)))
        self.cost_grid = cost
        self._path = path
        self._path_dist = False  # measured on first use (RPP never asks)

    @property
    def path_dist(self):
        """Every cell's distance (cells) to the path; None if none is in."""
        if self._path_dist is False:
            n = self.n
            on = [False] * (n * n)
            for (x, y) in densify(self._path, self.params.resolution):
                i = self.index(x, y)
                if i >= 0:
                    on[i] = True
            self._path_dist = edt(on, n, n) if any(on) else None
        return self._path_dist

    def index(self, x: float, y: float) -> int:
        """Return the row-major cell index of (x, y), or -1 off the window."""
        r = self.params.resolution
        ix = math.floor((x - self.ox) / r)
        iy = math.floor((y - self.oy) / r)
        if 0 <= ix < self.n and 0 <= iy < self.n:
            return ix + iy * self.n
        return -1

    def inside(self, x: float, y: float) -> bool:
        """Return whether (x, y) lies in the window."""
        return self.index(x, y) >= 0

    def cost(self, x: float, y: float) -> int:
        """Return the cell's cost, 0 to 254, or ``OFF`` off the window."""
        i = self.index(x, y)
        return self.cost_grid[i] if i >= 0 else OFF

    def path_cells_to(self, x: float, y: float) -> float:
        """Return the distance (cells) from (x, y) to the path, inf if none."""
        i = self.index(x, y)
        pd = self.path_dist
        if i < 0 or pd is None:
            return math.inf
        return pd[i]


def densify(path: Sequence[Point], step: float) -> List[Point]:
    """Return the polyline with points at most ``step`` apart."""
    out: List[Point] = []
    for a, b in zip(path, path[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(1, int(math.ceil(d / step)))
        for j in range(k):
            out.append((a[0] + (b[0] - a[0]) * j / k,
                        a[1] + (b[1] - a[1]) * j / k))
    if path:
        out.append((path[-1][0], path[-1][1]))
    return out


class PathTracker:
    """A global path, and the part of it a local controller is given."""

    #: Nav2's max_robot_pose_search_dist (m), as a count of 0.05 m points
    SEARCH = 200

    def __init__(self, path: Sequence[Point], goal_yaw: Optional[float] = None,
                 step: float = 0.05):
        """Densify ``path``; the goal is its last point."""
        self.path = densify(path, step)
        self.goal = self.path[-1]
        self.goal_yaw = goal_yaw
        self.i = 0

    def local(self, belief: Pose, window: LocalWindow) -> List[Point]:
        """Advance to the nearest point; return the run of points in window."""
        p = self.path
        best, bi = math.inf, self.i
        for j in range(self.i, min(len(p), self.i + self.SEARCH)):
            d = math.hypot(p[j][0] - belief[0], p[j][1] - belief[1])
            if d < best:
                best, bi = d, j
        self.i = bi
        out = []
        for q in p[bi:]:
            if not window.inside(*q):
                break
            out.append(q)
        return out

    def distance_to(self, x: float, y: float) -> float:
        """Distance (m) from (x, y) to the whole path polyline's points."""
        return min(math.hypot(q[0] - x, q[1] - y) for q in self.path)


@dataclass
class Candidate:
    """One trajectory a controller considered this cycle."""

    v: float
    w: float
    valid: bool
    rejection: str
    cost: float
    scores: List[float]
    traj: List[Point]


@dataclass
class Cycle:
    """What one control cycle decided."""

    status: str  # 'ok', 'invalid_path', 'no_valid', 'collision_ahead'
    v: float = 0.0
    w: float = 0.0
    chosen: int = -1
    candidates: List[Candidate] = field(default_factory=list)
    n_candidates: int = 0
    lookahead: Optional[Point] = None
    #: how many of ALL n_candidates were valid (MPPI sends only some)
    n_valid: int = 0


def normals(rng, n: int) -> List[float]:
    """
    Return ``n`` standard normals: Box-Muller, two per 64-bit draw.

    Each draw's high 32 bits give u1 in (0, 1], the low 32 bits u2 in
    [0, 1). Twice as many normals per draw as ``Rng.gauss`` (MPPI needs
    7,168 a cycle).
    """
    out: List[float] = []
    two_pi = 2.0 * math.pi
    while len(out) < n:
        x = rng.next_u64()
        u1 = ((x >> 32) + 1) / 4294967296.0
        u2 = (x & 0xFFFFFFFF) / 4294967296.0
        r = math.sqrt(-2.0 * math.log(u1))
        out.append(r * math.cos(two_pi * u2))
        out.append(r * math.sin(two_pi * u2))
    return out[:n]


def rollout(pose: Pose, v: float, w: float, steps: int,
            dt: float) -> List[Pose]:
    """Return the poses of constant (v, w) for ``steps`` periods."""
    out = []
    for _ in range(steps):
        pose = step_pose(pose, v, w, dt)
        out.append(pose)
    return out


# -- DWA -----------------------------------------------------------------------

@dataclass(frozen=True)
class DWAParams:
    """DWA's settings (DWB's where the model has the knob)."""

    v_max: float = 0.3
    w_max: float = 1.0
    acc_x: float = 3.0
    decel_x: float = -2.5
    acc_theta: float = 3.2
    period: float = 0.1
    vx_samples: int = 11
    vtheta_samples: int = 21
    sim_time: float = 1.5
    forward_point_distance: float = 0.1
    scales: Tuple[float, ...] = (8.0, 32.0, 24.0, 32.0, 24.0)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        d = asdict(self)
        d['scales'] = list(self.scales)
        return d


class DWA:
    """A dynamic-window velocity sampler after DWB (MODEL)."""

    kind = 'dwa'
    critics = ('base_obstacle', 'path_dist', 'goal_dist', 'path_align',
               'goal_align')

    def __init__(self, params: DWAParams = DWAParams()):
        """Keep the parameters (DWA has no state between cycles)."""
        self.params = params

    def compute(self, belief: Pose, v: float, w: float, window: LocalWindow,
                local: List[Point], dt: float) -> Cycle:
        """Score every sampled (v, w); return the cheapest valid one."""
        if not local:
            return Cycle('invalid_path')
        p = self.params
        res = window.params.resolution
        goal = local[-1]
        v_lo = max(0.0, v + p.decel_x * p.period)
        v_hi = min(p.v_max, v + p.acc_x * p.period)
        w_lo = max(-p.w_max, w - p.acc_theta * p.period)
        w_hi = min(p.w_max, w + p.acc_theta * p.period)
        steps = int(round(p.sim_time / dt))
        cands = []
        best, bi = math.inf, -1
        for a in range(p.vx_samples):
            vs = v_lo + (v_hi - v_lo) * a / (p.vx_samples - 1)
            for b in range(p.vtheta_samples):
                ws = w_lo + (w_hi - w_lo) * b / (p.vtheta_samples - 1)
                poses = rollout(belief, vs, ws, steps, dt)
                rej, worst = '', 0
                for q in poses:
                    c = window.cost(q[0], q[1])
                    if c == OFF:
                        rej = 'outside_window'
                        break
                    if c >= INSCRIBED:
                        rej = 'collision'
                        break
                    worst = max(worst, c)
                traj = [(q[0], q[1]) for q in poses]
                if rej:
                    cands.append(Candidate(vs, ws, False, rej, math.inf,
                                           [], traj))
                    continue
                ex, ey, eth = poses[-1]
                fx = ex + p.forward_point_distance * math.cos(eth)
                fy = ey + p.forward_point_distance * math.sin(eth)
                sc = [float(worst), window.path_cells_to(ex, ey),
                      math.hypot(ex - goal[0], ey - goal[1]) / res,
                      window.path_cells_to(fx, fy),
                      math.hypot(fx - goal[0], fy - goal[1]) / res]
                total = sum(k * s for k, s in zip(p.scales, sc))
                cands.append(Candidate(vs, ws, True, '', total, sc, traj))
                if total < best:
                    best, bi = total, len(cands) - 1
        if bi < 0:
            return Cycle('no_valid', candidates=cands, n_candidates=len(cands))
        c = cands[bi]
        return Cycle('ok', c.v, c.w, bi, cands, len(cands),
                     n_valid=sum(1 for k in cands if k.valid))

    def state_values(self) -> List[float]:
        """DWA keeps nothing between cycles."""
        return []


# -- RPP -----------------------------------------------------------------------

@dataclass(frozen=True)
class RPPParams:
    """Regulated Pure Pursuit's settings: Lab 5's (nav2_move_overlay.yaml)."""

    desired_linear_vel: float = 0.3
    lookahead_dist: float = 0.6
    rotate_to_heading_angular_vel: float = 1.0
    rotate_to_heading_min_angle: float = 0.785
    max_angular_accel: float = 3.2
    regulated_linear_scaling_min_radius: float = 0.9
    regulated_linear_scaling_min_speed: float = 0.25
    approach_velocity_scaling_dist: float = 0.6
    min_approach_linear_velocity: float = 0.05
    max_allowed_time_to_collision_up_to_carrot: float = 1.0

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return asdict(self)


class RPP:
    """A regulated pure-pursuit tracker (MODEL)."""

    kind = 'rpp'
    critics = ()

    def __init__(self, params: RPPParams = RPPParams()):
        """Keep the parameters."""
        self.params = params

    def compute(self, belief: Pose, v: float, w: float, window: LocalWindow,
                local: List[Point], dt: float,
                goal_dist: float = math.inf) -> Cycle:
        """Steer for the carrot; refuse to drive into a collision ahead."""
        if not local:
            return Cycle('invalid_path')
        p = self.params
        x, y, th = belief
        carrot = local[-1]
        for q in local:
            if math.hypot(q[0] - x, q[1] - y) >= p.lookahead_dist:
                carrot = q
                break
        dx, dy = carrot[0] - x, carrot[1] - y
        xr = math.cos(th) * dx + math.sin(th) * dy
        yr = -math.sin(th) * dx + math.cos(th) * dy
        ang = math.atan2(yr, xr)
        if abs(ang) > p.rotate_to_heading_min_angle:
            want = math.copysign(p.rotate_to_heading_angular_vel, ang)
            dw = p.max_angular_accel * dt
            wc = max(w - dw, min(w + dw, want))
            vc = 0.0
        else:
            d2 = xr * xr + yr * yr
            k = 2.0 * yr / d2 if d2 > 1e-12 else 0.0
            vc = p.desired_linear_vel
            if abs(k) > 1e-9:
                radius = 1.0 / abs(k)
                if radius < p.regulated_linear_scaling_min_radius:
                    vc = max(vc * radius /
                             p.regulated_linear_scaling_min_radius,
                             p.regulated_linear_scaling_min_speed)
            if goal_dist < p.approach_velocity_scaling_dist:
                vc = max(vc * goal_dist / p.approach_velocity_scaling_dist,
                         p.min_approach_linear_velocity)
            wc = vc * k
        # collision detection along the commanded arc, up to the carrot
        carrot_d = math.hypot(dx, dy)
        horizon = p.max_allowed_time_to_collision_up_to_carrot
        if vc > 1e-9:
            horizon = min(horizon, carrot_d / vc)
        step = window.params.resolution / max(abs(vc), 1e-9) if vc > 1e-9 \
            else dt
        step = min(step, dt)
        n = max(1, int(math.ceil(horizon / step)))
        poses = rollout(belief, vc, wc, n, horizon / n)
        hit = any(window.cost(q[0], q[1]) >= INSCRIBED for q in poses)
        traj = [(q[0], q[1]) for q in poses]
        cand = Candidate(vc, wc, not hit, 'collision_ahead' if hit else '',
                         0.0 if not hit else math.inf, [], traj)
        if hit:
            return Cycle('collision_ahead', candidates=[cand], n_candidates=1,
                         lookahead=carrot)
        return Cycle('ok', vc, wc, 0, [cand], 1, lookahead=carrot, n_valid=1)

    def state_values(self) -> List[float]:
        """RPP keeps nothing between cycles."""
        return []


# -- MPPI ----------------------------------------------------------------------

@dataclass(frozen=True)
class MPPIParams:
    """MPPI's settings: Lab 5's, except the sample count."""

    batch_size: int = 128
    time_steps: int = 28
    model_dt: float = 0.1
    vx_std: float = 0.2
    wz_std: float = 0.4
    vx_max: float = 0.3
    vx_min: float = 0.0
    wz_max: float = 1.0
    ax_max: float = 3.0
    ax_min: float = -2.5
    az_max: float = 3.2
    temperature: float = 0.3
    weights: Tuple[float, ...] = (3.81, 5.0, 3.0, 5.0, 14.0, 2.0)
    goal_threshold: float = 1.4
    near_threshold: float = 0.5
    max_angle_to_furthest: float = 1.0
    #: how many sampled trajectories the lens is sent per cycle
    emit: int = 24

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        d = asdict(self)
        d['weights'] = list(self.weights)
        return d


class MPPI:
    """A small model-predictive path-integral controller (MODEL)."""

    kind = 'mppi'
    critics = ('cost', 'goal', 'goal_angle', 'path_follow', 'path_align',
               'path_angle')

    def __init__(self, rng, params: MPPIParams = MPPIParams()):
        """Start from a zero control sequence; ``rng`` draws the noise."""
        self.params = params
        self.rng = rng
        self.u = [(0.0, 0.0)] * params.time_steps

    def _clip(self, seq):
        """Clip to the limits, then each step to the accelerations."""
        p = self.params
        vlo, vhi, wm = p.vx_min, p.vx_max, p.wz_max
        up, dn = p.ax_max * p.model_dt, p.ax_min * p.model_dt
        dw = p.az_max * p.model_dt
        out = []
        pv = pw = None
        for v, w in seq:
            v = vlo if v < vlo else vhi if v > vhi else v
            w = -wm if w < -wm else wm if w > wm else w
            if pv is not None:
                v = pv + dn if v < pv + dn else pv + up if v > pv + up else v
                w = pw - dw if w < pw - dw else pw + dw if w > pw + dw else w
            out.append((v, w))
            pv, pw = v, w
        return out

    def _scores(self, poses, window, local, goal, goal_yaw, goal_dist):
        p = self.params
        res = window.params.resolution
        collide, total = False, 0.0
        for q in poses[::2]:
            c = window.cost(q[0], q[1])
            if c == OFF or c >= INSCRIBED:
                collide = True
                break
            total += c
        sc = [COLLISION_COST if collide else
              total / (LETHAL * len(poses[::2])), 0.0, 0.0, 0.0, 0.0, 0.0]
        ex, ey, eth = poses[-1]
        if goal_dist < p.goal_threshold:
            sc[1] = math.hypot(ex - goal[0], ey - goal[1])
        if goal_dist < p.near_threshold and goal_yaw is not None:
            sc[2] = abs(wrap(eth - goal_yaw))
        if goal_dist >= p.goal_threshold:
            j = min(range(len(local)), key=lambda k: math.hypot(
                local[k][0] - ex, local[k][1] - ey))
            t = local[min(len(local) - 1, j + 5)]
            sc[3] = math.hypot(ex - t[0], ey - t[1])
        if goal_dist >= p.near_threshold:
            ds = [window.path_cells_to(q[0], q[1]) * res for q in poses[::4]]
            sc[4] = sum(min(d, 3.0) for d in ds) / len(ds)
            t = local[min(len(local) - 1, 4)]
            a = abs(wrap(math.atan2(t[1] - poses[0][1], t[0] - poses[0][0])
                         - poses[0][2]))
            sc[5] = a if a > p.max_angle_to_furthest else 0.0
        return sc

    def compute(self, belief: Pose, v: float, w: float, window: LocalWindow,
                local: List[Point], dt: float, goal: Point = None,
                goal_yaw: Optional[float] = None,
                goal_dist: float = math.inf) -> Cycle:
        """Sample, score, weight, apply the first control, shift."""
        if not local:
            return Cycle('invalid_path')
        p = self.params
        goal = goal or local[-1]
        seqs, costs, trajs, rows = [], [], [], []
        T = p.time_steps
        eps = normals(self.rng, 2 * T * p.batch_size)
        for k in range(p.batch_size):
            e = eps[2 * T * k:2 * T * (k + 1)]
            seq = self._clip([(u[0] + p.vx_std * e[2 * t],
                               u[1] + p.wz_std * e[2 * t + 1])
                              for t, u in enumerate(self.u)])
            pose, poses = belief, []
            for cv, cw in seq:
                pose = step_pose(pose, cv, cw, p.model_dt)
                poses.append(pose)
            sc = self._scores(poses, window, local, goal, goal_yaw, goal_dist)
            seqs.append(seq)
            costs.append(sum(k * s for k, s in zip(p.weights, sc)))
            trajs.append([(q[0], q[1]) for q in poses])
            rows.append(sc)
        lo = min(costs)
        cands = [Candidate(s[0][0], s[0][1], c < COLLISION_COST,
                           'collision' if c >= COLLISION_COST else '', c, r, t)
                 for s, c, r, t in zip(seqs, costs, rows, trajs)]
        if lo >= COLLISION_COST:
            return Cycle('no_valid', candidates=cands[:p.emit],
                         n_candidates=len(cands))
        ws = [math.exp(-(c - lo) / p.temperature) for c in costs]
        tot = sum(ws)
        u = [(sum(wk * s[t][0] for wk, s in zip(ws, seqs)) / tot,
              sum(wk * s[t][1] for wk, s in zip(ws, seqs)) / tot)
             for t in range(p.time_steps)]
        u = self._clip(u)
        pose, opt = belief, []
        for cv, cw in u:
            pose = step_pose(pose, cv, cw, p.model_dt)
            opt.append((pose[0], pose[1]))
        self.u = u[1:] + [u[-1]]
        best = Candidate(u[0][0], u[0][1], True, '', lo, [], opt)
        shown = cands[:p.emit] + [best]
        return Cycle('ok', u[0][0], u[0][1], len(shown) - 1, shown,
                     len(cands), n_valid=sum(1 for c in costs
                                             if c < COLLISION_COST))

    def state_values(self) -> List[float]:
        """Return the warm-start control sequence."""
        return [x for u in self.u for x in u]
