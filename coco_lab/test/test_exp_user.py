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

"""R2.1: algorithm files in experiments (coco_lab.exp_user; ADR 0013, ADR 0012)."""

import json
from pathlib import Path

from coco_lab import exp_user, experiments as E
import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / 'coco_lab' / 'templates'
ASTAR = (TEMPLATES / 'planner_astar.py').read_text()


def spec_for(src, family='planning', suite='arena-nav-50', ticks=600, **algo):
    sha = exp_user.register(src)
    return {'schema': E.SCHEMA, 'family': family, 'world': E.suite(suite)['world'],
            'algorithms': [dict({'name': 'user', 'id': 'mine', 'code_sha256': sha}, **algo)],
            'scenarios': {'kind': 'suite', 'id': suite}, 'limits': {'max_ticks': ticks}}


def first(src, family='planning', n=1, **kw):
    p = E.plan(spec_for(src, family, **kw))
    return [E.run_one(d) for d in p['runs'][:n]]


def test_user_spec_is_additive():
    # a built-in spec's id and descriptors are unchanged by R2 (no new keys)
    p = E.plan({'schema': E.SCHEMA, 'family': 'planning', 'world': 'coco_arena_v1',
                'algorithms': [{'name': 'astar'}],
                'scenarios': {'kind': 'suite', 'id': 'arena-nav-50'}})
    assert 'code_sha256' not in p['runs'][0] and 'api' not in p['spec']['algorithms'][0]
    u = E.plan(spec_for(ASTAR))
    a = u['spec']['algorithms'][0]
    assert a['api'] == 1 and len(a['code_sha256']) == 64 and a['label'] == 'Your algorithm'
    assert u['runs'][0]['code_sha256'] == a['code_sha256']
    assert 'heuristic_weight' not in a['params'] and 'inflation_radius' in a['params']


def test_user_spec_validation():
    with pytest.raises(E.SpecError):
        E.plan(dict(spec_for(ASTAR), algorithms=[{'name': 'user', 'code_sha256': 'xyz'}]))
    with pytest.raises(E.SpecError):
        E.plan(spec_for(ASTAR, api=2))
    with pytest.raises(E.SpecError):
        E.plan(spec_for(ASTAR, params={'user.bad-name': 1}))
    with pytest.raises(E.SpecError):
        E.plan(spec_for(ASTAR, params={'heuristic_weight': 3.0}))
    p = E.plan(spec_for(ASTAR, params={'user.cost_weight': 0.0}))
    assert p['runs'][0]['params']['user.cost_weight'] == 0.0
    sweep = dict(spec_for(ASTAR), sweep={'params': [{'name': 'user.cost_weight',
                                                     'values': [0.0, 4.0]}]})
    assert len(E.plan(sweep)['runs']) == 100


def test_planner_file_runs_and_is_deterministic():
    r = first(ASTAR)[0]
    assert r['status'] == 'found' and r['deterministic'] is True
    assert r['metrics']['expansions'] > 0 and r['metrics']['path_length_m'] > 0
    assert r['report']['calls'] == 1 and r['report']['n_problems'] == 0


def test_user_params_reach_ctx():
    src = ('def plan(costmap, start, goal, ctx):\n'
           '    print(ctx.params, ctx.config["connectivity"])\n    return None\n')
    r = first(src, params={'user.k': 3})[0]
    assert r['status'] == 'no_path' and "{'k': 3} 8" in r['report']['console']


@pytest.mark.parametrize('body,status,words', [
    ('return 5', 'invalid_output', 'returned int'),
    ('return []', 'invalid_output', 'empty path'),
    ('return [Pose2D(1e9, 0)]', 'invalid_output', 'off the map'),
    ('return [Pose2D(float("nan"), 0)]', 'invalid_output', 'not finite'),
    ('return [goal]', 'invalid_output', 'does not start'),
    ('return [start]', 'invalid_output', 'does not end'),
    ('return [start, goal]', 'collision', 'lethal or inscribed'),
])
def test_planner_contract(body, status, words):
    src = ('from coco_lab.api import Pose2D\n'
           f'def plan(costmap, start, goal, ctx):\n    {body}\n')
    r = first(src)[0]
    assert r['status'] == status and not r['success']
    assert words in r['report']['problems'][0]['message']


def test_planner_exception_and_budget():
    r = first('def plan(c, s, g, ctx):\n    x = {}\n    return x["missing"]\n')[0]
    assert r['status'] == 'error'
    assert r['report']['error']['type'] == 'KeyError' and r['report']['error']['line'] == 3
    r = first('def plan(c, s, g, ctx):\n    while True:\n        ctx.step(1000000)\n')[0]
    assert r['status'] == 'budget_exceeded'


def test_nondeterminism_is_flagged():
    # a set of objects iterates in address order: different between two runs
    src = ('from coco_lab.api import Pose2D\nclass C:\n    pass\n'
           'def plan(costmap, start, goal, ctx):\n'
           '    s = set(C() for _ in range(64))\n'
           '    for i, c in enumerate(s):\n        c.i = i\n'
           '    order = [o.i for o in sorted(s, key=hash)]\n'
           '    ctx.emit("note", text=str(order[:8]))\n    return None\n')
    r = first(src)[0]
    assert r['deterministic'] is False


def test_controller_file_runs_and_clamps():
    src = ('from coco_lab.api import Twist\n'
           'def control(state, scan, path, ctx):\n    return Twist.of(5.0, -9.0)\n')
    r = first(src, 'control', ticks=60)[0]
    rep = r['report']
    assert rep['clamped'] > 0 and 'clamped' in rep['clamp_examples'][0]
    assert r['metrics']['contacts'] >= 0 and r['status'] != 'error'


def test_controller_contract_errors_end_the_run():
    r = first('def control(state, scan, path, ctx):\n    return 3\n', 'control', ticks=60)[0]
    assert r['status'] == 'error' and 'not a Twist' in r['report']['problems'][0]['message']
    r = first('from coco_lab.api import NoValidControl\n'
              'def control(state, scan, path, ctx):\n    raise NoValidControl("blocked")\n',
              'control', ticks=60)[0]
    assert r['status'] == 'no_valid_control'


def test_localiser_file_runs_and_psd_is_checked():
    src = (TEMPLATES / 'localiser_empty.py').read_text()
    r = first(src, 'localisation', ticks=200)[0]
    assert r['status'] in ('timeout', 'localised', 'not_localised')
    assert r['report']['calls'] >= 199 and r['deterministic'] is True
    bad = ('from coco_lab.api import PoseWithCovariance\n'
           'def localise(odom, scan, map, ctx):\n'
           '    p = ctx.initial_pose\n'
           '    return PoseWithCovariance.of(p.x, p.y, p.theta, -1.0, 0.1, 0.1)\n')
    r = first(bad, 'localisation', ticks=50)[0]
    assert r['status'] == 'error' and 'covariance' in r['report']['problems'][0]['message']


def test_fulltask_refuses_user_files():
    with pytest.raises(E.SpecError):
        E.plan({'schema': E.SCHEMA, 'family': 'fulltask',
                'algorithms': [{'name': 'user', 'code_sha256': 'a' * 64}],
                'scenarios': {'kind': 'suite', 'id': 'colour-fetch-4'}})


def test_cli_algorithm(tmp_path):
    f = tmp_path / 'my_astar.py'
    f.write_text(ASTAR)
    spec = {'schema': E.SCHEMA, 'family': 'planning', 'world': 'coco_arena_v1',
            'algorithms': [{'name': 'astar'}],
            'scenarios': {'kind': 'sampled', 'n': 3}}
    (tmp_path / 'spec.json').write_text(json.dumps(spec))
    out = tmp_path / 'out'
    assert E.main(['run', str(tmp_path / 'spec.json'), '--algorithm', str(f), '--out', str(out),
                   '--workers', '1']) == 0
    runs = [json.loads(ln) for ln in (out / 'runs.jsonl').read_text().splitlines()]
    assert [r['algorithm'] for r in runs] == ['astar'] * 3 + ['my_astar'] * 3
    assert (out / 'algorithms' / 'my_astar.py').read_text() == ASTAR
    assert E.main(['verify', str(out), '--workers', '1']) == 0
