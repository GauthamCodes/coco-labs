# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
A small, deterministic glTF 2.0 binary (GLB) writer (M4.1).

Only what COCO's converted assets need: triangle meshes (POSITION, NORMAL,
uint32 or uint16 indices), metallic-roughness materials with a base colour,
and a node hierarchy with translation / rotation (quaternion xyzw) and
`extras`. No timestamps or random ids: the same input gives the same bytes,
so an asset's checksum is a property of its source.
"""

import json
import struct

import numpy as np

FLOAT, UINT16, UINT32 = 5126, 5123, 5125
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

    def _accessor(self, arr: np.ndarray, kind: str, target, minmax=False):
        ctype = {np.dtype('float32'): FLOAT, np.dtype('uint16'): UINT16, np.dtype('uint32'): UINT32}[arr.dtype]
        acc = {'bufferView': self._view(np.ascontiguousarray(arr).tobytes(), target), 'componentType': ctype,
               'count': int(arr.shape[0]), 'type': kind}
        if minmax:
            acc['min'] = [float(v) for v in arr.min(axis=0)]
            acc['max'] = [float(v) for v in arr.max(axis=0)]
        self.j['accessors'].append(acc)
        return len(self.j['accessors']) - 1

    def material(self, name, rgba, metallic=0.0, roughness=0.85):
        key = (name, tuple(round(float(c), 4) for c in rgba), metallic, roughness)
        if key in self._materials:
            return self._materials[key]
        self.j['materials'].append({'name': name, 'pbrMetallicRoughness': {
            'baseColorFactor': [round(float(c), 4) for c in rgba], 'metallicFactor': metallic, 'roughnessFactor': roughness}})
        self._materials[key] = len(self.j['materials']) - 1
        return self._materials[key]

    def mesh(self, name, positions, normals, indices, material):
        """One triangle primitive. positions, normals: (N, 3); indices: (M,) or (M/3, 3)."""
        p = np.asarray(positions, np.float32).reshape(-1, 3)
        n = np.asarray(normals, np.float32).reshape(-1, 3)
        i = np.asarray(indices).reshape(-1)
        i = i.astype(np.uint16 if p.shape[0] < 65536 else np.uint32)
        prim = {'attributes': {'POSITION': self._accessor(p, 'VEC3', ARRAY_BUFFER, minmax=True),
                               'NORMAL': self._accessor(n, 'VEC3', ARRAY_BUFFER)},
                'indices': self._accessor(i, 'SCALAR', ELEMENT_ARRAY_BUFFER), 'material': material, 'mode': 4}
        self.j['meshes'].append({'name': name, 'primitives': [prim]})
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

    def triangles(self) -> int:
        n = 0
        for m in self.j['meshes']:
            for p in m['primitives']:
                n += self.j['accessors'][p['indices']]['count'] // 3
        return n


def rpy_to_quat(r, p, y):
    """URDF / SDF fixed-axis roll-pitch-yaw to a quaternion (x, y, z, w)."""
    cr, sr = np.cos(r / 2), np.sin(r / 2)
    cp, sp = np.cos(p / 2), np.sin(p / 2)
    cy, sy = np.cos(y / 2), np.sin(y / 2)
    return [sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy]
