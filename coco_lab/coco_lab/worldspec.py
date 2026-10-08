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
World Spec v1: one versioned description of a world and its robot.

README section 5.1: geometry, bays, ramp zone, obstacles and the robot,
from which generators produce the Arena world (here) and, later, the
Gazebo SDF (designed for, not built: every 3D quantity the SDF needs --
box heights and centre heights, the ramp grade -- is carried and
validated, but nothing writes SDF in M1). ``docs/v2/WORLD_SPEC.md`` is the
reference; ``worlds/coco_arena_v1.yaml`` is the COCO arena.

The spec arrives as a parsed dict (YAML is parsed by the caller: this
module is standard-library only, so it runs under Pyodide unchanged).

- :func:`normalize` validates and returns the canonical form: every
  number a float except declared integers, keys in a fixed set, lists in
  their given order. Two YAML files that mean the same world give the same
  canonical form, and :func:`canonical_bytes` (Python's canonical JSON) is
  what ``run_id`` hashes (coco_schemas.runid).
- :func:`arena_map` rasterises the world into the :class:`LabMap` the
  Arena model drives in, in the MAP frame (world + ``world_to_map``), with
  exactly the rules ``gazebo_models/scripts/gen_navigation_world.py`` uses
  for the Stack's saved map, so the two agree cell for cell (tested).
"""

import json
import math
from typing import Dict, List, Tuple

from .maps import FREE, LabMap, OCCUPIED, UNKNOWN

SPEC_VERSION = 'coco.world_spec.v1'
BOX_KINDS = ('wall', 'obstacle', 'landmark', 'guard')


class SpecError(ValueError):
    """A World Spec that does not conform to v1."""


# -- validation ---------------------------------------------------------------

def _num(v, where: str, positive: bool = False, nonneg: bool = False) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) \
            or not math.isfinite(v):
        raise SpecError(f'{where}: expected a finite number, got {v!r}')
    if positive and not v > 0:
        raise SpecError(f'{where}: must be > 0, got {v!r}')
    if nonneg and not v >= 0:
        raise SpecError(f'{where}: must be >= 0, got {v!r}')
    return float(v)


def _int(v, where: str, minimum: int = 0) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < minimum:
        raise SpecError(f'{where}: expected an int >= {minimum}, got {v!r}')
    return v


def _str(v, where: str) -> str:
    if not isinstance(v, str) or not v:
        raise SpecError(f'{where}: expected a non-empty string, got {v!r}')
    return v


def _vec(v, n: int, where: str) -> List[float]:
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise SpecError(f'{where}: expected {n} numbers, got {v!r}')
    return [_num(x, f'{where}[{i}]') for i, x in enumerate(v)]


def _keys(d, required, optional, where: str) -> dict:
    if not isinstance(d, dict):
        raise SpecError(f'{where}: expected a mapping, got {type(d).__name__}')
    missing = [k for k in required if k not in d]
    extra = [k for k in d if k not in required and k not in optional]
    if missing:
        raise SpecError(f'{where}: missing {missing}')
    if extra:
        raise SpecError(f'{where}: unknown keys {extra} (v1 refuses, never '
                        'ignores, what it does not define)')
    return d


def _sources(d, where):
    _keys(d, (), tuple(d) if isinstance(d, dict) else (), where)
    return {k: _str(v, f'{where}.{k}') for k, v in d.items()}


def normalize(spec: Dict[str, object]) -> Dict[str, object]:
    """Validate ``spec`` and return its canonical form (a new dict)."""
    s = _keys(spec, ('spec_version', 'id', 'title', 'frame', 'world_to_map',
                     'bounds', 'boxes', 'ramps', 'robot', 'start', 'arena'),
              ('sources', 'notes'), 'spec')
    if s['spec_version'] != SPEC_VERSION:
        raise SpecError(f'spec_version is {s["spec_version"]!r}, this reader '
                        f'knows {SPEC_VERSION!r}')
    out: Dict[str, object] = {
        'spec_version': SPEC_VERSION,
        'id': _str(s['id'], 'id'),
        'title': _str(s['title'], 'title'),
    }
    if s.get('frame') != 'world':
        raise SpecError('frame: v1 geometry is in the Gazebo world frame '
                        '("world")')
    out['frame'] = 'world'
    out['world_to_map'] = _vec(s['world_to_map'], 2, 'world_to_map')
    b = _keys(s['bounds'], ('x_min', 'x_max', 'y_min', 'y_max'), (), 'bounds')
    bounds = {k: _num(b[k], f'bounds.{k}') for k in ('x_min', 'x_max',
                                                     'y_min', 'y_max')}
    if not (bounds['x_min'] < bounds['x_max']
            and bounds['y_min'] < bounds['y_max']):
        raise SpecError(f'bounds: empty or inverted {bounds}')
    out['bounds'] = bounds

    if not isinstance(s['boxes'], list) or not s['boxes']:
        raise SpecError('boxes: expected a non-empty list')
    boxes, ids = [], set()
    for i, bx in enumerate(s['boxes']):
        w = f'boxes[{i}]'
        _keys(bx, ('id', 'kind', 'center', 'size', 'z', 'height'), (), w)
        bid = _str(bx['id'], f'{w}.id')
        if bid in ids:
            raise SpecError(f'{w}.id: {bid!r} used twice')
        ids.add(bid)
        if bx['kind'] not in BOX_KINDS:
            raise SpecError(f'{w}.kind: {bx["kind"]!r} not in {BOX_KINDS}')
        size = _vec(bx['size'], 2, f'{w}.size')
        if min(size) <= 0:
            raise SpecError(f'{w}.size: must be > 0, got {size}')
        boxes.append({'id': bid, 'kind': bx['kind'],
                      'center': _vec(bx['center'], 2, f'{w}.center'),
                      'size': size,
                      'z': _num(bx['z'], f'{w}.z', nonneg=True),
                      'height': _num(bx['height'], f'{w}.height',
                                     positive=True)})
    out['boxes'] = boxes

    r = _keys(s['ramps'], ('angle_deg', 'foot_x', 'run', 'platform_length',
                           'width', 'centres_y'), (), 'ramps')
    centres = r['centres_y']
    if not isinstance(centres, list) or not centres:
        raise SpecError('ramps.centres_y: expected a non-empty list')
    out['ramps'] = {
        'angle_deg': _num(r['angle_deg'], 'ramps.angle_deg', positive=True),
        'foot_x': _num(r['foot_x'], 'ramps.foot_x'),
        'run': _num(r['run'], 'ramps.run', positive=True),
        'platform_length': _num(r['platform_length'],
                                'ramps.platform_length', positive=True),
        'width': _num(r['width'], 'ramps.width', positive=True),
        'centres_y': [_num(c, f'ramps.centres_y[{i}]')
                      for i, c in enumerate(centres)],
    }
    if out['ramps']['angle_deg'] >= 90:
        raise SpecError('ramps.angle_deg: must be < 90')

    rb = _keys(s['robot'], ('wheel_radius', 'wheel_separation', 'radius',
                            'ground_clearance', 'limits', 'lidar'), (),
               'robot')
    lim = _keys(rb['limits'], ('teleop_linear', 'teleop_angular',
                               'auto_linear', 'auto_angular',
                               'linear_accel', 'angular_accel'), (),
                'robot.limits')
    li = _keys(rb['lidar'], ('mount', 'samples', 'angle_min', 'angle_max',
                             'range_min', 'range_max'), (), 'robot.lidar')
    lidar = {'mount': _vec(li['mount'], 3, 'robot.lidar.mount'),
             'samples': _int(li['samples'], 'robot.lidar.samples', 1),
             'angle_min': _num(li['angle_min'], 'robot.lidar.angle_min'),
             'angle_max': _num(li['angle_max'], 'robot.lidar.angle_max'),
             'range_min': _num(li['range_min'], 'robot.lidar.range_min',
                               nonneg=True),
             'range_max': _num(li['range_max'], 'robot.lidar.range_max',
                               positive=True)}
    if not lidar['angle_min'] <= lidar['angle_max']:
        raise SpecError('robot.lidar: angle_min > angle_max')
    if not lidar['range_min'] < lidar['range_max']:
        raise SpecError('robot.lidar: range_min >= range_max')
    out['robot'] = {
        'wheel_radius': _num(rb['wheel_radius'], 'robot.wheel_radius',
                             positive=True),
        'wheel_separation': _num(rb['wheel_separation'],
                                 'robot.wheel_separation', positive=True),
        'radius': _num(rb['radius'], 'robot.radius', positive=True),
        'ground_clearance': _num(rb['ground_clearance'],
                                 'robot.ground_clearance', nonneg=True),
        'limits': {k: _num(lim[k], f'robot.limits.{k}', positive=True)
                   for k in ('teleop_linear', 'teleop_angular',
                             'auto_linear', 'auto_angular', 'linear_accel',
                             'angular_accel')},
        'lidar': lidar,
    }
    st = _keys(s['start'], ('x', 'y', 'theta'), (), 'start')
    out['start'] = {k: _num(st[k], f'start.{k}') for k in ('x', 'y', 'theta')}
    ar = _keys(s['arena'], ('resolution', 'margin', 'dt', 'unknown'), (),
               'arena')
    if ar['unknown'] not in ('blocked',):
        raise SpecError('arena.unknown: v1 knows only "blocked" (the Stack '
                        'runs Nav2 with allow_unknown false)')
    out['arena'] = {'resolution': _num(ar['resolution'], 'arena.resolution',
                                       positive=True),
                    'margin': _num(ar['margin'], 'arena.margin', nonneg=True),
                    'dt': _num(ar['dt'], 'arena.dt', positive=True),
                    'unknown': ar['unknown']}
    if 'sources' in s:
        out['sources'] = _sources(s['sources'], 'sources')
    if 'notes' in s:
        out['notes'] = _str(s['notes'], 'notes')
    return out


def canonical_bytes(spec: Dict[str, object]) -> bytes:
    """Return the canonical bytes of a spec (normalised first)."""
    return json.dumps(normalize(spec), sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


# -- the Arena world ------------------------------------------------------------

def scan_height(spec: Dict[str, object]) -> float:
    """Return the LiDAR beam height above the ground (m)."""
    rb = spec['robot']
    return rb['ground_clearance'] + rb['lidar']['mount'][2]


def ramp_rectangles(spec) -> List[Tuple[float, float, float, float]]:
    """
    Return each ramp bay's footprint at the LiDAR scan height.

    A flat-ground beam hits the up-ramp where the ramp is as high as the
    beam, ``inset = scan_height / tan(angle)`` past the foot, and the
    down-ramp the same distance before its far foot. ``(x0, x1, y0, y1)``
    in the world frame.
    """
    r = spec['ramps']
    inset = scan_height(spec) / math.tan(math.radians(r['angle_deg']))
    x0 = r['foot_x'] + inset
    x1 = r['foot_x'] + 2 * r['run'] + r['platform_length'] - inset
    return [(x0, x1, y - r['width'] / 2, y + r['width'] / 2)
            for y in r['centres_y']]


def box_rectangles(spec) -> List[Tuple[float, float, float, float]]:
    """Return every box's footprint ``(x0, x1, y0, y1)``, world frame."""
    out = []
    for b in spec['boxes']:
        (x, y), (sx, sy) = b['center'], b['size']
        out.append((x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2))
    return out


def arena_map(spec: Dict[str, object], map_id: str = '') -> LabMap:
    """
    Rasterise the world into the Arena's LabMap, in the MAP frame.

    The rules are ``gen_navigation_world.py``'s, so the result equals the
    Stack's saved map: cells inside the bounds are free; a ramp's scan-height
    footprint is occupied on its one-cell rim and unknown inside (the scan
    sees the silhouette, not the interior); every cell a box's collision
    rectangle touches (conservatively, half a cell grown) is occupied; the
    ``margin`` outside the bounds is unknown. Unknown is non-traversable
    (``arena.unknown == "blocked"``).
    """
    spec = normalize(spec)
    b, res = spec['bounds'], spec['arena']['resolution']
    m = spec['arena']['margin']
    ox, oy = b['x_min'] - m, b['y_min'] - m
    width = round((b['x_max'] - b['x_min'] + 2 * m) / res)
    height = round((b['y_max'] - b['y_min'] + 2 * m) / res)
    ramps, boxes = ramp_rectangles(spec), box_rectangles(spec)
    h = res / 2
    occ = bytearray(width * height)
    for row in range(height):
        y = oy + (height - row - 0.5) * res
        for col in range(width):
            x = ox + (col + 0.5) * res
            v = FREE if (b['x_min'] < x < b['x_max']
                         and b['y_min'] < y < b['y_max']) else UNKNOWN
            for a, bb, c, d in ramps:
                if a - h < x < bb + h and c - h < y < d + h:
                    v = (OCCUPIED if min(abs(x - a), abs(x - bb), abs(y - c),
                                         abs(y - d)) <= res else UNKNOWN)
            for a, bb, c, d in boxes:
                if a - h < x < bb + h and c - h < y < d + h:
                    v = OCCUPIED
                    break
            occ[row * width + col] = v
    dx, dy = spec['world_to_map']
    return LabMap(width, height, bytes(occ), map_id=map_id or spec['id'],
                  resolution=res, origin=(ox + dx, oy + dy), frame='map',
                  meta={'world_spec': spec['id']})


def to_map_frame(spec, x: float, y: float) -> Tuple[float, float]:
    """Convert a world-frame point into the map frame."""
    dx, dy = spec['world_to_map']
    return (x + dx, y + dy)
