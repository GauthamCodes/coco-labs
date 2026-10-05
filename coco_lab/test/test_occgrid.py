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

"""Occupancy-grid mapping with known poses: the log-odds update, exactly."""

import math
import random

from coco_lab import loc_teaching, mapeval, mapping, mapworld, occgrid
from coco_lab.maps import FREE, OCCUPIED, UNKNOWN
from coco_lab.sketch import LidarSpec, Noise, Scenario
from hypothesis import given, settings
from hypothesis import strategies as st
import pytest


@given(st.integers(-40, 40), st.integers(-40, 40), st.integers(-40, 40),
       st.integers(-40, 40))
@settings(max_examples=1000, deadline=None)
def test_bresenham_joins_its_end_points_with_8_neighbour_steps(x0, y0, x1,
                                                               y1):
    cells = occgrid.bresenham(x0, y0, x1, y1)
    assert cells[0] == (x0, y0) and cells[-1] == (x1, y1)
    assert len(cells) == max(abs(x1 - x0), abs(y1 - y0)) + 1
    for (a, b), (c, d) in zip(cells, cells[1:]):
        assert max(abs(c - a), abs(d - b)) == 1


def _grid(**kw):
    return occgrid.OccupancyGrid(20, 10, 0.1, (0.0, 0.0),
                                 occgrid.GridParams(**kw))


def test_one_beam_adds_l_occ_at_its_end_and_l_free_on_the_way():
    g = _grid()
    p = g.params
    # sensor at the centre of cell (2, 5), beam along +x, range 1.0 m
    g.integrate((0.25, 0.55, 0.0), [1.0], [0.0], (0.0, 0.0, 0.0), 0.1, 5.0)
    row = [g.logodds[ix + 5 * g.width] for ix in range(g.width)]
    assert row[12] == pytest.approx(p.l_occ)
    for ix in range(2, 12):
        assert row[ix] == pytest.approx(p.l_free)
    assert all(v == 0.0 for v in row[13:]) and row[1] == 0.0
    assert sum(g.seen) == 11


def test_a_beam_with_no_return_marks_nothing_occupied():
    g = _grid()
    g.integrate((0.25, 0.55, 0.0), [math.inf], [0.0], (0.0, 0.0, 0.0), 0.1,
                5.0)
    assert sum(g.seen) == 0
    g2 = _grid(miss_range=0.5)
    g2.integrate((0.25, 0.55, 0.0), [math.inf], [0.0], (0.0, 0.0, 0.0), 0.1,
                 5.0)
    assert max(g2.logodds) == 0.0 and min(g2.logodds) < 0
    assert sum(g2.seen) == 6


def test_below_range_min_is_skipped():
    g = _grid()
    g.integrate((0.25, 0.55, 0.0), [0.05], [0.0], (0.0, 0.0, 0.0), 0.1, 5.0)
    assert sum(g.seen) == 0


def test_the_clamp_holds():
    g = _grid(l_max=2.0, l_min=-1.0)
    for _ in range(10):
        g.integrate((0.25, 0.55, 0.0), [1.0], [0.0], (0.0, 0.0, 0.0), 0.1,
                    5.0)
    assert max(g.logodds) == 2.0 and min(g.logodds) == -1.0


@given(st.lists(st.tuples(st.floats(0.5, 1.5), st.floats(0.3, 0.7),
                          st.floats(-math.pi, math.pi),
                          st.floats(0.2, 1.4)), min_size=2, max_size=8),
       st.randoms(use_true_random=False))
@settings(max_examples=200, deadline=None)
def test_without_the_clamp_the_order_of_scans_does_not_matter(scans, rnd):
    """Adding log-odds is Bayes' rule for independent measurements."""
    def build(order):
        g = _grid(l_min=-1e9, l_max=1e9)
        for x, y, th, z in order:
            g.integrate((x, y, th), [z], [0.0], (0.0, 0.0, 0.0), 0.1, 5.0)
        return g
    a = build(scans)
    shuffled = list(scans)
    rnd.shuffle(shuffled)
    b = build(shuffled)
    assert a.seen == b.seen
    for u, v in zip(a.logodds, b.logodds):
        assert u == pytest.approx(v, abs=1e-9)


def test_u8_follows_nav_msgs_occupancy_grid():
    g = _grid()
    g.integrate((0.25, 0.55, 0.0), [1.0], [0.0], (0.0, 0.0, 0.0), 0.1, 5.0)
    u8 = g.to_u8()
    # north row first: grid row iy = 5 is LabMap row height - 1 - 5 = 4
    row = u8[4 * g.width:5 * g.width]
    assert row[12] == round(100 - 100 / (1 + math.exp(g.params.l_occ)))
    assert row[5] == round(100 - 100 / (1 + math.exp(g.params.l_free)))
    assert row[15] == occgrid.U8_UNKNOWN
    lm = g.to_labmap()
    # one hit: p = 0.70 >= 0.65, occupied; one pass: p = 0.40, neither
    assert lm.at((4, 12)) == OCCUPIED
    assert lm.at((4, 5)) == UNKNOWN
    assert lm.at((4, 15)) == UNKNOWN


def test_u8_thresholds_are_nav2s():
    cells = bytes([0, 25, 26, 64, 65, 100, 255])
    lm = occgrid.u8_to_labmap(cells, 7, 1, 0.1, (0.0, 0.0))
    assert list(lm.occupancy) == [FREE, FREE, UNKNOWN, UNKNOWN, OCCUPIED,
                                  OCCUPIED, UNKNOWN]


def test_known_poses_on_a_noise_free_world_reproduce_the_walls():
    """The map Lab 3 calls 'localisation solved' is right where it looked."""
    m = loc_teaching.landmarks_map()
    sc = Scenario(start=(1.5, 1.5, 0.0), route=loc_teaching.LANDMARKS_ROUTE,
                  seed=0, noise=Noise(odom_alphas=(0.0,) * 4,
                                      range_sigma=0.0))
    w = mapworld.from_sketch(m, sc)
    tr = mapping.run('known', w.inputs(), m, true_poses=w.true_poses())
    truth = mapeval.Truth(m, sc.start[:2])
    s = mapeval.score_map(truth, occgrid.u8_to_labmap(
        tr.maps[-1], m.width, m.height, m.resolution, m.origin), 0.10)
    assert s['precision'] == 1.0
    # one lap sees nearly every wall, not every last cell of them
    assert s['recall'] >= 0.9


def test_odometry_mapping_is_the_same_mapping_with_other_poses():
    m = loc_teaching.landmarks_map()
    sc = Scenario(start=(1.5, 1.5, 0.0), route=loc_teaching.LANDMARKS_ROUTE,
                  seed=3)
    w = mapworld.from_sketch(m, sc)
    inp = w.inputs()
    from coco_lab import slam
    a = mapping.run('odometry', inp, m)
    b = mapping.run_given_poses('known', inp, m, slam.dead_reckon(inp))
    assert a.maps == b.maps


def test_dead_reckoning_is_exact_composition():
    from coco_lab import slam
    rnd = random.Random(4)
    odom = [(0.0, 0.0, 0.0)]
    for _ in range(50):
        x, y, th = odom[-1]
        d = rnd.uniform(0, 0.3)
        th2 = th + rnd.uniform(-0.4, 0.4)
        odom.append((x + d * math.cos(th2), y + d * math.sin(th2), th2))
    start = (2.0, -1.0, 0.7)
    inp = slam.SlamInputs(list(range(51)), [float(i) for i in range(51)],
                          odom, [[1.0]] * 51,
                          LidarSpec(1, 0.0, 0.0, 0.1, 5.0), start)
    dr = slam.dead_reckon(inp)
    c, s = math.cos(0.7), math.sin(0.7)
    for (ox, oy, oth), (x, y, th) in zip(odom, dr):
        assert x == pytest.approx(2.0 + c * ox - s * oy, abs=1e-9)
        assert y == pytest.approx(-1.0 + s * ox + c * oy, abs=1e-9)
        assert math.remainder(th - (oth + 0.7), 2 * math.pi) == \
            pytest.approx(0.0, abs=1e-9)
