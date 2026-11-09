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

R3 additions (opt-in; without them every mode runs exactly as in R2.7):

- ``--snap SERVER`` (plan mode, repeatable): ask SERVER a second time with the start and the goal
  moved to the nearest free cell (raw cost < 253, breadth first, 8-connected -- the rule COCO Lab
  and the exported user node use) of the live ``/global_costmap/costmap_raw``; the row's server
  is ``SERVER+snapped`` and it records both snap distances. Stock rows are unchanged.
- ``--costs FILE`` (drive mode): for every plan the controller receives
  (``/received_global_plan``), the raw cost under each pose in the live global costmap and in the
  live local costmap (RPP's collision check reads the local one; poses are moved into its frame
  with tf), one JSON line per plan: the scenario, counts of poses at cost >= 253 (inscribed or
  lethal), >= 128 and the maxima, and the whole local profile.
"""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'm6'))
from m6f8_nav import quat, Runner, yaw_of  # noqa: E402
from nav2_msgs.action import ComputePathToPose  # noqa: E402
from nav2_msgs.msg import Costmap  # noqa: E402
from nav_msgs.msg import Path as PathMsg  # noqa: E402
import rclpy  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from rclpy.time import Time  # noqa: E402

LETHAL = 253   # nav2_costmap_2d INSCRIBED_INFLATED_OBSTACLE: the centre may not be there
LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)


class Grid:
    """A received nav2_msgs/Costmap: raw cost lookups in its own frame."""

    def __init__(self, m):
        md = m.metadata
        self.frame, self.res = m.header.frame_id, md.resolution
        self.w, self.h = md.size_x, md.size_y
        self.ox, self.oy = md.origin.position.x, md.origin.position.y
        self.data = m.data

    def cell(self, x, y):
        mx, my = math.floor((x - self.ox) / self.res), math.floor((y - self.oy) / self.res)
        return (mx, my) if 0 <= mx < self.w and 0 <= my < self.h else None

    def cost(self, c):
        return None if c is None else int(self.data[c[1] * self.w + c[0]])

    def centre(self, c):
        return (self.ox + (c[0] + 0.5) * self.res, self.oy + (c[1] + 0.5) * self.res)

    def nearest_free(self, x, y, limit=40):
        start = self.cell(x, y)
        if start is None:
            return None
        seen, q = {start}, deque([start])
        while q:
            c = q.popleft()
            if self.cost(c) < LETHAL:
                return c
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                n = (c[0] + d[0], c[1] + d[1])
                if (n not in seen and 0 <= n[0] < self.w and 0 <= n[1] < self.h
                        and abs(n[0] - start[0]) <= limit):
                    seen.add(n)
                    q.append(n)
        return None


class Costs:
    """The live global and local costmaps, and the cost under each plan the controller gets."""

    def __init__(self, n, out_path):
        import tf2_ros
        self.n, self.out = n, open(out_path, 'a')
        self.glob = self.loc = None
        self.scenario = None
        self.tf = tf2_ros.Buffer()
        self.listener = tf2_ros.TransformListener(self.tf, n)
        n.create_subscription(Costmap, '/global_costmap/costmap_raw', self._g, LATCHED)
        n.create_subscription(Costmap, '/local_costmap/costmap_raw', self._l, LATCHED)
        n.create_subscription(PathMsg, '/received_global_plan', self._plan, 10)

    def _g(self, m):
        self.glob = Grid(m)

    def _l(self, m):
        self.loc = Grid(m)

    def _to(self, frame, src, pts):
        if frame == src:
            return pts
        try:
            t = self.tf.lookup_transform(frame, src, Time())
        except Exception:
            return None
        tx, ty = t.transform.translation.x, t.transform.translation.y
        th = yaw_of(t.transform.rotation)
        c, s = math.cos(th), math.sin(th)
        return [(tx + c * x - s * y, ty + s * x + c * y) for x, y in pts]

    def _plan(self, m):
        if self.scenario is None or not m.poses:
            return
        pts = [(p.pose.position.x, p.pose.position.y) for p in m.poses]
        src = m.header.frame_id or 'map'
        row = {'id': self.scenario, 'sim_s': round(self.n.now_s(), 3), 'frame': src,
               'poses': len(pts)}
        for key, g in (('global', self.glob), ('local', self.loc)):
            if g is None:
                row[key] = None
                continue
            q = self._to(g.frame, src, pts)
            if q is None:
                row[key] = {'tf': 'unavailable'}
                continue
            costs = [g.cost(g.cell(x, y)) for x, y in q]
            inside = [c for c in costs if c is not None]
            row[key] = {'frame': g.frame, 'inside': len(inside),
                        'max': max(inside) if inside else None,
                        'n_ge_253': sum(c >= LETHAL for c in inside),
                        'n_ge_128': sum(c >= 128 for c in inside)}
            if key == 'local':
                row[key]['profile'] = costs
        self.out.write(json.dumps(row) + '\n')
        self.out.flush()


def snapped(n, sc):
    """The scenario with start and goal moved to the nearest free cell of the live costmap."""
    g = None
    end = time.time() + 20.0
    while time.time() < end and g is None:
        g = getattr(n, 'snap_grid', None)
        rclpy.spin_once(n, timeout_sec=0.1)
    if g is None:
        return None
    out = dict(sc)
    for k in ('start', 'goal'):
        x, y, th = sc[k][0], sc[k][1], sc[k][2] if len(sc[k]) > 2 else 0.0
        c = g.nearest_free(x, y)
        if c is None:
            return dict(out, snap_failed=k)
        cx, cy = g.centre(c)
        out[k] = [cx, cy, th]
        out[k + '_snap_m'] = round(math.hypot(cx - x, cy - y), 4)
    return out


def plan_row(n, client, server, sc, wait_s=120.0):
    row = {'id': sc['id'], 'server': server, 'start': sc['start'], 'goal': sc['goal']}
    for k in ('start_snap_m', 'goal_snap_m'):
        if k in sc:
            row[k] = sc[k]
    if not client.wait_for_server(timeout_sec=20.0):
        return dict(row, status='NO-SERVER')
    g = ComputePathToPose.Goal()
    g.use_start = True
    # R3.4: a server may name Nav2's planner as ACTION@PLANNER_ID (default GridBased, as R2.7)
    g.planner_id = server.partition('@')[2] or 'GridBased'
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
    ap.add_argument('--snap', action='append', default=[], metavar='SERVER',
                    help='plan mode: also ask SERVER with start and goal snapped to free cells')
    ap.add_argument('--costs', metavar='FILE',
                    help='drive mode: the cost under every received plan, one line per plan')
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
    costs = Costs(n, o.costs) if o.costs and o.mode == 'drive' else None
    if o.snap and o.mode == 'plan':
        n.snap_grid = None
        n.create_subscription(Costmap, '/global_costmap/costmap_raw',
                              lambda m: setattr(n, 'snap_grid', Grid(m)), LATCHED)
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
            clients = {s: ActionClient(n, ComputePathToPose, s.partition('@')[0])
                       for s in doc['servers']}
            for sc in doc['scenarios']:
                for s, c in clients.items():
                    row = plan_row(n, c, s, sc, o.plan_wait)
                    row['plan_wait_s'] = o.plan_wait
                    emit(row)
                    if s in o.snap:
                        ss = snapped(n, sc)
                        if ss is None or 'snap_failed' in ss:
                            emit({'id': sc['id'], 'server': s + '+snapped',
                                  'status': 'NO-COSTMAP' if ss is None else 'SNAP-FAILED',
                                  'snap_failed': None if ss is None else ss['snap_failed']})
                            continue
                        row = plan_row(n, c, s, ss, o.plan_wait)
                        row['server'] = s + '+snapped'
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
                if costs is not None:
                    costs.scenario = sc['id']
                row = n.goal({'id': sc['id'], 'pose': sc['goal']}, o.timeout)
                if costs is not None:
                    costs.scenario = None
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
