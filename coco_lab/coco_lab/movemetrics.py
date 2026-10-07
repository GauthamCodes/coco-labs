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
Lab 5's controller metrics, defined before any controller was measured.

Everything is in the MAP frame and on the SIMULATOR clock. A run's inputs:

``path``
    The frozen global path the controller was given, ``[(x, y, yaw)]``.
``gt``
    Ground-truth poses ``[(t, x, y, yaw)]`` (Gazebo's own odometry of the
    model, shifted into the map frame), in time order.
``window``
    ``(t0, t1)``: FollowPath's acceptance and its result, as the lab node
    stamped them. Every metric uses only samples with ``t0 <= t <= t1``.
``cmd``
    The CONTROLLER's output ``[(t, v, w)]`` (``/cmd_vel_nav``: what the
    controller asked for, before the velocity smoother and the collision
    monitor shape it), in time order.
``boxes``
    The world's static obstacles, axis-aligned ``(cx, cy, sx, sy)``
    (``navigation_world.json``, shifted into the map frame).
``actors``
    Moving cylinders ``{"radius": r, "track": [(t, x, y)]}``; a pose
    between samples is linearly interpolated, never extrapolated.

The four metrics (:func:`evaluate`):

**Tracking error** (m) -- Phase 1C's definition, unchanged: for every GT
sample in the window, its distance to the nearest point of the path
polyline; ``n``, ``mean``, ``p95`` (nearest rank: the value at 1-based
rank ``ceil(0.95 n)``) and ``max``.

**Travel time** (s) -- ``t1 - t0`` in simulator seconds. Reported for
every run; it is a *travel* time only when the run succeeded.

**Smoothness** -- two numbers from the controller's own commands in the
window: the RMS of the commanded linear acceleration ``dv/dt`` (m/s^2)
and of the commanded angular acceleration ``dw/dt`` (rad/s^2), each from
consecutive commands (``(v[i+1] - v[i]) / (t[i+1] - t[i])``; pairs with
``dt <= 0`` are skipped and counted). Lower is smoother. It measures the
controller, not the robot: the smoother and the monitor downstream are
the same for all three.

**Minimum clearance** (m) -- the smallest distance, over GT samples in
the window, between the robot's footprint and any obstacle. The footprint
is the rectangle enclosing chassis and wheels, ``FOOTPRINT`` = 0.297 x
0.314 m centred on base_footprint (derived from coco_config, the same
rectangle Lab 1 sweeps). Box clearance is the exact distance between two
convex polygons; actor clearance is the distance from the rectangle to the
cylinder's axis minus its radius. Either is ``0`` when the shapes overlap,
and ``contact`` is then true. Reported overall, against the static world
and against the actors separately, each with the time and the obstacle
that set it.

Contacts with actors are never felt in the simulator (they have no
collision geometry, ``coco_lab_ros.actors``); this is where they are
counted.
"""

import bisect
import math
from typing import Dict, List, Optional, Sequence, Tuple

#: (length along x, width along y), metres; centred on base_footprint.
FOOTPRINT = (0.297, 0.314)

Box = Tuple[float, float, float, float]


# -- tracking ----------------------------------------------------------------

def point_segment_distance(p, a, b) -> float:
    """Return the distance from point ``p`` to segment ``ab``."""
    ax, ay = a[0], a[1]
    dx, dy = b[0] - ax, b[1] - ay
    den = dx * dx + dy * dy
    if den == 0.0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / den))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def distance_to_polyline(p, poly) -> float:
    """Return the distance from ``p`` to the nearest point of ``poly``."""
    if len(poly) == 1:
        return math.hypot(p[0] - poly[0][0], p[1] - poly[0][1])
    return min(point_segment_distance(p, a, b)
               for a, b in zip(poly, poly[1:]))


def nearest_rank(values: Sequence[float], q: float) -> float:
    """Return the nearest-rank ``q``-quantile (1-based rank ceil(q n))."""
    if not values:
        raise ValueError('no values')
    s = sorted(values)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def tracking(gt, path) -> Dict[str, object]:
    """Return ``{n, mean, p95, max}`` of the GT samples' path distances."""
    xy = [(q[0], q[1]) for q in path]
    d = [distance_to_polyline((s[1], s[2]), xy) for s in gt]
    if not d:
        return {'n': 0, 'mean': None, 'p95': None, 'max': None}
    return {'n': len(d), 'mean': sum(d) / len(d),
            'p95': nearest_rank(d, 0.95), 'max': max(d)}


# -- smoothness --------------------------------------------------------------

def smoothness(cmd) -> Dict[str, object]:
    """Return the RMS commanded accelerations (see the module doc)."""
    av, aw, skipped = [], [], 0
    for (t0, v0, w0), (t1, v1, w1) in zip(cmd, cmd[1:]):
        dt = t1 - t0
        if dt <= 0.0:
            skipped += 1
            continue
        av.append((v1 - v0) / dt)
        aw.append((w1 - w0) / dt)

    def rms(xs):
        return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else None
    return {'n': len(av), 'rms_linear_accel': rms(av),
            'rms_angular_accel': rms(aw), 'skipped_pairs': skipped}


# -- clearance ---------------------------------------------------------------

def footprint_corners(x, y, yaw, size=FOOTPRINT):
    """Return the footprint rectangle's corners, counter-clockwise."""
    hl, hw = size[0] / 2.0, size[1] / 2.0
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x + c * px - s * py, y + s * px + c * py)
            for px, py in ((hl, hw), (-hl, hw), (-hl, -hw), (hl, -hw))]


def box_corners(box: Box):
    """Return an axis-aligned box's corners, counter-clockwise."""
    cx, cy, sx, sy = box
    hx, hy = sx / 2.0, sy / 2.0
    return [(cx + hx, cy + hy), (cx - hx, cy + hy), (cx - hx, cy - hy),
            (cx + hx, cy - hy)]


def _axes(poly):
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        n = math.hypot(ex, ey)
        out.append((-ey / n, ex / n))
    return out


def convex_overlap(a, b) -> bool:
    """Return whether two convex polygons overlap (separating axes)."""
    for ax in _axes(a) + _axes(b):
        pa = [p[0] * ax[0] + p[1] * ax[1] for p in a]
        pb = [p[0] * ax[0] + p[1] * ax[1] for p in b]
        if max(pa) < min(pb) or max(pb) < min(pa):
            return False
    return True


def polygon_distance(a, b) -> float:
    """Return the distance between convex polygons; 0 if they overlap."""
    if convex_overlap(a, b):
        return 0.0
    best = math.inf
    for p, poly in ((pt, b) for pt in a):
        for e0, e1 in zip(poly, poly[1:] + poly[:1]):
            best = min(best, point_segment_distance(p, e0, e1))
    for p, poly in ((pt, a) for pt in b):
        for e0, e1 in zip(poly, poly[1:] + poly[:1]):
            best = min(best, point_segment_distance(p, e0, e1))
    return best


def point_polygon_distance(p, poly) -> float:
    """Return the distance from ``p`` to a convex polygon; 0 if inside."""
    inside = True
    for e0, e1 in zip(poly, poly[1:] + poly[:1]):
        cross = (e1[0] - e0[0]) * (p[1] - e0[1]) - \
            (e1[1] - e0[1]) * (p[0] - e0[0])
        if cross < 0:
            inside = False
            break
    if inside:
        return 0.0
    return min(point_segment_distance(p, e0, e1)
               for e0, e1 in zip(poly, poly[1:] + poly[:1]))


def interpolate_track(track, t) -> Optional[Tuple[float, float]]:
    """Return an actor's ``(x, y)`` at ``t``; None outside its samples."""
    if not track or t < track[0][0] or t > track[-1][0]:
        return None
    ts = [s[0] for s in track]
    i = bisect.bisect_left(ts, t)
    if ts[i] == t:
        return track[i][1], track[i][2]
    a, b = track[i - 1], track[i]
    f = (t - a[0]) / (b[0] - a[0])
    return a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])


def clearance(gt, boxes: Sequence[Box], actors=(), reach: float = 3.0
              ) -> Dict[str, object]:
    """
    Return the minimum clearances (see the module doc).

    ``reach``: boxes whose centre is farther than ``reach`` plus their
    half-diagonal from the robot are skipped -- an exact prune, since no
    point of such a box can be within ``reach`` of the robot's centre,
    and the robot's own half-diagonal (0.216 m) is less than ``reach``.
    """
    rad = math.hypot(FOOTPRINT[0], FOOTPRINT[1]) / 2.0
    corners = [box_corners(b) for b in boxes]
    half_diag = [math.hypot(b[2], b[3]) / 2.0 for b in boxes]
    none = (math.inf, None, None)
    best = {'static': none, 'actor': none}
    for t, x, y, yaw in gt:
        fp = footprint_corners(x, y, yaw)
        for i, b in enumerate(boxes):
            if math.hypot(b[0] - x, b[1] - y) - half_diag[i] > reach + rad:
                continue
            d = polygon_distance(fp, corners[i])
            if d < best['static'][0]:
                best['static'] = (d, t, i)
        for j, a in enumerate(actors):
            p = interpolate_track(a['track'], t)
            if p is None:
                continue
            d = max(0.0, point_polygon_distance(p, fp) - a['radius'])
            if d < best['actor'][0]:
                best['actor'] = (d, t, j)

    def out(k):
        d, t, i = best[k]
        return {'min_m': None if d == math.inf else d, 't': t, 'index': i}
    s, a = out('static'), out('actor')
    vals = [v['min_m'] for v in (s, a) if v['min_m'] is not None]
    overall = min(vals) if vals else None
    return {'min_m': overall, 'static': s, 'actor': a,
            'contact': overall is not None and overall <= 0.0}


# -- one run -----------------------------------------------------------------

def in_window(samples, t0, t1):
    """Return the samples with ``t0 <= t <= t1``."""
    return [s for s in samples if t0 <= s[0] <= t1]


def evaluate(path, gt, window, cmd, boxes, actors=()) -> Dict[str, object]:
    """Return all four metrics for one run (see the module doc)."""
    t0, t1 = window
    g = in_window(gt, t0, t1)
    c = in_window(cmd, t0, t1)
    return {
        'tracking_m': tracking(g, path),
        'time_s': t1 - t0,
        'smoothness': smoothness(c),
        'clearance': clearance(g, boxes, actors),
        'samples': {'gt': len(g), 'cmd': len(c)},
    }


def boxes_in_map(world_boxes, world_to_map) -> List[Box]:
    """Return ``navigation_world.json`` boxes as map-frame ``Box`` tuples."""
    dx, dy = world_to_map
    return [(b['pose'][0] + dx, b['pose'][1] + dy, b['size'][0], b['size'][1])
            for b in world_boxes]


def distribution(values: Sequence[float]) -> Dict[str, object]:
    """Return ``{n, min, median, max}`` (median: mean of the middle two)."""
    s = sorted(v for v in values if v is not None)
    if not s:
        return {'n': 0, 'min': None, 'median': None, 'max': None}
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {'n': n, 'min': s[0], 'median': med, 'max': s[-1]}
