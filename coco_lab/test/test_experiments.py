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

"""R1: experiment specs, scenarios, runs, digests, the golden experiment and the CLI."""

import copy
import json
from pathlib import Path

import pytest

from coco_lab import experiments as ex
from coco_lab import games
from coco_lab.arena import Arena, ArenaError, InputEvent

FIX = Path(__file__).parent / 'fixtures' / 'r1' / 'golden_experiment.json'
WORLDS = Path(__file__).resolve().parents[2] / 'worlds'


@pytest.fixture(autouse=True)
def _worlds(monkeypatch):
    monkeypatch.setenv('COCO_WORLDS', str(WORLDS))


def _spec(**kw):
    s = {'schema': ex.SCHEMA, 'world': 'coco_arena_v1', 'family': 'planning',
         'algorithms': [{'name': 'astar'}, {'name': 'dijkstra'}],
         'scenarios': {'kind': 'sampled', 'n': 3, 'seed': 2}, 'seed': 1}
    s.update(kw)
    return s


def test_plan_fills_defaults_and_orders_runs():
    p = ex.plan(_spec(sweep={'params': [{'name': 'inflation_radius', 'values': [0.4, 0.6]}]}))
    assert len(p['runs']) == 2 * 2 * 3
    assert [r['index'] for r in p['runs']] == list(range(12))
    first = p['runs'][0]
    assert first['sweep'] == {'inflation_radius': 0.4} and first['algorithm'] == 'astar'
    assert first['params']['inflation_radius'] == 0.4 and first['params']['robot_radius'] == 0.25
    assert 'heuristic_weight' not in first['params']
    assert p['spec']['scenarios']['min_separation_m'] == 2.0
    assert p['spec']['model'] == {'hash_version': 3, 'experiment': 1}
    assert ex.plan(p['spec'])['id'] == p['id']      # the filled spec is a fixed point


@pytest.mark.parametrize('change, words', [
    ({'schema': 'x'}, 'schema'),
    ({'family': 'dance'}, 'family'),
    ({'algorithms': [{'name': 'rpp'}]}, 'planning algorithms'),
    ({'algorithms': [{'name': 'astar'}, {'name': 'astar'}]}, 'two algorithms'),
    ({'algorithms': [{'name': 'astar', 'params': {'heuristic_weight': 3}}]}, 'does nothing'),
    ({'algorithms': [{'name': 'astar', 'params': {'robot_radius': 0.9}}]}, 'cover robot_radius'),
    ({'model': {'hash_version': 2, 'experiment': 1}}, 'this build runs'),
    ({'scenarios': {'kind': 'sampled', 'n': 0}}, 'n is 1'),
    ({'scenarios': {'kind': 'sampled', 'n': 2, 'zones': ['zone_office']}}, 'no region zone'),
    ({'world': 'nowhere'}, 'not found'),
    ({'world_sha256': '0' * 64}, 'differs'),
])
def test_plan_refuses_what_it_cannot_run(change, words):
    with pytest.raises(ex.SpecError, match=words):
        ex.plan(_spec(**change))


def test_scenarios_are_deterministic_and_respect_their_constraints():
    spec = _spec(world='coco_depot_v1', scenarios={
        'kind': 'sampled', 'n': 12, 'seed': 9, 'min_separation_m': 6.0, 'stratify': 'zone'})
    a, b = ex.plan(spec), ex.plan(copy.deepcopy(spec))
    assert a['scenarios'] == b['scenarios']
    w = ex.world('coco_depot_v1')
    zones = [s['start_zone'] for s in a['scenarios']]
    assert sorted(set(zones)) == sorted(w.regions) and all(zones.count(z) == 2 for z in w.regions)
    for s in a['scenarios']:
        (sx, sy, _), (gx, gy) = s['start'], s['goal']
        assert ((gx - sx) ** 2 + (gy - sy) ** 2) ** 0.5 >= 6.0
        assert w.component(sx, sy) == w.component(gx, gy) >= 0
    other = ex.plan(dict(spec, scenarios=dict(spec['scenarios'], seed=10)))
    assert other['scenarios'] != a['scenarios']


def test_runs_are_pure_and_the_digest_ignores_timings():
    p = ex.plan(_spec())
    r1, r2 = ex.run_all(p), ex.run_all(p)
    assert [r['chain'] for r in r1] == [r['chain'] for r in r2]
    assert ex.digest(r1) == ex.digest(r2)
    r2[0]['metrics']['compute_ms'] += 1000.0
    assert ex.digest(r1) == ex.digest(r2)
    r2[0]['metrics']['expansions'] += 1
    assert ex.digest(r1) != ex.digest(r2)


def test_a_failure_is_a_result_not_an_omission():
    p = ex.plan(_spec(family='control', algorithms=[{'name': 'builtin'}],
                      scenarios={'kind': 'sampled', 'n': 2, 'seed': 4, 'min_separation_m': 4.0},
                      limits={'max_ticks': 10}))
    rs = ex.run_all(p)
    assert [r['status'] for r in rs] == ['timeout', 'timeout']
    assert all(r['fail_tick'] == 9 and not r['success'] for r in rs)
    g = ex.summarise(p, rs)['groups'][0]
    assert g['n'] == 2 and g['successes'] == 0 and g['status'] == {'timeout': 2}
    assert g['success']['low'] == 0.0


def test_controller_parameters_default_to_the_teaching_values():
    def drive(extra):
        a = Arena(json.loads((WORLDS / 'coco_arena_v1.json').read_text()), 1, hash_version=3)
        evs = [InputEvent(0, 'config', choice=c) for c in extra + ['move.controller=dwa']]
        evs.append(InputEvent(0, 'goal', x=4.0, y=2.0))
        ticks = [a.step(evs)] + [a.step() for _ in range(40)]
        return a, [t.pose for t in ticks], [t.state_hash for t in ticks]
    a, poses, hashes = drive([])
    # no override: the subsystem's attributes (all of them hashed by v2/v3) are as before
    assert not hasattr(a.subsystems['move'], 'overrides')
    same, poses2, hashes2 = drive(['move.dwa.v_max=0.3', 'move.window.cost_scaling_factor=65'])
    assert poses2 == poses                       # the defaults, set explicitly: same drive
    assert same.subsystems['move'].overrides == {'dwa': {'v_max': 0.3}}
    assert drive(['move.dwa.v_max=0.2'])[1] != poses
    a = Arena(json.loads((WORLDS / 'coco_arena_v1.json').read_text()), 1, hash_version=3)
    for bad in ('move.dwa.nope=1', 'move.dwa.v_max=x', 'move.mppi.emit=3',
                'move.dwa.scales=1,2', 'move.window.size=inf'):
        with pytest.raises(ArenaError):
            a.step([InputEvent(a.tick, 'config', choice=bad)])


def test_a_bot_driven_by_a_named_planner_plays_the_same_round():
    spec = json.loads((WORLDS / 'coco_depot_colours_v1.json').read_text())
    rec0, res0 = games.bot_fetch_colour(spec, 'red')
    rec1, res1 = games.bot_fetch_colour(spec, 'red', planner='astar')
    assert res1['scorecard'] == res0['scorecard']
    assert [e for e in rec1['inputs'] if e['kind'] != 'planner'] == rec0['inputs']
    assert {'kind': 'planner', 'choice': 'astar', 'tick': 0} in rec1['inputs']
    assert games.play(spec, rec1) == res1


def test_exports_are_complete_and_checksummed():
    p = ex.plan(_spec())
    rs = ex.run_all(p)
    files = ex.export(p, rs, {'runner': 'test'})
    assert set(files) == {'spec.json', 'results.csv', 'summary.json', 'runs.jsonl',
                          'manifest.json'}
    lines = files['results.csv'].decode().splitlines()
    assert len(lines) == 1 + len(rs) and lines[0].startswith('run,sweep_index,algorithm')
    man = json.loads(files['manifest.json'])
    assert man['digest'] == ex.digest(rs) and man['evidence'] == 'MODEL'
    assert set(man['files']) == set(files) - {'manifest.json'}


def test_golden_experiment():
    """The committed digests and chains (tools/r1/make_golden_experiment.py): never edited."""
    gold = json.loads(FIX.read_text())
    for case in gold['cases']:
        p = ex.plan(case['spec'])
        assert p['id'] == case['id'], case['name']
        rs = ex.run_all(p)
        assert [r['chain'] for r in rs] == case['chains'], case['name']
        assert ex.digest(rs) == case['digest'], case['name']


def test_cli_reproduces_the_golden_planning_digest(tmp_path):
    gold = json.loads(FIX.read_text())
    case = next(c for c in gold['cases'] if c['spec']['family'] == 'planning')
    spec = tmp_path / 'spec.json'
    spec.write_text(json.dumps(case['spec']))
    assert ex.main(['run', str(spec), '--out', str(tmp_path / 'out'), '--workers', '2',
                    '--worlds', str(WORLDS)]) == 0
    summary = json.loads((tmp_path / 'out' / 'summary.json').read_text())
    assert summary['digest'] == case['digest']
    assert ex.main(['verify', str(tmp_path / 'out'), '--sample', '0.5', '--workers', '1',
                    '--worlds', str(WORLDS)]) == 0
