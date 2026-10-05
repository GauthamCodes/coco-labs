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
Phase 4: the Sketch scenes over 20 worlds each -- what one world is not.

For every Lab 3 Sketch scene (``map_teaching.scene_scenario``) and world
seeds 0..19: simulate the world with the scene's drive and noise, run every
algorithm of ``map_teaching.run_specs()`` (FastSLAM seed 0) on it, score it
(``coco_lab.mapeval``, the bundle's definitions), and record per run the
final trajectory error and the map F1 -- and, for the pose graph, whether a
loop was closed and whether closing it lowered the final error.

This is SKETCH: coco_lab's model, not the robot. No ROS. Usage::

    python3 docs/data/lab3/sketch_counts.py --out docs/data/lab3/sketch_counts.json
"""

import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'coco_lab'))

from coco_lab import map_teaching, mapeval, mapworld, slambundle  # noqa: E402
from coco_lab import bundle  # noqa: E402

SEEDS = list(range(20))
SCENES = ('map_loop', 'map_corridor', 'map_landmarks')


def pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--out', required=True)
    ap.add_argument('--seeds', type=int, default=len(SEEDS))
    args = ap.parse_args(argv)
    seeds = list(range(args.seeds))
    maps = map_teaching.teaching_maps()
    out = {'label': 'Sketch (coco_lab\'s 2D model, not the robot), '
                    f'{len(seeds)} world seeds per scene, FastSLAM seed 0',
           'command': 'python3 docs/data/lab3/sketch_counts.py --out '
                      'docs/data/lab3/sketch_counts.json',
           'coco_lab_version': __import__('coco_lab').__version__,
           'git': bundle.git_provenance(os.path.join(HERE, '..', '..',
                                                     '..')),
           'scenes': {}}
    for sid in SCENES:
        per = {}
        closed = improved = 0
        for seed in seeds:
            m, sc = map_teaching.scene_scenario(sid, maps)
            sc.seed = seed
            w = mapworld.from_sketch(m, sc)
            sb = slambundle.SlamBundle.compute(
                m, w, map_teaching.run_specs(snapshots=1),
                bundle.make_provenance('sketch', seed=seed))
            runs = dict(sb.runs)
            for rid, tr in runs.items():
                per.setdefault(rid, {'final_ate': [], 'f1': []})
                per[rid]['final_ate'].append(tr.summary['ate_final']['rmse'])
                per[rid]['f1'].append(tr.summary['map']['f1'])
            pg = runs['pose_graph']
            if len(pg.arrays['loops.k'][1]):
                closed += 1
                if pg.summary['ate_final']['rmse'] < \
                        runs['pose_graph_noloop'].summary['ate_final']['rmse']:
                    improved += 1
            print(sid, seed, {r: round(v['final_ate'][-1], 3)
                              for r, v in per.items()}, flush=True)
        out['scenes'][sid] = {
            'seeds': seeds, 'loop_closed': closed, 'loop_improved': improved,
            'per_seed': {r: v for r, v in per.items()},
            'runs': {r: {'n': len(v['f1']),
                         'final_ate_median': statistics.median(v['final_ate']),
                         'final_ate_p10': pct(v['final_ate'], 0.1),
                         'final_ate_p90': pct(v['final_ate'], 0.9),
                         'f1_median': statistics.median(v['f1']),
                         'f1_p10': pct(v['f1'], 0.1),
                         'f1_p90': pct(v['f1'], 0.9)}
                     for r, v in per.items()},
        }
    with open(args.out, 'w') as f:
        f.write(json.dumps(mapeval.round_floats(out, 4), indent=1,
                           sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
