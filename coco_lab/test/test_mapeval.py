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

"""Lab 3's metrics do what their definitions say (coco_lab.mapeval)."""

import math
import random

from coco_lab import loc_teaching, mapeval
from coco_lab.maps import FREE, LabMap, OCCUPIED, UNKNOWN
from hypothesis import given, settings
from hypothesis import strategies as st
import pytest


@given(st.floats(-5, 5), st.floats(-5, 5), st.floats(-math.pi, math.pi),
       st.integers(0, 2 ** 31))
@settings(max_examples=1000, deadline=None)
def test_alignment_recovers_a_rigid_transform_exactly(tx, ty, th, seed):
    rnd = random.Random(seed)
    est = [(rnd.uniform(-10, 10), rnd.uniform(-10, 10), 0.0)
           for _ in range(12)]
    truth = [mapeval.apply_se2((tx, ty, th), p) for p in est]
    a = mapeval.ate(est, truth, align=True)
    assert a['rmse'] == pytest.approx(0.0, abs=1e-9)
    T = a['alignment']
    assert T[0] == pytest.approx(tx, abs=1e-7)
    assert T[1] == pytest.approx(ty, abs=1e-7)
    assert math.remainder(T[2] - th, 2 * math.pi) == pytest.approx(
        0.0, abs=1e-9)


def test_ate_without_alignment_is_the_plain_error():
    est = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    truth = [(0.0, 3.0, 0.0), (1.0, 4.0, 0.0)]
    a = mapeval.ate(est, truth, align=False)
    assert (a['mean'], a['max'], a['final']) == (3.5, 4.0, 4.0)
    assert a['rmse'] == pytest.approx(math.sqrt((9 + 16) / 2))
    # aligned: the best rigid fit ROTATES (1, 0) onto (1, 1) / sqrt(2)
    # and centres it, leaving sqrt(2) (0.5 - 0.5 / sqrt(2)) at both ends
    b = mapeval.ate(est, truth, align=True)
    assert b['rmse'] == pytest.approx(0.5 * math.sqrt(2) - 0.5, abs=1e-12)


def test_alignment_never_increases_the_error():
    rnd = random.Random(7)
    for _ in range(200):
        est = [(rnd.uniform(-5, 5), rnd.uniform(-5, 5), 0.0)
               for _ in range(8)]
        truth = [(x + rnd.gauss(0, 0.3), y + rnd.gauss(0, 0.3), 0.0)
                 for x, y, _ in est]
        assert mapeval.ate(est, truth, True)['rmse'] <= \
            mapeval.ate(est, truth, False)['rmse'] + 1e-12


def _room():
    return loc_teaching.landmarks_map()


def test_a_map_scored_against_itself_is_perfect():
    m = _room()
    T = mapeval.Truth(m, (1.5, 1.5))
    s = mapeval.score_map(T, m)
    assert (s['precision'], s['recall'], s['f1']) == (1.0, 1.0, 1.0)
    assert s['coverage'] == 1.0
    assert s['exact']['precision'] == 1.0 and s['exact']['recall'] == 1.0


def _shift(m: LabMap, dcol: int) -> LabMap:
    w, h = m.width, m.height
    occ = bytearray([FREE]) * (w * h)
    for r in range(h):
        for c in range(w):
            v = m.occupancy[r * w + c]
            c2 = c + dcol
            if 0 <= c2 < w and v == OCCUPIED:
                occ[r * w + c2] = OCCUPIED
    return LabMap(w, h, bytes(occ), resolution=m.resolution, origin=m.origin)


def test_the_tolerance_forgives_one_cell_and_exact_does_not():
    m = _room()
    T = mapeval.Truth(m, (1.5, 1.5))
    s = mapeval.score_map(T, _shift(m, 1), tol=0.10)
    assert s['precision'] == 1.0 and s['recall'] == 1.0
    assert s['exact']['precision'] < 0.9
    s3 = mapeval.score_map(T, _shift(m, 3), tol=0.10)
    assert s3['precision'] < 0.9


def test_unseen_walls_are_not_counted_and_unknown_is_not_coverage():
    m = _room()
    T = mapeval.Truth(m, (1.5, 1.5))
    # a box's interior is occupied truth but not a visible wall
    assert T.n_walls < m.count(OCCUPIED)
    blank = LabMap(m.width, m.height, bytes([UNKNOWN]) * (m.width *
                                                          m.height),
                   resolution=m.resolution, origin=m.origin)
    s = mapeval.score_map(T, blank)
    assert s['coverage'] == 0.0 and s['recall'] == 0.0
    assert s['precision'] is None and s['f1'] == 0.0


def test_reachable_stays_inside_the_walls():
    m = _room()
    reach = mapeval.reachable(m, (1.5, 1.5))
    # the outermost ring of cells is wall: never reachable
    w, h = m.width, m.height
    for c in range(w):
        assert not reach[c] and not reach[(h - 1) * w + c]
    assert sum(reach) == T_free_inside(m)


def T_free_inside(m):
    # every FREE cell of the landmarks room is connected to the start
    return m.count(FREE)


def test_the_diff_raster_counts_what_the_score_counts():
    m = _room()
    T = mapeval.Truth(m, (1.5, 1.5))
    test = _shift(m, 2)
    s = mapeval.score_map(T, test, tol=0.10)
    d = mapeval.diff_raster(T, test, tol=0.10)
    found = d.count(mapeval.DIFF_FOUND)
    false = d.count(mapeval.DIFF_FALSE)
    assert found + false == s['occupied_cells']
    assert found / (found + false) == pytest.approx(s['precision'])
    missed = d.count(mapeval.DIFF_MISSED)
    assert 1 - missed / T.n_walls <= s['recall'] + 1e-12


def test_resampling_onto_the_same_grid_is_the_identity():
    m = _room()
    cells = bytes(random.Random(1).randrange(256) for _ in range(
        m.width * m.height))
    out = mapeval.resample_onto(m, cells, m.width, m.height, m.resolution,
                                m.origin)
    assert out == cells


def test_resampling_follows_the_alignment():
    m = _room()
    cells = bytearray([0]) * (m.width * m.height)
    # one marked cell, then move the map by exactly 1 m in x
    cells[10 * m.width + 20] = 100
    out = mapeval.resample_onto(m, bytes(cells), m.width, m.height,
                                m.resolution, m.origin, (1.0, 0.0, 0.0))
    assert out[10 * m.width + 30] == 100
