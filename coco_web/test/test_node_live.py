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

"""The REAL node's Phase 2 inputs: ground truth, local plan, goal status."""

import time

from action_msgs.msg import GoalStatus, GoalStatusArray
from coco_config.robot import SPAWN_XY
from coco_web import platform_server as ps
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path
import pytest
import rclpy
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)


@pytest.fixture
def context():
    """Provide a ROS context for one test, torn down whatever happens."""
    rclpy.init()
    yield
    rclpy.shutdown()


def _latched():
    """Return bt_navigator's status-topic QoS (TRANSIENT_LOCAL, measured)."""
    return QoSProfile(
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        history=QoSHistoryPolicy.KEEP_LAST, depth=1)


def _spin_until(node, other, publish, predicate, seconds=5.0):
    """
    Publish at 10 Hz and spin until `predicate(snapshot)`; return the snap.

    Not once per spin: spin_once serves ONE callback, and publishing every
    iteration keeps the raw liveness subscription on the same topic (made
    first) always ready, so the truth callback would starve -- a test
    artefact a real spin() does not have.
    """
    deadline = time.monotonic() + seconds
    last = 0.0
    snap = None
    while time.monotonic() < deadline:
        if time.monotonic() - last >= 0.1:
            publish()
            last = time.monotonic()
        rclpy.spin_once(node, timeout_sec=0.02)
        rclpy.spin_once(other, timeout_sec=0.0)
        snap, _fresh = node.snapshot()
        if predicate(snap):
            break
    return snap


def test_ground_truth_arrives_in_the_map_frame(context):
    """World spawn + (1.5, 0.25) is map (1.5, 0.25): spawn is the origin."""
    sim = rclpy.create_node('fake_gz_bridge_for_platform_test')
    pub = sim.create_publisher(Odometry, '/model/coco/odometry', 10)
    node = ps.CocoWebNode()
    try:
        msg = Odometry()
        msg.pose.pose.position.x = SPAWN_XY[0] + 1.5
        msg.pose.pose.position.y = SPAWN_XY[1] + 0.25
        msg.pose.pose.orientation.w = 1.0

        snap = _spin_until(node, sim, lambda: pub.publish(msg),
                           lambda snap: snap.get('truth') is not None)
        assert snap['truth']['x'] == pytest.approx(1.5)
        assert snap['truth']['y'] == pytest.approx(0.25)
    finally:
        node.destroy_node()
        sim.destroy_node()


def test_the_local_plan_and_the_goal_status_arrive(context):
    """/local_plan becomes local_path; the action status names the goal."""
    nav = rclpy.create_node('fake_nav2_for_platform_test')
    local = nav.create_publisher(Path, '/local_plan', 10)
    status = nav.create_publisher(
        GoalStatusArray, '/navigate_to_pose/_action/status', _latched())
    node = ps.CocoWebNode()
    try:
        node.publish_goal(2.0, 0.0)
        path = Path()
        for x in (0.0, 0.1, 0.2):
            pose = PoseStamped()
            pose.pose.position.x = x
            path.poses.append(pose)
        entry = GoalStatus()
        entry.status = GoalStatus.STATUS_EXECUTING
        entry.goal_info.stamp = node.get_clock().now().to_msg()
        array = GoalStatusArray(status_list=[entry])

        def publish():
            local.publish(path)
            status.publish(array)
        snap = _spin_until(
            node, nav, publish,
            lambda snap: bool(snap.get('local_path'))
            and snap['goal']['status'] == 'executing')
        assert snap['local_path'] == [[0.0, 0.0], [0.1, 0.0], [0.2, 0.0]]
        assert snap['goal']['status'] == 'executing'
        assert (snap['goal']['x'], snap['goal']['y']) == (2.0, 0.0)
    finally:
        node.destroy_node()
        nav.destroy_node()


def test_a_goal_nav2_has_not_accepted_reads_sent(context):
    """No status entry after the goal: 'sent', never a borrowed status."""
    node = ps.CocoWebNode()
    try:
        node.publish_goal(1.0, 1.0)
        snap, _fresh = node.snapshot()
        assert snap['goal']['status'] == 'sent'
    finally:
        node.destroy_node()


def test_the_real_node_reports_its_config_came_from_coco_config(context):
    """With coco_config importable, nothing fell back."""
    node = ps.CocoWebNode()
    try:
        assert node.config_doc() == {'source': 'coco_config',
                                     'fallbacks': []}
    finally:
        node.destroy_node()
