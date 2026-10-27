#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.9 (Gautham, 2026-10-27: calibrate the odometry turn scale in the generated Gazebo files only):
how much COCO's wheel odometry over- or under-counts turning and distance, against Gazebo's truth,
over recorded gate runs (read only; STACK evidence).

    source /opt/ros/jazzy/setup.bash && tools/g2/odom_turn_scale.py OUT.json RUN_DIR...

Each RUN_DIR is an ``m6f8_run.sh`` output with ``bag/`` (/diff_drive_controller/odom and
/model/coco/odometry). Both are sampled on one 0.1 s grid over the time both exist; the turn is
the sum of |Δyaw| (wrapped per step), the distance the sum of |Δxy|. Per run and pooled:
``turn_scale`` = odometry's turn / the truth's turn (> 1: odometry over-counts), the same for
distance. The calibrated ``wheel_separation_multiplier`` is the current one times the pooled
turn scale: the controller divides the wheels' speed difference by separation × multiplier for
odometry, and multiplies the commanded turn rate by it for the wheels, so one value corrects both.
"""
import json
import math
import sys

import numpy as np
from rclpy.serialization import deserialize_message
import rosbag2_py
from rosidl_runtime_py.utilities import get_message

TOPICS = ('/diff_drive_controller/odom', '/model/coco/odometry')
STEP = 0.1


def read(bag):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=[t for t in TOPICS if t in types]))
    out = {t: ([], []) for t in TOPICS}
    while r.has_next():
        topic, data, _t = r.read_next()
        m = deserialize_message(data, get_message(types[topic]))
        p, q = m.pose.pose.position, m.pose.pose.orientation
        out[topic][0].append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9)
        out[topic][1].append((p.x, p.y, math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))))
    return {k: (np.array(t), np.array(v)) for k, (t, v) in out.items()}


def sampled(series, grid):
    t, v = series
    i = np.clip(np.searchsorted(t, grid), 0, len(t) - 1)
    return v[i]


def travel(v):
    dyaw = np.diff(v[:, 2])
    dyaw = (dyaw + np.pi) % (2 * np.pi) - np.pi
    return float(np.abs(dyaw).sum()), float(np.hypot(np.diff(v[:, 0]), np.diff(v[:, 1])).sum())


def run(d):
    s = read(f'{d}/bag')
    odom, truth = s['/diff_drive_controller/odom'], s['/model/coco/odometry']
    if len(odom[0]) < 10 or len(truth[0]) < 10:
        return {'run': d, 'skipped': 'too few samples'}
    t0, t1 = max(odom[0][0], truth[0][0]), min(odom[0][-1], truth[0][-1])
    grid = np.arange(t0, t1, STEP)
    o_turn, o_dist = travel(sampled(odom, grid))
    t_turn, t_dist = travel(sampled(truth, grid))
    return {'run': d, 'seconds': round(float(t1 - t0), 1), 'odom_turn_rad': round(o_turn, 3), 'truth_turn_rad': round(t_turn, 3),
            'odom_dist_m': round(o_dist, 3), 'truth_dist_m': round(t_dist, 3),
            'turn_scale': round(o_turn / t_turn, 4) if t_turn else None, 'dist_scale': round(o_dist / t_dist, 4) if t_dist else None}


def main() -> int:
    out, dirs = sys.argv[1], sys.argv[2:]
    rows = [run(d) for d in dirs]
    ok = [r for r in rows if 'skipped' not in r]
    pooled = {k: round(sum(r[k] for r in ok), 3) for k in ('odom_turn_rad', 'truth_turn_rad', 'odom_dist_m', 'truth_dist_m')}
    ts = [r['turn_scale'] for r in ok if r['turn_scale']]
    rep = {'evidence_class': 'STACK (recorded Gazebo + Nav2 runs, read only)', 'step_s': STEP, 'runs': len(ok),
           'pooled_turn_scale': round(pooled['odom_turn_rad'] / pooled['truth_turn_rad'], 4),
           'pooled_dist_scale': round(pooled['odom_dist_m'] / pooled['truth_dist_m'], 4),
           'turn_scale_per_run': {'min': min(ts), 'median': float(np.median(ts)), 'max': max(ts)} if ts else None,
           'pooled': pooled, 'rows': rows}
    with open(out, 'w') as f:
        json.dump(rep, f, indent=1)
        f.write('\n')
    print(json.dumps({k: rep[k] for k in ('runs', 'pooled_turn_scale', 'pooled_dist_scale', 'turn_scale_per_run')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
