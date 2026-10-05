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
Pose-graph SLAM: scan matching, loop closure, and a small optimiser.

The graph has one NODE per update (a robot pose) and an EDGE for every
measured relative pose between two nodes, with an information matrix
saying how much to trust it. SLAM is then "find the poses that disagree
least with every edge" -- a nonlinear least-squares problem (Lu and
Milios 1997; Grisetti et al., "A Tutorial on Graph-Based SLAM", 2010,
whose error and Jacobians this follows). slam_toolbox (Karto) and
Cartographer are both pose-graph SLAMs with far better front ends.

**Front end.** Node ``k``'s scan is matched to node ``k-1``'s by
point-to-line ICP (:func:`icp`) with odometry's relative pose as a
Gaussian PRIOR (a MAP match); odometry's information is its motion
model's (the same ``alphas`` every SLAM here is told), for that step's
motion. The edge's information is the ICP's own
Hessian ``sum(n n^T) / (N sigma_icp^2)`` PLUS odometry's information: along a
direction the scan cannot see (a smooth corridor's axis, where every
normal is perpendicular to it) the Hessian has nothing, and both the
edge's value and its information fall back to odometry there. That is how
a featureless corridor shows up: not as an error, but as missing
information (tested). (Matching without the prior let ICP slide 0.12 to
0.20 m along the loop room's corridors where odometry was within 0.03 m
-- measured in Phase 4, and the reason for the prior.)

**Loop closure.** At every node, earlier nodes at least ``loop_min_gap``
updates old and within ``loop_radius`` of the current ESTIMATE are
candidates; the nearest few are matched by ICP from the estimated relative
pose. One is accepted only if the match converged, fits (RMS residual
below ``loop_max_rmse``, inlier share above ``loop_min_inliers``) and is
WELL CONSTRAINED -- the ICP Hessian's smallest eigenvalue per point above
``loop_min_eig`` -- so a corridor, which matches equally well anywhere
along itself, cannot close a loop. Each accepted closure triggers the
optimiser over the whole graph.

**Optimiser** (:func:`optimise`). Gauss-Newton on SE(2): linearise every
edge's error at the current poses, build the sparse normal equations
``H dx = -b`` (3 x 3 blocks), fix node 0 (the gauge), and solve with
conjugate gradients preconditioned by the exact inverse of the graph's
CHAIN (:class:`ChainPreconditioner`). Repeat until the step is tiny. On
known small graphs it reaches the exact
least-squares answer (tested against a dense solve), and chi^2 never
rises from one iteration to the next on the cases tested.
"""

from dataclasses import asdict, dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple

from . import slam
from .maps import LabMap
from .occgrid import GridParams, OccupancyGrid
from .sketch import apply_delta, odom_delta, wrap

Pose = Tuple[float, float, float]
Mat3 = List[List[float]]
EDGE_KINDS = ('odom', 'icp', 'loop')
COLUMNS = ('icp_ok', 'loops', 'optimised')
INT_COLUMNS = ('row', 'icp_ok', 'loops', 'optimised')


# -- SE(2) ---------------------------------------------------------------------

def compose(a: Pose, b: Pose) -> Pose:
    """Return ``a (+) b``: ``b`` expressed in ``a``'s frame, made global."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            wrap(a[2] + b[2]))


def inverse(a: Pose) -> Pose:
    """Return ``a^-1``."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-c * a[0] - s * a[1], s * a[0] - c * a[1], wrap(-a[2]))


def between(a: Pose, b: Pose) -> Pose:
    """Return ``a^-1 (+) b``: ``b`` in ``a``'s frame."""
    return compose(inverse(a), b)


# -- ICP -------------------------------------------------------------------------

@dataclass
class ICPResult:
    """What a scan match found, and how much it is worth."""

    pose: Pose                 # the current scan's pose in the reference frame
    converged: bool
    rmse: float                # RMS point-to-line residual of the inliers (m)
    inliers: float             # share of the current scan's points matched
    hessian: Mat3              # sum of J^T J over inliers, (dx, dy, dyaw)
    iterations: int

    def min_eig_per_point(self) -> float:
        """Smallest eigenvalue of the Hessian, per matched point."""
        return min_eig3(self.hessian) / max(1, self._n)

    _n: int = 0


def scan_points(ranges: Sequence[float], angles: Sequence[float],
                mount: Pose, range_min: float,
                range_max: float) -> List[Tuple[float, float]]:
    """Return a scan's endpoints in ``base_footprint``, in beam order."""
    out = []
    for z, a in zip(ranges, angles):
        if range_min <= z < range_max:
            out.append(compose(mount, (z * math.cos(a), z * math.sin(a),
                                       0.0))[:2])
    return out


def _normals(pts: List[Tuple[float, float]], max_gap: float):
    """Return a unit normal per point from its scan neighbours, or None."""
    out = []
    n = len(pts)
    for i in range(n):
        a = pts[i - 1] if i > 0 else None
        b = pts[i + 1] if i < n - 1 else None
        p = pts[i]
        if a is not None and math.dist(a, p) > max_gap:
            a = None
        if b is not None and math.dist(b, p) > max_gap:
            b = None
        if a is None and b is None:
            out.append(None)
            continue
        u = a if a is not None else p
        v = b if b is not None else p
        tx, ty = v[0] - u[0], v[1] - u[1]
        L = math.hypot(tx, ty)
        out.append(None if L < 1e-9 else (-ty / L, tx / L))
    return out


class _Hash:
    """Points bucketed on a square grid, for nearest-neighbour queries."""

    def __init__(self, pts, cell):
        self.cell = cell
        self.b: Dict[Tuple[int, int], List[int]] = {}
        for i, (x, y) in enumerate(pts):
            self.b.setdefault((math.floor(x / cell), math.floor(y / cell)),
                              []).append(i)
        self.pts = pts

    def nearest(self, x, y, max_d):
        cx, cy = math.floor(x / self.cell), math.floor(y / self.cell)
        best, bd = -1, max_d * max_d
        for jx in (cx - 1, cx, cx + 1):
            for jy in (cy - 1, cy, cy + 1):
                for i in self.b.get((jx, jy), ()):
                    px, py = self.pts[i]
                    d = (px - x) ** 2 + (py - y) ** 2
                    if d < bd or (d == bd and i < best):
                        best, bd = i, d
        return best


def solve3(A: Mat3, b: Sequence[float]) -> Optional[List[float]]:
    """Solve a 3 x 3 system by Cramer's rule; None if singular."""
    (a, b_, c), (d, e, f), (g, h, i) = A
    det = a * (e * i - f * h) - b_ * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-300:
        return None
    x = (b[0] * (e * i - f * h) - b_ * (b[1] * i - f * b[2])
         + c * (b[1] * h - e * b[2])) / det
    y = (a * (b[1] * i - f * b[2]) - b[0] * (d * i - f * g)
         + c * (d * b[2] - b[1] * g)) / det
    z = (a * (e * b[2] - b[1] * h) - b_ * (d * b[2] - b[1] * g)
         + b[0] * (d * h - e * g)) / det
    return [x, y, z]


def min_eig3(A: Mat3) -> float:
    """Return the smallest eigenvalue of a symmetric 3 x 3 matrix."""
    a, b, c = A[0][0], A[1][1], A[2][2]
    d, e, f = A[0][1], A[1][2], A[0][2]
    p1 = d * d + e * e + f * f
    if p1 < 1e-30:
        return min(a, b, c)
    q = (a + b + c) / 3
    p2 = (a - q) ** 2 + (b - q) ** 2 + (c - q) ** 2 + 2 * p1
    p = math.sqrt(p2 / 6)
    B = [[(A[i][j] - (q if i == j else 0)) / p for j in range(3)]
         for i in range(3)]
    r = (B[0][0] * (B[1][1] * B[2][2] - B[1][2] * B[2][1])
         - B[0][1] * (B[1][0] * B[2][2] - B[1][2] * B[2][0])
         + B[0][2] * (B[1][0] * B[2][1] - B[1][1] * B[2][0])) / 2
    r = max(-1.0, min(1.0, r))
    phi = math.acos(r) / 3
    return q + 2 * p * math.cos(phi + 2 * math.pi / 3)


def icp(ref: List[Tuple[float, float]], cur: List[Tuple[float, float]],
        guess: Pose, max_iter: int = 25, max_dist: float = 0.5,
        normal_gap: float = 0.5, damping: float = 1e-3,
        prior: Optional[Mat3] = None, sigma: float = 0.05) -> ICPResult:
    """
    Point-to-line ICP: the pose of ``cur``'s frame in ``ref``'s frame.

    Each current point, moved by the pose so far, is paired with its
    nearest reference point within ``max_dist`` that has a normal; the
    step minimises the summed squared distance along those normals,
    linearised in the rotation. The scan counts as ONE measurement of
    standard deviation ``sigma``: each of its N residuals is weighted
    ``1 / (sigma^2 N)``, because neighbouring beams on one wall do not err
    independently (treating them as independent made a 60-beam scan claim
    millimetre accuracy, and the front end beat odometry LESS often than it
    lost to it on the arena -- measured in Phase 4). With ``prior`` (an information matrix on ``(x, y, yaw)``)
    the guess is a Gaussian PRIOR in the same least squares -- a MAP
    match: along a direction the scan cannot see (a corridor's axis) the
    answer stays at the guess instead of sliding. Without a prior a small
    ``damping`` regularises the step. Stops when the step is below
    0.1 mm and 0.0001 rad.
    """
    normals = _normals(ref, normal_gap)
    keep = [i for i, nv in enumerate(normals) if nv is not None]
    rpts = [ref[i] for i in keep]
    rnor = [normals[i] for i in keep]
    empty = [[0.0] * 3 for _ in range(3)]
    if len(rpts) < 3 or len(cur) < 3:
        return ICPResult(tuple(guess), False, math.inf, 0.0, empty, 0)
    h = _Hash(rpts, max_dist)
    x, y, th = guess
    it = 0
    converged = False
    H = empty
    pairs = []
    for it in range(1, max_iter + 1):
        c, s = math.cos(th), math.sin(th)
        H = [[0.0] * 3 for _ in range(3)]
        g = [0.0, 0.0, 0.0]
        pairs = []
        for (px, py) in cur:
            qx = x + c * px - s * py
            qy = y + s * px + c * py
            j = h.nearest(qx, qy, max_dist)
            if j < 0:
                continue
            nx, ny = rnor[j]
            rx, ry = rpts[j]
            e = nx * (qx - rx) + ny * (qy - ry)
            # d(q)/d(th) = (-s px - c py, c px - s py)
            jt = nx * (-s * px - c * py) + ny * (c * px - s * py)
            J = (nx, ny, jt)
            for a in range(3):
                g[a] += J[a] * e
                for b in range(3):
                    H[a][b] += J[a] * J[b]
            pairs.append(e)
        if len(pairs) < 3:
            break
        # the scan as ONE measurement of standard deviation ``sigma``: the
        # residuals of neighbouring beams on one wall are not independent
        w = 1.0 / (sigma * sigma * len(pairs))
        if prior is not None:
            dv = (x - guess[0], y - guess[1], wrap(th - guess[2]))
            A = [[w * H[a][b] + prior[a][b] for b in range(3)]
                 for a in range(3)]
            rhs = [-(w * g[a] + sum(prior[a][c] * dv[c] for c in range(3)))
                   for a in range(3)]
        else:
            A = [[H[a][b] + (damping * len(pairs) if a == b else 0.0)
                  for b in range(3)] for a in range(3)]
            rhs = [-g[0], -g[1], -g[2]]
        step = solve3(A, rhs)
        if step is None:
            break
        x, y, th = x + step[0], y + step[1], wrap(th + step[2])
        if abs(step[0]) < 1e-4 and abs(step[1]) < 1e-4 and \
                abs(step[2]) < 1e-4:
            converged = True
            break
    rmse = math.sqrt(sum(e * e for e in pairs) / len(pairs)) if pairs \
        else math.inf
    res = ICPResult((x, y, th), converged, rmse, len(pairs) / len(cur), H, it)
    res._n = len(pairs)
    return res


# -- the graph ---------------------------------------------------------------------

@dataclass
class Edge:
    """A measured pose of node ``j`` in node ``i``'s frame, and its information."""

    i: int
    j: int
    z: Pose
    info: Mat3
    kind: str


def edge_error(xi: Pose, xj: Pose, z: Pose) -> Tuple[float, float, float]:
    """Return ``t2v(z^-1 (xi^-1 xj))``: zero when the poses agree with ``z``."""
    return between(z, between(xi, xj))


def _jacobians(xi: Pose, xj: Pose, z: Pose):
    """Return A = de/dxi and B = de/dxj (Grisetti et al. 2010, eq. 32-33)."""
    ci, si = math.cos(xi[2]), math.sin(xi[2])
    cz, sz = math.cos(z[2]), math.sin(z[2])
    dx, dy = xj[0] - xi[0], xj[1] - xi[1]
    # Rz^T Ri^T
    RtRt = [[cz * ci - sz * si, cz * si + sz * ci],
            [-sz * ci - cz * si, -sz * si + cz * ci]]
    # Rz^T dRi^T/dth (tj - ti)
    dRi_t = (-si * dx + ci * dy, -ci * dx - si * dy)
    v = (cz * dRi_t[0] + sz * dRi_t[1], -sz * dRi_t[0] + cz * dRi_t[1])
    A = [[-RtRt[0][0], -RtRt[0][1], v[0]],
         [-RtRt[1][0], -RtRt[1][1], v[1]],
         [0.0, 0.0, -1.0]]
    B = [[RtRt[0][0], RtRt[0][1], 0.0],
         [RtRt[1][0], RtRt[1][1], 0.0],
         [0.0, 0.0, 1.0]]
    return A, B


def chi2(poses: Sequence[Pose], edges: Sequence[Edge]) -> float:
    """Return the summed ``e^T info e`` over every edge."""
    total = 0.0
    for ed in edges:
        e = edge_error(poses[ed.i], poses[ed.j], ed.z)
        for a in range(3):
            for b in range(3):
                total += e[a] * ed.info[a][b] * e[b]
    return total


def _matvec(Hd, Hoff, v, n):
    out = [0.0] * (3 * n)
    for i in range(n):
        B = Hd[i]
        for a in range(3):
            out[3 * i + a] += B[a][0] * v[3 * i] + B[a][1] * v[3 * i + 1] + \
                B[a][2] * v[3 * i + 2]
    for (i, j), B in Hoff.items():
        for a in range(3):
            out[3 * i + a] += B[a][0] * v[3 * j] + B[a][1] * v[3 * j + 1] + \
                B[a][2] * v[3 * j + 2]
            out[3 * j + a] += B[0][a] * v[3 * i] + B[1][a] * v[3 * i + 1] + \
                B[2][a] * v[3 * i + 2]
    return out


def _inv3(M: Mat3) -> Mat3:
    cols = [solve3(M, e) for e in ([1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0])]
    return [[cols[j][i] for j in range(3)] for i in range(3)]


def _mm3(A: Mat3, B: Mat3) -> Mat3:
    return [[A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j]
             for j in range(3)] for i in range(3)]


def _mv3(A: Mat3, v) -> List[float]:
    return [A[i][0] * v[0] + A[i][1] * v[1] + A[i][2] * v[2]
            for i in range(3)]


def _t3(A: Mat3) -> Mat3:
    return [[A[j][i] for j in range(3)] for i in range(3)]


class ChainPreconditioner:
    """
    The exact inverse of H's block-TRIDIAGONAL part, applied in O(n).

    The odometry/ICP chain links node i to i+1, so H restricted to its
    diagonal blocks and its (i, i+1) blocks is block tridiagonal, and SPD
    (each loop edge contributes a PSD block-diagonal part to it). Its block
    LDL^T (the block Thomas algorithm) is computed once per Gauss-Newton
    iteration. Preconditioned by it, conjugate gradients only has to
    resolve the loop closures' off-chain blocks -- a low-rank correction
    -- so it converges in a few iterations per loop closure instead of
    a number growing with the length of the chain ("subgraph
    preconditioning", Dellaert et al. 2010, with a chain as the subgraph).
    """

    def __init__(self, Hd, Hoff, n):
        self.n = n
        self.C = [Hoff.get((i, i + 1)) for i in range(n - 1)]
        self.Dinv = []
        self.L = []
        prev_inv = None
        for i in range(n):
            D = [row[:] for row in Hd[i]]
            if i > 0 and self.C[i - 1] is not None:
                Ct = _t3(self.C[i - 1])
                Li = _mm3(Ct, prev_inv)
                LC = _mm3(Li, self.C[i - 1])
                D = [[D[a][b] - LC[a][b] for b in range(3)] for a in range(3)]
            else:
                Li = None
            self.L.append(Li)
            prev_inv = _inv3(D)
            self.Dinv.append(prev_inv)

    def solve(self, r):
        n = self.n
        y = []
        for i in range(n):
            v = [r[3 * i], r[3 * i + 1], r[3 * i + 2]]
            if self.L[i] is not None:
                u = _mv3(self.L[i], y[i - 1])
                v = [v[0] - u[0], v[1] - u[1], v[2] - u[2]]
            y.append(v)
        x = [None] * n
        for i in range(n - 1, -1, -1):
            v = y[i]
            if i < n - 1 and self.C[i] is not None:
                u = _mv3(self.C[i], x[i + 1])
                v = [v[0] - u[0], v[1] - u[1], v[2] - u[2]]
            x[i] = _mv3(self.Dinv[i], v)
        return [c for blk in x for c in blk]


def pcg(Hd, Hoff, b, n, tol=1e-9, max_iter=None) -> Tuple[List[float], int]:
    """
    Solve ``H x = b`` (block-sparse SPD); return ``(x, iterations)``.

    Conjugate gradients preconditioned by :class:`ChainPreconditioner`.
    """
    M = ChainPreconditioner(Hd, Hoff, n)
    x = [0.0] * (3 * n)
    r = list(b)
    z = M.solve(r)
    p = list(z)
    rz = sum(u * v for u, v in zip(r, z))
    bn = math.sqrt(sum(v * v for v in b)) or 1.0
    it = 0
    for it in range(1, (max_iter or 3 * n + 20) + 1):
        Ap = _matvec(Hd, Hoff, p, n)
        pAp = sum(u * v for u, v in zip(p, Ap))
        if pAp <= 0:
            break
        alpha = rz / pAp
        for k in range(3 * n):
            x[k] += alpha * p[k]
            r[k] -= alpha * Ap[k]
        if math.sqrt(sum(v * v for v in r)) <= tol * bn:
            break
        z = M.solve(r)
        rz2 = sum(u * v for u, v in zip(r, z))
        beta = rz2 / rz
        rz = rz2
        p = [zv + beta * pv for zv, pv in zip(z, p)]
    return x, it


def linear_system(poses: Sequence[Pose], edges: Sequence[Edge],
                  fixed: int = 0, prior: float = 1e9):
    """Return ``(Hd, Hoff, b)``: the Gauss-Newton normal equations."""
    n = len(poses)
    Hd = [[[0.0] * 3 for _ in range(3)] for _ in range(n)]
    Hoff: Dict[Tuple[int, int], Mat3] = {}
    b = [0.0] * (3 * n)
    for ed in edges:
        xi, xj = poses[ed.i], poses[ed.j]
        e = edge_error(xi, xj, ed.z)
        A, B = _jacobians(xi, xj, ed.z)
        info = ed.info
        # AtO = A^T O, BtO = B^T O
        AtO = [[sum(A[k][a] * info[k][c] for k in range(3)) for c in range(3)]
               for a in range(3)]
        BtO = [[sum(B[k][a] * info[k][c] for k in range(3)) for c in range(3)]
               for a in range(3)]
        i, j = ed.i, ed.j
        Hij = Hoff.setdefault((i, j), [[0.0] * 3 for _ in range(3)]) \
            if i < j else None
        Hji = Hoff.setdefault((j, i), [[0.0] * 3 for _ in range(3)]) \
            if j < i else None
        for a in range(3):
            b[3 * i + a] += sum(AtO[a][c] * e[c] for c in range(3))
            b[3 * j + a] += sum(BtO[a][c] * e[c] for c in range(3))
            for c in range(3):
                Hd[i][a][c] += sum(AtO[a][k] * A[k][c] for k in range(3))
                Hd[j][a][c] += sum(BtO[a][k] * B[k][c] for k in range(3))
                if Hij is not None:
                    Hij[a][c] += sum(AtO[a][k] * B[k][c] for k in range(3))
                else:
                    Hji[a][c] += sum(BtO[a][k] * A[k][c] for k in range(3))
    for a in range(3):
        Hd[fixed][a][a] += prior
    return Hd, Hoff, b


def optimise(poses: Sequence[Pose], edges: Sequence[Edge],
             iterations: int = 10,
             fixed: int = 0) -> Tuple[List[Pose], List[float]]:
    """
    Gauss-Newton over the graph; return ``(poses, chi2 after each iteration)``.

    ``chi2[0]`` is before the first iteration. Node ``fixed`` is held by a
    strong prior (the gauge: a graph of relative measurements does not
    say where it is, only its shape).
    """
    x = [tuple(p) for p in poses]
    n = len(x)
    hist = [chi2(x, edges)]
    for _ in range(iterations):
        Hd, Hoff, b = linear_system(x, edges, fixed)
        dx, _ = pcg(Hd, Hoff, [-v for v in b], n)
        x = [(x[i][0] + dx[3 * i], x[i][1] + dx[3 * i + 1],
              wrap(x[i][2] + dx[3 * i + 2])) for i in range(n)]
        hist.append(chi2(x, edges))
        if max(abs(v) for v in dx) < 1e-5:
            break
    return x, hist


# -- the SLAM -------------------------------------------------------------------

@dataclass(frozen=True)
class PoseGraphParams:
    """Front end, loop closure and optimiser settings."""

    #: the odometry motion model's alphas, as told to every SLAM here; an
    #: odometry edge's covariance is that model's, for that step's motion
    alphas: Tuple[float, float, float, float] = (0.02, 0.02, 0.02, 0.02)
    #: floors on an odometry edge's standard deviation (a zero move would
    #: otherwise claim infinite certainty)
    odom_sigma_xy: float = 0.005
    odom_sigma_yaw: float = 0.002
    #: an ICP residual's standard deviation (sets the ICP Hessian's weight)
    icp_sigma: float = 0.05
    icp_max_dist: float = 0.5
    icp_max_rmse: float = 0.08
    icp_min_inliers: float = 0.5
    loop_closure: bool = True
    loop_radius: float = 2.0
    loop_min_gap: int = 20
    loop_candidates: int = 2
    loop_max_rmse: float = 0.05
    loop_min_inliers: float = 0.7
    loop_min_eig: float = 0.05
    #: after an accepted closure, look again only this many updates later
    loop_cooldown: int = 10
    iterations: int = 10
    snapshots: int = 16

    def check(self) -> None:
        """Raise :class:`slam.SlamError` unless the parameters make sense."""
        if len(self.alphas) != 4 or any(v < 0 for v in self.alphas):
            raise slam.SlamError('alphas: four values >= 0')
        for name in ('odom_sigma_xy', 'odom_sigma_yaw', 'icp_sigma',
                     'icp_max_dist', 'icp_max_rmse', 'loop_radius',
                     'loop_max_rmse'):
            v = getattr(self, name)
            if not (0 < v <= 10):
                raise slam.SlamError(f'{name} must be in (0, 10]')
        if not (0 <= self.icp_min_inliers <= 1 and
                0 <= self.loop_min_inliers <= 1):
            raise slam.SlamError('inlier shares in [0, 1]')
        if not (1 <= self.loop_min_gap <= 10000 and
                1 <= self.loop_candidates <= 10 and
                0 <= self.loop_cooldown <= 10000 and
                1 <= self.iterations <= 100):
            raise slam.SlamError('loop_min_gap, loop_candidates or '
                                 'iterations out of range')
        if not (0 <= self.snapshots <= 64):
            raise slam.SlamError('snapshots 0..64')

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        d = asdict(self)
        d['alphas'] = list(self.alphas)
        return d


def odometry_information(rot1: float, trans: float, rot2: float,
                         p: 'PoseGraphParams') -> Mat3:
    """
    Return the information of one odometry edge, in node ``k-1``'s frame.

    The odometry motion model's covariance for this step (``V M V^T``,
    linearised exactly as EKF-SLAM and Lab 2's EKF do it, at heading 0:
    the edge is expressed in the previous node's frame) plus the floors,
    inverted.
    """
    from .localise import _motion_jacobians
    _, Q = _motion_jacobians((0.0, 0.0, 0.0), rot1, trans, rot2, p.alphas)
    Q[0][0] += p.odom_sigma_xy ** 2
    Q[1][1] += p.odom_sigma_xy ** 2
    Q[2][2] += p.odom_sigma_yaw ** 2
    return _inv3(Q)


def _diag(sxy, syaw) -> Mat3:
    return [[1 / sxy ** 2, 0.0, 0.0], [0.0, 1 / sxy ** 2, 0.0],
            [0.0, 0.0, 1 / syaw ** 2]]


def _rebuild(like, grid_params, poses, inp, angles, upto) -> OccupancyGrid:
    li = inp.lidar
    g = OccupancyGrid.like(like, grid_params)
    for k in range(upto + 1):
        g.integrate(poses[k], inp.ranges[k], angles, li.mount, li.range_min,
                    li.range_max)
    return g


def run_pose_graph(inp: slam.SlamInputs, like: LabMap,
                   params: Optional[PoseGraphParams] = None,
                   grid_params: Optional[GridParams] = None) -> slam.SlamTrace:
    """Run pose-graph SLAM over ``inp``; return its trace."""
    p = params or PoseGraphParams()
    p.check()
    angles = inp.angles()
    li = inp.lidar
    pts = [scan_points(z, angles, li.mount, li.range_min, li.range_max)
           for z in inp.ranges]
    poses: List[Pose] = [tuple(inp.start)]
    edges: List[Edge] = []
    grid = OccupancyGrid.like(like, grid_params)
    grid.integrate(poses[0], inp.ranges[0], angles, li.mount, li.range_min,
                   li.range_max)
    cols = {c: [] for c in slam.COMMON_COLUMNS + COLUMNS}
    loop_events = []  # (update k, node j)
    opt = {'k': [], 'iterations': [], 'chi2_before': [], 'chi2_after': []}
    last_closure = -10 ** 9
    stale = False
    snaps = set(slam.snapshot_updates(len(inp), p.snapshots))
    snapshots, maps = [], []
    w_icp = 1.0 / p.icp_sigma ** 2

    def record(k, icp_ok, loops, optimised):
        e = poses[k]
        for name, v in zip(slam.COMMON_COLUMNS + COLUMNS,
                           (inp.rows[k], inp.t[k], e[0], e[1], e[2],
                            icp_ok, loops, optimised)):
            cols[name].append(v)

    record(0, 0, 0, 0)
    if 0 in snaps:
        snapshots.append(0)
        maps.append(grid.to_u8())
    for k in range(1, len(inp)):
        d = odom_delta(inp.odom[k - 1], inp.odom[k])
        guess = apply_delta((0.0, 0.0, 0.0), *d)
        odom_info = odometry_information(*d, p)
        r = icp(pts[k - 1], pts[k], guess, max_dist=p.icp_max_dist,
                prior=odom_info, sigma=p.icp_sigma)
        ok = (r.converged and r.rmse <= p.icp_max_rmse and
              r.inliers >= p.icp_min_inliers)
        if ok:
            wn = w_icp / max(1, r._n)
            info = [[wn * r.hessian[a][b] + odom_info[a][b]
                     for b in range(3)] for a in range(3)]
            edges.append(Edge(k - 1, k, r.pose, info, 'icp'))
        else:
            edges.append(Edge(k - 1, k, guess, odom_info, 'odom'))
        poses.append(compose(poses[k - 1], edges[-1].z))
        loops = 0
        optimised = 0
        if p.loop_closure and k >= p.loop_min_gap and \
                k - last_closure >= p.loop_cooldown:
            here = poses[k]
            cands = sorted(
                (math.hypot(poses[j][0] - here[0], poses[j][1] - here[1]), j)
                for j in range(0, k - p.loop_min_gap + 1))
            cands = [j for dd, j in cands if dd <= p.loop_radius]
            for j in cands[:p.loop_candidates]:
                lr = icp(pts[j], pts[k], between(poses[j], here),
                         max_dist=p.icp_max_dist)
                if not (lr.converged and lr.rmse <= p.loop_max_rmse and
                        lr.inliers >= p.loop_min_inliers and
                        lr.min_eig_per_point() >= p.loop_min_eig):
                    continue
                wn = w_icp / max(1, lr._n)
                info = [[wn * lr.hessian[a][b] for b in range(3)]
                        for a in range(3)]
                edges.append(Edge(j, k, lr.pose, info, 'loop'))
                loop_events.append((k, j))
                loops += 1
            if loops:
                last_closure = k
                stale = True
                poses, hist = optimise(poses, edges, p.iterations)
                opt['k'].append(k)
                opt['iterations'].append(len(hist) - 1)
                opt['chi2_before'].append(hist[0])
                opt['chi2_after'].append(hist[-1])
                optimised = 1
        if not stale:
            grid.integrate(poses[k], inp.ranges[k], angles, li.mount,
                           li.range_min, li.range_max)
        record(k, int(ok), loops, optimised)
        if k in snaps:
            # after an optimisation every past pose moved: the map is
            # rebuilt from the scans at their current estimates, lazily
            if stale:
                grid = _rebuild(like, grid_params, poses, inp, angles, k)
                stale = False
            snapshots.append(k)
            maps.append(grid.to_u8())
    arrays = {
        'edges.i': ('i32', [e.i for e in edges]),
        'edges.j': ('i32', [e.j for e in edges]),
        'edges.kind': ('i32', [EDGE_KINDS.index(e.kind) for e in edges]),
        'loops.k': ('i32', [a for a, _ in loop_events]),
        'loops.j': ('i32', [b for _, b in loop_events]),
        'opt.k': ('i32', opt['k']),
        'opt.iterations': ('i32', opt['iterations']),
        'opt.chi2_before': ('f64', opt['chi2_before']),
        'opt.chi2_after': ('f64', opt['chi2_after']),
    }
    for c, i in (('x', 0), ('y', 1), ('yaw', 2)):
        arrays[f'final.{c}'] = ('f64', [q[i] for q in poses])
    hdr = slam.header('pose_graph', p.to_dict(), slam.grid_header(
        grid.width, grid.height, grid.resolution, grid.origin), inp)
    hdr['grid_params'] = grid.params.to_dict()
    hdr['edge_kinds'] = list(EDGE_KINDS)
    tr = slam.SlamTrace(hdr, cols, INT_COLUMNS, arrays, snapshots, maps)
    tr.validate()
    return tr
