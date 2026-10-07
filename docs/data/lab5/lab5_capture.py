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
Freeze Lab 5's global paths: ask Nav2's own planner once, write them down.

  lab5_capture.py --scenarios S.json --out DIR --meta META.json

For every distinct ``path`` file the scenarios name, this asks
planner_server for ``GridBased`` (SmacPlanner2D, the mission's global
planner) from the scenario's ``start`` to its ``goal`` on the live global
costmap (``coco_lab_ros.nav2_client.Nav2Probe``: publishes nothing, moves
nothing) and writes ``DIR/<path file>``::

    {"schema": "coco_lab_ros.lab5_path", "version": "1.0", "frame": "map",
     "poses": [[x, y, yaw], ...], "planner_id": "GridBased",
     "start": [...], "goal": [...], "costmap_sha256": ..., "meta": ...}

Every controller run then READS that file (``lab_planner path_file:=``):
the global path is frozen, so a controller comparison compares
controllers, not plans (ROADMAP invariant 6).
"""

import argparse
import json
import math
import os
import sys
import time

from coco_lab_ros.nav2_client import Nav2Probe
from coco_lab_ros.costmap import Snapshot
import rclpy
from rclpy.executors import MultiThreadedExecutor


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scenarios', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--meta', required=True)
    a = ap.parse_args()
    scen = json.load(open(a.scenarios))['scenarios']
    meta = json.load(open(a.meta))
    wanted = {}
    for s in scen:
        wanted.setdefault(s['path'], (s['start'], s['goal'], s['id']))
    rclpy.init()
    probe = Nav2Probe()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(probe)
    import threading
    threading.Thread(target=ex.spin, daemon=True).start()
    rc = 0
    try:
        msg, h = probe.wait_settled(repeats=2, timeout=120.0)
        if msg is None or not probe.wait_for_planner(60.0):
            print('no settled costmap or no planner')
            return 2
        snap = Snapshot.from_msg(msg, probe.costmap_topic)
        os.makedirs(a.out, exist_ok=True)
        for name, (start, goal, sid) in sorted(wanted.items()):
            r = probe.compute('GridBased', tuple(start), tuple(goal))
            if not r['ok']:
                print(f'{name}: planner failed: {r["error_msg"]}')
                rc = 1
                continue
            poses = [[float(x), float(y), float(yaw)]
                     for x, y, yaw in r['poses']]
            doc = {
                'schema': 'coco_lab_ros.lab5_path', 'version': '1.0',
                'frame': 'map', 'planner_id': 'GridBased',
                'planner': 'nav2_smac_planner/SmacPlanner2D (the mission\'s)',
                'first_scenario': sid, 'start': start, 'goal': goal,
                'poses': poses,
                'length_m': sum(math.hypot(b[0] - a_[0], b[1] - a_[1])
                                for a_, b in zip(poses, poses[1:])),
                'planning_time_s': r['planning_time'],
                'costmap_sha256': h, 'costmap': snap.describe(),
                'captured_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                              time.gmtime()),
                'git_commit': meta.get('git_commit'),
                'git_dirty_paths': meta.get('git_dirty_paths'),
            }
            path = os.path.join(a.out, name)
            with open(path, 'w') as f:
                json.dump(doc, f, sort_keys=True, indent=1)
            print(f'{name}: {len(poses)} poses, {doc["length_m"]:.3f} m, '
                  f'end yaw {poses[-1][2]:.4f} (goal {goal[2]:.4f})')
    finally:
        ex.shutdown()
        probe.destroy_node()
        rclpy.shutdown()
    return rc


if __name__ == '__main__':
    sys.exit(main())
