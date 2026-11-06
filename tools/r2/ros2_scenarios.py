#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R2.7: the COCO-Bench scenarios Gazebo + Nav2 runs on (a scenarios file for ros2_bench.py).

    ros2_scenarios.py depot-nav-100 --every 5 --servers compute_path_to_pose,user_compute_path_to_pose --out FILE

Every ``every``-th scenario of the frozen suite (the Depot's world frame IS its map frame:
world_to_map [0, 0]); a goal without a heading faces along the start-goal line.
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('suite')
    ap.add_argument('--every', type=int, default=5)
    ap.add_argument('--servers', default='compute_path_to_pose,user_compute_path_to_pose')
    ap.add_argument('--out', required=True)
    o = ap.parse_args()
    st = json.loads((ROOT / 'coco_lab' / 'coco_lab' / 'benchmarks' / f'{o.suite}.v0.json').read_text())
    out = []
    for i, s in enumerate(st['scenarios']):
        if i % o.every:
            continue
        (sx, sy, *st_), (gx, gy, *gt) = s['start'], s['goal']
        heading = math.atan2(gy - sy, gx - sx)
        out.append({'id': s['id'], 'index': i, 'start': [sx, sy, st_[0] if st_ else heading],
                    'goal': [gx, gy, gt[0] if gt else heading]})
    doc = {'suite': o.suite, 'suite_version': st['version'], 'world': st['world'],
           'start': out[0]['start'], 'servers': o.servers.split(','), 'scenarios': out}
    Path(o.out).parent.mkdir(parents=True, exist_ok=True)
    Path(o.out).write_text(json.dumps(doc, indent=1) + '\n')
    print(f'{o.out}: {len(out)} scenarios')


if __name__ == '__main__':
    main()
