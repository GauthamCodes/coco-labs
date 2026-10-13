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
M4.3: kinematic terrain, the command source, hand-back and the gated grasp.

On World Spec v2; and a flat (v1) world exactly as before.
"""

import math
import os

from coco_lab import grasp as G
from coco_lab.arena import Arena, InputEvent, TERRAIN_LAYOUT
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _spec(v):
    with open(os.path.join(REPO, 'worlds', f'coco_arena_v{v}.yaml'), encoding='utf-8') as f:
        return yaml.safe_load(f)


V1, V2 = _spec(1), _spec(2)
RISE = 2 * math.tan(math.radians(18))
# the blue bay in the MAP frame (world + [2, 0]): up-wedge foot x 3, platform 5..6.2, y 2
FOOT, CREST, BAY_Y = 3.0, 5.0, 2.0


def _drive(a, ticks, v=0.3, w=0.0):
    out = []
    for _ in range(ticks):
        out.append(a.step([InputEvent(a.tick, 'teleop', linear=v, angular=w)]))
    return out


def test_a_flat_world_has_no_terrain_and_its_state_bytes_are_m3s():
    a = Arena(V1, seed=3)
    assert a.terrain is None and a.scan_smap is a.smap
    t = _drive(a, 20)[-1]
    assert (t.z, t.pitch, t.roll) == (0.0, 0.0, 0.0)
    assert TERRAIN_LAYOUT not in a.state_bytes() and b'grasp' not in a.state_bytes()


def test_the_robot_climbs_the_ramp_onto_the_platform_kinematically():
    a = Arena(V2, seed=3)
    a.pose = (FOOT - 0.6, BAY_Y, 0.0)
    ticks = _drive(a, 120)
    zs = [t.z for t in ticks]
    assert zs[0] == 0.0 and max(zs) == pytest.approx(RISE, abs=1e-9)   # up on the platform
    assert all(b >= a_ - 1e-12 for a_, b in zip(zs, zs[1:]))           # never down on the way up
    mid = [t for t in ticks if FOOT + 0.3 < t.pose[0] < CREST - 0.3]
    nose_up = -math.radians(18)
    assert mid and all(t.pitch == pytest.approx(nose_up, abs=1e-9) for t in mid)
    assert all(t.roll == 0.0 for t in ticks) and not any(t.contact for t in ticks)
    assert TERRAIN_LAYOUT in a.state_bytes()


def test_the_lidar_meets_the_ramp_where_it_rises_above_the_beam():
    a = Arena(V2, seed=3)
    a.pose = (FOOT - 1.0, BAY_Y, 0.0)
    a.ranges = a._scan()
    ahead = min(range(len(a.angles)), key=lambda k: abs(a.angles[k]))
    inset = a.beam_height / math.tan(math.radians(18))
    sensor_x = a.pose[0] + a.lidar.mount[0]
    # the beam nearest straight ahead is a few milliradians off it: range to the plane / cos
    want = (FOOT + inset - sensor_x) / math.cos(a.angles[ahead] + a.lidar.mount[2])
    assert a.ranges[ahead] == pytest.approx(want, abs=1e-6)


def test_driving_off_the_side_of_the_platform_is_a_contact_and_stops_the_robot():
    a = Arena(V2, seed=3)
    a.pose = (5.6, BAY_Y, math.pi / 2)            # on the platform, facing its side (+y)
    ticks = _drive(a, 60)
    assert any(t.contact for t in ticks)
    assert ticks[-1].pose[1] < BAY_Y + 1.25 and ticks[-1].z == pytest.approx(RISE, abs=1e-9)


def test_the_command_source_follows_the_arbiters_order():
    a = Arena(V1, seed=1)
    assert a.step([InputEvent(0, 'teleop', linear=0.2)]).source == 'teleop'
    assert a.step([InputEvent(1, 'goal', x=6.0, y=4.0)]).source == 'planner'
    assert a.step([InputEvent(2, 'stop')]).source == 'stop'
    assert a.step().source == 'idle'


def test_handing_back_resumes_the_persons_last_goal():
    a = Arena(V1, seed=1)
    a.step([InputEvent(0, 'goal', x=6.0, y=4.0)])
    a.step([InputEvent(1, 'teleop', linear=0.1)])
    assert a.goal is None
    t = a.step([InputEvent(2, 'autonomy')])
    assert a.goal == (6.0, 4.0) and t.source == 'planner'


def _facing(colour, dist):
    a = Arena(V2, seed=3)
    tx, ty = G.Grasp(a.spec['world_to_map']).targets[colour]
    a.pose = (tx - dist, ty, 0.0)
    return a


def test_the_grasp_approaches_picks_within_the_stacks_window_and_carries():
    a = _facing('blue', 0.45)
    t = a.step([InputEvent(0, 'grasp')])
    assert a.grasp.phase == 'approach' and t.source == 'mission'
    for _ in range(400):
        t = a.step()
        if a.grasp.phase == 'carry':
            break
    assert a.grasp.phase == 'carry' and a.grasp.target == 'blue'
    # it picked from inside the Stack's window
    ax, ay = G.Grasp.in_base(a.pose, G.Grasp(a.spec['world_to_map']).targets['blue'])
    assert G.WINDOW[0] <= ax <= G.WINDOW[1] and abs(ay) <= G.MAX_LATERAL
    before = list(a.grasp.targets['blue'])
    _drive(a, 10, v=-0.2)
    assert a.grasp.targets['blue'] != before            # it rides with the robot
    assert b'coco.arena.grasp.v1' in a.state_bytes()


def test_the_grasp_refuses_with_no_target_ahead_and_on_a_flat_world():
    a = _facing('red', 0.45)
    a.pose = (a.pose[0], a.pose[1], math.pi)           # facing away
    t = a.step([InputEvent(0, 'grasp')])
    assert a.grasp.phase == 'idle' and 'no target' in t.grasp['reason']
    f = Arena(V1, seed=3)
    t = f.step([InputEvent(0, 'grasp')])
    assert f.grasp is None and 'flat world' in t.grasp['reason']
    assert b'grasp' not in f.state_bytes()


def test_a_terrain_session_is_deterministic():
    def run():
        a = Arena(V2, seed=7)
        a.pose = (FOOT - 0.6, BAY_Y, 0.05)
        return [t.state_hash for t in _drive(a, 80, v=0.25, w=0.05)]
    assert run() == run()


@pytest.mark.parametrize('colour,y', [('red', -6.0), ('green', -2.0), ('blue', 2.0),
                                      ('yellow', 6.0)])
def test_a_planned_drive_climbs_to_each_platform_and_the_grasp_picks(colour, y):
    # the planner routes up the ramp (rims are walls, slopes are not); the gate is the Stack's
    a = Arena(V2, seed=1)
    a.step([InputEvent(0, 'goal', x=5.6, y=y)])
    while not a.step().arrived:
        assert a.tick < 600
    assert a.step().z == pytest.approx(RISE, abs=1e-9)
    a.step([InputEvent(a.tick, 'grasp')])
    while a.grasp.phase not in ('carry', 'idle'):
        a.step()
    assert (a.grasp.phase, a.grasp.target) == ('carry', colour)


def test_reset_puts_the_robot_home_and_the_targets_back():
    a = _facing('blue', 0.153)                         # already in the window
    a.step([InputEvent(0, 'grasp')])
    while a.grasp.phase != 'carry':
        a.step()
    _drive(a, 10, v=-0.2)
    home = G.Grasp(a.spec['world_to_map']).targets
    assert a.grasp.targets['blue'] != home['blue']
    t = a.step([InputEvent(a.tick, 'reset')])
    assert a.grasp.targets == home and a.grasp.phase == 'idle'
    assert t.pose == pytest.approx(tuple(a.start)) and t.z == 0.0


def test_a_stop_or_a_person_driving_cancels_the_approach():
    for cancel in ({'kind': 'stop'}, {'kind': 'teleop', 'linear': 0.1}):
        a = _facing('green', 0.45)
        a.step([InputEvent(0, 'grasp')])
        assert a.grasp.phase == 'approach'
        t = a.step([InputEvent(a.tick, **cancel)])
        assert a.grasp.phase == 'idle' and t.source == cancel['kind']
