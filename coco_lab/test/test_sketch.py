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
Sketch, the browser's robot model: geometry, motion, noise, determinism.

Every property the Localise lab leans on is checked here: the ray caster
against exact distances, the distance transform against brute force, the
unicycle against its closed form, the odometry model's decomposition, the
kidnap's meaning (truth jumps, odometry does not), the twins room's
symmetry, and that one scenario always gives one run.
"""

import math
import random

from coco_lab import loc_teaching, sketch
from coco_lab.maps import FREE, LabMap, OCCUPIED, Raster
from hypothesis import given, settings, strategies as st


def _box_room(w_m=6.0, h_m=4.0, res=0.1):
    r = Raster(int(w_m / res), int(h_m / res), res, (0.0, 0.0))
    for rect in ((0, w_m, 0, res), (0, w_m, h_m - res, h_m),
                 (0, res, 0, h_m), (w_m - res, w_m, 0, h_m)):
        r.paint(*rect, OCCUPIED, rule='overlap')
    return r.build('box', frame='map')


ROOM = sketch.SketchMap(_box_room())


@settings(max_examples=300, derandomize=True, database=None,
          deadline=None)
@given(st.floats(0.5, 5.5), st.floats(0.5, 3.5), st.floats(-math.pi, math.pi))
def test_a_ray_stops_at_the_inner_wall_face(x, y, a):
    """In an empty 6 x 4 m room with 0.1 m walls, the range is analytic."""
    r = ROOM.cast(x, y, a, 20.0)
    c, s = math.cos(a), math.sin(a)
    ts = []
    if c > 1e-12:
        ts.append((5.9 - x) / c)
    if c < -1e-12:
        ts.append((0.1 - x) / c)
    if s > 1e-12:
        ts.append((3.9 - y) / s)
    if s < -1e-12:
        ts.append((0.1 - y) / s)
    assert abs(r - min(ts)) < 1e-9


def test_a_subnormal_heading_is_axis_parallel_not_nan():
    """Regression: 1/sin(-3.4e-309) overflowed and 0 * inf gave NaN."""
    assert ROOM.cast(1.0, 1.0, -3.433219430118553e-309, 20.0) == \
        ROOM.cast(1.0, 1.0, 0.0, 20.0)


def test_a_ray_with_nothing_in_range_returns_inf():
    assert ROOM.cast(3.0, 2.0, 0.0, 1.0) == math.inf
    assert ROOM.cast(3.0, 2.0, 0.0, 3.0) < math.inf


def test_a_ray_from_inside_a_wall_is_zero():
    assert ROOM.cast(0.05, 2.0, 0.0, 10.0) == 0.0


@settings(max_examples=60, derandomize=True, database=None,
          deadline=None)
@given(st.integers(0, 2 ** 32 - 1), st.integers(1, 25), st.integers(1, 25),
       st.floats(0.0, 0.5))
def test_the_distance_transform_is_exact(seed, w, h, density):
    rng = random.Random(seed)
    blocked = [1 if rng.random() < density else 0 for _ in range(w * h)]
    d = sketch.edt(blocked, w, h)
    pts = [(i % w, i // w) for i, b in enumerate(blocked) if b]
    for i in range(w * h):
        want = min((math.hypot(i % w - x, i // w - y) for x, y in pts),
                   default=math.inf)
        assert d[i] == want or abs(d[i] - want) < 1e-9


@settings(max_examples=300, derandomize=True, database=None,
          deadline=None)
@given(st.floats(-5, 5), st.floats(-5, 5), st.floats(-3.1, 3.1),
       st.floats(-0.5, 0.5), st.floats(-1.5, 1.5), st.floats(0.01, 2.0))
def test_the_unicycle_step_is_its_closed_form(x, y, th, v, w, dt):
    x2, y2, th2 = sketch.step_pose((x, y, th), v, w, dt)
    # integrate the ODE finely; the closed form must agree
    n = 4000
    px, py, pth = x, y, th
    h = dt / n
    for _ in range(n):
        # midpoint rule on the heading
        mid = pth + w * h / 2
        px += v * h * math.cos(mid)
        py += v * h * math.sin(mid)
        pth += w * h
    assert abs(x2 - px) < 1e-6 and abs(y2 - py) < 1e-6
    assert abs(sketch.wrap(th2 - pth)) < 1e-9


@settings(max_examples=300, derandomize=True, database=None,
          deadline=None)
@given(st.floats(-5, 5), st.floats(-5, 5), st.floats(-3.1, 3.1),
       st.floats(-5, 5), st.floats(-5, 5), st.floats(-3.1, 3.1))
def test_odometry_delta_round_trips(x, y, th, x2, y2, th2):
    a, b = (x, y, th), (x2, y2, th2)
    r1, t, r2 = sketch.odom_delta(a, b)
    c = sketch.apply_delta(a, r1, t, r2)
    # a move under 1 mm is decomposed as a pure rotation by design (so a
    # turn in place is one rotation), which misplaces it by under 2 mm
    tol = 1e-9 if t > 1e-3 else 2.1e-3
    assert abs(c[0] - b[0]) < tol and abs(c[1] - b[1]) < tol
    assert abs(sketch.wrap(c[2] - b[2])) < 1e-9


def test_zero_alphas_add_no_odometry_noise():
    rng = random.Random(0)
    assert sketch.sample_delta(0.3, 1.0, -0.2, (0, 0, 0, 0), rng) == \
        (0.3, 1.0, -0.2)


def test_the_noise_stream_does_not_depend_on_the_alphas():
    a, b = random.Random(5), random.Random(5)
    sketch.sample_delta(0.1, 0.2, 0.3, (0, 0, 0, 0), a)
    sketch.sample_delta(0.1, 0.2, 0.3, (1, 1, 1, 1), b)
    assert a.random() == b.random()


def _scenario(**kw):
    base = {'start': (1.5, 1.5, 0.0), 'route': [(4.5, 1.5), (4.5, 2.8)],
            'seed': 11}
    base.update(kw)
    return sketch.Scenario(**base)


def test_one_scenario_gives_one_run_bit_for_bit():
    a = sketch.simulate(ROOM, _scenario())
    b = sketch.simulate(ROOM, _scenario())
    assert (a.t, a.gt, a.odom, a.cmd, a.updates, a.ranges) == \
        (b.t, b.gt, b.odom, b.cmd, b.updates, b.ranges)
    c = sketch.simulate(ROOM, _scenario(seed=12))
    assert c.odom != a.odom and c.gt == a.gt  # noise is not the driving


def test_with_no_noise_odometry_is_the_truth_moved_to_its_origin():
    sc = _scenario(noise=sketch.Noise((0, 0, 0, 0), 0.0))
    w = sketch.simulate(ROOM, sc)
    x0, y0, t0 = w.gt[0]
    for (gx, gy, gth), (ox, oy, oth) in zip(w.gt, w.odom):
        # odometry starts at (0, 0, 0): the truth relative to the start
        c, s = math.cos(-t0), math.sin(-t0)
        rx = c * (gx - x0) - s * (gy - y0)
        ry = s * (gx - x0) + c * (gy - y0)
        assert abs(rx - ox) < 1e-9 and abs(ry - oy) < 1e-9
        assert abs(sketch.wrap(gth - t0 - oth)) < 1e-9
    assert w.status == 'route_done'


def test_a_kidnap_moves_the_truth_and_not_the_odometry():
    sc = _scenario(noise=sketch.Noise((0, 0, 0, 0), 0.0),
                   kidnap=sketch.Kidnap(t=3.0, to=(4.0, 3.0, 1.0)))
    w = sketch.simulate(ROOM, sc)
    k = w.kidnap_row
    assert k is not None and abs(w.t[k] - 3.0) < 0.11
    jump_gt = math.hypot(w.gt[k][0] - w.gt[k - 1][0],
                         w.gt[k][1] - w.gt[k - 1][1])
    jump_odom = math.hypot(w.odom[k][0] - w.odom[k - 1][0],
                           w.odom[k][1] - w.odom[k - 1][1])
    assert jump_gt > 1.0
    assert jump_odom < sc.v_max * sc.dt + 1e-9


def test_the_kidnap_scene_carries_the_robot_across_the_room():
    """The lab says the robot is carried 9.2 m: pinned, so it stays true."""
    mid, sc, _ = loc_teaching.scenarios()['kidnap']
    w = sketch.simulate(sketch.SketchMap(loc_teaching.teaching_maps()[mid]),
                        sc)
    a, b = w.gt[w.kidnap_row - 1], w.gt[w.kidnap_row]
    assert round(math.hypot(b[0] - a[0], b[1] - a[1]), 1) == 9.2
    assert abs(w.t[w.kidnap_row] - 40.0) < 0.11


def test_updates_follow_amcl_thresholds():
    w = sketch.simulate(ROOM, _scenario())
    assert w.updates[0] == 0
    for a, b in zip(w.updates, w.updates[1:]):
        r1, t, r2 = sketch.odom_delta(w.odom[a], w.odom[b])
        moved = t >= sketch.UPDATE_MIN_D or \
            abs(sketch.wrap(w.odom[b][2] - w.odom[a][2])) >= \
            sketch.UPDATE_MIN_A
        assert moved
    assert len(w.ranges) == len(w.updates)


def test_noise_free_ranges_are_the_ray_caster_and_sigma_adds_noise():
    sc0 = _scenario(noise=sketch.Noise((0, 0, 0, 0), 0.0))
    w0 = sketch.simulate(ROOM, sc0)
    angles = sc0.lidar.angles()
    for row, z in zip(w0.updates, w0.ranges):
        assert z == sketch.observe(ROOM.scan(w0.gt[row], sc0.lidar, angles),
                                   sc0.lidar, 0.0, random.Random(0))
    w1 = sketch.simulate(ROOM, _scenario(
        noise=sketch.Noise((0, 0, 0, 0), 0.05)))
    diffs = [a - b for za, zb in zip(w0.ranges, w1.ranges)
             for a, b in zip(za, zb) if a < math.inf and b < math.inf]
    sd = math.sqrt(sum(d * d for d in diffs) / len(diffs))
    assert 0.04 < sd < 0.06


def test_coco_lidar_decimation_keeps_the_real_beam_angles():
    full = sketch.COCO_LIDAR.angles()
    dec = sketch.COCO_LIDAR.decimated(8).angles()
    assert len(full) == 480 and len(dec) == 60
    assert all(abs(d - full[8 * i]) < 1e-12 for i, d in enumerate(dec))


def test_the_twins_room_is_symmetric_to_the_ray_caster():
    """A pose and its 180-degree rotation see the same scan (no noise)."""
    sm = sketch.SketchMap(loc_teaching.twins_map())
    lidar = sketch.LidarSpec(72, -math.pi, math.pi * (1 - 2 / 72), 0.15,
                             12.0)  # sensor at the robot centre
    rng = random.Random(4)
    free = sm.free_cells(margin=0.3)
    for _ in range(25):
        ix, iy = free[rng.randrange(len(free))]
        x, y = sm.cell_centre(ix, iy)
        th = rng.uniform(-math.pi, math.pi)
        twin = (loc_teaching.WIDTH_M - x, loc_teaching.HEIGHT_M - y,
                sketch.wrap(th + math.pi))
        a = sm.scan((x, y, th), lidar)
        b = sm.scan(twin, lidar)
        assert all(abs(p - q) < 1e-6 or p == q for p, q in zip(a, b))


def test_the_landmarks_room_is_not_symmetric():
    sm = sketch.SketchMap(loc_teaching.landmarks_map())
    lidar = sketch.LidarSpec(72, -math.pi, math.pi * (1 - 2 / 72), 0.15,
                             12.0)
    p = (3.0, 2.5, 0.0)
    twin = (loc_teaching.WIDTH_M - 3.0, loc_teaching.HEIGHT_M - 2.5, math.pi)
    a, b = sm.scan(p, lidar), sm.scan(twin, lidar)
    assert max(abs(x - y) for x, y in zip(a, b)
               if x < math.inf and y < math.inf) > 1.0


def test_every_teaching_scenario_finishes_its_route():
    maps = loc_teaching.teaching_maps()
    for sid, (mid, sc, _) in loc_teaching.scenarios().items():
        w = sketch.simulate(sketch.SketchMap(maps[mid]), sc)
        assert w.status == 'route_done', sid
        assert (w.kidnap_row is not None) == (sc.kidnap is not None)


def test_the_drive_law_is_shared_and_stops_at_the_waypoint():
    assert sketch.drive_command((0, 0, 0), (0.05, 0.0), 0.3, 1.0, 0.1) \
        is None
    v, w = sketch.drive_command((0, 0, 0), (2.0, 0.0), 0.3, 1.0, 0.1)
    assert (v, w) == (0.3, 0.0)
    v, w = sketch.drive_command((0, 0, 0), (0.0, 2.0), 0.3, 1.0, 0.1)
    assert v == 0.0 and w == 1.0  # turn in place first


def test_a_blocked_start_or_kidnap_is_refused():
    try:
        sketch.simulate(ROOM, _scenario(start=(0.05, 2.0, 0.0)))
    except ValueError:
        pass
    else:
        raise AssertionError('a start inside a wall was accepted')
    try:
        sketch.simulate(ROOM, _scenario(
            kidnap=sketch.Kidnap(1.0, (0.05, 2.0, 0.0))))
    except ValueError:
        pass
    else:
        raise AssertionError('a kidnap into a wall was accepted')


def test_scenario_round_trips_through_its_dict():
    sc = _scenario(kidnap=sketch.Kidnap(3.0, (4.0, 3.0, 1.0)))
    again = sketch.Scenario.from_dict(sc.to_dict())
    assert again.to_dict() == sc.to_dict()


def test_unknown_cells_block_rays_like_walls():
    occ = bytearray([FREE] * 100)
    occ[5 * 10 + 7] = 2  # unknown
    m = LabMap(10, 10, bytes(occ), resolution=1.0, origin=(0.0, 0.0),
               frame='map')
    sm = sketch.SketchMap(m)
    assert abs(sm.cast(0.5, 4.5, 0.0, 20.0) - 6.5) < 1e-9
