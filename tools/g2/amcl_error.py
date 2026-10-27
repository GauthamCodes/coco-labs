#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.9 (Gautham, 2026-10-27: after the odometry calibration, re-measure AMCL's residual error and
report it): AMCL's error against Gazebo's truth over recorded gate runs (read only; STACK evidence).

    source /opt/ros/jazzy/setup.bash && tools/g2/amcl_error.py OUT.json RUN_DIR...

Per run: every leg's error at its end (``results.jsonl``: ``amcl_error_m``, AMCL's pose vs the truth
when the leg ended) and, from ``bag/``, every /amcl_pose against the truth (/model/coco/odometry, the
nearest sample within 0.05 s; the Depot's map frame is Gazebo's world, world_to_map [0, 0]): mean,
p95, max (m) and the mean signed (dx, dy) (a bias shows as a mean offset). Pooled: the leg-end errors'
median, p90 and max, and the per-run means' median.
"""
import json
import math
import sys

import numpy as np
from rclpy.serialization import deserialize_message
import rosbag2_py
from rosidl_runtime_py.utilities import get_message

TOPICS = ('/amcl_pose', '/model/coco/odometry')


def read(bag):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=[t for t in TOPICS if t in types]))
    out = {t: ([], []) for t in TOPICS}
    while r.has_next():
        topic, data, _t = r.read_next()
        m = deserialize_message(data, get_message(types[topic]))
        p = m.pose.pose.position
        out[topic][0].append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9)
        out[topic][1].append((p.x, p.y))
    return {k: (np.array(t), np.array(v)) for k, (t, v) in out.items()}


def q(a, f):
    return round(float(np.quantile(a, f)), 4) if len(a) else None


def run(d):
    legs = [json.loads(line) for line in open(f'{d}/results.jsonl') if line.strip()]
    ends = [x['amcl_error_m'] for x in legs if x.get('amcl_error_m') is not None]
    row = {'run': d, 'legs': len(legs), 'legs_succeeded': sum(x['status'] == 'SUCCEEDED' for x in legs),
           'leg_end_error_m': ends}
    s = read(f'{d}/bag')
    (ta, pa), (tt, pt) = s['/amcl_pose'], s['/model/coco/odometry']
    if len(ta) and len(tt):
        i = np.clip(np.searchsorted(tt, ta), 1, len(tt) - 1)
        i = np.where(np.abs(tt[i - 1] - ta) < np.abs(tt[i] - ta), i - 1, i)
        ok = np.abs(tt[i] - ta) <= 0.05
        d_xy = pa[ok] - pt[i[ok]]
        e = np.hypot(d_xy[:, 0], d_xy[:, 1])
        row.update(amcl_updates=int(ok.sum()), mean_m=round(float(e.mean()), 4), p95_m=q(e, 0.95),
                   max_m=round(float(e.max()), 4), mean_dx_dy_m=[round(float(v), 4) for v in d_xy.mean(axis=0)])
    return row


def main() -> int:
    out, dirs = sys.argv[1], sys.argv[2:]
    rows = [run(d) for d in dirs]
    ends = [e for r in rows for e in r['leg_end_error_m']]
    means = [r['mean_m'] for r in rows if 'mean_m' in r]
    rep = {'evidence_class': 'STACK (recorded Gazebo + Nav2 runs, read only)', 'runs': len(rows), 'legs': len(ends),
           'leg_end_error_m': {'median': q(ends, 0.5), 'p90': q(ends, 0.9), 'max': max(ends) if ends else None},
           'per_run_mean_m': {'median': q(means, 0.5), 'max': max(means) if means else None},
           'per_run_max_m': {'median': q([r['max_m'] for r in rows if 'max_m' in r], 0.5),
                             'max': max((r['max_m'] for r in rows if 'max_m' in r), default=None)},
           'mean_dx_dy_m': [round(float(np.mean([r['mean_dx_dy_m'][k] for r in rows if 'mean_dx_dy_m' in r])), 4) for k in (0, 1)]
           if means else None, 'rows': rows}
    with open(out, 'w') as f:
        json.dump(rep, f, indent=1)
        f.write('\n')
    print(json.dumps({k: rep[k] for k in ('runs', 'legs', 'leg_end_error_m', 'per_run_mean_m', 'per_run_max_m', 'mean_dx_dy_m')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
