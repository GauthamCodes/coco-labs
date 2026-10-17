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
One level, three outputs (M6F.2; README §5.1, invariant 12).

A World Spec (v1, v2 or v3) compiles to:

1. **The Arena model world** (:func:`arena_world`): the drive map the robot
   moves and plans in, the map its LiDAR scans, the elevation it follows, and
   (v3) the object spawns, actor lanes, zones and catalog -- at the level's
   resolution, or another one (0.1 m for the game, 0.05 m for Research).
2. **A Gazebo SDF world** (:func:`sdf_world`): every box a static model with a
   matching collision box; every ramp a solid right-triangular wedge (a binary
   STL, as ``gazebo_models/scripts/gen_ramp.py`` makes the Stack's); every
   platform a static box; every object a dynamic model; every actor a model
   **with a collision body** (Lab 5's lesson: an actor with none let a
   controller report "reached" through it), moved kinematically through
   ``set_pose`` from the schedule in ``actors.json``. The world's physics,
   systems, lights and scene come from a template SDF (the Stack's own world),
   never invented here.
3. **A Nav2 map** (:func:`nav2_map`): the map the Stack's 2D LiDAR would
   build, by ``gen_navigation_world.py``'s rules: free inside the bounds,
   unknown outside; each elevated solid's scan-height silhouette occupied on
   its one-cell rim and unknown inside; every box occupied. For the COCO arena
   it reproduces the Stack's saved ``coco_navigation.pgm`` (tested).

Standard library only, like the rest of ``coco_lab``; the YAML params file is
written by ``tools/m6/gen_level.py``, which has PyYAML.
"""

import copy
import io
import json
import math
import struct
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from . import worldspec_v3 as v3
from .maps import FREE, LabMap, OCCUPIED, UNKNOWN
from .terrain import Terrain
from .worldspec import (_rasterise, arena_map, box_rectangles, normalize, ramp_rectangles,
                        scan_height, SPEC_VERSION, terrain_map, TERRAIN_SPEC_VERSIONS)

#: ``gen_navigation_world.py``'s trinary PGM values and thresholds
PGM_VALUE = {FREE: 254, OCCUPIED: 0, UNKNOWN: 205}
OCCUPIED_THRESH = 0.65
FREE_THRESH = 0.196
#: the Stack's box colour (``gen_navigation_world.py``)
BOX_RGBA = '0.55 0.55 0.57 1'


def with_resolution(spec, resolution: Optional[float]) -> Dict[str, object]:
    """Return the canonical spec, at another arena resolution if one is given."""
    s = normalize(spec)
    if resolution is None or resolution == s['arena']['resolution']:
        return s
    s = copy.deepcopy(s)
    s['arena']['resolution'] = float(resolution)
    return normalize(s)


# -- 1. the Arena model world -----------------------------------------------------

def arena_world(spec, resolution: Optional[float] = None) -> Dict[str, object]:
    """
    Return the Arena model's world: maps, elevation and (v3) objects and actors.

    ``drive_map`` is what the robot moves and plans in (``arena_map``),
    ``scan_map`` what its LiDAR meets (boxes alone on a terrain world; the
    ramps are met analytically), both in the MAP frame.
    """
    s = with_resolution(spec, resolution)
    terrain = s['spec_version'] in TERRAIN_SPEC_VERSIONS
    drive = arena_map(s)
    out = {'spec_id': s['id'], 'spec_version': s['spec_version'],
           'resolution': s['arena']['resolution'], 'drive_map': drive,
           'scan_map': terrain_map(s, scan_only=True) if terrain else drive,
           'elevation': list(s.get('elevation', [])), 'objects': [], 'actors': [],
           'zones': [], 'catalog': []}
    if v3.is_v3(s):
        out.update(objects=v3.objects(s), actors=v3.elements(s, 'actor'),
                   zones=v3.zones(s), catalog=list(s['catalog']))
    return out


def arena_world_json(spec, resolution: Optional[float] = None) -> str:
    """Return :func:`arena_world` as canonical JSON (maps in MAP_FORMAT's form)."""
    w = arena_world(spec, resolution)
    w = dict(w, drive_map=w['drive_map'].to_dict(), scan_map=w['scan_map'].to_dict(),
             schema='coco_lab.arena_world', version=1)
    return json.dumps(w, sort_keys=True, separators=(',', ':'), allow_nan=False)


# -- 3. the Nav2 map ---------------------------------------------------------------

def _merge(rects: List[Tuple[float, float, float, float]], eps: float = 1e-9):
    """Merge rectangles that share a whole edge into one, until none do."""
    rects = list(rects)
    merged = True
    while merged:
        merged = False
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                same_y = abs(a[2] - b[2]) < eps and abs(a[3] - b[3]) < eps
                same_x = abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps
                if same_y and (abs(a[1] - b[0]) < eps or abs(b[1] - a[0]) < eps):
                    rects[i] = (min(a[0], b[0]), max(a[1], b[1]), a[2], a[3])
                elif same_x and (abs(a[3] - b[2]) < eps or abs(b[3] - a[2]) < eps):
                    rects[i] = (a[0], a[1], min(a[2], b[2]), max(a[3], b[3]))
                else:
                    continue
                del rects[j]
                merged = True
                break
            if merged:
                break
    return rects


def silhouettes(spec) -> List[Tuple[float, float, float, float]]:
    """
    Return the elevated solids as a flat 2D scan sees them, world frame.

    v1: its ``ramps`` rectangles. v2/v3: where the surface stands at the LiDAR
    beam height (``Terrain.rects_above``), touching rectangles merged (a bay's
    up-wedge, platform and down-wedge are one silhouette, as in v1).
    """
    s = normalize(spec)
    if s['spec_version'] == SPEC_VERSION:
        return ramp_rectangles(s)
    t = Terrain(dict(s, world_to_map=[0.0, 0.0]))
    return _merge(t.rects_above(scan_height(s)))


def nav_map(spec, resolution: Optional[float] = None) -> LabMap:
    """Return the Nav2 map as a LabMap, MAP frame (``gen_navigation_world.py``'s rules)."""
    s = with_resolution(spec, resolution)
    b, res, m = s['bounds'], s['arena']['resolution'], s['arena']['margin']
    ox, oy = b['x_min'] - m, b['y_min'] - m
    width = round((b['x_max'] - b['x_min'] + 2 * m) / res)
    height = round((b['y_max'] - b['y_min'] + 2 * m) / res)
    occ = _rasterise(b, res, ox, oy, width, height, silhouettes(s), box_rectangles(s))
    dx, dy = s['world_to_map']
    return LabMap(width, height, bytes(occ), map_id=s['id'] + '_nav2', resolution=res,
                  origin=(ox + dx, oy + dy), frame='map', meta={'world_spec': s['id']})


def nav2_map(spec, image: str, resolution: Optional[float] = None) -> Tuple[bytes, str]:
    """Return ``(pgm_bytes, yaml_text)`` for Nav2's map_server; ``image`` names the PGM."""
    m = nav_map(spec, resolution)
    pgm = (f'P5\n{m.width} {m.height}\n255\n'.encode()
           + m.occupancy.translate(bytes(PGM_VALUE.get(i, 0) for i in range(256))))
    yaml = (f'image: {image}\nmode: trinary\nresolution: {m.resolution}\n'
            f'origin: [{m.origin[0]}, {m.origin[1]}, 0]\nnegate: 0\n'
            f'occupied_thresh: {OCCUPIED_THRESH}\nfree_thresh: {FREE_THRESH}\n')
    return pgm, yaml


def read_pgm(data: bytes) -> Tuple[int, int, bytes]:
    """Parse a binary (P5) PGM; return ``(width, height, pixels)``."""
    f = io.BytesIO(data)
    fields = []
    while len(fields) < 4:
        line = f.readline()
        if not line:
            raise ValueError('truncated PGM header')
        fields += line.split(b'#')[0].split()
    if fields[0] != b'P5' or fields[3] != b'255':
        raise ValueError('not an 8-bit binary PGM')
    w, h = int(fields[1]), int(fields[2])
    px = f.read()
    if len(px) != w * h:
        raise ValueError(f'PGM has {len(px)} pixels, expected {w * h}')
    return w, h, px


# -- 2. the Gazebo SDF world ---------------------------------------------------------

def wedge_stl(run: float, rise: float, width: float) -> bytes:
    """
    Return a binary STL right-triangular prism: the wedge, in metres.

    ``gen_ramp.py``'s frame: the foot edge on the y axis at z = 0, rising along
    +x over ``run`` to ``rise``, a vertical back face at x = run, ``width``
    centred on y = 0. Eight facets, outward normals.
    """
    hw = width / 2
    a0, b0, c0 = (0.0, -hw, 0.0), (run, -hw, 0.0), (run, -hw, rise)
    a1, b1, c1 = (0.0, hw, 0.0), (run, hw, 0.0), (run, hw, rise)
    tris = [((0, -1, 0), (a0, b0, c0)), ((0, 1, 0), (a1, c1, b1)),
            ((0, 0, -1), (a0, b1, b0)), ((0, 0, -1), (a0, a1, b1)),
            ((1, 0, 0), (b0, b1, c1)), ((1, 0, 0), (b0, c1, c0))]
    n = (-rise, 0.0, run)   # the slope: its normal points up and back toward the foot
    ln = math.hypot(n[0], n[2])
    n = (n[0] / ln, 0.0, n[2] / ln)
    tris += [(n, (a0, c0, c1)), (n, (a0, c1, a1))]
    out = bytearray(b'coco_lab.worldgen wedge'.ljust(80, b' '))
    out += struct.pack('<I', len(tris))
    for normal, verts in tris:
        out += struct.pack('<3f', *normal)
        for v in verts:
            out += struct.pack('<3f', *v)
        out += b'\x00\x00'
    return bytes(out)


def _num(v: float) -> str:
    """Format a number for SDF: Python's shortest round-trip repr, ints bare."""
    return repr(float(v)) if v != int(v) else str(int(v))


def _vec(*vs) -> str:
    return ' '.join(_num(v) for v in vs)


def _geometry(parent, shape: str, dims) -> None:
    g = ET.SubElement(ET.SubElement(parent, 'geometry'), shape)
    if shape == 'box':
        ET.SubElement(g, 'size').text = _vec(*dims)
    elif shape == 'cylinder':
        ET.SubElement(g, 'radius').text = _num(dims[0])
        ET.SubElement(g, 'length').text = _num(dims[1])
    else:   # mesh
        ET.SubElement(g, 'uri').text = dims


def _link(model, shape, dims, rgba: str, name: str = 'link'):
    link = ET.SubElement(model, 'link', name=name)
    for kind in ('collision', 'visual'):
        el = ET.SubElement(link, kind, name=kind)
        _geometry(el, shape, dims)
        if kind == 'visual':
            mat = ET.SubElement(el, 'material')
            for prop in ('ambient', 'diffuse'):
                ET.SubElement(mat, prop).text = rgba
    return link


def _model(world, name: str, pose, static: bool):
    m = ET.SubElement(world, 'model', name=name)
    ET.SubElement(m, 'static').text = 'true' if static else 'false'
    ET.SubElement(m, 'pose').text = _vec(*pose)
    return m


def _inertial(link, mass: float, ixx: float, iyy: float, izz: float) -> None:
    i = ET.SubElement(link, 'inertial')
    ET.SubElement(i, 'mass').text = _num(mass)
    t = ET.SubElement(i, 'inertia')
    for k, v in (('ixx', ixx), ('ixy', 0), ('ixz', 0), ('iyy', iyy), ('iyz', 0),
                 ('izz', izz)):
        ET.SubElement(t, k).text = _num(v)


#: object colours by catalog name (visual only)
_RGBA = {'red': '0.85 0.15 0.12 1', 'green': '0.15 0.7 0.25 1', 'blue': '0.15 0.35 0.85 1',
         'yellow': '0.95 0.8 0.1 1', 'white': '0.92 0.92 0.92 1', 'grey': '0.5 0.5 0.5 1',
         'orange': '0.95 0.5 0.1 1', 'brown': '0.5 0.33 0.18 1', 'silver': '0.75 0.75 0.78 1',
         'black': '0.1 0.1 0.1 1'}


def _object_model(world, o) -> None:
    if o['shape'] == 'cylinder':
        r, h = o['diameter'] / 2, o['height']
        dims, shape = (r, h), 'cylinder'
        izz = o['mass'] * r * r / 2
        ixx = o['mass'] * (3 * r * r + h * h) / 12
        inertia = (ixx, ixx, izz)
    else:
        sx, sy, h = o['size']
        dims, shape = (sx, sy, h), 'box'
        m = o['mass']
        inertia = (m * (sy * sy + h * h) / 12, m * (sx * sx + h * h) / 12,
                   m * (sx * sx + sy * sy) / 12)
    model = _model(world, o['id'], (o['x'], o['y'], o['z'] + h / 2, 0, 0, o['yaw']), False)
    link = _link(model, shape, dims, _RGBA.get(o['colour'], _RGBA['grey']))
    _inertial(link, o['mass'], *inertia)


def _actor_model(world, a) -> None:
    x, y, yaw = v3.actor_pose(a, 0.0)
    length, width = a['footprint']
    model = _model(world, a['id'], (x, y, 0, 0, 0, yaw), False)
    link = _link(model, 'box', (length, width, a['height']),
                 '0.95 0.6 0.1 1' if a['actor'] == 'forklift' else '0.3 0.6 0.9 1',
                 name='body')
    for el in link.findall('collision') + link.findall('visual'):
        p = ET.Element('pose')
        p.text = _vec(0, 0, a['height'] / 2, 0, 0, 0)
        el.insert(0, p)
    # moved by set_pose (actors.json), never by physics: no gravity, kinematic
    ET.SubElement(link, 'gravity').text = 'false'
    ET.SubElement(link, 'kinematic').text = 'true'


def sdf_world(spec, template: str, world_name: Optional[str] = None,
              mesh_dir: str = 'meshes', objects: bool = True
              ) -> Tuple[str, Dict[str, bytes]]:
    """
    Return ``(sdf_text, files)``: the level as a Gazebo world, and its side files.

    ``template`` is an SDF world (the Stack's ``coco_navigation.world``): its
    physics, systems, lights, scene and ``ground_plane`` are kept and every
    other model removed; the ground plane grows, centred on the bounds, only
    if it does not already cover them and their margin. ``files`` maps
    relative paths to bytes: one STL per wedge (``<mesh_dir>/<id>.stl``) and,
    on v3, ``actors.json`` (the actors' kinematic schedule).
    """
    s = normalize(spec)
    root = ET.fromstring(_strip_comments(template))
    world = root.find('world')
    if world is None:
        raise ValueError('template: no <world>')
    if world_name:
        world.set('name', world_name)
    for model in list(world.findall('model')):
        if model.get('name') != 'ground_plane':
            world.remove(model)
        else:
            _fit_ground(model, s)
    files: Dict[str, bytes] = {}
    for bx in s['boxes']:
        (x, y), (sx, sy) = bx['center'], bx['size']
        _link(_model(world, bx['id'], (x, y, bx['z'], 0, 0, 0), True), 'box',
              (sx, sy, bx['height']), BOX_RGBA)
    for e in s.get('elevation', []):
        if e['kind'] == 'wedge':
            path = f'{mesh_dir}/{e["id"]}.stl'
            files[path] = wedge_stl(e['run'], e['rise'], e['width'])
            _link(_model(world, e['id'], (e['foot'][0], e['foot'][1], 0, 0, 0, e['yaw']),
                         True), 'mesh', path, BOX_RGBA)
        else:
            (cx, cy), (sx, sy, sz) = e['center'], e['size']
            _link(_model(world, e['id'], (cx, cy, sz / 2, 0, 0, 0), True), 'box',
                  (sx, sy, sz), BOX_RGBA)
    if v3.is_v3(s):
        if objects:
            for o in v3.objects(s):
                _object_model(world, o)
        actors = v3.elements(s, 'actor')
        for a in actors:
            _actor_model(world, a)
        files['actors.json'] = (json.dumps(
            {'schema': 'coco_lab.actor_schedule', 'version': 1, 'world_spec': s['id'],
             'frame': 'world', 'actors': actors}, sort_keys=True, indent=1) + '\n').encode()
    ET.indent(root, space='  ')
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            + ET.tostring(root, encoding='unicode') + '\n'), files


def object_sdf(spec, object_id: str) -> str:
    """Return one object as a standalone, spawnable SDF model (``/world/<w>/create``)."""
    s = normalize(spec)
    o = next(x for x in v3.objects(s) if x['id'] == object_id)
    root = ET.Element('sdf', version='1.8')
    _object_model(root, o)
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='unicode') + '\n'


def _strip_comments(text: str) -> str:
    out, i = [], 0
    while True:
        j = text.find('<!--', i)
        if j < 0:
            out.append(text[i:])
            return ''.join(out)
        out.append(text[i:j])
        i = text.index('-->', j) + 3


def _fit_ground(model, s) -> None:
    b, m = s['bounds'], s['arena']['margin']
    need = (b['x_min'] - m, b['x_max'] + m, b['y_min'] - m, b['y_max'] + m)
    pose = model.find('pose')
    px, py = (0.0, 0.0) if pose is None else tuple(float(v) for v in pose.text.split()[:2])
    for size in model.findall('.//plane/size'):
        sx, sy = (float(v) for v in size.text.split())
        if px - sx / 2 <= need[0] and need[1] <= px + sx / 2 \
                and py - sy / 2 <= need[2] and need[3] <= py + sy / 2:
            continue
        cx, cy = (need[0] + need[1]) / 2, (need[2] + need[3]) / 2
        size.text = _vec(need[1] - need[0], need[3] - need[2])
        if pose is None:
            pose = ET.SubElement(model, 'pose')
        pose.text = _vec(cx, cy, 0, 0, 0, 0)


# -- reading an SDF world back ------------------------------------------------------

def sdf_footprints(sdf_text: str) -> Dict[str, Dict[str, object]]:
    """
    Parse an SDF world back to each model's collision geometry, world frame.

    For the round-trip test and the Proving Ground comparison: ``{name: {
    'pose': [x, y, z, roll, pitch, yaw], 'static': bool, 'shape': 'box' |
    'cylinder' | 'mesh' | 'plane', 'dims': [...] or uri, 'offset': [...]}}``
    (the first collision of the first link; ``offset`` its pose in the link).
    """
    root = ET.fromstring(_strip_comments(sdf_text))
    out = {}
    for model in root.iter('model'):
        pose = model.find('pose')
        p = [0.0] * 6 if pose is None else [float(v) for v in pose.text.split()]
        col = model.find('link/collision')
        if col is None:
            continue
        g = col.find('geometry')
        shape = g[0].tag
        if shape == 'box':
            dims = [float(v) for v in g[0].find('size').text.split()]
        elif shape == 'cylinder':
            dims = [float(g[0].find('radius').text), float(g[0].find('length').text)]
        elif shape == 'mesh':
            dims = g[0].find('uri').text
        else:
            dims = [float(v) for v in g[0].find('size').text.split()] \
                if g[0].find('size') is not None else []
        cp = col.find('pose')
        static = model.find('static')
        out[model.get('name')] = {
            'pose': p, 'static': static is not None and static.text.strip() == 'true',
            'shape': shape, 'dims': dims,
            'offset': [0.0] * 6 if cp is None else [float(v) for v in cp.text.split()]}
    return out


def read_stl(data: bytes) -> List[Tuple[Tuple[float, float, float], ...]]:
    """Parse a binary STL into its triangles' vertices."""
    (n,) = struct.unpack_from('<I', data, 80)
    tris = []
    for k in range(n):
        vals = struct.unpack_from('<12f', data, 84 + 50 * k)
        tris.append(tuple(tuple(vals[3 + 3 * i:6 + 3 * i]) for i in range(3)))
    return tris
