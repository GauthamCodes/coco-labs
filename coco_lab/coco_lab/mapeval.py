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
How good is a map, and how good is a trajectory? Lab 3's metrics, defined.

Every number Lab 3 prints about a map or a trajectory is computed here, by
the definitions below, and nowhere else (the browser renders them).

**Absolute trajectory error** (:func:`ate`). The estimated positions are
first moved by the ONE rigid 2D transform (rotation + translation, no
scale) that best fits them to the true positions in the least-squares
sense (Horn 1987 / Umeyama 1991, in 2D: a closed form, :func:`align_se2`)
-- because a SLAM's map frame is its own, and only the SHAPE of the
trajectory can be wrong. Then: RMSE, mean, max and final position error,
in metres. ``align=False`` scores in the given frame instead (used where
the start was told and the frames already agree).

**Map score** (:func:`score_map`), against a ground-truth occupancy map
(``truth``) of the same placement:

- ``exact``: :func:`coco_lab.maps.compare_occupied` -- the project's
  cell-exact precision and recall of occupied cells (Phase 1B), kept for
  continuity. It punishes a wall drawn one cell off as two errors.
- ``precision`` at tolerance ``tol``: the share of the map's OCCUPIED cells
  within ``tol`` metres of a truly occupied cell.
- ``recall`` at ``tol``: the share of the truth's VISIBLE wall cells that
  have a mapped occupied cell within ``tol``. A visible wall cell is an
  occupied truth cell with a 4-neighbour that is free AND reachable from
  the start (flood fill over the truth's free cells): the back of a solid
  box, or the far side of the arena's outer wall, can never be seen and
  is not counted.
- ``f1``: the harmonic mean of those two -- **the map score**.
- ``coverage``: the share of reachable truly-free cells the map has
  observed (FREE or OCCUPIED, not UNKNOWN).

Distances use the exact Euclidean distance transform (``sketch.edt``)
between cell centres.
"""

from collections import deque
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .maps import compare_occupied, FREE, LabMap, OCCUPIED, UNKNOWN
from .sketch import edt, wrap

Pose = Tuple[float, float, float]
#: the map score's default tolerance: two cells at 0.05 m, one at 0.10 m
DEFAULT_TOL = 0.10


def align_se2(est: Sequence[Sequence[float]],
              truth: Sequence[Sequence[float]]) -> Tuple[float, float, float]:
    """
    Return ``(tx, ty, theta)`` minimising sum |R(theta) e + t - g|^2.

    The 2D closed form: centre both point sets, theta = atan2 of the
    cross terms, then t moves the rotated centroid onto the true one.
    """
    n = len(est)
    if n == 0 or n != len(truth):
        raise ValueError('align_se2 needs two equal, non-empty point lists')
    ex = sum(p[0] for p in est) / n
    ey = sum(p[1] for p in est) / n
    gx = sum(p[0] for p in truth) / n
    gy = sum(p[1] for p in truth) / n
    sxx = sxy = syx = syy = 0.0
    for e, g in zip(est, truth):
        a, b = e[0] - ex, e[1] - ey
        c, d = g[0] - gx, g[1] - gy
        sxx += a * c
        sxy += a * d
        syx += b * c
        syy += b * d
    th = math.atan2(sxy - syx, sxx + syy)
    co, si = math.cos(th), math.sin(th)
    return (gx - (co * ex - si * ey), gy - (si * ex + co * ey), th)


def apply_se2(T: Tuple[float, float, float], p: Sequence[float]) -> Pose:
    """Return pose (or point) ``p`` moved by ``T = (tx, ty, theta)``."""
    tx, ty, th = T
    co, si = math.cos(th), math.sin(th)
    yaw = wrap(p[2] + th) if len(p) > 2 else 0.0
    return (tx + co * p[0] - si * p[1], ty + si * p[0] + co * p[1], yaw)


def ate(est: Sequence[Sequence[float]], truth: Sequence[Sequence[float]],
        align: bool = True) -> Dict[str, object]:
    """Return the absolute trajectory error (metres) and the alignment used."""
    T = align_se2(est, truth) if align else (0.0, 0.0, 0.0)
    errs = []
    for e, g in zip(est, truth):
        a = apply_se2(T, e)
        errs.append(math.hypot(a[0] - g[0], a[1] - g[1]))
    n = len(errs)
    return {
        'n': n, 'aligned': bool(align), 'alignment': list(T),
        'rmse': math.sqrt(sum(v * v for v in errs) / n),
        'mean': sum(errs) / n, 'max': max(errs), 'final': errs[-1],
    }


def errors(est, truth, T=(0.0, 0.0, 0.0)) -> List[float]:
    """Return the per-pose position errors after moving ``est`` by ``T``."""
    out = []
    for e, g in zip(est, truth):
        a = apply_se2(T, e)
        out.append(math.hypot(a[0] - g[0], a[1] - g[1]))
    return out


def reachable(truth: LabMap, start_xy: Tuple[float, float]) -> bytearray:
    """
    Return a mask (row-major, like ``occupancy``) of free cells reachable
    from ``start_xy`` by 4-connected steps through the truth's FREE cells.
    """
    w, h = truth.width, truth.height
    occ = truth.occupancy
    mask = bytearray(w * h)
    cell = truth.cell_at(*start_xy)
    if cell is None:
        raise ValueError(f'start {start_xy} is off the truth map')
    s = cell[0] * w + cell[1]
    if occ[s] != FREE:
        # start on a wall cell (rasterisation): take the nearest free cell
        best = None
        for i, v in enumerate(occ):
            if v == FREE:
                r, c = divmod(i, w)
                d = (r - cell[0]) ** 2 + (c - cell[1]) ** 2
                if best is None or d < best[0]:
                    best = (d, i)
        if best is None:
            return mask
        s = best[1]
    mask[s] = 1
    q = deque([s])
    while q:
        i = q.popleft()
        r, c = divmod(i, w)
        for j, ok in ((i - w, r > 0), (i + w, r < h - 1), (i - 1, c > 0),
                      (i + 1, c < w - 1)):
            if ok and not mask[j] and occ[j] == FREE:
                mask[j] = 1
                q.append(j)
    return mask


def visible_walls(truth: LabMap, reach: bytearray) -> bytearray:
    """Return a mask of occupied truth cells 4-adjacent to a reachable cell."""
    w, h = truth.width, truth.height
    occ = truth.occupancy
    out = bytearray(w * h)
    for i, v in enumerate(occ):
        if v != OCCUPIED:
            continue
        r, c = divmod(i, w)
        if (r > 0 and reach[i - w]) or (r < h - 1 and reach[i + w]) or \
                (c > 0 and reach[i - 1]) or (c < w - 1 and reach[i + 1]):
            out[i] = 1
    return out


class Truth:
    """A ground-truth map prepared for scoring (distance field, masks)."""

    def __init__(self, truth: LabMap, start_xy: Tuple[float, float]):
        """Precompute what every score against ``truth`` needs."""
        self.map = truth
        self.reach = reachable(truth, start_xy)
        self.walls = visible_walls(truth, self.reach)
        res = truth.resolution
        self.dist = [d * res for d in edt(
            [v == OCCUPIED for v in truth.occupancy], truth.width,
            truth.height)]
        self.n_reach = sum(self.reach)
        self.n_walls = sum(self.walls)


def score_map(truth: Truth, test: LabMap,
              tol: float = DEFAULT_TOL) -> Dict[str, object]:
    """Score ``test`` against the prepared ``truth``; see the module docs."""
    t = truth.map
    if (t.width, t.height, t.resolution, t.origin) != \
            (test.width, test.height, test.resolution, test.origin):
        raise ValueError('test map must have the truth map\'s placement '
                         '(use resample_onto)')
    occ = test.occupancy
    n_occ = good = 0
    for i, v in enumerate(occ):
        if v == OCCUPIED:
            n_occ += 1
            if truth.dist[i] <= tol + 1e-9:
                good += 1
    tdist = edt([v == OCCUPIED for v in occ], test.width, test.height)
    res = test.resolution
    found = sum(1 for i, m in enumerate(truth.walls)
                if m and tdist[i] * res <= tol + 1e-9)
    seen = sum(1 for i, m in enumerate(truth.reach)
               if m and occ[i] != UNKNOWN)
    precision = good / n_occ if n_occ else None
    recall = found / truth.n_walls if truth.n_walls else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else 0.0)
    return {
        'tol_m': tol, 'precision': precision, 'recall': recall, 'f1': f1,
        'coverage': seen / truth.n_reach if truth.n_reach else None,
        'occupied_cells': n_occ, 'visible_wall_cells': truth.n_walls,
        'reachable_free_cells': truth.n_reach,
        'exact': compare_occupied(t, test),
    }


def resample_onto(like: LabMap, cells: bytes, width: int, height: int,
                  resolution: float, origin: Tuple[float, float],
                  T: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                  ) -> bytes:
    """
    Return OccupancyGrid bytes (north row first) on ``like``'s grid.

    ``cells`` is a grid in its own frame; ``T`` takes that frame into
    ``like``'s (the trajectory alignment, for a SLAM whose map frame is its
    own). Each target cell takes the value of the source cell under its
    centre (nearest neighbour), or 255 (unknown) off the source grid.
    """
    ti = (-(math.cos(T[2]) * T[0] + math.sin(T[2]) * T[1]),
          math.sin(T[2]) * T[0] - math.cos(T[2]) * T[1], -T[2])
    co, si = math.cos(ti[2]), math.sin(ti[2])
    out = bytearray([255]) * (like.width * like.height)
    lr, (lox, loy) = like.resolution, like.origin
    for row in range(like.height):
        y = loy + (like.height - 1 - row + 0.5) * lr
        for col in range(like.width):
            x = lox + (col + 0.5) * lr
            sx = ti[0] + co * x - si * y
            sy = ti[1] + si * x + co * y
            ix = math.floor((sx - origin[0]) / resolution)
            iy = math.floor((sy - origin[1]) / resolution)
            if 0 <= ix < width and 0 <= iy < height:
                out[row * like.width + col] = \
                    cells[(height - 1 - iy) * width + ix]
    return bytes(out)


def score_run(truth: Truth, cells: bytes, grid: Dict[str, object],
              est, true_poses, align: bool, thresholds,
              tol: float = DEFAULT_TOL) -> Dict[str, object]:
    """
    Score one run's final map and trajectory; return the summary block.

    ``est`` is the trajectory scored (final where the algorithm revises
    it); with ``align`` the same alignment moves the map onto the truth.
    """
    from .occgrid import GridParams, u8_to_labmap
    a = ate(est, true_poses, align=align)
    T = tuple(a['alignment'])
    like = truth.map
    on = resample_onto(like, cells, grid['width'], grid['height'],
                       grid['resolution'], tuple(grid['origin']), T)
    gp = GridParams(free_thresh=thresholds[0], occupied_thresh=thresholds[1])
    lm = u8_to_labmap(on, like.width, like.height, like.resolution,
                      like.origin, gp)
    return {'ate': a, 'map': score_map(truth, lm, tol)}


def round_floats(x, nd: int = 6):
    """Return ``x`` with every float rounded to ``nd`` places (stable JSON)."""
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: round_floats(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [round_floats(v, nd) for v in x]
    return x


def unknown_share(cells: bytes) -> Optional[float]:
    """Return the share of 255 (unknown) bytes."""
    return cells.count(255) / len(cells) if cells else None
