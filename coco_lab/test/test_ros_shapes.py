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
The ROS-shaped model without ROS (M6F.7).

The field-by-field check against the real Jazzy messages and the recorded bags
is ``coco_lab_ros/test/test_m6f_ros_shapes.py``; this one runs where ROS is not.
"""

import math
import os

from coco_lab import ros_shapes as rs
from coco_lab.arena import Arena, InputEvent
from coco_lab.maps import LabMap
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
with open(os.path.join(REPO, 'worlds', 'coco_depot_v1.yaml'), encoding='utf-8') as _f:
    DEPOT = yaml.safe_load(_f)


def test_stamps_split_seconds_exactly():
    assert rs.stamp(0.0) == {'sec': 0, 'nanosec': 0}
    assert rs.stamp(12.3) == {'sec': 12, 'nanosec': 300_000_000}
    assert rs.stamp(1.9999999999) == {'sec': 2, 'nanosec': 0}


def test_the_grid_is_row_major_from_the_origin():
    m = LabMap(3, 2, bytes([1, 0, 2,
                            0, 0, 1]), resolution=0.5, origin=(-1.0, 2.0), frame='map')
    g = rs.occupancy_grid(m, 4.0)
    assert g['data'] == [0, 0, 100, 100, 0, -1]          # bottom row first
    assert g['info']['origin']['position'] == {'x': -1.0, 'y': 2.0, 'z': 0.0}
    assert (g['info']['width'], g['info']['height'], g['info']['resolution']) == (3, 2, 0.5)


def test_quaternions_are_unit_and_yaw_only():
    for yaw in (-3.0, -1.2, 0.0, 0.7, math.pi):
        q = rs.quaternion(yaw)
        assert math.isclose(sum(v * v for v in q.values()), 1.0)
        assert (q['x'], q['y']) == (0.0, 0.0)
        assert math.isclose(2 * math.atan2(q['z'], q['w']), math.atan2(math.sin(yaw),
                                                                       math.cos(yaw)))


def test_the_depot_robot_speaks_every_shape():
    a = Arena(DEPOT, seed=1)
    a.step([InputEvent(0, 'goal', x=27.0, y=6.0)])
    for _ in range(15):
        a.step(())
    scan = rs.laser_scan(a)
    assert len(scan['ranges']) == 480 and scan['header']['frame_id'] == 'lidar_link'
    assert scan['header']['stamp'] == rs.stamp(a.t_world)
    od = rs.odometry(a)
    x, y = od['pose']['pose']['position']['x'], od['pose']['pose']['position']['y']
    sx, sy, _ = a.start
    assert (x, y) == pytest.approx((a.pose[0] - sx, a.pose[1] - sy), abs=1e-9)
    assert od['twist']['twist']['linear']['x'] == a.v
    st = rs.tf_static(a)['transforms']
    assert st[0]['transform']['translation']['z'] == DEPOT['robot']['ground_clearance']
    assert [st[1]['transform']['translation'][k] for k in 'xyz'] == \
        DEPOT['robot']['lidar']['mount']
    p = rs.path(a.waypoints, a.t_world)
    assert len(p['poses']) == len(a.waypoints)


def test_the_graph_names_the_readme_topics_and_is_a_tree():
    g = rs.ros_graph()
    names = {t['name'] for t in g['topics']}
    assert {'/scan', '/odom', '/map', '/plan', '/cmd_vel'} <= names
    assert [t['when'] for t in g['topics'] if t['name'] in ('/map', '/tf_static')] == \
        ['latched', 'latched']
    children = [c for _, c in g['tf_tree']]
    assert len(children) == len(set(children)) and g['tf_tree'][0][0] == 'map'
    assert g['evidence'] == 'MODEL' and 'invariant 2' in g['note']


def test_the_committed_graph_is_current():
    import json
    with open(os.path.join(REPO, 'docs', 'v2', 'm6', 'data', 'ros_graph.json'),
              encoding='utf-8') as f:
        assert json.load(f) == rs.ros_graph()
