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
The ROS-shaped model against the real ROS 2 message definitions (M6F.7).

Every shape ``coco_lab.ros_shapes`` makes fills the real Jazzy message class
field for field (``rosidl_runtime_py.set_message_fields`` refuses unknown
fields) and reads back with exactly the same structure. The comparison with
recorded Stack bags (``tools/m6/compare_ros_shapes.py``) is recomputed and must
equal its committed evidence, ``docs/v2/m6/data/ros_shapes_vs_stack.json``.
"""

import copy
import importlib.util
import json
import math
import os

from coco_lab import ros_shapes as rs
from coco_lab.arena import Arena, InputEvent
import pytest
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.set_message import set_message_fields
from rosidl_runtime_py.utilities import get_message
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as _f:
    V1 = yaml.safe_load(_f)
EVIDENCE = os.path.join(REPO, 'docs', 'v2', 'm6', 'data', 'ros_shapes_vs_stack.json')


@pytest.fixture(scope='module')
def arena():
    a = Arena(V1, seed=1)
    a.step([InputEvent(0, 'goal', x=6.0, y=-4.0)])
    for _ in range(20):
        a.step(())
    return a


def _same(ours, theirs, path='$'):
    if isinstance(ours, dict):
        assert isinstance(theirs, dict) and list(ours) == list(theirs), path
        for k in ours:
            _same(ours[k], theirs[k], f'{path}.{k}')
    elif isinstance(ours, list):
        assert len(ours) == len(theirs), path
        for i, (x, y) in enumerate(zip(ours, theirs)):
            _same(x, y, f'{path}[{i}]')
    elif isinstance(ours, float):
        assert theirs == pytest.approx(ours, rel=1e-6, abs=1e-6), path   # float32 fields
    else:
        assert ours == theirs, path


def _plain(v):
    # every field of the real message, in its definition's order, recursively
    if hasattr(v, 'get_fields_and_field_types'):
        return {f: _plain(getattr(v, f)) for f in v.get_fields_and_field_types()}
    if isinstance(v, (list, tuple)) or type(v).__name__ in ('array', 'ndarray'):
        return [_plain(x) for x in v]
    return v


def _fill(type_name, shape):
    msg = get_message(type_name)()
    set_message_fields(msg, copy.deepcopy(shape))     # it replaces nested dicts in place
    assert list(message_to_ordereddict(msg)) == list(shape)
    _same(json.loads(json.dumps(shape)), _plain(msg))
    return msg


def test_laser_scan(arena):
    m = _fill('sensor_msgs/msg/LaserScan', rs.laser_scan(arena))
    assert len(m.ranges) == 480 and m.header.frame_id == 'lidar_link'


def test_occupancy_grid(arena):
    m = _fill('nav_msgs/msg/OccupancyGrid', rs.occupancy_grid(arena.lab_map, 1.5))
    assert (m.info.width, m.info.height) == (arena.lab_map.width, arena.lab_map.height)
    assert set(m.data) <= {0, 100, -1}
    # ROS row 0 is the bottom: the first cell is the LabMap's bottom-left
    w = arena.lab_map.width
    bottom_left = arena.lab_map.occupancy[(arena.lab_map.height - 1) * w]
    assert m.data[0] == {0: 0, 1: 100, 2: -1}[bottom_left]


def test_twists(arena):
    _fill('geometry_msgs/msg/Twist', rs.twist(arena.v, arena.w))
    m = _fill('geometry_msgs/msg/TwistStamped', rs.twist_stamped(0.3, -0.5, 2.25))
    assert (m.header.stamp.sec, m.header.stamp.nanosec) == (2, 250_000_000)
    assert (m.twist.linear.y, m.twist.linear.z) == (0.0, 0.0)     # COCO never strafes


def test_path(arena):
    m = _fill('nav_msgs/msg/Path', rs.path(arena.waypoints or [(0.0, 0.0), (1.0, 1.0)], 2.0))
    assert m.header.frame_id == 'map' and all(p.header.frame_id == 'map' for p in m.poses)


def test_odometry(arena):
    m = _fill('nav_msgs/msg/Odometry', rs.odometry(arena))
    assert (m.header.frame_id, m.child_frame_id) == ('odom', 'base_footprint')
    assert len(m.pose.covariance) == 36


def test_tf_tree(arena):
    dyn = _fill('tf2_msgs/msg/TFMessage', rs.tf(arena))
    st = _fill('tf2_msgs/msg/TFMessage', rs.tf_static(arena))
    edges = [[t.header.frame_id, t.child_frame_id] for t in dyn.transforms + st.transforms]
    assert edges == rs.ros_graph()['tf_tree']
    # map -> odom -> base_footprint lands on the robot's pose
    mo, ob = dyn.transforms
    yaw = 2 * math.atan2(mo.transform.rotation.z, mo.transform.rotation.w)
    ox, oy = ob.transform.translation.x, ob.transform.translation.y
    x = mo.transform.translation.x + math.cos(yaw) * ox - math.sin(yaw) * oy
    y = mo.transform.translation.y + math.sin(yaw) * ox + math.cos(yaw) * oy
    assert (x, y) == pytest.approx(arena.pose[:2], abs=1e-9)


def test_every_graph_topic_is_a_real_message_type():
    g = rs.ros_graph()
    for t in g['topics']:
        assert get_message(t['type']) is not None, t['name']
        assert t['publisher'] in g['nodes'] and set(t['subscribers']) <= set(g['nodes'])
    assert {t['name'] for t in g['topics']} >= {'/scan', '/odom', '/map', '/plan', '/cmd_vel'}
    assert next(t for t in g['topics'] if t['name'] == '/scan')['rate_hz'] == 10.0


def test_the_stack_comparison_reproduces_its_committed_evidence():
    spec = importlib.util.spec_from_file_location(
        'compare_ros_shapes', os.path.join(REPO, 'tools', 'm6', 'compare_ros_shapes.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    got = json.loads(json.dumps(mod.compare()))
    with open(EVIDENCE, encoding='utf-8') as f:
        assert got == json.load(f)
    sh = got['shapes']
    assert sh['tf_static']['model'] == sh['tf_static']['stack']
    assert sh['odometry_frames']['model'] == sh['odometry_frames']['stack']
    assert sh['cmd_vel_frame']['model'] == sh['cmd_vel_frame']['stack'] == ''
    assert sh['plan_frame']['model'] == sh['plan_frame']['stack'] == 'map'
    scan = sh['scan']
    for k in ('frame_id', 'ranges', 'scan_time', 'time_increment', 'range_max'):
        assert scan['model'][k] == scan['stack'][k], k
    for k in ('angle_min', 'angle_max', 'angle_increment', 'range_min'):
        assert scan['model'][k] == pytest.approx(scan['stack'][k], abs=1e-6)   # float32
    # the one shape difference, reported: the model computes no intensities
    assert (scan['model']['intensities'], scan['stack']['intensities']) == (0, 480)
