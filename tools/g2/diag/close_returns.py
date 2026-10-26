#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# G2.8 per-round gate diagnosis (docs/v2/g2/data/g28/round_gate/README.md); read only, STACK runs.
# Run with ROS 2 sourced: source /opt/ros/jazzy/setup.bash
"""Read-only: at leg start + DT, the scan returns within RMAX of the lidar, in the map frame, and their distance to the map."""
import json, math, os, sys
import numpy as np, yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import diagnose_m6f8 as d
run, leg, gen, DT = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
RMAX = 0.9
L = [json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))]
t = L[leg]['t_start_sim'] + DT
data = d.read(os.path.join(run, 'bag'))
tr = [m for tt, m in data['/model/coco/odometry'] if tt <= t][-1]
sc = [m for tt, m in data['/scan'] if tt <= t][-1]
pose = d.pose2d(tr)
mp = d.load_map(gen)
xs, ys = d.beams(sc, pose)
x0, y0, th = pose
lx, ly = x0 + math.cos(th) * -0.09 - math.sin(th) * 0.1, y0 + math.sin(th) * -0.09 + math.cos(th) * 0.1
r = np.hypot(np.asarray(xs) - lx, np.asarray(ys) - ly)
dist = d.dist_at(mp, np.asarray(xs), np.asarray(ys))
sel = r < RMAX
print('pose', [round(v, 2) for v in pose], 'returns <', RMAX, 'm:', int(sel.sum()))
pts = sorted(zip(r[sel], np.asarray(xs)[sel], np.asarray(ys)[sel], dist[sel]))
for rr, x, y, dd in pts[:: max(1, len(pts) // 14)]:
    print(f'  r {rr:.2f}  at ({x:.2f}, {y:.2f})  map distance {dd:.2f}{"  UNMAPPED" if dd > 0.15 else ""}')
