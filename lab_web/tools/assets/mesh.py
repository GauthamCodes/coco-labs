# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Triangle meshes for the asset converters (M4.1): read STL, weld, decimate by
vertex clustering, normals, boxes, and rigid transforms. numpy only.

Vertex clustering (Rossignac-Borrel) snaps every vertex to a grid of cell
`cell` metres and merges what lands together; it is crude but deterministic
and fast, and enough for M4.1's first conversion. M4.2's pipeline replaces
it (docs/v2/adr/0006-asset-pipeline.md).
"""

import struct

import numpy as np


def read_stl(path):
    """Return (V, 3) float64 vertices and (T, 3) int triangles, welded exactly."""
    data = open(path, 'rb').read()
    n = struct.unpack_from('<I', data, 80)[0] if len(data) >= 84 else 0
    if len(data) == 84 + 50 * n:
        rec = np.frombuffer(data, dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), count=n, offset=84)
        tri = rec['v'].reshape(-1, 3).astype(np.float64)
    else:  # ASCII
        vs = [list(map(float, ln.split()[1:4])) for ln in data.decode('ascii', 'replace').splitlines()
              if ln.strip().startswith('vertex')]
        tri = np.array(vs, dtype=np.float64)
    v, inv = np.unique(tri, axis=0, return_inverse=True)
    return v, inv.reshape(-1, 3)


def cluster(v, t, cell):
    """Vertex-clustering decimation at `cell` metres. Returns (V', T')."""
    if cell <= 0:
        return v, t
    key = np.floor(v / cell).astype(np.int64)
    _, rep, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    # each cluster's vertex: the mean of its members
    nv = np.zeros((rep.shape[0], 3))
    np.add.at(nv, inv, v)
    nv /= np.bincount(inv, minlength=rep.shape[0])[:, None]
    nt = inv[t]
    keep = (nt[:, 0] != nt[:, 1]) & (nt[:, 1] != nt[:, 2]) & (nt[:, 0] != nt[:, 2])
    nt = nt[keep]
    # drop duplicate triangles (same three vertices, any order)
    s = np.sort(nt, axis=1)
    _, first = np.unique(s, axis=0, return_index=True)
    nt = nt[np.sort(first)]
    used = np.unique(nt)
    remap = -np.ones(nv.shape[0], np.int64)
    remap[used] = np.arange(used.shape[0])
    return nv[used], remap[nt]


def decimate_to(v, t, max_tris, start_cell=0.0005):
    """Grow the cluster cell until the mesh has at most `max_tris` triangles."""
    if t.shape[0] <= max_tris:
        return v, t, 0.0
    cell = start_cell
    while True:
        nv, nt = cluster(v, t, cell)
        if nt.shape[0] <= max_tris:
            return nv, nt, cell
        cell *= 1.25


def flat(v, t):
    """Unweld for flat shading: each triangle its own three vertices and face normal."""
    p = v[t].reshape(-1, 3)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    fn = np.cross(b - a, c - a)
    ln = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = np.divide(fn, ln, out=np.zeros_like(fn), where=ln > 0)
    return p, np.repeat(fn, 3, axis=0), np.arange(p.shape[0])


def smooth(v, t, crease_deg=40.0):
    """Normals smoothed across edges flatter than `crease_deg`, split where sharper (CAD edges stay crisp)."""
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    fn = np.cross(b - a, c - a)
    ln = np.linalg.norm(fn, axis=1, keepdims=True)
    fnu = np.divide(fn, ln, out=np.zeros_like(fn), where=ln > 0)
    # per corner: the area-weighted mean of the faces at that vertex whose normal is within the crease
    acc = np.zeros((v.shape[0], 3))
    np.add.at(acc, t.reshape(-1), np.repeat(fn, 3, axis=0))
    vn = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-12)
    corner_face = np.repeat(fnu, 3, axis=0)
    corner_vn = vn[t.reshape(-1)]
    sharp = (corner_face * corner_vn).sum(axis=1) < np.cos(np.radians(crease_deg))
    n = np.where(sharp[:, None], corner_face, corner_vn)
    # corners that disagree with their vertex's normal get their own vertex
    key = np.concatenate([t.reshape(-1)[:, None].astype(np.float64), np.round(n, 3)], axis=1)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    p = v[t.reshape(-1)][first]
    return p, n[first], inv.reshape(-1)


def box(size):
    """An axis-aligned box centred on the origin: (V, 3), (T, 3), 24 vertices for crisp faces."""
    sx, sy, sz = (s / 2 for s in size)
    faces = [((1, 0, 0), [(sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz), (sx, -sy, sz)]),
             ((-1, 0, 0), [(-sx, sy, -sz), (-sx, -sy, -sz), (-sx, -sy, sz), (-sx, sy, sz)]),
             ((0, 1, 0), [(sx, sy, -sz), (-sx, sy, -sz), (-sx, sy, sz), (sx, sy, sz)]),
             ((0, -1, 0), [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz)]),
             ((0, 0, 1), [(-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]),
             ((0, 0, -1), [(-sx, sy, -sz), (sx, sy, -sz), (sx, -sy, -sz), (-sx, -sy, -sz)])]
    p, n, t = [], [], []
    for nrm, quad in faces:
        k = len(p)
        p += quad
        n += [nrm] * 4
        t += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    return np.array(p, float), np.array(n, float), np.array(t, np.int64)


def rot_rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx


def transform(p, n, xyz, rpy):
    """Apply a rigid transform (fixed-axis rpy, then translate) to points and normals."""
    R = rot_rpy(*rpy)
    return p @ R.T + np.asarray(xyz, float), n @ R.T
