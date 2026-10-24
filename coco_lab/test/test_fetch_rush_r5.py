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
G2 rules 5: the actors stop for COCO, and AUTO reacts to them.

Gautham, 2026-10-24: "the robot just stays still and the forklift moves forward phasing through
the robot". Rules 4 (and earlier) actors are a schedule: the model refuses COCO's step into an
actor, but an actor moving onto a standing COCO is never checked, so it drives through it.
Rules 5 (``actors.yield=1``, ``avoid.on=1`` in the setup inputs): each actor holds while its next
pose would bring its box within ``radius + ACTOR_STOP_MARGIN`` of COCO and closer, and AUTO
(``games.ActorAvoid``) waits for a moving actor or re-plans around a stopped one.

**Overlap**, as these tests measure it: COCO's circle (centre = the truth pose, radius
``spec.robot.radius``) and an actor's box (its footprint at its actual pose) intersect, i.e.
``games.box_distance(centre, box) < radius`` -- the clearance ``DepotActors.clearance`` is < 0.
"""
import hashlib
import json
from pathlib import Path

from coco_lab import games, loc_arena, numerics  # noqa: F401 -- loc_arena: the subsystem
from coco_lab.arena import Arena, InputEvent
from coco_lab.rng import Rng
import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / 'worlds' / 'coco_depot_v1.json'
SPEC = json.loads(SPEC_PATH.read_text())
FILE = games.rounds_file('coco_depot_v1', 5)
DOC = games.load_rounds(rules=5) if FILE.exists() else None
DOC4 = games.load_rounds(rules=4)
ROUNDS = [(mode, seed) for mode in sorted(DOC4['rounds'])
          for seed in sorted(DOC4['rounds'][mode], key=int)]


def _arena(start, yielding=True, hash_version=1, avoid=None):
    a = Arena(SPEC, 1, hash_version=hash_version)
    rows = [{'tick': 0, 'kind': 'kidnap', 'x': start[0], 'y': start[1], 'theta': start[2],
             'has_theta': True}]
    rows += games.setup_inputs('fetch_rush', 0, 1, yielding=yielding)
    if avoid is False:
        rows = [r for r in rows if r.get('choice') != 'avoid.on=1']
    a.step([InputEvent(**r) for r in rows])
    return a


def _run(a, ticks, goal=None, until_arrived=False):
    """Step ``ticks`` (a goal first, if given); return min clearance, refused steps, arrival."""
    act = a.subsystems['actors']
    worst, refused, arrived = act.clearance(a.pose[0], a.pose[1], a.radius), 0, None
    if goal is not None:
        a.step([InputEvent(a.tick, 'goal', x=goal[0], y=goal[1])])
    for _ in range(ticks):
        t = a.step([])
        worst = min(worst, act.clearance(a.pose[0], a.pose[1], a.radius))
        refused += t.blocked
        if t.arrived and arrived is None:
            arrived = a.t_world
            if until_arrived:
                break
    return worst, refused, arrived


def test_the_setup_inputs_add_yield_only_from_rules_5():
    four = games.setup_inputs('fetch_rush', 1, 4, games.round_for(1, rules=4))
    five = games.setup_inputs('fetch_rush', 1, 5, games.round_for(1, rules=4))
    assert not any(r.get('choice') in games.YIELD_SETUP for r in four)
    assert five == four + [{'tick': 0, 'kind': 'config', 'choice': c} for c in games.YIELD_SETUP]
    assert games.setup_inputs('rush_hour', 'aisle_to_dispatch') == \
        games.setup_inputs('rush_hour', 'aisle_to_dispatch', 5)
    assert games.FETCH_RUSH_RULES == games.YIELD_RULES == 5


def test_without_yield_nothing_is_added_to_the_state():
    """A rules-4 Arena's actors carry no yield state (so every rules-4 hash is unchanged)."""
    a = _arena((30.0, 6.0, 0.0), yielding=False)
    act = a.subsystems['actors']
    assert not act.yielding() and not hasattr(act, 'lag') and 'avoid' not in a.subsystems
    assert act.state_bytes() == b'coco.arena.actors.v1\x00' + (4).to_bytes(4, 'little')
    assert act.times() == [a.t_world] * 4


def test_head_on_the_forklift_stops_for_a_parked_coco():
    """COCO parked in the east-west lane: rules 4's forklift drives through it; rules 5's stops."""
    with numerics.version(3):
        old = _run(_arena((30.0, 11.0, 0.0), yielding=False), 400)
        a = _arena((30.0, 11.0, 0.0), yielding=True)
        new = _run(a, 400)
    assert old[0] == pytest.approx(-0.22), "rules 4: the forklift box ran over COCO's centre"
    assert new[0] > 0.0, 'rules 5: no overlap'
    lag = a.subsystems['actors'].lag
    assert lag[0] > 300, 'the east-west forklift held for COCO (it never reached it)'
    assert new[0] >= games.ACTOR_STOP_MARGIN - 0.15 - 1e-9, \
        'it stops within one step (1.5 m/s x 0.1 s) of its stop distance'


@pytest.mark.parametrize('seed', range(1, 9))
def test_no_actor_ever_overlaps_coco_driven_anyhow(seed):
    """A person's random teleop near the lanes, for 600 ticks per seed: no overlap, ever."""
    rng = Rng(seed)
    # in or beside the lanes and the walkers' crossings (none inside an actor at the start)
    starts = [(20.0, 11.0), (24.2, 9.0), (33.75, 18.0), (40.0, 12.0), (30.0, 9.6), (45.0, 11.0),
              (33.75, 23.5), (19.0, 11.0)]
    x, y = starts[seed - 1]
    a = _arena((x, y, rng.uniform(-3.14, 3.14)))
    act = a.subsystems['actors']
    worst = act.clearance(a.pose[0], a.pose[1], a.radius)
    assert worst > 0.0, 'the start is clear of every actor'
    for k in range(600):
        rows = []
        if k % 15 == 0:
            rows = [InputEvent(a.tick, 'teleop', linear=rng.uniform(-0.5, 0.5),
                               angular=rng.uniform(-1.2, 1.2))]
        a.step(rows)
        worst = min(worst, act.clearance(a.pose[0], a.pose[1], a.radius))
    assert worst > 0.0


def test_auto_crossing_the_lane_waits_or_goes_and_never_overlaps():
    """AUTO across the east-west lane at several start times: it arrives, never overlapping."""
    for wait in (0, 40, 100, 150):
        a = _arena((28.0, 8.0, 1.5708))
        for _ in range(wait):
            a.step([])
        worst, refused, arrived = _run(a, 1500, goal=(28.0, 14.3), until_arrived=True)
        assert worst > 0.0 and arrived is not None, (wait, worst, arrived)
        assert refused == 0, f'start {wait}: AUTO drove into an actor'


def test_auto_reaches_its_goal_after_the_forklift_blocks_it():
    """
    Head-on in the lane: the forklift stops, AUTO re-plans around it and arrives.

    COCO in the lane, its goal along the lane beyond the oncoming forklift: the forklift stops
    for COCO, AUTO (right of way) re-plans around it and arrives -- no deadlock.
    """
    a = _arena((24.0, 11.0, 3.1416))
    worst, refused, arrived = _run(a, 2500, goal=(18.0, 11.0), until_arrived=True)
    av = a.subsystems['avoid']
    assert arrived is not None, av.view()
    assert worst > 0.0 and refused == 0
    assert av.replans >= 1 and max(a.subsystems['actors'].lag) > 0


def test_avoid_needs_its_setting_and_adds_no_arena_attribute():
    four = Arena(SPEC, 1, hash_version=3)
    four.step([InputEvent(0, 'config', choice='actors.on=1')])
    a = Arena(SPEC, 1, hash_version=3)
    a.step([InputEvent(0, 'config', choice=c) for c in
            ('actors.on=1', 'actors.yield=1', 'avoid.on=1')])
    assert set(vars(a)) == set(vars(four)), 'rules 5 adds nothing to the Arena itself'
    assert sorted(a.subsystems) == ['actors', 'avoid']
    with pytest.raises(Exception):
        a.step([InputEvent(a.tick, 'config', choice='avoid.off=1')])


@pytest.mark.skipif(DOC is None, reason='rules 5 rounds not generated yet')
def test_the_rounds_are_rules_4_s_draw_under_rules_5():
    assert DOC['spec_sha256'] == hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    assert DOC['rules'] == 5 and DOC['modes'] == games.ROUND_MODES_R4 == games.round_modes(5)
    assert DOC['yield_setup'] == list(games.YIELD_SETUP)
    assert DOC['actor_stop_margin_m'] == games.ACTOR_STOP_MARGIN
    for k in ('trips', 'approach', 'crossings', 'crossing_bands', 'crossing_windows', 'starts',
              'lanes', 'timer_factor', 'hash_version'):
        assert DOC[k] == DOC4[k], k
    for mode, seed in ROUNDS:
        m = games.ROUND_MODES_R4[mode]
        rnd = DOC['rounds'][mode][seed]
        drawn = games.draw_round(int(seed), DOC['trips'], m['budget_m'], m['orders'],
                                 rnd['attempt'])
        assert drawn == {'region': rnd['region'], 'orders': rnd['orders']}
        card, rec = rnd['reference']['card'], rnd['reference']['record']
        assert card['deliveries'] == m['orders'] and card['rules'] == 5 and rec['rules'] == 5
        assert rnd['timer_s'] == round(rnd['reference_time_s'] * games.ROUND_TIMER_FACTOR, 1)
        assert [r['choice'] for r in rec['inputs'] if r['tick'] == 0][-2:] == \
            list(games.YIELD_SETUP)


@pytest.mark.skipif(DOC is None, reason='rules 5 rounds not generated yet')
@pytest.mark.parametrize('mode', ['phone', 'full'])
def test_the_reference_record_replays_to_its_card(mode):
    rnd = games.round_for(1, rules=5, mode=mode)
    got = games.play(SPEC, rnd['reference']['record'])
    assert got['scorecard'] == rnd['reference']['card']
    assert got['hash_chain'] == rnd['reference']['hash_chain']


@pytest.mark.skipif(DOC is None, reason='rules 5 rounds not generated yet')
@pytest.mark.parametrize('mode,seed', ROUNDS)
def test_the_reference_bot_never_overlaps_an_actor(mode, seed):
    rec = DOC['rounds'][mode][seed]['reference']['record']
    a = Arena(SPEC, rec['seed'], hash_version=rec['hash_version'])
    by = {}
    for e in rec['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    worst = 9.0
    for _ in range(rec['ticks']):
        a.step(by.get(a.tick, ()))
        act = a.subsystems['actors']
        worst = min(worst, act.clearance(a.pose[0], a.pose[1], a.radius))
    assert worst > 0.0
