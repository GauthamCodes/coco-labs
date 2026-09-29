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

"""The real-run metric definitions, on synthetic streams."""

from coco_lab_ros import run_analysis as ra
import pytest

GT = [(0.0, 0.0, 0.1, 0.0), (1.0, 1.0, 0.1, 0.0), (2.0, 2.0, -0.2, 0.0)]
PLAN = [(0.0, 0.0), (2.0, 0.0)]


def test_window_and_interpolation():
    assert ra.window(GT, 0.5, 2.0) == GT[1:]
    assert ra.interpolate_xy(GT, 0.5) == pytest.approx((0.5, 0.1))
    assert ra.interpolate_xy(GT, 1.0) == (1.0, 0.1)
    assert ra.interpolate_xy(GT, 2.5) is None
    assert ra.interpolate_xy(GT, -0.1) is None


def test_tracking_error():
    st = ra.tracking_error(GT, PLAN)
    assert st['n'] == 3
    assert st['mean'] == pytest.approx((0.1 + 0.1 + 0.2) / 3)
    assert st['max'] == pytest.approx(0.2) and st['p95'] == pytest.approx(0.2)


def test_belief_gap_skips_rather_than_extrapolates():
    amcl = [(0.5, 0.5, 0.4, 0.0), (1.0, 1.0, 0.1, 0.0), (9.0, 0.0, 0.0, 0.0)]
    g = ra.belief_gap(amcl, GT)
    assert g['n'] == 2 and g['skipped'] == 1
    assert g['max'] == pytest.approx(0.3) and g['mean'] == pytest.approx(0.15)
    assert ra.belief_gap([], GT)['mean'] is None


def test_endpoint_error():
    assert ra.endpoint_error(GT, 1.5, (1.0, 0.0)) == pytest.approx(0.1)
    assert ra.endpoint_error(GT, -1.0, (0.0, 0.0)) is None


def test_arbiter_timeline_records_changes_only():
    s = ['mode=nav active=none teleop=--', 'mode=nav active=none teleop=--',
         'mode=nav active=nav teleop=--', 'mode=nav active=none teleop=--']
    tl = ra.arbiter_timeline(list(zip([0.0, 0.5, 1.0, 2.0], s)))
    assert tl == [[0.0, 'nav', 'none'], [1.0, 'nav', 'nav'],
                  [2.0, 'nav', 'none']]


def test_world_to_map_shift():
    assert ra.to_map([(1.0, -2.0, 0.0, 0.3)], 2.0, 0.0) == \
        [(1.0, 0.0, 0.0, 0.3)]
