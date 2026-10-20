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
Independent MODEL costmap layers for Compare; never alters Arena state.

Rows follow the caller's occupancy grid. Inflation uses centre-to-centre
Euclidean distance and Nav2 Jazzy's unsigned-byte truncation:
https://api.nav2.org/nav2-jazzy/html/inflation__layer_8hpp_source.html
This is not Nav2: scan marks are rebuilt each observation, with no temporal
obstacle persistence, unknown-space tracking or footprint polygon.
"""
from dataclasses import dataclass
from typing import Iterable, Sequence

from .columns import Batch
from .numerics import math
from .sketch import edt

LETHAL = 254
INSCRIBED = 253


@dataclass(frozen=True)
class InflationParams:
    inflation_radius: float = 0.5
    cost_scaling_factor: float = 10.0
    robot_radius: float = 0.25

    def __post_init__(self):
        for name in ('inflation_radius', 'cost_scaling_factor', 'robot_radius'):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(name + ' must be finite and nonnegative')
        if self.inflation_radius < self.robot_radius:
            raise ValueError('inflation_radius must cover robot_radius')


def inflation_cost(distance: float, params: InflationParams) -> int:
    """Cost at distance in metres; circular robot radius is inscribed radius."""
    if math.isnan(distance) or distance < 0:
        raise ValueError('distance must be nonnegative')
    if distance == 0:
        return LETHAL
    if distance > params.inflation_radius:
        return 0
    if distance <= params.robot_radius:
        return INSCRIBED
    return int(252 * math.exp(-params.cost_scaling_factor *
                              (distance - params.robot_radius)))


@dataclass(frozen=True)
class CostmapLayers:
    width: int
    height: int
    resolution: float
    static: bytes
    obstacle: bytes
    inflation: bytes
    combined: bytes
    clearance: tuple


def build_layers(width: int, height: int, resolution: float,
                 occupied: Sequence[bool], obstacle_cells: Iterable[int] = (),
                 params: InflationParams = InflationParams()) -> CostmapLayers:
    """
    Build four additive layers from static occupancy and LiDAR hit cells.

    Scan projection stays with the sensor's declared coordinate conversion;
    this function accepts only in-grid hit indices, never fabricated truth.
    Inflation contains the halo only; lethal marks remain in source layers.
    Combined is the maximum of all three layers. Clearance is distance to
    the nearest occupied cell centre, in metres, not footprint clearance.
    """
    if (type(width) is not int or type(height) is not int or
            width <= 0 or height <= 0):
        raise ValueError('positive integer dimensions required')
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError('positive finite resolution required')
    n = width * height
    if len(occupied) != n:
        raise ValueError('occupancy length does not match dimensions')
    static = bytes(LETHAL if cell else 0 for cell in occupied)
    obstacle = bytearray(n)
    for index in obstacle_cells:
        if type(index) is not int or not 0 <= index < n:
            raise ValueError('obstacle cell outside grid')
        obstacle[index] = LETHAL
    marks = [bool(a or b) for a, b in zip(static, obstacle)]
    clearance = tuple(d * resolution for d in edt(marks, width, height))
    inflation = bytes(0 if mark else inflation_cost(distance, params)
                      for mark, distance in zip(marks, clearance))
    combined = bytes(max(a, b, c) for a, b, c in
                     zip(static, obstacle, inflation))
    return CostmapLayers(width, height, resolution, static, bytes(obstacle),
                         inflation, combined, clearance)


def scan_obstacle_cells(lab_map, pose, ranges, angles, mount,
                        range_min: float, range_max: float):
    """
    Project valid LiDAR hits using LabMap's north-first convention.

    Maximum-range returns are no hits. Invalid/outside readings are ignored,
    not clamped into a boundary cell. The belief pose is supplied by caller.
    """
    if len(ranges) != len(angles):
        raise ValueError('scan ranges and angles must have equal length')
    c, s = math.cos(pose[2]), math.sin(pose[2])
    sx = pose[0] + c * mount[0] - s * mount[1]
    sy = pose[1] + s * mount[0] + c * mount[1]
    heading = pose[2] + mount[2]
    cells = set()
    for distance, angle in zip(ranges, angles):
        if not (math.isfinite(distance) and math.isfinite(angle) and
                range_min <= distance < range_max):
            continue
        cell = lab_map.cell_at(sx + distance * math.cos(heading + angle),
                               sy + distance * math.sin(heading + angle))
        if cell is not None:
            cells.add(cell[0] * lab_map.width + cell[1])
    return sorted(cells)


def emit_layers(layers: CostmapLayers, params: InflationParams, origin,
                callback, tick=0, t_world=0.0, update=0, map_id='compare',
                batch_size=2048):
    """Emit the new costmap.layers family in existing columnar transport."""
    if batch_size <= 0:
        raise ValueError('positive batch_size required')
    callback('coco.costmap.layers.header.v1', tick, None, {
        'map_id': map_id, 'width': layers.width, 'height': layers.height,
        'resolution': layers.resolution, 'origin_x': origin[0],
        'origin_y': origin[1], 'row0_is_bottom': False,
        'inflation_radius': params.inflation_radius,
        'cost_scaling_factor': params.cost_scaling_factor,
        'robot_radius': params.robot_radius})
    batch = Batch('coco.costmap.v1.LayersBatch', map_id=map_id, update=update)
    for i, costs in enumerate(zip(layers.static, layers.obstacle,
                                  layers.inflation, layers.combined)):
        batch.add(tick, t_world, row=i // layers.width, col=i % layers.width,
                  static_cost=costs[0], obstacle_cost=costs[1],
                  inflation_cost=costs[2], combined_cost=costs[3])
        if len(batch) >= batch_size:
            columns, scalars = batch.drain()
            callback('coco.costmap.layers.cells.v1', tick, columns, scalars)
    if len(batch):
        columns, scalars = batch.drain()
        callback('coco.costmap.layers.cells.v1', tick, columns, scalars)
