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
M1.3: the Arena model's LiDAR against Gazebo, on Lab 2's recorded poses.

    python3 docs/v2/data/m1/lidar/arena_lidar_fidelity.py \
        ~/coco_lab_runs/lab2/fidelity_1 ~/coco_lab_runs/lab2/fidelity_s1 \
        --out docs/v2/data/m1/lidar/arena_lidar_fidelity.json

Lab 2 measured Sketch's LiDAR on the saved Nav2 map against Gazebo's at
identical TRUE poses (``docs/data/lab2/an_fidelity.py``; 86.7 % of beams
within 5 cm, 237 scans after the tilt filter). M1.3 replaces that map with
the Arena world GENERATED from ``worlds/coco_arena_v1.yaml`` and casts with
the Arena's own LiDAR (``coco_lab.arena.Arena``). This re-runs the same
comparison, with Lab 2's rules (480 beams; a scan whose robot settled
tilted by more than 2 degrees is excluded; a model range outside
[range_min, range_max] is no return; per beam ``e = gazebo - model`` where
both returned), and also compares the Arena's ranges with Lab 2's Sketch
ranges beam for beam, to say WHY the figure holds or moves.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

import yaml  # noqa: E402

from coco_lab import maps, sketch  # noqa: E402
from coco_lab.arena import Arena  # noqa: E402

INF = math.inf
LAB2 = os.path.join(REPO, 'docs', 'data', 'lab2', 'fidelity', 'fidelity.json')
NAV_YAML = os.path.join(REPO, 'gazebo_models', 'maps', 'coco_navigation.yaml')
SPEC = os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('sessions', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-tilt', type=float, default=2.0)
    a = ap.parse_args(argv)

    with open(SPEC, encoding='utf-8') as f:
        arena = Arena(yaml.safe_load(f), seed=0)
    lab2_smap = sketch.SketchMap(maps.load_nav2(NAV_YAML))
    lidar = arena.lidar
    angles = lidar.angles()
    assert lidar.samples == 480

    classes = {'both': 0, 'gz_only': 0, 'model_only': 0, 'neither': 0}
    absd = []
    scans_recorded = scans_used = 0
    beams_differing_from_lab2_sketch = 0
    max_diff_from_lab2_sketch = 0.0
    for sess in a.sessions:
        path = os.path.join(sess, 'scans.jsonl')
        for line in open(path):
            r = json.loads(line)
            scans_recorded += 1
            _, x, y, yaw, _, tilt = r['truth']
            if math.degrees(tilt) > a.max_tilt:
                continue
            scans_used += 1
            assert len(r['ranges']) == 480
            pose = (x, y, yaw)
            model = arena.smap.scan(pose, lidar, angles)
            lab2 = lab2_smap.scan(pose, sketch.COCO_LIDAR,
                                  sketch.COCO_LIDAR.angles())
            for m, s in zip(model, lab2):
                if m != s:
                    beams_differing_from_lab2_sketch += 1
                    if m < INF and s < INF:
                        max_diff_from_lab2_sketch = max(
                            max_diff_from_lab2_sketch, abs(m - s))
            for g, m in zip(r['ranges'], model):
                g = INF if g is None else g
                m = INF if (m < lidar.range_min or m > lidar.range_max) else m
                if g < INF and m < INF:
                    classes['both'] += 1
                    absd.append(abs(g - m))
                elif g < INF:
                    classes['gz_only'] += 1
                elif m < INF:
                    classes['model_only'] += 1
                else:
                    classes['neither'] += 1

    with open(LAB2) as f:
        lab2 = json.load(f)['scans']
    frac = {f'{t:.2f}': sum(1 for v in absd if v < t) / len(absd)
            for t in (0.01, 0.02, 0.05, 0.10, 0.25)}
    out = {
        'tool': 'docs/v2/data/m1/lidar/arena_lidar_fidelity.py',
        'evidence_class': 'MODEL vs STACK',
        'model': 'coco_lab.arena.Arena on worlds/coco_arena_v1.yaml '
                 '(arena_map, 0.05 m, map frame), 480-beam LiDAR from the spec',
        'sessions': [os.path.basename(s) for s in a.sessions],
        'max_tilt_deg': a.max_tilt,
        'scans_recorded': scans_recorded,
        'scans_used': scans_used,
        'beams': sum(classes.values()),
        'classes': classes,
        'frac_abs_below': frac,
        'lab2_frac_abs_below': lab2['frac_abs_below'],
        'lab2_scans_used': lab2['scans_used'],
        'lab2_classes': lab2['classes'],
        'beams_differing_from_lab2_sketch': beams_differing_from_lab2_sketch,
        'max_abs_range_difference_from_lab2_sketch_m':
            max_diff_from_lab2_sketch,
    }
    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: out[k] for k in (
        'scans_used', 'beams', 'classes', 'frac_abs_below',
        'beams_differing_from_lab2_sketch')}, indent=1))


if __name__ == '__main__':
    main()
