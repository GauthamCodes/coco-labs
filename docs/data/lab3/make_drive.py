#!/usr/bin/env python3
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
Phase 4: cut one recorded drive out of a Lab 2 session, for every SLAM.

Input: a Lab 2 ``fidelity`` session (``docs/data/lab2/lab2_run.sh``): a
fresh simulator, the tour driven by ``lab2_probe.py`` through the arbiter,
recorded as a rosbag2 (MCAP). Its ``drives.jsonl`` gives the drive's
sim-time window.

Output, under OUT:

``bag/``
    A derived rosbag2 (MCAP) holding ONLY the drive's window (1 s either
    side) and only what a SLAM may read, byte for byte as recorded:
    ``/clock``, ``/scan``, ``/tf`` WITHOUT AMCL's ``map -> odom`` (the
    session ran AMCL; a SLAM publishes its own ``map -> odom``),
    ``/tf_static`` (all of it, as recorded, transient local), the wheel
    odometry ``/diff_drive_controller/odom``, ``/imu``, and the truth
    ``/model/coco/odometry`` (for scoring only; no SLAM subscribes to it).
    Topic QoS profiles are copied from the source.
``drive.json.gz``
    The same drive for coco_lab: per scan, its stamp, the 480 ranges
    (``null`` = no return), the wheel-odometry pose (``odom ->
    base_footprint`` from ``/tf``, interpolated at the scan stamp) and the
    truth pose in the MAP frame (``/model/coco/odometry`` + ``world_to_map``,
    interpolated at the scan stamp).
``drive_meta.json``
    Provenance: the source bag's file hashes, the session's ``meta.json``,
    the window, counts, and this script's command line.

Needs the ROS environment (rosbag2_py). Usage::

    python3 docs/data/lab3/make_drive.py ~/coco_lab_runs/lab2/fidelity_s1 \\
        tour ~/coco_lab_runs/lab3/drives/s1_tour
"""

import argparse
import bisect
import gzip
import hashlib
import json
import math
import os
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
WORLD_JSON = os.path.join(REPO, 'gazebo_models', 'config',
                          'navigation_world.json')
KEEP = ('/clock', '/scan', '/tf', '/tf_static',
        '/diff_drive_controller/odom', '/imu', '/model/coco/odometry')
PAD_S = 1.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y),
                      1 - 2 * (q.y * q.y + q.z * q.z))


def stamp(h):
    return h.stamp.sec + h.stamp.nanosec * 1e-9


def interp(series, t):
    """Linear interpolation of (t, x, y, yaw) rows at t (yaw unwrapped)."""
    ts = [r[0] for r in series]
    i = bisect.bisect_left(ts, t)
    if i <= 0:
        return series[0][1:], abs(series[0][0] - t)
    if i >= len(series):
        return series[-1][1:], abs(series[-1][0] - t)
    a, b = series[i - 1], series[i]
    f = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
    dyaw = math.atan2(math.sin(b[3] - a[3]), math.cos(b[3] - a[3]))
    yaw = a[3] + f * dyaw
    yaw = math.atan2(math.sin(yaw), math.cos(yaw))
    return ((a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]), yaw),
            min(t - a[0], b[0] - t))


def window(session, label):
    t0 = t1 = None
    with open(os.path.join(session, 'drives.jsonl')) as f:
        for line in f:
            d = json.loads(line)
            if d.get('label') != label:
                continue
            t0 = d['t'] if t0 is None else t0
            t1 = d['t']
    if t0 is None:
        raise SystemExit(f'no drive {label!r} in {session}/drives.jsonl')
    return t0, t1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('session')
    ap.add_argument('drive')
    ap.add_argument('out')
    args = ap.parse_args(argv)
    src = os.path.join(args.session, 'bag')
    t0, t1 = window(args.session, args.drive)
    lo, hi = t0 - PAD_S, t1 + PAD_S
    w2m = tuple(json.load(open(WORLD_JSON))['world_to_map'])
    os.makedirs(args.out, exist_ok=True)
    dst = os.path.join(args.out, 'bag')
    if os.path.exists(dst):
        raise SystemExit(f'{dst} exists; refusing to overwrite')

    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=src, storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    topics = {t.name: t for t in r.get_all_topics_and_types()}
    types = {n: t.type for n, t in topics.items()}
    w = rosbag2_py.SequentialWriter()
    w.open(rosbag2_py.StorageOptions(uri=dst, storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    for name in KEEP:
        w.create_topic(topics[name])
    r.set_filter(rosbag2_py.StorageFilter(topics=list(KEEP)))
    TF = get_message('tf2_msgs/msg/TFMessage')
    from rclpy.serialization import serialize_message
    counts = {n: 0 for n in KEEP}
    dropped_map_odom = 0
    scans, odom, truth = [], [], []
    while r.has_next():
        topic, data, t_ns = r.read_next()
        t = t_ns * 1e-9
        if topic == '/tf_static':
            w.write(topic, data, t_ns)  # all of it, whenever recorded
            counts[topic] += 1
            continue
        if not (lo <= t <= hi):
            continue
        if topic == '/tf':
            msg = deserialize_message(data, TF)
            keep = [tr for tr in msg.transforms
                    if not (tr.header.frame_id == 'map' and
                            tr.child_frame_id == 'odom')]
            dropped_map_odom += len(msg.transforms) - len(keep)
            for tr in keep:
                if tr.header.frame_id == 'odom' and \
                        tr.child_frame_id == 'base_footprint':
                    odom.append((stamp(tr.header),
                                 tr.transform.translation.x,
                                 tr.transform.translation.y,
                                 yaw_of(tr.transform.rotation)))
            if not keep:
                continue
            if len(keep) != len(msg.transforms):
                msg.transforms = keep
                data = serialize_message(msg)
        elif topic == '/scan':
            m = deserialize_message(data, get_message(types[topic]))
            scans.append((stamp(m.header),
                          [v if math.isfinite(v) else None for v in m.ranges],
                          (m.angle_min, m.angle_max, len(m.ranges),
                           m.range_min, m.range_max, m.header.frame_id)))
        elif topic == '/model/coco/odometry':
            m = deserialize_message(data, get_message(types[topic]))
            p = m.pose.pose
            truth.append((stamp(m.header), p.position.x + w2m[0],
                          p.position.y + w2m[1], yaw_of(p.orientation)))
        w.write(topic, data, t_ns)
        counts[topic] += 1
    del w
    odom.sort()
    truth.sort()
    # only scans inside the drive itself (not the padding)
    rows = []
    gaps = []
    for ts, ranges, geom in scans:
        if not (t0 <= ts <= t1):
            continue
        o, go = interp(odom, ts)
        g, gg = interp(truth, ts)
        gaps.append(max(go, gg))
        rows.append({'t': ts, 'ranges': ranges, 'odom': list(o),
                     'truth': list(g)})
    geom = scans[0][2]
    drive = {
        'schema': 'coco_lab.recorded_drive', 'version': '1.0',
        'lidar': {'angle_min': geom[0], 'angle_max': geom[1],
                  'samples': geom[2], 'range_min': geom[3],
                  'range_max': geom[4], 'frame': geom[5]},
        'frames': {'truth': 'map (world + world_to_map)',
                   'odom': 'odom -> base_footprint from /tf'},
        'rows': rows,
    }
    with gzip.open(os.path.join(args.out, 'drive.json.gz'), 'wt',
                   compresslevel=6) as f:
        json.dump(drive, f, separators=(',', ':'))
    files = sorted(os.listdir(src))
    meta = {
        'command': 'python3 docs/data/lab3/make_drive.py ' + ' '.join(
            sys.argv[1:] if argv is None else argv),
        'session': os.path.abspath(args.session),
        'drive': args.drive,
        'window_sim_s': [t0, t1], 'padding_s': PAD_S,
        'source_bag_sha256': {n: sha256(os.path.join(src, n))
                              for n in files},
        'session_meta': json.load(open(os.path.join(args.session,
                                                    'meta.json'))),
        'messages_written': counts,
        'map_to_odom_transforms_dropped': dropped_map_odom,
        'scans_in_drive': len(rows),
        'interp_max_gap_s': max(gaps) if gaps else None,
        'world_to_map': list(w2m),
    }
    with open(os.path.join(args.out, 'drive_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1, sort_keys=True)
    print(json.dumps({k: meta[k] for k in (
        'window_sim_s', 'messages_written', 'map_to_odom_transforms_dropped',
        'scans_in_drive', 'interp_max_gap_s')}, indent=1))


if __name__ == '__main__':
    main()
