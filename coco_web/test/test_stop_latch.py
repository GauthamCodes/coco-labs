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

"""The latched STOP's pure policy, without a ROS graph."""

import ast
import os

from coco_web import stop_latch as sl
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ARBITER = os.path.join(HERE, '..', '..', 'custom_teleop', 'custom_teleop',
                       'cmd_vel_arbiter.py')


def _arbiter_modes():
    """MODE_ALIASES and AUTONOMOUS_MODES from the arbiter, read with ast."""
    tree = ast.parse(open(ARBITER).read())
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], 'id', None)
            if name in ('MODE_ALIASES', 'AUTONOMOUS_MODES'):
                found[name] = ast.literal_eval(node.value)
    return found


def test_moving_modes_are_exactly_the_arbiters_autonomous_spellings():
    """Every spelling the arbiter maps onto nav/rl/approach, and no other."""
    modes = _arbiter_modes()
    autonomous = set(modes['AUTONOMOUS_MODES'])
    expected = autonomous | {alias for alias, target
                             in modes['MODE_ALIASES'].items()
                             if target in autonomous}
    assert sl.MOVING_MODES == expected


@pytest.mark.parametrize('mode', ['nav', 'NAV ', 'auto', 'rl', 'ramp',
                                  'approach', 'nav2', 'autonomous'])
def test_moving(mode):
    assert sl.is_moving_mode(mode)


@pytest.mark.parametrize('mode', ['idle', 'stop', 'teleop', 'manual', '',
                                  'none', None, 3])
def test_not_moving(mode):
    assert not sl.is_moving_mode(mode)


@pytest.mark.parametrize('state,fresh,running', [
    ('CLIMB', True, True), ('NAVIGATE_TO_RAMP', True, True),
    ('RECOVERY', True, True), ('GRASP', True, True),
    ('IDLE', True, False), ('COMPLETE', True, False),
    ('ABORT', True, False), ('', True, False), (None, True, False),
    ('CLIMB', False, False),
])
def test_mission_running(state, fresh, running):
    assert sl.mission_running(state, fresh) is running


def test_latch_lifecycle():
    latch = sl.StopLatch()
    assert not latch.latched and not latch.blocks('drive')
    latch.engage(100.0)
    latch.engage(200.0)                         # keeps the first time
    assert latch.as_dict() == {'latched': True, 'since': 100.0,
                               'violations': 0}
    assert latch.blocks('drive') and latch.blocks('nav_goal')
    for kind in ('stop', 'set_mode', 'mission', 'select_target',
                 'set_arm', 'ping', 'subscribe'):
        assert not latch.blocks(kind), kind
    zero = {'linear': 0.0, 'angular': 0.0}
    assert not latch.blocks('drive', zero)       # a zero starts nothing
    assert latch.blocks('drive', {'linear': 0.0, 'angular': 0.1})
    assert latch.release() is True
    assert latch.release() is False
    assert not latch.blocks('drive')


@pytest.mark.parametrize('kind,frame,releases', [
    ('set_mode', {'mode': 'teleop'}, True),
    ('set_mode', {'mode': 'auto'}, True),
    ('set_mode', {'mode': 'stop'}, False),
    ('mission', {'action': 'start'}, True),
    ('mission', {'action': 'abort'}, False),
    ('select_target', {'colour': 'red'}, False),
    ('drive', {'linear': 0.1, 'angular': 0.0}, False),
])
def test_what_releases(kind, frame, releases):
    assert sl.StopLatch().releases(kind, frame) is releases


def test_violations_count_only_moving_modes_while_latched():
    latch = sl.StopLatch()
    assert not latch.violated_by('nav')          # released: not ours
    latch.engage(1.0)
    assert not latch.violated_by('idle')
    assert not latch.violated_by('teleop')
    assert latch.violated_by('nav')
    assert latch.violated_by('rl')
    assert latch.as_dict()['violations'] == 2


def test_zero_hold():
    hold = sl.ZeroHold()
    assert not hold.active(0.0)
    hold.hold(10.0)
    assert hold.active(10.0) and hold.active(10.0 + sl.HOLD_S - 1e-6)
    assert not hold.active(10.0 + sl.HOLD_S)
    hold.hold(10.5, 0.1)                          # never shortens
    assert hold.active(10.9)
    hold.cancel()
    assert not hold.active(10.9)
