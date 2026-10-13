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
"""M4.8: the ghost race: deterministic, scored like a person, stars from its own result."""

import json
import os

from coco_lab import play, race
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as _f:
    SPEC = yaml.safe_load(_f)
with open(os.path.join(REPO, 'lab_web', 'play', 'levels.json'), encoding='utf-8') as _f:
    LEVELS = json.load(_f)
RACE = LEVELS['challenges']['race-the-ghost']['levels']
WARM = next(lv for lv in RACE if lv['id'] == 'warm-up')


def _submit(level, inputs):
    return play.score(LEVELS, {'v': 1, 'challenge': 'race-the-ghost', 'level': level['id'],
                               'level_hash': play.level_hash(level), 'inputs': inputs}, SPEC)


def test_the_committed_references_are_the_ghosts_own_result():
    lv = {k: v for k, v in WARM.items() if k not in ('reference', 'ghost_track')}
    assert race.references(SPEC, lv) == WARM['reference']
    assert race.ghost_inputs(SPEC, lv) == race.ghost_inputs(SPEC, lv)      # deterministic


def test_the_ghost_scored_like_a_person_earns_two_stars():
    lv = {k: v for k, v in WARM.items() if k not in ('reference', 'ghost_track')}
    r = _submit(WARM, race.ghost_inputs(SPEC, lv))
    assert r['valid'] and r['stars'] == 2
    m = {x['name']: x['value'] for x in r['metrics']}
    assert m['time_s'] == pytest.approx(WARM['reference']['ghost']['time_s'])
    assert m['contacts'] == WARM['reference']['ghost']['contacts']


def test_standing_still_does_not_finish_and_a_goal_input_is_refused():
    r = _submit(WARM, [])
    assert not r['valid'] and r['stars'] == 0 and 'did not reach the flag' in r['why']
    with pytest.raises(play.PlayError, match='may only drive'):
        _submit(WARM, [{'tick': 0, 'kind': 'goal', 'x': 2.5, 'y': 2.0}])


def test_a_track_drawn_for_the_ghost_ends_at_the_flag():
    tr = WARM['ghost_track']
    g = WARM['goal']
    assert len(tr) == WARM['reference']['ghost']['finish_tick'] + 1
    assert (tr[-1][0] - g[0]) ** 2 + (tr[-1][1] - g[1]) ** 2 <= WARM['finish_m'] ** 2


def test_the_clock_starts_at_the_first_input():
    # a person reads the level first: the same drive begun 50 ticks later takes the same time
    lv = {k: v for k, v in WARM.items() if k not in ('reference', 'ghost_track')}
    log = race.ghost_inputs(SPEC, lv)
    late = [dict(r, tick=r['tick'] + 50) for r in log]
    a, b = race.drive(SPEC, WARM, log), race.drive(SPEC, WARM, late)
    assert b['start_tick'] == 50 and b['finish_tick'] == a['finish_tick']


def test_every_level_separates_its_stars():
    for lv in RACE:
        g = lv['reference']['ghost']
        assert g['finish_tick'] < lv['max_ticks'] and g['contacts'] == 0
