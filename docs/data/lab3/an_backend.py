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
Phase 4: score one ROS SLAM backend run (``slam_replay.sh``) on its drive.

- **Trajectory**: the backend's ONLINE belief at every scan of the drive
  (``lab3_common.online_poses``: its latest ``map -> odom`` composed with
  the recorded wheel odometry), against the truth at the same stamps,
  ``coco_lab.mapeval.ate`` (rigid 2D alignment, no scale). The wheel
  odometry alone is scored the same way, as the baseline.
- **Map**: the backend's LAST ``/map``, moved into the truth's frame by
  that same alignment, resampled onto the truth raster (nearest), thresholded
  at nav2's 0.25 / 0.65, and scored by ``mapeval.score_map`` (tolerance
  0.10 m) against Phase 1B's ground truth.

Usage::

    python3 docs/data/lab3/an_backend.py DRIVE_DIR RUN_DIR [--out F]
"""

import argparse
import json
import os

import lab3_common as C
from coco_lab import mapeval


def score(drive_dir, run_dir, truth=None):
    drive = C.load_drive(drive_dir)
    with open(os.path.join(run_dir, 'record.json')) as f:
        rec = json.load(f)
    tmap, _ = C.ground_truth() if truth is None else truth
    gt = [tuple(r['truth']) for r in drive['rows']]
    T = mapeval.Truth(tmap, gt[0][:2])
    est, before = C.online_poses(drive, rec['map_to_odom'])
    a = mapeval.ate(est, gt, align=True)
    odom = mapeval.ate([tuple(r['odom']) for r in drive['rows']], gt,
                       align=True)
    out = {'run': os.path.abspath(run_dir), 'drive': os.path.abspath(
        drive_dir), 'n_scans': len(gt), 'scans_before_first_map_to_odom':
        before, 'map_to_odom_messages': len(rec['map_to_odom']),
        'maps_seen': rec['maps_seen'], 'ate_online': a,
        'ate_wheel_odometry': odom}
    m = rec['final_map']
    if m is None:
        out['map'] = None
    else:
        cells, w, h, res, origin = C.ros_grid_to_u8(m)
        on = mapeval.resample_onto(tmap, cells, w, h, res, origin,
                                   tuple(a['alignment']))
        from coco_lab.occgrid import GridParams, u8_to_labmap
        lm = u8_to_labmap(on, tmap.width, tmap.height, tmap.resolution,
                          tmap.origin, GridParams(
                              free_thresh=C.THRESHOLDS[0],
                              occupied_thresh=C.THRESHOLDS[1]))
        out['map'] = mapeval.score_map(T, lm, C.TOL)
        out['map_grid'] = {'width': w, 'height': h, 'resolution': res,
                           'origin': list(origin), 'stamp': m['stamp']}
    for name in ('meta.json', 'end.json'):
        p = os.path.join(run_dir, name)
        if os.path.exists(p):
            with open(p) as f:
                out[name.split('.')[0]] = json.load(f)
    return mapeval.round_floats(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('drive')
    ap.add_argument('run')
    ap.add_argument('--out')
    args = ap.parse_args(argv)
    res = score(args.drive, args.run)
    text = json.dumps(res, indent=1, sort_keys=True)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(text + '\n')
    s = {k: res[k] for k in ('ate_online', 'ate_wheel_odometry')}
    print(json.dumps({'ate_online_rmse': s['ate_online']['rmse'],
                      'odom_rmse': s['ate_wheel_odometry']['rmse'],
                      'map': res['map'] and {k: res['map'][k] for k in (
                          'precision', 'recall', 'f1', 'coverage')}},
                     indent=1))


if __name__ == '__main__':
    main()
