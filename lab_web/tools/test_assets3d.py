# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
The 3D assets (M4.2; ADR 0006): lab_web/public/assets3d/, made by
lab_web/tools/assets/build_assets.mjs from the recorded Gazebo world and the
robot's URDF. Standard library only, like the converters (CI has no numpy and
no ROS). That every committed file is what the pipeline makes now, byte for
byte, is checked by lab_web/test/assets3d.test.ts (it needs meshoptimizer).
"""

import hashlib
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
ASSETS = os.path.join(REPO, 'lab_web', 'public', 'assets3d')
URDF = os.path.join(HERE, 'assets', 'coco_robo2.urdf')
XACRO = os.path.join(REPO, 'gazebo_models', 'urdf', 'coco_robo2.xacro')
MANIFEST = json.load(open(os.path.join(ASSETS, 'manifest.json')))


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def glb(path):
    data = open(path, 'rb').read()
    magic, version, total = struct.unpack_from('<4sII', data, 0)
    assert (magic, version, total) == (b'glTF', 2, len(data))
    n, kind = struct.unpack_from('<I4s', data, 12)
    assert kind == b'JSON'
    return json.loads(data[20:20 + n])


def test_the_committed_urdf_is_the_xacros_expansion():
    # the URDF is expanded where ROS is installed (convert_robot.py --from-xacro) and
    # records the xacro's sha256: a changed xacro fails here until it is re-expanded
    first = open(URDF).readline()
    assert f'sha256 {sha(XACRO)}' in first, 'run: python3 lab_web/tools/assets/convert_robot.py --from-xacro'
    assert '/home/' not in open(URDF).read()


def test_every_asset_is_licensed_sourced_and_its_sources_are_the_repositorys_files():
    for a in MANIFEST['assets']:
        assert a['licence'] and a['sources'], a['file']
        assert sha(os.path.join(ASSETS, a['file'])) == a['sha256'], a['file']
        assert os.path.getsize(os.path.join(ASSETS, a['file'])) == a['bytes']
        for s in a['sources']:
            assert sha(os.path.join(REPO, s['path'])) == s['sha256'], (a['file'], s['path'])


def test_the_first_scene_and_the_robot_are_within_their_budgets():
    # README §5.4: the first scene 5 MB or less compressed, of which the robot 1.5 MB or less
    b = MANIFEST['budget']
    assert b == {'first_scene_bytes': 5_000_000, 'robot_bytes': 1_500_000}
    by = {a['file']: a['bytes'] for a in MANIFEST['assets']}
    assert by['robot_high.glb'] <= b['robot_bytes'] and by['robot_low.glb'] <= b['robot_bytes']
    assert by['arena.glb'] + by['robot_high.glb'] == MANIFEST['first_scene']['desktop_bytes'] <= b['first_scene_bytes']
    assert by['arena.glb'] + by['robot_low.glb'] == MANIFEST['first_scene']['phone_bytes'] <= b['first_scene_bytes']


def test_every_asset_is_meshopt_compressed_and_the_robot_keeps_its_joints():
    for a in MANIFEST['assets']:
        j = glb(os.path.join(ASSETS, a['file']))
        assert j['extensionsRequired'] == ['EXT_meshopt_compression']
        assert all('EXT_meshopt_compression' in v.get('extensions', {}) for v in j['bufferViews'])
        if a['kind'] == 'robot':
            joints = {n['extras']['joint']: n['extras'] for n in j['nodes'] if 'joint' in n.get('extras', {})}
            moving = sorted(v['type'] for v in joints.values() if v['type'] != 'fixed')
            assert moving == ['continuous'] * 4 + ['revolute'] * 4  # 4 wheels; 2 arm joints + 2 fingers
            names = {n['name'] for n in j['nodes']}
            assert {'link:camera_link', 'link:lidar_link', 'link:grip1', 'link:grip2'} <= names


def test_the_levels_of_detail_meet_their_triangle_budgets():
    # README §5.4: about 20k triangles near the camera, well under 5k for phones
    lv = MANIFEST['levels']
    assert lv['high']['triangles'] <= 20000 and lv['low']['triangles'] < 5000
    assert all(m['tris'] <= m['source_tris'] for v in lv.values() for m in v['meshes'])


def test_the_world_is_the_recorded_world_and_the_traverse_bays():
    s = json.load(open(os.path.join(ASSETS, 'arena.json')))
    meta = json.load(open(os.path.join(REPO, 'docs', 'data', 'lab1c', 'runs', 'astar', 'meta.json')))
    assert sha(os.path.join(REPO, s['world'])) == s['world_sha256']
    assert s['world_sha256'] in json.dumps(meta)  # the world Lab 1C's recorded runs name
    kinds = s['kinds']
    assert sum(v for k, v in kinds.items() if k not in ('ramps', 'platforms')) == 70
    assert (kinds['ramps'], kinds['platforms']) == (8, 4)
