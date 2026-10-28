#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.6, step 1: why Gazebo + Nav2 fail on the Depot (M6F.8: the Dock 1 leg aborts with 205
START_OCCUPIED; AMCL ends ~0.5 m south of the truth). Measured from recorded runs, read only.

    source /opt/ros/jazzy/setup.bash && tools/g2/diagnose_m6f8.py RUN_DIR GEN_DIR OUT.json

RUN_DIR: an ``m6f8_run.sh`` output (``bag/``, ``results.jsonl``); GEN_DIR: the generated level
(``nav2/coco_depot_v1.{yaml,pgm}``, ``nav2/nav2_params.yaml``). STACK evidence, never modified.

1. **Odometry**: /diff_drive_controller/odom against the truth (/model/coco/odometry, Gazebo's
   world frame = the Depot's map frame, world_to_map [0, 0]), aligned at the first sample: the
   drift the wheels alone accumulate.
2. **AMCL**: /amcl_pose against the truth at each AMCL update (dx, dy, error).
3. **Scan vs map**: for every 5th scan, each in-range beam's end point (from the lidar's pose:
   base_link -> lidar_link (-0.09, 0.1) on the robot) and its distance to the nearest occupied
   map cell. Scored at the truth pose and at AMCL's pose; and the map offset (dx, dy, 0.05 m
   steps within 0.6 m) that fits the scan best at the truth. If the best offset is ~0 the map and
   the world agree; if the scan fits better away from the truth, the map (or a body in the world
   but not in the map) pulls AMCL there.
4. **Unmapped returns**: beams ending more than 0.25 m from any occupied cell at the truth pose:
   something the LiDAR sees that the map does not have, clustered (0.5 m cells), with counts.
5. **Each goal**: from results.jsonl, the truth, AMCL's estimate and the error when the leg ended.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from rclpy.serialization import deserialize_message
import rosbag2_py
from rosidl_runtime_py.utilities import get_message
from scipy.ndimage import distance_transform_edt
import yaml

TOPICS = ('/model/coco/odometry', '/amcl_pose', '/diff_drive_controller/odom', '/scan')
LIDAR = (-0.09, 0.1)          # base_link -> lidar_link (coco_robo2 URDF; ros_shapes.tf_static)


def read(bag):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=[t for t in TOPICS if t in types]))
    out = {t: [] for t in TOPICS}
    while r.has_next():
        topic, data, _t = r.read_next()
        m = deserialize_message(data, get_message(types[topic]))
        st = m.header.stamp
        out[topic].append((st.sec + st.nanosec * 1e-9, m))
    return out


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def pose2d(m):
    p = m.pose.pose if hasattr(m.pose, 'pose') else m.pose
    return (p.position.x, p.position.y, yaw(p.orientation))


def nearest(series, t):
    ts = series[0]
    i = int(np.searchsorted(ts, t))
    i = min(max(i, 0), len(ts) - 1)
    if i > 0 and abs(ts[i - 1] - t) < abs(ts[i] - t):
        i -= 1
    return series[1][i], abs(ts[i] - t)


def load_map(gen):
    with open(os.path.join(gen, 'nav2', 'coco_depot_v1.yaml')) as f:
        y = yaml.safe_load(f)
    img = np.array(Image.open(os.path.join(gen, 'nav2', y['image'])))
    occ = img < 128                          # trinary pgm: occupied black (0), free white, unknown grey (205)
    occ = occ[::-1, :]                       # row 0 at the origin
    dist = distance_transform_edt(~occ) * y['resolution']
    return y, occ, dist


def beams(scan, pose):
    x, y, th = pose
    lx, ly = x + LIDAR[0] * math.cos(th) - LIDAR[1] * math.sin(th), y + LIDAR[0] * math.sin(th) + LIDAR[1] * math.cos(th)
    r = np.array(scan.ranges, dtype=float)
    a = scan.angle_min + np.arange(len(r)) * scan.angle_increment + th
    ok = np.isfinite(r) & (r >= scan.range_min) & (r < scan.range_max)
    return lx + r[ok] * np.cos(a[ok]), ly + r[ok] * np.sin(a[ok])


def dist_at(mp, xs, ys):
    y, _occ, dist = mp
    res, (ox, oy) = y['resolution'], y['origin'][:2]
    c = np.floor((xs - ox) / res).astype(int)
    rw = np.floor((ys - oy) / res).astype(int)
    inside = (c >= 0) & (rw >= 0) & (c < dist.shape[1]) & (rw < dist.shape[0])
    d = np.full(xs.shape, np.nan)
    d[inside] = dist[rw[inside], c[inside]]
    return d


def score(mp, scan, pose):
    xs, ys = beams(scan, pose)
    d = dist_at(mp, xs, ys)
    d = d[np.isfinite(d)]
    return (float(np.mean(np.minimum(d, 0.5))) if d.size else None, float(np.mean(d < 0.1)) if d.size else None, int(d.size))


def main() -> int:
    run, gen, out = sys.argv[1:4]
    data = read(os.path.join(run, 'bag'))
    mp = load_map(gen)
    truth = (np.array([t for t, _ in data['/model/coco/odometry']]), [pose2d(m) for _, m in data['/model/coco/odometry']])
    odom = data['/diff_drive_controller/odom']
    rep = {'run': os.path.basename(run.rstrip('/')), 'class': 'STACK (recorded Gazebo + Nav2), measured offline',
           'samples': {t: len(v) for t, v in data.items()}}
    # 1. odometry drift, aligned at the first odom sample with the truth
    if odom:
        t0, m0 = odom[0]
        o0 = pose2d(m0)
        g0, _ = nearest(truth, t0)
        rot = g0[2] - o0[2]
        rows = []
        for t, m in odom[::20]:
            o = pose2d(m)
            dx, dy = o[0] - o0[0], o[1] - o0[1]
            ex = g0[0] + dx * math.cos(rot) - dy * math.sin(rot)
            ey = g0[1] + dx * math.sin(rot) + dy * math.cos(rot)
            g, _ = nearest(truth, t)
            rows.append([round(t, 2), round(ex - g[0], 4), round(ey - g[1], 4)])
        rep['odom_minus_truth'] = {'every': '20th odom sample', 'end': rows[-1], 'max_abs_m': round(max(math.hypot(r[1], r[2]) for r in rows), 4), 'rows': rows}
    # 2. AMCL vs truth
    am = []
    for t, m in data['/amcl_pose']:
        a = pose2d(m)
        g, dt = nearest(truth, t)
        am.append({'t': round(t, 2), 'dx': round(a[0] - g[0], 4), 'dy': round(a[1] - g[1], 4), 'err': round(math.hypot(a[0] - g[0], a[1] - g[1]), 4),
                   'dth_deg': round(math.degrees(math.atan2(math.sin(a[2] - g[2]), math.cos(a[2] - g[2]))), 2), 'truth': [round(v, 3) for v in g],
                   'cov_xx': round(m.pose.covariance[0], 5), 'cov_yy': round(m.pose.covariance[7], 5)})
    rep['amcl_minus_truth'] = am
    amcl_series = (np.array([t for t, _ in data['/amcl_pose']]), [pose2d(m) for _, m in data['/amcl_pose']])
    # 3. scan vs map at the truth, at AMCL's pose, and the best-fitting map offset
    rows, unmapped = [], {}
    offs = [(dx, dy) for dx in np.arange(-0.6, 0.601, 0.05) for dy in np.arange(-0.6, 0.601, 0.05)]
    for t, s in data['/scan'][::5]:
        g, dtg = nearest(truth, t)
        if dtg > 0.05:
            continue
        row = {'t': round(t, 2), 'truth': [round(v, 3) for v in g], 'at_truth': score(mp, s, g)}
        if len(amcl_series[0]):
            a, dta = nearest(amcl_series, t)
            row['at_amcl'] = score(mp, s, a)
            row['amcl_dt_s'] = round(dta, 2)
        best = min(offs, key=lambda o: score(mp, s, (g[0] + o[0], g[1] + o[1], g[2]))[0] or 9)
        row['best_offset'] = [round(float(best[0]), 2), round(float(best[1]), 2)]
        row['at_best'] = score(mp, s, (g[0] + best[0], g[1] + best[1], g[2]))
        rows.append(row)
        xs, ys = beams(s, g)
        d = dist_at(mp, xs, ys)
        for x, y_, dd in zip(xs, ys, d):
            if np.isfinite(dd) and dd > 0.25:
                k = (round(x * 2) / 2, round(y_ * 2) / 2)
                unmapped[k] = unmapped.get(k, 0) + 1
    rep['scan_vs_map'] = {'note': 'mean distance (m, capped 0.5) of beam ends to the nearest occupied cell; fraction within 0.1 m; beams',
                          'rows': rows}
    if rows:
        bo = np.array([r['best_offset'] for r in rows])
        rep['scan_vs_map']['best_offset_median'] = [round(float(np.median(bo[:, 0])), 3), round(float(np.median(bo[:, 1])), 3)]
    rep['unmapped_returns'] = sorted(([k[0], k[1], n] for k, n in unmapped.items() if n >= 20), key=lambda r: -r[2])[:40]
    # 5. the legs
    with open(os.path.join(run, 'results.jsonl')) as f:
        legs = [json.loads(line) for line in f if line.strip()]
    rep['legs'] = [{k: L.get(k) for k in ('id', 'goal', 'status', 'error_code', 'driven_m', 'end_truth', 'end_amcl', 'amcl_error_m')} for L in legs]
    with open(out, 'w') as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({'run': rep['run'], 'odom_end': rep.get('odom_minus_truth', {}).get('end'), 'amcl_last': am[-1] if am else None,
                      'best_offset_median': rep['scan_vs_map'].get('best_offset_median'), 'unmapped_top': rep['unmapped_returns'][:8]}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
