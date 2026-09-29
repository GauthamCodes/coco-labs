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
Phase 1C live checks. Publishes nothing.

  lab1c_watch.py once --out F.json          one sample (below)
  lab1c_watch.py watch --out F.jsonl        one sample per second until SIGINT
  lab1c_watch.py params --merged M.yaml --out F.json
                                            live readback vs the merged file
  lab1c_watch.py wait-status --out F.json --timeout S
                                            wait for a terminal /lab/status

A sample: the publishers (node names) of the wheel topic and of every
arbiter input and command-chain link; the arbiter's latest status line;
the lab_planner node's publishers and their safety verdict
(``coco_lab_ros.safety.violations``); the wall and ROS time.

``params`` reads EVERY leaf of the merged file's ``planner_server`` and
``global_costmap`` sections back off the running nodes (GetParameters),
and exits 1 on any mismatch (plan F-3: stop before measuring).
"""

import argparse
import json
import math
import signal
import sys
import threading
import time

from coco_lab_ros import safety
from coco_lab_ros.params import flatten, load
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import (QoSDurabilityPolicy, QoSProfile,
                       QoSReliabilityPolicy)
from std_msgs.msg import String

TOPICS = (safety.WHEEL_TOPIC,) + safety.ARBITER_INPUTS + safety.COMMAND_CHAIN
TERMINAL = ('succeeded', 'follow_failed', 'failed', 'error', 'done')


class Watch:
    def __init__(self):
        rclpy.init()
        self.node = rclpy.create_node('lab1c_watch')
        self.status = None
        self.lab = []
        self.node.create_subscription(String, '/cmd_vel_arbiter/status',
                                      self._on_arb, 10)
        self.node.create_subscription(
            String, '/lab/status', self._on_lab,
            QoSProfile(depth=50, reliability=QoSReliabilityPolicy.RELIABLE,
                       durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
        self.ex = MultiThreadedExecutor(num_threads=2)
        self.ex.add_node(self.node)
        self.spin = threading.Thread(target=self.ex.spin, daemon=True)
        self.spin.start()

    def _on_arb(self, msg):
        self.status = msg.data

    def _on_lab(self, msg):
        self.lab.append(json.loads(msg.data))

    def sample(self):
        n = self.node
        pubs = {t: sorted(i.node_name for i in
                          n.get_publishers_info_by_topic(t)) for t in TOPICS}
        lab = None
        names = n.get_node_names_and_namespaces()
        if ('lab_planner', '/') in names:
            lp = n.get_publisher_names_and_types_by_node('lab_planner', '/')
            lab = {'publishers': sorted(t for t, _ in lp),
                   'violations': safety.violations(lp)}
        return {'wall': time.time(),
                'ros': n.get_clock().now().nanoseconds * 1e-9,
                'publishers': pubs, 'arbiter_status': self.status,
                'lab_planner': lab,
                'wheel_ok': pubs[safety.WHEEL_TOPIC] == ['cmd_vel_arbiter'],
                'lab_phase': self.lab[-1]['phase'] if self.lab else None}

    def close(self):
        # Stop the executor and JOIN its thread before destroying the node:
        # destroying it under a spinning executor segfaulted at exit in the
        # 1C dry run (measured, core dumped).
        self.ex.shutdown()
        self.spin.join(timeout=10)
        self.node.destroy_node()
        rclpy.shutdown()


def param_value(v):
    t = v.type
    return {1: v.bool_value, 2: v.integer_value, 3: v.double_value,
            4: v.string_value, 6: list(v.bool_array_value),
            7: list(v.integer_array_value), 8: list(v.double_array_value),
            9: list(v.string_array_value)}.get(t)


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def readback(w, merged_path):
    from rcl_interfaces.srv import GetParameters
    doc = load(merged_path)
    out = {'merged': merged_path, 'checked': 0, 'mismatches': []}
    for node, section in (('/planner_server', doc['planner_server']),
                          ('/global_costmap/global_costmap',
                           doc['global_costmap']['global_costmap'])):
        want = flatten(section['ros__parameters'])
        cli = w.node.create_client(GetParameters, f'{node}/get_parameters')
        if not cli.wait_for_service(timeout_sec=20):
            out['mismatches'].append([node, '*', 'service unavailable'])
            continue
        names = sorted(want)
        fut = cli.call_async(GetParameters.Request(names=names))
        deadline = time.monotonic() + 20
        while not fut.done() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not fut.done():
            out['mismatches'].append([node, '*', 'timeout'])
            continue
        for name, v in zip(names, fut.result().values):
            got = param_value(v)
            out['checked'] += 1
            if not same(want[name], got):
                out['mismatches'].append([node, name, want[name], got])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cmd', choices=('once', 'watch', 'params',
                                    'wait-status'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--merged')
    ap.add_argument('--timeout', type=float, default=900.0)
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
        if a.cmd == 'wait-status':
            deadline = time.monotonic() + a.timeout
            while time.monotonic() < deadline:
                if w.lab and w.lab[-1]['phase'] in TERMINAL:
                    break
                time.sleep(0.2)
            json.dump(w.lab, open(a.out, 'w'), sort_keys=True, indent=1)
            last = w.lab[-1]['phase'] if w.lab else None
            print(f'lab status: {last}')
            return 0 if last in TERMINAL else 2
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
