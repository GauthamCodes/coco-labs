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

"""Hand-computed Nav2 formula and independent layer contracts (MODEL)."""
import math

from coco_lab.costmap import (build_layers, emit_layers, inflation_cost,
                              InflationParams, scan_obstacle_cells)
from coco_lab.maps import LabMap
import pytest


def test_hand_computed_bands_and_truncation():
    p = InflationParams(1.0, math.log(2) / 0.25, 0.25)
    assert inflation_cost(0, p) == 254
    assert inflation_cost(0.125, p) == 253
    assert inflation_cost(0.25, p) == 253
    # Every extra 0.25 m halves 252; unsigned-byte conversion truncates.
    assert inflation_cost(0.5, p) == 126
    assert inflation_cost(0.75, p) == 63
    assert inflation_cost(1.0, p) == 31
    assert inflation_cost(1.000001, p) == 0
    assert inflation_cost(math.inf, p) == 0


def test_layers_union_and_exact_diagonal_distance():
    occupied = [False] * 9
    occupied[0] = True
    layers = build_layers(3, 3, 0.25, occupied, [8, 8],
                          InflationParams(1, 1, 0.25))
    assert layers.static[0] == layers.obstacle[8] == 254
    assert layers.static[8] == layers.obstacle[0] == 0
    assert layers.inflation[0] == layers.inflation[8] == 0
    assert layers.combined[1] == 253
    assert layers.clearance[4] == pytest.approx(math.sqrt(2) * 0.25)
    assert layers.combined[4] == 227  # floor(252 exp(-0.10355339...))
    assert layers.combined == bytes(max(a, b, c) for a, b, c in
                                    zip(layers.static, layers.obstacle,
                                        layers.inflation))
    assert occupied == [True] + [False] * 8  # caller data untouched


def test_empty_and_new_scan_clear_previous_marks():
    first = build_layers(3, 1, 0.25, [False] * 3, [1])
    second = build_layers(3, 1, 0.25, [False] * 3)
    assert first.combined == bytes([253, 254, 253])
    assert second.combined == bytes(3)
    assert all(math.isinf(d) for d in second.clearance)


@pytest.mark.parametrize('kwargs', [
    {'inflation_radius': -1}, {'cost_scaling_factor': math.nan},
    {'robot_radius': math.inf}, {'inflation_radius': 0.1},
])
def test_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        InflationParams(**kwargs)


@pytest.mark.parametrize('args', [
    (0, 1, 1, []), (True, 1, 1, [False]), (1, 1, 0, [False]),
    (1, 1, math.nan, [False]), (1, 1, 1, []),
    (1, 1, 1, [False], [-1]), (1, 1, 1, [False], [1]),
])
def test_invalid_grid(args):
    with pytest.raises(ValueError):
        build_layers(*args)


def test_scan_projection_uses_mount_and_north_first_rows():
    m = LabMap(4, 4, [0] * 16, resolution=1, origin=(0, 0))
    # Facing north, sensor mounted 0.5 m ahead. East is a -pi/2 beam.
    cells = scan_obstacle_cells(m, (1.5, 1, math.pi / 2),
                                [1, 1, 3, math.nan, -1, 5],
                                [0, -math.pi / 2, 0, 0, 0, 0],
                                (0.5, 0, 0), 0.1, 3)
    assert cells == [5, 10]
    with pytest.raises(ValueError):
        scan_obstacle_cells(m, (1, 1, 0), [1], [], (0, 0, 0), 0, 3)


def test_emitted_batches_preserve_cells_clocks_and_sequence():
    rows = []
    p = InflationParams()
    layers = build_layers(3, 2, 0.25, [True] + [False] * 5)
    emit_layers(layers, p, (-1, -2), lambda *args: rows.append(args),
                tick=7, t_world=0.7, update=2, batch_size=4)
    assert rows[0][2] is None
    assert rows[0][3]['row0_is_bottom'] is False
    batches = rows[1:]
    assert [len(item[2]['seq']) for item in batches] == [4, 2]
    assert [v for _, _, c, _ in batches for v in c['seq']] == list(range(6))
    assert [v for _, _, c, _ in batches for v in c['combined_cost']] == list(layers.combined)
    for channel, tick, columns, scalars in batches:
        assert channel == 'coco.costmap.layers.cells.v1'
        assert tick == 7 and list(columns['tick']) == [7] * len(columns['seq'])
        assert scalars == {'map_id': 'compare', 'update': 2}
