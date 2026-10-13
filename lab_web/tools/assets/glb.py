# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
A small, deterministic glTF 2.0 binary (GLB) writer (M4.1, M4.2). Standard
library only, so it runs wherever the site's tools do (CI has no numpy).

Only what COCO's converted assets need: triangle meshes (POSITION, optional
NORMAL, uint32 indices), metallic-roughness materials with a base colour,
and a node hierarchy with translation / rotation (quaternion xyzw) and
`extras`. No timestamps or random ids: the same input gives the same bytes.
These are the SOURCE files of the pipeline (ADR 0006); compress.mjs turns
them into what the site serves.
"""

import json
import math
import struct
from array import array

FLOAT, UINT32 = 5126, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963


class GLB:
    def __init__(self, generator='coco-labs lab_web/tools/assets/glb.py'):
        self.j = {'asset': {'version': '2.0', 'generator': generator}, 'scene': 0,
                  'scenes': [{'nodes': []}], 'nodes': [], 'meshes': [], 'materials': [],
                  'accessors': [], 'bufferViews': [], 'buffers': []}
        self.bin = bytearray()
        self._materials = {}

    def _view(self, data: bytes, target):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.j['bufferViews'].append({'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data), 'target': target})
        self.bin.extend(data)
        return len(self.j['bufferViews']) - 1

    def _vec3(self, flat):
        a = array('f', flat)
        acc = {'bufferView': self._view(a.tobytes(), ARRAY_BUFFER), 'componentType': FLOAT,
               'count': len(a) // 3, 'type': 'VEC3'}
        self.j['accessors'].append(acc)
        return acc, len(self.j['accessors']) - 1

    def material(self, name, rgba, metallic=0.0, roughness=0.85):
        rgba = [round(float(c), 4) for c in rgba]
        key = (name, tuple(rgba), metallic, roughness)
        if key in self._materials:
            return self._materials[key]
        self.j['materials'].append({'name': name, 'pbrMetallicRoughness': {
            'baseColorFactor': rgba, 'metallicFactor': metallic, 'roughnessFactor': roughness}})
        self._materials[key] = len(self.j['materials']) - 1
        return self._materials[key]

    def mesh(self, name, positions, indices, material, normals=None, extras=None):
        """One triangle primitive. positions (and normals): flat [x, y, z, ...]; indices: flat."""
        acc, pi = self._vec3(positions)
        p = array('f', positions)
        acc['min'] = [min(p[k::3]) for k in range(3)]
        acc['max'] = [max(p[k::3]) for k in range(3)]
        attrs = {'POSITION': pi}
        if normals is not None:
            attrs['NORMAL'] = self._vec3(normals)[1]
        ia = array('I', indices)
        self.j['accessors'].append({'bufferView': self._view(ia.tobytes(), ELEMENT_ARRAY_BUFFER),
                                    'componentType': UINT32, 'count': len(ia), 'type': 'SCALAR'})
        prim = {'attributes': attrs, 'indices': len(self.j['accessors']) - 1, 'material': material, 'mode': 4}
        m = {'name': name, 'primitives': [prim]}
        if extras:
            m['extras'] = extras
        self.j['meshes'].append(m)
        return len(self.j['meshes']) - 1

    def node(self, name, mesh=None, translation=None, rotation=None, children=(), extras=None, root=False):
        nd = {'name': name}
        if mesh is not None:
            nd['mesh'] = mesh
        if translation is not None and any(abs(v) > 0 for v in translation):
            nd['translation'] = [float(v) for v in translation]
        if rotation is not None and any(abs(v) > 1e-12 for v in rotation[:3]):
            nd['rotation'] = [float(v) for v in rotation]
        if children:
            nd['children'] = list(children)
        if extras:
            nd['extras'] = extras
        self.j['nodes'].append(nd)
        k = len(self.j['nodes']) - 1
        if root:
            self.j['scenes'][0]['nodes'].append(k)
        return k

    def bytes(self, extras=None) -> bytes:
        while len(self.bin) % 4:
            self.bin.append(0)
        j = dict(self.j)
        j['buffers'] = [{'byteLength': len(self.bin)}]
        if extras:
            j['extras'] = extras
        js = json.dumps(j, sort_keys=True, separators=(',', ':')).encode()
        js += b' ' * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        return (struct.pack('<4sII', b'glTF', 2, total) + struct.pack('<I4s', len(js), b'JSON') + js
                + struct.pack('<I4s', len(self.bin), b'BIN\x00') + bytes(self.bin))


def rpy_to_quat(r, p, y):
    """URDF / SDF fixed-axis roll-pitch-yaw to a quaternion (x, y, z, w)."""
    cr, sr = math.cos(r / 2), math.sin(r / 2)
    cp, sp = math.cos(p / 2), math.sin(p / 2)
    cy, sy = math.cos(y / 2), math.sin(y / 2)
    return [sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy]
