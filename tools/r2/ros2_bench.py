#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R2.7: drive Gazebo + Nav2 through COCO-Bench scenarios (STACK evidence). Run by
tools/m6/m6f8_run.sh as its NAV_DRIVER (one fresh simulator per run):

    ros2_bench.py SCENARIOS.json OUT/results.jsonl --world LEVEL --mode plan|drive|round [...]

SCENARIOS.json: ``{"start": [x, y, yaw], "scenarios": [{"id", "start", "goal"}], "servers": [...]}``.

- ``plan``: for every scenario, ask each named ComputePathToPose server (Nav2's
  ``compute_path_to_pose`` with planner_id GridBased -- stock Nav2 -- and the user's
  ``user_compute_path_to_pose``) for a path from the scenario's start to its goal on the LIVE
  global costmap (use_start: no driving); record success, the path's length and the time asked.
- ``drive``: for every scenario, teleport COCO to its start (Gazebo set_pose), re-initialise
  localisation, send NavigateToPose and record m6f8_nav.py's row (status, driven metres from
  Gazebo's ground truth, sim seconds, final distance to the goal).
- ``round``: the goal file's ordered goals from one start (m6f8_nav.py's own behaviour).
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'm6'))
from m6f8_nav import quat, Runner  # noqa: E402
from nav2_msgs.action import ComputePathToPose  # noqa: E402
import rclpy  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402


def plan_row(n, client, server, sc, wait_s=120.0):
    row = {'id': sc['id'], 'server': server, 'start': sc['start'], 'goal': sc['goal']}
    if not client.wait_for_server(timeout_sec=20.0):
        return dict(row, status='NO-SERVER')
    g = ComputePathToPose.Goal()
    g.use_start = True
    g.planner_id = 'GridBased'
    for ps, (x, y, th) in ((g.start, sc['start']), (g.goal, sc['goal'])):
        ps.header.frame_id = 'map'
        ps.header.stamp = n.get_clock().now().to_msg()
        ps.pose.position.x, ps.pose.position.y = float(x), float(y)
        q = quat(th)
        (ps.pose.orientation.x, ps.pose.orientation.y, ps.pose.orientation.z,
         ps.pose.orientation.w) = q
    t0, s0 = time.time(), n.now_s()
    fut = client.send_goal_async(g)
    rclpy.spin_until_future_complete(n, fut, timeout_sec=30.0)
    h = fut.result()
    if h is None or not h.accepted:
        return dict(row, status='REJECTED')
    res = h.get_result_async()
    rclpy.spin_until_future_complete(n, res, timeout_sec=wait_s)
    r = res.result()
    row['wall_s'] = round(time.time() - t0, 3)
    row['sim_s'] = round(n.now_s() - s0, 3)
    if r is None:
        return dict(row, status='NO-RESULT')
    pts = [(p.pose.position.x, p.pose.position.y) for p in r.result.path.poses]
    row['status'] = 'SUCCEEDED' if r.status == 4 and pts else f'STATUS_{r.status}'
    row['error_code'] = int(getattr(r.result, 'error_code', -1))
    row['poses'] = len(pts)
    row['length_m'] = round(sum(math.hypot(b[0] - a[0], b[1] - a[1])
                                for a, b in zip(pts, pts[1:])), 4) if pts else None
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('goals')
    ap.add_argument('out')
    ap.add_argument('--world', default='coco_depot_v1')
    ap.add_argument('--mode', default='plan', choices=('plan', 'drive', 'round'))
    ap.add_argument('--timeout', type=float, default=420.0)
    ap.add_argument('--initial-pose', action='store_true')
    ap.add_argument('--plan-wait', type=float, default=120.0, help='wall seconds to wait for a plan')
    ap.add_argument('--spawn', action='append', default=[], metavar='PACKAGE:ACTION',
                    help='also run coco_user_<x> as PACKAGE serving ACTION (a second user planner)')
    o = ap.parse_args()
    doc = json.load(open(o.goals))
    extra = []
    for sp in o.spawn:
        pkg, action = sp.split(':')
        extra.append(subprocess.Popen(
            ['ros2', 'run', pkg, pkg, '--ros-args', '-p', 'use_sim_time:=true', '-p',
             f'action_name:={action}', '-r', f'__node:={pkg}_extra'],
            stdout=open(Path(o.out).parent / f'{pkg}_extra.log', 'w'), stderr=subprocess.STDOUT,
            start_new_session=True))
    rclpy.init()
    n = Runner()
    n.spin_for(3.0)
    for _ in range(3):
        n.initial_pose(*doc['start'])
        n.spin_for(1.0)
    n.spin_for(5.0)
    with open(o.out, 'a') as f:
        def emit(row):
            f.write(json.dumps(row) + '\n')
            f.flush()
            print(json.dumps({k: row.get(k) for k in ('id', 'server', 'status', 'length_m',
                                                      'driven_m', 'sim_s', 'truth_to_goal_m')}),
                  flush=True)
        if o.mode == 'plan':
            clients = {s: ActionClient(n, ComputePathToPose, s) for s in doc['servers']}
            for sc in doc['scenarios']:
                for s, c in clients.items():
                    row = plan_row(n, c, s, sc, o.plan_wait)
                    row['plan_wait_s'] = o.plan_wait
                    emit(row)
        elif o.mode == 'drive':
            for sc in doc['scenarios']:
                ok = n.teleport(o.world, *sc['start'])
                n.spin_for(2.0)
                for _ in range(3):
                    n.initial_pose(*sc['start'])
                    n.spin_for(1.0)
                n.spin_for(4.0)
                row = n.goal({'id': sc['id'], 'pose': sc['goal']}, o.timeout)
                row['teleported'] = ok
                row['start'] = sc['start']
                emit(row)
        else:
            for g in doc['goals']:
                emit(n.goal(g, o.timeout))
    rclpy.shutdown()
    import os
    import signal
    for p in extra:   # the whole group: `ros2 run` leaves its node running if only it is stopped
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
