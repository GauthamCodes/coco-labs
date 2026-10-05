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
Phase 4: coco_lab's mapping and SLAM on a recorded drive, scored like a backend.

The SAME recorded drive the ROS backends replayed (``make_drive.py``): its
wheel odometry and its LiDAR (every 8th of 480 beams: 60, Sketch's
default), at the update rows ``coco_lab.mapworld.update_rows`` picks. The
idealised landmark observations EKF-SLAM needs are SYNTHESISED from the
recorded truth and the truth raster's corners (the robot has no landmark
sensor) -- EKF-SLAM's numbers are therefore NOT comparable with the LiDAR
SLAMs', and are labelled so.

**Arms** (every one on the same world, documented defaults otherwise):

``known``, ``odometry``
    occupancy mapping with the true / the dead-reckoned poses.
``pose_graph``, ``pose_graph_noloop``
    loop closure on / off -- the loop-closure effect; its odometry edges
    use the calibrated motion model below, as EKF-SLAM and FastSLAM do.
``ekf_slam``, ``fastslam``
    with the motion model CALIBRATED on a different drive: Lab 2's square
    drive (same session, not the tour) measured 2.445 rad of wheel-yaw
    error over 10.974 rad turned (``docs/data/lab2/fidelity/
    fidelity.json``), so ``alpha1 = (2.445 / 10.974)^2 = 0.0497``; the
    straight drives measured 0.000 m, so the other three alphas get a
    small floor, 0.005, CHOSEN, not measured.
``ekf_slam_amcl``, ``fastslam_amcl``
    with COCO's own AMCL alphas, 0.2 x 4 (``gazebo_models/config/
    nav2_params.yaml``) -- deliberately loose values for AMCL.

FastSLAM draws random numbers, so it is run with seeds 0..4 and every
seed is reported (one run is not a rate). Grid: the truth raster's
placement (0.05 m). The start pose is told (as ``/initialpose``).

Scoring is ``an_backend.py``'s: ATE after a rigid 2D alignment, and the
final map moved by that alignment and scored against Phase 1B's truth at
0.10 m. ``online`` = the estimate at each update as it ran; ``final`` = the
trajectory at the end (FastSLAM's surviving ancestry, the optimised pose
graph). Wall-clock time per run is reported (load average with it).

Usage::

    python3 docs/data/lab3/an_coco.py DRIVE_DIR --out F [--arms ...]
"""

import argparse
import json
import os
import time

import lab3_common as C
from coco_lab import mapeval, mapping, mapworld
from coco_lab.ekfslam import EKFSlamParams
from coco_lab.fastslam import FastSlamParams
from coco_lab.posegraph import PoseGraphParams
from coco_lab.sketch import COCO_LIDAR

BEAM_STEP = 8
SNAPSHOTS = 8
AMCL_ALPHAS = (0.2, 0.2, 0.2, 0.2)
FLOOR = 0.005
WORLD_SEED = 0
FASTSLAM_SEEDS = (0, 1, 2, 3, 4)
#: the arena's corners at 2 m spacing: 40, spread over the whole arena
#: (at 1 m and a cap of 32 they all fell in its southern half -- measured)
LANDMARKS = mapworld.LandmarkSpec(min_separation=2.0, max_count=64)
LAB2_FIDELITY = os.path.join(C.REPO, 'docs', 'data', 'lab2', 'fidelity',
                             'fidelity.json')
ARMS = ('known', 'odometry', 'pose_graph', 'pose_graph_noloop', 'ekf_slam',
        'ekf_slam_amcl', 'fastslam', 'fastslam_amcl')


def calibrated_alphas():
    """alpha1 from Lab 2's square drive (see the module docstring)."""
    with open(LAB2_FIDELITY) as f:
        d = json.load(f)
    sq = [r for r in d['drives'] if r['drive'] == 'square']
    if len(sq) != 1:
        raise SystemExit('expected exactly one square drive in Lab 2')
    sq = sq[0]
    a1 = (sq['gazebo']['final_yaw_err_rad'] / sq['rotation_rad']) ** 2
    return (a1, FLOOR, FLOOR, FLOOR), {
        'source': 'docs/data/lab2/fidelity/fidelity.json, drive square '
                  f'({sq["session"]})',
        'final_yaw_err_rad': sq['gazebo']['final_yaw_err_rad'],
        'rotation_rad': sq['rotation_rad'], 'alpha1': a1,
        'floor_chosen_not_measured': FLOOR}


def payload(drive):
    rows = drive['rows']
    li = dict(drive['lidar'])
    li['mount'] = list(COCO_LIDAR.mount)
    return {'lidar': li, 'beam_step': BEAM_STEP,
            't': [r['t'] for r in rows], 'gt': [r['truth'] for r in rows],
            'odom': [r['odom'] for r in rows],
            'ranges_full': [r['ranges'] for r in rows]}


def arm_runs(arm, cal):
    """Return ``[(label, algorithm, params)]`` for one arm."""
    if arm in ('known', 'odometry'):
        return [(arm, arm, mapping.GivenPoseParams(snapshots=SNAPSHOTS))]
    if arm == 'pose_graph':
        return [(arm, arm, PoseGraphParams(alphas=cal, snapshots=SNAPSHOTS))]
    if arm == 'pose_graph_noloop':
        return [(arm, 'pose_graph', PoseGraphParams(
            alphas=cal, snapshots=SNAPSHOTS, loop_closure=False))]
    alphas = AMCL_ALPHAS if arm.endswith('_amcl') else cal
    if arm.startswith('ekf_slam'):
        return [(arm, 'ekf_slam', EKFSlamParams(alphas=alphas,
                                                snapshots=SNAPSHOTS))]
    return [(f'{arm}@seed{s}', 'fastslam', FastSlamParams(
        alphas=alphas, snapshots=SNAPSHOTS, seed=s)) for s in FASTSLAM_SEEDS]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('drive')
    ap.add_argument('--out', required=True)
    ap.add_argument('--arms', nargs='+', default=list(ARMS))
    args = ap.parse_args(argv)
    cal, cal_doc = calibrated_alphas()
    drive = C.load_drive(args.drive)
    tmap, _ = C.ground_truth()
    t0 = time.perf_counter()
    world = mapworld.from_recorded(payload(drive), tmap, spec=LANDMARKS,
                                   seed=WORLD_SEED)
    if len(world.landmarks) >= LANDMARKS.max_count:
        raise SystemExit('landmark extraction hit max_count: it would '
                         'leave part of the arena without landmarks')
    inp = world.inputs()
    truth_poses = world.true_poses()
    T = mapeval.Truth(tmap, truth_poses[0][:2])
    out = {'drive': os.path.abspath(args.drive), 'n_rows': len(world.t),
           'n_updates': len(world.updates), 'beam_step': BEAM_STEP,
           'n_beams': world.lidar.samples, 'landmarks': len(world.landmarks),
           'landmark_spec': LANDMARKS.to_dict(),
           'landmark_observations': sum(map(len, world.observations)),
           'world_build_s': time.perf_counter() - t0,
           'alphas': {'amcl': list(AMCL_ALPHAS), 'calibrated': list(cal),
                      'calibration': cal_doc},
           'loadavg_start': open('/proc/loadavg').read().split()[:3],
           'runs': {}}
    for arm in args.arms:
        for label, alg, params in arm_runs(arm, cal):
            t1 = time.perf_counter()
            tr = mapping.run(alg, inp, tmap, params, true_poses=truth_poses)
            wall = time.perf_counter() - t1
            g = tr.header['grid']
            online = mapeval.ate(tr.estimates(), truth_poses, align=True)
            final = mapeval.ate(tr.final_trajectory(), truth_poses,
                                align=True)
            s = mapeval.score_run(T, tr.maps[-1], g, tr.final_trajectory(),
                                  truth_poses, True, C.THRESHOLDS, C.TOL)
            rec = {'arm': arm, 'algorithm': alg, 'wall_s': wall,
                   'ate_online': online, 'ate_final': final,
                   'map': s['map'], 'params': tr.header['params']}
            if alg == 'pose_graph':
                a = tr.arrays
                rec['loop_closures'] = len(a['loops.k'][1])
                rec['icp_edges'] = sum(tr.columns['icp_ok'])
                rec['optimisations'] = len(a['opt.k'][1])
            if alg == 'fastslam':
                rec['resampled'] = sum(tr.columns['resampled'])
            out['runs'][label] = rec
            print(f"{label:22s} {wall:6.1f}s ATE online "
                  f"{online['rmse']:.3f} final {final['rmse']:.3f}  "
                  f"F1 {s['map']['f1']:.3f} P {s['map']['precision']:.3f} "
                  f"R {s['map']['recall']:.3f}", flush=True)
    out['loadavg_end'] = open('/proc/loadavg').read().split()[:3]
    out['command'] = 'python3 docs/data/lab3/an_coco.py ' + ' '.join(
        argv if argv is not None else __import__('sys').argv[1:])
    with open(args.out, 'w') as f:
        f.write(json.dumps(mapeval.round_floats(out), indent=1,
                           sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
