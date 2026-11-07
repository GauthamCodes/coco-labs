#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.4: the validated STACK subset of a COCO-Bench v1 suite (a scenarios file for ros2_bench.py).

    stack_scenarios.py SUITE --n 20 [--servers A,B@NavFn,...] [--rule yield] --out FILE

The first ceil(n/3) scenarios of each tier in id order (easy, medium, hard; then cut to n), so the
subset spans the suite's difficulty. Depot worlds only (their world frame IS the map frame). A goal
without a heading faces along the start-goal line. ``--rule`` keeps one actor rule of a paired
suite (ctrl-dynamic-30): Gazebo's generated actors follow one scenario rule per session
(derivation 5: they yield), so the STACK subset is the yielding half.
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIERS = ('easy', 'medium', 'hard')


def subset(st, n, rule=None):
    scen = [s for s in st['scenarios'] if rule is None or s.get('actor_rule') == rule]
    per = -(-n // 3)
    out = []
    for t in TIERS:
        out += [s for s in scen if s['tier'] == t][:per]
    return out[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('suite')
    ap.add_argument('--n', type=int, default=20)
    ap.add_argument('--servers', default='compute_path_to_pose,compute_path_to_pose@NavFn,'
                                          'compute_path_to_pose@SmacHybrid,user_compute_path_to_pose')
    ap.add_argument('--rule')
    ap.add_argument('--out', required=True)
    o = ap.parse_args()
    st = json.loads((ROOT / 'coco_lab' / 'coco_lab' / 'benchmarks' / f'{o.suite}.v1.json').read_text())
    if not str(st['world']).startswith('coco_depot'):
        raise SystemExit(f'{o.suite}: STACK subsets are on Depot worlds only')
    out = []
    for s in subset(st, o.n, o.rule):
        (sx, sy, *st_), (gx, gy, *gt) = s['start'], s['goal']
        heading = math.atan2(gy - sy, gx - sx)
        out.append({'id': s['id'], 'tier': s['tier'], 'start': [sx, sy, st_[0] if st_ else heading],
                    'goal': [gx, gy, gt[0] if gt else heading]})
    doc = {'suite': o.suite, 'suite_version': st['version'], 'world': st['world'],
           'start': out[0]['start'], 'servers': o.servers.split(','), 'scenarios': out,
           'subset': f'first ceil(n/3) per tier, n={o.n}' + (f', rule {o.rule}' if o.rule else '')}
    Path(o.out).parent.mkdir(parents=True, exist_ok=True)
    Path(o.out).write_text(json.dumps(doc, indent=1) + '\n')
    print(f'{o.out}: {len(out)} scenarios')


if __name__ == '__main__':
    main()
