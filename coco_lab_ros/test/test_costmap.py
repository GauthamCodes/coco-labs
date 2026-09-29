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

"""The costmap_raw adapter: row flip, value mapping, world/cell, identity."""

from types import SimpleNamespace

from coco_lab.maps import FREE, OCCUPIED, UNKNOWN
from coco_lab_ros.costmap import (f32, NO_INFORMATION, occupancy_of,
                                  raw_from_labmap, recover_resolution,
                                  Snapshot, snapshot_from_labmap)
import pytest

# 3 x 2, deliberately asymmetric. Nav2 order: row my=0 is the BOTTOM.
BOTTOM = [0, 1, 2]
TOP = [252, 253, 255]


def tiny(**kw):
    args = {'width': 3, 'height': 2, 'resolution': 0.05,
            'origin': (-1.0, 2.0), 'frame_id': 'map',
            'data': bytes(BOTTOM + TOP)}
    args.update(kw)
    return Snapshot(**args)


def test_the_rows_are_flipped():
    m = tiny().to_labmap()
    # LabMap row 0 is the TOP row, i.e. Nav2's my = 1.
    assert [m.at((0, c)) for c in range(3)] == [FREE, OCCUPIED, UNKNOWN]
    assert [m.at((1, c)) for c in range(3)] == [FREE, FREE, FREE]
    assert list(m.cost[:3]) == [252.0, 253.0, 255.0]
    assert list(m.cost[3:]) == [0.0, 1.0, 2.0]


def test_every_raw_value_maps_as_declared():
    for v in range(256):
        want = FREE if v <= 252 else UNKNOWN if v == 255 else OCCUPIED
        assert occupancy_of(v) == want, v


def test_the_two_frames_put_every_centre_at_the_same_point():
    s = tiny()
    m = s.to_labmap()
    for mx in range(3):
        for my in range(2):
            row, col = s.to_lab(mx, my)
            assert s.from_lab(row, col) == (mx, my)
            assert m.cell_centre(row, col) == pytest.approx(
                s.cell_centre(mx, my), abs=1e-12)
            assert m.cell_at(*s.cell_centre(mx, my)) == (row, col)


def test_the_labmap_is_lossless():
    s = tiny()
    m = s.to_labmap()
    assert raw_from_labmap(m) == s.data
    assert snapshot_from_labmap(m).content_hash() == s.content_hash()


def test_the_hash_ignores_the_stamp_and_sees_one_byte():
    a = tiny(stamp=(1, 2), layer='master', source_topic='/x')
    b = tiny(stamp=(9, 9))
    assert a.content_hash() == b.content_hash()
    c = tiny(data=bytes(BOTTOM + [252, 253, 254]))
    assert a.content_hash() != c.content_hash()
    assert a.content_hash() != tiny(origin=(-1.0, 2.05)).content_hash()


def test_world_to_cell_matches_nav2_at_the_edges():
    s = tiny()
    assert s.world_to_cell(-1.0, 2.0) == (0, 0)          # the origin itself
    assert s.world_to_cell(-1.0 - 1e-9, 2.0) is None     # left of it
    assert s.world_to_cell(-1.0, 2.0 - 1e-9) is None     # below it
    assert s.world_to_cell(-1.0 + 0.149999, 2.0) == (2, 0)
    assert s.world_to_cell(-1.0 + 0.15, 2.0) is None     # the far edge
    assert s.world_to_cell(-1.0 + 0.05, 2.0 + 0.05) == (1, 1)


def test_the_float32_step_is_nav2s_not_pythons():
    # (wx - ox) / r lands a hair under 3 in float64 and rounds UP to 3.0 in
    # float32; Nav2's cast then says cell 3 where a float64 floor says 2.
    s = tiny(width=10, height=1, data=bytes(10), origin=(0.0, 0.0))
    wx = 0.15 - 1e-10
    assert wx / 0.05 < 3.0
    assert f32(wx / 0.05) == 3.0
    assert s.world_to_cell(wx, 0.0) == (3, 0)


def test_resolution_is_recovered_from_its_float32():
    for r in (0.05, 0.1, 0.025, 0.2):
        assert recover_resolution(f32(r)) == r
    assert f32(0.05) != 0.05


def test_from_msg_reads_a_nav2_costmap():
    msg = SimpleNamespace(
        header=SimpleNamespace(frame_id='map',
                               stamp=SimpleNamespace(sec=7, nanosec=5)),
        metadata=SimpleNamespace(
            size_x=3, size_y=2, resolution=f32(0.05), layer='master',
            origin=SimpleNamespace(position=SimpleNamespace(x=-1.0, y=2.0))),
        data=BOTTOM + TOP)
    s = Snapshot.from_msg(msg, '/global_costmap/costmap_raw')
    assert s.resolution == 0.05 and s.resolution_f32 == f32(0.05)
    assert s.content_hash() == tiny().content_hash()
    assert s.stamp == (7, 5) and s.layer == 'master'
    assert s.describe()['source_topic'] == '/global_costmap/costmap_raw'


def test_outside_counts_as_no_information():
    assert tiny().raw_cost_at_world(100.0, 100.0) == NO_INFORMATION


def test_bad_snapshots_are_refused():
    with pytest.raises(ValueError):
        tiny(data=bytes(5))
    with pytest.raises(ValueError):
        tiny(resolution=0.0)
