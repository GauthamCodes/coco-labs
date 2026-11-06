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

"""R3.1: COCO-Bench v1 -- frozen suites, tiers, conditions (coco_lab.bench_v1)."""

import json
from pathlib import Path

from coco_lab import bench_v1 as B
from coco_lab import experiments as E
from coco_lab.exp_families import _conditions
import pytest

WORLDS = Path(__file__).resolve().parents[2] / 'worlds'
BENCH = Path(E.__file__).parent / 'benchmarks'
ALL = sorted(B.SUITES) + [B.TASK_SUITE]


@pytest.fixture(autouse=True)
def _worlds(monkeypatch):
    monkeypatch.setenv('COCO_WORLDS', str(WORLDS))


def v1(sid):
    return json.loads((BENCH / f'{sid}.v1.json').read_text())


def test_every_suite_is_committed_and_well_formed():
    for sid in ALL:
        s = v1(sid)
        assert s['schema'] == B.SCHEMA and s['id'] == sid and s['version'] == 1
        ids = [x['id'] for x in s['scenarios']]
        assert len(ids) == len(set(ids)), sid
        assert sum(s['tiers']['counts'].values()) == len(ids), sid
        assert {x['tier'] for x in s['scenarios']} <= set(B.TIERS), sid
        if sid != B.TASK_SUITE:
            assert len(ids) == B.SUITES[sid]['n'], sid
            assert s['world_sha256'] == E.world_sha256(s['world']), sid


@pytest.mark.parametrize('sid', ['arena-nav-50', 'depot-nav-100', 'depot-narrow-30'])
def test_carried_suites_keep_their_v0_scenarios_exactly(sid):
    bare = [{k: v for k, v in x.items() if k not in ('features', 'difficulty', 'tier')}
            for x in v1(sid)['scenarios']]
    assert bare == E.suite(sid, 0)['scenarios']


def test_tiers_are_thirds_by_difficulty():
    s = v1('depot-long-50')
    order = sorted(s['scenarios'], key=lambda x: (x['difficulty'], x['id']))
    tiers = [x['tier'] for x in order]
    assert tiers == sorted(tiers, key=B.TIERS.index)
    assert s['tiers']['counts'] == {'easy': 17, 'medium': 17, 'hard': 16}


def test_ranks_share_ties_and_span_zero_to_one():
    assert B._ranks([3, 1, 2]) == [1.0, 0.0, 0.5]
    assert B._ranks([1, 1, 2]) == [0.25, 0.25, 1.0]


def test_a_pair_keeps_its_tier_under_both_actor_rules():
    s = v1('ctrl-dynamic-30')
    by = {}
    for x in s['scenarios']:
        by.setdefault(x['pair'], set()).add((x['tier'], x['difficulty']))
        assert ('actors.yield=1' in x['config']) == (x['actor_rule'] == 'yield')
    assert len(by) == 15 and all(len(v) == 1 for v in by.values())


def test_filtered_suites_pass_their_own_filter():
    for sid in ('depot-long-50', 'depot-clutter-50', 'ctrl-corridor-30', 'ctrl-corners-30'):
        keep = B.SUITES[sid]['keep']
        assert all(keep(x['features']) for x in v1(sid)['scenarios']), sid


def test_features_are_reproducible():
    s = v1('ctrl-corners-30')
    w = E.world(s['world'])
    for x in s['scenarios'][:3]:
        assert B.features(w, x) == x['features']


def test_a_held_out_draw_differs_and_is_deterministic():
    a = B.generate('ctrl-corners-30', seed=12345, n=3)
    b = B.generate('ctrl-corners-30', seed=12345, n=3)
    assert a == b
    pub = {(tuple(x['start']), tuple(x['goal'])) for x in v1('ctrl-corners-30')['scenarios']}
    assert not any((tuple(x['start']), tuple(x['goal'])) in pub for x in a)


def test_conditions_are_only_the_allowed_settings():
    assert _conditions({}) == []
    assert _conditions({'config': ['actors.on=1', 'actors.yield=1']}) == ['actors.on=1',
                                                                          'actors.yield=1']
    for bad in (['move.controller=dwa'], ['arena.slip=on'], [3]):
        with pytest.raises(ValueError):
            _conditions({'config': bad})


def test_kidnap_and_global_scenarios_carry_their_conditions():
    for x in v1('loc-kidnap-20')['scenarios']:
        assert x['kidnap_at_s'] == 12.0 and x['features']['kidnap_m'] >= 5.0
    glob = v1('loc-global-20')['scenarios']
    assert all(x['config'] == ['localise.mcl.init=global'] for x in glob)


def test_task_suite_is_the_committed_rounds():
    s = v1(B.TASK_SUITE)
    assert [x['id'] for x in s['scenarios']] == \
        [f'fr_phone_{i}' for i in E.FETCH_RUSH_SEEDS] + [f'colour_{c}' for c in E.FETCH_COLOURS]
    assert s['held_out']['n'] == 0
