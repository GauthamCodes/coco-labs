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
Sketch's copies of COCO's numbers equal their sources (CLAUDE.md rule 3).

coco_lab may not import coco_config or read package data (no ROS, and it
must run in Pyodide), so ``coco_lab.sketch`` COPIES a few values. This
test, in the ROS-side package, pins every copy to where it comes from:

- ``COCO_LIDAR``: the ``lidar`` sensor and ``lidar_joint`` in
  ``gazebo_models/urdf/coco_robo2.xacro`` (and ``base_footprint_joint``
  offsets only in z, so the mount is the same in ``base_footprint``);
- ``UPDATE_MIN_D`` / ``UPDATE_MIN_A``: AMCL's in the mission's
  ``nav2_params.yaml``;
- ``ROBOT_RADIUS``: at least half the diagonal of COCO's footprint,
  derived from coco_config as Lab 1.1 derives it, by under 1 cm.
"""

import math
import os
import re
import xml.etree.ElementTree as ET

from coco_config import robot
from coco_lab import sketch
from coco_lab_ros import params

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
XACRO = os.path.join(REPO, 'gazebo_models', 'urdf', 'coco_robo2.xacro')
NAV2 = os.path.join(REPO, 'gazebo_models', 'config', 'nav2_params.yaml')


def _xml():
    with open(XACRO, encoding='utf-8') as f:
        text = f.read()
    # xacro's namespace is declared; ElementTree reads plain tags fine
    return ET.fromstring(text)


def _joint(root, name):
    for j in root.iter('joint'):
        if j.get('name') == name:
            o = j.find('origin')
            return ([float(v) for v in o.get('xyz').split()],
                    [float(v) for v in o.get('rpy').split()],
                    j.find('parent').get('link'), j.find('child').get('link'))
    raise AssertionError(f'no joint {name}')


def test_the_lidar_is_cocos():
    root = _xml()
    sensors = [s for s in root.iter('sensor') if s.get('name') == 'lidar']
    assert len(sensors) == 1
    s = sensors[0]
    h = s.find('lidar/scan/horizontal')
    r = s.find('lidar/range')
    lid = sketch.COCO_LIDAR
    assert int(h.find('samples').text) == lid.samples
    assert float(h.find('min_angle').text) == lid.angle_min
    assert float(h.find('max_angle').text) == lid.angle_max
    assert float(r.find('min').text) == lid.range_min
    assert float(r.find('max').text) == lid.range_max
    assert s.find('lidar/noise') is None  # Gazebo adds no range noise


def test_the_lidar_mount_is_cocos():
    root = _xml()
    xyz, rpy, parent, child = _joint(root, 'lidar_joint')
    assert (parent, child) == ('base_link', 'lidar_link')
    bxyz, brpy, bparent, bchild = _joint(root, 'base_footprint_joint')
    assert (bparent, bchild) == ('base_footprint', 'base_link')
    assert bxyz[:2] == [0.0, 0.0] and brpy == [0.0, 0.0, 0.0]
    assert tuple(xyz[:2]) == sketch.COCO_LIDAR.mount[:2]
    assert rpy[2] == sketch.COCO_LIDAR.mount[2]
    assert tuple(xyz) == robot.LIDAR_MOUNT_XYZ


def test_the_update_thresholds_are_amcls():
    amcl = params.load(NAV2)['amcl']['ros__parameters']
    assert amcl['update_min_d'] == sketch.UPDATE_MIN_D
    assert amcl['update_min_a'] == sketch.UPDATE_MIN_A


def test_the_collision_radius_covers_the_footprint():
    length = max(robot.CHASSIS_SIZE[0], robot.WHEELBASE + 2 * robot.WHEEL_RADIUS)
    width = max(robot.CHASSIS_SIZE[1], robot.WHEEL_SEPARATION + robot.WHEEL_WIDTH)
    half_diag = math.hypot(length, width) / 2
    assert half_diag <= sketch.ROBOT_RADIUS < half_diag + 0.01


def test_the_default_scan_is_cocos_decimated():
    assert re.search(r'decimated\(8\)', open(sketch.__file__).read())
    assert sketch.Scenario((0, 0, 0), [(1, 0)]).lidar == \
        sketch.COCO_LIDAR.decimated(8)
