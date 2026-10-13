# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Triangle meshes for the asset converters (M4.2): read STL and weld it, boxes,
rigid transforms, flat normals. Standard library only (CI has no numpy).

A mesh here is (positions, indices): a flat list [x0, y0, z0, x1, ...] and a
flat list of vertex indices, three per triangle. Simplification and
smooth normals happen later, in compress.mjs (meshoptimizer; ADR 0006).
"""

import math
import struct


def read_stl(path, scale=(1.0, 1.0, 1.0)):
    """A binary or ASCII STL, welded on exact coordinates: (positions, indices)."""
    data = open(path, 'rb').read()
    n = struct.unpack_from('<I', data, 80)[0] if len(data) >= 84 else -1
    if len(data) == 84 + 50 * n:
        corners = []
        for k in range(n):
            v = struct.unpack_from('<9f', data, 84 + 50 * k + 12)
            corners += [v[0:3], v[3:6], v[6:9]]
    else:
        corners = [tuple(map(float, ln.split()[1:4])) for ln in data.decode('ascii', 'replace').splitlines()
                   if ln.strip().startswith('vertex')]
    index, pos, ind = {}, [], []
    sx, sy, sz = scale
    for c in corners:
        k = index.get(c)
        if k is None:
            k = index[c] = len(pos) // 3
            pos += [c[0] * sx, c[1] * sy, c[2] * sz]
        ind.append(k)
    # drop triangles that welding made degenerate
    out = []
    for t in range(0, len(ind), 3):
        a, b, c = ind[t:t + 3]
        if a != b and b != c and a != c:
            out += [a, b, c]
    return pos, out


def box(size):
    """An axis-aligned box centred on the origin: 24 vertices (crisp faces), normals, 12 triangles."""
    sx, sy, sz = (s / 2 for s in size)
    faces = [((1, 0, 0), [(sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz), (sx, -sy, sz)]),
             ((-1, 0, 0), [(-sx, sy, -sz), (-sx, -sy, -sz), (-sx, -sy, sz), (-sx, sy, sz)]),
             ((0, 1, 0), [(sx, sy, -sz), (-sx, sy, -sz), (-sx, sy, sz), (sx, sy, sz)]),
             ((0, -1, 0), [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz)]),
             ((0, 0, 1), [(-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]),
             ((0, 0, -1), [(-sx, sy, -sz), (sx, sy, -sz), (sx, -sy, -sz), (-sx, -sy, -sz)])]
    p, n, t = [], [], []
    for nrm, quad in faces:
        k = len(p) // 3
        for q in quad:
            p += list(q)
            n += list(nrm)
        t += [k, k + 1, k + 2, k, k + 2, k + 3]
    return p, n, t


def flat(positions, indices):
    """Unweld for flat shading: each triangle its own three vertices and its face normal."""
    p, n, t = [], [], []
    for k in range(0, len(indices), 3):
        a, b, c = (positions[3 * i:3 * i + 3] for i in indices[k:k + 3])
        u = [b[j] - a[j] for j in range(3)]
        v = [c[j] - a[j] for j in range(3)]
        f = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        ln = math.sqrt(sum(x * x for x in f)) or 1.0
        f = [x / ln for x in f]
        base = len(p) // 3
        p += a + b + c
        n += f * 3
        t += [base, base + 1, base + 2]
    return p, n, t


def rot_rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr]]


def transform(positions, normals, xyz, rpy):
    """Apply a rigid transform (fixed-axis rpy, then translate) to flat point and normal lists."""
    R = rot_rpy(*rpy)

    def rot(flat_, add):
        out = []
        for k in range(0, len(flat_), 3):
            x, y, z = flat_[k:k + 3]
            out += [R[i][0] * x + R[i][1] * y + R[i][2] * z + add[i] for i in range(3)]
        return out

    return rot(positions, list(xyz)), (rot(normals, [0.0, 0.0, 0.0]) if normals is not None else None)
