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
Assemble runs.json from the three real runs' directories. Pure.

  python3 lab1c_runs.py --out runs.json RUN_DIR [RUN_DIR ...]

Each RUN_DIR holds what ``lab1c_run.sh run`` and ``lab_export`` wrote:
``meta.json`` (provenance), ``metrics.json`` (the export), ``checks.json``
(the live publisher/arbiter samples) and ``runner.log`` (PASS/FAIL
lines). Nothing is recomputed here except the start/middle/end selection
already in checks.json; every number is copied from those files.
"""

import argparse
import json
import os
import re
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def runner_lines(path):
    out = []
    with open(path) as f:
        for line in f:
            m = re.match(r'lab1c: (PASS|FAIL) (.*) \(\d\d:\d\d:\d\d UTC\)', line)
            if m:
                out.append([m.group(1), m.group(2)])
    return out


def check_summary(c):
    def pick(s):
        if not s:
            return None
        return {'wheel_publishers':
                s['publishers']['/diff_drive_controller/cmd_vel'],
                'arbiter_status': s['arbiter_status'],
                'lab_phase': s['lab_phase'],
                'lab_planner_violations': (s['lab_planner'] or {}).get(
                    'violations')}
    return {'samples': c['samples'], 'violation_count': c['violation_count'],
            'samples_without_arbiter_status':
                c.get('samples_without_arbiter_status'),
            'start': pick(c['start']), 'middle': pick(c['middle']),
            'end': pick(c['end'])}


def run_record(d):
    meta = load(os.path.join(d, 'meta.json'))
    rec = {'dir': d, 'meta': meta,
           'runner_checks': runner_lines(os.path.join(d, 'runner.log'))}
    mp = os.path.join(d, 'metrics.json')
    rec['metrics'] = load(mp) if os.path.exists(mp) else None
    cp = os.path.join(d, 'checks.json')
    rec['live_checks'] = check_summary(load(cp)) if os.path.exists(cp) \
        else None
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('runs', nargs='+')
    a = ap.parse_args()
    doc = {'schema': 'coco_lab.lab1c.runs/1',
           'runs': [run_record(d) for d in a.runs]}
    with open(a.out, 'w') as f:
        json.dump(doc, f, sort_keys=True, indent=1)
    for r in doc['runs']:
        m = r['metrics'] or {}
        print(r['meta']['run_id'], (m.get('result') or {}).get('phase'),
              m.get('duration_sim_s'), (m.get('tracking_error_m') or {})
              .get('mean'), m.get('recoveries_total'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
