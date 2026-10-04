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
Lab 2's kidnap A/B overlays change exactly what they say, and nothing else.

Arm A (``nav2_loc_shipped.yaml``) merges to the mission's own parameters;
arm B (``nav2_loc_recovery.yaml``) differs from them in exactly AMCL's two
``recovery_alpha_*`` keys, set to Nav2's suggested 0.1 / 0.001. The
mission file itself is never touched (``test_params.py`` pins its hash).
"""

import os

from coco_lab_ros import params

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(PKG)
MISSION = os.path.join(REPO, 'gazebo_models', 'config', 'nav2_params.yaml')
SHIPPED = os.path.join(PKG, 'config', 'nav2_loc_shipped.yaml')
RECOVERY = os.path.join(PKG, 'config', 'nav2_loc_recovery.yaml')


def _merged(overlay):
    return params.deep_merge(params.load(MISSION), params.load(overlay))


def test_the_mission_ships_injection_off():
    amcl = params.load(MISSION)['amcl']['ros__parameters']
    assert amcl['recovery_alpha_fast'] == 0.0
    assert amcl['recovery_alpha_slow'] == 0.0


def test_arm_a_merges_to_the_mission_exactly():
    assert params.differing_keys(params.load(MISSION),
                                 _merged(SHIPPED)) == []


def test_arm_b_changes_only_the_two_recovery_alphas():
    merged = _merged(RECOVERY)
    assert params.differing_keys(params.load(MISSION), merged) == [
        'amcl.ros__parameters.recovery_alpha_fast',
        'amcl.ros__parameters.recovery_alpha_slow',
    ]
    amcl = merged['amcl']['ros__parameters']
    assert amcl['recovery_alpha_fast'] == 0.1
    assert amcl['recovery_alpha_slow'] == 0.001


def test_merge_files_writes_the_same_parameters(tmp_path):
    out = tmp_path / 'merged.yaml'
    params.merge_files(MISSION, RECOVERY, str(out))
    assert params.load(str(out)) == _merged(RECOVERY)
