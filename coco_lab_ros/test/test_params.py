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
The overlay merge, and what it does to the mission's real file.

Acceptance criterion J4: the mission ``nav2_params.yaml`` is byte-identical
to Phase 1B's ``e06dc94``, and the merged parameters differ from it ONLY in
``planner_server.planner_plugins`` and the new ``NavFnAStar`` block.
"""

import hashlib
import os

from coco_lab_ros import params

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(PKG)
MISSION = os.path.join(REPO, 'gazebo_models', 'config', 'nav2_params.yaml')
OVERLAY = os.path.join(PKG, 'config', 'nav2_lab_overlay.yaml')

#: SHA-256 of gazebo_models/config/nav2_params.yaml at e06dc94 (SESSION_LOG
#: 1C-0, measured from `git show e06dc94:...`).
MISSION_SHA256 = \
    '06c308aff78d4e7327212bbca280f62be7a7baef604ae41676e886b72301db8c'


def test_nested_mappings_merge_and_lists_are_replaced():
    base = {'a': {'b': 1, 'c': [1, 2], 'd': {'e': 1}}, 'x': 5}
    over = {'a': {'c': [9], 'd': {'f': 2}}, 'y': 6}
    out = params.deep_merge(base, over)
    assert out == {'a': {'b': 1, 'c': [9], 'd': {'e': 1, 'f': 2}},
                   'x': 5, 'y': 6}
    assert base == {'a': {'b': 1, 'c': [1, 2], 'd': {'e': 1}}, 'x': 5}
    out['a']['d']['e'] = 99
    assert base['a']['d']['e'] == 1          # no shared structure


def test_dump_is_deterministic():
    a = {'z': 1, 'a': {'y': [1, 2], 'b': 0.5}}
    b = {'a': {'b': 0.5, 'y': [1, 2]}, 'z': 1}
    assert params.dump(a) == params.dump(b)


def test_the_mission_file_is_byte_identical_to_1b():
    with open(MISSION, 'rb') as f:
        assert hashlib.sha256(f.read()).hexdigest() == MISSION_SHA256


def test_the_merge_changes_only_the_planner_list_and_navfnastar(tmp_path):
    out = tmp_path / 'merged.yaml'
    info = params.merge_files(MISSION, OVERLAY, str(out))
    changed = info['differing_keys']
    pre = 'planner_server.ros__parameters.'
    assert changed == sorted([
        pre + 'planner_plugins',
        pre + 'NavFnAStar.plugin', pre + 'NavFnAStar.tolerance',
        pre + 'NavFnAStar.use_astar', pre + 'NavFnAStar.allow_unknown'])
    merged = params.load(str(out))
    ps = merged['planner_server']['ros__parameters']
    assert ps['planner_plugins'] == ['GridBased', 'NavFn', 'NavFnAStar']
    base = params.load(MISSION)['planner_server']['ros__parameters']
    # GridBased and NavFn untouched; NavFnAStar is NavFn with use_astar on.
    assert ps['GridBased'] == base['GridBased']
    assert ps['NavFn'] == base['NavFn']
    assert ps['NavFnAStar'] == dict(base['NavFn'], use_astar=True)
    # The mission file itself was not touched by merging.
    test_the_mission_file_is_byte_identical_to_1b()


def test_merging_twice_gives_the_same_bytes(tmp_path):
    a, b = tmp_path / 'a.yaml', tmp_path / 'b.yaml'
    params.merge_files(MISSION, OVERLAY, str(a))
    params.merge_files(MISSION, OVERLAY, str(b))
    assert a.read_bytes() == b.read_bytes()


def test_the_cli(tmp_path, capsys):
    out = tmp_path / 'm.yaml'
    assert params.main(['merge', '--base', MISSION, '--overlay', OVERLAY,
                        '--out', str(out)]) == 0
    text = capsys.readouterr().out
    assert f'base {MISSION_SHA256}' in text
    assert 'differs planner_server.ros__parameters.planner_plugins' in text
