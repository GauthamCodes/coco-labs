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

"""Regression tests for the behavioural gaps documented in ADR 0008."""
import copy
import json
from pathlib import Path
import time

from coco_lab.arena import Arena, InputEvent
from coco_lab.race import drive, RaceError
import pytest

SPEC = json.loads((Path(__file__).parents[2] / 'worlds/coco_arena_v1.json').read_text())


@pytest.mark.parametrize('name,value', [
    ('last_auto_goal', ('planner', (2.0, 3.0))),
    ('teleop', (0.1, 0.2)), ('waypoints', [(1.0, 2.0)]),
    ('_goal_request', (2.0, 3.0)), ('range_sigma', 0.01),
    ('user_teleop', True), ('goal_source', 'mission'),
])
def test_v2_covers_state_that_v1_did_not(name, value):
    a = Arena(SPEC, 1, hash_version=2)
    before = a.state_hash()
    setattr(a, name, value)
    assert a.state_hash() != before


def test_versions_are_separate_without_changing_motion():
    a, b = Arena(SPEC, 1), Arena(SPEC, 1, hash_version=2)
    for k in range(10):
        e = [InputEvent(tick=k, kind='teleop', linear=0.2)]
        ta, tb = a.step(e), b.step(e)
        assert ta.pose == tb.pose
        assert ta.state_hash != tb.state_hash


def test_v2_covers_filter_parameters_and_anchor():
    import coco_lab.loc_arena  # noqa: F401 (registers the subsystem)
    a = Arena(SPEC, 1, hash_version=2)
    a.step([InputEvent(tick=0, kind='config', choice='localise.filter=mcl')])
    b = copy.deepcopy(a)
    b.subsystems['localise'].anchor = (1.0, 2.0, 3.0)
    assert a.state_hash() != b.state_hash()
    b = copy.deepcopy(a)
    b.subsystems['localise'].mcl_params.particles += 1
    assert a.state_hash() != b.state_hash()


def test_huge_first_tick_refused_before_arena_construction():
    before = time.perf_counter()
    with pytest.raises(RaceError, match='tick'):
        drive({}, {}, [{'tick': 10**12, 'kind': 'teleop', 'linear': 0.2}])
    assert time.perf_counter() - before < 0.05


def test_legacy_verification_does_not_change_canonical_result():
    from coco_lab import play
    r = play._finish({'value': 1.0, 'other': 0.0})
    before = dict(r)
    h = play.verification_hashes(r)
    assert h['canonical'] == r['hash']
    assert h['legacy_json_before_m36'] != r['hash']
    assert r == before
