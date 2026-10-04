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
AMCL on wheel odometry vs AMCL on robot_localization's: the summary.

Reads ``amcl_replay.py``'s JSON lines (one file per session, drive and
arm) and reports, per drive and arm, the AMCL pose's error to the truth at
the pose's own stamp: mean, max and final position error, final heading
error, and the number of AMCL poses. Same session, same drive, same scans:
only the odometry AMCL was given differs.

Usage::

    python3 docs/data/lab2/an_amcl.py RUN_DIR... --out docs/data/lab2/amcl_odom.json
"""

import argparse
import glob
import json
import math
import os
import sys


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def summarise(path):
    rows = [json.loads(line) for line in open(path)]
    meta = rows[0]
    pts = [r for r in rows[1:] if r['kind'] == 'amcl'
           and meta['t0'] <= r['t'] <= meta['t1'] + 1.0]
    if not pts:
        return dict(meta, n=0)
    err = [math.hypot(r['amcl'][0] - r['truth'][0],
                      r['amcl'][1] - r['truth'][1]) for r in pts]
    yaw = [abs(wrap(r['amcl'][2] - r['truth'][2])) for r in pts]
    return {
        'session': meta['session'], 'drive': meta['drive'],
        'arm': meta['arm'], 'n': len(pts), 'play_rc': meta['play_rc'],
        'mean_err_xy': sum(err) / len(err), 'max_err_xy': max(err),
        'final_err_xy': err[-1], 'final_err_yaw': yaw[-1],
        'max_truth_dt': max(abs(r['truth_dt']) for r in pts),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    rows = []
    for d in args.dirs:
        for p in sorted(glob.glob(os.path.join(d, '*.jsonl'))):
            rows.append(summarise(p))
    for r in rows:
        if r.get('n'):
            print(f"{r['session']}/{r['drive']}/{r['arm']:5s} n={r['n']:4d} "
                  f"mean {r['mean_err_xy']:.3f} max {r['max_err_xy']:.3f} "
                  f"final {r['final_err_xy']:.3f} m")
        else:
            print(f"{r.get('session')}/{r.get('drive')}/{r.get('arm')}: "
                  f"no AMCL poses (VOID)")
    result = {
        'tool': 'docs/data/lab2/an_amcl.py',
        'command': 'python3 docs/data/lab2/an_amcl.py ' + ' '.join(
            os.path.basename(os.path.normpath(d)) for d in args.dirs),
        'definition': (
            'amcl_replay.py: per recorded drive, a fresh map_server + AMCL '
            '(the session\'s merged mission parameters, initial pose = the '
            'truth at the drive\'s start) on a private domain, the bag '
            'played from the drive\'s start at 1x; arms differ ONLY in the '
            'odom -> base_footprint transform: the recorded wheel '
            'odometry, or robot_localization (ekf_odom_imu.yaml, '
            'publish_tf on) fed the recorded wheel twist and gyro.'),
        'cite': 'docs/RESULTS.md "COCO Lab Phase 3"; '
                'docs/data/lab2/amcl_odom.json',
        'drives': rows,
    }
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
