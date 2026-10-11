# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
COCO's robot, URDF -> glTF (M4.1, first conversion; README §5.4).

  python3 lab_web/tools/assets/convert_robot.py OUT_DIR

Expands `gazebo_models/urdf/coco_robo2.xacro` (read-only; ROS's xacro), reads
its links, joints, visuals and materials, and writes two levels of detail,
`robot_high.glb` and `robot_low.glb`, with the joint hierarchy kept:

  coco (root: ROS z-up -> glTF y-up)
    link:base_footprint
      joint:<name>          the joint's fixed origin (URDF <origin>)
        q:<name>            identity; the renderer rotates it about extras.axis
          link:<child>      the child link and its visuals

Meshes come from `gazebo_models/meshes/*.stl` (millimetres, scaled by the
URDF), decimated by vertex clustering to the level's triangle budget, shared
between the budget's meshes in proportion to their source triangles. Every
number the conversion used is printed and written to OUT_DIR/robot.json.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from glb import GLB, rpy_to_quat  # noqa: E402
import mesh as M  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
XACRO = os.path.join(REPO, 'gazebo_models', 'urdf', 'coco_robo2.xacro')
MESHES = os.path.join(REPO, 'gazebo_models', 'meshes')
LEVELS = {'high': 20000, 'low': 4500}   # README §5.4: ~20k near the camera, well under 5k for phones
Z_UP_TO_Y_UP = rpy_to_quat(-np.pi / 2, 0, 0)


def urdf_xml():
    """Expand the xacro. Its one `$(find gazebo_models)` (ros2_control's parameter file,
    irrelevant to visuals) is pointed at this repository, so no ament path is consulted --
    an inherited AMENT_PREFIX_PATH can name unrelated workspaces (CLAUDE.md)."""
    sys.path.insert(0, '/opt/ros/jazzy/lib/python3.12/site-packages')
    import xacro  # noqa: E402
    text = open(XACRO).read().replace('$(find gazebo_models)', os.path.join(REPO, 'gazebo_models'))
    doc = xacro.parse(text)
    xacro.process_doc(doc)
    return doc.toxml()


def vec(s, n=3, default=0.0):
    return [float(x) for x in s.split()] if s else [default] * n


def origin(el):
    o = el.find('origin') if el is not None else None
    return (vec(o.get('xyz')), vec(o.get('rpy'))) if o is not None else ([0.0] * 3, [0.0] * 3)


def cylinder(radius, length, n=24):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([radius * np.cos(a), radius * np.sin(a)], axis=1)
    v = np.concatenate([np.c_[ring, np.full(n, -length / 2)], np.c_[ring, np.full(n, length / 2)],
                        [[0, 0, -length / 2], [0, 0, length / 2]]])
    t = []
    for i in range(n):
        j = (i + 1) % n
        t += [(i, j, n + j), (i, n + j, n + i), (2 * n, j, i), (2 * n + 1, n + i, n + j)]
    return v, np.array(t)


def geometry(g):
    """(V, T, source-triangle-count, description) for one URDF <geometry>."""
    if g.find('mesh') is not None:
        m = g.find('mesh')
        fn = m.get('filename').replace('package://gazebo_models/meshes', MESHES)
        v, t = M.read_stl(fn)
        v = v * np.array(vec(m.get('scale'), default=1.0))
        return v, t, os.path.basename(fn)
    if g.find('box') is not None:
        p, _, t = M.box(vec(g.find('box').get('size')))
        return p, t, 'box'
    if g.find('cylinder') is not None:
        c = g.find('cylinder')
        v, t = cylinder(float(c.get('radius')), float(c.get('length')))
        return v, t, 'cylinder'
    if g.find('sphere') is not None:
        r = float(g.find('sphere').get('radius'))
        v, t = cylinder(r, 2 * r, 12)
        return v, t, 'sphere(as cylinder)'
    raise ValueError('unknown geometry')


def build(level_tris, root, colours, report):
    links = {lk.get('name'): lk for lk in root.findall('link')}
    joints = root.findall('joint')
    children = {}
    for j in joints:
        children.setdefault(j.find('parent').get('link'), []).append(j)
    child_links = {j.find('child').get('link') for j in joints}
    base = [n for n in links if n not in child_links][0]
    # every visual, its source triangles, so the budget can be shared
    visuals = []
    for name, lk in links.items():
        for k, vis in enumerate(lk.findall('visual')):
            v, t, src = geometry(vis.find('geometry'))
            mat = vis.find('material')
            visuals.append((name, k, vis, v, t, src, mat.get('name') if mat is not None else None))
    # water-filling: a mesh under the fair share keeps every triangle; the rest share what is left equally
    sizes = sorted(x[4].shape[0] for x in visuals)
    left, n_left, cap = level_tris, len(sizes), None
    for s in sizes:
        if s * n_left <= left:
            left -= s
            n_left -= 1
        else:
            cap = left // n_left
            break
    g = GLB()
    vis_nodes = {}
    for name, k, vis, v, t, src, matname in visuals:
        share = t.shape[0] if cap is None else min(t.shape[0], cap)
        dv, dt, cell = M.decimate_to(v, t, share)
        p, n, i = M.smooth(dv, dt)
        xyz, rpy = origin(vis)
        rgba = colours.get(matname, (0.6, 0.6, 0.6, 1))
        mi = g.material(matname or 'default', rgba, 0.0, 0.7)
        mesh = g.mesh(f'{name}:{k}', p, n, i, mi)
        node = g.node(f'visual:{name}:{k}', mesh=mesh, translation=xyz, rotation=rpy_to_quat(*rpy))
        vis_nodes.setdefault(name, []).append(node)
        report.append({'link': name, 'visual': k, 'source': src, 'source_tris': int(t.shape[0]),
                       'tris': int(dt.shape[0]), 'cluster_cell_m': round(cell, 6)})

    def link_node(name):
        kids = list(vis_nodes.get(name, []))
        for j in children.get(name, []):
            jn = j.get('name')
            xyz, rpy = origin(j)
            axis = vec(j.find('axis').get('xyz')) if j.find('axis') is not None else [1.0, 0.0, 0.0]
            lim = j.find('limit')
            extras = {'joint': jn, 'type': j.get('type'), 'axis': axis}
            if lim is not None and lim.get('lower') is not None:
                extras['limits'] = [float(lim.get('lower')), float(lim.get('upper'))]
            q = g.node(f'q:{jn}', children=[link_node(j.find('child').get('link'))], extras=extras)
            kids.append(g.node(f'joint:{jn}', translation=xyz, rotation=rpy_to_quat(*rpy), children=[q]))
        return g.node(f'link:{name}', children=kids)

    top = link_node(base)
    g.node('coco', rotation=Z_UP_TO_Y_UP, children=[top], root=True,
           extras={'frame': 'base_footprint; ROS z-up, rotated to glTF y-up at this node'})
    return g


def main(out):
    os.makedirs(out, exist_ok=True)
    root = ET.fromstring(urdf_xml())
    colours = {}
    for m in root.iter('material'):
        c = m.find('color')
        if c is not None and m.get('name'):
            colours[m.get('name')] = vec(c.get('rgba'), 4)
    summary = {'source': os.path.relpath(XACRO, REPO), 'meshes_dir': os.path.relpath(MESHES, REPO), 'levels': {}}
    for level, budget in LEVELS.items():
        report = []
        g = build(budget, root, colours, report)
        data = g.bytes(extras={'source': summary['source'], 'level': level, 'triangle_budget': budget})
        path = os.path.join(out, f'robot_{level}.glb')
        open(path, 'wb').write(data)
        summary['levels'][level] = {'file': os.path.basename(path), 'bytes': len(data), 'triangles': g.triangles(),
                                    'budget': budget, 'visuals': report}
        print(f'robot_{level}.glb: {len(data):,} B, {g.triangles():,} triangles (budget {budget:,})')
    json.dump(summary, open(os.path.join(out, 'robot.json'), 'w'), indent=1, sort_keys=True)


if __name__ == '__main__':
    main(sys.argv[1])
