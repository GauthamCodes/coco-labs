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
Phase 4: record what a SLAM backend publishes while a drive is replayed.

Subscribes (use_sim_time, the bag's /clock):

- ``/tf``: every ``map -> odom`` the SLAM publishes, with its header stamp
  and the sim time it arrived -- the ONLINE correction, which composed with
  the recorded wheel odometry gives the backend's belief at each scan;
- ``/map`` (``nav_msgs/OccupancyGrid``, transient local): the latest one,
  which at the end of the drive is the backend's final map.

On SIGINT/SIGTERM it writes ``--out`` (JSON) and exits. It publishes
nothing.
"""

import argparse
import json
import math
import os
import signal
import sys
import threading

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)
from nav_msgs.msg import OccupancyGrid
from tf2_msgs.msg import TFMessage


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y),
                      1 - 2 * (q.y * q.y + q.z * q.z))


class Recorder(Node):

    def __init__(self):
        super().__init__('lab3_slam_record',
                         parameter_overrides=[Parameter(
                             'use_sim_time', Parameter.Type.BOOL, True)])
        self.lock = threading.Lock()
        self.map_to_odom = []
        self.maps_seen = 0
        self.last_map = None
        self.create_subscription(TFMessage, '/tf', self.on_tf, 1000)
        latched = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                             reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, latched)

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_tf(self, msg):
        rows = []
        for tr in msg.transforms:
            if tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
                t = tr.transform
                rows.append((tr.header.stamp.sec +
                             tr.header.stamp.nanosec * 1e-9, self.now(),
                             t.translation.x, t.translation.y,
                             yaw_of(t.rotation)))
        if rows:
            with self.lock:
                self.map_to_odom.extend(rows)

    def on_map(self, msg):
        with self.lock:
            self.maps_seen += 1
            self.last_map = (self.now(), msg)

    def dump(self, path):
        with self.lock:
            m = None
            if self.last_map is not None:
                t, g = self.last_map
                i = g.info
                m = {'received_sim_s': t,
                     'stamp': g.header.stamp.sec + g.header.stamp.nanosec * 1e-9,
                     'frame_id': g.header.frame_id,
                     'width': i.width, 'height': i.height,
                     'resolution': i.resolution,
                     'origin': [i.origin.position.x, i.origin.position.y,
                                yaw_of(i.origin.orientation)],
                     # int8 -1..100; -1 = unknown
                     'data': list(g.data)}
            out = {'map_to_odom': self.map_to_odom,
                   'map_to_odom_columns': ['stamp', 'received_sim_s', 'x',
                                           'y', 'yaw'],
                   'maps_seen': self.maps_seen, 'final_map': m}
        with open(path, 'w') as f:
            json.dump(out, f, separators=(',', ':'))
        return len(out['map_to_odom']), m is not None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    rclpy.init(args=None)
    node = Recorder()
    stop = threading.Event()

    def on_signal(*_):
        stop.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    ex = rclpy.executors.SingleThreadedExecutor()
    ex.add_node(node)
    th = threading.Thread(target=lambda: _spin(ex), daemon=True)
    th.start()
    stop.wait()
    n, has_map = node.dump(args.out)
    print(f'[lab3_slam_record] wrote {args.out}: {n} map->odom, '
          f'final map {"yes" if has_map else "NO"}', file=sys.stderr)
    sys.stderr.flush()
    # the file is written and closed; tearing rclpy down while the spin
    # thread is inside a wait aborted the process (measured), so leave now
    os._exit(0)


def _spin(ex):
    try:
        ex.spin()
    except ExternalShutdownException:
        pass


if __name__ == '__main__':
    main()
