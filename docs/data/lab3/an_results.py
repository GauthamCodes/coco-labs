#!/usr/bin/env python3
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
Phase 4: gather every real-drive result into ``results.json``.

Inputs (all outside git, under ``~/coco_lab_runs``): the extracted drives
(``drives/<id>/drive_meta.json``), every backend round
(``<round dir>/backends/<drive>_<backend>_<arm>/score.json``, written by
``an_backend.py``; the round's name is given on the command line), and
coco_lab's runs on each drive (``an_coco.py`` JSON). Nothing is recomputed
here except the summary rows: every number is copied from those files,
with the machine's load average at the end of each backend run, because
an ONLINE backend under load may drop scans.

Usage::

    python3 docs/data/lab3/an_results.py --drives ~/coco_lab_runs/lab3/drives \\
        --round r1=~/coco_lab_runs/lab3 --round r2=~/coco_lab_runs/lab3_r2 \\
        --coco s1_tour=~/coco_lab_runs/lab3/coco_s1_tour.json \\
        --coco 1_tour=~/coco_lab_runs/lab3/coco_1_tour.json \\
        --out docs/data/lab3/results.json
"""

import argparse
import glob
import json
import math
import os

DRIVES = ('s1_tour', '1_tour')


def length(rows):
    return sum(math.dist(a['truth'][:2], b['truth'][:2])
               for a, b in zip(rows, rows[1:]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--drives', required=True)
    ap.add_argument('--round', action='append', default=[])
    ap.add_argument('--coco', action='append', default=[])
    ap.add_argument('--notes', action='append', default=[])
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    import lab3_common as C
    drives = []
    for d in DRIVES:
        path = os.path.join(os.path.expanduser(args.drives), d)
        meta = json.load(open(os.path.join(path, 'drive_meta.json')))
        drive = C.load_drive(path)
        drives.append({
            'id': d, 'session': os.path.basename(meta['session']),
            'window_sim_s': meta['window_sim_s'],
            'length_m': round(length(drive['rows']), 2),
            'scans': meta['scans_in_drive'],
            'map_to_odom_dropped': meta['map_to_odom_transforms_dropped'],
            'source_bag_sha256': meta['source_bag_sha256']})
    backends = []
    odom = {}
    for spec in args.round:
        name, base = spec.split('=', 1)
        for p in sorted(glob.glob(os.path.join(os.path.expanduser(base),
                                               'backends', '*',
                                               'score.json'))):
            s = json.load(open(p))
            run = os.path.basename(os.path.dirname(p))
            drive, rest = run.split('_tour_', 1)
            drive += '_tour'
            backend, arm = rest.rsplit('_', 1)
            end = s.get('end', {})
            meta = s.get('meta', {})
            m = s['map'] or {}
            odom[drive] = s['ate_wheel_odometry']['rmse']
            backends.append({
                'drive': drive, 'backend': backend, 'arm': arm, 'round': name,
                'ate_online_rmse': s['ate_online']['rmse'],
                'ate_online_max': s['ate_online']['max'],
                'f1': m.get('f1'), 'precision': m.get('precision'),
                'recall': m.get('recall'), 'coverage': m.get('coverage'),
                'loadavg_start': meta.get('loadavg_start'),
                'loadavg_end': end.get('loadavg_end'),
                'play_wall_s': end.get('play_wall_s'),
                'map_to_odom_messages': s['map_to_odom_messages'],
                'run': f'{name}:{run}'})
    for d in drives:
        d['wheel_odometry_ate_rmse'] = odom.get(d['id'])
    coco = []
    for spec in args.coco:
        drive, path = spec.split('=', 1)
        c = json.load(open(os.path.expanduser(path)))
        for label, r in sorted(c['runs'].items()):
            arm, _, seed = label.partition('@seed')
            coco.append({
                'drive': drive, 'arm': arm, 'seed': int(seed) if seed else None,
                'ate_online_rmse': r['ate_online']['rmse'],
                'ate_final_rmse': r['ate_final']['rmse'],
                'f1': r['map']['f1'], 'precision': r['map']['precision'],
                'recall': r['map']['recall'], 'coverage': r['map']['coverage'],
                'wall_s': r['wall_s'], 'loop_closures': r.get('loop_closures')})
        for d in drives:
            if d['id'] == drive:
                d['updates'] = c['n_updates']
                d['coco_alphas'] = c['alphas']
                d['landmarks'] = c['landmarks']
    out = {
        'label': 'measured: recorded drives replayed into each backend '
                 '(1.0x requested, online) and coco_lab, identical scans '
                 'and wheel odometry; scored by coco_lab.mapeval against the '
                 'Phase 1B ground-truth raster',
        'command': 'python3 docs/data/lab3/an_results.py (see '
                   'docs/data/lab3/README.md)',
        'drives': drives, 'backends': backends, 'coco_lab': coco,
        'notes': args.notes,
    }
    with open(args.out, 'w') as f:
        f.write(json.dumps(out, indent=1, sort_keys=True) + '\n')
    print(f'{len(backends)} backend runs, {len(coco)} coco_lab runs')


if __name__ == '__main__':
    main()
