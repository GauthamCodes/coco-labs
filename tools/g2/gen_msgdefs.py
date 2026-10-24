#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.5: what the browser's rosbag2 export needs from real ROS 2 Jazzy, generated once and
committed (the browser has no ROS):

    source /opt/ros/jazzy/setup.bash && tools/g2/gen_msgdefs.py [--check]

- ``lab_web/src/ros/msgdefs.json``: per message type the schema text rosbag2 writes into an
  MCAP file (``rosbag2_py.LocalMessageDefinitionSource``, encoding ``ros2msg``: the .msg text
  with its dependencies) and the type's RIHS01 hash (``share/<pkg>/msg/<Type>.json``). These are
  ROS 2's interface definitions (Apache-2.0), copied as text.
- ``lab_web/test/fixtures/cdr_goldens.json``: sample messages and the bytes
  ``rclpy.serialization.serialize_message`` gives for them (CDR, little endian). The browser's
  CDR writer (src/ros/cdr.ts) must give the same bytes (test/g2_cdr.test.ts). The samples are
  the parity fixture's own model messages (lab_web/test/fixtures/ros_shapes_parity.json) and a
  few edge cases (an empty frame id, an infinite range, an empty path).
"""
import argparse
import copy
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFS = os.path.join(REPO, 'lab_web', 'src', 'ros', 'msgdefs.json')
GOLD = os.path.join(REPO, 'lab_web', 'test', 'fixtures', 'cdr_goldens.json')
TYPES = ['sensor_msgs/msg/LaserScan', 'nav_msgs/msg/Odometry', 'nav_msgs/msg/Path',
         'nav_msgs/msg/OccupancyGrid', 'geometry_msgs/msg/TwistStamped', 'tf2_msgs/msg/TFMessage',
         'sensor_msgs/msg/JointState']
SHARE = os.environ.get('AMENT_PREFIX', '/opt/ros/jazzy') + '/share'


def defs():
    import rosbag2_py
    src = rosbag2_py.LocalMessageDefinitionSource()
    out = {}
    for t in TYPES:
        d = src.get_full_text(t)
        pkg, _, name = t.split('/')
        with open(os.path.join(SHARE, pkg, 'msg', f'{name}.json')) as f:
            h = next(x['hash_string'] for x in json.load(f)['type_hashes'] if x['type_name'] == t)
        out[t] = {'encoding': d.encoding, 'text': d.encoded_message_definition, 'type_hash': h}
    return out


def _inf(x):
    return math.inf if x is None else x


def samples():
    with open(os.path.join(REPO, 'lab_web', 'test', 'fixtures', 'ros_shapes_parity.json')) as f:
        fx = json.load(f)
    rows = []
    first = next(r for r in fx['ticks'] if 'ranges' in r)
    scan = dict(first['want']['scan'], ranges=[_inf(r) for r in first['ranges']])
    rows.append(('sensor_msgs/msg/LaserScan', 'parity tick scan (with no-return beams)', scan))
    r5 = fx['ticks'][5]['want']
    rows.append(('nav_msgs/msg/Odometry', 'parity tick 5 odom', r5['odom']))
    rows.append(('tf2_msgs/msg/TFMessage', 'parity tick 5 tf', r5['tf']))
    rows.append(('tf2_msgs/msg/TFMessage', 'tf_static', fx['info']['tf_static']))
    rows.append(('geometry_msgs/msg/TwistStamped', 'parity tick 5 cmd_vel (empty frame id)', r5['cmd_vel']))
    plan = next(r['want']['plan'] for r in fx['ticks'] if 'plan' in r['want'])
    rows.append(('nav_msgs/msg/Path', 'parity plan', plan))
    rows.append(('nav_msgs/msg/Path', 'empty path', {'header': {'stamp': {'sec': 0, 'nanosec': 0}, 'frame_id': 'map'}, 'poses': []}))
    grid = dict(fx['map']['grid'], info=dict(fx['map']['grid']['info'], width=3, height=2))
    grid['data'] = [0, 100, -1, 0, 0, 100]
    rows.append(('nav_msgs/msg/OccupancyGrid', 'a 3 x 2 grid (the map header)', grid))
    rows.append(('sensor_msgs/msg/JointState', 'arm joints', {
        'header': {'stamp': {'sec': 12, 'nanosec': 300000000}, 'frame_id': ''},
        'name': ['m_link1_Revolute-6', 'm_link2_Revolute-7', 'm_link3_Revolute-8', 'm_link3_Revolute-9'],
        'position': [0.1, -0.25, 0.5, -0.5], 'velocity': [], 'effort': []}))
    return rows


def goldens():
    from rclpy.serialization import serialize_message
    from rosidl_runtime_py import set_message_fields
    from rosidl_runtime_py.utilities import get_message
    out = []
    for t, what, msg in samples():
        m = get_message(t)()
        set_message_fields(m, copy.deepcopy(msg))   # it fills nested messages in place: keep ours a dict
        js = json.loads(json.dumps(msg, allow_nan=True).replace('Infinity', '1e999'))   # JSON for the test
        out.append({'type': t, 'what': what, 'msg': _nulls(js), 'cdr': serialize_message(m).hex()})
    return out


def _nulls(x):
    """inf -> None (JSON has no infinity; the test maps null back to Infinity)."""
    if isinstance(x, float) and math.isinf(x):
        return None
    if isinstance(x, list):
        return [_nulls(v) for v in x]
    if isinstance(x, dict):
        return {k: _nulls(v) for k, v in x.items()}
    return x


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    o = ap.parse_args()
    files = {DEFS: json.dumps(defs(), indent=1, sort_keys=True) + '\n',
             GOLD: json.dumps({'about': 'G2.5: CDR bytes from rclpy.serialization.serialize_message (ROS 2 Jazzy) '
                                        'for sample messages (tools/g2/gen_msgdefs.py)',
                               'samples': goldens()}, indent=1, sort_keys=True, allow_nan=False) + '\n'}
    bad = 0
    for path, text in files.items():
        if o.check:
            same = os.path.exists(path) and open(path).read() == text
            print(('current: ' if same else 'STALE: ') + path)
            bad += not same
        else:
            with open(path, 'w') as f:
                f.write(text)
            print('wrote', path, len(text), 'bytes')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
