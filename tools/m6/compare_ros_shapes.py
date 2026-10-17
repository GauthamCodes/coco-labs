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
Compare the ROS-shaped model with recorded Stack bags (M6F.7).

    compare_ros_shapes.py [--out docs/v2/m6/data/ros_shapes_vs_stack.json]

Needs ROS 2 Jazzy (``rosbag2_py``). The bags are the committed fixtures
``coco_lab_ros/test/fixtures/bags/lab2_kidnap_recovery_k1`` (``/scan``,
``/diff_drive_controller/odom``, ``/model/coco/odometry``, ``/tf_static``) and
``lab5_crossing_dwb_1`` (``/diff_drive_controller/cmd_vel``, ``/lab/plan``).
Shapes: the scan's geometry and frame, the static transforms, the frames of
odometry, commands and paths. Values: every recorded scan against the model's
scan from the recorded ground-truth pose (``/model/coco/odometry``, world frame,
shifted into the map frame) on World Spec v1, beam by beam, wherever both
ranges are finite and inside the sensor's limits.
"""

import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
BAGS = os.path.join(REPO, 'coco_lab_ros', 'test', 'fixtures', 'bags')


def _yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def compare():
    import yaml
    from coco_lab import ros_shapes as rs
    from coco_lab.arena import Arena
    from coco_lab.sketch import wrap
    from coco_lab_ros.adapter import read_bag

    with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    a = Arena(spec, seed=1)
    lab2 = os.path.join(BAGS, 'lab2_kidnap_recovery_k1')
    lab5 = os.path.join(BAGS, 'lab5_crossing_dwb_1')
    scans, truth, first = [], [], {}
    for topic, msg, _ in read_bag(lab2, ['/scan', '/model/coco/odometry', '/tf_static',
                                         '/diff_drive_controller/odom']):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9 \
            if hasattr(msg, 'header') else None
        first.setdefault(topic, msg)
        if topic == '/scan':
            scans.append((t, msg))
        elif topic == '/model/coco/odometry':
            truth.append((t, msg.pose.pose.position.x, msg.pose.pose.position.y,
                          _yaw(msg.pose.pose.orientation)))
    for topic, msg, _ in read_bag(lab5, ['/diff_drive_controller/cmd_vel', '/lab/plan']):
        first.setdefault(topic, msg)
    s = first['/scan']
    model = rs.laser_scan(a)
    static = {(tr.header.frame_id, tr.child_frame_id):
              [tr.transform.translation.x, tr.transform.translation.y,
               tr.transform.translation.z] for tr in first['/tf_static'].transforms}
    ours = {(tr['header']['frame_id'], tr['child_frame_id']):
            [tr['transform']['translation'][k] for k in 'xyz']
            for tr in rs.tf_static(a)['transforms']}
    odom = first['/diff_drive_controller/odom']
    shapes = {
        'scan': {'stack': {'frame_id': s.header.frame_id, 'angle_min': s.angle_min,
                           'angle_max': s.angle_max, 'angle_increment': s.angle_increment,
                           'time_increment': s.time_increment, 'scan_time': s.scan_time,
                           'range_min': s.range_min, 'range_max': s.range_max,
                           'ranges': len(s.ranges), 'intensities': len(s.intensities)},
                 'model': {'frame_id': model['header']['frame_id'],
                           **{k: model[k] for k in ('angle_min', 'angle_max',
                                                    'angle_increment', 'time_increment',
                                                    'scan_time', 'range_min', 'range_max')},
                           'ranges': len(model['ranges']),
                           'intensities': len(model['intensities'])}},
        'tf_static': {'stack': {f'{p}->{c}': v for (p, c), v in sorted(static.items())
                                if (p, c) in ours},
                      'model': {f'{p}->{c}': v for (p, c), v in sorted(ours.items())}},
        'odometry_frames': {'stack': [odom.header.frame_id, odom.child_frame_id],
                            'model': [rs.odometry(a)['header']['frame_id'],
                                      rs.odometry(a)['child_frame_id']]},
        'cmd_vel_frame': {'stack': first['/diff_drive_controller/cmd_vel'].header.frame_id,
                          'model': rs.twist_stamped(0.0, 0.0, 0.0)['header']['frame_id']},
        'plan_frame': {'stack': first['/lab/plan'].header.frame_id,
                       'model': rs.path([(0.0, 0.0), (1.0, 0.0)], 0.0)['header']['frame_id']},
    }
    dx, dy = spec['world_to_map']
    diffs = []
    for t, sc in scans:
        tr = min(truth, key=lambda r: abs(r[0] - t))
        a.pose = (tr[1] + dx, tr[2] + dy, wrap(tr[3]))
        for rec, mod in zip(sc.ranges, a._scan()):
            if math.isfinite(rec) and sc.range_min <= rec <= sc.range_max \
                    and math.isfinite(mod) and mod < a.lidar.range_max:
                diffs.append(abs(rec - mod))
    diffs.sort()
    values = {'bag': 'lab2_kidnap_recovery_k1', 'scans': len(scans), 'beams': len(diffs),
              'median_abs_m': statistics.median(diffs),
              'p90_abs_m': diffs[int(0.9 * len(diffs))],
              'within_0.05_m': sum(d <= 0.05 for d in diffs) / len(diffs),
              'world': 'worlds/coco_arena_v1.yaml',
              'pose': '/model/coco/odometry (Gazebo ground truth), nearest stamp'}
    return {'schema': 'coco_lab.m6f.ros_shapes_vs_stack', 'version': 1,
            'evidence': 'MODEL vs STACK (recorded)', 'shapes': shapes,
            'scan_values': values}


def main():
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(
        REPO, 'docs', 'v2', 'm6', 'data', 'ros_shapes_vs_stack.json')
    result = compare()
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.write('\n')
    print(json.dumps(result['scan_values']))
    print(out)


if __name__ == '__main__':
    main()
