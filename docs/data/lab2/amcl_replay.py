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
AMCL on wheel odometry vs AMCL on robot_localization's, offline, same scans.

For one scripted drive of one recorded fidelity session, start a fresh
``nav2_map_server`` + ``nav2_amcl`` (the mission's AMCL parameters, as
merged for that session) on a private ROS domain, give AMCL the TRUE pose
at the drive's start, and play the bag from that instant to the drive's
end. Only the odometry AMCL is given differs between the arms:

``wheel``  the recorded ``odom -> base_footprint`` (diff_drive_controller)
``ekf``    robot_localization's ``ekf_node`` (``ekf_odom_imu.yaml``, with
           ``publish_tf`` on) fed the recorded wheel twist and gyro

The recorded ``/tf`` is relayed with the LIVE AMCL's ``map -> odom``
removed (and, in the ekf arm, the wheel ``odom -> base_footprint`` too);
``/tf_static`` is read from the bag and re-published latched, because
playing from an offset skips it. ``/amcl_pose`` is logged with the truth
at its stamp.

Usage (ROS environment; nothing else on the domain)::

    python3 docs/data/lab2/amcl_replay.py SESSION_DIR DRIVE ARM OUT_JSONL
"""

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

import rclpy
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
import yaml

from geometry_msgs.msg import PoseWithCovarianceStamped
from tf2_msgs.msg import TFMessage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAP_YAML = os.path.join(REPO, 'gazebo_models', 'maps', 'coco_navigation.yaml')
EKF_CFG = os.path.join(REPO, 'coco_lab_ros', 'config', 'ekf_odom_imu.yaml')
WORLD_TO_MAP = (2.0, 0.0)


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def bag_reader(bag, topics):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=list(topics)))
    return r, types


def first_bag_time(bag):
    meta = yaml.safe_load(open(os.path.join(bag, 'metadata.yaml')))
    ns = meta['rosbag2_bagfile_information']['starting_time'][
        'nanoseconds_since_epoch']
    return ns * 1e-9


def tf_static(bag):
    r, types = bag_reader(bag, ['/tf_static'])
    while r.has_next():
        _, data, _ = r.read_next()
        return deserialize_message(data, get_message(types['/tf_static']))
    raise SystemExit('no /tf_static in the bag')


def truth_series(bag):
    r, types = bag_reader(bag, ['/model/coco/odometry'])
    out = []
    while r.has_next():
        _, data, _ = r.read_next()
        m = deserialize_message(data, get_message(types[
            '/model/coco/odometry']))
        p = m.pose.pose
        out.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9,
                    p.position.x + WORLD_TO_MAP[0],
                    p.position.y + WORLD_TO_MAP[1], yaw_of(p.orientation)))
    out.sort()
    return out


def nearest(series, t):
    import bisect
    i = bisect.bisect_left(series, (t,))
    c = [series[j] for j in (i - 1, i) if 0 <= j < len(series)]
    return min(c, key=lambda s: abs(s[0] - t))


class Relay(Node):
    """Republish the bag's /tf minus what the replay must own."""

    def __init__(self, drop_child, static_msg, log):
        super().__init__('lab2_tf_relay', parameter_overrides=[
            rclpy.parameter.Parameter('use_sim_time', value=True)])
        self.drop = drop_child
        self.pub = self.create_publisher(TFMessage, '/tf', 100)
        latched = QoSProfile(depth=1,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.spub = self.create_publisher(TFMessage, '/tf_static', latched)
        self.spub.publish(static_msg)
        self.create_subscription(TFMessage, '/tf_rec', self._tf, 100)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose',
                                 self._amcl, latched)
        self.log = log
        self.n = 0

    def _tf(self, msg):
        keep = [t for t in msg.transforms
                if (t.header.frame_id, t.child_frame_id) not in self.drop]
        if keep:
            self.pub.publish(TFMessage(transforms=keep))

    def _amcl(self, m):
        p = m.pose.pose
        self.log.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9,
                         p.position.x, p.position.y, yaw_of(p.orientation),
                         m.pose.covariance[0], m.pose.covariance[7]))
        self.n += 1


def main(argv):
    sess, drive, arm, out = argv
    bag = os.path.join(sess, 'bag')
    rows = [json.loads(line) for line in
            open(os.path.join(sess, 'drives.jsonl'))]
    ticks = [r for r in rows if r['label'] == drive and r['kind'] == 'drive']
    end = [r for r in rows if r['label'] == drive and r['kind'] == 'drive_end']
    t0, t1 = ticks[0]['truth'][0], end[0]['truth'][0]
    truth = truth_series(bag)
    g0 = nearest(truth, t0)
    merged = yaml.safe_load(open(os.path.join(sess, 'nav2_lab_params.yaml')))
    amcl = dict(merged['amcl']['ros__parameters'])
    amcl.update(use_sim_time=True, set_initial_pose=True,
                always_reset_initial_pose=True,
                initial_pose={'x': g0[1], 'y': g0[2], 'z': 0.0,
                              'yaw': g0[3]})
    tmp = tempfile.mkdtemp(prefix='lab2_amcl_')
    pfile = os.path.join(tmp, 'params.yaml')
    yaml.safe_dump({
        'amcl': {'ros__parameters': amcl},
        'map_server': {'ros__parameters': {
            'use_sim_time': True, 'yaml_filename': MAP_YAML}},
        'lifecycle_manager_lab2': {'ros__parameters': {
            'use_sim_time': True, 'autostart': True,
            'node_names': ['map_server', 'amcl']}},
    }, open(pfile, 'w'))
    procs = []

    def start(cmd, name):
        log = open(os.path.join(os.path.dirname(out),
                                f'{os.path.basename(out)}.{name}.log'), 'w')
        procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                      start_new_session=True))

    rclpy.init()
    log = []
    drop = {('map', 'odom')}
    if arm == 'ekf':
        drop.add(('odom', 'base_footprint'))
    node = Relay(drop, tf_static(bag), log)
    ex = SingleThreadedExecutor()
    ex.add_node(node)

    def spin():
        try:
            ex.spin()
        except ExternalShutdownException:
            pass
    th = threading.Thread(target=spin, daemon=True)
    th.start()
    try:
        ros = ['--ros-args', '--params-file', pfile]
        start(['ros2', 'run', 'nav2_map_server', 'map_server'] + ros, 'map')
        start(['ros2', 'run', 'nav2_amcl', 'amcl'] + ros, 'amcl')
        start(['ros2', 'run', 'nav2_lifecycle_manager', 'lifecycle_manager',
               '--ros-args', '-r', '__node:=lifecycle_manager_lab2',
               '--params-file', pfile], 'lifecycle')
        if arm == 'ekf':
            start([os.environ.get('RL_EXEC', 'ekf_node'), '--ros-args', '-r',
                   '__node:=ekf_filter_node', '--params-file', EKF_CFG, '-p',
                   'publish_tf:=true'] if os.environ.get('RL_EXEC') else
                  ['ros2', 'run', 'robot_localization', 'ekf_node',
                   '--ros-args', '-r', '__node:=ekf_filter_node',
                   '--params-file', EKF_CFG, '-p', 'publish_tf:=true'], 'ekf')
        time.sleep(8.0)
        start_off = max(0.0, t0 - first_bag_time(bag) - 2.0)
        dur = (t1 - t0) + 3.0
        play = subprocess.run(
            ['ros2', 'bag', 'play', bag, '--clock', '100', '-r', '1',
             '--start-offset', f'{start_off:.3f}',
             '--playback-duration', f'{dur:.3f}', '--topics', '/scan', '/tf',
             '/diff_drive_controller/odom', '/imu', '--remap',
             '/tf:=/tf_rec'], capture_output=True, text=True,
            timeout=dur * 4 + 120)
        time.sleep(2.0)
    finally:
        for p in procs:
            try:
                os.killpg(p.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
        time.sleep(3.0)
        for p in procs:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        rclpy.try_shutdown()
        th.join(timeout=5)
    with open(out, 'w') as f:
        f.write(json.dumps({'kind': 'meta', 'session': os.path.basename(sess),
                            'drive': drive, 'arm': arm, 't0': t0, 't1': t1,
                            'initial_pose_map': list(g0[1:]),
                            'play_rc': play.returncode,
                            'amcl_poses': len(log)}) + '\n')
        for s in log:
            g = nearest(truth, s[0])
            f.write(json.dumps({'kind': 'amcl', 't': s[0], 'amcl': list(s[1:4]),
                                'cov_xx': s[4], 'cov_yy': s[5],
                                'truth': list(g[1:]), 'truth_dt': g[0] - s[0]})
                    + '\n')
    print(f'{os.path.basename(sess)}/{drive}/{arm}: {len(log)} AMCL poses, '
          f'play rc {play.returncode}')
    return 0 if log else 4


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
