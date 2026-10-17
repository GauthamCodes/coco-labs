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

"""The COCO Depot level (M6F.3; docs/v2/m6/DEPOT_DESIGN.md)."""

import importlib.util
import json
import os
import sys

from coco_lab import grasp_assist as ga
from coco_lab import worldspec_v3 as v3
from coco_lab.arena import Arena, InputEvent, PLANNERS
from coco_lab.grasp import TARGET_DIAMETER, TARGET_HEIGHT
from coco_lab.search import search
from coco_lab.sketch import _nearest_free
from coco_lab.worldspec import normalize
import pytest
import yaml

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


def _load(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return yaml.safe_load(f)


DEPOT = _load(REPO, 'worlds', 'coco_depot_v1.yaml')
V2 = _load(REPO, 'worlds', 'coco_arena_v2.yaml')
N = normalize(DEPOT)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_yaml_is_what_the_layout_script_writes():
    mk = _module(os.path.join(REPO, 'worlds', 'tools', 'make_coco_depot_v1.py'), 'mk_depot')
    with open(os.path.join(REPO, 'worlds', 'coco_depot_v1.yaml'), encoding='utf-8') as f:
        assert f.read() == mk.dump(mk.build())


def test_the_depot_is_48_by_32_with_the_coco_arenas_robot_and_ramp():
    b = N['bounds']
    assert (b['x_max'] - b['x_min'], b['y_max'] - b['y_min']) == (48.0, 32.0)
    assert DEPOT['robot'] == V2['robot']
    arena_ramp = next(e for e in normalize(V2)['elevation'] if e['kind'] == 'wedge')
    ramp = v3.elements(N, 'ramp')[0]
    assert (ramp['run'], ramp['rise'], ramp['width']) == \
        (arena_ramp['run'], arena_ramp['rise'], arena_ramp['width'])
    assert N['arena']['resolution'] == 0.1


def test_the_six_zones_are_there():
    labels = {z['label'] for z in v3.zones(N, 'region')}
    assert labels == {'Loading dock', 'High-bay aisles', 'Mezzanine', 'Office block',
                      'Workshop maze', 'Forklift lanes'}
    assert len(v3.zones(N, 'drop')) == 4
    kinds = {e['kind'] for e in N['kit']}
    assert kinds >= {'wall', 'door', 'rack', 'bench', 'pallet', 'ramp', 'platform', 'zone',
                     'object', 'actor'}
    assert len(v3.elements(N, 'actor')) == 4


def test_every_solid_stands_above_the_lidar_beam():
    beam = N['robot']['ground_clearance'] + N['robot']['lidar']['mount'][2]
    assert all(bx['height'] > beam for bx in N['boxes'])


def test_the_graspable_catalog_repeats_the_stacks_verified_targets():
    graspable = [c for c in N['catalog'] if c['id'] in
                 ('can_small', 'bottle_steel', 'canister', 'can_large')]
    assert sorted(c['diameter'] for c in graspable) == sorted(TARGET_DIAMETER.values())
    assert all(c['height'] == TARGET_HEIGHT and c['magnetic'] for c in graspable)
    lo, hi = ga.FINGER_VERIFIED
    assert all(lo <= ga.width(c) <= hi for c in graspable)


DESIGNED = {
    'bad_too_wide': 'too_wide', 'bad_crate': 'too_wide', 'bad_too_low': 'out_of_reach',
    'bad_on_shelf': 'out_of_reach', 'bad_on_desk': 'out_of_reach',
    'bad_on_bench': 'out_of_reach', 'bad_not_magnetic': 'not_magnetic',
}


def test_each_object_has_its_designed_static_affordance():
    aff = ga.affordances(N)
    assert len(aff) == 18
    for oid, a in aff.items():
        if oid in DESIGNED:
            assert ga.first_reason(a['reasons']) == DESIGNED[oid], oid
        else:   # the ten graspable ones, and bad_blocked (blocked needs the map: M6F.5)
            assert a['reasons'] == [], oid
            assert a['band_z'] == pytest.approx(0.128, abs=1e-12)
    assert set(aff['bad_crate']['reasons']) == {'too_wide', 'out_of_reach', 'not_magnetic'}


def test_the_reach_envelope_is_derived_and_the_stacks_grasp_height_is_inside_it():
    lo, hi = ga.reach_band()
    assert lo < 0.128 <= hi < 0.13
    assert ga.reachable(ga.band_height({'z': 0.0, 'shape': 'cylinder', 'height': 0.158},
                                       0.0))


@pytest.fixture(scope='module')
def depot_arena():
    return Arena(DEPOT, seed=1)


GOALS = {'loading dock': (46.5, 6.5), 'high-bay aisle 1': (20.0, 17.6),
         'high-bay aisle 3': (28.5, 26.0), 'office NE room': (10.0, 29.0),
         'office SW room': (2.5, 23.0), 'mezzanine deck': (42.0, 29.5),
         'forklift lane': (30.0, 12.0)}


@pytest.mark.parametrize('name', sorted(GOALS))
def test_a_planner_reaches_every_zone_from_the_start(depot_arena, name):
    a = depot_arena
    s = _nearest_free(a.grid, a.plan_map.cell_at(a.start[0], a.start[1]))
    t = _nearest_free(a.grid, a.plan_map.cell_at(*GOALS[name]))
    assert search(a.grid, s, t, **PLANNERS['astar']).found


def test_every_maze_dead_end_object_is_reachable(depot_arena):
    a = depot_arena
    s = _nearest_free(a.grid, a.plan_map.cell_at(a.start[0], a.start[1]))
    for o in v3.objects(N):
        if o['id'].startswith('obj_maze'):
            t = _nearest_free(a.grid, a.plan_map.cell_at(o['x'] + 0.3, o['y']))
            assert search(a.grid, s, t, **PLANNERS['astar']).found, o['id']


def test_the_robot_drives_up_the_ramp_onto_the_mezzanine():
    a = Arena(DEPOT, seed=1)
    ramp = v3.elements(N, 'ramp')[0]
    a.pose = (ramp['foot'][0] - 0.6, ramp['foot'][1], 0.0)
    ticks = [a.step([InputEvent(a.tick, 'teleop', linear=0.3)]) for _ in range(120)]
    assert max(t.z for t in ticks) == pytest.approx(ramp['rise'], abs=1e-9)
    assert not any(t.contact for t in ticks)


def test_no_two_actors_ever_meet_in_ten_minutes():
    actors = v3.elements(N, 'actor')
    for i, a in enumerate(actors):
        for b in actors[i + 1:]:
            for k in range(0, 6000):
                t = k * 0.1
                cb = v3.actor_corners(b, t)
                xs, ys = [p[0] for p in cb], [p[1] for p in cb]
                assert not v3.obb_hits_rect(v3.actor_corners(a, t),
                                            (min(xs), max(xs), min(ys), max(ys))), \
                    (a['id'], b['id'], t)


def test_the_committed_output_checksums_reproduce(tmp_path):
    sys.path.insert(0, os.path.join(REPO, 'tools', 'm6'))
    import gen_level
    with open(os.path.join(REPO, 'docs', 'v2', 'm6', 'data', 'coco_depot_v1_outputs.json'),
              encoding='utf-8') as f:
        want = json.load(f)
    _, _, written, _ = gen_level.generate(os.path.join(REPO, 'worlds', 'coco_depot_v1.yaml'),
                                          str(tmp_path), [0.1, 0.05], 0.05, False)
    assert written == want['outputs']
    assert set(want['gz_sdf_check'].values()) == {0}
