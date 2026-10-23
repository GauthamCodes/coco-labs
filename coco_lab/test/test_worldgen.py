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
One level, three outputs (M6F.2): the generators, on the Proving Ground and a kit level.

The Proving Ground is the COCO arena: its generated Nav2 map must be the Stack's
saved map byte for byte, and its generated SDF the Stack's world, model for model;
``docs/v2/m6/PROVING_GROUND.md`` reports every difference.
"""

import json
import math
import os
import shutil
import subprocess
import sys

from coco_lab import worldgen
from coco_lab import worldspec_v3 as v3
from coco_lab.maps import OCCUPIED, UNKNOWN
from coco_lab.worldspec import arena_map, normalize
import pytest
import yaml

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
GZ = os.path.join(REPO, 'gazebo_models')


def _load(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return yaml.safe_load(f)


def _read(*parts, mode='r'):
    with open(os.path.join(*parts), mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f:
        return f.read()


V1 = _load(REPO, 'worlds', 'coco_arena_v1.yaml')
V2 = _load(REPO, 'worlds', 'coco_arena_v2.yaml')
KIT = _load(HERE, 'fixtures', 'm6f', 'kit_demo_v3.yaml')
TEMPLATE = _read(GZ, 'worlds', 'coco_navigation.world')
#: the round trip's tolerance (m): SDF text keeps Python's shortest repr, exact;
#: STL vertices are float32, ~1e-7 m at these sizes
TOL = 1e-6


# -- the Proving Ground: the COCO arena ------------------------------------------------

@pytest.mark.parametrize('spec', [V1, V2], ids=['v1', 'v2'])
def test_the_nav2_map_is_the_stacks_saved_map_byte_for_byte(spec):
    pgm, ym = worldgen.nav2_map(spec, 'coco_navigation.pgm')
    assert pgm == _read(GZ, 'maps', 'coco_navigation.pgm', mode='rb')
    assert ym == _read(GZ, 'maps', 'coco_navigation.yaml')


def test_the_generated_world_has_every_box_of_the_stacks_world_exactly():
    sdf, _ = worldgen.sdf_world(V2, TEMPLATE)
    gen, orig = worldgen.sdf_footprints(sdf), worldgen.sdf_footprints(TEMPLATE)
    assert set(orig) <= set(gen) and len(orig) == 71        # 70 boxes and the ground
    for name, o in orig.items():
        assert gen[name] == o, name
    # the world's physics, systems, lights and scene are the template's, untouched
    import xml.etree.ElementTree as ET
    keep = [ET.tostring(e) for e in ET.fromstring(TEMPLATE).find('world') if e.tag != 'model']
    got = [ET.tostring(e) for e in ET.fromstring(sdf).find('world') if e.tag != 'model']
    assert [k.split() for k in keep] == [g.split() for g in got]


def test_the_ramps_and_platforms_match_what_the_stacks_launch_spawns():
    # The Stack spawns them from full_world_robo.launch.py (traverse:=true), not the
    # world file; lab_web/public/assets3d/arena.json is that spawn, converted (M4.2).
    arena = json.loads(_read(REPO, 'lab_web', 'public', 'assets3d', 'arena.json'))
    sdf, files = worldgen.sdf_world(V2, TEMPLATE)
    gen = worldgen.sdf_footprints(sdf)
    spawned = [f for f in arena['footprints'] if f['kind'] in ('ramps', 'platforms')]
    extra = sorted(set(gen) - set(worldgen.sdf_footprints(TEMPLATE)))
    assert len(extra) == len(spawned) == 12
    for f in spawned:
        if f['kind'] == 'ramps':
            m = [n for n in extra if gen[n]['shape'] == 'mesh'
                 and math.dist(gen[n]['pose'][:2], f['foot'][:2]) < 1e-12
                 and abs(math.remainder(gen[n]['pose'][5] - f['yaw'], 2 * math.pi)) < 1e-9]
            assert len(m) == 1, f['name']
            tris = worldgen.read_stl(files[gen[m[0]]['dims']])
            xs = [v[0] for t in tris for v in t]
            zs = [v[2] for t in tris for v in t]
            assert max(xs) == pytest.approx(f['run'], abs=TOL)
            assert max(zs) == pytest.approx(f['rise'], abs=TOL)
        else:
            m = [n for n in extra if gen[n]['shape'] == 'box'
                 and math.dist(gen[n]['pose'][:3], f['center']) < 1e-9]
            assert len(m) == 1, f['name']
            assert gen[m[0]]['dims'] == pytest.approx(f['size'], abs=1e-9)


def test_the_generated_wedge_is_the_stacks_wedge_mesh():
    stack = worldgen.read_stl(_read(GZ, 'meshes', 'ramp_wedge_18.stl', mode='rb'))
    wedge = next(e for e in normalize(V2)['elevation'] if e['kind'] == 'wedge')
    ours = worldgen.read_stl(worldgen.wedge_stl(wedge['run'], wedge['rise'], wedge['width']))
    key = sorted({tuple(round(c, 6) for c in v) for t in stack for v in t})
    assert key == sorted({tuple(round(c, 6) for c in v) for t in ours for v in t})
    assert len(stack) == len(ours) == 8


# -- the round trip: SDF back to footprints ---------------------------------------------

@pytest.fixture(scope='module')
def kit_world():
    return worldgen.sdf_world(KIT, TEMPLATE, world_name='kit_demo_v3')


def test_every_box_round_trips_through_the_sdf(kit_world):
    sdf, _ = kit_world
    got = worldgen.sdf_footprints(sdf)
    for b in normalize(KIT)['boxes']:
        g = got[b['id']]
        assert g['static'] and g['shape'] == 'box'
        assert g['pose'] == pytest.approx([*b['center'], b['z'], 0, 0, 0], abs=TOL)
        assert g['dims'] == pytest.approx([*b['size'], b['height']], abs=TOL)


def test_every_wedge_round_trips_through_its_mesh(kit_world):
    sdf, files = kit_world
    got = worldgen.sdf_footprints(sdf)
    for e in normalize(KIT)['elevation']:
        g = got[e['id']]
        if e['kind'] == 'platform':
            assert g['pose'][:3] == pytest.approx([*e['center'], e['size'][2] / 2], abs=TOL)
            assert g['dims'] == pytest.approx(e['size'], abs=TOL)
            continue
        assert g['pose'] == pytest.approx([*e['foot'], 0, 0, 0, e['yaw']], abs=TOL)
        verts = [v for t in worldgen.read_stl(files[g['dims']]) for v in t]
        c, s = math.cos(e['yaw']), math.sin(e['yaw'])
        world = [(g['pose'][0] + c * x - s * y, g['pose'][1] + s * x + c * y, z)
                 for x, y, z in verts]
        x0, x1 = sorted((e['foot'][0], e['foot'][0] + c * e['run']))
        assert min(p[0] for p in world) == pytest.approx(x0, abs=TOL)
        assert max(p[0] for p in world) == pytest.approx(x1, abs=TOL)
        assert max(p[1] for p in world) - min(p[1] for p in world) == \
            pytest.approx(e['width'], abs=TOL)
        assert max(p[2] for p in world) == pytest.approx(e['rise'], abs=TOL)


def test_objects_and_actors_are_models_with_collision_bodies(kit_world):
    sdf, files = kit_world
    got = worldgen.sdf_footprints(sdf)
    s = normalize(KIT)
    for o in v3.objects(s):
        g = got[o['id']]
        h = o['height'] if o['shape'] == 'cylinder' else o['size'][2]
        assert not g['static'] and g['pose'][2] == pytest.approx(o['z'] + h / 2, abs=TOL)
    for a in v3.elements(s, 'actor'):
        g = got[a['id']]        # Lab 5's lesson: an actor without one passes through
        assert g['shape'] == 'box' and not g['static']
        assert g['dims'] == pytest.approx([*a['footprint'], a['height']], abs=TOL)
        x, y, yaw = v3.actor_pose(a, 0.0)
        assert g['pose'] == pytest.approx([x, y, 0, 0, 0, yaw], abs=TOL)
    schedule = json.loads(files['actors.json'])
    assert [a['id'] for a in schedule['actors']] == ['walker_1', 'forklift_1']


def test_an_object_is_spawnable_on_its_own():
    text = worldgen.object_sdf(KIT, 'can_floor')
    got = worldgen.sdf_footprints(text)
    assert list(got) == ['can_floor'] and got['can_floor']['shape'] == 'cylinder'
    assert got['can_floor']['dims'] == pytest.approx([0.014, 0.158])


# -- the Nav2 map against the model ----------------------------------------------------

def _pgm_occupancy(pgm):
    w, h, px = worldgen.read_pgm(pgm)
    back = {v: k for k, v in worldgen.PGM_VALUE.items()}
    return w, h, bytes(back[p] for p in px)


@pytest.mark.parametrize('res', [0.1, 0.05])
def test_pgm_pixels_are_the_models_occupancy_outside_the_elevated_solids(res):
    pgm, _ = worldgen.nav2_map(KIT, 'kit.pgm', res)
    w, h, occ = _pgm_occupancy(pgm)
    nav = worldgen.nav_map(KIT, res)
    assert (w, h, occ) == (nav.width, nav.height, nav.occupancy)
    drive = arena_map(worldgen.with_resolution(KIT, res))
    assert (drive.width, drive.height, drive.origin) == (w, h, nav.origin)
    # Inside an elevated solid's footprint the two differ by design: the Nav2 map is
    # what a flat 2D scan sees (the silhouette above the beam), the model drives the
    # terrain (ledges occupied, ramp surfaces free). One cell of dilation: the
    # rasteriser and the ledge test both reach one cell past a footprint.
    elevated = {e['id'] for e in normalize(KIT)['elevation']}
    sil = [(x0 - res, x1 + res, y0 - res, y1 + res)
           for rid, (x0, x1, y0, y1) in v3.static_rects(normalize(KIT)) if rid in elevated]
    differ = outside = 0
    for row in range(h):
        for col in range(w):
            x, y = drive.cell_centre(row, col)
            if any(a <= x <= b and c <= y <= d for a, b, c, d in sil):
                continue
            outside += 1
            differ += occ[row * w + col] != drive.occupancy[row * w + col]
    assert outside > 0.9 * w * h and differ == 0
    # and inside: the silhouette's rim is occupied, as the 2D scan sees it
    x0, x1, y0, y1 = worldgen.silhouettes(KIT)[0]
    rim = nav.cell_at(x0 + res / 4, (y0 + y1) / 2)
    assert nav.at(rim) == OCCUPIED
    assert nav.at(nav.cell_at((x0 + x1) / 2, (y0 + y1) / 2)) == UNKNOWN


def test_the_v1_nav_map_is_the_arena_map():
    assert worldgen.nav_map(V1).occupancy == arena_map(V1).occupancy


@pytest.mark.parametrize('res', [0.1, 0.05])
def test_the_yaml_origin_and_resolution_place_every_pixel(res):
    _, text = worldgen.nav2_map(KIT, 'kit.pgm', res)
    y = yaml.safe_load(text)
    nav = worldgen.nav_map(KIT, res)
    assert y['resolution'] == res and y['mode'] == 'trinary' and y['image'] == 'kit.pgm'
    assert y['origin'] == [nav.origin[0], nav.origin[1], 0]
    s = normalize(KIT)
    assert y['origin'][:2] == pytest.approx([s['bounds']['x_min'] - s['arena']['margin'],
                                             s['bounds']['y_min'] - s['arena']['margin']])
    # map_server: pixel (col, row) from the top-left has its centre at
    # origin + ((col + 0.5) * res, (height - row - 0.5) * res)
    for row, col in ((0, 0), (nav.height - 1, nav.width - 1), (17, 23)):
        cx = y['origin'][0] + (col + 0.5) * res
        cy = y['origin'][1] + (nav.height - row - 0.5) * res
        assert nav.cell_centre(row, col) == pytest.approx((cx, cy))


# -- the Arena model world ---------------------------------------------------------------

def test_the_arena_world_at_the_game_and_research_resolutions():
    game, research = worldgen.arena_world(KIT, 0.1), worldgen.arena_world(KIT, 0.05)
    assert (game['drive_map'].width * 2, game['drive_map'].height * 2) == \
        (research['drive_map'].width, research['drive_map'].height)
    assert game['resolution'] == 0.1 and research['resolution'] == 0.05
    assert [o['id'] for o in game['objects']] == [o['id'] for o in research['objects']]
    assert len(game['actors']) == 2 and len(game['zones']) == 1 and len(game['catalog']) == 3
    assert game['scan_map'] is not game['drive_map']          # terrain: the LiDAR's own map
    w = json.loads(worldgen.arena_world_json(KIT))
    assert w['schema'] == 'coco_lab.arena_world' and w['drive_map']['geo']['resolution'] == 0.1


def test_the_wedge_mesh_is_a_closed_prism_with_outward_normals():
    data = worldgen.wedge_stl(2.0, 0.65, 2.5)
    tris = worldgen.read_stl(data)
    assert len(tris) == 8 and len(data) == 84 + 50 * 8
    for k, t in enumerate(tris):
        import struct
        n = struct.unpack_from('<3f', data, 84 + 50 * k)
        a, b, c = t
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        assert sum(cross[i] * n[i] for i in range(3)) > 0      # winding agrees with the normal
    # every edge is shared by exactly two triangles: closed
    edges = {}
    for t in tris:
        for i in range(3):
            e = tuple(sorted((t[i], t[(i + 1) % 3])))
            edges[e] = edges.get(e, 0) + 1
    assert set(edges.values()) == {2}


# -- the Nav2 params derivation (tools/m6/gen_level.py) -------------------------------------

def test_nav2_params_change_only_the_level_keys_and_never_the_original(tmp_path):
    sys.path.insert(0, os.path.join(REPO, 'tools', 'm6'))
    import gen_level
    original = _read(GZ, 'config', 'nav2_params.yaml')
    text, changes = gen_level.derive_nav2_params(KIT, 'kit_demo_v3.yaml', 0.1)
    assert _read(GZ, 'config', 'nav2_params.yaml') == original
    derived, base = yaml.safe_load(text), yaml.safe_load(original)
    assert sorted(c['key'] for c in changes) == [
        'amcl.ros__parameters.initial_pose',
        'global_costmap.global_costmap.ros__parameters.resolution',
        'map_server.ros__parameters.yaml_filename']
    for c in changes:
        node, ref = derived, base
        *path, last = c['key'].split('.')
        for k in path:
            node, ref = node[k], ref[k]
        ref[last] = node[last]
    assert derived == base
    assert derived['amcl']['ros__parameters']['initial_pose'] == \
        {'x': 2.0, 'y': 5.0, 'z': 0.0, 'yaw': 0.0}


@pytest.mark.gz
@pytest.mark.skipif(shutil.which('gz') is None, reason='the gz CLI is not installed')
@pytest.mark.parametrize('spec', [KIT, V2], ids=['kit', 'v2'])
def test_gz_sdf_check_passes_on_every_generated_world(spec, tmp_path):
    sdf, files = worldgen.sdf_world(spec, TEMPLATE)
    (tmp_path / 'world.sdf').write_text(sdf)
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    r = subprocess.run(['gz', 'sdf', '-k', str(tmp_path / 'world.sdf')], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0 and 'Valid' in r.stdout, r.stdout + r.stderr
