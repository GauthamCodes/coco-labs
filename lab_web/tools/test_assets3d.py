# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
The 3D assets (M4.1): lab_web/public/assets3d/, converted from the Gazebo
SDF world and the URDF by lab_web/tools/assets/. The committed files must be
what the converters make now (the world in every environment; the robot
where ROS's xacro is installed), and their structure must be what the
renderer relies on: glTF 2.0 binaries, the joint hierarchy, the budgets.
"""

import hashlib
import json
import os
import struct
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
ASSETS = os.path.join(REPO, 'lab_web', 'public', 'assets3d')
CONVERTERS = os.path.join(HERE, 'assets')
HAVE_XACRO = os.path.isdir('/opt/ros/jazzy/lib/python3.12/site-packages/xacro')


def glb(path):
    data = open(path, 'rb').read()
    magic, version, total = struct.unpack_from('<4sII', data, 0)
    assert (magic, version, total) == (b'glTF', 2, len(data))
    n, kind = struct.unpack_from('<I4s', data, 12)
    assert kind == b'JSON'
    j = json.loads(data[20:20 + n])
    m, kind2 = struct.unpack_from('<I4s', data, 20 + n)
    assert kind2 == b'BIN\x00' and 28 + n + m == len(data) and j['buffers'][0]['byteLength'] == m
    return j


def triangles(j):
    return sum(j['accessors'][p['indices']]['count'] // 3 for mesh in j['meshes'] for p in mesh['primitives'])


def test_the_world_is_what_the_converter_makes_from_the_recorded_sdf(tmp_path):
    r = subprocess.run([sys.executable, os.path.join(CONVERTERS, 'convert_world.py'), str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for f in ('arena.glb', 'arena.json'):
        assert open(tmp_path / f, 'rb').read() == open(os.path.join(ASSETS, f), 'rb').read(), f


@pytest.mark.skipif(not HAVE_XACRO, reason="the robot is converted where ROS's xacro is installed")
def test_the_robot_is_what_the_converter_makes_from_the_urdf(tmp_path):
    r = subprocess.run([sys.executable, os.path.join(CONVERTERS, 'convert_robot.py'), str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for f in ('robot_high.glb', 'robot_low.glb', 'robot.json'):
        assert open(tmp_path / f, 'rb').read() == open(os.path.join(ASSETS, f), 'rb').read(), f


def test_the_world_is_the_recorded_world_and_the_traverse_bays():
    s = json.load(open(os.path.join(ASSETS, 'arena.json')))
    world = os.path.join(REPO, s['world'])
    # the world file Lab 1C's recorded runs name (docs/data/lab1c/runs/*/meta.json "world")
    meta = json.load(open(os.path.join(REPO, 'docs', 'data', 'lab1c', 'runs', 'astar', 'meta.json')))
    assert hashlib.sha256(open(world, 'rb').read()).hexdigest() == s['world_sha256']
    assert json.dumps(meta).count(s['world_sha256']) >= 1
    kinds = s['kinds']
    assert sum(v for k, v in kinds.items() if k not in ('ramps', 'platforms')) == 70  # every SDF box
    assert (kinds['ramps'], kinds['platforms']) == (8, 4)                         # four bays: up, down, platform
    j = glb(os.path.join(ASSETS, 'arena.glb'))
    assert j['scenes'][0]['nodes'] == [len(j['nodes']) - 1] and j['nodes'][-1]['name'] == 'arena'


def test_the_robot_keeps_its_joints_and_meets_its_triangle_budgets():
    s = json.load(open(os.path.join(ASSETS, 'robot.json')))
    for level, budget in (('high', 20000), ('low', 5000)):
        j = glb(os.path.join(ASSETS, f'robot_{level}.glb'))
        joints = {n['extras']['joint']: n['extras'] for n in j['nodes'] if 'extras' in n and 'joint' in n['extras']}
        wheels = [k for k, v in joints.items() if v['type'] == 'continuous']
        arm = [k for k, v in joints.items() if v['type'] == 'revolute']
        assert len(wheels) == 4 and len(arm) == 4, joints        # 4 wheels; 2 arm joints + 2 fingers
        assert all(len(v['axis']) == 3 for v in joints.values())
        assert triangles(j) == s['levels'][level]['triangles'] <= budget
        names = {n['name'] for n in j['nodes']}
        assert {'link:camera_link', 'link:lidar_link', 'link:grip1', 'link:grip2'} <= names
