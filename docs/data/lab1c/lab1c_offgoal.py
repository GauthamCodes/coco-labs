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
POST-HOC analysis of the conformance pairs whose Smac raw path did not end
on the goal cell. Pure; reads conformance.json and S0_costmap_raw.bin.gz.

  python3 lab1c_offgoal.py CONFORMANCE_DIR [--out offgoal.json]

Written AFTER the sweep, to investigate (plan F-6) rather than to redefine
anything: the pre-registered comparison excluded these pairs by its own
rule and stays as it was. Two questions, both answered on S0:

1. Is Smac's truncated path the C1 optimum to the cell where it STOPPED?
   (coco_lab C1 Dijkstra, start -> Smac's end cell; relative gap.)
2. Do the stopped-short goals sit in costlier cells than the others?
   (raw S0 cost of the goal cell, per group.)
"""

import argparse
import gzip
import json
import os
import sys

from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.metrics import distribution
from coco_lab_ros.planning import Planner


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dir')
    ap.add_argument('--out')
    a = ap.parse_args()
    doc = json.load(open(os.path.join(a.dir, 'conformance.json')))
    s0 = doc['S0']
    data = gzip.decompress(open(os.path.join(a.dir, 'S0_costmap_raw.bin.gz'),
                                'rb').read())
    snap = Snapshot(width=s0['width'], height=s0['height'],
                    resolution=s0['resolution'], origin=tuple(s0['origin']),
                    frame_id=s0['frame_id'], data=data)
    assert snap.content_hash() == s0['content_hash'], 'S0 file != S0'
    planner = Planner(snap)
    rows = []
    for p in doc['pairs']:
        r = p['smac_raw']
        g = tuple(p['goal_cell'])
        row = {'draw': p['draw'], 'endpoint_ok': r['endpoint_ok'],
               'goal_cost': snap.cost(*g)}
        if not r['endpoint_ok']:
            end = tuple(r['end_cell'])
            best = planner.plan_cells(tuple(p['start_cell']), end,
                                      'dijkstra', 'zero', 'C1')
            row.update({'end_cell': list(end), 'end_cost': snap.cost(*end),
                        'cells_off_chebyshev': max(abs(end[0] - g[0]),
                                                   abs(end[1] - g[1])),
                        'E_smac_raw': r['E'],
                        'E_c1_to_end_cell': best.result.cost,
                        'rel_gap_to_end_cell':
                            (r['E'] - best.result.cost) / best.result.cost})
        rows.append(row)
    off = [x for x in rows if not x['endpoint_ok']]
    on = [x for x in rows if x['endpoint_ok']]
    out = {
        'S0': s0['content_hash'], 'off_goal': len(off), 'on_goal': len(on),
        'rel_gap_to_end_cell': distribution(
            [x['rel_gap_to_end_cell'] for x in off]),
        'optimal_to_end_cell_within_1e-4': sum(
            1 for x in off if abs(x['rel_gap_to_end_cell']) <= 1e-4),
        'goal_cost_off': distribution([x['goal_cost'] for x in off]),
        'goal_cost_on': distribution([x['goal_cost'] for x in on]),
        'cells_off_chebyshev': sorted(x['cells_off_chebyshev'] for x in off),
        'rows': rows,
    }
    text = json.dumps(out, sort_keys=True, indent=1)
    if a.out:
        open(a.out, 'w').write(text + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'},
                     sort_keys=True, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
