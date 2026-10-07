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
Is the actor visible to the robot's LiDAR? Measured, per scan.

  lab5_actor_seen.py RUN_DIR [--within 2.5] [--out actor_seen.json]

For every ``/scan`` (stamp t) while the actor -- placed where ``/lab/actors``
says it was commanded at t -- is within ``--within`` metres of the robot's
GROUND-TRUTH position, take the beam that points at the actor's centre
(bearing from the lidar, mounted at ``coco_config.robot.LIDAR_MOUNT_XYZ``
= (-0.09, +0.10) m in the base frame) and compare its measured range
with the geometry: ``distance - radius``. A beam that returns within
``tol`` of that is a hit. ``run.json`` (lab5_extract.py) must exist.

Also counts beams within +-0.2 rad of the bearing that are shorter than
the expected free-space range would be without the actor, as a second,
looser check. Nothing here can make the actor visible; it only reports.
"""

import argparse
import bisect
import json
import math
import os
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run_dir')
    ap.add_argument('--within', type=float, default=2.5)
    ap.add_argument('--tol', type=float, default=0.08)
    ap.add_argument('--lidar-x', type=float, default=-0.09)
    ap.add_argument('--lidar-y', type=float, default=0.10)
    ap.add_argument('--out', default='actor_seen.json')
    a = ap.parse_args()
    run = json.load(open(os.path.join(a.run_dir, 'run.json')))
    gt = run['gt']
    ts = [g[0] for g in gt]
    tracks = run['actors']
    if not tracks:
        print('no actors in this run')
        return 1
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=os.path.join(a.run_dir, 'bag'),
                                     storage_id='mcap'),
           rosbag2_py.ConverterOptions('cdr', 'cdr'))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=['/scan']))
    cls = get_message(types['/scan'])
    rows = []
    while r.has_next():
        _, data, _ = r.read_next()
        m = deserialize_message(data, cls)
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        i = bisect.bisect_left(ts, t)
        if i <= 0 or i >= len(gt):
            continue
        _, rx, ry, ryaw = gt[i]
        c, s_ = math.cos(ryaw), math.sin(ryaw)
        lx = rx + c * a.lidar_x - s_ * a.lidar_y
        ly = ry + s_ * a.lidar_x + c * a.lidar_y
        for aid, tr in tracks.items():
            tts = [s[0] for s in tr]
            j = bisect.bisect_right(tts, t) - 1
            if j < 0:
                continue
            _, ax, ay, _ = tr[j]
            d = math.hypot(ax - lx, ay - ly)
            if d > a.within:
                continue
            bearing = math.atan2(ay - ly, ax - lx) - ryaw
            bearing = math.atan2(math.sin(bearing), math.cos(bearing))
            k = round((bearing - m.angle_min) / m.angle_increment)
            if not 0 <= k < len(m.ranges):
                rows.append([t, aid, d, None, None, 'out of the field of '
                             'view'])
                continue
            meas = m.ranges[k]
            expect = d - 0.15
            rows.append([round(t, 3), aid, round(d, 4),
                         round(float(meas), 4), round(expect, 4),
                         'hit' if abs(meas - expect) <= a.tol else 'miss'])
    hits = sum(1 for x in rows if x[5] == 'hit')
    seen = [x for x in rows if x[5] in ('hit', 'miss')]
    out = {'run': os.path.basename(a.run_dir), 'within_m': a.within,
           'tol_m': a.tol, 'scans_in_range': len(seen), 'hits': hits,
           'misses': len(seen) - hits,
           'out_of_view': sum(1 for x in rows if x[5].startswith('out')),
           'abs_error_m': sorted(abs(x[3] - x[4]) for x in seen)[
               len(seen) // 2] if seen else None,
           'rows': rows}
    with open(os.path.join(a.run_dir, a.out), 'w') as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
