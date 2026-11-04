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

"""R2.1: the algorithm API's types and context (coco_lab.api; ADR 0013)."""

import json
from pathlib import Path

from coco_lab import api
from coco_lab.exp_user import psd_problem
from coco_lab.numerics import math
from coco_lab.rng import Rng
import pytest

WORLDS = Path(__file__).resolve().parents[2] / 'worlds'


def test_message_shapes_match_ros():
    # the fields of the Jazzy messages, in order (the ROS node fills them one to one)
    assert api.LaserScan.__slots__ == ('header', 'angle_min', 'angle_max', 'angle_increment',
                                       'time_increment', 'scan_time', 'range_min', 'range_max',
                                       'ranges', 'intensities')
    assert api.OccupancyGrid.__slots__ == ('header', 'info', 'data')
    assert api.MapMetaData.__slots__ == ('map_load_time', 'resolution', 'width', 'height',
                                         'origin')
    assert api.Costmap.__slots__ == ('header', 'metadata', 'data')
    assert api.CostmapMetaData.__slots__ == ('map_load_time', 'update_time', 'layer',
                                             'resolution', 'size_x', 'size_y', 'origin')
    assert api.Odometry.__slots__ == ('header', 'child_frame_id', 'pose', 'twist')
    assert api.Twist.__slots__ == ('linear', 'angular')
    assert api.Pose2D.__slots__ == ('x', 'y', 'theta')
    assert api.PoseWithCovariance.__slots__ == ('pose', 'covariance')


def test_yaw_round_trip_is_exact():
    for i in range(-400, 401):
        yaw = i * 0.0078125 + 1e-9 * i
        assert api.yaw_of(api.quaternion_from_yaw(yaw)) == yaw
    q = api.quaternion_from_yaw(0.7)
    q.z = 0.0
    assert api.yaw_of(q) == 0.0          # changed since: computed, not remembered
    assert abs(api.yaw_of(api.Quaternion(0, 0, math.sin(0.35), math.cos(0.35))) - 0.7) < 1e-12
    assert api.Pose.from_2d(1, 2, 0.3).to_2d() == api.Pose2D(1, 2, 0.3)


def test_grid_helpers_are_ros_ordered():
    md = api.CostmapMetaData(resolution=0.5, size_x=4, size_y=3,
                             origin=api.Pose.from_2d(-1.0, 2.0))
    cm = api.Costmap(metadata=md, data=tuple(range(12)))
    assert cm.world_to_map(-1.0, 2.0) == (0, 0)
    assert cm.world_to_map(0.9, 3.4) == (3, 2)
    assert cm.world_to_map(1.0, 2.0) is None and cm.world_to_map(-1.01, 2.0) is None
    assert cm.map_to_world(3, 2) == (0.75, 3.25)
    assert cm.cost(3, 2) == 11 and cm.cost(4, 0) == api.NO_INFORMATION
    assert cm.cost_at(0.9, 3.4) == 11 and cm.is_free(0, 0)
    assert (cm.width, cm.height, cm.resolution) == (4, 3, 0.5)


def test_robot_is_cocos():
    spec = json.loads((WORLDS / 'coco_depot_v1.json').read_text())
    r = api.Robot.from_spec(spec['robot'])
    assert (r.radius, r.max_linear, r.max_angular, r.max_linear_accel, r.max_angular_accel) == \
        (0.22, 0.3, 1.0, 2.0, 4.0)
    assert r.lidar_mount == (-0.09, 0.1)


def test_context_emit_and_budget():
    seen = []
    c = api.Context(Rng(1), api.Robot(), budget=3, sink=seen.append)
    c.emit('expand', x=1.0, y=2.0)
    assert seen == [('expand', {'x': 1.0, 'y': 2.0})]
    with pytest.raises(ValueError):
        c.emit('teleport', x=1)
    with pytest.raises(ValueError):
        c.emit('expand', x=1.0)
    c.step(3)
    with pytest.raises(api.BudgetExceeded):
        c.step()
    kept = api.Context(Rng(1), api.Robot())
    for _ in range(api.Context.MAX_EVENTS + 5):
        kept.emit('note', text='.')
    assert len(kept.events) == api.Context.MAX_EVENTS and kept.dropped == 5


def test_random_matches_rng():
    a, b = api.Random(Rng(5)), Rng(5)
    assert [a.random(), a.uniform(1, 2), a.gauss(0, 1)] == \
        [b.random(), b.uniform(1, 2), b.gauss(0, 1)]
    items = list(range(10))
    api.Random(Rng(3)).shuffle(items)
    assert sorted(items) == list(range(10)) and items != list(range(10))
    assert len(set(api.Random(Rng(3)).sample(range(100), 10))) == 10


def test_psd_check():
    good = api.PoseWithCovariance.of(0, 0, 0, 0.1, 0.2, 0.05, 0.05).covariance
    assert psd_problem(good) is None
    assert psd_problem([0.0] * 36) is None
    bad = list(good)
    bad[1] = 0.5                              # not symmetric
    assert 'symmetric' in psd_problem(bad)
    bad[6] = 0.5                              # symmetric, |cov_xy| > sqrt(var_x var_y)
    assert psd_problem(bad) is not None
    neg = list(good)
    neg[0] = -0.1
    assert 'negative' in psd_problem(neg)
