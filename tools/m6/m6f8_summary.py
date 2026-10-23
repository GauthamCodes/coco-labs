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
M6F.8: the committed summary of raw run directories (raw logs stay in ~/coco_lab_runs/m6/).

    m6f8_summary.py OUT.json RUN_DIR [RUN_DIR ...]

Per run: meta.json, each goal's row from results.jsonl (status, Nav2 error code and its
name, simulated seconds, driven metres, ground truth's and AMCL's distance), and the sha256
of every file in the run directory (bag included), so the raw evidence can be re-checked.
"""
import hashlib
import json
import os
import sys

#: nav2_msgs (Jazzy) result codes seen in these runs; the .action files are the source
CODES = {0: 'NONE', 103: 'FollowPath INVALID_PATH', 205: 'ComputePathToPose START_OCCUPIED'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def run(d):
    meta = json.load(open(os.path.join(d, 'meta.json')))
    rows = [json.loads(line) for line in open(os.path.join(d, 'results.jsonl'))]
    keep = ('id', 'label', 'goal', 'status', 'error_code', 'error_msg', 'sim_s', 'wall_s',
            'driven_m', 'truth_to_goal_m', 'amcl_error_m', 'end_truth', 'end_amcl',
            'reset_to_start')
    goals = [dict({k: r.get(k) for k in keep}, error_name=CODES.get(r.get('error_code')))
             for r in rows]
    files = {}
    for root, _, names in os.walk(d):
        for n in sorted(names):
            p = os.path.join(root, n)
            files[os.path.relpath(p, d)] = {'bytes': os.path.getsize(p), 'sha256': sha(p)}
    real = [g for g in goals if (g['driven_m'] or 0) > 0 or g['status'] != 'SUCCEEDED']
    return {'run': os.path.basename(d.rstrip('/')), 'raw_dir': d.replace(os.path.expanduser('~'), '~'),
            'meta': meta, 'goals': goals,
            'succeeded': sum(g['status'] == 'SUCCEEDED' for g in goals), 'of': len(goals),
            'succeeded_with_driving': sum(g['status'] == 'SUCCEEDED' and (g['driven_m'] or 0) > 0
                                          for g in goals), 'legs_with_driving_or_failed': len(real),
            'files': files}


def main():
    out, dirs = sys.argv[1], sys.argv[2:]
    doc = {'about': 'M6F.8 Gazebo + Nav2 on the Depot (tools/m6/m6f8_summary.py); STACK evidence',
           'error_codes': {str(k): v for k, v in CODES.items()},
           'runs': [run(os.path.abspath(d)) for d in dirs]}
    with open(out, 'w') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    for r in doc['runs']:
        print(r['run'], f"{r['succeeded']}/{r['of']}", 'files', len(r['files']))


if __name__ == '__main__':
    main()
