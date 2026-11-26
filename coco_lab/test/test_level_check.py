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
"""R5.5: the world editor's live check (coco_lab.level_check) on levels built from scratch."""
import copy
from pathlib import Path

import yaml

from coco_lab.level_check import check

REPO = Path(__file__).resolve().parents[2]
DEPOT = yaml.safe_load((REPO / 'worlds/coco_depot_v1.yaml').read_text(encoding='utf-8'))


def small(extra=(), start=(2.0, 2.0)):
    """A 10 x 8 m room, as the editor makes one: four walls, a start, the Depot's robot."""
    kit = [{'id': 'w_s', 'kind': 'wall', 'from': [0, 0], 'to': [10, 0], 'thickness': 0.15, 'height': 2.0},
           {'id': 'w_n', 'kind': 'wall', 'from': [0, 8], 'to': [10, 8], 'thickness': 0.15, 'height': 2.0},
           {'id': 'w_w', 'kind': 'wall', 'from': [0, 0], 'to': [0, 8], 'thickness': 0.15, 'height': 2.0},
           {'id': 'w_e', 'kind': 'wall', 'from': [10, 0], 'to': [10, 8], 'thickness': 0.15, 'height': 2.0}]
    return {'spec_version': 'coco.world_spec.v3', 'id': 'editor_test', 'title': 'Editor test', 'frame': 'world',
            'world_to_map': [0.0, 0.0], 'bounds': {'x_min': 0.0, 'x_max': 10.0, 'y_min': 0.0, 'y_max': 8.0},
            'robot': copy.deepcopy(DEPOT['robot']), 'start': {'x': start[0], 'y': start[1], 'theta': 0.0},
            'arena': {'resolution': 0.1, 'margin': 0.5, 'dt': 0.1, 'unknown': 'blocked'}, 'kit': kit + list(extra)}


def test_an_open_room_reaches_its_goals():
    r = check(small(), [[8, 6], [5, 4]])
    assert r['ok'], r['errors']
    assert r['start']['fits']
    assert [g['reachable'] for g in r['goals']] == [True, True]
    assert 6.0 < r['goals'][0]['path_m'] < 9.0                       # ~ the straight line (7.2 m), on 8-connected cells
    # the lowered spec it returns is accepted by the reader as it is (the derived keys equal the kit's)
    assert check(r['spec'], [[8, 6]])['ok'] and r['spec']['boxes']


def test_a_sealed_room_makes_a_goal_unreachable():
    inner = [{'id': 'c_s', 'kind': 'wall', 'from': [6, 4], 'to': [10, 4], 'thickness': 0.15, 'height': 2.0},
             {'id': 'c_w', 'kind': 'wall', 'from': [6, 4], 'to': [6, 8], 'thickness': 0.15, 'height': 2.0}]
    r = check(small(inner), [[8, 6]])
    assert not r['ok'] and not r['goals'][0]['reachable']
    assert any('not reachable' in e for e in r['errors'])
    # a door wide enough for COCO opens it
    door = {'id': 'd', 'kind': 'door', 'wall': 'c_w', 'at': 2.0, 'width': 1.2}
    assert check(small(inner + [door]), [[8, 6]])['ok']


def test_coco_must_fit_at_its_start():
    box = {'id': 'b', 'kind': 'bench', 'center': [2.0, 2.0], 'size': [1.0, 1.0], 'height': 0.8}
    r = check(small([box]), [[8, 6]])
    assert not r['ok'] and not r['start']['fits']
    assert any('does not fit at the start' in e for e in r['errors'])


def test_the_validators_refusals_come_through_in_its_words():
    bad = small()
    bad['kit'].append({'id': 'w_s', 'kind': 'wall', 'from': [1, 1], 'to': [2, 1], 'thickness': 0.15, 'height': 2.0})
    r = check(bad, [[8, 6]])
    assert not r['ok'] and r['errors'] and r['goals'] == []
    off = check(small(), [[30, 30]])
    assert not off['ok'] and 'outside the map' in off['errors'][0]
