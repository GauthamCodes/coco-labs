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
Phase 4: were coco_lab's pose-graph loop closures on the real tours TRUE?

A loop closure says "the scan at update k was taken where node j was",
up to the matched relative pose. With the simulator's truth both can be
checked: the TRUE relative pose between the two updates against the
matched one. A closure whose matched pose is more than 0.5 m (or 0.2 rad)
from the truth joined two places that were NOT where the match said --
a false closure (on this arena, typically one bay mistaken for another).

Usage::

    python3 docs/data/lab3/an_loops.py DRIVE_DIR [DRIVE_DIR ...] --out F
"""

import argparse
import json
import math
import os

import an_coco as A
import lab3_common as C
from coco_lab import mapeval, mapping, mapworld
from coco_lab import posegraph as pg

FALSE_M = 0.5
FALSE_RAD = 0.2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('drives', nargs='+')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    cal, _ = A.calibrated_alphas()
    tmap, _ = C.ground_truth()
    out = {'definition': f'false: matched relative pose more than {FALSE_M} m '
                         f'or {FALSE_RAD} rad from the true one',
           'command': 'python3 docs/data/lab3/an_loops.py ' + ' '.join(
               os.path.basename(os.path.normpath(d)) for d in args.drives),
           'drives': {}}
    for d in args.drives:
        drive = C.load_drive(d)
        w = mapworld.from_recorded(A.payload(drive), tmap, spec=A.LANDMARKS,
                                   seed=A.WORLD_SEED)
        inp, tp = w.inputs(), w.true_poses()
        p = A.arm_runs('pose_graph', cal)[0][2]
        tr = mapping.run('pose_graph', inp, tmap, p)
        a = tr.arrays
        rows = []
        for e in range(len(a['edges.i'][1])):
            if pg.EDGE_KINDS[a['edges.kind'][1][e]] != 'loop':
                continue
            i, j = a['edges.i'][1][e], a['edges.j'][1][e]
            true_rel = pg.between(tp[i], tp[j])
            gap = math.hypot(tp[i][0] - tp[j][0], tp[i][1] - tp[j][1])
            rows.append({'node_old': i, 'node_new': j,
                         'true_distance_m': gap,
                         'true_rel': list(true_rel)})
        # the trace keeps each edge's ends, not its measurement: re-run the
        # (deterministic) pose graph and capture each loop edge's matched z
        matched = _loop_measurements(inp, tp, p)
        assert len(matched) == len(rows)
        for r, m in zip(rows, matched):
            r['matched_rel'] = list(m)
            r['error_m'] = math.hypot(m[0] - r['true_rel'][0],
                                      m[1] - r['true_rel'][1])
            r['error_rad'] = abs(math.remainder(m[2] - r['true_rel'][2],
                                                2 * math.pi))
            r['false'] = r['error_m'] > FALSE_M or r['error_rad'] > FALSE_RAD
        fin = mapeval.ate(tr.final_trajectory(), tp, align=True)['rmse']
        out['drives'][os.path.basename(os.path.normpath(d))] = {
            'closures': len(rows),
            'false': sum(r['false'] for r in rows),
            'final_ate_rmse': fin, 'closures_detail': rows}
        print(os.path.basename(d), len(rows), 'closures,',
              sum(r['false'] for r in rows), 'false; final ATE', round(fin, 3))
    with open(args.out, 'w') as f:
        f.write(json.dumps(mapeval.round_floats(out, 4), indent=1,
                           sort_keys=True) + '\n')


def _loop_measurements(inp, tp, p):
    """Re-run the pose graph's loop-edge bookkeeping to get each z (as built)."""
    captured = []
    real_edge = pg.Edge

    class Spy(real_edge):
        def __init__(self, i, j, z, info, kind):
            super().__init__(i, j, z, info, kind)
            if kind == 'loop':
                captured.append(z)

    pg.Edge = Spy
    try:
        tmap, _ = C.ground_truth()
        mapping.run('pose_graph', inp, tmap, p)
    finally:
        pg.Edge = real_edge
    return captured


if __name__ == '__main__':
    main()
