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
"""R6.B2: the built-in planners written through the algorithm API -- reference tests."""
from pathlib import Path

from coco_lab import experiments as ex
import pytest

REPO = Path(__file__).resolve().parents[2]
NEW = ex.API_BUILTINS['planning']


@pytest.fixture(scope='module')
def runs():
    spec = {'schema': ex.SCHEMA, 'world': 'coco_arena_v1', 'family': 'planning', 'seed': 1,
            'algorithms': [{'name': n} for n in ('astar',) + NEW],
            'scenarios': {'kind': 'sampled', 'n': 2, 'seed': 2}}
    p = ex.plan(spec)
    return p, ex.run_all(p)


def _by(runs, name):
    return [r for r in runs[1] if r['algorithm'] == name]


def test_every_api_builtin_is_deterministic_and_finds_a_clear_path(runs):
    for name in NEW:
        rs = _by(runs, name)
        assert all(r['deterministic'] for r in rs), name           # run twice: the same chain
        assert [r['status'] for r in rs] == ['found', 'found'], name   # 'collision' if not clear


def test_theta_star_is_never_longer_than_grid_astar(runs):
    a = {r['scenario']: r['metrics']['path_length_m'] for r in _by(runs, 'astar')}
    for r in _by(runs, 'theta_star'):
        assert r['metrics']['path_length_m'] <= a[r['scenario']] + 1e-9


def test_rrt_star_refines_rrt(runs):
    rrt = {r['scenario']: r['metrics']['path_length_m'] for r in _by(runs, 'rrt')}
    for r in _by(runs, 'rrt_star'):
        assert r['metrics']['path_length_m'] <= rrt[r['scenario']]


def test_the_spec_names_the_builtin_and_records_its_code(runs):
    p = runs[0]
    assert ex.plan(p['spec'])['id'] == p['id']                        # a fixed point
    for a in p['spec']['algorithms'][1:]:
        assert a['name'] in NEW and len(a['code_sha256']) == 64
    with pytest.raises(ex.SpecError, match='differs'):
        ex.plan(dict(p['spec'], algorithms=[{'name': 'rrt', 'code_sha256': '0' * 64}]))


def test_theta_star_is_gautham_anils_entry_unchanged():
    """The built-in is the entry's code; only its docstring's first paragraph differs."""
    entry = (REPO / 'leaderboard/submissions/depot-nav-100/theta_star/algorithm.py').read_text()
    built = ex.api_builtin_source('theta_star')
    assert entry.split('"""', 2)[2] == built.split('"""', 2)[2]
    assert 'Gautham Anil' in built


def test_ekf_scanmatch_tracks_from_a_known_start():
    """EKF + scan matching: a tracker (deterministic; within half a metre on a short run)."""
    spec = {'schema': ex.SCHEMA, 'world': 'coco_depot_v1', 'family': 'localisation', 'seed': 1,
            'algorithms': [{'name': 'ekf_scanmatch'}],
            'scenarios': {'kind': 'suite', 'id': 'loc-track-30', 'version': 1},
            'limits': {'max_ticks': 300}}
    p = ex.plan(spec)
    r = ex.run_all(dict(p, runs=p['runs'][:1]))[0]
    assert r['deterministic'] and r['status'] != 'error'
    assert r['metrics']['mean_err_xy_m'] < 0.5
