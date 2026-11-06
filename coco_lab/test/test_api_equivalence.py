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
R2.1: the built-ins through the algorithm API reproduce the native built-ins (ADR 0013).

Each built-in is run twice on the same descriptor: natively (``name``) and through its
``coco_lab.api_builtins`` wrapper as user code is run (``name: user``, measured by
``coco_lab.exp_user``). Status, every metric but wall time, the expanded cells in order,
the path cell for cell, and (Arena families) the truth pose at every tick must be equal.
D* Lite's path length and cost are the recorded exception (ADR 0013).
"""

import copy
from pathlib import Path

from coco_lab import experiments as E
from coco_lab.trace import EXPAND, PATH
import pytest


# this tree's worlds/: an installed coco_lab (CI, the suites runner) has none of its own,
# so set COCO_WORLDS as test_experiments.py does
WORLDS = Path(__file__).resolve().parents[2] / 'worlds'


@pytest.fixture(autouse=True)
def _worlds(monkeypatch):
    monkeypatch.setenv('COCO_WORLDS', str(WORLDS))


def runs(family, suite, name, n, max_ticks=3000):
    spec = {'schema': E.SCHEMA, 'family': family, 'world': E.suite(suite)['world'],
            'algorithms': [{'name': name}], 'scenarios': {'kind': 'suite', 'id': suite},
            'limits': {'max_ticks': max_ticks}}
    return E.plan(spec)['runs'][:n]


def wrapped(d):
    u = copy.deepcopy(d)
    u['name'], u['code_sha256'] = 'user', 'builtin:' + d['name']
    return u


def strip(m):
    return {k: v for k, v in m.items() if k not in E.TIMING_METRICS}


def planned(d):
    rows = []
    rec = E.run_one(d, sink=lambda r: rows.append((r[0], r[1], r[2])), twice=False)
    return rec, [r[1:] for r in rows if r[0] == EXPAND], [r[1:] for r in rows if r[0] == PATH]


@pytest.mark.parametrize('name', ['bfs', 'dijkstra', 'astar', 'greedy', 'weighted_astar'])
def test_search_planners_identical(name):
    for d in runs('planning', 'arena-nav-50', name, 4) + runs('planning', 'depot-narrow-30',
                                                              name, 2):
        native, n_exp, n_path = planned(d)
        api, a_exp, a_path = planned(wrapped(d))
        assert native['status'] == api['status']
        assert strip(native['metrics']) == strip(api['metrics'])
        assert n_exp == a_exp and n_path == a_path
        assert api['report']['n_problems'] == 0 and api['report']['clamped'] == 0


def test_dstar_lite_identical():
    # the wrapper's measurement adds the path in D* Lite's own order (compensated sum()),
    # so length and cost are byte-identical too (Gautham, 2026-11-06)
    cases = runs('planning', 'arena-nav-50', 'dstar_lite', 4)
    cases += runs('planning', 'depot-narrow-30', 'dstar_lite', 2)
    for d in cases:
        native, _, n_path = planned(d)
        api, _, a_path = planned(wrapped(d))
        assert native['status'] == api['status'] and n_path == a_path
        assert strip(native['metrics']) == strip(api['metrics'])


def test_user_paths_add_up_sequentially():
    # a user's file is never measured with D* Lite's summation, whatever it is called
    from coco_lab import api_builtins
    assert all(api_builtins.algorithm(n).summation == 'sequential'
               for n in api_builtins.PLANNERS if n != 'dstar_lite')
    assert api_builtins.algorithm('dstar_lite').summation == 'compensated'


def poses(d):
    out = []
    rec = E.run_one(d, on_tick=lambda a, t: out.append(tuple(a.pose)), twice=False)
    return rec, out


@pytest.mark.parametrize('name,ticks', [('dwa', 400), ('rpp', 400), ('mppi', 40)])
def test_controllers_identical(name, ticks):
    for d in runs('control', 'arena-nav-50', name, 2, ticks):
        native, n_poses = poses(d)
        api, a_poses = poses(wrapped(d))
        assert native['status'] == api['status'] and native['fail_tick'] == api['fail_tick']
        assert strip(native['metrics']) == strip(api['metrics'])
        assert n_poses == a_poses and len(n_poses) >= 5
        assert api['report']['clamped'] == 0


@pytest.mark.parametrize('name', ['mcl', 'mcl_augmented', 'ekf'])
def test_localisers_identical(name):
    for d in runs('localisation', 'arena-nav-50', name, 1, 250):
        native, n_poses = poses(d)
        api, a_poses = poses(wrapped(d))
        assert native['status'] == api['status']
        assert strip(native['metrics']) == strip(api['metrics'])
        assert native['series'] == api['series']
        assert n_poses == a_poses
