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

"""The whole loop's core and the Arena's localise subsystem (M2.3)."""

import math
import os

from coco_lab import arena as arena_mod
from coco_lab.arena import Arena, ArenaError, InputEvent, replay, SLIP_TURN
from coco_lab.loc_arena import ArenaLocaliser
from coco_lab.localise import MCL, MCLParams
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'),
          encoding='utf-8') as _f:
    SPEC = yaml.safe_load(_f)

CFG = lambda t, c: InputEvent(t, 'config', choice=c)  # noqa: E731


def drive(a, inputs, ticks):
    by = {}
    for e in inputs:
        by.setdefault(e.tick, []).append(e)
    return [a.step(by.get(a.tick, ())) for _ in range(ticks)]


def test_without_a_loop_input_the_state_is_m1s():
    a = Arena(SPEC, seed=5)
    drive(a, [InputEvent(0, 'goal', x=6.0, y=4.0)], 30)
    assert not a.loop and a.subsystems == {}
    n = len(a.ranges)
    assert len(a.state_bytes()) == 8 + 5 * 8 + 3 + 2 * 8 + 2 * 4 \
        + 32 + 32 + 4 + 4 * n


def test_a_subsystem_whose_pack_is_not_loaded_is_refused():
    saved = arena_mod.SUBSYSTEMS.pop('localise')
    try:
        a = Arena(SPEC, seed=1)
        with pytest.raises(ArenaError, match='not loaded'):
            a.step([CFG(0, 'localise.filter=mcl')])
    finally:
        arena_mod.SUBSYSTEMS['localise'] = saved
    assert arena_mod.SUBSYSTEMS['localise'] is ArenaLocaliser


def test_the_loop_is_deterministic_and_sees_its_seed():
    ins = [CFG(0, 'arena.range_sigma=0.02'), CFG(0, 'localise.filter=both'),
           InputEvent(0, 'goal', x=6.0, y=4.0),
           InputEvent(40, 'kidnap', x=2.0, y=-2.0, theta=0.5, has_theta=True)]
    a = replay(SPEC, 3, ins, 70)
    assert a == replay(SPEC, 3, ins, 70)
    assert a != replay(SPEC, 4, ins, 70)


def test_a_kidnap_moves_the_truth_and_tells_no_one():
    a = Arena(SPEC, seed=2)
    drive(a, [CFG(0, 'localise.filter=mcl'),
              InputEvent(0, 'teleop', linear=0.3)], 12)
    belief, odom = a.belief(), a.odom
    t = a.step([InputEvent(12, 'kidnap', x=2.0, y=-2.0, theta=1.0,
                           has_theta=True)])
    assert math.hypot(t.pose[0] - 2.0, t.pose[1] + 2.0) < 0.05
    # odometry moved by the step only; the belief is where it was
    assert math.hypot(a.odom[0] - odom[0], a.odom[1] - odom[1]) < 0.1
    assert math.hypot(t.belief[0] - belief[0], t.belief[1] - belief[1]) < 0.1
    ox, oy = a.smap.origin
    wall = next((ox + (i + 0.5) * a.smap.resolution, oy + 0.5 * a.smap.resolution)
                for i in range(a.smap.width)
                if a.smap.clearance(ox + (i + 0.5) * a.smap.resolution,
                                    oy + 0.5 * a.smap.resolution) < 0.05)
    with pytest.raises(ArenaError, match='wall'):
        a.step([InputEvent(13, 'kidnap', x=wall[0], y=wall[1])])


def test_the_planner_starts_from_the_belief_not_the_truth():
    a = Arena(SPEC, seed=2)
    drive(a, [CFG(0, 'localise.filter=mcl')], 2)
    a.step([InputEvent(2, 'kidnap', x=2.0, y=-2.0, has_theta=True)])
    belief = a.belief()
    t = a.step([InputEvent(3, 'goal', x=6.0, y=4.0)])
    first = t.plans[0].result.trace.events
    start_cell = a.plan_map.cell_at(*belief[:2])
    truth_cell = a.plan_map.cell_at(*t.pose[:2])
    assert start_cell != truth_cell
    assert (first['row'][0], first['col'][0]) == start_cell


def test_slip_turns_the_body_less_than_the_wheels_report():
    a = Arena(SPEC, seed=1)
    a.step([CFG(0, 'arena.odom_alphas=0,0,0,0'), CFG(0, 'arena.slip=on')])
    th0, od0 = a.pose[2], a.odom[2]
    drive(a, [InputEvent(1, 'teleop', linear=0.0, angular=0.8)], 8)
    turned, reported = a.pose[2] - th0, a.odom[2] - od0
    assert reported > 0.3
    assert turned == pytest.approx(SLIP_TURN * reported, rel=1e-6)
    b = Arena(SPEC, seed=1)
    b.step([CFG(0, 'arena.odom_alphas=0,0,0,0')])
    th0, od0 = b.pose[2], b.odom[2]
    drive(b, [InputEvent(1, 'teleop', linear=0.0, angular=0.8)], 8)
    assert b.pose[2] - th0 == pytest.approx(b.odom[2] - od0, rel=1e-9)


def test_a_loop_input_cannot_amend_a_tick():
    a = Arena(SPEC, seed=1)
    a.begin_step([InputEvent(0, 'goal', x=6.0, y=4.0)])
    with pytest.raises(ArenaError, match='cannot amend'):
        a.amend([CFG(0, 'arena.slip=on')])
    a.finish_step()


def test_loop_inputs_apply_first_in_their_tick():
    ins_a = [InputEvent(0, 'goal', x=6.0, y=4.0), CFG(0, 'arena.slip=on')]
    ins_b = [CFG(0, 'arena.slip=on'), InputEvent(0, 'goal', x=6.0, y=4.0)]
    assert replay(SPEC, 1, ins_a, 20) == replay(SPEC, 1, ins_b, 20)


def test_settings_are_checked_and_restart_the_filter():
    a = Arena(SPEC, seed=1)
    a.step([CFG(0, 'localise.filter=mcl')])
    assert len(a.subsystems['localise'].mcl.P) == 300
    a.step([CFG(1, 'localise.mcl.particles=120')])
    assert len(a.subsystems['localise'].mcl.P) == 120
    for bad in ('localise.mcl.particles=0', 'localise.filter=ukf',
                'localise.nope=1', 'arena.slip=maybe', 'arena.bogus=1'):
        with pytest.raises(ArenaError):
            a.step([CFG(a.tick, bad)])
    with pytest.raises(ArenaError):
        InputEvent(0, 'config', choice='no-equals-sign')


def test_the_arena_mcl_is_lab2s_class_draw_for_draw():
    """The Arena's MCL is localise.MCL: replayed alone, it gives the same estimates."""
    from coco_lab import localise
    from coco_lab.rng import Rng
    created, fed, est = [], [], []
    orig_init, orig_update = localise.MCL.__init__, localise.MCL.update

    def init(self, smap, lidar, params, start, rng):
        created.append((list(rng.state), start))
        orig_init(self, smap, lidar, params, start, rng)

    def update(self, odom, z):
        fed.append((odom, list(z)))
        u = orig_update(self, odom, z)
        est.append(u['est'])
        return u
    localise.MCL.__init__, localise.MCL.update = init, update
    try:
        a = Arena(SPEC, seed=9)
        drive(a, [CFG(0, 'arena.range_sigma=0.02'),
                  CFG(0, 'localise.filter=mcl'),
                  InputEvent(0, 'goal', x=6.0, y=4.0)], 80)
    finally:
        localise.MCL.__init__, localise.MCL.update = orig_init, orig_update
    assert len(created) == 1 and len(est) >= 8
    state, start = created[0]
    rng = Rng(0)
    rng.state = state
    m = MCL(a.smap, a.lidar, MCLParams(), start, rng)
    alone = [m.update(o, z)['est'] for o, z in fed]
    assert alone == est


def test_reset_restarts_the_filters_at_the_start():
    a = Arena(SPEC, seed=1)
    drive(a, [CFG(0, 'localise.filter=ekf'),
              InputEvent(0, 'teleop', linear=0.4)], 20)
    a.step([InputEvent(20, 'reset')])
    loc = a.subsystems['localise']
    assert a.odom == pytest.approx((0.0, 0.0, 0.0), abs=0.02)
    assert loc.ekf is not None and loc.ekf.updates <= 1
    # ...at the START pose, not where the belief was before the reset (M3.0)
    assert loc.belief() == pytest.approx(a.start, abs=0.05)


def test_a_reset_after_a_kidnap_forgets_the_old_belief():
    # odometry is not told of a kidnap, so the belief stays put; a reset is
    # a new run, and must start the filter where the robot now is (home)
    for filt in ('mcl', 'ekf'):
        a = Arena(SPEC, seed=1)
        drive(a, [CFG(0, f'localise.filter={filt}'),
                  InputEvent(0, 'kidnap', x=6.0, y=4.0, theta=0.0, has_theta=True)], 5)
        assert math.hypot(*(b - s for b, s in zip(a.belief()[:2], a.start[:2]))) < 0.5
        a.step([InputEvent(a.tick, 'reset')])
        assert a.pose == pytest.approx(a.start, abs=0.02)
        assert a.belief()[:2] == pytest.approx(a.start[:2], abs=0.15), filt
