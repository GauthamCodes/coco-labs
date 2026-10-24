#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.6: a recorded Gazebo + Nav2 run of a Fetch Rush round, as Play's "Race Nav2" ghost (STACK).

    source /opt/ros/jazzy/setup.bash && tools/g2/make_ghost.py RUN_DIR GOALS.json OUT.json

RUN_DIR is a ``tools/m6/m6f8_run.sh`` run of a round's goals (``tools/m6/m6f8_goals.py ghost``).
Writes the truth (Gazebo's /model/coco/odometry) at 10 Hz from the first leg's start (t = 0) to
the last leg's end, and the legs (Nav2's status, driving time, distance), with where it came from:
the bag's sha256, the goals, the run's meta (git commit, generated files' checksums). What it is
NOT, said in the file: no grasp happened (Nav2 drove the legs only; the arm did not move), and
Gazebo's actors were parked at their path's start (M6F.8's setup), so no forklift crossed.
"""
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnose_m6f8 as d  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    run, goals_path, out = sys.argv[1:4]
    goals = json.load(open(goals_path))
    meta = json.load(open(os.path.join(run, 'meta.json')))
    legs = [json.loads(line) for line in open(os.path.join(run, 'results.jsonl')) if line.strip()]
    bag = [os.path.join(run, 'bag', f) for f in sorted(os.listdir(os.path.join(run, 'bag'))) if f.endswith('.mcap')]
    data = d.read(os.path.join(run, 'bag'))
    t0 = legs[0]['t_start_sim']
    t1 = legs[-1]['t_start_sim'] + legs[-1]['sim_s']
    track, nxt = [], t0
    for t, m in data['/model/coco/odometry']:
        if t < t0 - 1e-6 or t > t1 + 0.05:
            continue
        if t + 1e-6 >= nxt:
            x, y, th = d.pose2d(m)
            track.append([round(t - t0, 2), round(x, 3), round(y, 3), round(th, 3)])
            nxt += 0.1
    doc = {
        'schema': 'coco_lab.stack_ghost', 'version': 1, 'evidence': 'STACK',
        'what': 'COCO driven by Nav2 in Gazebo Harmonic (the full ROS 2 stack, headless), recorded: Gazebo\'s ground truth',
        'not': ['no grasp: Nav2 drove the round\'s legs only, the arm did not move',
                'Gazebo\'s actors were parked at their paths\' start (no forklift or walker moved)',
                'never hardware: no physical robot exists'],
        'round': {k: goals.get(k) for k in ('rules', 'mode', 'seed', 'region', 'orders', 'ghost_m', 'reference_time_s', 'start')},
        'legs': [{'id': L['id'], 'status': L['status'], 'error_code': L.get('error_code'), 't0': round(L['t_start_sim'] - t0, 2),
                  'sim_s': L['sim_s'], 'driven_m': L['driven_m'], 'truth_to_goal_m': L.get('truth_to_goal_m')} for L in legs],
        'all_succeeded': all(L['status'] == 'SUCCEEDED' for L in legs),
        'driving_s': round(sum(L['sim_s'] for L in legs), 2), 'driven_m': round(sum(L['driven_m'] for L in legs), 3),
        'track_columns': ['t_s', 'x', 'y', 'yaw'], 'track': track,
        'source': {'run': os.path.basename(run.rstrip('/')), 'bag_sha256': {os.path.basename(b): sha(b) for b in bag},
                   'git_commit': meta.get('git_commit'), 'map_pgm_sha256': meta.get('map_pgm_sha256'),
                   'nav2_params_sha256': meta.get('nav2_params_sha256'), 'world_sha256': meta.get('world_sha256'),
                   'started_utc': meta.get('started_utc'), 'packages': meta.get('packages'),
                   'goals_sha256': sha(goals_path)},
    }
    text = json.dumps(doc, separators=(',', ':'), sort_keys=True) + '\n'
    with open(out, 'w') as f:
        f.write(text)
    print(json.dumps({'out': out, 'bytes': len(text), 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'legs': [(L['id'], L['status']) for L in doc['legs']],
                      'driving_s': doc['driving_s'], 'points': len(track)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
