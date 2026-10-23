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
Grasp Assist, the model side (M6F.5; README §5.8): MODEL · MoveIt-style.

The scenarios are ``fixtures/m6f/grasp_scenarios.json``; their golden traces
``fixtures/m6f/grasp_golden.json`` (``tools/m6/make_grasp_golden.py``).
"""

import json
import os

from coco_lab import arm
from coco_lab import grasp_assist as ga
from coco_lab.arena import Arena, ArenaError, InputEvent
from coco_lab.grasp import APPROACH_RANGE, MAX_LATERAL, WINDOW
from coco_lab.sketch import WAYPOINT_TOL
import pytest
import yaml

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
FIX = os.path.join(HERE, 'fixtures', 'm6f')


def _json(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return json.load(f)


SCEN = _json('grasp_scenarios.json')
GOLDEN = _json('grasp_golden.json')['results']
BY_NAME = {s['name']: s for s in SCEN['scenarios']}
with open(os.path.join(REPO, SCEN['spec']), encoding='utf-8') as _f:
    DEPOT = yaml.safe_load(_f)
with open(os.path.join(REPO, 'worlds', 'coco_arena_v2.yaml'), encoding='utf-8') as _f:
    V2 = yaml.safe_load(_f)
STAGE = [n for n, _ in ga.TABLES['coco.manip.v1.StageBatch']]


def _col(row, name):
    return row[1 + STAGE.index(name)]


@pytest.fixture(scope='module')
def runs():
    return {name: ga.run_scenario(DEPOT, s) for name, s in BY_NAME.items()}


# -- the outcomes ------------------------------------------------------------------

@pytest.mark.parametrize('name', sorted(BY_NAME))
def test_each_scenario_ends_as_designed(runs, name):
    want, last = BY_NAME[name]['expect'], runs[name]['stages'][-1]
    assert _col(last, 'stage') == want['stage'], last
    if want['reason']:
        assert _col(last, 'outcome') == \
            f'{want["object"]}: {ga.REASON_TEXT[want["reason"]]}'
    elif want['stage'] != 'refused':
        assert _col(last, 'object_id') == want['object']


@pytest.mark.parametrize('reason', ga.REASONS)
def test_every_refusal_reason_is_given(runs, reason):
    texts = [_col(r['stages'][-1], 'outcome') for r in runs.values()]
    assert any(t.endswith(ga.REASON_TEXT[reason]) for t in texts)


@pytest.mark.parametrize('name', [n for n in sorted(BY_NAME) if n.startswith('pick')])
def test_a_successful_pick_ends_inside_the_stacks_approach_window(runs, name):
    stages = runs[name]['stages']
    reach = next(r for r in stages if _col(r, 'stage') == 'reach')
    ahead, left = _col(reach, 'ahead'), _col(reach, 'left')
    assert WINDOW[0] <= ahead <= WINDOW[1] and abs(left) <= MAX_LATERAL
    j1, j2 = _col(reach, 'ik_joint1'), _col(reach, 'ik_joint2')
    x, z = arm.fk(j1, j2)
    assert x == pytest.approx(ahead, abs=1e-9)                  # the IK reaches the object
    assert [_col(r, 'stage') for r in stages][-4:] in (
        ['reach', 'grip', 'verify', 'carry'], ['verify', 'carry', 'release', 'done'])


def test_the_release_puts_the_object_down_in_front(runs):
    r = runs['pick_then_release_at_the_dock']
    x, y, th = r['pose']
    ox, oy, oz, status = r['objects']['obj_dock']
    mid = (WINDOW[0] + WINDOW[1]) / 2
    assert status == 'placed' and r['carried'] is None and oz == 0.0
    assert (ox, oy) == pytest.approx((x + mid * __import__('math').cos(th),
                                      y + mid * __import__('math').sin(th)))


def test_a_deck_pick_stands_on_the_deck(runs):
    deck = next(e for e in DEPOT['kit'] if e['id'] == 'mezzanine_deck')['top']
    assert runs['pick_mezzanine_deck']['objects']['obj_mez_1'][2] == pytest.approx(deck)


def test_the_person_and_stop_win_over_the_assist(runs):
    for name in ('the_person_takes_the_wheels', 'stop_wins'):
        stages = runs[name]['stages']
        assert _col(stages[-1], 'stage') == 'aborted'
        assert runs[name]['carried'] is None


# -- determinism and golden traces ---------------------------------------------------

@pytest.mark.parametrize('name', sorted(BY_NAME))
def test_golden_traces(runs, name):
    r = runs[name]
    assert {k: r[k] for k in ('stages', 'hash_chain', 'last_hash', 'carried')} == GOLDEN[name]


def test_repeated_runs_are_identical(runs):
    for name in ('pick_dispatch_floor', 'pick_dispatch_floor_hash_v2', 'refuse_blocked'):
        again = ga.run_scenario(DEPOT, BY_NAME[name])
        assert again == runs[name]


def test_listening_to_the_events_does_not_change_the_state(runs):
    s = BY_NAME['pick_dispatch_floor']
    a = Arena(DEPOT, s['seed'])                       # no on_family: nothing drained
    a.pose = tuple(s['pose'])
    by = {}
    for e in s['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    hashes = [a.step(by.get(a.tick, ())).state_hash for _ in range(s['ticks'])]
    assert hashes[-1] == runs['pick_dispatch_floor']['last_hash']


# -- the events ------------------------------------------------------------------------

def test_every_stage_and_the_arm_are_emitted():
    got = {}

    def hook(ch, tick, cols, scalars):
        got.setdefault(ch, []).append((cols, scalars))
    s = BY_NAME['pick_dispatch_floor']
    a = Arena(DEPOT, s['seed'], on_family=hook)
    a.pose = tuple(s['pose'])
    a.step([InputEvent(0, 'config', choice='assist.grasp=go')])
    for _ in range(s['ticks']):
        a.step(())
    (env_cols, env), = got[ga.CH_ENVELOPE]
    assert env_cols is None and env == ga.envelope() and env['badge'] == 'MODEL · MoveIt-style'
    stages = [st for cols, _ in got[ga.CH_STAGES] for st in cols['stage']]
    assert stages == ['detect', 'check', 'choose', 'approach', 'align', 'creep', 'reach',
                      'grip', 'verify', 'carry']
    (cand, _), = got[ga.CH_CANDIDATES]
    assert list(cand['object_id']) == ['obj_dispatch'] and list(cand['rank']) == [0]
    arm_rows = [p for cols, _ in got[ga.CH_ARM] for p in cols['phase']]
    assert arm_rows[0] == 'unfold' and arm_rows[-1] == 'stowed'
    magnets = [m for cols, _ in got[ga.CH_ARM] for m in cols['magnet_on']]
    assert magnets[-1] == 1


def test_the_envelope_is_derived_from_existing_constants():
    env = ga.envelope()
    assert (env['window_near'], env['window_far']) == WINDOW
    assert env['max_lateral'] == MAX_LATERAL and env['finger_max'] == 0.032
    assert env['standoff'] == pytest.approx(APPROACH_RANGE - WAYPOINT_TOL)
    assert env['short_radius'] == APPROACH_RANGE
    assert env['reach_band_lo'] < 0.128 <= env['reach_band_hi']


def test_the_candidate_ranking_prefers_the_cheapest_approach():
    a = Arena(DEPOT, seed=1)
    a.step([InputEvent(0, 'config', choice='assist.target=any')])
    sub = a.subsystems['assist']
    a.pose = (45.0, 7.5, 0.0)      # the dock canister 1.5 m ahead; the crate 0.5 m behind
    rows = {r['object_id']: r for r in sub.candidates(a)}
    assert set(rows) == {'obj_dock', 'bad_crate'}
    assert (rows['obj_dock']['rank'], rows['obj_dock']['reason']) == (0, '')
    assert rows['obj_dock']['seen_by'] == 'camera' and rows['bad_crate']['seen_by'] == 'radius'
    assert rows['bad_crate']['reason'] == 'too_wide' and rows['bad_crate']['rank'] == 1
    assert rows['bad_crate']['reasons_mask'] == 0b111     # too wide, out of reach, not magnetic


def test_grasp_assist_needs_a_v3_level():
    a = Arena(V2, seed=1)
    with pytest.raises(ArenaError, match='World Spec v3'):
        a.step([InputEvent(0, 'config', choice='assist.grasp=go')])
