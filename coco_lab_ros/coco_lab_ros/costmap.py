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
One ``nav2_msgs/Costmap`` at one instant, and the adapter into coco_lab.

**Why ``costmap_raw`` (owner decision D-2).** ``/global_costmap/costmap``
is a ``nav_msgs/OccupancyGrid`` whose values Nav2 translates
(``costmap_2d_publisher.cpp`` @1.3.11): 0 -> 0, 1..252 -> 1..98, 253 ->
99, 254 -> 100, 255 -> -1. 252 raw values fold onto 98, so Smac's costs
cannot be recovered from it. ``/global_costmap/costmap_raw`` carries the
uint8 master costs themselves, and a snapshot is taken from that.

**Frames.** Nav2 indexes ``data[my * size_x + mx]`` with ``my = 0`` the
BOTTOM row (the origin is the bottom-left corner). A
:class:`coco_lab.maps.LabMap` puts row 0 at the TOP. So Nav2 cell
``(mx, my)`` is lab cell ``(row, col) = (size_y - 1 - my, mx)``, and the
two place every cell centre at the same metric point (tested).

**The value mapping** (Smac 2D's ``inCollision``, ``collision_checker.cpp``
@1.3.11 :172-183, with ``allow_unknown: false``):

- 0 .. 252 -> FREE, and the cost layer holds the raw value exactly;
- 253 (INSCRIBED) and 254 (LETHAL) -> OCCUPIED;
- 255 (NO_INFORMATION) -> UNKNOWN, which ``to_grid(unknown='blocked')``
  blocks.

The cost layer keeps the raw value for EVERY cell, blocked ones
included, so the snapshot's bytes are recoverable from the LabMap
(:func:`raw_from_labmap`), losslessly.

**World to cell** is Nav2's own (``Costmap2D::worldToMapContinuous`` then
the truncating cast in ``AStarAlgorithm<Node2D>::setStart``/``setGoal``):
``mx = float32((wx - origin_x) / resolution)``, cell ``int(mx)``. The
float32 step is emulated exactly, because a point a hair inside a cell
edge can round across it in float32.

**Resolution.** ``CostmapMetaData.resolution`` is float32; Nav2 converts
with its own double ``resolution_``. :func:`recover_resolution` returns
the shortest decimal that round-trips the float32 (0.05 for 0.05's
float32, 0.0500000007...), which is the configured double whenever the
configuration was written with at most seven significant digits.
"""

from dataclasses import dataclass, field
import hashlib
import math
import struct
from typing import Dict, Optional, Tuple

from coco_lab.maps import FREE, LabMap, OCCUPIED, UNKNOWN

#: Nav2's cost values (nav2_costmap_2d/cost_values.hpp).
FREE_SPACE = 0
MAX_NON_OBSTACLE = 252
INSCRIBED = 253
LETHAL = 254
NO_INFORMATION = 255

SNAPSHOT_SCHEMA = 'coco_lab_ros.costmap/1'


def f32(x: float) -> float:
    """Round a Python float to the nearest float32, as C++ does."""
    return struct.unpack('<f', struct.pack('<f', x))[0]


def recover_resolution(res_f32: float) -> float:
    """Return the shortest decimal that rounds to ``res_f32`` in float32."""
    for digits in range(1, 10):
        candidate = float(f'{res_f32:.{digits}g}')
        if f32(candidate) == f32(res_f32):
            return candidate
    return float(res_f32)


def occupancy_of(raw: int) -> int:
    """Map one raw Nav2 cost onto a LabMap occupancy value."""
    if raw <= MAX_NON_OBSTACLE:
        return FREE
    if raw == NO_INFORMATION:
        return UNKNOWN
    return OCCUPIED


@dataclass(frozen=True)
class Snapshot:
    """
    One costmap at one instant, in Nav2's own storage order.

    ``data`` is ``width * height`` raw uint8 costs, ``data[my * width +
    mx]``, ``my = 0`` the bottom row. ``resolution`` is the recovered
    double; ``resolution_f32`` the value the message carried.
    """

    width: int
    height: int
    resolution: float
    origin: Tuple[float, float]
    frame_id: str
    data: bytes
    resolution_f32: float = 0.0
    stamp: Tuple[int, int] = (0, 0)
    layer: str = ''
    source_topic: str = ''
    meta: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        """Check dimensions and the data length."""
        if not (self.width > 0 and self.height > 0):
            raise ValueError(f'bad size {self.width} x {self.height}')
        if len(self.data) != self.width * self.height:
            raise ValueError(f'data has {len(self.data)} bytes, expected '
                             f'{self.width * self.height}')
        if not (math.isfinite(self.resolution) and self.resolution > 0):
            raise ValueError(f'bad resolution {self.resolution!r}')

    # -- construction --------------------------------------------------------

    @classmethod
    def from_msg(cls, msg, source_topic: str = '') -> 'Snapshot':
        """Build a snapshot from a ``nav2_msgs/Costmap`` (duck-typed)."""
        md = msg.metadata
        res32 = float(md.resolution)
        return cls(
            width=int(md.size_x), height=int(md.size_y),
            resolution=recover_resolution(res32),
            origin=(float(md.origin.position.x),
                    float(md.origin.position.y)),
            frame_id=str(msg.header.frame_id),
            data=bytes(bytearray(msg.data)),
            resolution_f32=res32,
            stamp=(int(msg.header.stamp.sec), int(msg.header.stamp.nanosec)),
            layer=str(md.layer),
            source_topic=source_topic)

    # -- identity ---------------------------------------------------------------

    def content_hash(self) -> str:
        """
        Return ``'sha256:<hex>'`` over what the costmap IS.

        Hashed, in order: the line ``coco_lab_ros.costmap/1 <width>
        <height> <resolution> <origin_x> <origin_y> <frame_id>`` (``repr``
        of each float) and a newline, then the raw data. The stamp, layer
        and topic are NOT hashed: two messages with one hash are the same
        costmap published twice, which is exactly what a "did the costmap
        change" check needs.
        """
        h = hashlib.sha256()
        h.update(f'{SNAPSHOT_SCHEMA} {self.width} {self.height} '
                 f'{self.resolution!r} {self.origin[0]!r} '
                 f'{self.origin[1]!r} {self.frame_id}\n'.encode('utf-8'))
        h.update(self.data)
        return 'sha256:' + h.hexdigest()

    def describe(self) -> Dict[str, object]:
        """Return the snapshot's metadata, for provenance records."""
        return {
            'schema': SNAPSHOT_SCHEMA,
            'content_hash': self.content_hash(),
            'width': self.width, 'height': self.height,
            'resolution': self.resolution,
            'resolution_f32': self.resolution_f32,
            'origin': list(self.origin), 'frame_id': self.frame_id,
            'stamp': list(self.stamp), 'layer': self.layer,
            'source_topic': self.source_topic,
        }

    # -- cells ----------------------------------------------------------------

    def cost(self, mx: int, my: int) -> int:
        """Return the raw cost of Nav2 cell ``(mx, my)``."""
        if not (0 <= mx < self.width and 0 <= my < self.height):
            raise IndexError(f'({mx}, {my}) outside {self.width} x '
                             f'{self.height}')
        return self.data[my * self.width + mx]

    def world_to_map_continuous(self, wx: float, wy: float
                                ) -> Optional[Tuple[float, float]]:
        """
        Nav2's ``worldToMapContinuous``: float32 map coordinates, or None.

        ``None`` exactly where Nav2 returns false: left of or below the
        origin, or at/after the far edge.
        """
        ox, oy = self.origin
        if wx < ox or wy < oy:
            return None
        mx = f32((wx - ox) / self.resolution)
        my = f32((wy - oy) / self.resolution)
        if mx < self.width and my < self.height:
            return mx, my
        return None

    def world_to_cell(self, wx: float, wy: float
                      ) -> Optional[Tuple[int, int]]:
        """Return the Nav2 cell ``(mx, my)`` Smac 2D plans from, or None."""
        m = self.world_to_map_continuous(wx, wy)
        if m is None:
            return None
        return int(m[0]), int(m[1])

    def cell_centre(self, mx: int, my: int) -> Tuple[float, float]:
        """Return the world (frame) centre of Nav2 cell ``(mx, my)``."""
        r = self.resolution
        return (self.origin[0] + (mx + 0.5) * r,
                self.origin[1] + (my + 0.5) * r)

    def to_lab(self, mx: int, my: int) -> Tuple[int, int]:
        """Return the LabMap ``(row, col)`` of Nav2 cell ``(mx, my)``."""
        return (self.height - 1 - my, mx)

    def from_lab(self, row: int, col: int) -> Tuple[int, int]:
        """Return the Nav2 ``(mx, my)`` of LabMap cell ``(row, col)``."""
        return (col, self.height - 1 - row)

    def raw_cost_at_world(self, wx: float, wy: float) -> int:
        """
        Return the raw cost of the cell containing ``(wx, wy)``.

        Outside the map counts as ``NO_INFORMATION`` (255).
        """
        c = self.world_to_cell(wx, wy)
        return NO_INFORMATION if c is None else self.cost(*c)

    # -- the adapter -----------------------------------------------------------

    def to_labmap(self, map_id: str = '') -> LabMap:
        """
        Return this snapshot as a :class:`coco_lab.maps.LabMap`.

        Rows are flipped (Nav2 bottom-up to LabMap top-down); occupancy
        follows :func:`occupancy_of`; the cost layer is the raw value of
        every cell. Placement (resolution, origin, frame) is preserved.
        """
        w, h = self.width, self.height
        table = bytes(occupancy_of(v) for v in range(256))
        occ = bytearray(w * h)
        cost = [0.0] * (w * h)
        for my in range(h):
            src = self.data[my * w:(my + 1) * w]
            row = h - 1 - my
            occ[row * w:(row + 1) * w] = src.translate(table)
            cost[row * w:(row + 1) * w] = [float(v) for v in src]
        return LabMap(w, h, bytes(occ), cost, map_id=map_id,
                      resolution=self.resolution, origin=self.origin,
                      frame=self.frame_id or None,
                      meta={'source': 'nav2_msgs/Costmap',
                            'snapshot_hash': self.content_hash(),
                            'source_topic': self.source_topic,
                            'stamp': list(self.stamp)})


def raw_from_labmap(m: LabMap) -> bytes:
    """Invert :meth:`Snapshot.to_labmap`: Nav2-ordered raw bytes."""
    if m.cost is None:
        raise ValueError('the map has no cost layer')
    w, h = m.width, m.height
    out = bytearray(w * h)
    for row in range(h):
        my = h - 1 - row
        out[my * w:(my + 1) * w] = bytes(
            int(v) for v in m.cost[row * w:(row + 1) * w])
    return bytes(out)


def snapshot_from_labmap(m: LabMap) -> Snapshot:
    """Rebuild the snapshot a LabMap was made from (hash-identical)."""
    return Snapshot(width=m.width, height=m.height,
                    resolution=m.resolution, origin=m.origin,
                    frame_id=m.frame or '', data=raw_from_labmap(m))
