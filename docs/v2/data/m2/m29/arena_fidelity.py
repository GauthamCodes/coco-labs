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
The Arena's fidelity against the full stack in Gazebo (M2.9).

No ROS. Inputs held fixed: Lab 2's two recorded fidelity sessions
(``~/coco_lab_runs/lab2/fidelity_1``, ``fidelity_s1``; the same files
``docs/data/lab2/an_fidelity.py`` measured Sketch from), Lab 2's loaders
and statistics (imported from that file, unchanged), and the M2.5
controller comparison (``docs/v2/data/m2/m25/move_comparison.json``).
What changes is the model under test: the ARENA (``coco_lab.arena``), not
Lab 2's Sketch.

1. **LiDAR at identical poses.** Each recorded scan's TRUE pose (tilt at
   most 2 degrees) is cast by the Arena's own ray caster on the Arena's
   world (``worlds/coco_arena_v1.yaml`` rasterised at 0.05 m, map frame),
   all 480 beams, no range noise; ``e = gazebo - arena`` per beam.
2. **Odometry, straight and turning, slip off and on.** Each scripted
   drive's recorded command sequence is replayed tick for tick through the
   Arena's motion functions (``step_pose``; the wheels do the command; with
   ``arena.slip=on`` the body turns ``SLIP_TURN`` of it) and its odometry
   noise (``sample_delta`` with the Arena's ``ODOM_ALPHAS``, 200 seeds).
   Reported against Gazebo's wheel-odometry error on the same drive, and
   the Arena's TRUE end pose against Gazebo's true end pose (what the same
   commands did to the body in each world).
3. **Controller tracking** against the Lab 5 recordings: the M2.5 numbers,
   re-tabulated (nothing re-run).

Usage::

    python3 docs/v2/data/m2/m29/arena_fidelity.py ~/coco_lab_runs/lab2/fidelity_1 \\
        ~/coco_lab_runs/lab2/fidelity_s1 --out docs/v2/data/m2/m29/fidelity_v1.json
"""

import argparse
import importlib.util
import json
import math
import os
import platform
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.dont_write_bytecode = True

import yaml  # noqa: E402
from coco_lab import arena as A  # noqa: E402

_spec = importlib.util.spec_from_file_location('an_fidelity', os.path.join(REPO, 'docs', 'data', 'lab2', 'an_fidelity.py'))
LAB2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LAB2)
INF = math.inf
SEEDS = 200


def world():
    with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as f:
        return A.Arena(yaml.safe_load(f), 1)


def scans(sessions, max_tilt_deg=2.0):
    """Gazebo's ranges against the Arena's ray caster at the recorded true poses."""
    a = world()
    assert a.lidar.samples == 480 and a.range_sigma == 0.0
    classes = {'both': 0, 'gz_only': 0, 'arena_only': 0, 'neither': 0}
    err, absd, excluded, per_pose = [], [], [], []
    # the same poses cast by Lab 2's Sketch on the Nav2 map: are the two worlds the same to the LiDAR?
    nav = LAB2.sketch.SketchMap(LAB2.maps.load_nav2(LAB2.NAV_YAML))
    same = differ = 0
    n = 0
    for sess in sessions:
        for line in open(os.path.join(sess, 'scans.jsonl')):
            r = json.loads(line)
            n += 1
            _, x, y, yaw, _, tilt = r['truth']
            if math.degrees(tilt) > max_tilt_deg:
                excluded.append({'session': os.path.basename(sess), 'i': r['i'], 'tilt_deg': math.degrees(tilt)})
                continue
            assert abs(r['angle_min'] - a.lidar.angle_min) < 1e-6 and len(r['ranges']) == 480
            ar = a.smap.scan((x, y, yaw), a.lidar, a.angles)
            sk = nav.scan((x, y, yaw), LAB2.sketch.COCO_LIDAR, LAB2.sketch.COCO_LIDAR.angles())
            for u, w in zip(ar, sk):
                same, differ = (same + 1, differ) if (u == w or abs(u - w) < 1e-9) else (same, differ + 1)
            pe = []
            for g, s in zip(r['ranges'], ar):
                g = INF if g is None else g
                s = s if a.lidar.range_min <= s <= a.lidar.range_max else INF
                if g < INF and s < INF:
                    classes['both'] += 1
                    err.append(g - s)
                    absd.append(abs(g - s))
                    pe.append(abs(g - s))
                elif g < INF:
                    classes['gz_only'] += 1
                elif s < INF:
                    classes['arena_only'] += 1
                else:
                    classes['neither'] += 1
            per_pose.append({'session': os.path.basename(sess), 'i': r['i'], 'k': r['k'], 'pose': [x, y, yaw],
                             'median_abs_e': LAB2.pct(pe, 50) if pe else None,
                             'p90_abs_e': LAB2.pct(pe, 90) if pe else None})
    return {
        'scans_recorded': n, 'scans_used': n - len(excluded), 'scans_excluded_tilt': excluded,
        'beams': sum(classes.values()), 'classes': classes,
        'error_m': LAB2.dist_summary(err), 'abs_error_m': LAB2.dist_summary(absd),
        'frac_abs_below': {f'{t:.2f}': sum(1 for v in absd if v < t) / len(absd) for t in (0.01, 0.02, 0.05, 0.10, 0.25)},
        'vs_sketch_on_nav2_map': {'beams_identical': same, 'beams_different': differ},
        'per_pose_worst': sorted([p for p in per_pose if p['p90_abs_e']], key=lambda p: -p['p90_abs_e'])[:40],
    }


def replay(start, cmds, dts, slip, alphas, seed):
    """The Arena's truth and odometry (placed by ``start``) for a command sequence."""
    rng = random.Random(random.Random(seed).getrandbits(64))
    pose, odom = start, (0.0, 0.0, 0.0)
    for (v, w), dt in zip(cmds, dts):
        wheels = A.step_pose(pose, v, w, dt)
        new = A.step_pose(pose, v, w * A.SLIP_TURN, dt) if slip else wheels
        r1, t, r2 = A.odom_delta(pose, wheels)
        odom = A.apply_delta(odom, *A.sample_delta(r1, t, r2, alphas, rng))
        pose = new
    return pose, LAB2.compose(start, odom)


def err(od, tr):
    return math.hypot(od[0] - tr[0], od[1] - tr[1]), abs(A.wrap(od[2] - tr[2]))


def drives(sessions):
    """Per scripted drive: Gazebo's odometry error and the Arena's, slip off and on."""
    out = []
    for sess in sessions:
        rows = [json.loads(line) for line in open(os.path.join(sess, 'drives.jsonl'))]
        for label in dict.fromkeys(r['label'] for r in rows):
            ticks = [r for r in rows if r['label'] == label and r['kind'] == 'drive']
            end = [r for r in rows if r['label'] == label and r['kind'] == 'drive_end']
            if not ticks or not end:
                continue
            end = end[0]
            seq = ticks + [end]
            gt0 = tuple(ticks[0]['truth'][1:4])
            place = LAB2.compose(gt0, LAB2.inverse(tuple(ticks[0]['odom'][1:4])))
            dist = sum(math.hypot(b['truth'][1] - a['truth'][1], b['truth'][2] - a['truth'][2]) for a, b in zip(seq, seq[1:]))
            rot = sum(abs(A.wrap(b['truth'][3] - a['truth'][3])) for a, b in zip(seq, seq[1:]))
            wheel_rot = sum(abs(A.wrap(b['odom'][3] - a['odom'][3])) for a, b in zip(seq, seq[1:]))
            gt_end = tuple(end['truth'][1:4])
            gz_pos, gz_yaw = err(LAB2.compose(place, tuple(end['odom'][1:4])), gt_end)
            cmds = [tuple(r['cmd']) for r in ticks]
            dts = [b['t'] - a['t'] for a, b in zip(ticks, ticks[1:])] + [0.1]
            arms = {}
            for slip in (False, True):
                tr0, od0 = replay(gt0, cmds, dts, slip, (0, 0, 0, 0), 0)
                pos0, yaw0 = err(od0, tr0)
                noisy = [err(*replay(gt0, cmds, dts, slip, A.ODOM_ALPHAS, s)[::-1]) for s in range(SEEDS)]
                arms['slip_on' if slip else 'slip_off'] = {
                    'zero_noise': {'final_pos_err_m': pos0, 'final_yaw_err_rad': yaw0},
                    'default_noise': {'alphas': list(A.ODOM_ALPHAS), 'seeds': SEEDS,
                                      'final_pos_err_m': LAB2.dist_summary([p for p, _ in noisy]),
                                      'final_yaw_err_rad': LAB2.dist_summary([y for _, y in noisy])},
                    'truth_end_vs_gazebo_truth_m': math.hypot(tr0[0] - gt_end[0], tr0[1] - gt_end[1]),
                    'truth_end_yaw_vs_gazebo_rad': abs(A.wrap(tr0[2] - gt_end[2])),
                }
            out.append({'session': os.path.basename(sess), 'drive': label, 'status': end['status'],
                        'distance_m': dist, 'rotation_rad': rot, 'wheel_odom_rotation_rad': wheel_rot,
                        # what the slip option models: how much more the wheels say it turned than it did
                        'yaw_overcount': {'gazebo': wheel_rot / rot if rot >= 1.0 else None,
                                          'arena_slip_off': 1.0 if rot >= 1.0 else None,
                                          'arena_slip_on': 1.0 / A.SLIP_TURN if rot >= 1.0 else None},
                        'gazebo': {'final_pos_err_m': gz_pos, 'final_yaw_err_rad': gz_yaw}, 'arena': arms})
    return out


def tracking():
    """M2.5's tracking error, model against stack, per scenario and controller."""
    d = json.load(open(os.path.join(REPO, 'docs', 'v2', 'data', 'm2', 'm25', 'move_comparison.json')))
    pair = {'DWB': 'dwa', 'RPP': 'rpp', 'MPPI': 'mppi'}
    rows = []
    for sc, v in d['scenarios'].items():
        for stack_name, model_name in pair.items():
            s, m = v['stack'][stack_name], v['model'][model_name]['summary']
            rows.append({'scenario': sc, 'stack_controller': stack_name, 'model_controller': model_name.upper(),
                         'stack_outcomes': s['outcomes'], 'model_outcomes': m['outcomes'],
                         'stack_tracking_mean_m': s['tracking_mean_m'], 'model_tracking_mean_m': m['tracking_mean_m'],
                         'stack_tracking_max_m': s['tracking_max_m'], 'model_tracking_max_m': m['tracking_max_m']})
    return {'source': 'docs/v2/data/m2/m25/move_comparison.json', 'rows': rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('sessions', nargs=2)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    sessions = [os.path.expanduser(s) for s in a.sessions]
    result = {
        'tool': 'docs/v2/data/m2/m29/arena_fidelity.py', 'evidence': {'model': 'MODEL', 'reference': 'STACK'},
        'python': platform.python_version(),
        'sessions': [os.path.basename(s) for s in sessions],
        'session_meta': [{k: json.load(open(os.path.join(s, 'meta.json'))).get(k) for k in ('git_commit', 'started_utc')}
                         for s in sessions],
        'world': 'worlds/coco_arena_v1.yaml (0.05 m, map frame)',
        'slip_turn': A.SLIP_TURN,
        'scans': scans(sessions),
        'drives': drives(sessions),
        'tracking': tracking(),
        'sketch_reference': 'docs/data/lab2/fidelity/fidelity.json (Lab 2: the same sessions against Sketch on the Nav2 map)',
    }
    with open(a.out, 'w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.write('\n')
    s = result['scans']
    print('vs sketch', s['vs_sketch_on_nav2_map'])
    print('scans', s['scans_used'], 'of', s['scans_recorded'], s['classes'], 'abs median %.4f p95 %.4f p99 %.4f' % (
        s['abs_error_m']['median'], s['abs_error_m']['p95'], s['abs_error_m']['p99']))
    for d in result['drives']:
        print(d['session'], d['drive'], 'overcount', d['yaw_overcount'], round(d['distance_m'], 1), round(d['rotation_rad'], 1), 'wheel rot', round(d['wheel_odom_rotation_rad'], 1),
              'gz', round(d['gazebo']['final_pos_err_m'], 3), {k: round(v['default_noise']['final_pos_err_m']['median'], 3) for k, v in d['arena'].items()},
              'slip0', round(d['arena']['slip_on']['zero_noise']['final_pos_err_m'], 3))
    return 0


if __name__ == '__main__':
    sys.exit(main())
