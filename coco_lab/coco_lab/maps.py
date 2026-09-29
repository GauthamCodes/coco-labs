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
Map schema v1: the canonical, versioned map every lab run searches.

The normative description is ``docs/labs/MAP_FORMAT.md``; this module is
its reference implementation and the tests pin one to the other.

A :class:`LabMap` is *data*: dimensions, one occupancy value per cell, an
optional cost layer, and optional placement in a metric frame. It is not a
graph. How a robot may move over it -- 4 or 8 neighbours, the diagonal
cost, the corner rule, how the cost layer weighs, whether unknown cells
are passable -- is a **run input**, given to :meth:`LabMap.to_grid`, so the
same map can be searched under several move models and a comparison can
hold the map fixed while changing only the model.

**Coordinates.** A cell is ``(row, col)``, row 0 is the TOP row, storage is
row-major. This is the image convention of a PGM file and of Nav2's
map_server, and the convention :class:`coco_lab.grid.Grid` already uses.
With placement (``resolution`` metres per cell and ``origin``, the frame
coordinates of the map's bottom-left corner, yaw 0) the centre of cell
``(row, col)`` is::

    x = origin_x + (col + 0.5) * resolution
    y = origin_y + (height - 1 - row + 0.5) * resolution

so ``y`` grows upward while ``row`` grows downward.

**Identity.** :meth:`LabMap.content_hash` is a SHA-256 over everything that
changes what the map *is*: dimensions, occupancy, the cost layer and the
placement. It excludes ``id`` and ``meta``, which only name and describe.
Two maps with one hash are interchangeable for every search and every
drawing; a bundle records the hash, so a replay can prove it is showing the
map that was actually searched.

This is a teaching grid. It is not a ROS ``OccupancyGrid`` and not a Nav2
costmap; :func:`from_nav2` is the one declared conversion, and it converts
a *saved map* (pgm + yaml), not a costmap.
"""

import hashlib
import json
import math
import os
import struct
from typing import Dict, Optional, Sequence, Tuple

from .grid import DEFAULT_COST_SCALE, DEFAULT_COST_WEIGHT, Grid
from .heuristics import SQRT2

SCHEMA = 'coco_lab.map'
VERSION = '1.0'
MAJOR = 1

#: Occupancy values, and the character each has in the JSON ``rows``.
FREE, OCCUPIED, UNKNOWN = 0, 1, 2
CELL_CHARS = '.#?'

#: What :meth:`LabMap.to_grid` may do with an unknown cell.
UNKNOWN_POLICIES = ('blocked', 'free')

#: Rasterisation rules; see :class:`Raster`.
RULES = ('centre', 'overlap')

#: Resource bounds. A map is untrusted input when it arrives in a bundle
#: or a file; these keep a hostile one from exhausting memory.
MAX_SIDE = 16384
MAX_CELLS = 16_000_000


class MapError(ValueError):
    """A map that does not conform to the schema."""


def _check_dims(width, height) -> None:
    for name, v in (('width', width), ('height', height)):
        if not (isinstance(v, int) and not isinstance(v, bool)
                and 0 < v <= MAX_SIDE):
            raise MapError(f'{name} must be an int in 1..{MAX_SIDE}, '
                           f'got {v!r}')
    if width * height > MAX_CELLS:
        raise MapError(f'{width} x {height} exceeds {MAX_CELLS} cells')


def _finite(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


class LabMap:
    """
    An immutable occupancy map with an optional cost layer and placement.

    ``occupancy`` is ``width * height`` values in ``{0, 1, 2}`` (free,
    occupied, unknown), row-major from the top-left. ``cost`` is ``None``
    or ``width * height`` finite values ``>= 0``. ``resolution`` (metres
    per cell, ``> 0``) and ``origin`` (``(x, y)`` of the bottom-left
    corner) come together or not at all; ``frame`` names their frame.
    """

    def __init__(self, width: int, height: int,
                 occupancy: Sequence[int],
                 cost: Optional[Sequence[float]] = None,
                 map_id: str = '',
                 resolution: Optional[float] = None,
                 origin: Optional[Tuple[float, float]] = None,
                 frame: Optional[str] = None,
                 meta: Optional[Dict[str, object]] = None):
        """Validate and freeze the map; it is immutable afterwards."""
        _check_dims(width, height)
        n = width * height
        try:
            occ = occupancy if isinstance(occupancy, bytes) \
                else bytes(occupancy)
        except (TypeError, ValueError):
            raise MapError('occupancy must be a sequence of 0, 1 or 2') \
                from None
        if len(occ) != n:
            raise MapError(f'occupancy has {len(occ)} cells, expected {n}')
        if occ.translate(None, b'\x00\x01\x02'):
            raise MapError('occupancy values must be 0, 1 or 2')
        self.width = width
        self.height = height
        self._occ = occ
        if cost is not None:
            if len(cost) != n:
                raise MapError(f'cost has {len(cost)} cells, expected {n}')
            for i, c in enumerate(cost):
                if not (_finite(c) and c >= 0):
                    raise MapError(
                        f'cost[{i}] must be finite and >= 0, got {c!r}')
            self._cost = tuple(float(c) for c in cost)
        else:
            self._cost = None
        if (resolution is None) != (origin is None):
            raise MapError('resolution and origin come together or not '
                           'at all')
        if resolution is not None:
            if not (_finite(resolution) and resolution > 0):
                raise MapError(f'resolution must be finite and > 0, '
                               f'got {resolution!r}')
            try:
                ox, oy = origin
            except (TypeError, ValueError):
                raise MapError(f'origin must be (x, y), got {origin!r}') \
                    from None
            if not (_finite(ox) and _finite(oy)):
                raise MapError(f'origin must be finite, got {origin!r}')
            self.resolution = float(resolution)
            self.origin = (float(ox), float(oy))
        else:
            self.resolution = None
            self.origin = None
        if frame is not None and not isinstance(frame, str):
            raise MapError(f'frame must be a string, got {frame!r}')
        if frame is not None and resolution is None:
            raise MapError('a frame needs a resolution and origin')
        self.frame = frame
        if not isinstance(map_id, str):
            raise MapError(f'id must be a string, got {map_id!r}')
        self.id = map_id
        self.meta = dict(meta or {})

    # -- queries -----------------------------------------------------------

    @property
    def occupancy(self) -> bytes:
        """Return the occupancy values, row-major, as bytes."""
        return self._occ

    @property
    def cost(self) -> Optional[Tuple[float, ...]]:
        """Return the cost layer, row-major, or ``None``."""
        return self._cost

    @property
    def has_geo(self) -> bool:
        """Return whether the map is placed in a metric frame."""
        return self.resolution is not None

    def in_bounds(self, cell: Tuple[int, int]) -> bool:
        """Return whether ``(row, col)`` is inside the map."""
        r, c = cell
        return 0 <= r < self.height and 0 <= c < self.width

    def at(self, cell: Tuple[int, int]) -> int:
        """Return the occupancy value of ``(row, col)``."""
        if not self.in_bounds(cell):
            raise MapError(f'{cell!r} is outside {self.width} x '
                           f'{self.height}')
        return self._occ[cell[0] * self.width + cell[1]]

    def count(self, value: int) -> int:
        """Return how many cells hold ``value``."""
        return self._occ.count(value)

    def cell_centre(self, row: int, col: int) -> Tuple[float, float]:
        """Return the frame coordinates of the centre of ``(row, col)``."""
        self._need_geo()
        r = self.resolution
        return (self.origin[0] + (col + 0.5) * r,
                self.origin[1] + (self.height - 1 - row + 0.5) * r)

    def cell_at(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """Return the ``(row, col)`` containing ``(x, y)``, or ``None``."""
        self._need_geo()
        col = math.floor((x - self.origin[0]) / self.resolution)
        up = math.floor((y - self.origin[1]) / self.resolution)
        row = self.height - 1 - up
        return (row, col) if self.in_bounds((row, col)) else None

    def _need_geo(self):
        if not self.has_geo:
            raise MapError(f'map {self.id!r} has no resolution/origin')

    # -- identity ----------------------------------------------------------

    def content_hash(self) -> str:
        r"""
        Return ``'sha256:<hex>'`` over the map's defining content.

        The hashed bytes are, in order: the ASCII line
        ``coco_lab.map/1 <width> <height>\\n``; the occupancy bytes; the
        line ``cost\\n`` and the cost layer as little-endian float64, or
        the line ``nocost\\n``; the line ``geo <resolution> <ox> <oy>
        <frame>\\n`` using ``repr`` of each float, or ``nogeo\\n``. ``id``
        and ``meta`` are not hashed.
        """
        h = hashlib.sha256()
        h.update(f'coco_lab.map/{MAJOR} {self.width} {self.height}\n'
                 .encode('ascii'))
        h.update(self._occ)
        if self._cost is None:
            h.update(b'nocost\n')
        else:
            h.update(b'cost\n')
            h.update(struct.pack(f'<{len(self._cost)}d', *self._cost))
        if self.has_geo:
            h.update(f'geo {self.resolution!r} {self.origin[0]!r} '
                     f'{self.origin[1]!r} {self.frame or ""}\n'
                     .encode('utf-8'))
        else:
            h.update(b'nogeo\n')
        return 'sha256:' + h.hexdigest()

    def __eq__(self, other) -> bool:
        """Compare by content, id and meta included."""
        return (isinstance(other, LabMap)
                and self.content_hash() == other.content_hash()
                and self.id == other.id and self.meta == other.meta)

    # -- the move model is a run input ---------------------------------

    def to_grid(self, connectivity: int = 8, diagonal_cost: float = SQRT2,
                corner_cutting: bool = False,
                cost_weight: float = DEFAULT_COST_WEIGHT,
                cost_scale: float = DEFAULT_COST_SCALE,
                unknown: str = 'blocked') -> Grid:
        """
        Return a searchable :class:`Grid` under the given move model.

        ``unknown`` decides unknown cells: ``'blocked'`` (the default, as
        Nav2 does with ``allow_unknown: false``) or ``'free'``.
        """
        if unknown not in UNKNOWN_POLICIES:
            raise MapError(f'unknown must be one of {UNKNOWN_POLICIES}, '
                           f'got {unknown!r}')
        blocked_values = (OCCUPIED, UNKNOWN) if unknown == 'blocked' \
            else (OCCUPIED,)
        blocked = [v in blocked_values for v in self._occ]
        return Grid(self.width, self.height, blocked, self._cost,
                    connectivity=connectivity, diagonal_cost=diagonal_cost,
                    corner_cutting=corner_cutting, cost_weight=cost_weight,
                    cost_scale=cost_scale)

    # -- transformations ---------------------------------------------------

    def downsample(self, factor: int, map_id: Optional[str] = None
                   ) -> 'LabMap':
        """
        Return the map at ``factor`` times coarser resolution.

        Each ``factor x factor`` block becomes one cell: occupied if any
        cell in it is occupied, else unknown if any is unknown, else free
        -- conservative, so a free coarse cell is free at full resolution.
        The cost is the block's maximum. A partial block at the right or
        bottom edge is kept. Placement is preserved: the bottom-left corner
        stays put, and the top edge moves up to a whole coarse cell.
        """
        if not (isinstance(factor, int) and factor >= 1):
            raise MapError(f'factor must be an int >= 1, got {factor!r}')
        w = -(-self.width // factor)
        h = -(-self.height // factor)
        # Blocks are anchored at the BOTTOM-left, so that the origin (the
        # bottom-left corner) is unchanged; row 0 of the coarse map may be
        # a partial block.
        pad = h * factor - self.height
        occ = bytearray(w * h)
        cost = [0.0] * (w * h) if self._cost is not None else None
        for row in range(self.height):
            cr = (row + pad) // factor
            for col in range(self.width):
                i = row * self.width + col
                j = cr * w + col // factor
                v = self._occ[i]
                if v == OCCUPIED or (v == UNKNOWN and occ[j] == FREE):
                    occ[j] = v
                if cost is not None and self._cost[i] > cost[j]:
                    cost[j] = self._cost[i]
        return LabMap(w, h, bytes(occ), cost,
                      map_id=map_id if map_id is not None
                      else f'{self.id}@x{factor}',
                      resolution=None if not self.has_geo
                      else self.resolution * factor,
                      origin=self.origin, frame=self.frame,
                      meta=dict(self.meta, downsampled_from=self.id,
                                downsample_factor=factor,
                                downsample_rule='any_occupied'))

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, object]:
        """Return the JSON-ready form described in MAP_FORMAT.md."""
        rows = [self._occ[r * self.width:(r + 1) * self.width]
                .translate(_TO_CHARS).decode('ascii')
                for r in range(self.height)]
        return {
            'schema': SCHEMA,
            'version': VERSION,
            'id': self.id,
            'width': self.width,
            'height': self.height,
            'rows': rows,
            'cost': None if self._cost is None else list(self._cost),
            'geo': None if not self.has_geo else {
                'resolution': self.resolution,
                'origin': list(self.origin),
                'frame': self.frame,
            },
            'meta': dict(self.meta),
            'content_hash': self.content_hash(),
        }

    def to_json(self) -> str:
        """Return canonical JSON: sorted keys, no whitespace, no NaN."""
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(',', ':'), allow_nan=False)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> 'LabMap':
        """
        Build and validate a map, refusing an unknown MAJOR version.

        If ``content_hash`` is present it must match the content; a map
        altered after it was written is refused, not repaired.
        """
        if not isinstance(data, dict):
            raise MapError('a map must be a JSON object')
        if data.get('schema') != SCHEMA:
            raise MapError(f'schema is {data.get("schema")!r}, '
                           f'not {SCHEMA!r}')
        _check_major(data.get('version'), 'map')
        width, height = data.get('width'), data.get('height')
        _check_dims(width, height)
        rows = data.get('rows')
        if not (isinstance(rows, list) and len(rows) == height
                and all(isinstance(r, str) and len(r) == width
                        for r in rows)):
            raise MapError(f'rows must be {height} strings of {width} '
                           f'characters')
        text = ''.join(rows)
        if not text.isascii():
            raise MapError(f'rows may only contain {CELL_CHARS!r}')
        occ = text.encode('ascii')
        if occ.translate(None, CELL_CHARS.encode('ascii')):
            raise MapError(f'rows may only contain {CELL_CHARS!r}')
        occ = occ.translate(_FROM_CHARS)
        cost = data.get('cost')
        if cost is not None and not isinstance(cost, list):
            raise MapError('cost must be a list or null')
        geo = data.get('geo')
        resolution = origin = frame = None
        if geo is not None:
            if not isinstance(geo, dict):
                raise MapError('geo must be an object or null')
            resolution, origin = geo.get('resolution'), geo.get('origin')
            frame = geo.get('frame')
            if not (isinstance(origin, list) and len(origin) == 2):
                raise MapError(f'geo.origin must be [x, y], got {origin!r}')
        meta = data.get('meta') or {}
        if not isinstance(meta, dict):
            raise MapError('meta must be an object')
        m = cls(width, height, occ, cost, map_id=data.get('id', ''),
                resolution=resolution,
                origin=None if origin is None else tuple(origin),
                frame=frame, meta=meta)
        declared = data.get('content_hash')
        if declared is not None and declared != m.content_hash():
            raise MapError(f'content_hash {declared!r} does not match the '
                           f'content ({m.content_hash()})')
        return m

    @classmethod
    def from_json(cls, text: str) -> 'LabMap':
        """Parse and validate JSON produced by :meth:`to_json`."""
        try:
            data = json.loads(text)
        except (ValueError, RecursionError) as exc:
            raise MapError(f'not JSON: {exc}') from None
        return cls.from_dict(data)

    @classmethod
    def from_ascii(cls, text: str, map_id: str = '',
                   **kwargs) -> Tuple['LabMap', Dict[str, Tuple[int, int]]]:
        """
        Build a map from ``#`` (occupied), ``?`` (unknown) and free cells.

        Every other character is free. Letters mark cells and are returned
        as ``{letter: (row, col)}``, like :meth:`Grid.from_ascii`.
        """
        rows = [line.strip() for line in text.strip().splitlines()
                if line.strip()]
        if not rows:
            raise MapError('empty map')
        width = len(rows[0])
        if any(len(r) != width for r in rows):
            raise MapError('rows must all be the same length')
        occ = bytearray()
        marks: Dict[str, Tuple[int, int]] = {}
        for r, line in enumerate(rows):
            for c, ch in enumerate(line):
                occ.append(OCCUPIED if ch == '#' else
                           UNKNOWN if ch == '?' else FREE)
                if ch.isalpha():
                    if ch in marks:
                        raise MapError(f'marker {ch!r} appears twice')
                    marks[ch] = (r, c)
        return cls(width, len(rows), bytes(occ), map_id=map_id,
                   **kwargs), marks

    def to_ascii(self) -> str:
        """Return the rows joined by newlines, in ``.#?`` characters."""
        return '\n'.join(self.to_dict()['rows'])


_TO_CHARS = bytes.maketrans(b'\x00\x01\x02', CELL_CHARS.encode('ascii'))
_FROM_CHARS = bytes.maketrans(CELL_CHARS.encode('ascii'), b'\x00\x01\x02')


def _check_major(version, what: str) -> None:
    version = str(version or '')
    try:
        major = int(version.split('.')[0])
    except ValueError:
        raise MapError(f'bad {what} version {version!r}') from None
    if major != MAJOR:
        raise MapError(f'{what} major version {major} is not supported '
                       f'(this reader speaks {MAJOR}.x)')


# -- rasterisation ---------------------------------------------------------

class Raster:
    """
    Paint axis-aligned rectangles into a placed map, in order.

    Every cell starts as ``fill``. :meth:`paint` sets the cells a rectangle
    covers, under one of two declared rules, and later paints override
    earlier ones:

    ``'centre'``
        A cell is covered if its CENTRE lies inside the closed rectangle.
        Area-fair: each cell goes to whatever occupies its middle.
    ``'overlap'``
        A cell is covered if its square overlaps the rectangle with
        positive area -- conservative, a thin wall still marks every cell
        it passes through. This is the rule
        ``gazebo_models/scripts/gen_navigation_world.py`` uses for boxes.
    """

    def __init__(self, width: int, height: int, resolution: float,
                 origin: Tuple[float, float], fill: int = FREE):
        """Start a ``width x height`` raster whose cells are all ``fill``."""
        _check_dims(width, height)
        self.width, self.height = width, height
        self.resolution = float(resolution)
        self.origin = (float(origin[0]), float(origin[1]))
        self.cells = bytearray([fill]) * (width * height)

    def paint(self, xmin: float, xmax: float, ymin: float, ymax: float,
              value: int, rule: str = 'centre') -> int:
        """Set every covered cell to ``value``; return how many were set."""
        if rule not in RULES:
            raise MapError(f'rule must be one of {RULES}, got {rule!r}')
        if value not in (FREE, OCCUPIED, UNKNOWN):
            raise MapError(f'bad value {value!r}')
        res, (ox, oy) = self.resolution, self.origin
        half = res / 2 if rule == 'overlap' else 0.0
        n = 0
        # Only scan the rectangle's neighbourhood, not the whole map.
        c0 = max(0, math.floor((xmin - ox) / res) - 1)
        c1 = min(self.width - 1, math.ceil((xmax - ox) / res) + 1)
        u0 = max(0, math.floor((ymin - oy) / res) - 1)
        u1 = min(self.height - 1, math.ceil((ymax - oy) / res) + 1)
        for up in range(u0, u1 + 1):
            y = oy + (up + 0.5) * res
            if rule == 'overlap':
                inside_y = ymin - half < y < ymax + half
            else:
                inside_y = ymin <= y <= ymax
            if not inside_y:
                continue
            row = self.height - 1 - up
            for col in range(c0, c1 + 1):
                x = ox + (col + 0.5) * res
                if rule == 'overlap':
                    inside = xmin - half < x < xmax + half
                else:
                    inside = xmin <= x <= xmax
                if inside:
                    self.cells[row * self.width + col] = value
                    n += 1
        return n

    def build(self, map_id: str = '', frame: Optional[str] = None,
              meta: Optional[Dict[str, object]] = None) -> LabMap:
        """Return the painted raster as a :class:`LabMap`."""
        return LabMap(self.width, self.height, bytes(self.cells),
                      map_id=map_id, resolution=self.resolution,
                      origin=self.origin, frame=frame, meta=meta)


# -- Nav2 saved maps -------------------------------------------------------

#: The keys a nav2_map_server map yaml may carry, and nothing else.
NAV2_KEYS = ('image', 'mode', 'resolution', 'origin', 'negate',
             'occupied_thresh', 'free_thresh')

#: Bounds on an untrusted PGM, before any pixel is read.
MAX_PGM_BYTES = 64 * 1024 * 1024


def parse_nav2_yaml(text: str) -> Dict[str, object]:
    """
    Parse a nav2_map_server map yaml, and only that.

    The accepted language is flat ``key: value`` lines, ``#`` comments,
    and one flow list ``[x, y, yaw]`` for ``origin``. A key outside
    :data:`NAV2_KEYS`, a nested block or a duplicate key is refused: this
    is not a YAML parser, and it will not guess.
    """
    out: Dict[str, object] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#', 1)[0].rstrip()
        if not line.strip():
            continue
        if line[0].isspace() or ':' not in line:
            raise MapError(f'yaml line {n}: not a flat "key: value" line')
        key, value = (s.strip() for s in line.split(':', 1))
        if key not in NAV2_KEYS:
            raise MapError(f'yaml line {n}: unknown key {key!r}')
        if key in out:
            raise MapError(f'yaml line {n}: duplicate key {key!r}')
        if key == 'image':
            out[key] = value.strip('\'"')
        elif key == 'mode':
            out[key] = value.strip('\'"')
        elif key == 'origin':
            if not (value.startswith('[') and value.endswith(']')):
                raise MapError(f'yaml line {n}: origin must be [x, y, yaw]')
            try:
                parts = [float(p) for p in value[1:-1].split(',')]
            except ValueError:
                raise MapError(f'yaml line {n}: bad origin {value!r}') \
                    from None
            if len(parts) != 3 or not all(map(math.isfinite, parts)):
                raise MapError(f'yaml line {n}: origin must be 3 numbers')
            out[key] = parts
        else:
            try:
                out[key] = float(value)
            except ValueError:
                raise MapError(f'yaml line {n}: {key} must be a number') \
                    from None
    for key in ('image', 'resolution', 'origin'):
        if key not in out:
            raise MapError(f'yaml has no {key!r}')
    return out


def parse_pgm(data: bytes) -> Tuple[int, int, int, bytes]:
    """
    Return ``(width, height, maxval, pixels)`` from a P5 or P2 PGM.

    ``pixels`` is one byte per pixel, row-major from the top. ``maxval``
    must be at most 255. Size is checked before any allocation.
    """
    if len(data) > MAX_PGM_BYTES:
        raise MapError(f'pgm is {len(data)} bytes, over {MAX_PGM_BYTES}')
    magic = data[:2]
    if magic not in (b'P5', b'P2'):
        raise MapError(f'not a P5/P2 pgm (magic {magic!r})')
    pos, fields = 2, []
    while len(fields) < 3:
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b'#':
            while pos < len(data) and data[pos:pos + 1] not in b'\n\r':
                pos += 1
            continue
        start = pos
        while pos < len(data) and data[pos:pos + 1].isdigit():
            pos += 1
        if start == pos:
            raise MapError('pgm header is truncated or malformed')
        fields.append(int(data[start:pos]))
    width, height, maxval = fields
    _check_dims(width, height)
    if not 0 < maxval <= 255:
        raise MapError(f'pgm maxval must be 1..255, got {maxval}')
    n = width * height
    if magic == b'P5':
        pos += 1  # exactly one whitespace byte after maxval
        pixels = data[pos:pos + n]
        if len(pixels) != n:
            raise MapError(f'pgm has {len(pixels)} pixel bytes, '
                           f'expected {n}')
    else:
        values = data[pos:].split()
        if len(values) != n:
            raise MapError(f'pgm has {len(values)} pixels, expected {n}')
        pixels = bytes(int(v) for v in values)
    if max(pixels) > maxval:
        raise MapError('pgm pixel exceeds maxval')
    return width, height, maxval, bytes(pixels)


def from_nav2(yaml_text: str, pgm_bytes: bytes, map_id: str = '',
              frame: str = 'map') -> LabMap:
    """
    Convert a nav2_map_server saved map into a :class:`LabMap`.

    ``trinary`` mode only, as map_server defines it: a pixel's shade
    ``p`` (scaled to 0..255) gives ``occ = p/255`` if ``negate`` else
    ``(255 - p)/255``; ``occ > occupied_thresh`` is occupied, ``occ <
    free_thresh`` is free, anything else unknown. The origin's yaw must
    be 0 -- a rotated map is refused, not silently straightened.
    """
    meta = parse_nav2_yaml(yaml_text)
    mode = meta.get('mode', 'trinary')
    if mode != 'trinary':
        raise MapError(f'only trinary maps are supported, not {mode!r}')
    ox, oy, yaw = meta['origin']
    if yaw != 0.0:
        raise MapError(f'origin yaw {yaw} != 0 is not supported')
    negate = meta.get('negate', 0.0)
    if negate not in (0.0, 1.0):
        raise MapError(f'negate must be 0 or 1, got {negate}')
    occ_t = meta.get('occupied_thresh', 0.65)
    free_t = meta.get('free_thresh', 0.25)
    if not (0.0 <= free_t <= occ_t <= 1.0):
        raise MapError('need 0 <= free_thresh <= occupied_thresh <= 1')
    width, height, maxval, pixels = parse_pgm(pgm_bytes)
    table = bytearray(256)
    for p in range(maxval + 1):
        shade = p * 255.0 / maxval
        occ = shade / 255.0 if negate else (255.0 - shade) / 255.0
        table[p] = (OCCUPIED if occ > occ_t else
                    FREE if occ < free_t else UNKNOWN)
    return LabMap(width, height, pixels.translate(bytes(table)),
                  map_id=map_id, resolution=meta['resolution'],
                  origin=(ox, oy), frame=frame,
                  meta={'source': 'nav2_map_server',
                        'image': meta['image'], 'mode': mode,
                        'negate': int(negate),
                        'occupied_thresh': occ_t, 'free_thresh': free_t})


def load_nav2(yaml_path: str, map_id: str = '',
              frame: str = 'map') -> LabMap:
    """Read a map yaml and the image it names (relative to the yaml)."""
    with open(yaml_path, encoding='utf-8') as f:
        text = f.read(1024 * 1024)
    image = parse_nav2_yaml(text)['image']
    path = image if os.path.isabs(image) else os.path.join(
        os.path.dirname(os.path.abspath(yaml_path)), image)
    with open(path, 'rb') as f:
        data = f.read(MAX_PGM_BYTES + 1)
    return from_nav2(text, data, map_id=map_id, frame=frame)


def to_nav2(m: LabMap, image: str) -> Tuple[str, bytes]:
    """
    Return ``(yaml_text, pgm_bytes)`` for ``m`` as a trinary saved map.

    Free, occupied and unknown are written as 254, 0 and 205, the values
    ``map_saver`` writes, with thresholds 0.65 / 0.196 -- the values
    ``gen_navigation_world.py`` writes. The free threshold matters: 205
    means ``occ = 0.196``, which a ``free_thresh`` of 0.25 would read back
    as FREE. The cost layer and ``meta`` do not survive, so a map with a
    cost layer is refused.
    """
    if m.cost is not None:
        raise MapError('a Nav2 saved map cannot carry a cost layer')
    if not m.has_geo:
        raise MapError('a Nav2 saved map needs resolution and origin')
    pixels = m.occupancy.translate(bytes.maketrans(b'\x00\x01\x02',
                                                   b'\xfe\x00\xcd'))
    pgm = f'P5\n{m.width} {m.height}\n255\n'.encode('ascii') + pixels
    yaml_text = (f'image: {image}\nmode: trinary\n'
                 f'resolution: {m.resolution!r}\n'
                 f'origin: [{m.origin[0]!r}, {m.origin[1]!r}, 0.0]\n'
                 f'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n')
    return yaml_text, pgm


def compare_occupied(truth: LabMap, test: LabMap) -> Dict[str, object]:
    """
    Return cell-level precision and recall of ``test``'s occupied cells.

    Both maps must have the same dimensions and placement. A cell counts
    as occupied only if its value is OCCUPIED. A cell ``test`` marks
    unknown is never a false positive; if ``truth`` has it occupied it is
    a miss for recall, and it is also reported on its own.
    """
    if (truth.width, truth.height) != (test.width, test.height):
        raise MapError('maps differ in dimensions')
    if (truth.resolution, truth.origin) != (test.resolution, test.origin):
        raise MapError('maps differ in placement')
    tp = fp = fn = unk_truth_occ = 0
    for a, b in zip(truth.occupancy, test.occupancy):
        if b == UNKNOWN:
            unk_truth_occ += a == OCCUPIED
            continue
        if a == OCCUPIED and b == OCCUPIED:
            tp += 1
        elif b == OCCUPIED:
            fp += 1
        elif a == OCCUPIED:
            fn += 1
    return {
        'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
        'truth_occupied_marked_unknown': unk_truth_occ,
        'test_unknown': test.count(UNKNOWN),
        'precision': tp / (tp + fp) if tp + fp else None,
        'recall': tp / (tp + fn + unk_truth_occ)
        if tp + fn + unk_truth_occ else None,
    }
