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
G2.5: the browser's "Save as rosbag2 (MCAP)" file, opened by real ROS 2 Jazzy.

``lab_web/test/fixtures/g2_model_bag.mcap`` is what the browser writes for a recorded
session (lab_web/test/g2_bag.test.ts keeps it byte-identical to src/ros/bag.ts's output).
Here rosbag2_py opens it with the mcap storage plugin, every message deserialises into the
real Jazzy class, the frames and stamps are the model's, the latched topics are offered
transient local (so ``ros2 bag play`` re-offers them to a late RViz), and the QoS and types
are what ``ros2 bag info`` reports.
"""

import os

from rclpy.serialization import deserialize_message
import rosbag2_py
from rosidl_runtime_py.utilities import get_message

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BAG = os.path.join(REPO, 'lab_web', 'test', 'fixtures', 'g2_model_bag.mcap')


def _read():
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=BAG, storage_id='mcap'),
           rosbag2_py.ConverterOptions('cdr', 'cdr'))
    topics = {t.name: t for t in r.get_all_topics_and_types()}
    msgs = []
    while r.has_next():
        topic, data, t = r.read_next()
        msgs.append((topic, deserialize_message(data, get_message(topics[topic].type)), t))
    return topics, msgs


def test_rosbag2_opens_it_and_every_message_deserialises():
    topics, msgs = _read()
    assert {n: t.type for n, t in topics.items()} == {
        '/scan': 'sensor_msgs/msg/LaserScan', '/odom': 'nav_msgs/msg/Odometry',
        '/tf': 'tf2_msgs/msg/TFMessage', '/tf_static': 'tf2_msgs/msg/TFMessage',
        '/map': 'nav_msgs/msg/OccupancyGrid', '/plan': 'nav_msgs/msg/Path',
        '/cmd_vel': 'geometry_msgs/msg/TwistStamped', '/joint_states': 'sensor_msgs/msg/JointState'}
    assert all(t.serialization_format == 'cdr' for t in topics.values())
    count = {}
    for topic, _m, _t in msgs:
        count[topic] = count.get(topic, 0) + 1
    assert count['/scan'] == count['/odom'] == count['/tf'] == count['/cmd_vel'] == 24
    assert count['/map'] == count['/tf_static'] == 1


def test_frames_stamps_and_shapes_are_the_models():
    _topics, msgs = _read()
    for topic, m, t in msgs:
        if topic == '/tf' or topic == '/tf_static':
            stamps = [tr.header.stamp for tr in m.transforms]
        else:
            stamps = [m.header.stamp]
        assert all(s.sec * 1_000_000_000 + s.nanosec == t for s in stamps), topic
        if topic == '/scan':
            assert m.header.frame_id == 'lidar_link' and len(m.ranges) == 480 and len(m.intensities) == 0
        if topic == '/odom':
            assert (m.header.frame_id, m.child_frame_id) == ('odom', 'base_footprint')
        if topic == '/tf':
            assert [(x.header.frame_id, x.child_frame_id) for x in m.transforms] == [('map', 'odom'), ('odom', 'base_footprint')]
        if topic == '/tf_static':
            assert [(x.header.frame_id, x.child_frame_id) for x in m.transforms] == [('base_footprint', 'base_link'), ('base_link', 'lidar_link')]
        if topic == '/map':
            assert m.header.frame_id == 'map' and len(m.data) == m.info.width * m.info.height
            assert set(m.data) <= {-1, 0, 100}
        if topic == '/plan':
            assert m.header.frame_id == 'map' and len(m.poses) >= 1
        if topic == '/cmd_vel':
            assert m.header.frame_id == ''


def test_latched_topics_are_offered_transient_local():
    from rclpy.qos import DurabilityPolicy, ReliabilityPolicy
    topics, _msgs = _read()
    for name, t in topics.items():
        qos = [rosbag2_py.convert_rclcpp_qos_to_rclpy_qos(q) for q in t.offered_qos_profiles]
        latched = name in ('/map', '/tf_static')
        assert qos and all(q.durability == (DurabilityPolicy.TRANSIENT_LOCAL if latched else DurabilityPolicy.VOLATILE)
                           and q.reliability == ReliabilityPolicy.RELIABLE and q.depth == (1 if latched else 10)
                           for q in qos), name
