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

"""Lab 3's teaching worlds say what their descriptions say."""

import math

from coco_lab import map_teaching as mt
from coco_lab import mapworld
from coco_lab import posegraph as pg
from coco_lab.maps import FREE, OCCUPIED
from coco_lab.sketch import COCO_LIDAR, SketchMap
import pytest


@pytest.fixture(scope='module')
def maps():
    return mt.teaching_maps()


def test_every_scene_drives_its_route_to_the_end(maps):
    for sid in mt.scenarios():
        m, sc = mt.scene_scenario(sid, maps)
        w = mapworld.from_sketch(m, sc)
        assert w.status == 'route_done', sid
        end = w.gt[-1]
        last = sc.route[-1]
        assert math.hypot(end[0] - last[0], end[1] - last[1]) < 0.2, sid


def test_the_loop_rooms_drive_is_a_loop(maps):
    m, sc = mt.scene_scenario('map_loop', maps)
    w = mapworld.from_sketch(m, sc)
    # it passes its start again after going round the block
    near = [i for i, p in enumerate(w.gt)
            if math.hypot(p[0] - sc.start[0], p[1] - sc.start[1]) < 0.5]
    assert near[0] == 0 and near[-1] > len(w.gt) // 2


def test_the_corridor_is_two_straight_featureless_walls(maps):
    m = maps['map_corridor']
    y0, y1 = mt.CORRIDOR_Y
    x0, x1 = mt.CORRIDOR_X
    for col in range(m.width):
        x = m.origin[0] + (col + 0.5) * m.resolution
        if not x0 + 0.2 < x < x1 - 0.2:
            continue
        column = []
        for row in range(m.height):
            y = m.origin[1] + (m.height - 1 - row + 0.5) * m.resolution
            column.append((y, m.occupancy[row * m.width + col]))
        free = [y for y, v in column if v == FREE]
        # every column of the corridor is the same: free exactly in y0..y1
        assert min(free) > y0 - 0.1 and max(free) < y1 + 0.1
        assert all(v == OCCUPIED for y, v in column
                   if y < y0 - 0.1 or y > y1 + 0.1)


def test_a_scan_mid_corridor_cannot_see_how_far_along_it_is(maps):
    """The ICP Hessian is blind along the axis there, sharp in a room."""
    smap = SketchMap(maps['map_corridor'])
    lidar = COCO_LIDAR.decimated(8)
    ang = lidar.angles()

    def min_eig(pose):
        z = smap.scan(pose, lidar, ang)
        pts = pg.scan_points(z, ang, lidar.mount, lidar.range_min,
                             lidar.range_max)
        r = pg.icp(pts, pts, (0.0, 0.0, 0.0))
        return r.min_eig_per_point()

    assert min_eig((15.0, 3.0, 0.0)) < 0.01
    assert min_eig((3.0, 3.0, 0.5)) > 0.05


def test_run_specs_tell_the_slams_the_true_noise():
    for rid, alg, p in mt.run_specs(scale=2.0):
        if alg in ('ekf_slam', 'fastslam'):
            assert tuple(p.alphas) == (0.04,) * 4
    ids = [r for r, _, _ in mt.run_specs()]
    assert ids == list(mt.RUN_IDS)
    noloop = {r: p for r, _, p in mt.run_specs()}['pose_graph_noloop']
    assert noloop.loop_closure is False


def test_a_click_behind_a_wall_is_driven_around_it(maps):
    smap = SketchMap(maps['map_loop'])
    # from the south corridor to the north one: the block is in between
    route = mt.plan_route(smap, (2.0, 2.0), [(10.0, 8.0)])
    assert route[-1] == (10.0, 8.0) and len(route) >= 2
    for (x0, y0), (x1, y1) in zip([(2.0, 2.0)] + route, route):
        for i in range(21):
            f = i / 20
            assert not smap.is_blocked(x0 + f * (x1 - x0), y0 + f * (y1 - y0))


def test_an_unreachable_click_is_refused(maps):
    smap = SketchMap(maps['map_loop'])
    with pytest.raises(ValueError, match='cannot be reached'):
        mt.plan_route(smap, (2.0, 2.0), [(8.0, 5.0)])  # inside the block
    with pytest.raises(ValueError, match='waypoints'):
        mt.plan_route(smap, (2.0, 2.0), [(3.0, 2.0)] * (mt.MAX_CLICKS + 1))


def test_the_arena_scenario_is_fixed_but_its_route_is_the_learners():
    a = mt.arena_scenario()
    b = mt.arena_scenario([(1.0, 1.0)])
    assert a.start == b.start == mt.ARENA_START
    assert a.seed == b.seed == mt.ARENA_SEED
    assert a.noise == b.noise and b.route == [(1.0, 1.0)]
