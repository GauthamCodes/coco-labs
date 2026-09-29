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
Asking Nav2's planners for paths, and watching what they see.

Shared by the static smoke test and the Phase 1C conformance runner. A
:class:`Nav2Probe` is a plain rclpy node that PUBLISHES NOTHING: it
subscribes ``costmap_raw`` and Smac 2D's ``unsmoothed_plan``, and calls
``compute_path_to_pose``, which returns a path and moves nothing.

**unsmoothed_plan** (owner decision D-3). Smac 2D publishes its raw A*
path on ``unsmoothed_plan`` -- ``create_publisher`` on planner_server's
node, so ``/unsmoothed_plan`` at the root namespace -- and ONLY while that
topic has a subscriber (``smac_planner_2d.cpp`` @1.3.11 :146, :307-310).
So the probe subscribes before any request, and the raw path of a request
is the message that arrives between sending it and its result. Nav2
1.3.11 has no parameter that disables Smac 2D's smoother: this is the
planner's own pre-smoothing output, not a smoothing-disabled run.
"""

import threading
import time

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose
from nav2_msgs.msg import Costmap
from nav_msgs.msg import Path
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)

from .costmap import Snapshot
from .pathing import yaw_to_quaternion

LATCHED = QoSProfile(depth=1, history=QoSHistoryPolicy.KEEP_LAST,
                     reliability=QoSReliabilityPolicy.RELIABLE,
                     durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
RAW_PLAN_TOPIC = '/unsmoothed_plan'


class Nav2Probe(Node):
    """Watch costmap_raw and unsmoothed_plan; call ComputePathToPose."""

    def __init__(self, costmap_topic='/global_costmap/costmap_raw',
                 raw_plan_topic=RAW_PLAN_TOPIC, name='lab_nav2_probe',
                 **kwargs):
        """Subscribe both topics and create the action client."""
        super().__init__(name, **kwargs)
        cb = ReentrantCallbackGroup()
        self.costmap_topic = costmap_topic
        self._lock = threading.Lock()
        self._costmap = None          # (msg, hash, receive monotonic)
        self._costmap_count = 0
        self._raw = []                # [(receive monotonic, Path)]
        self.create_subscription(Costmap, costmap_topic, self._on_costmap,
                                 LATCHED, callback_group=cb)
        self.create_subscription(Path, raw_plan_topic, self._on_raw,
                                 QoSProfile(depth=10), callback_group=cb)
        self._client = ActionClient(self, ComputePathToPose,
                                    'compute_path_to_pose',
                                    callback_group=cb)

    # -- costmap -------------------------------------------------------------

    def _on_costmap(self, msg):
        h = Snapshot.from_msg(msg, self.costmap_topic).content_hash()
        with self._lock:
            self._costmap = (msg, h, time.monotonic())
            self._costmap_count += 1

    def latest_costmap(self):
        """Return ``(msg, hash, count)`` of the newest costmap, or Nones."""
        with self._lock:
            if self._costmap is None:
                return None, None, self._costmap_count
            return self._costmap[0], self._costmap[1], self._costmap_count

    def wait_costmap(self, timeout=60.0, after_count=0):
        """Wait for a costmap newer than ``after_count``; return it."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg, h, n = self.latest_costmap()
            if msg is not None and n > after_count:
                return msg, h, n
            time.sleep(0.02)
        return None, None, self.latest_costmap()[2]

    def wait_settled(self, repeats=2, timeout=120.0):
        """Wait until ``repeats`` consecutive costmaps share one hash."""
        deadline = time.monotonic() + timeout
        seen, n = [], 0
        while time.monotonic() < deadline:
            msg, h, n = self.wait_costmap(max(0.1, deadline -
                                              time.monotonic()), n)
            if msg is None:
                break
            seen.append(h)
            if len(seen) >= repeats and len(set(seen[-repeats:])) == 1:
                return msg, h
        return None, None

    # -- unsmoothed_plan -----------------------------------------------------

    def _on_raw(self, msg):
        with self._lock:
            self._raw.append((time.monotonic(), msg))

    def raw_plans_since(self, t0):
        """Return the raw plans received at or after monotonic ``t0``."""
        with self._lock:
            return [m for t, m in self._raw if t >= t0]

    def raw_subscribed(self):
        """Return how many publishers the raw-plan subscription matches."""
        return self.count_publishers(RAW_PLAN_TOPIC)

    # -- planning -------------------------------------------------------------

    def wait_for_planner(self, timeout=60.0):
        """Wait for the compute_path_to_pose action server."""
        return self._client.wait_for_server(timeout_sec=timeout)

    def compute(self, planner_id, start, goal, frame='map', timeout=30.0,
                raw_wait=2.0):
        """
        Request one path; return a result dict.

        ``start`` and ``goal`` are ``(x, y, yaw)`` in ``frame``. The dict
        holds ``ok``, ``error_code``, ``error_msg``, ``poses`` ([(x, y,
        yaw)]), ``planning_time`` (s, as the server reports it),
        ``wall`` (s, round trip) and ``raw`` (the unsmoothed_plan poses
        received during the call, or None).
        """
        from .pathing import quaternion_to_yaw
        goal_msg = ComputePathToPose.Goal()
        goal_msg.planner_id = planner_id
        goal_msg.use_start = True
        goal_msg.start = self._pose(start, frame)
        goal_msg.goal = self._pose(goal, frame)
        t0 = time.monotonic()
        ev = threading.Event()
        box = {}

        def done_send(fut):
            handle = fut.result()
            box['handle'] = handle
            if handle is None or not handle.accepted:
                ev.set()
                return
            res = handle.get_result_async()
            res.add_done_callback(lambda f: (box.update(result=f.result()),
                                             ev.set()))
        self._client.send_goal_async(goal_msg).add_done_callback(done_send)
        out = {'planner_id': planner_id, 'ok': False, 'error_code': None,
               'error_msg': '', 'poses': [], 'planning_time': None,
               'wall': None, 'raw': None}
        if not ev.wait(timeout):
            out['error_msg'] = 'timeout'
            return out
        out['wall'] = time.monotonic() - t0
        wrapped = box.get('result')
        if wrapped is None:
            out['error_msg'] = 'rejected'
            return out
        r = wrapped.result
        out['error_code'] = int(r.error_code)
        out['error_msg'] = str(r.error_msg)
        out['planning_time'] = (r.planning_time.sec
                                + r.planning_time.nanosec * 1e-9)
        out['poses'] = [(p.pose.position.x, p.pose.position.y,
                         quaternion_to_yaw(p.pose.orientation.x,
                                           p.pose.orientation.y,
                                           p.pose.orientation.z,
                                           p.pose.orientation.w))
                        for p in r.path.poses]
        out['ok'] = r.error_code == 0 and bool(out['poses'])
        deadline = time.monotonic() + raw_wait
        raws = self.raw_plans_since(t0)
        while not raws and time.monotonic() < deadline:
            time.sleep(0.02)
            raws = self.raw_plans_since(t0)
        if raws:
            out['raw'] = [(p.pose.position.x, p.pose.position.y)
                          for p in raws[-1].poses]
            out['raw_messages'] = len(raws)
        return out

    def _pose(self, xyyaw, frame):
        ps = PoseStamped()
        ps.header.frame_id = frame
        ps.pose.position.x, ps.pose.position.y = xyyaw[0], xyyaw[1]
        q = yaw_to_quaternion(xyyaw[2] if len(xyyaw) > 2 else 0.0)
        (ps.pose.orientation.x, ps.pose.orientation.y,
         ps.pose.orientation.z, ps.pose.orientation.w) = q
        return ps
