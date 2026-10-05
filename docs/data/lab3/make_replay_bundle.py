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
Phase 4: one recorded drive and everything run on it, as ONE map bundle.

The Lab 3 page's Replay: COCO's real 121 m tour (``make_drive.py``),
coco_lab's runs on it (``an_coco.py``'s settings: 60 beams, the
square-drive-calibrated motion model, FastSLAM seed 0) and the ROS
backends' measured runs on the SAME drive (``slam_replay.sh`` outputs):
their online trajectories at the same update rows and their final maps,
carried as data and scored by the same coco_lab code.

The truth is Phase 1B's ground-truth raster (``lab3_common``); scoring
aligns every trajectory rigidly (no SLAM here was given the map frame, and
the backends were not given the start). coco_lab's runs are replayed byte
for byte at site build; the external runs are data with provenance.

Usage::

    python3 docs/data/lab3/make_replay_bundle.py DRIVE_DIR OUT_DIR \\
        RUN_DIR [RUN_DIR ...]
"""

import argparse
import json
import os

import an_coco as A
import lab3_common as C
from coco_lab import bundle, mapworld, slambundle
from coco_lab.ekfslam import EKFSlamParams
from coco_lab.fastslam import FastSlamParams
from coco_lab.mapping import GivenPoseParams
from coco_lab.posegraph import PoseGraphParams

SNAPSHOTS = 6


def specs(cal):
    return [
        ('known', 'known', GivenPoseParams(snapshots=SNAPSHOTS)),
        ('odometry', 'odometry', GivenPoseParams(snapshots=SNAPSHOTS)),
        ('ekf_slam', 'ekf_slam', EKFSlamParams(alphas=cal,
                                               snapshots=SNAPSHOTS)),
        ('fastslam', 'fastslam', FastSlamParams(alphas=cal, seed=0,
                                                snapshots=SNAPSHOTS)),
        ('pose_graph', 'pose_graph', PoseGraphParams(alphas=cal,
                                                    snapshots=SNAPSHOTS)),
        ('pose_graph_noloop', 'pose_graph', PoseGraphParams(
            alphas=cal, snapshots=SNAPSHOTS, loop_closure=False)),
    ]


def external(run_dir, drive, updates):
    """An ExternalRun from a slam_replay.sh directory (scored later)."""
    with open(os.path.join(run_dir, 'record.json')) as f:
        rec = json.load(f)
    with open(os.path.join(run_dir, 'meta.json')) as f:
        meta = json.load(f)
    est, _ = C.online_poses(drive, rec['map_to_odom'])
    cells, w, h, res, origin = C.ros_grid_to_u8(rec['final_map'])
    eid = f"{meta['backend']}_{meta['arm']}"
    return slambundle.ExternalRun(
        eid, meta['backend'], meta['arm'], [est[r] for r in updates], cells,
        {'width': w, 'height': h, 'resolution': res,
         'origin': list(origin)},
        {'run': os.path.basename(os.path.normpath(run_dir)),
         'record_sha256': C.sha256_file(os.path.join(run_dir,
                                                      'record.json')),
         'backend_version': meta.get('slam_toolbox') if meta['backend'] ==
         'slam_toolbox' else 'ros-jazzy-cartographer-ros 2.0.9003 (released '
         'deb, user-space prefix)',
         'rate_requested': meta.get('rate'),
         'started_utc': meta.get('started_utc'),
         'online': 'the latest map->odom at each scan, composed with the '
                   'recorded wheel odometry'})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('drive')
    ap.add_argument('out')
    ap.add_argument('runs', nargs='+')
    args = ap.parse_args(argv)
    cal, cal_doc = A.calibrated_alphas()
    drive = C.load_drive(args.drive)
    with open(os.path.join(args.drive, 'drive_meta.json')) as f:
        dmeta = json.load(f)
    tmap, _ = C.ground_truth()
    world = mapworld.from_recorded(A.payload(drive), tmap, spec=A.LANDMARKS,
                                   seed=A.WORLD_SEED)
    world.recorded = {
        'drive': os.path.basename(os.path.normpath(args.drive)),
        'session': os.path.basename(dmeta['session']),
        'window_sim_s': dmeta['window_sim_s'],
        'beam_step': A.BEAM_STEP,
        'landmarks': 'IDEALISED: synthesised from the recorded truth and '
                     'the truth raster; COCO has no landmark sensor',
        'calibration': cal_doc,
        'command': 'python3 docs/data/lab3/make_replay_bundle.py ' + ' '.join(
            os.path.basename(os.path.normpath(p)) for p in
            [args.drive] + args.runs),
    }
    bag = os.path.join(args.drive, 'bag')
    mcap = [n for n in sorted(os.listdir(bag)) if n.endswith('.mcap')][0]
    prov = bundle.make_provenance(
        'recorded-run', seed=A.WORLD_SEED,
        git=bundle.git_provenance(C.REPO),
        rosbag={'sha256': C.sha256_file(os.path.join(bag, mcap)),
                'sim_time_start': dmeta['window_sim_s'][0],
                'sim_time_end': dmeta['window_sim_s'][1]},
        tool='docs/data/lab3/make_replay_bundle.py')
    ext = [external(r, drive, world.updates) for r in args.runs]
    sb = slambundle.SlamBundle.compute(tmap, world, specs(cal), prov,
                                       align=True, external=ext)
    digest = slambundle.write_slam_bundle(sb, args.out, 'gzip')
    size = sum(os.path.getsize(os.path.join(args.out, n))
               for n in os.listdir(args.out))
    print(digest, size, 'bytes')
    for rid, tr in sb.runs:
        s = tr.summary
        print(f"{rid:20s} final ATE {s['ate_final']['rmse']:.3f} "
              f"F1 {s['map']['f1']:.3f}")
    for e in sb.external:
        print(f"{e.id:20s} online ATE {e.summary['ate_online']['rmse']:.3f} "
              f"F1 {e.summary['map']['f1']:.3f}")


if __name__ == '__main__':
    main()
