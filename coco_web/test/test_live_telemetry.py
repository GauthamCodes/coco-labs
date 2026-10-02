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

"""Phase 2 telemetry helpers: belief, ground truth, goal status."""

from coco_config.robot import SPAWN_XY
from coco_web import telemetry as tele
import pytest


def test_belief_carries_the_filter_spread_and_its_age():
    """Diagonal of the 6x6 covariance, and age on one clock."""
    cov = [0.0] * 36
    cov[0], cov[7], cov[35] = 0.04, 0.09, 0.01
    out = tele.belief_payload((1.0, 2.0, 0.5), cov, stamp=10.0, now=10.25)
    assert out == {'x': 1.0, 'y': 2.0, 'yaw': 0.5, 'cov_xx': 0.04,
                   'cov_yy': 0.09, 'cov_yawyaw': 0.01, 'age_s': 0.25}


def test_belief_from_the_future_is_age_zero_not_negative():
    """A clock step backwards must not report a negative age."""
    out = tele.belief_payload((0, 0, 0), [0.0] * 36, stamp=5.0, now=4.0)
    assert out['age_s'] == 0.0


def test_belief_without_a_covariance_says_so():
    """None, not a made-up zero spread."""
    out = tele.belief_payload((0, 0, 0), None, stamp=0.0, now=0.0)
    assert out['cov_xx'] is None and out['cov_yawyaw'] is None


def test_truth_at_spawn_is_the_map_origin():
    """The map's origin IS the spawn point, so truth there is (0, 0)."""
    out = tele.truth_to_map(SPAWN_XY[0], SPAWN_XY[1], 0.3, SPAWN_XY)
    assert out == {'x': pytest.approx(0.0), 'y': pytest.approx(0.0),
                   'yaw': 0.3}


def test_truth_shift_matches_the_world_geometry_shift():
    """The same derivation as world_geometry: map x = world x - SPAWN_X."""
    out = tele.truth_to_map(4.0, -1.0, 0.0, SPAWN_XY)
    assert out['x'] == pytest.approx(4.0 + (-SPAWN_XY[0]))
    assert out['y'] == pytest.approx(-1.0 - SPAWN_XY[1])


@pytest.mark.parametrize('entries,sent,expected', [
    ([], 10.0, None),                                   # not accepted yet
    ([(9.0, 2)], 10.0, None),                           # the mission's goal
    ([(9.0, 2), (10.2, 1)], 10.0, 'accepted'),
    ([(10.2, 2)], 10.0, 'executing'),
    ([(10.2, 4)], 10.0, 'succeeded'),
    ([(10.2, 6)], 10.0, 'aborted'),
    ([(10.2, 5), (11.0, 2)], 10.0, 'executing'),        # newest wins
    ([(10.2, 99)], 10.0, 'unknown'),
])
def test_goal_status_is_this_browsers_goal_only(entries, sent, expected):
    """Older goals (the mission's) never answer for a browser goal."""
    assert tele.goal_status(entries, sent) == expected
