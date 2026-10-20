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
World Spec v3: the modular level kit (M6F.1; docs/v2/m6/WORLD_SPEC_V3.md, ADR 0100).

A v3 level is authored as a list of **kit elements** -- walls, door openings,
racks with their aisles, benches, pallets, ramps, platforms (a mezzanine),
zones (docks, drop zones), object spawns and actor lanes -- plus an object
catalog. It is a superset of v2:

- **v1 and v2 specs are not touched.** :func:`normalize` hands them to
  ``coco_lab.worldspec.normalize`` unchanged, so their canonical bytes, maps
  and every state hash stay exactly what they were (pinned by
  ``test/fixtures/m6f/prechange_v1v2.json``, made before this module existed).
- **v3 lowers onto v2's primitives.** Every solid kit element becomes
  axis-aligned ``boxes`` and every ramp or platform becomes ``elevation``
  (wedges and platforms, ADR 0007), exactly the fields the Arena model,
  ``coco_lab.terrain`` and the rasteriser already read. The lowered lists
  are part of the canonical form, *derived*: re-normalising a canonical v3
  spec recomputes them and refuses any disagreement, so ``normalize`` is
  idempotent and nobody can hand-edit a derived box.
- :func:`from_v2` writes any v2 world as v3 kit elements; lowering gives back
  its boxes and elevation unchanged (tested on the COCO arena).

Validation refuses what the model and the Stack would disagree about, with
the reason: a solid lower than the LiDAR beam (the Stack's 2D scan would
never see what the model's map holds), a door or an aisle narrower than the
robot can pass at the level's resolution, a ramp the terrain model cannot
follow, a rack aisle another solid intrudes on, an actor lane that runs
through a solid, an object standing inside one. Every threshold is derived
from the spec's own robot and arena blocks; none is a new constant.

Standard library only (Pyodide), like ``worldspec``.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from . import worldspec
from .numerics import math
from .worldspec import (_int, _keys, _num, _sources, _str, _vec, BOX_KINDS,
                        scan_height, SPEC_VERSION_V3, SpecError)

SPEC_VERSIONS = worldspec.SPEC_VERSIONS + (SPEC_VERSION_V3,)

#: every kit element kind, in the order the docs describe them
KIT_KINDS = ('wall', 'door', 'rack', 'bench', 'pallet', 'box', 'ramp', 'platform',
             'zone', 'object', 'actor')
#: the solid kinds, lowered to ``boxes`` (and the box kind each lowers to)
SOLID_KINDS = {'wall': 'wall', 'rack': 'obstacle', 'bench': 'obstacle',
               'pallet': 'obstacle'}
ZONE_ROLES = ('dock', 'drop', 'pickup', 'start', 'region')
ACTOR_KINDS = ('forklift', 'walker')
ACTOR_MODES = ('loop', 'pingpong')
SIDES = ('+x', '-x', '+y', '-y')
CATALOG_SHAPES = ('cylinder', 'box')
#: wedges the terrain model follows: axis-aligned (coco_lab.terrain)
_YAWS = (0.0, math.pi)
#: geometric comparisons (m)
_EPS = 1e-9

Rect = Tuple[float, float, float, float]


def is_v3(spec) -> bool:
    """Return whether ``spec`` claims World Spec v3."""
    return isinstance(spec, dict) and spec.get('spec_version') == SPEC_VERSION_V3


def normalize(spec: Dict[str, object]) -> Dict[str, object]:
    """Validate any World Spec (v1, v2 or v3) and return its canonical form."""
    return normalize_v3(spec) if is_v3(spec) else worldspec.normalize(spec)


# -- small geometry -----------------------------------------------------------

def _rect(center, size) -> Rect:
    (x, y), (sx, sy) = center, size[:2]
    return (x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2)


def _overlap(a: Rect, b: Rect, eps: float = _EPS) -> bool:
    """Whether two closed rectangles share interior (touching edges do not)."""
    return a[0] < b[1] - eps and b[0] < a[1] - eps and a[2] < b[3] - eps and b[2] < a[3] - eps


def _inside(p, r: Rect, margin: float = 0.0) -> bool:
    return r[0] + margin <= p[0] <= r[1] - margin and r[2] + margin <= p[1] <= r[3] - margin


def passable_width(spec) -> float:
    """
    Return the narrowest gap the robot can be planned through at the resolution (m).

    The Arena plans on the map inflated by the robot's radius, and the
    rasteriser marks every cell a solid touches, which can grow a solid by up
    to one cell on each side: ``2 * (radius + resolution)``. Derived from the
    spec's own ``robot.radius`` and ``arena.resolution``; tested by planning
    through every door and aisle of the Depot.
    """
    return 2 * (spec['robot']['radius'] + spec['arena']['resolution'])


def obb_corners(cx: float, cy: float, yaw: float, length: float,
                width: float) -> List[Tuple[float, float]]:
    """Return the corners of a ``length`` x ``width`` rectangle along ``yaw`` at (cx, cy)."""
    c, s = math.cos(yaw), math.sin(yaw)
    hl, hw = length / 2, width / 2
    return [(cx + c * a - s * b, cy + s * a + c * b)
            for a, b in ((hl, hw), (-hl, hw), (-hl, -hw), (hl, -hw))]


def obb_hits_rect(corners: Sequence[Tuple[float, float]], r: Rect) -> bool:
    """Return whether a convex quad overlaps an axis-aligned rectangle (separating axes)."""
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    if max(xs) <= r[0] or min(xs) >= r[1] or max(ys) <= r[2] or min(ys) >= r[3]:
        return False
    rc = ((r[0], r[2]), (r[1], r[2]), (r[1], r[3]), (r[0], r[3]))
    for i in range(4):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 4]
        nx, ny = y1 - y0, x0 - x1
        a = [nx * x + ny * y for x, y in corners]
        b = [nx * x + ny * y for x, y in rc]
        if max(a) <= min(b) + _EPS or max(b) <= min(a) + _EPS:
            return False
    return True


# -- the v3 validator -----------------------------------------------------------

def _robot(rb) -> Dict[str, object]:
    """Validate the robot block: exactly v1/v2's fields and rules."""
    rb = _keys(rb, ('wheel_radius', 'wheel_separation', 'radius', 'ground_clearance',
                    'limits', 'lidar'), (), 'robot')
    lim = _keys(rb['limits'], ('teleop_linear', 'teleop_angular', 'auto_linear',
                               'auto_angular', 'linear_accel', 'angular_accel'), (),
                'robot.limits')
    li = _keys(rb['lidar'], ('mount', 'samples', 'angle_min', 'angle_max', 'range_min',
                             'range_max'), (), 'robot.lidar')
    lidar = {'mount': _vec(li['mount'], 3, 'robot.lidar.mount'),
             'samples': _int(li['samples'], 'robot.lidar.samples', 1),
             'angle_min': _num(li['angle_min'], 'robot.lidar.angle_min'),
             'angle_max': _num(li['angle_max'], 'robot.lidar.angle_max'),
             'range_min': _num(li['range_min'], 'robot.lidar.range_min', nonneg=True),
             'range_max': _num(li['range_max'], 'robot.lidar.range_max', positive=True)}
    if not lidar['angle_min'] <= lidar['angle_max']:
        raise SpecError('robot.lidar: angle_min > angle_max')
    if not lidar['range_min'] < lidar['range_max']:
        raise SpecError('robot.lidar: range_min >= range_max')
    return {
        'wheel_radius': _num(rb['wheel_radius'], 'robot.wheel_radius', positive=True),
        'wheel_separation': _num(rb['wheel_separation'], 'robot.wheel_separation',
                                 positive=True),
        'radius': _num(rb['radius'], 'robot.radius', positive=True),
        'ground_clearance': _num(rb['ground_clearance'], 'robot.ground_clearance',
                                 nonneg=True),
        'limits': {k: _num(lim[k], f'robot.limits.{k}', positive=True)
                   for k in ('teleop_linear', 'teleop_angular', 'auto_linear',
                             'auto_angular', 'linear_accel', 'angular_accel')},
        'lidar': lidar,
    }


def _catalog(items) -> List[Dict[str, object]]:
    if not isinstance(items, list):
        raise SpecError('catalog: expected a list')
    out, ids = [], set()
    for i, it in enumerate(items):
        w = f'catalog[{i}]'
        if not isinstance(it, dict) or it.get('shape') not in CATALOG_SHAPES:
            raise SpecError(f'{w}.shape: expected one of {CATALOG_SHAPES}')
        dims = ('diameter', 'height') if it['shape'] == 'cylinder' else ('size',)
        _keys(it, ('id', 'label', 'shape', 'magnetic', 'colour', 'mass') + dims, ('notes',), w)
        item = {'id': _str(it['id'], f'{w}.id'), 'label': _str(it['label'], f'{w}.label'),
                'shape': it['shape'], 'colour': _str(it['colour'], f'{w}.colour'),
                'mass': _num(it['mass'], f'{w}.mass', positive=True)}
        if not isinstance(it['magnetic'], bool):
            raise SpecError(f'{w}.magnetic: expected true or false')
        item['magnetic'] = it['magnetic']
        if it['shape'] == 'cylinder':
            item['diameter'] = _num(it['diameter'], f'{w}.diameter', positive=True)
            item['height'] = _num(it['height'], f'{w}.height', positive=True)
        else:
            size = _vec(it['size'], 3, f'{w}.size')
            if min(size) <= 0:
                raise SpecError(f'{w}.size: must be > 0, got {size}')
            item['size'] = size
        if 'notes' in it:
            item['notes'] = _str(it['notes'], f'{w}.notes')
        if item['id'] in ids:
            raise SpecError(f'{w}.id: {item["id"]!r} used twice')
        ids.add(item['id'])
        out.append(item)
    return out


def _element(e, w: str) -> Dict[str, object]:
    """One kit element, structurally (geometry is checked once all are read)."""
    if not isinstance(e, dict) or e.get('kind') not in KIT_KINDS:
        raise SpecError(f'{w}.kind: expected one of {KIT_KINDS}')
    k = e['kind']
    out = {'id': None, 'kind': k}
    if k == 'wall':
        _keys(e, ('id', 'kind', 'from', 'to', 'thickness', 'height'), (), w)
        a, b = _vec(e['from'], 2, f'{w}.from'), _vec(e['to'], 2, f'{w}.to')
        if (a[0] == b[0]) == (a[1] == b[1]):
            raise SpecError(f'{w}: a wall runs along x or along y, from != to '
                            '(the rasteriser and the terrain model are axis-aligned)')
        out.update({'from': a, 'to': b,
                    'thickness': _num(e['thickness'], f'{w}.thickness', positive=True),
                    'height': _num(e['height'], f'{w}.height', positive=True)})
    elif k == 'door':
        _keys(e, ('id', 'kind', 'wall', 'at', 'width'), (), w)
        out.update({'wall': _str(e['wall'], f'{w}.wall'),
                    'at': _num(e['at'], f'{w}.at', positive=True),
                    'width': _num(e['width'], f'{w}.width', positive=True)})
    elif k in ('rack', 'bench', 'pallet', 'box'):
        req = ('id', 'kind', 'center', 'size', 'height')
        opt = {'rack': ('aisle', 'aisles', 'shelves'), 'box': ('role',)}.get(k, ())
        _keys(e, req + (('aisle', 'aisles', 'shelves') if k == 'rack' else ()),
              opt if k != 'rack' else (), w)
        size = _vec(e['size'], 2, f'{w}.size')
        if min(size) <= 0:
            raise SpecError(f'{w}.size: must be > 0, got {size}')
        out.update({'center': _vec(e['center'], 2, f'{w}.center'), 'size': size,
                    'height': _num(e['height'], f'{w}.height', positive=True)})
        if k == 'box':
            role = e.get('role', 'obstacle')
            if role not in BOX_KINDS:
                raise SpecError(f'{w}.role: {role!r} not in {BOX_KINDS}')
            out['role'] = role
        if k == 'rack':
            out['aisle'] = _num(e['aisle'], f'{w}.aisle', positive=True)
            sides = e['aisles']
            if not isinstance(sides, list) or not sides \
                    or any(s not in SIDES for s in sides) or len(set(sides)) != len(sides):
                raise SpecError(f'{w}.aisles: a non-empty list of distinct {SIDES}')
            out['aisles'] = list(sides)
            shelves = e['shelves']
            if not isinstance(shelves, list):
                raise SpecError(f'{w}.shelves: expected a list of heights')
            out['shelves'] = [_num(s, f'{w}.shelves[{j}]', nonneg=True)
                              for j, s in enumerate(shelves)]
            if out['shelves'] != sorted(out['shelves']) \
                    or any(s >= out['height'] for s in out['shelves']):
                raise SpecError(f'{w}.shelves: ascending, and below the rack top')
    elif k == 'ramp':
        _keys(e, ('id', 'kind', 'foot', 'yaw', 'run', 'rise', 'width'), ('onto',), w)
        yaw = _num(e['yaw'], f'{w}.yaw')
        if not any(abs(yaw - y) < 1e-9 for y in _YAWS):
            raise SpecError(f'{w}.yaw: the terrain model follows axis-aligned ramps '
                            '(yaw 0 or pi, coco_lab.terrain); got {yaw!r}')
        out.update({'foot': _vec(e['foot'], 2, f'{w}.foot'), 'yaw': yaw,
                    'run': _num(e['run'], f'{w}.run', positive=True),
                    'rise': _num(e['rise'], f'{w}.rise', positive=True),
                    'width': _num(e['width'], f'{w}.width', positive=True)})
        if 'onto' in e:
            out['onto'] = _str(e['onto'], f'{w}.onto')
    elif k == 'platform':
        _keys(e, ('id', 'kind', 'center', 'size', 'top'), (), w)
        size = _vec(e['size'], 2, f'{w}.size')
        if min(size) <= 0:
            raise SpecError(f'{w}.size: must be > 0, got {size}')
        out.update({'center': _vec(e['center'], 2, f'{w}.center'), 'size': size,
                    'top': _num(e['top'], f'{w}.top', positive=True)})
    elif k == 'zone':
        _keys(e, ('id', 'kind', 'role', 'center', 'size'), ('label',), w)
        if e['role'] not in ZONE_ROLES:
            raise SpecError(f'{w}.role: {e["role"]!r} not in {ZONE_ROLES}')
        size = _vec(e['size'], 2, f'{w}.size')
        if min(size) <= 0:
            raise SpecError(f'{w}.size: must be > 0, got {size}')
        out.update({'role': e['role'], 'center': _vec(e['center'], 2, f'{w}.center'),
                    'size': size})
        if 'label' in e:
            out['label'] = _str(e['label'], f'{w}.label')
    elif k == 'object':
        _keys(e, ('id', 'kind', 'item', 'at'), ('support', 'shelf', 'yaw'), w)
        out.update({'item': _str(e['item'], f'{w}.item'), 'at': _vec(e['at'], 2, f'{w}.at'),
                    'support': _str(e.get('support', 'floor'), f'{w}.support'),
                    'yaw': _num(e.get('yaw', 0.0), f'{w}.yaw')})
        if 'shelf' in e:
            out['shelf'] = _int(e['shelf'], f'{w}.shelf', 0)
    else:   # actor
        _keys(e, ('id', 'kind', 'actor', 'path', 'mode', 'speed', 'footprint', 'height'),
              ('phase',), w)
        if e['actor'] not in ACTOR_KINDS:
            raise SpecError(f'{w}.actor: {e["actor"]!r} not in {ACTOR_KINDS}')
        if e['mode'] not in ACTOR_MODES:
            raise SpecError(f'{w}.mode: {e["mode"]!r} not in {ACTOR_MODES}')
        path = e['path']
        if not isinstance(path, list) or len(path) < 2:
            raise SpecError(f'{w}.path: at least two points')
        pts = [_vec(p, 2, f'{w}.path[{j}]') for j, p in enumerate(path)]
        if any(a == b for a, b in zip(pts, pts[1:])):
            raise SpecError(f'{w}.path: repeated point')
        fp = _vec(e['footprint'], 2, f'{w}.footprint')
        if min(fp) <= 0:
            raise SpecError(f'{w}.footprint: must be > 0, got {fp}')
        out.update({'actor': e['actor'], 'path': pts, 'mode': e['mode'],
                    'speed': _num(e['speed'], f'{w}.speed', positive=True),
                    'footprint': fp,
                    'height': _num(e['height'], f'{w}.height', positive=True),
                    'phase': _num(e.get('phase', 0.0), f'{w}.phase', nonneg=True)})
    out['id'] = _str(e['id'], f'{w}.id')
    return out


def normalize_v3(spec) -> Dict[str, object]:
    """Validate a World Spec v3 and return its canonical form, lowered primitives included."""
    s = _keys(spec, ('spec_version', 'id', 'title', 'frame', 'world_to_map', 'bounds',
                     'robot', 'start', 'arena', 'kit'),
              ('catalog', 'sources', 'notes', 'boxes', 'elevation'), 'spec')
    out: Dict[str, object] = {'spec_version': SPEC_VERSION_V3,
                              'id': _str(s['id'], 'id'), 'title': _str(s['title'], 'title')}
    if s.get('frame') != 'world':
        raise SpecError('frame: geometry is in the Gazebo world frame ("world")')
    out['frame'] = 'world'
    out['world_to_map'] = _vec(s['world_to_map'], 2, 'world_to_map')
    b = _keys(s['bounds'], ('x_min', 'x_max', 'y_min', 'y_max'), (), 'bounds')
    bounds = {k: _num(b[k], f'bounds.{k}') for k in ('x_min', 'x_max', 'y_min', 'y_max')}
    if not (bounds['x_min'] < bounds['x_max'] and bounds['y_min'] < bounds['y_max']):
        raise SpecError(f'bounds: empty or inverted {bounds}')
    out['bounds'] = bounds
    out['robot'] = _robot(s['robot'])
    st = _keys(s['start'], ('x', 'y', 'theta'), (), 'start')
    out['start'] = {k: _num(st[k], f'start.{k}') for k in ('x', 'y', 'theta')}
    ar = _keys(s['arena'], ('resolution', 'margin', 'dt', 'unknown'), (), 'arena')
    if ar['unknown'] != 'blocked':
        raise SpecError('arena.unknown: only "blocked" (Nav2 runs allow_unknown false)')
    out['arena'] = {'resolution': _num(ar['resolution'], 'arena.resolution', positive=True),
                    'margin': _num(ar['margin'], 'arena.margin', nonneg=True),
                    'dt': _num(ar['dt'], 'arena.dt', positive=True), 'unknown': 'blocked'}
    out['catalog'] = _catalog(s.get('catalog', []))
    if not isinstance(s['kit'], list) or not s['kit']:
        raise SpecError('kit: expected a non-empty list')
    kit, ids = [], set()
    for i, e in enumerate(s['kit']):
        item = _element(e, f'kit[{i}]')
        if item['id'] in ids:
            raise SpecError(f'kit[{i}].id: {item["id"]!r} used twice')
        ids.add(item['id'])
        kit.append(item)
    out['kit'] = kit
    _check_geometry(out)
    out['boxes'], out['elevation'] = lower(out)
    for key in ('boxes', 'elevation'):
        if key in s and s[key] != out[key]:
            raise SpecError(f'{key}: derived from the kit and must not be edited; the '
                            'given list differs from what the kit lowers to')
    if 'sources' in s:
        out['sources'] = _sources(s['sources'], 'sources')
    if 'notes' in s:
        out['notes'] = _str(s['notes'], 'notes')
    return out


# -- lowering: kit -> v2 primitives ---------------------------------------------

def _wall_segments(wall, doors) -> List[Tuple[float, float]]:
    """Return the wall's solid stretches along its length, ``(s0, s1)`` from ``from``."""
    (ax, ay), (bx, by) = wall['from'], wall['to']
    length = abs(bx - ax) + abs(by - ay)
    cuts = sorted((d['at'] - d['width'] / 2, d['at'] + d['width'] / 2) for d in doors)
    out, s = [], 0.0
    for c0, c1 in cuts:
        if c0 > s:
            out.append((s, c0))
        s = c1
    if s < length:
        out.append((s, length))
    return out


def _wall_boxes(wall, doors) -> List[Dict[str, object]]:
    (ax, ay), (bx, by) = wall['from'], wall['to']
    along_x = ay == by
    sign = 1.0 if (bx > ax if along_x else by > ay) else -1.0
    t, h = wall['thickness'], wall['height']
    out = []
    segs = _wall_segments(wall, doors)
    for j, (s0, s1) in enumerate(segs):
        mid = (s0 + s1) / 2
        if along_x:
            center, size = [ax + sign * mid, ay], [s1 - s0, t]
        else:
            center, size = [ax, ay + sign * mid], [t, s1 - s0]
        bid = wall['id'] if len(segs) == 1 else f'{wall["id"]}#{j}'
        out.append({'id': bid, 'kind': 'wall', 'center': center, 'size': size,
                    'z': h / 2, 'height': h})
    return out


def lower(spec) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """
    Lower a (validated) v3 kit to v2's ``boxes`` and ``elevation``.

    Kit order is kept: each solid element gives its boxes in turn (a wall cut
    by doors gives one box per solid stretch, ``<id>#<n>``), each ramp a
    wedge, each platform a platform. Boxes stand on the floor
    (``z = height / 2``), as every v2 box does.
    """
    doors: Dict[str, List[Dict[str, object]]] = {}
    for e in spec['kit']:
        if e['kind'] == 'door':
            doors.setdefault(e['wall'], []).append(e)
    boxes, elevation = [], []
    for e in spec['kit']:
        k = e['kind']
        if k == 'wall':
            boxes.extend(_wall_boxes(e, doors.get(e['id'], [])))
        elif k in SOLID_KINDS or k == 'box':
            boxes.append({'id': e['id'], 'kind': e['role'] if k == 'box' else SOLID_KINDS[k],
                          'center': list(e['center']), 'size': list(e['size']),
                          'z': e['height'] / 2, 'height': e['height']})
        elif k == 'ramp':
            elevation.append({'id': e['id'], 'kind': 'wedge', 'foot': list(e['foot']),
                              'yaw': e['yaw'], 'run': e['run'], 'rise': e['rise'],
                              'width': e['width']})
        elif k == 'platform':
            elevation.append({'id': e['id'], 'kind': 'platform', 'center': list(e['center']),
                              'size': [e['size'][0], e['size'][1], e['top']]})
    return boxes, elevation


def _elevation_rect(e) -> Rect:
    if e['kind'] == 'wedge':
        fx, fy = e['foot']
        d = 1.0 if math.cos(e['yaw']) > 0 else -1.0
        a, b = fx, fx + d * e['run']
        return (min(a, b), max(a, b), fy - e['width'] / 2, fy + e['width'] / 2)
    return _rect(e['center'], e['size'])


def static_rects(spec) -> List[Tuple[str, Rect]]:
    """Return every solid's and elevated solid's footprint with its id, world frame."""
    if 'boxes' in spec:
        boxes, elevation = spec['boxes'], spec['elevation']
    else:
        boxes, elevation = lower(spec)
    return ([(bx['id'], _rect(bx['center'], bx['size'])) for bx in boxes]
            + [(e['id'], _elevation_rect(e)) for e in elevation])


# -- geometry checks ------------------------------------------------------------

def _check_geometry(spec) -> None:
    by_id = {e['id']: e for e in spec['kit']}
    catalog = {c['id']: c for c in spec['catalog']}
    beam = scan_height(spec)
    gap = passable_width(spec)
    b = spec['bounds']
    m = spec['arena']['margin']
    outer = (b['x_min'] - m, b['x_max'] + m, b['y_min'] - m, b['y_max'] + m)
    inner = (b['x_min'], b['x_max'], b['y_min'], b['y_max'])
    for e in spec['kit']:
        w = f'kit {e["id"]!r}'
        if 'height' in e and e['kind'] != 'actor' and e['height'] <= beam:
            raise SpecError(f'{w}: {e["height"]} m tall is at or below the LiDAR beam '
                            f"({beam:.4f} m): the Stack's 2D scan would never see what the "
                            "model's map holds; make it taller or leave it out")
        if e['kind'] == 'door':
            wall = by_id.get(e['wall'])
            if wall is None or wall['kind'] != 'wall':
                raise SpecError(f'{w}: wall {e["wall"]!r} is not a wall in the kit')
            (ax, ay), (bx, by) = wall['from'], wall['to']
            length = abs(bx - ax) + abs(by - ay)
            if not (e['width'] / 2 <= e['at'] <= length - e['width'] / 2):
                raise SpecError(f'{w}: the opening runs past the end of {e["wall"]!r}')
            if e['width'] < gap:
                raise SpecError(f'{w}: {e["width"]} m is narrower than the robot can pass '
                                f'at this resolution ({gap:.3f} m = 2 x (radius + '
                                'resolution))')
    for wall_id in {e['wall'] for e in spec['kit'] if e['kind'] == 'door'}:
        cuts = sorted((d['at'] - d['width'] / 2, d['at'] + d['width'] / 2)
                      for d in spec['kit'] if d['kind'] == 'door' and d['wall'] == wall_id)
        if any(a[1] > b_[0] for a, b_ in zip(cuts, cuts[1:])):
            raise SpecError(f'kit {wall_id!r}: two door openings overlap')
    boxes, elevation = lower(spec)
    rects = [(bx['id'], _rect(bx['center'], bx['size'])) for bx in boxes] \
        + [(e['id'], _elevation_rect(e)) for e in elevation]
    for rid, r in rects:
        if not (outer[0] <= r[0] and r[1] <= outer[1] and outer[2] <= r[2]
                and r[3] <= outer[3]):
            raise SpecError(f'kit {rid!r}: outside the bounds and their margin')
    for e in spec['kit']:
        w = f'kit {e["id"]!r}'
        if e['kind'] == 'rack':
            _check_aisles(e, rects, gap, inner)
        elif e['kind'] == 'ramp' and 'onto' in e:
            _check_onto(e, by_id)
        elif e['kind'] == 'zone':
            if not _inside(e['center'], inner):
                raise SpecError(f"{w}: the zone's centre is outside the bounds")
        elif e['kind'] == 'object':
            _check_object(e, by_id, catalog, rects, inner)
        elif e['kind'] == 'actor':
            _check_actor(e, rects, inner)


def _aisle_strip(r: Rect, side: str, width: float) -> Rect:
    x0, x1, y0, y1 = r
    return {'+x': (x1, x1 + width, y0, y1), '-x': (x0 - width, x0, y0, y1),
            '+y': (x0, x1, y1, y1 + width), '-y': (x0, x1, y0 - width, y0)}[side]


def _check_aisles(rack, rects, gap, inner) -> None:
    w = f'kit {rack["id"]!r}'
    if rack['aisle'] < gap:
        raise SpecError(f'{w}: aisle {rack["aisle"]} m is narrower than the robot can pass '
                        f'at this resolution ({gap:.3f} m)')
    r = _rect(rack['center'], rack['size'])
    for side in rack['aisles']:
        strip = _aisle_strip(r, side, rack['aisle'])
        if not (inner[0] - _EPS <= strip[0] and strip[1] <= inner[1] + _EPS
                and inner[2] - _EPS <= strip[2] and strip[3] <= inner[3] + _EPS):
            raise SpecError(f'{w}: its {side} aisle runs outside the bounds')
        for oid, o in rects:
            if oid != rack['id'] and _overlap(strip, o):
                raise SpecError(f'{w}: {oid!r} stands in its {side} aisle '
                                f'({rack["aisle"]} m clear required)')


def _check_onto(ramp, by_id) -> None:
    w = f'kit {ramp["id"]!r}'
    p = by_id.get(ramp['onto'])
    if p is None or p['kind'] != 'platform':
        raise SpecError(f'{w}.onto: {ramp["onto"]!r} is not a platform in the kit')
    if abs(p['top'] - ramp['rise']) > 1e-9:
        raise SpecError(f'{w}: rises {ramp["rise"]} m onto a platform {p["top"]} m high')
    d = 1.0 if math.cos(ramp['yaw']) > 0 else -1.0
    crest = ramp['foot'][0] + d * ramp['run']
    px0, px1, py0, py1 = _rect(p['center'], p['size'])
    edge = px0 if d > 0 else px1
    fy, hw = ramp['foot'][1], ramp['width'] / 2
    if abs(crest - edge) > 1e-9 or fy - hw < py0 - 1e-9 or fy + hw > py1 + 1e-9:
        raise SpecError(f'{w}: its crest does not meet {ramp["onto"]!r}\'s edge '
                        f'(crest x {crest}, edge x {edge})')


def _footprint(item) -> float:
    """Return the catalog item's footprint radius (m), for placement checks."""
    if item['shape'] == 'cylinder':
        return item['diameter'] / 2
    return math.hypot(item['size'][0], item['size'][1]) / 2


def _check_object(o, by_id, catalog, rects, inner) -> None:
    w = f'kit {o["id"]!r}'
    item = catalog.get(o['item'])
    if item is None:
        raise SpecError(f'{w}.item: {o["item"]!r} is not in the catalog')
    rad = _footprint(item)
    if o['support'] == 'floor':
        if 'shelf' in o:
            raise SpecError(f'{w}: a shelf index needs a rack support')
        if not _inside(o['at'], inner, rad):
            raise SpecError(f'{w}: outside the bounds')
        for rid, r in rects:
            if _overlap((o['at'][0] - rad, o['at'][0] + rad, o['at'][1] - rad,
                         o['at'][1] + rad), r):
                raise SpecError(f'{w}: stands inside {rid!r} (support "floor")')
        return
    sup = by_id.get(o['support'])
    if sup is None or sup['kind'] not in ('bench', 'rack', 'pallet', 'platform', 'box'):
        raise SpecError(f'{w}.support: {o["support"]!r} is not a bench, rack, pallet, '
                        'box or platform in the kit')
    if sup['kind'] == 'rack':
        if 'shelf' not in o or o['shelf'] >= len(sup['shelves']):
            raise SpecError(f'{w}: on a rack, name a shelf index below '
                            f'{len(sup["shelves"])}')
    elif 'shelf' in o:
        raise SpecError(f'{w}: only a rack has shelves')
    if not _inside(o['at'], _rect(sup['center'], sup['size']), rad):
        raise SpecError(f'{w}: not on {o["support"]!r}\'s top')


def _check_actor(a, rects, inner) -> None:
    w = f'kit {a["id"]!r}'
    for p in a['path']:
        if not _inside(p, inner):
            raise SpecError(f'{w}: path point {p} outside the bounds')
    length, width = a['footprint']
    pts = a['path'] + ([a['path'][0]] if a['mode'] == 'loop' else [])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        yaw = math.atan2(y1 - y0, x1 - x0)
        n = max(1, math.ceil(seg / 0.05))
        for j in range(n + 1):
            f = j / n
            corners = obb_corners(x0 + f * (x1 - x0), y0 + f * (y1 - y0), yaw, length, width)
            for rid, r in rects:
                if obb_hits_rect(corners, r):
                    raise SpecError(f'{w}: its lane runs through {rid!r} near '
                                    f'({x0 + f * (x1 - x0):.2f}, {y0 + f * (y1 - y0):.2f})')


# -- reading a canonical v3 spec ---------------------------------------------------

def elements(spec, kind: str) -> List[Dict[str, object]]:
    """Return the canonical spec's kit elements of one kind, in kit order."""
    return [e for e in spec['kit'] if e['kind'] == kind]


def support_height(spec, obj) -> float:
    """Return the height (m, above the floor) of the surface an object stands on."""
    if obj['support'] == 'floor':
        return 0.0
    sup = next(e for e in spec['kit'] if e['id'] == obj['support'])
    if sup['kind'] == 'rack':
        return sup['shelves'][obj['shelf']]
    if sup['kind'] == 'platform':
        return sup['top']
    return sup['height']


def objects(spec) -> List[Dict[str, object]]:
    """
    Every object spawn, resolved: catalog fields, its base height, world frame.

    ``z`` is the height of the surface it stands on (the floor 0, a bench or
    pallet top, a rack shelf, a platform top).
    """
    catalog = {c['id']: c for c in spec['catalog']}
    out = []
    for o in elements(spec, 'object'):
        out.append(dict(catalog[o['item']], id=o['id'], item=o['item'], x=o['at'][0],
                        y=o['at'][1], z=support_height(spec, o), yaw=o['yaw'],
                        support=o['support']))
    return out


def actor_pose(actor, t: float) -> Tuple[float, float, float]:
    """
    Return the actor's (x, y, yaw) at time ``t`` (s), world frame: kinematic only.

    It moves at ``speed`` along its path from ``phase`` metres in; a ``loop``
    path closes back to its first point, a ``pingpong`` path walks back the
    way it came. The yaw is the direction of travel.
    """
    pts = list(actor['path'])
    if actor['mode'] == 'loop':
        pts.append(pts[0])
    else:
        pts = pts + pts[-2::-1]
    segs = [(a, b, math.hypot(b[0] - a[0], b[1] - a[1])) for a, b in zip(pts, pts[1:])]
    total = sum(s[2] for s in segs)
    s = (actor['phase'] + actor['speed'] * t) % total
    for a, b, length in segs:
        if s <= length or (a, b, length) == segs[-1]:
            f = min(1.0, s / length)
            return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]),
                    math.atan2(b[1] - a[1], b[0] - a[0]))
        s -= length
    raise AssertionError('unreachable')


def actor_corners(actor, t: float) -> List[Tuple[float, float]]:
    """Return the actor's collision footprint at time ``t``, world frame."""
    x, y, yaw = actor_pose(actor, t)
    return obb_corners(x, y, yaw, actor['footprint'][0], actor['footprint'][1])


def zones(spec, role: Optional[str] = None) -> List[Dict[str, object]]:
    """Return the zones, optionally of one role."""
    return [z for z in elements(spec, 'zone') if role is None or z['role'] == role]


# -- v2 -> v3 -------------------------------------------------------------------

def from_v2(spec) -> Dict[str, object]:
    """
    Write a World Spec v2 as v3 kit elements (the superset, made concrete).

    Each box becomes a ``box`` element of the same role (its ``z`` must be
    ``height / 2``: a box standing on the floor, as every v2 box does), each
    wedge a ``ramp``, each platform a ``platform``. Lowering the result gives
    back the v2 boxes and elevation exactly.
    """
    s = worldspec.normalize(spec)
    if s['spec_version'] != worldspec.SPEC_VERSION_V2:
        raise SpecError('from_v2: needs a World Spec v2')
    kit = []
    for bx in s['boxes']:
        if bx['z'] != bx['height'] / 2:
            raise SpecError(f'from_v2: box {bx["id"]!r} does not stand on the floor')
        kit.append({'id': bx['id'], 'kind': 'box', 'role': bx['kind'],
                    'center': list(bx['center']), 'size': list(bx['size']),
                    'height': bx['height']})
    for e in s['elevation']:
        if e['kind'] == 'wedge':
            kit.append({'id': e['id'], 'kind': 'ramp', 'foot': list(e['foot']),
                        'yaw': e['yaw'], 'run': e['run'], 'rise': e['rise'],
                        'width': e['width']})
        else:
            kit.append({'id': e['id'], 'kind': 'platform', 'center': list(e['center']),
                        'size': list(e['size'][:2]), 'top': e['size'][2]})
    out = {k: s[k] for k in ('id', 'title', 'frame', 'world_to_map', 'bounds', 'robot',
                             'start', 'arena')}
    out.update(spec_version=SPEC_VERSION_V3, kit=kit, catalog=[])
    if 'sources' in s:
        out['sources'] = dict(s['sources'])
    return out
