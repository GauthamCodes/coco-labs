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
M6F.8: drive Nav2's NavigateToPose through a list of goals and record each result.

    m6f8_nav.py GOALS.json OUT.jsonl [--timeout 420] [--initial-pose] [--reset-each]

GOALS.json is ``tools/m6/m6f8_goals.py``'s (map frame; on the Depot map = world). Per goal,
one JSON line: the action's status (SUCCEEDED / ABORTED / CANCELED / REJECTED / TIMEOUT),
Nav2's ``error_code`` and ``error_msg`` from the result, the simulation time taken, the
distance driven and the final pose from Gazebo's ground truth (``/model/coco/odometry``)
and from AMCL (``/amcl_pose``), and their distances to the goal. Evidence class STACK (the
full ROS 2 stack in Gazebo). It publishes nothing to the wheels: Nav2 drives through the
arbiter; ``--initial-pose`` publishes the goal file's ``start`` once on ``/initialpose``.
``--reset-each`` makes every goal an independent leg from the start: before each goal, COCO
is teleported there in Gazebo (``/world/<world>/set_pose``, the simulator's own service)
and AMCL is re-seeded with the same pose, so one failed leg cannot fail the next.
"""
import argparse
import json
import math
import subprocess
import time

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

STATUS = {GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED', GoalStatus.STATUS_ABORTED: 'ABORTED',
          GoalStatus.STATUS_CANCELED: 'CANCELED'}


def quat(yaw):
    return 0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2)


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class Runner(Node):
    """NavigateToPose client; watches ground truth and AMCL."""

    def __init__(self):
        super().__init__('m6f8_nav', parameter_overrides=[
            Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.truth = self.amcl = None
        self.create_subscription(Odometry, '/model/coco/odometry', self._truth, 20)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self._amcl, 10)
        self.init_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 1)

    def _truth(self, m):
        p = m.pose.pose
        self.truth = (p.position.x, p.position.y, yaw_of(p.orientation))

    def _amcl(self, m):
        p = m.pose.pose
        self.amcl = (p.position.x, p.position.y, yaw_of(p.orientation))

    def now_s(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def spin_for(self, wall_s):
        end = time.time() + wall_s
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def initial_pose(self, x, y, yaw):
        m = PoseWithCovarianceStamped()
        m.header.frame_id = 'map'
        m.header.stamp = self.get_clock().now().to_msg()
        m.pose.pose.position.x, m.pose.pose.position.y = float(x), float(y)
        q = quat(yaw)
        (m.pose.pose.orientation.x, m.pose.pose.orientation.y,
         m.pose.pose.orientation.z, m.pose.pose.orientation.w) = q
        m.pose.covariance[0] = m.pose.covariance[7] = 0.05 ** 2
        m.pose.covariance[35] = 0.05 ** 2
        self.init_pub.publish(m)

    def teleport(self, world, x, y, yaw):
        q = quat(yaw)
        req = (f"name: 'coco', position: {{x: {x}, y: {y}, z: 0.05}}, "
               f"orientation: {{x: 0, y: 0, z: {q[2]}, w: {q[3]}}}")
        r = subprocess.run(['gz', 'service', '-s', f'/world/{world}/set_pose', '--reqtype',
                            'gz.msgs.Pose', '--reptype', 'gz.msgs.Boolean', '--timeout', '5000',
                            '--req', req], capture_output=True, text=True, timeout=30)
        return 'data: true' in r.stdout

    def goal(self, g, timeout_s):
        x, y, yaw = g['pose']
        row = {'id': g['id'], 'label': g.get('label'), 'goal': g['pose']}
        if not self.client.wait_for_server(timeout_sec=30.0):
            return dict(row, status='NO-SERVER')
        msg = NavigateToPose.Goal()
        msg.pose.header.frame_id = 'map'
        msg.pose.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x, msg.pose.pose.position.y = float(x), float(y)
        q = quat(yaw)
        (msg.pose.pose.orientation.x, msg.pose.pose.orientation.y,
         msg.pose.pose.orientation.z, msg.pose.pose.orientation.w) = q
        row['start_truth'] = self.truth
        row['t_start_sim'] = self.now_s()
        row['t_start_wall'] = time.time()
        fut = self.client.send_goal_async(msg)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=30.0)
        h = fut.result()
        if h is None or not h.accepted:
            return dict(row, status='REJECTED')
        res = h.get_result_async()
        driven, last = 0.0, self.truth
        while not res.done():
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.truth and last:
                driven += math.hypot(self.truth[0] - last[0], self.truth[1] - last[1])
            last = self.truth
            if self.now_s() - row['t_start_sim'] > timeout_s:
                c = h.cancel_goal_async()
                rclpy.spin_until_future_complete(self, c, timeout_sec=10.0)
                rclpy.spin_until_future_complete(self, res, timeout_sec=20.0)
                row['status'] = 'TIMEOUT'
                break
        r = res.result()
        if 'status' not in row:
            row['status'] = STATUS.get(r.status, f'STATUS_{r.status}') if r else 'NO-RESULT'
        if r is not None:
            row['error_code'] = int(getattr(r.result, 'error_code', -1))
            row['error_msg'] = str(getattr(r.result, 'error_msg', ''))
        self.spin_for(1.0)
        row['sim_s'] = round(self.now_s() - row['t_start_sim'], 2)
        row['wall_s'] = round(time.time() - row['t_start_wall'], 2)
        row['driven_m'] = round(driven, 3)
        row['end_truth'] = self.truth
        row['end_amcl'] = self.amcl
        if self.truth:
            row['truth_to_goal_m'] = round(math.hypot(self.truth[0] - x, self.truth[1] - y), 3)
        if self.amcl and self.truth:
            row['amcl_error_m'] = round(math.hypot(self.amcl[0] - self.truth[0],
                                                   self.amcl[1] - self.truth[1]), 3)
        return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('goals')
    ap.add_argument('out')
    ap.add_argument('--timeout', type=float, default=420.0, help='per goal, simulated seconds')
    ap.add_argument('--initial-pose', action='store_true')
    ap.add_argument('--reset-each', action='store_true')
    ap.add_argument('--world', default='coco_depot_v1')
    o = ap.parse_args()
    doc = json.load(open(o.goals))
    rclpy.init()
    n = Runner()
    n.spin_for(3.0)
    if o.initial_pose:
        for _ in range(3):
            n.initial_pose(*doc['start'])
            n.spin_for(1.0)
        n.spin_for(5.0)
    with open(o.out, 'a') as f:
        for g in doc['goals']:
            reset = None
            if o.reset_each:
                reset = n.teleport(o.world, *doc['start'])
                n.spin_for(2.0)
                for _ in range(3):
                    n.initial_pose(*doc['start'])
                    n.spin_for(1.0)
                n.spin_for(4.0)
            row = n.goal(g, o.timeout)
            if reset is not None:
                row['reset_to_start'] = reset
            f.write(json.dumps(row) + '\n')
            f.flush()
            print(json.dumps({k: row.get(k) for k in ('id', 'status', 'error_code', 'sim_s',
                                                      'driven_m', 'truth_to_goal_m')}),
                  flush=True)
    n.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
