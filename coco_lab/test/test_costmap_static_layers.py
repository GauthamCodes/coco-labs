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
G1.13: costmap.StaticLayers gives build_layers' four layers byte for byte.

Play's Robot vision re-drew the model's costmap every 4 s with build_layers over the whole
Depot grid (161,700 cells), stalling the model ~0.9 s each time in the browser (measured on the
laptop, docs/v2/g1/data/g113/README.md). StaticLayers keeps the static map's share and updates
only the boxes around new marks; it must never differ from build_layers.
"""
import json
from pathlib import Path

from coco_lab.costmap import (build_layers, emit_cells, InflationParams,
                              scan_obstacle_cells, StaticLayers)
from hypothesis import given, settings, strategies as st
import pytest

REPO = Path(__file__).resolve().parents[2]


def same(occupied, w, h, res, cells, params):
    want = build_layers(w, h, res, occupied, cells, params)
    got = StaticLayers(w, h, res, occupied, params).layers(cells)
    assert got == (want.static, want.obstacle, want.inflation, want.combined)


@settings(max_examples=150, deadline=None)
@given(st.integers(3, 24), st.integers(3, 24), st.sampled_from([0.05, 0.1, 0.25]),
       st.data(), st.floats(0.0, 0.6), st.floats(0.0, 1.0), st.floats(0.0, 20.0))
def test_equal_to_build_layers_on_random_grids(w, h, res, data, robot, extra, scaling):
    occupied = data.draw(st.lists(st.booleans(), min_size=w * h, max_size=w * h))
    cells = data.draw(st.lists(st.integers(0, w * h - 1), max_size=12))
    params = InflationParams(robot_radius=robot, inflation_radius=robot + extra,
                             cost_scaling_factor=scaling)
    same(occupied, w, h, res, cells, params)


def test_equal_on_an_empty_map_and_with_repeated_cells():
    params = InflationParams()
    same([False] * 400, 20, 20, 0.1, [7, 7, 210, 399, 0], params)
    same([False] * 400, 20, 20, 0.1, [], params)


def test_equal_on_the_depot_with_coco_s_own_scan():
    from coco_lab.arena import Arena, InputEvent
    from coco_lab import games, loc_arena  # noqa: F401 -- loc_arena: the subsystem
    spec = json.loads((REPO / 'worlds' / 'coco_depot_v1.json').read_text())
    a = Arena(spec, 1, hash_version=3)
    a.step([InputEvent(**e) for e in games.setup_inputs('fetch_rush', 1, 3, mode='phone')])
    m, li = a.lab_map, a.lidar
    params = InflationParams(robot_radius=a.radius, inflation_radius=max(0.5, a.radius))
    hits = scan_obstacle_cells(m, a.belief(), a.ranges, a.angles, li.mount,
                               li.range_min, li.range_max)
    occupied = [v != 0 for v in m.occupancy]
    assert hits and any(not occupied[i] for i in hits), 'the scan adds marks the static map lacks'
    same(occupied, m.width, m.height, m.resolution, hits, params)


def test_rejects_what_build_layers_rejects():
    with pytest.raises(ValueError):
        StaticLayers(0, 3, 0.1, [])
    with pytest.raises(ValueError):
        StaticLayers(2, 2, 0.1, [False] * 3)
    with pytest.raises(ValueError):
        StaticLayers(2, 2, 0.1, [False] * 4).layers([4])


def test_emit_cells_sends_the_listed_cells_in_emit_layers_columns():
    layers = StaticLayers(4, 3, 0.1, [False] * 12).layers([5])
    got = []
    emit_cells(4, [5, 6], layers, InflationParams(), (0.0, 0.0), lambda *a: got.append(a),
               height=3, resolution=0.1)
    assert got[0][0] == 'coco.costmap.layers.header.v1'
    cols = got[1][2]
    assert list(cols['row']) == [1, 1] and list(cols['col']) == [1, 2]
    assert list(cols['combined_cost']) == [layers[3][5], layers[3][6]]


@settings(max_examples=80, deadline=None)
@given(st.integers(3, 20), st.integers(3, 20), st.data())
def test_cells_outside_touched_equal_the_static_layers(w, h, data):
    occupied = data.draw(st.lists(st.booleans(), min_size=w * h, max_size=w * h))
    cells = data.draw(st.lists(st.integers(0, w * h - 1), max_size=10))
    sl = StaticLayers(w, h, 0.1, occupied, InflationParams())
    got = sl.layers(cells)
    empty = bytes(w * h)
    for i in range(w * h):
        if i not in sl.touched:
            assert (got[1][i], got[2][i], got[3][i]) == (empty[i], sl.inflation[i], sl.combined[i])


def test_batch_add_many_equals_repeated_add():
    from coco_lab.columns import Batch
    a = Batch('coco.costmap.v1.LayersBatch', map_id='m', update=3)
    b = Batch('coco.costmap.v1.LayersBatch', map_id='m', update=3)
    names = ('row', 'col', 'static_cost', 'obstacle_cost', 'inflation_cost', 'combined_cost')
    values = [(0, 1, 0, 0, 12, 12), (2, 3, 254, 0, 0, 254), (4, 4, 0, 254, 0, 254)]
    rows = [dict(zip(names, row)) for row in values]
    for r in rows:
        a.add(7, 0.7, **r)
    b.add_many(7, 0.7, **{k: [r[k] for r in rows] for k in rows[0]})
    ca, sa = a.drain()
    cb, sb = b.drain()
    assert sa == sb and {k: list(v) for k, v in ca.items()} == {k: list(v) for k, v in cb.items()}
    assert {k: type(v) for k, v in ca.items()} == {k: type(v) for k, v in cb.items()}


def test_emit_cells_equals_emit_layers_on_every_cell():
    from coco_lab.costmap import build_layers, emit_layers
    occupied = [i % 7 == 0 for i in range(9 * 5)]
    params = InflationParams()
    full = build_layers(9, 5, 0.1, occupied, [3, 20], params)
    got_a, got_b = [], []
    emit_layers(full, params, (0.0, 0.0), lambda *x: got_a.append(x),
                tick=4, t_world=0.4, update=4, batch_size=7)
    layers = (full.static, full.obstacle, full.inflation, full.combined)
    emit_cells(9, range(45), layers, params, (0.0, 0.0), lambda *x: got_b.append(x),
               height=5, resolution=0.1, tick=4, t_world=0.4, update=4, batch_size=7)

    def norm(got):
        return [(c, t, {k: list(v) for k, v in cols.items()} if cols else None, sc)
                for c, t, cols, sc in got]
    assert norm(got_a) == norm(got_b)
