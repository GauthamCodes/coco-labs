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
The REAL node sees AMCL's startup pose, and asks for a no-motion update.

Phase 2 Part A measured `localised: false` for the whole 400 s a stationary
robot sat at spawn. AMCL publishes /amcl_pose TRANSIENT_LOCAL: one pose at
startup (set_initial_pose), and then only on filter updates, which need
motion. Every other subscriber on the graph matched that durability. The
platform alone subscribed VOLATILE, so it missed the one message that
existed (measured with `ros2 topic info -v /amcl_pose`).
"""

import time

from coco_web import platform_server as ps
from geometry_msgs.msg import PoseWithCovarianceStamped
import pytest
import rclpy
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)
from std_srvs.srv import Empty


@pytest.fixture
def context():
    """Provide a ROS context for one test, torn down whatever happens."""
    rclpy.init()
    yield
    rclpy.shutdown()


def _amcl_qos():
    """Return the QoS of AMCL's own /amcl_pose publisher (Jazzy, measured)."""
    return QoSProfile(
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        history=QoSHistoryPolicy.KEEP_LAST, depth=1)


def test_a_pose_published_before_the_platform_started_still_arrives(context):
    """The startup pose is latched; a late joiner must receive it."""
    amcl = rclpy.create_node('fake_amcl_for_platform_test')
    pub = amcl.create_publisher(PoseWithCovarianceStamped, '/amcl_pose',
                                _amcl_qos())
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.pose.pose.position.x = 1.25
    msg.pose.pose.orientation.w = 1.0
    pub.publish(msg)                      # BEFORE the platform exists
    node = ps.CocoWebNode()
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            rclpy.spin_once(amcl, timeout_sec=0.0)
            snap, _fresh = node.snapshot()
            if snap.get('frame') == 'map':
                break
        assert snap.get('frame') == 'map'
        assert snap['pose']['x'] == pytest.approx(1.25)
    finally:
        node.destroy_node()
        amcl.destroy_node()


def test_it_asks_amcl_for_one_no_motion_update(context):
    """Once AMCL's service exists, exactly one request, then none."""
    amcl = rclpy.create_node('fake_amcl_service_for_platform_test')
    calls = []

    def serve(_request, response):
        calls.append(time.monotonic())
        return response

    amcl.create_service(Empty, '/request_nomotion_update', serve)
    node = ps.CocoWebNode()
    try:
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            rclpy.spin_once(amcl, timeout_sec=0.0)
        assert len(calls) == 1
    finally:
        node.destroy_node()
        amcl.destroy_node()
