#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R5.1: the acceptance check, run inside the container against the running stack.

    docker exec <container> coco-ros2 check [--json] [--window 10]

Acceptance (docs/v2/r5/R5_PROMPT.md, R5.1): every Nav2 lifecycle node is "active", and the topics
/scan, /odom, /tf, /map, /plan and /cmd_vel exist. Also required here, because a LIVE stack that
broke them must not pass: cmd_vel_arbiter is the only publisher of the wheel topic (README
invariant 3), and /scan, /odom and /clock carry messages. Recorded, not gated: AMCL's pose against
Gazebo's truth, the real-time factor over the window, the node list, foxglove_bridge's
parameters and the installed versions of the main packages.

Evidence class: LIVE -- COCO's ROS 2 stack running now, a Gazebo simulation, never hardware.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import rclpy
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import Odometry
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped

NAV_NODES = ['/bt_navigator', '/controller_server', '/planner_server', '/amcl', '/map_server',
             '/local_costmap/local_costmap', '/global_costmap/global_costmap',
             '/velocity_smoother', '/collision_monitor', '/behavior_server']
REQUIRED_TOPICS = ['/scan', '/odom', '/tf', '/map', '/plan', '/cmd_vel']
WHEELS = '/diff_drive_controller/cmd_vel'
TELEOP = '/cmd_vel_teleop'
PACKAGES = ['ros-jazzy-nav2-bringup', 'ros-jazzy-nav2-amcl', 'ros-jazzy-nav2-smac-planner',
            'ros-jazzy-nav2-regulated-pure-pursuit-controller', 'ros-jazzy-ros-gz-sim',
            'ros-jazzy-gz-ros2-control', 'ros-jazzy-foxglove-bridge', 'ros-jazzy-rmw-cyclonedds-cpp']


def sh(*cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, repr(e)


def lifecycle(node, name):
    cli = node.create_client(GetState, f'{name}/get_state')
    try:
        if not cli.wait_for_service(timeout_sec=5.0):
            return 'no service'
        fut = cli.call_async(GetState.Request())
        rclpy.spin_until_future_complete(node, fut, timeout_sec=5.0)
        res = fut.result()
        return res.current_state.label if res is not None else 'no answer'
    finally:
        node.destroy_client(cli)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', action='store_true', help='print the record as JSON only')
    ap.add_argument('--window', type=float, default=10.0, help='seconds to sample the topics')
    a = ap.parse_args(argv)

    ready = None
    if os.path.exists('/tmp/coco/ready.json'):
        with open('/tmp/coco/ready.json', encoding='utf-8') as f:
            ready = json.load(f)
    index = {}
    if os.path.exists('/opt/coco/levels/index.json'):
        with open('/opt/coco/levels/index.json', encoding='utf-8') as f:
            index = json.load(f)['levels']
    level = index.get((ready or {}).get('level'), {})

    rclpy.init()
    node = rclpy.create_node('coco_ros2_check')
    seen = {'/scan': [], '/odom': [], '/clock': []}
    last = {}

    def stamp(topic):
        def cb(msg):
            seen.setdefault(topic, []).append(time.monotonic())
            last[topic] = msg
        return cb

    # best effort: matches a reliable or a best-effort publisher alike
    sensor = qos_profile_sensor_data
    node.create_subscription(LaserScan, '/scan', stamp('/scan'), sensor)
    node.create_subscription(Odometry, '/odom', stamp('/odom'), sensor)
    node.create_subscription(Clock, '/clock', stamp('/clock'), sensor)
    node.create_subscription(Odometry, '/model/coco/odometry', stamp('/model/coco/odometry'), sensor)
    latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
    node.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', stamp('/amcl_pose'), latched)

    t0 = time.monotonic()
    clocks = []
    while time.monotonic() - t0 < a.window:
        rclpy.spin_once(node, timeout_sec=0.05)
        if '/clock' in last and (not clocks or clocks[-1][2] is not last['/clock']):
            c = last['/clock'].clock
            clocks.append((time.monotonic(), c.sec + c.nanosec * 1e-9, last['/clock']))
    states = {n: lifecycle(node, n) for n in NAV_NODES}
    topics = dict(node.get_topic_names_and_types())
    wheel_pubs = sorted(f'{i.node_namespace.rstrip("/")}/{i.node_name}'
                        for i in node.get_publishers_info_by_topic(WHEELS))
    teleop_pubs = sorted(f'{i.node_namespace.rstrip("/")}/{i.node_name}'
                         for i in node.get_publishers_info_by_topic(TELEOP))
    nodes = sorted(f'{ns.rstrip("/")}/{n}' for n, ns in node.get_node_names_and_namespaces())

    rtf = None
    if len(clocks) >= 2 and clocks[-1][0] > clocks[0][0]:
        rtf = (clocks[-1][1] - clocks[0][1]) / (clocks[-1][0] - clocks[0][0])
    loc = None
    if '/amcl_pose' in last and '/model/coco/odometry' in last:
        p = last['/amcl_pose'].pose.pose.position
        q = last['/model/coco/odometry'].pose.pose.position
        dx, dy = level.get('world_to_map', [0.0, 0.0]) if level else (0.0, 0.0)
        loc = {'amcl_map': [round(p.x, 3), round(p.y, 3)],
               'truth_world': [round(q.x, 3), round(q.y, 3)], 'world_to_map': [dx, dy],
               'error_m': round(math.hypot(p.x - (q.x + dx), p.y - (q.y + dy)), 3)}
    node.destroy_node()
    rclpy.shutdown()

    rc, bridge_params = sh('ros2', 'param', 'dump', '/foxglove_bridge')
    rc2, versions = sh('dpkg-query', '-W', '-f', '${Package} ${Version}\\n', *PACKAGES)
    image = {}
    if os.path.exists('/opt/coco/image.json'):
        with open('/opt/coco/image.json', encoding='utf-8') as f:
            image = json.load(f)

    nav2_active = all(s == 'active' for s in states.values())
    topic_ok = {t: t in topics for t in REQUIRED_TOPICS}
    rates = {t: round(len(v) / a.window, 2) for t, v in seen.items()}
    record = {
        'schema': 'coco_ros2.check', 'version': 1,
        'evidence_class': 'LIVE (COCO\'s ROS 2 stack running now: a Gazebo simulation, never hardware)',
        'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'image': image, 'ready': ready,
        'level': {k: level.get(k) for k in ('id', 'kind', 'derivation', 'verification')} if level else None,
        'acceptance': {'nav2_active': nav2_active, 'topics_exist': topic_ok},
        'required_also': {
            'wheel_topic_publishers': wheel_pubs,
            'arbiter_is_the_only_wheel_publisher': wheel_pubs == ['/cmd_vel_arbiter'],
            'messages_per_s': rates,
            'scan_odom_clock_arrive': all(rates[t] > 0 for t in ('/scan', '/odom', '/clock')),
        },
        'recorded': {
            'lifecycle': states, 'topic_types': {t: topics[t] for t in REQUIRED_TOPICS if t in topics},
            'real_time_factor': None if rtf is None else round(rtf, 3),
            'rtf_window_s': a.window, 'localisation': loc, 'nodes': nodes,
            'teleop_publishers': teleop_pubs,
            'topics': sorted(topics), 'foxglove_bridge_params': bridge_params,
            'package_versions': versions,
        },
    }
    record['pass'] = (nav2_active and all(topic_ok.values())
                      and record['required_also']['arbiter_is_the_only_wheel_publisher']
                      and record['required_also']['scan_odom_clock_arrive'])
    if a.json:
        print(json.dumps(record, indent=1, sort_keys=True))
    else:
        print(f'level        {record["level"] and record["level"]["id"]}')
        print(f'nav2 active  {nav2_active}  ' + ' '.join(f'{n}={s}' for n, s in states.items() if s != 'active'))
        print('topics       ' + ' '.join(f'{t}={"yes" if ok else "NO"}' for t, ok in topic_ok.items()))
        print(f'wheel pubs   {wheel_pubs}')
        print(f'rates /s     {rates}')
        print(f'RTF          {record["recorded"]["real_time_factor"]} over {a.window:g} s')
        print(f'localisation {loc}')
        print('PASS' if record['pass'] else 'FAIL')
    return 0 if record['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
