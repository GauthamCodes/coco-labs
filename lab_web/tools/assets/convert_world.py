# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
COCO's arena, Gazebo SDF -> glTF (M4.1, first conversion; README §5.1, D3).

  python3 lab_web/tools/assets/convert_world.py OUT_DIR

The scene the Case File recordings were made in (Labs 1, 4 and 5 ran
`full_world_robo.launch.py traverse:=true` on the default world; Lab 1C's run
metadata records its sha256, which this checks):

- `gazebo_models/worlds/coco_navigation.world` (read-only): the ground and
  70 static boxes (walls, obstacles, landmarks, bay guards);
- what the launch file spawns with `traverse:=true`, at its default 18°
  grade, from the same constants (`coco_config.robot`): in each of the four
  bays an up-wedge (`ramp.sdf`, `meshes/ramp_wedge_18.stl`) with its foot at
  RAMP_FOOT_X, a flat platform box at the crest, and a mirrored down-wedge.

Targets, actors and the robot are not part of the static world (they move or
change per episode). Geometry stays in the Gazebo WORLD frame; the renderer
places it in the map frame with the World Spec's `world_to_map`. One GLB,
`arena.glb`, one mesh per kind; `arena.json` lists every footprint, which
M4.2's World Spec <-> SDF check compares against.
"""

import hashlib
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from glb import GLB, rpy_to_quat  # noqa: E402
import mesh as M  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_config'))
from coco_config.robot import (PLATFORM_LEN, RAMP_ANGLE_DEG, RAMP_FOOT_X, RAMP_RUN,  # noqa: E402
                               RAMP_SUMMIT_X, RAMP_WIDTH, TARGETS)

WORLD = os.path.join(REPO, 'gazebo_models', 'worlds', 'coco_navigation.world')
RAMP_SDF = os.path.join(REPO, 'gazebo_models', 'urdf', 'ramp.sdf')
MESHES = os.path.join(REPO, 'gazebo_models', 'meshes')
#: the world file the recordings ran (docs/data/lab1c/runs/*/meta.json "world")
RECORDED_WORLD_SHA256 = 'cbe9415ab6b029c759a4dcceb67042b70e73d0569e2d98391bca5921a54d58bd'
Z_UP_TO_Y_UP = rpy_to_quat(-np.pi / 2, 0, 0)


def vec(s, n=3):
    return [float(x) for x in s.split()] if s is not None and s.strip() else [0.0] * n


def kind_of(name):
    for k in ('wall_', 'landmark', 'guard', 'column', 'approach', 'spine', 'room', 'offset', 'dead_end', 'cluster'):
        if k in name:
            return {'wall_': 'walls', 'landmark': 'landmarks', 'guard': 'bay_guards', 'column': 'bay_columns',
                    'approach': 'bay_approaches'}.get(k, 'obstacles')
    return 'obstacles'


def main(out):
    os.makedirs(out, exist_ok=True)
    sha = hashlib.sha256(open(WORLD, 'rb').read()).hexdigest()
    if sha != RECORDED_WORLD_SHA256:
        raise SystemExit(f'{WORLD} is not the world the recordings ran ({sha[:12]} != {RECORDED_WORLD_SHA256[:12]})')
    w = ET.parse(WORLD).getroot().find('world')
    parts = {}          # kind -> [(P, N, T)]
    footprints = []
    ground = None
    for m in w.findall('model'):
        mxyz_rpy = vec(m.findtext('pose'), 6)
        for lk in m.findall('link'):
            lp = vec(lk.findtext('pose'), 6)
            for v in lk.findall('visual'):
                vp = vec(v.findtext('pose'), 6)
                g = v.find('geometry')
                if g.find('plane') is not None:
                    ground = (vec(g.find('plane').findtext('size'), 2), vec(v.findtext('material/diffuse'), 4))
                    continue
                if g.find('box') is None:
                    raise SystemExit(f'{m.get("name")}: only boxes and the plane are expected')
                size = vec(g.find('box').findtext('size'))
                if any(abs(a) > 1e-9 for a in lp + vp[:6]):
                    raise SystemExit(f'{m.get("name")}: link/visual poses are not expected in this world')
                p, n, t = M.box(size)
                p, n = M.transform(p, n, mxyz_rpy[:3], mxyz_rpy[3:])
                parts.setdefault(kind_of(m.get('name')), []).append((p, n, t))
                footprints.append({'name': m.get('name'), 'kind': kind_of(m.get('name')), 'center': mxyz_rpy[:3],
                                   'yaw': mxyz_rpy[5], 'size': size})
    # traverse:=true, as full_world_robo.launch.py spawns it
    rise = RAMP_RUN * math.tan(math.radians(RAMP_ANGLE_DEG))
    plat_x = RAMP_SUMMIT_X + PLATFORM_LEN / 2.0
    far_foot = RAMP_SUMMIT_X + PLATFORM_LEN + RAMP_RUN
    ramp = ET.parse(RAMP_SDF).getroot().find('model/link/visual')
    wedge_file = ramp.findtext('geometry/mesh/uri').replace('package://gazebo_models/meshes', MESHES).replace(
        'ramp_wedge_18.stl', f'ramp_wedge_{RAMP_ANGLE_DEG}.stl')
    wv, wt = M.read_stl(wedge_file)
    wp, wn, wi = M.flat(wv, wt)
    ramp_rgba = vec(ramp.findtext('material/diffuse'), 4)
    for tg in TARGETS:
        y = tg.lane_y
        for (x, yaw, what) in ((RAMP_FOOT_X, 0.0, 'ramp_up'), (far_foot, math.pi, 'ramp_down')):
            p, n = M.transform(wp, wn, (x, y, 0.0), (0, 0, yaw))
            parts.setdefault('ramps', []).append((p, n, wi.reshape(-1, 3)))
            footprints.append({'name': f'{what}_{tg.colour}', 'kind': 'ramps', 'foot': [x, y, 0.0], 'yaw': yaw,
                               'run': RAMP_RUN, 'width': RAMP_WIDTH, 'rise': rise})
        p, n, t = M.box((PLATFORM_LEN, RAMP_WIDTH, rise))
        p, n = M.transform(p, n, (plat_x, y, rise / 2.0), (0, 0, 0))
        parts.setdefault('platforms', []).append((p, n, t))
        footprints.append({'name': f'ramp_platform_{tg.colour}', 'kind': 'platforms', 'center': [plat_x, y, rise / 2.0],
                           'yaw': 0.0, 'size': [PLATFORM_LEN, RAMP_WIDTH, rise]})
    g = GLB()
    wall_rgba = [0.55, 0.55, 0.57, 1]
    kids = []
    for kind in sorted(parts):
        P = np.concatenate([x[0] for x in parts[kind]])
        N = np.concatenate([x[1] for x in parts[kind]])
        off, T = 0, []
        for p, _, t in parts[kind]:
            T.append(t + off)
            off += p.shape[0]
        rgba = ramp_rgba if kind in ('ramps', 'platforms') else wall_rgba
        mat = g.material(kind if kind in ('ramps', 'platforms') else 'arena_grey', rgba, 0.0, 0.9)
        kids.append(g.node(kind, mesh=g.mesh(kind, P, N, np.concatenate(T), mat)))
    if ground:
        (gx, gy), grgba = ground
        p, n, t = M.box((gx, gy, 0.01))
        p = p - np.array([0, 0, 0.005 + 0.002])   # just below z = 0, under the floor layers
        kids.append(g.node('ground', mesh=g.mesh('ground', p, n, t, g.material('ground', grgba, 0.0, 1.0))))
    g.node('arena', rotation=Z_UP_TO_Y_UP, children=kids, root=True,
           extras={'frame': 'Gazebo world; z-up, rotated to glTF y-up at this node'})
    data = g.bytes(extras={'world': os.path.relpath(WORLD, REPO), 'world_sha256': sha, 'traverse': True,
                           'ramp_angle_deg': RAMP_ANGLE_DEG})
    open(os.path.join(out, 'arena.glb'), 'wb').write(data)
    summary = {'world': os.path.relpath(WORLD, REPO), 'world_sha256': sha, 'spawned': 'full_world_robo.launch.py traverse:=true',
               'ramp_angle_deg': RAMP_ANGLE_DEG, 'rise_m': rise, 'bytes': len(data), 'triangles': g.triangles(),
               'kinds': {k: len(v) for k, v in sorted(parts.items())}, 'footprints': footprints}
    json.dump(summary, open(os.path.join(out, 'arena.json'), 'w'), indent=1, sort_keys=True)
    print(f'arena.glb: {len(data):,} B, {g.triangles():,} triangles, {len(footprints)} footprints '
          f'{dict(summary["kinds"])}')


if __name__ == '__main__':
    main(sys.argv[1])
