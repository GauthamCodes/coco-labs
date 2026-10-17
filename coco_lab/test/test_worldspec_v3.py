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
World Spec v3, the level kit (M6F.1): a superset that changes no v1 or v2 byte.

The v1/v2 proof replays ``fixtures/m6f/prechange_v1v2.json``, made by
``tools/m6/make_prechange_fixture.py`` at 0d1f37f, before this module existed,
and the first ten committed M1 determinism sessions
(``docs/v2/data/m1/determinism/``) against their committed Pyodide hashes.
"""

import copy
import gzip
import hashlib
import json
import math
import os

from coco_lab import worldspec_v3 as v3
from coco_lab.arena import Arena, InputEvent
from coco_lab.worldspec import (arena_map, canonical_bytes, normalize, SpecError,
                                terrain_map)
import pytest
import yaml

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


def _load(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return yaml.safe_load(f)


V1 = _load(REPO, 'worlds', 'coco_arena_v1.yaml')
V2 = _load(REPO, 'worlds', 'coco_arena_v2.yaml')
KIT = _load(HERE, 'fixtures', 'm6f', 'kit_demo_v3.yaml')
with open(os.path.join(HERE, 'fixtures', 'm6f', 'prechange_v1v2.json'), encoding='utf-8') as _f:
    PRE = json.load(_f)
SPECS = {'coco_arena_v1': V1, 'coco_arena_v2': V2}
M1 = os.path.join(REPO, 'docs', 'v2', 'data', 'm1', 'determinism')


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hashes(spec, seed, inputs, ticks, **kw):
    a = Arena(spec, seed, **kw)
    by = {}
    for e in inputs:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    return [a.step(by.get(a.tick, ())).state_hash for _ in range(ticks)]


# -- v1 and v2: not one byte changed ---------------------------------------------

def test_the_fixture_was_made_before_v3_existed():
    assert PRE['made_at_commit'].startswith('0d1f37f')


@pytest.mark.parametrize('name', sorted(SPECS))
def test_v1_and_v2_canonical_bytes_and_maps_are_the_prechange_ones(name):
    spec, pre = SPECS[name], PRE['specs'][name]
    assert _sha(canonical_bytes(spec)) == pre['canonical_sha256']
    assert v3.normalize(spec) == normalize(spec)          # the v3 reader hands them over
    m = arena_map(spec)
    assert _sha(m.occupancy) == pre['arena_map_sha256']
    assert m.content_hash() == pre['arena_map_content_hash']
    assert [m.width, m.height, m.resolution, list(m.origin)] == pre['arena_map_shape']
    if 'scan_map_sha256' in pre:
        assert _sha(terrain_map(spec, scan_only=True).occupancy) == pre['scan_map_sha256']


@pytest.mark.parametrize('name,k', [(n, k) for n in sorted(SPECS) for k in range(6)])
def test_prechange_sessions_replay_byte_for_byte_through_the_v3_reader(name, k):
    s = PRE['specs'][name]['sessions'][k]
    spec = v3.normalize(SPECS[name])
    assert _hashes(spec, s['seed'], s['inputs'], s['ticks'],
                   hash_version=s['hash_version']) == s['hashes']


@pytest.mark.parametrize('k', range(10))
def test_committed_m1_sessions_keep_their_pyodide_hashes(k):
    with open(os.path.join(M1, 'sessions.json'), encoding='utf-8') as f:
        session = json.load(f)['sessions'][k]
    with gzip.open(os.path.join(M1, 'hashes_pyodide-node.json.gz'), 'rt') as f:
        want = {str(s['id']): s['hashes'] for s in json.load(f)['sessions']}[str(k)]
    got = _hashes(v3.normalize(V1), session['seed'], session['inputs'], session['ticks'],
                  planner=session['planner'])
    assert got == want


# -- v2 written as a kit: the superset, concretely ---------------------------------

def test_v2_written_as_a_kit_lowers_to_the_same_boxes_elevation_and_maps():
    kit = v3.from_v2(V2)
    n, n2 = v3.normalize(kit), normalize(V2)
    assert n['spec_version'] == v3.SPEC_VERSION_V3
    assert n['boxes'] == n2['boxes'] and n['elevation'] == n2['elevation']
    assert arena_map(kit).occupancy == arena_map(V2).occupancy
    assert terrain_map(kit, scan_only=True).occupancy == \
        terrain_map(V2, scan_only=True).occupancy


@pytest.mark.parametrize('k', range(6))
def test_v2_written_as_a_kit_drives_tick_for_tick_like_v2(k):
    # Hash v1 hashes the model state alone: identical. Every input but the gated
    # grasp, which holds the COCO arena's targets on v2 and refuses on v3.
    s = PRE['specs']['coco_arena_v2']['sessions'][k]
    inputs = [e for e in s['inputs'] if e['kind'] != 'grasp']
    assert _hashes(v3.from_v2(V2), s['seed'], inputs, 150) == _hashes(V2, s['seed'], inputs, 150)


def test_hash_v2_binds_the_spelling_of_the_world():
    # ADR 0008: hash v2 commits to the canonical spec (state_v2.world_hash), so the
    # same geometry spelled as v3 is a different world there -- as it should be.
    s = PRE['specs']['coco_arena_v2']['sessions'][1]
    assert s['hash_version'] == 2
    inputs = [e for e in s['inputs'] if e['kind'] != 'grasp']
    assert _hashes(v3.from_v2(V2), s['seed'], inputs, 3, hash_version=2) \
        != _hashes(V2, s['seed'], inputs, 3, hash_version=2)


# -- the kit -----------------------------------------------------------------------

def test_the_demo_levels_robot_is_the_coco_arenas():
    assert KIT['robot'] == V2['robot']


def test_normalize_is_idempotent_and_canonical():
    n = v3.normalize(KIT)
    assert v3.normalize(n) == n
    assert canonical_bytes(n) == canonical_bytes(KIT)
    respelled = copy.deepcopy(KIT)
    respelled['bounds']['x_max'] = 14.0
    respelled['kit'][0]['height'] = 2
    assert canonical_bytes(respelled) == canonical_bytes(KIT)
    assert all(isinstance(x, float) for x in n['bounds'].values())


def test_a_door_cuts_its_wall_into_solid_stretches():
    boxes = {b['id']: b for b in v3.normalize(KIT)['boxes']}
    assert 'wall_mid' not in boxes
    lo, hi = boxes['wall_mid#0'], boxes['wall_mid#1']
    assert lo['center'][1] + lo['size'][1] / 2 == pytest.approx(2.5)
    assert hi['center'][1] - hi['size'][1] / 2 == pytest.approx(3.5)
    assert all(b['z'] == b['height'] / 2 for b in boxes.values())   # all on the floor


def test_solids_lower_to_v2_box_kinds_and_ramps_to_elevation():
    n = v3.normalize(KIT)
    kinds = {b['id']: b['kind'] for b in n['boxes']}
    assert kinds['rack_1'] == kinds['bench_1'] == kinds['pallet_1'] == 'obstacle'
    assert kinds['wall_s'] == 'wall'
    assert [(e['id'], e['kind']) for e in n['elevation']] == [('ramp_1', 'wedge'),
                                                              ('deck_1', 'platform')]


def test_objects_resolve_their_support_height():
    z = {o['id']: o['z'] for o in v3.objects(v3.normalize(KIT))}
    assert z == {'can_floor': 0.0, 'bottle_bench': 0.75, 'can_shelf': 1.2,
                 'can_deck': 0.649839392466, 'crate_floor': 0.0}


def test_actor_lanes_are_kinematic_functions_of_time():
    n = v3.normalize(KIT)
    walker, forklift = v3.elements(n, 'actor')
    assert v3.actor_pose(walker, 0.0) == (2.0, 2.0, 0.0)
    assert v3.actor_pose(walker, 5.0)[:2] == pytest.approx((4.0, 2.0))   # on its way back
    assert v3.actor_pose(walker, 5.0)[2] == pytest.approx(math.pi)
    assert v3.actor_pose(walker, 7.0)[:2] == pytest.approx((2.0, 2.0))   # a full cycle
    assert v3.actor_pose(forklift, 0.0)[:2] == pytest.approx((9.0, 0.9))  # phase 1 m in
    corners = v3.actor_corners(forklift, 0.0)
    assert sorted(round(c[0], 9) for c in corners) == [8.1, 8.1, 9.9, 9.9]


def test_the_arena_runs_a_v3_level_with_terrain_and_plans_through_the_door():
    a = Arena(KIT, seed=5)
    assert a.terrain is not None and a.spec['spec_version'] == v3.SPEC_VERSION_V3
    ticks = [a.step([InputEvent(0, 'goal', x=9.0, y=2.5)])]
    ticks += [a.step(()) for _ in range(450)]
    assert ticks[-1].pose[0] > 8.0                # through the partition's only door
    assert not any(t.contact for t in ticks)


def test_the_robot_climbs_the_kit_ramp_onto_the_deck():
    a = Arena(KIT, seed=5)
    a.pose = (8.0, 5.0, 0.0)
    ticks = [a.step([InputEvent(a.tick, 'teleop', linear=0.3)]) for _ in range(110)]
    assert max(t.z for t in ticks) == pytest.approx(0.649839392466, abs=1e-9)
    assert not any(t.contact for t in ticks)


def test_the_gated_grasp_refuses_on_a_v3_level_and_invents_no_targets():
    a = Arena(KIT, seed=5)
    a.step([InputEvent(0, 'grasp')])
    assert a.grasp is None and 'Grasp Assist' in a.grasp_notice


def test_passable_width_is_derived_from_the_robot_and_the_resolution():
    n = v3.normalize(KIT)
    assert v3.passable_width(n) == pytest.approx(2 * (0.22 + 0.1))


# -- refusals: never guessed ----------------------------------------------------------

def _kit_index(kit_id):
    return next(i for i, e in enumerate(KIT['kit']) if e['id'] == kit_id)


def _set(kit_id, **kw):
    def mutate(s):
        s['kit'][_kit_index(kit_id)].update(kw)
    return mutate


def _add(element):
    def mutate(s):
        s['kit'].append(element)
    return mutate


BAD = [
    (_set('pallet_1', height=0.15), 'below the LiDAR beam'),
    (_set('door_mid', width=0.5), 'narrower than the robot can pass'),
    (_set('door_mid', at=0.3), 'runs past the end'),
    (_add({'id': 'door_2', 'kind': 'door', 'wall': 'wall_mid', 'at': 3.5, 'width': 1.0}),
     'overlap'),
    (_add({'id': 'door_3', 'kind': 'door', 'wall': 'rack_1', 'at': 1.0, 'width': 1.0}),
     'is not a wall'),
    (_add({'id': 'bench_x', 'kind': 'bench', 'center': [3, 6.0], 'size': [0.6, 0.4],
           'height': 0.7}), 'stands in its -y aisle'),
    (_set('rack_1', aisle=0.5), 'aisle 0.5 m is narrower'),
    (_set('rack_1', aisles=['+z']), 'aisles'),
    (_set('rack_1', shelves=[1.2, 0.4]), 'ascending'),
    (_set('ramp_1', yaw=1.5707963), 'axis-aligned'),
    (_set('ramp_1', rise=0.5), 'onto a platform'),
    (_set('ramp_1', foot=[8.0, 5.0]), 'does not meet'),
    (_set('can_floor', at=[11, 2]), "inside 'pallet_1'"),
    (_set('can_floor', item='nothing'), 'not in the catalog'),
    (_set('can_shelf', shelf=7), 'shelf index'),
    (_set('bottle_bench', at=[12, 8]), 'not on'),
    (_set('walker_1', path=[[9, 2], [12, 2]]), "runs through 'pallet_1'"),
    (_set('walker_1', path=[[2, 2], [15, 2]]), 'outside the bounds'),
    (_set('forklift_1', actor='robot'), 'actor'),
    (_set('wall_s', to=[14, 1]), 'along x or along y'),
    (_set('wall_s', id='wall_n'), 'used twice'),
    (_set('bench_1', legs=4), 'unknown keys'),
    (_add({'id': 'x', 'kind': 'teleporter'}), 'kind'),
    (lambda s: s.update(boxes=[]), 'derived from the kit'),
    (lambda s: s.update(spec_version='coco.world_spec.v4'), 'spec_version'),
    (lambda s: s.update(frame='map'), 'frame'),
    (lambda s: s['catalog'][0].update(magnetic='yes'), 'magnetic'),
    (lambda s: s['arena'].update(unknown='free'), 'unknown'),
]


@pytest.mark.parametrize('mutate,match', BAD)
def test_bad_kits_are_refused_with_the_reason(mutate, match):
    s = copy.deepcopy(KIT)
    mutate(s)
    with pytest.raises(SpecError, match=match):
        v3.normalize(s)
