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
lab_planner: plan with coco_lab, drive with Nav2's FollowPath. Once.

The node sits ABOVE controller_server, as an action client, and nowhere
else (plan §C.1). One run is:

1. wait for ``settle_count`` consecutive ``costmap_raw`` messages with one
   content hash, and snapshot the last (owner decision D-2);
2. read the robot's AMCL belief, ``map -> base_footprint`` from TF;
3. convert both ends to cells exactly as Smac 2D does, and run the
   requested coco_lab algorithm on the C1 graph of the snapshot;
4. publish, latched, the snapshot (``/lab/costmap_snapshot``), the trace
   (``/lab/trace_gz``: gzip of the trace's v1 JSON), the path
   (``/lab/plan``) and a JSON status line (``/lab/status``), and write a
   glass-box bundle of the search to ``out_dir``;
5. send that path, unsmoothed, to ``FollowPath`` -- one goal, no
   replanning -- and report the result.

With ``path_file`` set (Phase 6, Lab 5) steps 1 and 3-4's search are
skipped: the path is READ from a frozen JSON file (:func:`load_path_file`)
and sent unchanged, so every controller drives exactly the same global
path. ``controller_id`` picks the controller (``FollowPath`` = the
mission's DWB; ``MPPI`` and ``RPP`` exist only under the lab's
``nav2_move_overlay.yaml``).

It never publishes velocity, never publishes ``/mission/mode`` (the
arbiter's mode comes from its launch parameter), and publishes nothing but
:data:`coco_lab_ros.safety.LAB_TOPICS` (tested on a constructed node).
"""

import array
import gzip
import hashlib
import json
import os
import threading
import time

from action_msgs.msg import GoalStatus
import coco_lab
from coco_lab.bundle import (Bundle, git_provenance, make_provenance,
                             write_bundle)
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import FollowPath
from nav2_msgs.msg import Costmap
from nav_msgs.msg import Path
import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)
from rclpy.time import Time
from std_msgs.msg import String, UInt8MultiArray
from tf2_ros import Buffer, TransformListener

from . import __version__
from .costmap import Snapshot
from .metrics import path_length
from .pathing import path_poses, quaternion_to_yaw, yaw_to_quaternion
from .planning import PlanError, Planner

LATCHED = QoSProfile(depth=1, history=QoSHistoryPolicy.KEEP_LAST,
                     reliability=QoSReliabilityPolicy.RELIABLE,
                     durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
STATUS_QOS = QoSProfile(depth=50, history=QoSHistoryPolicy.KEEP_LAST,
                        reliability=QoSReliabilityPolicy.RELIABLE,
                        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)


def load_path_file(path):
    """
    Return ``(poses, frame, sha256)`` of a frozen path file.

    The file is JSON ``{"frame": "map", "poses": [[x, y, yaw], ...]}``
    (more keys allowed); at least two poses, every number finite. The
    hash is of the file's bytes, so a run can say which path it drove.
    """
    import math
    with open(path, 'rb') as f:
        raw = f.read()
    data = json.loads(raw.decode('utf-8'))
    poses = data.get('poses')
    if not isinstance(poses, list) or len(poses) < 2:
        raise ValueError(f'{path}: "poses" must list at least two poses')
    out = []
    for q in poses:
        if (not isinstance(q, list) or len(q) != 3
                or not all(isinstance(v, (int, float))
                           and math.isfinite(v) for v in q)):
            raise ValueError(f'{path}: bad pose {q!r}')
        out.append((float(q[0]), float(q[1]), float(q[2])))
    frame = data.get('frame', 'map')
    return out, frame, hashlib.sha256(raw).hexdigest()


def sim_seconds(t) -> float:
    """Return an rclpy Time as float seconds."""
    return t.nanoseconds * 1e-9


class LabPlanner(Node):
    """The lab's planner node (see the module doc)."""

    def __init__(self, **kwargs):
        """Declare parameters, publishers, the costmap and TF inputs."""
        super().__init__('lab_planner', **kwargs)
        d = self.declare_parameter
        d('algorithm', 'astar')
        d('heuristic', 'euclidean')
        d('graph', 'C1')
        d('tie_break', 'low_h')
        d('goal_x', 0.0)
        d('goal_y', 0.0)
        d('goal_yaw', 0.0)
        d('costmap_topic', '/global_costmap/costmap_raw')
        d('global_frame', 'map')
        d('base_frame', 'base_footprint')
        d('settle_count', 2)
        d('costmap_timeout', 120.0)
        d('tf_timeout', 60.0)
        d('follow', True)
        d('controller_id', 'FollowPath')
        d('goal_checker_id', 'goal_checker')
        d('progress_checker_id', '')
        d('follow_timeout', 600.0)
        d('out_dir', '')
        d('run_id', '')
        d('path_file', '')
        d('autostart', True)
        self.p = {n: self.get_parameter(n).value for n in (
            'algorithm', 'heuristic', 'graph', 'tie_break', 'goal_x',
            'goal_y', 'goal_yaw', 'costmap_topic', 'global_frame',
            'base_frame', 'settle_count', 'costmap_timeout', 'tf_timeout',
            'follow', 'controller_id', 'goal_checker_id',
            'progress_checker_id', 'follow_timeout', 'out_dir', 'run_id',
            'path_file', 'autostart')}

        # The ONLY publishers this node creates (coco_lab_ros.safety).
        self._plan_pub = self.create_publisher(Path, '/lab/plan', LATCHED)
        self._status_pub = self.create_publisher(String, '/lab/status',
                                                 STATUS_QOS)
        self._snap_pub = self.create_publisher(
            Costmap, '/lab/costmap_snapshot', LATCHED)
        self._trace_pub = self.create_publisher(
            UInt8MultiArray, '/lab/trace_gz', LATCHED)

        cb = ReentrantCallbackGroup()
        self._lock = threading.Lock()
        self._costmaps = []
        self.create_subscription(Costmap, self.p['costmap_topic'],
                                 self._on_costmap, LATCHED,
                                 callback_group=cb)
        self._tf = Buffer()
        self._tf_listener = TransformListener(self._tf, self)
        self._follow = ActionClient(self, FollowPath, 'follow_path',
                                    callback_group=cb)
        self.done = threading.Event()
        self.outcome = None
        self._thread = None
        if self.p['autostart']:
            self._thread = threading.Thread(target=self._run_safely,
                                            daemon=True)
            self._thread.start()

    # -- inputs -----------------------------------------------------------

    def _on_costmap(self, msg):
        with self._lock:
            self._costmaps.append((msg, Snapshot.from_msg(
                msg, self.p['costmap_topic']).content_hash()))
            del self._costmaps[:-max(1, int(self.p['settle_count']))]

    def status(self, phase, **fields):
        """Publish one JSON status line (and log it)."""
        body = {'phase': phase, 'run_id': self.p['run_id'],
                't_sim': sim_seconds(self.get_clock().now()),
                't_wall': time.time()}
        body.update(fields)
        text = json.dumps(body, sort_keys=True, separators=(',', ':'))
        self._status_pub.publish(String(data=text))
        self.get_logger().info(text[:400])
        return body

    def wait_costmap(self):
        """Return the settled costmap message, or None on timeout."""
        n = max(1, int(self.p['settle_count']))
        deadline = time.monotonic() + float(self.p['costmap_timeout'])
        while time.monotonic() < deadline and self.context.ok():
            with self._lock:
                window = list(self._costmaps)
            if len(window) >= n and len({h for _, h in window[-n:]}) == 1:
                return window[-1][0]
            time.sleep(0.05)
        return None

    def wait_pose(self):
        """Return ``(x, y, yaw, stamp_s)`` of the AMCL belief, or None."""
        deadline = time.monotonic() + float(self.p['tf_timeout'])
        while time.monotonic() < deadline and self.context.ok():
            try:
                t = self._tf.lookup_transform(
                    self.p['global_frame'], self.p['base_frame'],
                    Time())
            except Exception:  # noqa: B902 -- any TF failure: retry
                time.sleep(0.1)
                continue
            q = t.transform.rotation
            st = t.header.stamp
            return (t.transform.translation.x, t.transform.translation.y,
                    quaternion_to_yaw(q.x, q.y, q.z, q.w),
                    st.sec + st.nanosec * 1e-9)
        return None

    # -- the run --------------------------------------------------------------

    def _run_safely(self):
        try:
            self.outcome = self.run()
        except Exception as exc:  # noqa: B902 -- report, never hang
            self.outcome = self.status('error', error=repr(exc))
        finally:
            self.done.set()

    def run(self):
        """Plan once and (if ``follow``) drive once. Return the outcome."""
        p = self.p
        if p['path_file']:
            return self.run_frozen()
        self.status('waiting', costmap_topic=p['costmap_topic'])
        msg = self.wait_costmap()
        if msg is None:
            return self.status('failed', reason='no settled costmap within '
                               f'{p["costmap_timeout"]} s')
        pose = self.wait_pose()
        if pose is None:
            return self.status('failed', reason=f'no {p["global_frame"]} -> '
                               f'{p["base_frame"]} transform')
        snap = Snapshot.from_msg(msg, p['costmap_topic'])
        planner = Planner(snap)
        goal = (float(p['goal_x']), float(p['goal_y']))
        try:
            plan = planner.plan_world(pose[:2], goal, p['algorithm'],
                                      p['heuristic'], p['graph'],
                                      p['tie_break'])
        except PlanError as exc:
            return self.status('failed', reason=str(exc),
                               snapshot_hash=snap.content_hash(),
                               start_world=list(pose[:3]))
        trace_json = plan.result.trace.to_json().encode('utf-8')
        trace_sha = hashlib.sha256(trace_json).hexdigest()
        summary = dict(plan.result.trace.summary)
        base = {
            'algorithm': p['algorithm'], 'heuristic': p['heuristic'],
            'graph': p['graph'], 'tie_break': p['tie_break'],
            'model': plan.model, 'snapshot': snap.describe(),
            'start_world': list(pose[:3]), 'belief_stamp': pose[3],
            'goal_world': [goal[0], goal[1], float(p['goal_yaw'])],
            'start_cell': list(plan.start_nav2),
            'goal_cell': list(plan.goal_nav2),
            'trace_sha256': trace_sha, 'summary': summary,
            'plan_wall_s': plan.plan_seconds,
            'coco_lab_version': coco_lab.__version__,
            'coco_lab_ros_version': __version__,
        }
        self._snap_pub.publish(msg)
        self._trace_pub.publish(UInt8MultiArray(data=array.array(
            'B', gzip.compress(trace_json, compresslevel=6, mtime=0))))
        if not plan.found:
            self._write('plan.json', base)
            return self.status('failed', reason='no path', **base)

        poses = path_poses(plan.cells_nav2(), snap, float(p['goal_yaw']))
        path = self._path_msg(poses, snap.frame_id)
        self._plan_pub.publish(path)
        base['path_cells'] = len(poses)
        base['path_L_m'] = path_length([q[:2] for q in poses])
        base['poses'] = [list(q) for q in poses]
        self._write('plan.json', base)
        self._write_bundle(plan)
        planned = {k: v for k, v in base.items() if k != 'poses'}
        self.status('planned', **planned)
        if not p['follow']:
            return self.status('done', followed=False)
        return self.follow(path)

    def run_frozen(self):
        """Drive a frozen path file once (no search). Return the outcome."""
        p = self.p
        try:
            poses, frame, sha = load_path_file(p['path_file'])
        except (OSError, ValueError) as exc:
            return self.status('failed', reason=f'path_file: {exc}')
        pose = self.wait_pose()
        if pose is None:
            return self.status('failed', reason=f'no {p["global_frame"]} -> '
                               f'{p["base_frame"]} transform')
        path = self._path_msg(poses, frame)
        self._plan_pub.publish(path)
        base = {
            'path_file': os.path.basename(p['path_file']),
            'path_sha256': sha, 'frame': frame, 'path_cells': len(poses),
            'path_L_m': path_length([q[:2] for q in poses]),
            'start_world': list(pose[:3]), 'belief_stamp': pose[3],
            'goal_world': list(poses[-1]),
            'controller_id': p['controller_id'],
            'coco_lab_version': coco_lab.__version__,
            'coco_lab_ros_version': __version__,
        }
        self._write('plan.json', dict(base, poses=[list(q) for q in poses]))
        self.status('planned', **base)
        if not p['follow']:
            return self.status('done', followed=False)
        return self.follow(path)

    def _path_msg(self, poses, frame):
        path = Path()
        path.header.frame_id = frame
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y, yaw in poses:
            ps = PoseStamped()
            ps.header = path.header
            ps.pose.position.x, ps.pose.position.y = x, y
            q = yaw_to_quaternion(yaw)
            (ps.pose.orientation.x, ps.pose.orientation.y,
             ps.pose.orientation.z, ps.pose.orientation.w) = q
            path.poses.append(ps)
        return path

    def follow(self, path):
        """Send ONE FollowPath goal and wait for its result."""
        p = self.p
        if not self._follow.wait_for_server(timeout_sec=30.0):
            return self.status('failed', reason='follow_path action server '
                               'unavailable')
        goal = FollowPath.Goal()
        goal.path = path
        goal.controller_id = p['controller_id']
        goal.goal_checker_id = p['goal_checker_id']
        goal.progress_checker_id = p['progress_checker_id']
        sent = self._wait(self._follow.send_goal_async(goal), 30.0)
        handle = sent.result() if sent else None
        if handle is None or not handle.accepted:
            return self.status('failed', reason='FollowPath goal rejected')
        accepted = self.status('following', controller_id=p['controller_id'],
                               goal_checker_id=p['goal_checker_id'],
                               poses=len(path.poses))
        fut = self._wait(handle.get_result_async(),
                         float(p['follow_timeout']))
        if fut is None:
            handle.cancel_goal_async()
            return self.status('failed', reason='FollowPath timed out',
                               t_accept_sim=accepted['t_sim'])
        res = fut.result()
        out = {'t_accept_sim': accepted['t_sim'],
               't_accept_wall': accepted['t_wall'],
               'action_status': int(res.status),
               'error_code': int(res.result.error_code),
               'error_msg': str(res.result.error_msg)}
        phase = ('succeeded' if res.status == GoalStatus.STATUS_SUCCEEDED
                 else 'follow_failed')
        final = self.status(phase, **out)
        self._write('result.json', final)
        return final

    def _wait(self, future, timeout):
        ev = threading.Event()
        future.add_done_callback(lambda _: ev.set())
        return future if ev.wait(timeout) else None

    # -- files ------------------------------------------------------------------

    def _out(self, name):
        d = self.p['out_dir']
        if not d:
            return None
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, name)

    def _write(self, name, obj):
        path = self._out(name)
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(obj, f, sort_keys=True, indent=1)

    def _write_bundle(self, plan):
        path = self._out('plan_bundle')
        if not path:
            return
        prov = make_provenance(
            'glass-box', git=git_provenance(os.path.dirname(
                os.path.realpath(__file__))), tool='coco_lab_ros.lab_planner')
        run = {'start': list(plan.start_lab), 'goal': list(plan.goal_lab),
               'model': plan.model}
        write_bundle(Bundle.from_run(plan.result, plan.lab_map, run, prov),
                     path, compression='gzip')


def main(args=None):
    """Run the node until shutdown (it stays up after its one run)."""
    rclpy.init(args=args)
    node = LabPlanner()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
