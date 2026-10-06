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
Phase 5 (Lab 4): leaving a bay that did not hold the target, and the
search-mode datum.

``retreat_cmd`` is pure, so its shape is asserted here and a kinematic
roll-out shows it backs down the line it came up. Whether the chassis
does so on the 18 degree wedge in Gazebo is a measurement, not this
file's claim.
"""

import inspect
import math
from types import SimpleNamespace

from coco_config.robot import CLIMB_END_X, PRE_RAMP_X, region_by_id
import pytest

driver = pytest.importorskip('coco_rl.ramp_driver')
retreat_cmd = driver.retreat_cmd
GOAL = driver.RETREAT_GOAL_X


def test_the_retreat_goal_is_on_the_flat_in_front_of_the_ramp():
    assert GOAL == pytest.approx(PRE_RAMP_X + 0.15)
    assert GOAL < 1.0                          # the ramp foot is at x = 1.0


def test_it_reverses_and_never_pivots():
    for yaw in (-0.6, -0.2, 0.0, 0.3, 1.0):
        for drift in (-0.4, 0.0, 0.4):
            lin, ang, done = retreat_cmd(yaw, 2.0, drift, GOAL)
            assert not done
            # The linear term never depends on heading: a pivot on a
            # grade is how a skid-steer base loses its footing.
            assert lin == -driver.RETREAT_SPEED
            assert abs(ang) <= driver.RETREAT_YAW_CLAMP


def test_it_stops_at_the_goal():
    assert retreat_cmd(0.0, GOAL + driver.RETREAT_ARRIVE / 2, 0.0,
                       GOAL) == (0.0, 0.0, True)
    assert retreat_cmd(0.0, GOAL - 1.0, 0.0, GOAL)[2]


def test_a_drift_to_the_left_turns_it_left_so_it_backs_toward_the_line():
    # Backing up with a positive yaw moves the robot toward -y.
    _, ang, _ = retreat_cmd(0.0, 2.0, +0.2, GOAL)
    assert ang > 0
    _, ang, _ = retreat_cmd(0.0, 2.0, -0.2, GOAL)
    assert ang < 0
    assert retreat_cmd(0.0, 2.0, 0.0, GOAL)[1] == 0.0


def test_a_kinematic_rollout_backs_down_the_line_it_came_up():
    x, y, yaw = CLIMB_END_X, 0.12, -0.15
    dt = 1.0 / driver.DESCEND_HZ
    for _ in range(4000):
        lin, ang, done = retreat_cmd(yaw, x, y, GOAL)
        if done:
            break
        x += lin * math.cos(yaw) * dt
        y += lin * math.sin(yaw) * dt
        yaw += ang * dt
    assert done
    assert x <= GOAL + driver.RETREAT_ARRIVE
    assert abs(y) < 0.05 and abs(yaw) < 0.1


def _stub(search_mode):
    log = SimpleNamespace(info=lambda *_: None)
    return SimpleNamespace(_region_map={}, _lane_y=None,
                           _search_mode=search_mode,
                           get_logger=lambda: log)


def test_searching_the_colour_does_not_set_the_datum():
    stub = _stub(True)
    driver.RampDriver._on_colour(stub, SimpleNamespace(data='red'))
    assert stub._lane_y is None
    driver.RampDriver._on_region(stub, SimpleNamespace(data='bay_3'))
    assert stub._lane_y == region_by_id('bay_3').lane_y
    driver.RampDriver._on_colour(stub, SimpleNamespace(data='red'))
    assert stub._lane_y == region_by_id('bay_3').lane_y


def test_told_the_region_topic_is_ignored():
    stub = _stub(False)
    driver.RampDriver._on_colour(stub, SimpleNamespace(data='red'))
    told = stub._lane_y
    driver.RampDriver._on_region(stub, SimpleNamespace(data='bay_3'))
    assert stub._lane_y == told


def test_an_unknown_region_leaves_the_datum_alone():
    stub = _stub(True)
    driver.RampDriver._on_region(stub, SimpleNamespace(data='bay_2'))
    driver.RampDriver._on_region(stub, SimpleNamespace(data='bay_9'))
    assert stub._lane_y == region_by_id('bay_2').lane_y


def test_the_node_serves_retreat_and_declares_search_mode():
    source = inspect.getsource(driver.RampDriver.__init__)
    assert "'/ramp/retreat', self._on_retreat" in source
    assert "declare_parameter('search_mode', False)" in source
    assert "'/mission/search_region'" in source
    # The retreat publishes where every segment publishes: the env's own
    # cmd_vel topic (/cmd_vel_rl through the arbiter). No new publisher.
    run = inspect.getsource(driver.RampDriver._run_retreat)
    assert 'create_publisher' not in run and 'env._publish' in run
