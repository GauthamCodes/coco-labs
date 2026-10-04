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
Lab 2's robot_localization configuration: what it fuses, and what it leaves alone.

- it fuses the wheels' vx, vy and the gyro's yaw rate -- never the wheels'
  yaw rate (skid-steer's weak axis, measured) and never the IMU's
  orientation (Gazebo's is ground truth with zero covariance, measured);
- it never publishes TF, so the odometry transform AMCL and Nav2 use stays
  the diff_drive_controller's;
- nothing the mission runs loads it: no file under gazebo_models,
  coco_mission or custom_teleop names robot_localization or the config.
"""

import os

from coco_lab_ros import params

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(PKG)
CONFIG = os.path.join(PKG, 'config', 'ekf_odom_imu.yaml')
LAUNCH = os.path.join(PKG, 'launch', 'lab_ekf.launch.py')

# robot_localization's 15-element order: x y z, roll pitch yaw, vx vy vz,
# vroll vpitch vyaw, ax ay az
NAMES = ('x', 'y', 'z', 'roll', 'pitch', 'yaw', 'vx', 'vy', 'vz', 'vroll',
         'vpitch', 'vyaw', 'ax', 'ay', 'az')


def cfg():
    return params.load(CONFIG)['ekf_filter_node']['ros__parameters']


def fused(key):
    return {n for n, on in zip(NAMES, cfg()[key]) if on}


def test_it_fuses_wheel_speed_and_gyro_rate_only():
    assert fused('odom0_config') == {'vx', 'vy'}
    assert fused('imu0_config') == {'vyaw'}
    c = cfg()
    assert c['odom0'] == '/diff_drive_controller/odom'
    assert c['imu0'] == '/imu'
    assert c['two_d_mode'] is True
    assert c['world_frame'] == c['odom_frame'] == 'odom'
    assert c['base_link_frame'] == 'base_footprint'


def test_it_never_publishes_tf():
    assert cfg()['publish_tf'] is False
    with open(LAUNCH, encoding='utf-8') as f:
        text = f.read()
    assert "'ekf_odom_imu.yaml'" in text
    assert 'publish_tf' not in text.split('"""')[-1]  # no override in code


def test_nothing_the_mission_runs_loads_it():
    hits = []
    for pkg in ('gazebo_models', 'coco_mission', 'custom_teleop', 'coco_web'):
        for root, dirs, files in os.walk(os.path.join(REPO, pkg)):
            dirs[:] = [d for d in dirs if d not in ('test', '__pycache__')]
            for name in files:
                if not name.endswith(('.py', '.yaml', '.xml', '.xacro')):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='replace') as f:
                    text = f.read()
                if 'robot_localization' in text or 'ekf_odom_imu' in text:
                    hits.append(os.path.relpath(path, REPO))
    assert hits == []
