# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Extract the full 3D ground truth from Lab 4's recorded fetches (M4.3).

Lab 4's matrix (``~/coco_lab_runs/lab4/matrix/<run>/bag``) recorded
``/model/coco/odometry`` -- Gazebo's own pose of the robot, nav_msgs/Odometry,
the WORLD frame -- through every climb up a bay's ramp. This writes, per bag,
the pose decimated to one row per 0.1 s of recorded time (the Arena's tick):
``t, x, y, z, roll, pitch, yaw`` (REP-103), and the sha256 of every file in
the bag, so the analysis (``terrain_fidelity.py``, no ROS) is reproducible
from committed data and traceable to the recordings.

Needs ROS 2 Jazzy (rosbag2_py, rclpy serialization). Usage::

    source /opt/ros/jazzy/setup.bash
    python3 docs/v2/data/m4/m43/extract_lab4_truth.py ~/coco_lab_runs/lab4/matrix \\
        --out docs/v2/data/m4/m43/lab4_truth.json.gz
"""

import argparse
import gzip
import hashlib
import json
import math
import os

from nav_msgs.msg import Odometry
from rclpy.serialization import deserialize_message
import rosbag2_py

TOPIC = '/model/coco/odometry'
STEP_NS = 100_000_000


def rpy(q):
    """REP-103 roll, pitch, yaw of a quaternion (x, y, z, w)."""
    x, y, z, w = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def extract(bag):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'),
           rosbag2_py.ConverterOptions('cdr', 'cdr'))
    r.set_filter(rosbag2_py.StorageFilter(topics=[TOPIC]))
    rows, t0, next_t, seen = [], None, None, 0
    while r.has_next():
        _, data, t = r.read_next()
        seen += 1
        m = deserialize_message(data, Odometry)
        ts = m.header.stamp.sec * 1_000_000_000 + m.header.stamp.nanosec
        if t0 is None:
            t0, next_t = ts, ts
        if ts < next_t:
            continue
        next_t += STEP_NS * ((ts - next_t) // STEP_NS + 1)
        p, o = m.pose.pose.position, m.pose.pose.orientation
        ro, pi, ya = rpy((o.x, o.y, o.z, o.w))
        rows.append([round((ts - t0) / 1e9, 3), p.x, p.y, p.z, ro, pi, ya])
    return rows, seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('matrix')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = {'source': TOPIC + ' (Gazebo ground truth, world frame), header stamps (sim time)',
           'decimation': 'first sample of every 0.1 s of recorded time',
           'columns': ['t', 'x', 'y', 'z', 'roll', 'pitch', 'yaw'], 'runs': []}
    for run in sorted(os.listdir(a.matrix)):
        bag = os.path.join(a.matrix, run, 'bag')
        if not os.path.isdir(bag):
            continue
        rows, seen = extract(bag)
        files = {f: sha256(os.path.join(bag, f)) for f in sorted(os.listdir(bag))}
        out['runs'].append({'run': run, 'bag': f'lab4/matrix/{run}/bag', 'sha256': files,
                            'messages': seen, 'rows': rows})
        print(f'{run}: {seen} messages -> {len(rows)} rows, z max {max(r[3] for r in rows):.3f}')
    with gzip.open(a.out, 'wt', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))


if __name__ == '__main__':
    main()
