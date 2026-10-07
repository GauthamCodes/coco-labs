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
lab_planner against a FAKE FollowPath server, on a private ROS domain.

The golden costmap is published on ``/global_costmap/costmap_raw``, a
static ``map -> base_footprint`` puts the robot on the golden start cell,
and a fake ``follow_path`` action server records what it is sent and
succeeds. Checked: exactly one goal, carrying the expected poses (cell
centres, travel-direction yaw, goal yaw last), ``controller_id`` and
``goal_checker_id``; the status sequence; the latched trace equals the
status's hash; the glass-box bundle on disk loads and REPLAYS exactly.
And a blocked goal fails without sending any goal.
"""

import array
import gzip
import hashlib
import json
import math
import os
import threading
import time

from coco_lab import bundle
from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.pathing import path_poses
from coco_lab_ros.planning import Planner
import golden_costmap
import pytest

DOMAIN = 87


def golden_snapshot():
    d = json.loads(golden_costmap.text())
    return Snapshot(width=d['width'], height=d['height'],
                    resolution=d['resolution'], origin=tuple(d['origin']),
                    frame_id=d['frame_id'], data=bytes(d['data']))


def costmap_msg(snap):
    from nav2_msgs.msg import Costmap
    m = Costmap()
    m.header.frame_id = snap.frame_id
    m.metadata.layer = 'master'
    m.metadata.resolution = snap.resolution
    m.metadata.size_x, m.metadata.size_y = snap.width, snap.height
    m.metadata.origin.position.x, m.metadata.origin.position.y = snap.origin
    m.metadata.origin.orientation.w = 1.0
    m.data = array.array('B', snap.data)
    return m


def run_planner(tmp_path, goal_cell, start_cell=(2, 2)):
    """Run one lab_planner against the fakes; return what happened."""
    import rclpy
    from geometry_msgs.msg import TransformStamped
    from nav2_msgs.action import FollowPath
    from nav2_msgs.msg import Costmap
    from rclpy.action import ActionServer
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.parameter import Parameter
    from rclpy.qos import (QoSDurabilityPolicy, QoSProfile,
                           QoSReliabilityPolicy)
    from std_msgs.msg import String, UInt8MultiArray
    from tf2_ros import StaticTransformBroadcaster
    from coco_lab_ros.planner_node import LabPlanner

    snap = golden_snapshot()
    sx, sy = snap.cell_centre(*start_cell)
    gx, gy = snap.cell_centre(*goal_cell)
    ctx = rclpy.Context()
    rclpy.init(context=ctx, domain_id=DOMAIN)
    fake = rclpy.create_node('fake_nav2', context=ctx)
    latched = QoSProfile(depth=1,
                         reliability=QoSReliabilityPolicy.RELIABLE,
                         durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
    cm_pub = fake.create_publisher(Costmap, '/global_costmap/costmap_raw',
                                   latched)
    goals, statuses, traces = [], [], []

    def execute(handle):
        goals.append(handle.request)
        handle.succeed()
        return FollowPath.Result()
    ActionServer(fake, FollowPath, 'follow_path', execute)
    fake.create_subscription(
        String, '/lab/status', lambda m: statuses.append(json.loads(m.data)),
        QoSProfile(depth=50, reliability=QoSReliabilityPolicy.RELIABLE,
                   durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
    fake.create_subscription(UInt8MultiArray, '/lab/trace_gz',
                             lambda m: traces.append(bytes(m.data)), latched)
    t = TransformStamped()
    t.header.frame_id, t.child_frame_id = 'map', 'base_footprint'
    t.transform.translation.x, t.transform.translation.y = sx, sy
    t.transform.rotation.w = 1.0
    StaticTransformBroadcaster(fake).sendTransform(t)

    node = LabPlanner(context=ctx, parameter_overrides=[
        Parameter('algorithm', Parameter.Type.STRING, 'astar'),
        Parameter('heuristic', Parameter.Type.STRING, 'euclidean'),
        Parameter('goal_x', Parameter.Type.DOUBLE, gx),
        Parameter('goal_y', Parameter.Type.DOUBLE, gy),
        Parameter('goal_yaw', Parameter.Type.DOUBLE, 0.5),
        Parameter('out_dir', Parameter.Type.STRING, str(tmp_path)),
        Parameter('run_id', Parameter.Type.STRING, 'test-run'),
        Parameter('costmap_timeout', Parameter.Type.DOUBLE, 30.0),
        Parameter('tf_timeout', Parameter.Type.DOUBLE, 30.0)])
    ex = MultiThreadedExecutor(num_threads=4, context=ctx)
    ex.add_node(fake)
    ex.add_node(node)
    spin = threading.Thread(target=ex.spin, daemon=True)
    spin.start()
    try:
        for _ in range(3):              # settle_count 2 needs repeats
            cm_pub.publish(costmap_msg(snap))
            time.sleep(0.2)
        assert node.done.wait(60), 'lab_planner never finished'
        time.sleep(0.5)
        return snap, node.outcome, goals, statuses, traces
    finally:
        ex.shutdown()
        node.destroy_node()
        fake.destroy_node()
        rclpy.shutdown(context=ctx)


def test_one_plan_one_followpath_goal(tmp_path):
    snap, outcome, goals, statuses, traces = run_planner(tmp_path, (36, 26))
    assert outcome['phase'] == 'succeeded', outcome
    assert [s['phase'] for s in statuses] == ['waiting', 'planned',
                                              'following', 'succeeded']
    assert len(goals) == 1, 'exactly one FollowPath goal, no replanning'
    g = goals[0]
    assert g.controller_id == 'FollowPath'
    assert g.goal_checker_id == 'goal_checker'

    expected = Planner(snap).plan_cells((2, 2), (36, 26), 'astar',
                                        'euclidean', 'C1')
    want = path_poses(expected.cells_nav2(), snap, 0.5)
    got = g.path.poses
    assert len(got) == len(want) == len(expected.result.path)
    for p, (x, y, yaw) in zip(got, want):
        assert p.pose.position.x == pytest.approx(x, abs=1e-9)
        assert p.pose.position.y == pytest.approx(y, abs=1e-9)
        q = p.pose.orientation
        assert 2 * math.atan2(q.z, q.w) == pytest.approx(yaw, abs=1e-9)
    assert g.path.header.frame_id == 'map'

    planned = statuses[1]
    assert planned['snapshot']['content_hash'] == snap.content_hash()
    assert planned['start_cell'] == [2, 2] and planned['goal_cell'] == \
        [36, 26]
    trace_json = gzip.decompress(traces[-1])
    assert hashlib.sha256(trace_json).hexdigest() == planned['trace_sha256']

    b = bundle.load_bundle(str(tmp_path / 'plan_bundle'))
    assert b.provenance['source_kind'] == 'glass-box'
    assert b.run['model']['corner_cutting'] is True
    r = bundle.replay(b)
    assert r.reproduced, r.detail
    assert b.trace.to_json().encode() == trace_json
    with open(tmp_path / 'result.json') as f:
        assert json.load(f)['phase'] == 'succeeded'


def test_a_blocked_goal_fails_and_sends_nothing(tmp_path):
    snap = golden_snapshot()
    blocked = next((mx, my) for my in range(snap.height)
                   for mx in range(snap.width) if snap.cost(mx, my) == 254)
    _, outcome, goals, statuses, _ = run_planner(tmp_path, blocked)
    assert outcome['phase'] == 'failed' and 'blocked' in outcome['reason']
    assert goals == []
    assert not os.path.exists(tmp_path / 'plan_bundle')


def run_frozen(tmp_path, path_file, controller_id):
    """Run lab_planner with ``path_file`` against a fake FollowPath."""
    import rclpy
    from geometry_msgs.msg import TransformStamped
    from nav2_msgs.action import FollowPath
    from rclpy.action import ActionServer
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.parameter import Parameter
    from tf2_ros import StaticTransformBroadcaster
    from coco_lab_ros.planner_node import LabPlanner

    ctx = rclpy.Context()
    rclpy.init(context=ctx, domain_id=DOMAIN)
    fake = rclpy.create_node('fake_nav2', context=ctx)
    goals = []

    def execute(handle):
        goals.append(handle.request)
        handle.succeed()
        return FollowPath.Result()
    ActionServer(fake, FollowPath, 'follow_path', execute)
    t = TransformStamped()
    t.header.frame_id, t.child_frame_id = 'map', 'base_footprint'
    t.transform.rotation.w = 1.0
    StaticTransformBroadcaster(fake).sendTransform(t)
    node = LabPlanner(context=ctx, parameter_overrides=[
        Parameter('path_file', Parameter.Type.STRING, str(path_file)),
        Parameter('controller_id', Parameter.Type.STRING, controller_id),
        Parameter('out_dir', Parameter.Type.STRING, str(tmp_path / 'out')),
        Parameter('tf_timeout', Parameter.Type.DOUBLE, 30.0)])
    ex = MultiThreadedExecutor(num_threads=4, context=ctx)
    ex.add_node(fake)
    ex.add_node(node)
    spin = threading.Thread(target=ex.spin, daemon=True)
    spin.start()
    try:
        assert node.done.wait(60), 'lab_planner never finished'
        return node.outcome, goals
    finally:
        ex.shutdown()
        node.destroy_node()
        fake.destroy_node()
        rclpy.shutdown(context=ctx)


def test_a_frozen_path_is_sent_unchanged_to_the_named_controller(tmp_path):
    poses = [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.5, 0.5, 1.5707963]]
    f = tmp_path / 'path.json'
    f.write_text(json.dumps({'frame': 'map', 'poses': poses}))
    outcome, goals = run_frozen(tmp_path, f, 'MPPI')
    assert outcome['phase'] == 'succeeded', outcome
    assert len(goals) == 1 and goals[0].controller_id == 'MPPI'
    got = goals[0].path.poses
    assert len(got) == 3
    for p, (x, y, yaw) in zip(got, poses):
        assert p.pose.position.x == x and p.pose.position.y == y
        q = p.pose.orientation
        assert 2 * math.atan2(q.z, q.w) == pytest.approx(yaw, abs=1e-9)
    plan = json.loads((tmp_path / 'out' / 'plan.json').read_text())
    assert plan['path_sha256'] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert plan['controller_id'] == 'MPPI' and plan['poses'] == poses
    assert not os.path.exists(tmp_path / 'out' / 'plan_bundle')


@pytest.mark.parametrize('body', [
    '{"poses": [[0, 0, 0]]}', '{"poses": [[0, 0], [1, 1]]}',
    '{"poses": [[0, 0, 0], [1, NaN, 0]]}', '{}'])
def test_a_bad_path_file_is_refused(tmp_path, body):
    from coco_lab_ros.planner_node import load_path_file
    f = tmp_path / 'bad.json'
    f.write_text(body)
    with pytest.raises(ValueError):
        load_path_file(str(f))
