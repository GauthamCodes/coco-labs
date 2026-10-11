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

"""The Arena's fetch mission, its arm, and the goal hook (M2.6)."""

import ast
import collections
import math
import os

from coco_lab import arm, fetch_problem, mission_arena, regionsearch as rs
from coco_lab.arena import Arena, ArenaError, InputEvent, replay
import coco_lab.move_arena  # noqa: F401 -- registers the move subsystem
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'),
          encoding='utf-8') as _f:
    SPEC = yaml.safe_load(_f)
CFG = lambda t, c: InputEvent(t, 'config', choice=c)  # noqa: E731


def fetch(colour, *cfg, seed=3, ticks=6000):
    seen = collections.defaultdict(list)

    def fam(ch, tick, cols, scalars):
        seen[ch].append((tick, cols, scalars))
    a = Arena(SPEC, seed, on_family=fam)
    a.step([CFG(0, c) for c in cfg] + [CFG(0, f'mission.start={colour}')])
    m = a.subsystems['mission']
    while m.state not in ('done', 'failed') and a.tick < ticks:
        a.step(())
    return a, m, seen


def transitions(seen):
    out = []
    for _, cols, _ in seen['coco.mission.fsm.transition.v1']:
        out += list(zip(cols['from_state'], cols['to_state'], cols['event']))
    return out


# -- the arm ---------------------------------------------------------------------

def test_the_arm_is_arm_iks_geometry():
    src = os.path.join(REPO, 'coco_moveit_config', 'scripts', 'arm_ik.py')
    tree = ast.parse(open(src).read())
    ref = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
           if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
           and n.targets[0].id.isupper()}
    for k in ('S_X', 'S_Z', 'L1', 'L2', 'PHI1', 'GAMMA0', 'SHOULDER_LIMITS',
              'ELBOW_LIMITS'):
        assert getattr(arm, k) == ref[k], k


def test_the_grasp_pose_puts_the_pinch_on_the_target():
    x, z = arm.fk(*arm.POSES['grasp'])
    assert (x, z) == pytest.approx(arm.TARGET_XZ, abs=1e-3)
    for q in arm.ik(0.10, 0.20):
        assert arm.fk(*q) == pytest.approx((0.10, 0.20), abs=1e-9)
    hx, hz = arm.fk(*arm.hover_pose())
    assert (hx, hz) == pytest.approx(
        (arm.TARGET_XZ[0], arm.TARGET_XZ[1] + arm.HOVER_CLEARANCE), abs=1e-9)


def test_the_magnet_holds_and_the_fingers_only_close():
    phases = [arm.script_state(t / 10) for t in range(int(
        arm.script_seconds() * 10))]
    assert phases[-1] is not None and arm.script_state(
        arm.script_seconds() + 0.01) is None
    hold = [s for s in phases if s['holding']]
    assert hold and all(s['magnet_on'] for s in hold)
    assert hold[0]['phase'] == 'magnet'
    assert {s['phase'] for s in phases} == {p[0] for p in arm.GRASP_SCRIPT}
    for s in phases:
        lo, hi = arm.SHOULDER_LIMITS
        assert lo <= s['joint1'] <= hi
        assert arm.ELBOW_LIMITS[0] <= s['joint2'] <= arm.ELBOW_LIMITS[1]


# -- the problem -----------------------------------------------------------------

def test_the_problem_is_lab_4s_bay_search():
    p = rs.SearchProblem.from_dict(fetch_problem.PROBLEM)
    assert p.ids == ('bay_1', 'bay_2', 'bay_3', 'bay_4')
    assert p.detection == (0.9,) * 4
    assert p.prior == (0.25,) * 4
    assert fetch_problem.LAYOUT == {'red': 'bay_1', 'green': 'bay_2',
                                    'blue': 'bay_3', 'yellow': 'bay_4'}


# -- the core hooks --------------------------------------------------------------

def test_plan_clearance_is_hashed_only_when_set():
    ins = [CFG(0, 'arena.range_sigma=0.0'), InputEvent(0, 'goal', x=3, y=2)]
    base = replay(SPEC, 1, ins, 5)
    assert base == replay(SPEC, 1, ins, 5)
    assert base != replay(SPEC, 1, ins + [CFG(0, 'arena.plan_clearance=0.4')],
                          5)
    with pytest.raises(ArenaError):
        Arena(SPEC, 1).step([CFG(0, 'arena.plan_clearance=0.1')])


def test_a_requested_goal_is_planned_next_tick_and_survives_an_amend():
    a = Arena(SPEC, 2)
    a.step(())
    a.request_goal(3.0, 2.0)
    a.begin_step(())
    a.amend([InputEvent(1, 'planner', choice='dijkstra')])
    t = a.finish_step()
    assert a.goal == (3.0, 2.0) and t.plans and a.mode == 'goal'
    assert t.plans[0].planner == 'dijkstra'


# -- the mission -----------------------------------------------------------------

def test_a_fetch_completes_and_searches_by_expected_cost():
    a, m, seen = fetch('red')
    assert (m.state, m.result) == ('done', 'fetch')
    tr = transitions(seen)
    assert tr[0] == ('idle', 'localise', 'start')
    assert tr[-1] == ('return', 'done', 'home')
    # every choice is regionsearch's, from the belief the robot then had
    acts = [(cols['region'][0], cols['expected_cost'][0])
            for _, cols, _ in seen['coco.decide.search.action.v1']]
    p = m.problem
    belief, searched, loc = p.prior, (), p.start
    for (i, cost), (_, obs, _) in zip(
            acts, seen['coco.decide.search.observation.v1']):
        view = rs.SearchView(belief, searched, loc)
        assert i == rs.choose('expected_cost', p, view)
        assert cost == pytest.approx(rs.candidate_costs(p, view)[i])
        belief = rs.update(belief, i, bool(obs['found'][0]), 0.9)
        searched, loc = searched + (i,), p.ids[i]
    assert acts[-1][0] == p.index('bay_1')
    # every order of the bays left is costed at every choice
    first = mission_arena.order_rows(
        seen['coco.decide.search.orders.v1'][0][1])
    assert len(first) == 24


def test_the_assumption_is_labelled_in_the_data():
    a, m, seen = fetch('blue', ticks=10)
    (_, _, head), = seen['coco.decide.search.header.v1']
    assert head['detection'] == 0.9
    assert head['detection_label'] == 'ASSUMPTION'
    (_, _, mh), = seen['coco.mission.fsm.header.v1']
    assert mh['evidence'] == 'MODEL'
    assert 'not modelled' in mh['params']['simplified']


def test_a_miss_is_bayes_and_the_camera_never_lies():
    a, m, seen = fetch('red', 'mission.detect=1.0')
    for _, cols, _ in seen['coco.sensor.detect.colour.v1']:
        if cols['detected'][0]:
            assert cols['region_id'][0] == 'bay_1'
    (_, b0, _) = seen['coco.decide.search.belief.v1'][0]
    (_, b1, _) = seen['coco.decide.search.belief.v1'][1]
    first = seen['coco.decide.search.action.v1'][0][1]['region'][0]
    assert list(b0['probability']) == [0.25] * 4
    assert b1['probability'][first] == pytest.approx(
        0.25 * 0.1 / (1 - 0.25 * 0.9))


def test_the_world_can_hide_the_target_where_the_layout_does_not_put_it():
    a, m, seen = fetch('red', 'mission.truth=bay_3')
    assert m.result == 'fetch'
    found = [cols['region_id'][0]
             for _, cols, _ in seen['coco.sensor.detect.colour.v1']
             if cols['detected'][0]]
    assert found == ['bay_3']


def test_a_grasp_streams_the_arm():
    a, m, seen = fetch('green')
    arms = seen['coco.arm.state.v1']
    assert len(arms) >= arm.script_seconds() / a.dt - 1
    phases = [cols['phase'][0] for _, cols, _ in arms]
    assert phases[0] == 'unfold' and phases[-1] == 'stowed'
    assert all(cols['holding'][0] for _, cols, _ in arms[-3:])


def test_a_mislocalised_robot_searches_the_wrong_bay_and_believes_it():
    # the belief 4 m south of the truth (bays are 4 m apart): the robot
    # drives to where it believes Bay 3 is, the camera sees Bay 4, and the
    # miss is booked against Bay 3 -- the error reaches the search's belief
    a, m, seen = fetch('red', 'move.belief_offset=0.0,-4.0,0.0', ticks=1500)
    reasons = [r for _, cols, _ in seen['coco.mission.fsm.transition.v1']
               for r in cols['reason']]
    miss = [r for r in reasons if r.startswith('no red target')]
    assert miss[0].startswith('no red target (the camera saw Bay 4 (the '
                              'robot believes it is at Bay 3))')
    (_, b1, _) = seen['coco.decide.search.belief.v1'][1]
    assert b1['probability'][2] == pytest.approx(0.25 * 0.1 / (1 - 0.225))
    # and it drove into what it believed it was clear of
    assert m.state == 'failed' and 'moved less than' in m.result


def spy_reset_home(a):
    calls = []
    original = a.reset_home

    def spy():
        original()
        calls.append((a.pose, a.odom, a.mode, a.goal))
    a.reset_home = spy
    return calls


def test_a_fetch_after_another_starts_from_home():
    # M3.0 "reset home": the mislocalised fetch fails away from home (M2.6's
    # stall); the next fetch must not inherit that pose -- it starts home
    a, m, seen = fetch('red', 'move.belief_offset=0.0,-4.0,0.0', ticks=1500)
    assert m.state == 'failed'
    stuck = a.pose[:2]
    assert math.hypot(stuck[0] - a.start[0], stuck[1] - a.start[1]) > 1.0
    calls = spy_reset_home(a)
    a.step([CFG(a.tick, 'mission.start=green')])
    assert calls == [(a.start, (0.0, 0.0, 0.0), 'idle', None)]
    assert m.colour == 'green' and m.state not in ('idle', 'done', 'failed')
    # the move scenario's belief offset went with the reset (a reset is a new run)
    assert a.subsystems['move'].offset is None
    reasons = [r for _, cols, _ in seen['coco.mission.fsm.transition.v1']
               for r in cols['reason']]
    start = [r for r in reasons if r.startswith('told to fetch the green')]
    assert len(start) == 1 and start[0].endswith(
        f'put back home from ({stuck[0]:.2f}, {stuck[1]:.2f}))')
    # the first fetch's start said nothing of the kind
    assert [r for r in reasons if 'put back home' in r] == start


def test_a_stall_no_longer_poisons_the_next_fetch():
    # M2's seek recording (lab_web/tools/perf/seek_check.mjs settings, seed
    # 1): MCL + an occupancy map from the belief + DWA. Red's fetch stalls
    # near (1.7, 5.7) -- M2.6's measured DWA weakness. Before M3.0 every
    # later fetch started there and stalled again; now green starts home,
    # with its filter restarted at home too, and completes.
    import coco_lab.loc_arena  # noqa: F401 -- registers localise
    import coco_lab.map_arena  # noqa: F401 -- registers map
    a = Arena(SPEC, 1)
    a.step([CFG(0, c) for c in (
        'arena.range_sigma=0.02', 'localise.filter=mcl',
        'map.algorithm=occupancy', 'map.poses=belief', 'move.controller=dwa',
        'mission.start=red')])
    m = a.subsystems['mission']
    while m.state not in ('done', 'failed'):
        a.step(())
    assert m.state == 'failed' and 'no_valid_control' in m.result
    assert a.pose[:2] == pytest.approx((1.70, 5.71), abs=0.01)
    a.step([CFG(a.tick, 'mission.start=green')])
    assert a.belief()[:2] == pytest.approx((0.0, 0.0), abs=0.2)
    while m.state not in ('done', 'failed') and a.tick < 3000:
        a.step(())
    assert m.state == 'done' and m.result == 'fetch'


def test_a_restart_mid_fetch_also_starts_from_home():
    a = Arena(SPEC, 1)
    a.step([CFG(0, 'mission.start=red')])
    for _ in range(200):
        a.step(())
    m = a.subsystems['mission']
    assert m.state not in ('idle', 'done', 'failed')
    calls = spy_reset_home(a)
    a.step([CFG(a.tick, 'mission.start=blue')])
    assert [c[0] for c in calls] == [a.start] and m.colour == 'blue'


def test_a_sessions_first_fetch_starts_where_the_robot_stands():
    # the mislocalised experiments put the robot somewhere first: a first
    # fetch must not undo that
    a = Arena(SPEC, 1)
    a.step([InputEvent(0, 'kidnap', x=6.0, y=4.0, theta=0.0, has_theta=True)])
    calls = spy_reset_home(a)
    a.step([CFG(a.tick, 'mission.start=red')])
    assert calls == []
    assert math.hypot(a.pose[0] - 6.0, a.pose[1] - 4.0) < 0.1


def test_after_a_reset_input_the_next_fetch_is_not_reset_twice():
    a = Arena(SPEC, 1)
    a.step([CFG(0, 'mission.start=red')])
    for _ in range(50):
        a.step(())
    calls = spy_reset_home(a)
    a.step([InputEvent(a.tick, 'reset')])
    a.step([CFG(a.tick, 'mission.start=yellow')])
    assert len(calls) == 1   # the reset input's own


def test_a_two_fetch_session_is_deterministic():
    ins = [CFG(0, 'mission.start=red'), CFG(300, 'mission.start=green')]
    h = replay(SPEC, 5, ins, 400)
    assert h == replay(SPEC, 5, ins, 400)
    assert h != replay(SPEC, 5, ins[:1], 400)


def test_a_bad_setting_is_refused():
    for bad in ('mission.start=purple', 'mission.truth=bay_9',
                'mission.detect=0', 'mission.speed=1'):
        with pytest.raises(ArenaError):
            Arena(SPEC, 1).step([CFG(0, bad)])


def test_abort_fails_the_mission():
    a = Arena(SPEC, 1)
    a.step([CFG(0, 'mission.start=red')])
    for _ in range(5):
        a.step(())
    a.step([CFG(a.tick, 'mission.abort=1')])
    m = a.subsystems['mission']
    assert m.state == 'failed' and 'ABORTED' in m.result
    assert a.mode == 'idle'


def test_the_mission_is_deterministic_and_hashed():
    ins = [CFG(0, 'mission.start=yellow')]
    h = replay(SPEC, 3, ins, 120)
    assert h == replay(SPEC, 3, ins, 120)
    assert h != replay(SPEC, 3, [CFG(0, 'mission.start=red')], 120)


def test_states_are_the_documented_ones():
    assert mission_arena.NOMINAL == ('localise', 'choose_bay', 'go_to_bay',
                                     'detect', 'grasp', 'return', 'done')
    assert math.isclose(mission_arena.CLEARANCE, 0.40)
