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

"""L, E, I, c_max and the statistics, against hand-computed values."""

import math

from coco_lab_ros import metrics
from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.pathing import cells_from_poses, path_poses
from coco_lab_ros.planning import CONFIGS
import pytest

R = 0.05


def uniform(cost, w=6, h=4, blocked=()):
    data = bytearray([cost] * (w * h))
    for mx, my in blocked:
        data[my * w + mx] = 254
    return Snapshot(width=w, height=h, resolution=R, origin=(0.0, 0.0),
                    frame_id='map', data=bytes(data))


def c1(s):
    return s.to_labmap().to_grid(**CONFIGS['C1'])


def test_length():
    assert metrics.path_length([(0, 0), (3, 4), (3, 5)]) == 6.0
    assert metrics.path_length([(1, 1)]) == 0.0


def test_edge_sum_by_hand():
    s = uniform(126)                   # 1 + 2 * 126 / 252 = 2
    lab = metrics.lab_cells_of([(0, 0), (1, 0), (2, 1)], s)
    e, why = metrics.edge_sum(lab, c1(s))
    assert why is None
    assert e == pytest.approx(2 * 1 + 2 * math.sqrt(2), rel=1e-12)


def test_edge_sum_is_undefined_not_coerced():
    s = uniform(0, blocked=[(2, 0)])
    g = c1(s)
    jump = metrics.lab_cells_of([(0, 0), (2, 2)], s)
    assert metrics.edge_sum(jump, g)[0] is None
    into = metrics.lab_cells_of([(1, 0), (2, 0)], s)
    e, why = metrics.edge_sum(into, g)
    assert e is None and 'blocked' in why
    assert metrics.edge_sum([], g)[0] is None


def test_integrated_cost_by_hand():
    s = uniform(63)                    # 1 + 2 * 63 / 252 = 1.5
    pts = [(0.025, 0.025), (0.225, 0.025)]
    out = metrics.integrated_cost(pts, s)
    assert out['I'] == pytest.approx(0.2 * 1.5, rel=1e-12)
    assert out['c_max'] == 63 and not out['enters_blocked']
    assert out['samples'] == 80        # 0.2 m / 2.5 mm


def test_integrated_cost_flags_blocked_and_outside():
    s = uniform(0, blocked=[(3, 0)])
    out = metrics.integrated_cost([(0.025, 0.025), (0.275, 0.025)], s)
    assert out['enters_blocked'] and out['c_max'] == 254
    out = metrics.integrated_cost([(0.025, 0.025), (9.0, 0.025)], s)
    assert out['enters_blocked'] and out['c_max'] == 255


def test_tracking_and_distribution():
    poly = [(0.0, 0.0), (1.0, 0.0)]
    assert metrics.distance_to_polyline((0.5, 0.3), poly) == \
        pytest.approx(0.3)
    assert metrics.distance_to_polyline((2.0, 0.0), poly) == \
        pytest.approx(1.0)
    vals = list(range(1, 21))          # 1..20
    st = metrics.tracking_stats(vals)
    assert st['p95'] == 19 and st['max'] == 20 and st['mean'] == 10.5
    d = metrics.distribution([4.0, 1.0, 3.0, 2.0])
    assert (d['min'], d['p25'], d['median'], d['p75'], d['max']) == \
        (1.0, 1.75, 2.5, 3.25, 4.0)
    assert metrics.tracking_stats([])['mean'] is None


def test_path_poses_face_the_next_pose_and_end_on_the_goal_yaw():
    s = uniform(0)
    poses = path_poses([(0, 0), (1, 0), (2, 1)], s, goal_yaw=0.3)
    assert poses[0][:2] == pytest.approx((0.025, 0.025))
    assert poses[0][2] == pytest.approx(0.0)
    assert poses[1][2] == pytest.approx(math.pi / 4)
    assert poses[2][2] == 0.3
    (x, y, yaw), = path_poses([(1, 1)], s, 1.0)
    assert (x, y) == pytest.approx((0.075, 0.075)) and yaw == 1.0


def test_smac_corner_poses_map_back_to_their_cells():
    s = uniform(0)
    cells = [(0, 0), (1, 1), (2, 1), (5, 3)]
    corners = [(mx * R, my * R) for mx, my in cells]
    back, worst = cells_from_poses(corners, s, 'corner')
    assert back == cells and worst < 1e-9
    centres = [s.cell_centre(*c) for c in cells]
    back, worst = cells_from_poses(centres, s, 'centre')
    assert back == cells and worst < 1e-9
    # A centre read as a corner is half a cell off: the residual says so.
    _, worst = cells_from_poses(centres, s, 'corner')
    assert worst == pytest.approx(0.5)
