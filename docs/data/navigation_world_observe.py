#!/usr/bin/env python3
"""Read-only evidence: actual navigation publishers and mission/grasp states."""
import argparse
import json
from pathlib import Path
import time

import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from nav_msgs.msg import OccupancyGrid, Path as NavPath, Odometry
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PolygonStamped
from std_msgs.msg import String


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=1800)
    args = parser.parse_args()
    rclpy.init()
    node = rclpy.create_node('navigation_world_observer')
    result = {}

    def callback(topic):
        def receive(msg, info):
            entry = result.setdefault(topic, {'count': 0})
            entry['count'] += 1
            if hasattr(msg, 'header'):
                entry['frame'] = msg.header.frame_id
            if hasattr(msg, 'poses'):
                entry['max_poses'] = max(entry.get('max_poses', 0), len(msg.poses))
            if hasattr(msg, 'info'):
                entry['size'] = [msg.info.width, msg.info.height]
                entry['resolution'] = msg.info.resolution
            if hasattr(msg, 'ranges'):
                entry['rays'] = len(msg.ranges)
            if isinstance(msg, String):
                entry['last'] = msg.data
                if topic == '/mission/state':
                    state = msg.data.split()[0]
                    if not entry.get('states') or entry['states'][-1] != state:
                        entry.setdefault('states', []).append(state)
                elif topic.startswith('/magnet'):
                    if not entry.get('states') or entry['states'][-1] != msg.data:
                        entry.setdefault('states', []).append(msg.data)
                elif topic == '/grasp/status':
                    entry['lifted_seen'] = entry.get('lifted_seen', False) or 'lifted=1' in msg.data
                    entry['placed_seen'] = entry.get('placed_seen', False) or 'outcome=placed' in msg.data
            if isinstance(msg, Odometry):
                p = msg.pose.pose.position
                entry['last_position'] = [p.x, p.y, p.z]
                entry['max_distance_from_home'] = max(
                    entry.get('max_distance_from_home', 0), ((p.x+2)**2+p.y**2)**.5)
            if topic in ('/plan', '/local_plan'):
                for endpoint in node.get_publishers_info_by_topic(topic):
                    if bytes(endpoint.endpoint_gid) == bytes(info['publisher_gid']):
                        pubs = entry.setdefault('observed_publishers', [])
                        publisher = {'node': endpoint.node_name, 'type': endpoint.topic_type}
                        if publisher not in pubs:
                            pubs.append(publisher)
        return receive

    subscriptions = [('/map', OccupancyGrid, True),
                     ('/global_costmap/costmap', OccupancyGrid, True),
                     ('/local_costmap/costmap', OccupancyGrid, True),
                     ('/plan', NavPath, False), ('/local_plan', NavPath, False),
                     ('/scan', LaserScan, False),
                     ('/local_costmap/published_footprint', PolygonStamped, False),
                     ('/mission/state', String, False), ('/grasp/status', String, False),
                     ('/model/coco/odometry', Odometry, False)]
    subscriptions += [(f'/magnet/target_{colour}/state', String, False)
                      for colour in ('red', 'green', 'blue', 'yellow')]
    for topic, message_type, latched in subscriptions:
        qos = QoSProfile(depth=5,
                         reliability=ReliabilityPolicy.RELIABLE if latched else ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL if latched else DurabilityPolicy.VOLATILE)
        node.create_subscription(message_type, topic, callback(topic), qos)
    start = time.monotonic()
    next_save = start
    try:
        while time.monotonic()-start < args.duration:
            rclpy.spin_once(node, timeout_sec=.2)
            if time.monotonic() >= next_save:
                args.out.write_text(json.dumps(result, indent=2)+'\n')
                next_save = time.monotonic()+2
            state = result.get('/mission/state', {}).get('last', '')
            if state.startswith(('state=COMPLETE ', 'state=ABORT ')):
                break
    finally:
        args.out.write_text(json.dumps(result, indent=2)+'\n')
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
