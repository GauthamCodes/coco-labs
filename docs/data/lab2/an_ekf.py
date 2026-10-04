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
robot_localization (wheel odometry + gyro) against wheel odometry alone.

Identical recorded conditions: every estimate here comes from ONE recorded
fidelity session -- its wheel odometry (``/diff_drive_controller/odom``),
its gyro, its truth (``/model/coco/odometry``) and its live AMCL pose --
and the EKF output that ``rl_replay.sh`` produced from that same bag.

Per scripted drive (``drives.jsonl``: straight, square, tour), each
odometry estimate is anchored to the truth at the drive's first tick (the
same placement ``an_fidelity.py`` uses) and its error to the truth is
taken at every truth sample: final and maximum position error, final yaw
error. (The live AMCL pose is NOT a baseline here: the fidelity session
teleports the robot between scans, so AMCL was kidnapped before the
drives; AMCL on each odometry is ``amcl_replay.py``'s job.)

Usage (in the ROS environment, for rosbag2_py)::

    python3 docs/data/lab2/an_ekf.py SESSION_DIR:RL_DIR [...] --out F.json
"""

import argparse
import bisect
import json
import math
import os
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

WORLD_TO_MAP = (2.0, 0.0)
ADOPTED = ('coco_lab_ros/config/ekf_odom_imu.yaml: the wheels\' pose x, y '
           'differentiated + the gyro\'s yaw rate (not the wheels\' heading '
           'or yaw rate, not the IMU orientation); robot_localization\'s '
           'ekf_node replayed offline at 1x on each session\'s own bag '
           '(rl_replay.sh). Gazebo\'s gyro is noiseless: an upper bound for '
           'a real one.')


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def compose(a, b):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            wrap(a[2] + b[2]))


def inverse(a):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-c * a[0] - s * a[1], s * a[0] - c * a[1], -a[2])


def read(bag, topics):
    """{topic: [(t_header, x, y, yaw)]} from a bag, header-stamped."""
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=list(topics)))
    out = {t: [] for t in topics}
    while r.has_next():
        topic, data, _ = r.read_next()
        m = deserialize_message(data, get_message(types[topic]))
        st = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        p = m.pose.pose
        out[topic].append((st, p.position.x, p.position.y,
                           yaw_of(p.orientation)))
    for t in out:
        out[t].sort()
    return out


def at(series, t):
    """The sample nearest ``t`` (series sorted by time)."""
    i = bisect.bisect_left(series, (t,))
    cands = [series[j] for j in (i - 1, i) if 0 <= j < len(series)]
    return min(cands, key=lambda s: abs(s[0] - t))


def segments(drives_jsonl):
    rows = [json.loads(line) for line in open(drives_jsonl)]
    out = []
    for label in dict.fromkeys(r['label'] for r in rows):
        ticks = [r for r in rows if r['label'] == label and r['kind'] == 'drive']
        end = [r for r in rows if r['label'] == label
               and r['kind'] == 'drive_end']
        if ticks and end:
            out.append((label, ticks[0]['truth'][0], end[0]['truth'][0]))
    return out


def score(truth, est, t0, t1):
    """Anchor ``est`` to the truth at t0; errors over [t0, t1]."""
    g0 = at(truth, t0)[1:]
    e0 = at(est, t0)[1:]
    place = compose(g0, inverse(e0))
    worst = 0.0
    last = None
    n = 0
    for s in truth:
        if s[0] < t0 or s[0] > t1:
            continue
        e = at(est, s[0])
        if abs(e[0] - s[0]) > 0.2:
            continue  # no estimate near this instant
        p = compose(place, e[1:])
        err = math.hypot(p[0] - s[1], p[1] - s[2])
        worst = max(worst, err)
        last = (err, abs(wrap(p[2] - s[3])))
        n += 1
    return {'final_pos_err_m': last[0], 'final_yaw_err_rad': last[1],
            'max_pos_err_m': worst, 'samples': n}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('pairs', nargs='+', help='SESSION_DIR:RL_DIR')
    ap.add_argument('--out', required=True)
    ap.add_argument('--config', default=ADOPTED,
                    help='what configuration the RL_DIRs were replayed with')
    args = ap.parse_args(argv)
    drives = []
    for pair in args.pairs:
        sess, rl = pair.split(':')
        src = read(os.path.join(sess, 'bag'),
                   ['/model/coco/odometry', '/diff_drive_controller/odom'])
        ekf = read(os.path.join(rl, 'rl_bag'), ['/odometry/filtered'])
        truth = [(t, x + WORLD_TO_MAP[0], y + WORLD_TO_MAP[1], th)
                 for t, x, y, th in src['/model/coco/odometry']]
        for label, t0, t1 in segments(os.path.join(sess, 'drives.jsonl')):
            dist = rot = 0.0
            seg = [s for s in truth if t0 <= s[0] <= t1]
            for a, b in zip(seg, seg[1:]):
                dist += math.hypot(b[1] - a[1], b[2] - a[2])
                rot += abs(wrap(b[3] - a[3]))
            drives.append({
                'session': os.path.basename(sess), 'drive': label,
                't0': t0, 't1': t1, 'distance_m': dist, 'rotation_rad': rot,
                'wheel_odom': score(truth, src['/diff_drive_controller/odom'],
                                    t0, t1),
                'ekf': score(truth, ekf['/odometry/filtered'], t0, t1),
            })
            d = drives[-1]
            print(f"{d['session']}/{label}: {dist:.1f} m {rot:.1f} rad | "
                  f"wheel final {d['wheel_odom']['final_pos_err_m']:.3f} m "
                  f"max {d['wheel_odom']['max_pos_err_m']:.3f} | EKF final "
                  f"{d['ekf']['final_pos_err_m']:.3f} m max "
                  f"{d['ekf']['max_pos_err_m']:.3f}")
    result = {
        'tool': 'docs/data/lab2/an_ekf.py',
        'command': 'python3 docs/data/lab2/an_ekf.py ' + ' '.join(
            ':'.join(os.path.basename(x) for x in p.split(':'))
            for p in args.pairs),
        'config': args.config,
        'cite': 'docs/RESULTS.md "COCO Lab Phase 3"; '
                'docs/data/lab2/ekf_drift.json',
        'drives': drives,
    }
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
