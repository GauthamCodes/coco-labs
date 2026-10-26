#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# G2.8 per-round gate diagnosis (docs/v2/g2/data/g28/round_gate/README.md); read only, STACK runs.
# Run with ROS 2 sourced: source /opt/ros/jazzy/setup.bash
"""Read-only: per-window summary of /plan, /cmd_vel_nav, /cmd_vel_smoothed, wheel cmd, collision monitor during one leg."""
import json, math, os, sys
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
run, leg = sys.argv[1], int(sys.argv[2]); step = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
L = [json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))]
t0 = L[leg]['t_start_sim']; t1 = t0 + L[leg]['sim_s']
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=os.path.join(run, 'bag'), storage_id='mcap'), rosbag2_py.ConverterOptions('', ''))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
want = ['/plan', '/cmd_vel_nav', '/cmd_vel_smoothed', '/diff_drive_controller/cmd_vel', '/collision_monitor_state', '/clock']
r.set_filter(rosbag2_py.StorageFilter(topics=want))
clock = None; bins = {}
def b(t): return int((t - t0) // step)
while r.has_next():
    topic, raw, _ = r.read_next()
    m = deserialize_message(raw, get_message(types[topic]))
    if topic == '/clock':
        clock = m.clock.sec + m.clock.nanosec * 1e-9; continue
    if clock is None or not (t0 <= clock <= t1): continue
    k = b(clock); e = bins.setdefault(k, {})
    if topic == '/plan':
        e['plans'] = e.get('plans', 0) + 1
        ps = m.poses
        if ps:
            L_ = sum(math.hypot(ps[i].pose.position.x - ps[i-1].pose.position.x, ps[i].pose.position.y - ps[i-1].pose.position.y) for i in range(1, len(ps)))
            mid = ps[min(len(ps) - 1, 20)].pose.position
            e['plan'] = f'{L_:.1f} m via ({mid.x:.1f},{mid.y:.1f})'
    elif topic == '/collision_monitor_state':
        e.setdefault('cm', set()).add(f'{m.action_type}:{m.polygon_name}')
    else:
        tw = getattr(m, 'twist', m)
        key = {'/cmd_vel_nav': 'nav', '/cmd_vel_smoothed': 'smooth', '/diff_drive_controller/cmd_vel': 'wheels'}[topic]
        lst = e.setdefault(key, []); lst.append((tw.linear.x, tw.angular.z))
for k in sorted(bins):
    e = bins[k]
    def s(key):
        v = e.get(key)
        if not v: return '-'
        return f'n{len(v)} v[{min(a for a, _ in v):+.2f},{max(a for a, _ in v):+.2f}] w[{min(c for _, c in v):+.2f},{max(c for _, c in v):+.2f}]'
    print(f't+{k * step:5.0f}  nav {s("nav"):<38} wheels {s("wheels"):<38} cm {",".join(sorted(e.get("cm", []))) or "-":<28} plan {e.get("plan", "-")} ({e.get("plans", 0)})')
