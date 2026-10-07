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

"""Lab 5's metric definitions (coco_lab.movemetrics), checked by hand."""

import math
import random

from coco_lab import movemetrics as mm
import pytest

HL, HW = mm.FOOTPRINT[0] / 2, mm.FOOTPRINT[1] / 2


def test_the_footprint_is_lab_ones_rectangle():
    # length max(chassis, wheelbase + 2r), width max(chassis, track + w):
    # the rectangle Lab 1 sweeps (lab_web/tools/build_catalog.py)
    assert mm.FOOTPRINT == (0.297, 0.314)


# -- tracking ------------------------------------------------------------------

def test_tracking_is_distance_to_the_polyline():
    path = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
    gt = [(0, 0.5, 0.0, 0), (1, 0.5, 0.2, 0), (2, 1.3, 0.5, 0),
          (3, 1.0, 1.0, 0)]
    t = mm.tracking(gt, path)
    assert t['n'] == 4
    assert t['max'] == pytest.approx(0.3)
    assert t['mean'] == pytest.approx((0 + 0.2 + 0.3 + 0) / 4)
    assert t['p95'] == pytest.approx(0.3)      # rank ceil(0.95 x 4) = 4


def test_p95_is_nearest_rank():
    assert mm.nearest_rank(list(range(1, 21)), 0.95) == 19
    assert mm.nearest_rank([5.0], 0.95) == 5.0


def test_no_samples_no_numbers():
    assert mm.tracking([], [(0, 0, 0), (1, 0, 0)])['mean'] is None


# -- smoothness ----------------------------------------------------------------

def test_constant_commands_are_perfectly_smooth():
    s = mm.smoothness([(0.1 * i, 0.3, 0.2) for i in range(20)])
    assert s['rms_linear_accel'] == 0 and s['rms_angular_accel'] == 0
    assert s['n'] == 19


def test_rms_acceleration_is_exact():
    # v: 0, 0.1, 0.3 at dt 0.1 -> a 1.0, 2.0 -> rms sqrt(2.5)
    cmd = [(0.0, 0.0, 0.0), (0.1, 0.1, 0.5), (0.2, 0.3, 0.0)]
    s = mm.smoothness(cmd)
    assert s['rms_linear_accel'] == pytest.approx(math.sqrt(2.5))
    assert s['rms_angular_accel'] == pytest.approx(math.sqrt((25 + 25) / 2))


def test_non_increasing_times_are_skipped_and_counted():
    s = mm.smoothness([(0.0, 0, 0), (0.0, 1, 1), (0.1, 1, 1)])
    assert s['skipped_pairs'] == 1 and s['n'] == 1
    assert mm.smoothness([])['rms_linear_accel'] is None


# -- clearance -------------------------------------------------------------------

def test_box_clearance_axis_aligned_and_rotated():
    box = [(1.0, 0.0, 0.2, 0.2)]
    c = mm.clearance([(0, 0.0, 0.0, 0.0)], box)
    assert c['static']['min_m'] == pytest.approx(1.0 - 0.1 - HL)
    c = mm.clearance([(0, 0.0, 0.0, math.pi / 2)], box)
    assert c['static']['min_m'] == pytest.approx(1.0 - 0.1 - HW)
    assert not c['contact']


def test_a_corner_to_corner_gap_is_euclidean():
    # box's lower-left corner diagonal from the robot's upper-right corner
    box = (HL + 0.3 + 0.5, HW + 0.4 + 0.5, 1.0, 1.0)
    c = mm.clearance([(0, 0.0, 0.0, 0.0)], [box])
    assert c['static']['min_m'] == pytest.approx(0.5)


def test_overlap_is_zero_and_contact():
    c = mm.clearance([(0, 0.0, 0.0, 0.3)], [(0.1, 0.0, 0.2, 0.2)])
    assert c['min_m'] == 0.0 and c['contact']


def test_actor_clearance_is_to_the_cylinder():
    actors = [{'radius': 0.15, 'track': [(0.0, 1.0, 0.0), (10.0, 1.0, 0.0)]}]
    c = mm.clearance([(5.0, 0.0, 0.0, 0.0)], [], actors)
    assert c['actor']['min_m'] == pytest.approx(1.0 - HL - 0.15)
    assert c['static']['min_m'] is None
    assert c['min_m'] == c['actor']['min_m']


def test_actor_track_is_interpolated_never_extrapolated():
    tr = [(0.0, 0.0, 0.0), (2.0, 2.0, 0.0)]
    assert mm.interpolate_track(tr, 1.0) == (1.0, 0.0)
    assert mm.interpolate_track(tr, 2.5) is None
    actors = [{'radius': 0.15, 'track': tr}]
    c = mm.clearance([(9.0, 0.0, 0.0, 0.0)], [], actors)
    assert c['actor']['min_m'] is None


def test_an_actor_walking_through_the_robot_is_a_contact():
    actors = [{'radius': 0.15, 'track': [(0.0, -1.0, 0.0), (2.0, 1.0, 0.0)]}]
    gt = [(t / 10, 0.0, 0.0, 0.0) for t in range(21)]
    c = mm.clearance(gt, [], actors)
    assert c['contact'] and c['actor']['min_m'] == 0.0


def test_polygon_distance_matches_brute_force():
    rng = random.Random(11)
    for _ in range(300):
        a = mm.footprint_corners(rng.uniform(-2, 2), rng.uniform(-2, 2),
                                 rng.uniform(-3.2, 3.2))
        box = (rng.uniform(-2, 2), rng.uniform(-2, 2),
               rng.uniform(0.05, 1.5), rng.uniform(0.05, 1.5))
        b = mm.box_corners(box)
        d = mm.polygon_distance(a, b)
        assert d == pytest.approx(mm.polygon_distance(b, a))
        if d == 0.0:
            assert mm.convex_overlap(a, b)
            continue
        # brute force: densely sampled boundaries, never below the exact

        def edge_pts(poly):
            for p, q in zip(poly, poly[1:] + poly[:1]):
                for k in range(41):
                    f = k / 40
                    yield (p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1]))
        brute = min(math.hypot(p[0] - q[0], p[1] - q[1])
                    for p in edge_pts(a) for q in edge_pts(b))
        assert d <= brute + 1e-12
        assert brute - d < 0.05


def test_far_boxes_are_pruned_exactly():
    near = (1.0, 0.0, 0.2, 0.2)
    far = (50.0, 0.0, 0.2, 0.2)
    c = mm.clearance([(0, 0.0, 0.0, 0.0)], [far, near])
    assert c['static']['index'] == 1


# -- one run ----------------------------------------------------------------------

def test_evaluate_uses_only_the_window():
    path = [(0, 0, 0), (10, 0, 0)]
    gt = [(t, t * 0.3, 0.0 if t < 10 else 5.0, 0) for t in range(20)]
    cmd = [(t * 0.1, 0.3, 0.0) for t in range(200)]
    r = mm.evaluate(path, gt, (0.0, 9.0), cmd, [(20.0, 0.0, 0.2, 0.2)])
    assert r['tracking_m']['max'] == 0.0
    assert r['time_s'] == 9.0
    assert r['samples'] == {'gt': 10, 'cmd': 91}


def test_boxes_in_map_shift_by_world_to_map():
    b = mm.boxes_in_map([{'name': 'x', 'pose': [1, 2, 0.5],
                          'size': [3, 4, 1]}], [2, 0])
    assert b == [(3, 2, 3, 4)]


def test_distribution():
    assert mm.distribution([3, 1, 2, None]) == {'n': 3, 'min': 1,
                                                'median': 2, 'max': 3}
    assert mm.distribution([1, 2, 3, 4])['median'] == 2.5
    assert mm.distribution([])['n'] == 0
