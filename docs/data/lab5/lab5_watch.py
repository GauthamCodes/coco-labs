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
Phase 6 (Lab 5) live checks. Publishes nothing, except ``inject``.

Phase 1C's ``lab1c_watch.py`` (imported by path, not copied) plus:

  lab5_watch.py once|watch|wait-status ...   as 1C, and every sample also
                                             checks the lab_actors node's
                                             publishers (safety.ACTOR_TOPICS)
  lab5_watch.py params --merged M.yaml --out F.json
                                             live readback of EVERY leaf of
                                             the merged controller_server,
                                             planner_server and both
                                             costmaps' sections (stop before
                                             measuring on any mismatch)
  lab5_watch.py inject --dx DX --dy DY --dyaw DYAW --sigma S --out F.json
                                             THE OPERATOR ACTION of the
                                             mislocalised scenario: one
                                             /initialpose, offset from the
                                             robot's ground truth by
                                             (DX, DY, DYAW) in the map frame
                                             -- the interface RViz's "2D
                                             Pose Estimate" uses, as C2-M5.1's
                                             injector did. Then it waits and
                                             records AMCL's belief against
                                             ground truth.
"""

import argparse
import importlib.util
import json
import math
import os
import signal
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'lab1c_watch', os.path.join(HERE, '..', 'lab1c', 'lab1c_watch.py'))
w1c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w1c)

from coco_lab_ros import safety  # noqa: E402
from coco_lab_ros.params import flatten, load  # noqa: E402

SECTIONS = (
    ('/controller_server', ('controller_server',)),
    ('/planner_server', ('planner_server',)),
    ('/local_costmap/local_costmap', ('local_costmap', 'local_costmap')),
    ('/global_costmap/global_costmap', ('global_costmap', 'global_costmap')),
)

WORLD_TO_MAP = (2.0, 0.0)


class Watch(w1c.Watch):
    """1C's watch, plus the actor node's publisher verdict."""

    def sample(self):
        s = super().sample()
        n = self.node
        act = None
        if ('lab_actors', '/') in n.get_node_names_and_namespaces():
            lp = n.get_publisher_names_and_types_by_node('lab_actors', '/')
            act = {'publishers': sorted(t for t, _ in lp),
                   'violations': safety.violations(lp, safety.ACTOR_TOPICS)}
        s['lab_actors'] = act
        return s


def _get(cli, names, timeout=30.0):
    """Return the values list, or None on timeout."""
    from rcl_interfaces.srv import GetParameters
    fut = cli.call_async(GetParameters.Request(names=names))
    deadline = time.monotonic() + timeout
    while not fut.done() and time.monotonic() < deadline:
        time.sleep(0.05)
    return list(fut.result().values) if fut.done() else None


def readback(w, merged_path):
    """
    Read every merged leaf back off the running nodes.

    rclcpp answers a GetParameters request that names ANY undeclared
    parameter with an EMPTY list (measured, Phase 6: DWB does not declare
    the mission file's ``FollowPath.stateful``), which a plain ``zip``
    turns into "0 checked, 0 mismatches" -- a pass that saw nothing. So a
    short answer falls back to one request per name; a name the node does
    not declare is listed under ``undeclared`` (the node ignores it, as it
    does in the mission), and a section that checks nothing fails.
    """
    from rcl_interfaces.srv import GetParameters
    doc = load(merged_path)
    out = {'merged': merged_path, 'checked': 0, 'mismatches': [],
           'undeclared': [], 'per_node': {}}
    for node, keys in SECTIONS:
        section = doc
        for k in keys:
            section = section[k]
        want = flatten(section['ros__parameters'])
        cli = w.node.create_client(GetParameters, f'{node}/get_parameters')
        if not cli.wait_for_service(timeout_sec=20):
            out['mismatches'].append([node, '*', 'service unavailable'])
            continue
        names = sorted(want)
        values = _get(cli, names)
        if values is None:
            out['mismatches'].append([node, '*', 'timeout'])
            continue
        if len(values) != len(names):
            values = []
            for name in names:
                one = _get(cli, [name])
                values.append(one[0] if one else None)
        checked = 0
        for name, v in zip(names, values):
            if v is None:
                out['undeclared'].append([node, name])
                continue
            got = w1c.param_value(v)
            checked += 1
            if not w1c.same(want[name], got):
                out['mismatches'].append([node, name, want[name], got])
        out['per_node'][node] = {'leaves': len(names), 'checked': checked}
        out['checked'] += checked
        if checked == 0:
            out['mismatches'].append([node, '*', 'nothing checked'])
    return out


def inject(w, dx, dy, dyaw, sigma, settle):
    """Publish one offset /initialpose; return the before/after record."""
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry
    box = {'gt': None, 'amcl': []}

    def on_gt(m):
        q = m.pose.pose.orientation
        box['gt'] = (m.pose.pose.position.x + WORLD_TO_MAP[0],
                     m.pose.pose.position.y + WORLD_TO_MAP[1],
                     math.atan2(2 * (q.w * q.z + q.x * q.y),
                                1 - 2 * (q.y * q.y + q.z * q.z)))

    def on_amcl(m):
        p = m.pose.pose.position
        box['amcl'].append((time.time(), p.x, p.y))
    from rclpy.qos import (QoSDurabilityPolicy, QoSProfile,
                           QoSReliabilityPolicy)
    w.node.create_subscription(Odometry, '/model/coco/odometry', on_gt, 10)
    w.node.create_subscription(
        PoseWithCovarianceStamped, '/amcl_pose', on_amcl,
        QoSProfile(depth=10, reliability=QoSReliabilityPolicy.RELIABLE,
                   durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
    pub = w.node.create_publisher(PoseWithCovarianceStamped,
                                  '/initialpose', 10)
    deadline = time.monotonic() + 30
    while box['gt'] is None and time.monotonic() < deadline:
        time.sleep(0.1)
    if box['gt'] is None:
        return {'ok': False, 'reason': 'no ground truth'}
    while pub.get_subscription_count() == 0 and time.monotonic() < deadline:
        time.sleep(0.1)
    gx, gy, gyaw = box['gt']
    tx, ty, tyaw = gx + dx, gy + dy, gyaw + dyaw
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = w.node.get_clock().now().to_msg()
    msg.pose.pose.position.x, msg.pose.pose.position.y = tx, ty
    msg.pose.pose.orientation.z = math.sin(tyaw / 2)
    msg.pose.pose.orientation.w = math.cos(tyaw / 2)
    cov = [0.0] * 36
    cov[0] = cov[7] = sigma * sigma
    cov[35] = 0.01 ** 2
    msg.pose.covariance = cov
    t0 = time.time()
    pub.publish(msg)
    time.sleep(settle)
    after = [a for a in box['amcl'] if a[0] >= t0]
    last = after[-1] if after else None
    gx2, gy2, _ = box['gt']
    return {'ok': True, 'gt_at_inject': [gx, gy, gyaw],
            'told': [tx, ty, tyaw], 'sigma_xy': sigma,
            'amcl_after': [last[1], last[2]] if last else None,
            'gt_after': [gx2, gy2],
            'gap_after_m': (math.hypot(last[1] - gx2, last[2] - gy2)
                            if last else None),
            'amcl_updates_after': len(after), 'settle_s': settle}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=('once', 'watch', 'params',
                                    'wait-status', 'inject'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--merged')
    ap.add_argument('--timeout', type=float, default=900.0)
    ap.add_argument('--dx', type=float, default=0.0)
    ap.add_argument('--dy', type=float, default=0.0)
    ap.add_argument('--dyaw', type=float, default=0.0)
    ap.add_argument('--sigma', type=float, default=0.05)
    ap.add_argument('--settle', type=float, default=8.0)
    a = ap.parse_args()
    w = Watch()
    try:
        time.sleep(1.5)                     # discovery
        if a.cmd == 'once':
            s = w.sample()
            json.dump(s, open(a.out, 'w'), sort_keys=True, indent=1)
            print(json.dumps({'wheel_ok': s['wheel_ok'],
                              'wheel': s['publishers'][safety.WHEEL_TOPIC],
                              'arbiter': s['arbiter_status']}))
            return 0 if s['wheel_ok'] else 1
        if a.cmd == 'params':
            r = readback(w, a.merged)
            json.dump(r, open(a.out, 'w'), sort_keys=True, indent=1)
            print(f'params checked {r["checked"]} mismatches '
                  f'{len(r["mismatches"])}')
            return 1 if r['mismatches'] or not r['checked'] else 0
        if a.cmd == 'inject':
            r = inject(w, a.dx, a.dy, a.dyaw, a.sigma, a.settle)
            json.dump(r, open(a.out, 'w'), sort_keys=True, indent=1)
            print(json.dumps(r, sort_keys=True))
            return 0 if r['ok'] else 1
        if a.cmd == 'wait-status':
            deadline = time.monotonic() + a.timeout
            while time.monotonic() < deadline:
                if w.lab and w.lab[-1]['phase'] in w1c.TERMINAL:
                    break
                time.sleep(0.2)
            json.dump(w.lab, open(a.out, 'w'), sort_keys=True, indent=1)
            last = w.lab[-1]['phase'] if w.lab else None
            print(f'lab status: {last}')
            return 0 if last in w1c.TERMINAL else 2
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        with open(a.out, 'a') as f:
            while not stop.is_set():
                f.write(json.dumps(w.sample(), sort_keys=True) + '\n')
                f.flush()
                stop.wait(1.0)
        return 0
    finally:
        w.close()


if __name__ == '__main__':
    sys.exit(main())
