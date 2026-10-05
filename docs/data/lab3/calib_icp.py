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
Phase 4: how good is one scan match? Calibrated on a drive NOT scored.

The pose graph treats a scan match as ONE measurement of standard deviation
``icp_sigma`` (``coco_lab.posegraph``): its information is
``H / (N sigma^2)``, H the ICP Hessian over N matched points. This script
measures that sigma on Lab 2's SQUARE drive (session ``fidelity_s1``, the
same recording, not the tours that are scored): for every consecutive pair
of updates, the scan match from odometry's guess (no prior), its error
``e`` against the TRUE relative pose, and ``e^T (H/N) e``. If the model is
right, ``e^T (H / (N sigma^2)) e`` is chi-squared with 3 degrees of
freedom, mean 3, so ``sigma^2 = mean(e^T (H/N) e) / 3``. Accepted matches
only (the front end's own rmse / inlier test).

The same measurement is made for SKETCH on Lab 2's twins room (no Lab 3
claim uses it), at the Lab 3 scenes' noise (``--sketch``): Sketch's LiDAR
has 2 cm range noise, Gazebo's none, so the two differ, and each world
gets its own.

Usage::

    python3 docs/data/lab3/calib_icp.py DRIVE_DIR [--out F]
    python3 docs/data/lab3/calib_icp.py --sketch [--out F]
"""

import argparse
import json
import math
import statistics

import an_coco as A
import lab3_common as C
from coco_lab import mapeval, mapworld
from coco_lab import posegraph as pg
from coco_lab.sketch import apply_delta, odom_delta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('drive', nargs='?')
    ap.add_argument('--sketch', action='store_true')
    ap.add_argument('--out')
    args = ap.parse_args(argv)
    if args.sketch:
        from coco_lab import loc_teaching, map_teaching
        from coco_lab.sketch import Scenario
        m = loc_teaching.twins_map()
        route = [(2.0, 1.2), (10.0, 1.2), (10.0, 6.8), (2.0, 6.8), (2.0, 1.2)]
        sc = Scenario(start=(1.5, 1.2, 0.0), route=route, seed=0,
                      noise=map_teaching.noise(), max_time=900.0)
        w = mapworld.from_sketch(m, sc)
        args.drive = 'sketch: loc_twins, seed 0, the Lab 3 scenes\' noise'
    else:
        drive = C.load_drive(args.drive)
        tmap, _ = C.ground_truth()
        w = mapworld.from_recorded(A.payload(drive), tmap, spec=A.LANDMARKS)
    inp, tp = w.inputs(), w.true_poses()
    p = pg.PoseGraphParams()
    ang = inp.angles()
    li = inp.lidar
    pts = [pg.scan_points(z, ang, li.mount, li.range_min, li.range_max)
           for z in inp.ranges]
    q, errs, used = [], [], 0
    for k in range(1, len(inp)):
        d = odom_delta(inp.odom[k - 1], inp.odom[k])
        guess = apply_delta((0.0, 0.0, 0.0), *d)
        r = pg.icp(pts[k - 1], pts[k], guess, max_dist=p.icp_max_dist)
        if not (r.converged and r.rmse <= p.icp_max_rmse and
                r.inliers >= p.icp_min_inliers):
            continue
        used += 1
        true = pg.between(tp[k - 1], tp[k])
        e = (r.pose[0] - true[0], r.pose[1] - true[1],
             math.remainder(r.pose[2] - true[2], 2 * math.pi))
        n = max(1, r._n)
        q.append(sum(e[a] * r.hessian[a][b] * e[b] / n
                     for a in range(3) for b in range(3)))
        errs.append((math.hypot(e[0], e[1]), abs(e[2])))
    sigma = math.sqrt(statistics.mean(q) / 3)
    out = {
        'drive': args.drive, 'updates': len(inp), 'matches_accepted': used,
        'icp_sigma': sigma,
        'icp_sigma_from_median': math.sqrt(statistics.median(q) / 2.366),
        'translation_error_m': {'median': statistics.median(e[0] for e in
                                                           errs),
                                'max': max(e[0] for e in errs)},
        'rotation_error_rad': {'median': statistics.median(e[1] for e in
                                                           errs),
                               'max': max(e[1] for e in errs)},
        'definition': 'sigma^2 = mean(e^T (H/N) e) / 3 over accepted '
                      'consecutive matches; median-based value uses the '
                      'chi2(3) median 2.366',
    }
    text = json.dumps(mapeval.round_floats(out, 6), indent=1, sort_keys=True)
    print(text)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(text + '\n')


if __name__ == '__main__':
    main()
