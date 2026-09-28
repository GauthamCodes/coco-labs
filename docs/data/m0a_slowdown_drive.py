#!/usr/bin/env python3
"""Milestone 0A -- a stand-in controller for an injected SLOWDOWN.

Publishes a CONSTANT raw forward command on /cmd_vel_nav (TwistStamped,
stamped with the node's sim clock, 20 Hz -- as c2nav42_cmdpath.py's probe
does) for DRIVE sim seconds, then zero for 2 s. Nothing downstream is
touched: whether the wheels follow 0.30 m/s or the collision monitor's
gated command is what the recorder measures.

    python3 m0a_slowdown_drive.py [--speed 0.30] [--drive 10.0]
"""
import argparse
import time

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.parameter import Parameter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--speed', type=float, default=0.30)
    ap.add_argument('--drive', type=float, default=10.0)
    args = ap.parse_args()
    rclpy.init()
    node = rclpy.create_node('m0a_slowdown_drive', parameter_overrides=[
        Parameter('use_sim_time', Parameter.Type.BOOL, True)])
    pub = node.create_publisher(TwistStamped, '/cmd_vel_nav', 10)

    def now():
        return node.get_clock().now().nanoseconds * 1e-9

    deadline = time.monotonic() + 30.0
    while now() == 0.0 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if now() == 0.0:
        print('m0a_slowdown_drive: no /clock -- refusing')
        return 2

    def hold(v, secs):
        t_end = now() + secs
        while now() < t_end:
            msg = TwistStamped()
            msg.header.stamp = node.get_clock().now().to_msg()
            msg.header.frame_id = 'base_footprint'
            msg.twist.linear.x = v
            pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.05)

    t0 = now()
    hold(args.speed, args.drive)
    t1 = now()
    hold(0.0, 2.0)
    print(f'm0a_slowdown_drive: raw {args.speed} m/s from sim t={t0:.3f} to {t1:.3f}')
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
