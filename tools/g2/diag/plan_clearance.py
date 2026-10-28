#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# G2.8 per-round gate diagnosis (docs/v2/g2/data/g28/round_gate/README.md); read only, STACK runs.
# Run with ROS 2 sourced: source /opt/ros/jazzy/setup.bash
"""Read-only: clearance (distance to the nearest occupied map cell) along the first /plan of a leg."""
import json, math, os, sys
import numpy as np, yaml
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
run, leg, gen = sys.argv[1], int(sys.argv[2]), sys.argv[3]
L = [json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))]
t0 = L[leg]['t_start_sim']
my = yaml.safe_load(open(os.path.join(gen, 'nav2', 'coco_depot_v1.yaml')))
with open(os.path.join(gen, 'nav2', my['image']), 'rb') as f:
    assert f.readline().strip() == b'P5'
    line = f.readline()
    while line.startswith(b'#'): line = f.readline()
    w, h = map(int, line.split()); mx = int(f.readline()); img = np.frombuffer(f.read(), np.uint8).reshape(h, w)
occ = (255 - img.astype(float)) / 255.0 > my['occupied_thresh']
res, (ox, oy, _) = my['resolution'], my['origin']
ys, xs = np.nonzero(occ); pts = np.stack([ox + (xs + 0.5) * res, oy + (h - 1 - ys + 0.5) * res], 1)
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=os.path.join(run, 'bag'), storage_id='mcap'), rosbag2_py.ConverterOptions('', ''))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=['/plan', '/clock']))
clock = None; plan = None
while r.has_next():
    topic, raw, _ = r.read_next()
    m = deserialize_message(raw, get_message(types[topic]))
    if topic == '/clock': clock = m.clock.sec + m.clock.nanosec * 1e-9; continue
    if clock and clock >= t0 + 2: plan = m; break
P = [(p.pose.position.x, p.pose.position.y) for p in plan.poses]
acc = 0; prev = P[0]; rows = []
near = pts[(np.abs(pts[:, 0] - P[0][0]) < 6) & (np.abs(pts[:, 1] - P[0][1]) < 6)]
for (x, y) in P:
    acc += math.hypot(x - prev[0], y - prev[1]); prev = (x, y)
    if acc > 4.0: break
    c = float(np.min(np.hypot(near[:, 0] - x, near[:, 1] - y)))
    rows.append((round(acc, 2), round(x, 2), round(y, 2), round(c, 3)))
print('map res', res, 'plan points', len(P), 'first 4 m:')
for row in rows[::4]: print(row)
print('min clearance in the first 4 m:', min(r[3] for r in rows), 'at', min(rows, key=lambda r: r[3]))
