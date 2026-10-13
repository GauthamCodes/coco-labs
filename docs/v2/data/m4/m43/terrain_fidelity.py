# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
The Arena's terrain against Gazebo's, at identical poses (M4.3).

No ROS. Inputs held fixed: Lab 4's recorded fetches, extracted by
``extract_lab4_truth.py`` into ``lab4_truth.json.gz`` (Gazebo's ground truth
of the robot, world frame, one row per 0.1 s). For every recorded row the
Arena is put at the recorded TRUE (x, y, yaw) on World Spec v2
(``worlds/coco_arena_v2.yaml``, map frame = world + ``world_to_map``) and
its kinematic terrain following (``Arena.tilt``: the surface under the
wheel base's four corners) gives z, pitch and roll; ``e = gazebo - arena``.

Rows are classed by where the ARENA puts the robot: ``flat`` (z = 0 and
level), ``platform`` (at the platform's height, level), ``slope`` (pitched
or rolled, the wheel base on a ramp or across an edge). The run that never
climbed (``B3_colours_s7_red.void-1``) is included: it is flat-floor data.

Usage::

    python3 docs/v2/data/m4/m43/terrain_fidelity.py --out docs/v2/data/m4/m43/terrain_fidelity.json
"""

import argparse
import gzip
import json
import math
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.dont_write_bytecode = True

import yaml  # noqa: E402
from coco_lab import arena as A  # noqa: E402


def pct(v, q):
    s = sorted(v)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))] if s else None


def stats(v):
    a = [abs(x) for x in v]
    return {'n': len(v), 'mean': sum(v) / len(v) if v else None, 'median_abs': pct(a, 0.5),
            'p95_abs': pct(a, 0.95), 'max_abs': max(a) if a else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--truth', default=os.path.join(HERE, 'lab4_truth.json.gz'))
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    with gzip.open(a.truth, 'rt', encoding='utf-8') as f:
        truth = json.load(f)
    with open(os.path.join(REPO, 'worlds', 'coco_arena_v2.yaml'), encoding='utf-8') as f:
        arena = A.Arena(yaml.safe_load(f), 1)
    dx, dy = arena.spec['world_to_map']
    rise = max(e['size'][2] for e in arena.spec['elevation'] if e['kind'] == 'platform')
    classes = {k: {'z': [], 'pitch': [], 'roll': []} for k in ('flat', 'slope', 'platform')}
    per_run, worst = [], {'z': None, 'pitch': None, 'roll': None}
    # every wedge's two ends along x (the spec's world frame, as the truth is), named
    edges = []
    for e in arena.spec['elevation']:
        if e['kind'] == 'wedge':
            fx = e['foot'][0]
            far = fx + e['run'] * (1 if math.cos(e.get('yaw', 0.0)) > 0 else -1)
            fy, hw = e['foot'][1], e['width'] / 2
            edges += [(fx, fy, hw, e['id'] + ' foot'), (far, fy, hw, e['id'] + ' top')]

    def near(wx, wy):
        # the edges of the wedges whose width spans y (every bay shares its x), else all of them
        cand = [c for c in edges if abs(wy - c[1]) <= c[2]] or edges
        d, name = min((abs(wx - c[0]), c[3]) for c in cand)
        return {'edge': name, 'distance_m': d}
    for run in truth['runs']:
        er = {'z': [], 'pitch': [], 'roll': []}
        for t, x, y, z, roll, pitch, yaw in run['rows']:
            arena.pose = (x + dx, y + dy, yaw)
            mz, mp, mr = arena.tilt()
            if mp == 0.0 and mr == 0.0:
                cls = 'flat' if mz == 0.0 else 'platform' if abs(mz - rise) < 1e-9 else 'slope'
            else:
                cls = 'slope'
            for k, g, m in (('z', z, mz), ('pitch', pitch, mp), ('roll', roll, mr)):
                e = g - m
                classes[cls][k].append(e)
                er[k].append(e)
                if worst[k] is None or abs(e) > abs(worst[k]['e']):
                    worst[k] = {'e': e, 'run': run['run'], 't': t, 'world_xy_yaw': [x, y, yaw],
                                'gazebo': g, 'arena': m, 'class': cls, 'nearest_edge': near(x, y)}
        per_run.append({'run': run['run'], 'rows': len(run['rows']),
                        'gazebo_z_max': max(r[3] for r in run['rows']),
                        'onto_platform': max(r[3] for r in run['rows']) > rise - 0.01,
                        **{k: stats(v) for k, v in er.items()}})
    out = {
        'criterion': "the Arena's kinematic terrain following against Gazebo's ground truth "
                     'at identical (x, y, yaw) (README §5.1; M4.3)',
        'class': 'MODEL against STACK (recorded); SIMPLIFIED MODEL',
        'source': os.path.relpath(a.truth, REPO), 'bags': [r['bag'] for r in truth['runs']],
        'spec': 'worlds/coco_arena_v2.yaml', 'model': 'coco_lab.arena.Arena.tilt (coco_lab.terrain)',
        'units': {'z': 'm', 'pitch': 'rad', 'roll': 'rad'},
        'by_class': {c: {k: stats(v) for k, v in d.items()} for c, d in classes.items()},
        'worst': worst, 'per_run': per_run,
        'python': platform.python_version(),
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    for c, d in out['by_class'].items():
        print(c, d['z']['n'], ' '.join(f"{k}: med {d[k]['median_abs']:.4f} p95 {d[k]['p95_abs']:.4f} "
                                       f"max {d[k]['max_abs']:.4f}" for k in ('z', 'pitch', 'roll')))
    for k, w in worst.items():
        print('worst', k, json.dumps(w))


if __name__ == '__main__':
    main()
