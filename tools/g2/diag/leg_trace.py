#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# G2.8 per-round gate diagnosis (docs/v2/g2/data/g28/round_gate/README.md); read only, STACK runs.
# Run with ROS 2 sourced: source /opt/ros/jazzy/setup.bash
"""Read-only: trace one leg of an m6f8 run (truth, controller cmd, wheel cmd, collision monitor, min scan)."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import diagnose_m6f8 as d
run, leg = sys.argv[1], int(sys.argv[2])
L = [json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))]
t0 = L[leg]['t_start_sim']; t1 = t0 + L[leg]['sim_s']
data = d.read(os.path.join(run, 'bag'))
print('topics:', sorted(k for k in data if data[k])[:30])
def at(topic, t):
    s = data.get(topic) or []
    best = None
    for tt, m in s:
        if tt <= t: best = m
        else: break
    return best
step = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
t = t0
while t <= t1 + 1e-6:
    tr = at('/model/coco/odometry', t)
    x, y, th = d.pose2d(tr) if tr else (float('nan'),) * 3
    nav = at('/cmd_vel_nav', t); whl = at('/diff_drive_controller/cmd_vel', t)
    def vw(m):
        if m is None: return '-'
        tw = getattr(m, 'twist', m)
        return f'{tw.linear.x:+.2f}/{tw.angular.z:+.2f}'
    cm = at('/collision_monitor_state', t)
    cms = f'{cm.action_type}:{cm.polygon_name}' if cm is not None else '-'
    sc = at('/scan', t)
    mn = min([r for r in sc.ranges if sc.range_min < r < sc.range_max], default=float('nan')) if sc else float('nan')
    print(f't+{t - t0:6.1f}  x {x:6.2f} y {y:5.2f} th {math.degrees(th):6.1f}  nav {vw(nav):>12}  wheels {vw(whl):>12}  cm {cms:<22} minscan {mn:.2f}')
    t += step
