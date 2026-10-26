#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# G2.8 per-round gate diagnosis (docs/v2/g2/data/g28/round_gate/README.md); read only, STACK runs.
# Run with ROS 2 sourced: source /opt/ros/jazzy/setup.bash
"""Read-only: per 2 s window in [A, B] s of a leg: mean |w| commanded by the controller and sent to the wheels, and the truth's yaw rate."""
import json, math, os, sys
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
run, leg, A, B = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
L = [json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))]
t0 = L[leg]['t_start_sim']
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=os.path.join(run, 'bag'), storage_id='mcap'), rosbag2_py.ConverterOptions('', ''))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=['/clock', '/cmd_vel_nav', '/diff_drive_controller/cmd_vel', '/model/coco/odometry']))
clock = None; W = {}
while r.has_next():
    topic, raw, _ = r.read_next()
    m = deserialize_message(raw, get_message(types[topic]))
    if topic == '/clock': clock = m.clock.sec + m.clock.nanosec * 1e-9; continue
    if clock is None: continue
    rel = clock - t0
    if not (A <= rel < B): continue
    e = W.setdefault(int(rel // 2), {'nav': [], 'wh': [], 'yaw': [], 'v': []})
    if topic == '/model/coco/odometry':
        q = m.pose.pose.orientation; e['yaw'].append(math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))); e['v'].append(m.twist.twist.angular.z)
    else:
        tw = getattr(m, 'twist', m); e['nav' if topic == '/cmd_vel_nav' else 'wh'].append((tw.linear.x, tw.angular.z))
mean = lambda a: sum(a) / len(a) if a else float('nan')
for k in sorted(W):
    e = W[k]
    dyaw = math.degrees(math.atan2(math.sin(e['yaw'][-1] - e['yaw'][0]), math.cos(e['yaw'][-1] - e['yaw'][0]))) if len(e['yaw']) > 1 else float('nan')
    print(f't+{2 * k:5.0f}  nav w mean {mean([w for _, w in e["nav"]]):+.3f} (n{len(e["nav"])})  wheels w mean {mean([w for _, w in e["wh"]]):+.3f} (n{len(e["wh"])})  truth yaw change {dyaw:+6.1f} deg  truth w mean {mean(e["v"]):+.3f}')
