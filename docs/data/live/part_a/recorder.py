"""Record the command path and mode topics with wall-clock arrival times."""
import json
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from nav_msgs.msg import Path
from rclpy.node import Node
from std_msgs.msg import String

out = open(sys.argv[1], 'a', buffering=1)


def w(topic, **kw):
    out.write(json.dumps({'t': time.time(), 'topic': topic, **kw}) + '\n')


class Rec(Node):
    def __init__(self):
        super().__init__('live_audit_recorder')
        for topic in ('/diff_drive_controller/cmd_vel', '/cmd_vel_teleop',
                      '/cmd_vel_gated', '/cmd_vel_rl', '/cmd_vel_approach'):
            self.create_subscription(
                TwistStamped, topic,
                lambda m, tp=topic: w(tp, lin=m.twist.linear.x,
                                      ang=m.twist.angular.z), 50)
        for topic in ('/mission/mode', '/cmd_vel_arbiter/status',
                      '/mission/state'):
            self.create_subscription(
                String, topic, lambda m, tp=topic: w(tp, data=m.data), 50)
        self.create_subscription(
            PoseStamped, '/goal_pose',
            lambda m: w('/goal_pose', x=m.pose.position.x,
                        y=m.pose.position.y), 10)
        self.create_subscription(Path, '/plan',
                                 lambda m: w('/plan', n=len(m.poses)), 10)
        self.create_timer(5.0, self._pubs)

    def _pubs(self):
        topic = '/diff_drive_controller/cmd_vel'
        w('pubcount', wheel=self.count_publishers(topic),
          names=[i.node_name for i in
                 self.get_publishers_info_by_topic(topic)])


rclpy.init()
node = Rec()
try:
    rclpy.spin(node)
except Exception:  # noqa: BLE001 - shutdown by signal
    pass
