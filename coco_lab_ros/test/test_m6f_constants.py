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
Grasp Assist's copies of COCO's numbers equal their sources (M6F.5).

``coco_lab.grasp_assist`` may not import coco_config (no ROS; Pyodide), so it
copies the camera's field of view and position, and relies on ``coco_lab.grasp``'s
copies of the window and the targets (pinned by test_sketch_constants.py's
sibling checks and here). This test, on the ROS side, pins each to its source.
"""

from coco_config import robot
from coco_lab import arm, grasp
from coco_lab import grasp_assist as ga
import pytest


def test_the_camera_is_coco_configs():
    assert ga.CAMERA_HFOV == robot.CAMERA_HFOV
    assert ga.CAMERA_X == robot.CAMERA_XYZ[0]


def test_the_window_and_the_lateral_limit_are_the_stacks_gate():
    near, far = robot.approach_window('red')
    assert grasp.WINDOW == pytest.approx((near, far), abs=1e-12)
    assert all(robot.approach_window(t.colour) == (near, far) for t in robot.TARGETS)
    assert grasp.MAX_LATERAL == robot.GRASP_MAX_LATERAL


def test_the_fingers_and_the_band_come_from_the_targets():
    assert sorted(grasp.TARGET_DIAMETER.values()) == sorted(t.diameter for t in robot.TARGETS)
    assert ga.FINGER_MAX == max(t.diameter for t in robot.TARGETS)
    assert grasp.TARGET_HEIGHT == robot.TARGET_HEIGHT
    assert arm.TARGET_XZ[1] == robot.TARGET_GRASP_Z
    assert ga.BAND_BELOW_TOP == pytest.approx(robot.TARGET_HEIGHT - robot.TARGET_GRASP_Z)
    assert arm.HOVER_CLEARANCE == robot.GRASP_HOVER_CLEARANCE


def test_the_depot_graspables_weigh_what_the_stacks_targets_weigh():
    import os
    import yaml
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, '..', '..', 'worlds', 'coco_depot_v1.yaml'),
              encoding='utf-8') as f:
        depot = yaml.safe_load(f)
    graspable = [c for c in depot['catalog'] if c['id'] in
                 ('can_small', 'bottle_steel', 'canister', 'can_large')]
    assert len(graspable) == 4
    assert all(c['mass'] == robot.TARGET_MASS for c in graspable)
