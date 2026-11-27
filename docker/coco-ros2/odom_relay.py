#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R5.1: /odom for the coco-ros2 image -- a relay of COCO's wheel odometry.

COCO's stack publishes its wheel odometry as ``/diff_drive_controller/odom``
(gazebo_models/urdf/coco_controllers.yaml; Nav2 reads that topic). R5's
acceptance names the conventional ``/odom``, so the image republishes every
message unchanged under that name. Nothing in COCO's stack reads ``/odom``;
this node only adds the name. Its own node name says what it is.
"""
import rclpy
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

SOURCE = '/diff_drive_controller/odom'
TARGET = '/odom'


class OdomRelay(Node):
    def __init__(self):
        super().__init__('coco_odom_relay')
        self.pub = self.create_publisher(Odometry, TARGET, 10)
        self.create_subscription(Odometry, SOURCE, self.pub.publish, 10)
        self.get_logger().info(f'relaying {SOURCE} -> {TARGET} (unchanged)')


def main():
    rclpy.init()
    node = OdomRelay()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
