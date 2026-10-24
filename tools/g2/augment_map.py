#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.6: the generated Nav2 map plus what the LiDAR sees that it leaves out (a diagnosis tool).

    tools/g2/augment_map.py GEN_DIR OUT_DIR [--objects] [--actors]

The generated map (``worldgen.nav_map``) rasterises the level's static solids only. In Gazebo the
LiDAR (scan plane ``scan_height``, 0.2135 m on the Depot) also sees:

- ``--objects``: catalog objects whose body crosses the scan plane (on the Depot: ``bad_crate``,
  0.3 m tall on the floor; the cans are 0.158 m, under it);
- ``--actors``: the actors, parked in M6F.8's runs at their path's first point, facing along it
  (forklifts 2.4 x 1.2 m, walkers 0.5 x 0.5 m).

Writes OUT_DIR/nav2/{coco_depot_v1.pgm, coco_depot_v1.yaml, nav2_params.yaml (map path set)} and
``augment.json`` (what was added, cell counts). GEN_DIR is read only.
"""
import argparse
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import worldspec_v3 as v3  # noqa: E402
from coco_lab.worldspec import normalize, scan_height  # noqa: E402
import yaml  # noqa: E402


def read_pgm(path):
    with open(path, 'rb') as f:
        data = f.read()
    parts, i = [], 0
    while len(parts) < 4:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b'#':
            i = data.index(b'\n', i)
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        parts.append(data[i:j]); i = j
    w, h = int(parts[1]), int(parts[2])
    return w, h, bytearray(data[i + 1:i + 1 + w * h])


def footprints(spec, objects, actors):
    s = normalize(spec)
    sh = scan_height(s)
    dx, dy = s['world_to_map']
    out = []
    if objects:
        for o in v3.objects(spec):
            top = o.get('height') if o['shape'] == 'cylinder' else o['size'][2]
            if not (o['z'] < sh < o['z'] + top):
                continue
            L, W = (o['diameter'], o['diameter']) if o['shape'] == 'cylinder' else (o['size'][0], o['size'][1])
            out.append({'what': f"object {o['id']}", 'x': o['x'] + dx, 'y': o['y'] + dy, 'yaw': o.get('yaw', 0.0), 'L': L, 'W': W})
    if actors:
        for a in v3.elements(spec, 'actor'):
            (x0, y0), (x1, y1) = a['path'][0], a['path'][1]
            out.append({'what': f"actor {a['id']} (parked at its path start)", 'x': x0 + dx, 'y': y0 + dy,
                        'yaw': math.atan2(y1 - y0, x1 - x0), 'L': a['footprint'][0], 'W': a['footprint'][1]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('gen'); ap.add_argument('out')
    ap.add_argument('--objects', action='store_true'); ap.add_argument('--actors', action='store_true')
    o = ap.parse_args()
    with open(os.path.join(o.gen, 'nav2', 'coco_depot_v1.yaml')) as f:
        my = yaml.safe_load(f)
    w, h, px = read_pgm(os.path.join(o.gen, 'nav2', my['image']))
    res, (ox, oy) = my['resolution'], my['origin'][:2]
    spec = json.load(open(os.path.join(REPO, 'worlds', 'coco_depot_v1.json')))
    added = []
    for fp in footprints(spec, o.objects, o.actors):
        c, s = math.cos(fp['yaw']), math.sin(fp['yaw'])
        n = 0
        r = math.hypot(fp['L'], fp['W']) / 2 + res
        for row in range(h):
            y = oy + (h - 1 - row + 0.5) * res
            if abs(y - fp['y']) > r:
                continue
            for col in range(w):
                x = ox + (col + 0.5) * res
                if abs(x - fp['x']) > r:
                    continue
                lx, ly = c * (x - fp['x']) + s * (y - fp['y']), -s * (x - fp['x']) + c * (y - fp['y'])
                if abs(lx) <= fp['L'] / 2 and abs(ly) <= fp['W'] / 2 and px[row * w + col] != 0:
                    px[row * w + col] = 0
                    n += 1
        added.append(dict(fp, cells=n))
    os.makedirs(os.path.join(o.out, 'nav2'), exist_ok=True)
    with open(os.path.join(o.out, 'nav2', 'coco_depot_v1.pgm'), 'wb') as f:
        f.write(f'P5\n{w} {h}\n255\n'.encode() + bytes(px))
    with open(os.path.join(o.out, 'nav2', 'coco_depot_v1.yaml'), 'w') as f:
        yaml.safe_dump(dict(my, image='coco_depot_v1.pgm'), f, sort_keys=False)
    with open(os.path.join(o.gen, 'nav2', 'nav2_params.yaml')) as f:
        params = yaml.safe_load(f)
    params['map_server']['ros__parameters']['yaml_filename'] = os.path.join(os.path.abspath(o.out), 'nav2', 'coco_depot_v1.yaml')
    with open(os.path.join(o.out, 'nav2', 'nav2_params.yaml'), 'w') as f:
        yaml.safe_dump(params, f, sort_keys=False)
    with open(os.path.join(o.out, 'augment.json'), 'w') as f:
        json.dump({'from': os.path.abspath(o.gen), 'objects': o.objects, 'actors': o.actors, 'added': added}, f, indent=1)
    print(json.dumps([(a['what'], a['cells']) for a in added]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
