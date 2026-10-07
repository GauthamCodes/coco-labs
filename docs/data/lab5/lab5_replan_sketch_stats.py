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
D* Lite's work against A* from scratch, over the seeded Sketch worlds.

  python3 -P docs/data/lab5/lab5_replan_sketch_stats.py [--seeds 200] [--out F]

Deterministic (``replan.sketch_world(seed)`` for seeds 0..N-1, default
sense radius 2.5). For each episode: total expansions of D* Lite (all
rounds) and of A* from scratch (all rounds), the costs agreeing every
round, and per REPLAN (round >= 1) whether D* Lite did more work than A*
on that round. Writes ``replan_sketch_stats.json`` beside this script.
"""

import argparse
import json
import os
import sys

from coco_lab.movemetrics import distribution
from coco_lab.replan import run_replan, sketch_world

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seeds', type=int, default=200)
    ap.add_argument('--out', default=os.path.join(HERE,
                                                  'replan_sketch_stats.json'))
    a = ap.parse_args()
    rows, replans, worse = [], 0, 0
    for seed in range(a.seeds):
        r = run_replan(sketch_world(seed))
        s = r.summary()
        for rd in r.rounds[1:]:
            replans += 1
            worse += rd.dstar_expansions > rd.astar_expansions
        rows.append({'seed': seed, 'status': s['status'],
                     'replans': s['replans'],
                     'dstar': s['dstar_expansions'],
                     'astar': s['astar_expansions'],
                     'ratio': s['dstar_expansions'] / s['astar_expansions'],
                     'costs_agree': s['costs_agree']})
    out = {'seeds': a.seeds, 'sense_radius': 2.5,
           'reached': sum(1 for r in rows if r['status'] == 'reached'),
           'costs_agree_all': all(r['costs_agree'] for r in rows),
           'episode_ratio_dstar_over_astar': distribution(
               [r['ratio'] for r in rows]),
           'episodes_dstar_less_total': sum(1 for r in rows
                                            if r['dstar'] < r['astar']),
           'replans': replans, 'replans_dstar_more': worse,
           'rows': rows}
    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
