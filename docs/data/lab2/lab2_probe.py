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
Phase 3 (Lab 2) live probe: scans at poses, scripted drives, kidnaps.

Run by ``lab2_run.sh`` on a FRESH simulator with the lab stack up. It
moves the robot in exactly two ways, and neither is a new wheel publisher:

- **teleport**: ``gz service /world/coco_world/set_pose`` on model
  ``coco`` (the kidnap; Sketch's ``Kidnap``). Odometry and AMCL are not
  told, which is what a kidnap is.
- **drive**: ``/cmd_vel_teleop`` (``TwistStamped``), an INPUT of
  ``cmd_vel_arbiter``, which stays the wheel topic's only publisher
  (``lab1c_watch.py`` checks it on every sample). The commands come from
  ``coco_lab.sketch.drive_command`` -- the same function that drives the
  Sketch robot -- applied to the TRUE pose, so a Sketch drive and a
  Gazebo drive follow one control law.

Frames: the map frame is the world frame shifted by
``navigation_world.json``'s ``world_to_map`` (2, 0); everything written
here is in the MAP frame except the raw odometry, which is in ``odom``.

Subcommands (all write JSON lines, one object per sample):

``scans --n N --seed S --out F``
    N seeded poses on the saved map (clearance >= 0.4 m, uniform yaw);
    at each: teleport, settle 2.0 s of sim time, then record the next
    three scans with the truth pose at each scan's stamp.
``drive --label L --start x,y,yaw --route x,y;x,y;... --out F``
    teleport to start, settle, then drive the route at 10 Hz of sim time,
    logging truth, wheel odometry, IMU yaw rate and the command per tick.
``kidnap --to x,y,yaw --rotate-s T --out F``
    wait for AMCL to be within 0.3 m / 0.2 rad of the truth at spawn,
    record 10 s still, teleport to ``--to``, then rotate in place at
    0.5 rad/s for T s of sim time (AMCL updates every 0.2 rad), logging
    every /amcl_pose against the truth.
"""

import argparse
import json
import math
import os
import random
import subprocess
import sys
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data

from geometry_msgs.msg import PoseWithCovarianceStamped, TwistStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, LaserScan

from coco_lab import maps as lab_maps
from coco_lab import sketch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
NAV_YAML = os.path.join(REPO, 'gazebo_models', 'maps', 'coco_navigation.yaml')
WORLD_JSON = os.path.join(REPO, 'gazebo_models', 'config',
                          'navigation_world.json')
WORLD = 'coco_world'
SPAWN_Z = 0.05


def yaw_of(q):
    """Yaw of a quaternion message."""
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def tilt_of(q):
    """Angle between the body z axis and world z, radians."""
    zz = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
    return math.acos(max(-1.0, min(1.0, zz)))


def stamp(msg):
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9


class Probe(Node):
    """Subscriptions and the teleop publisher; all callbacks just store."""

    def __init__(self, w2m):
        super().__init__('lab2_probe',
                         parameter_overrides=[rclpy.parameter.Parameter(
                             'use_sim_time', value=True)])
        self.w2m = w2m
        self.lock = threading.Lock()
        self.truth = []   # (t, x_map, y_map, yaw, z, tilt)
        self.odom = None  # (t, x, y, yaw, vx, wz)
        self.imu = None   # (t, wz)
        self.scans = []   # LaserScan, newest last (bounded)
        self.amcl = None  # (t, x, y, yaw, cxx, cyy, caa)
        self.amcl_n = 0
        self.create_subscription(Odometry, '/model/coco/odometry',
                                 self._truth, qos_profile_sensor_data)
        self.create_subscription(Odometry, '/diff_drive_controller/odom',
                                 self._odom, qos_profile_sensor_data)
        self.create_subscription(Imu, '/imu', self._imu,
                                 qos_profile_sensor_data)
        self.create_subscription(LaserScan, '/scan', self._scan,
                                 qos_profile_sensor_data)
        # AMCL publishes /amcl_pose only on a filter update, latched
        # (transient local): a robot standing at spawn makes no update, so a
        # VOLATILE subscriber never sees the pose. That VOIDed the first two
        # kidnap sessions ("AMCL never localised at spawn").
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._amcl,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.pub = self.create_publisher(TwistStamped, '/cmd_vel_teleop', 10)

    def _truth(self, m):
        p = m.pose.pose
        row = (stamp(m), p.position.x + self.w2m[0],
               p.position.y + self.w2m[1], yaw_of(p.orientation),
               p.position.z, tilt_of(p.orientation))
        with self.lock:
            self.truth.append(row)
            if len(self.truth) > 4000:
                del self.truth[:2000]

    def _odom(self, m):
        p = m.pose.pose
        with self.lock:
            self.odom = (stamp(m), p.position.x, p.position.y,
                         yaw_of(p.orientation), m.twist.twist.linear.x,
                         m.twist.twist.angular.z)

    def _imu(self, m):
        with self.lock:
            self.imu = (stamp(m), m.angular_velocity.z)

    def _scan(self, m):
        with self.lock:
            self.scans.append(m)
            if len(self.scans) > 50:
                del self.scans[:25]

    def _amcl(self, m):
        p = m.pose.pose
        c = m.pose.covariance
        with self.lock:
            self.amcl = (stamp(m), p.position.x, p.position.y,
                         yaw_of(p.orientation), c[0], c[7], c[35])
            self.amcl_n += 1

    # -- helpers --------------------------------------------------------
    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def truth_at(self, t):
        with self.lock:
            rows = list(self.truth)
        if not rows:
            return None
        return min(rows, key=lambda r: abs(r[0] - t))

    def latest_truth(self):
        with self.lock:
            return self.truth[-1] if self.truth else None

    def wait_sim(self, dt):
        t0 = self.now()
        while self.now() - t0 < dt:
            time.sleep(0.01)

    def send(self, v, w):
        m = TwistStamped()
        m.header.stamp = self.get_clock().now().to_msg()
        m.header.frame_id = 'base_link'
        m.twist.linear.x = float(v)
        m.twist.angular.z = float(w)
        self.pub.publish(m)


def teleport(x_map, y_map, yaw, w2m):
    """Move model coco to a MAP-frame pose. Returns gz's reply text."""
    x, y = x_map - w2m[0], y_map - w2m[1]
    req = (f'name: "coco" position: {{x: {x:.4f} y: {y:.4f} z: {SPAWN_Z}}} '
           f'orientation: {{x: 0 y: 0 z: {math.sin(yaw / 2):.6f} '
           f'w: {math.cos(yaw / 2):.6f}}}')
    r = subprocess.run(['gz', 'service', '-s', f'/world/{WORLD}/set_pose',
                        '--reqtype', 'gz.msgs.Pose', '--reptype',
                        'gz.msgs.Boolean', '--timeout', '5000', '--req', req],
                       capture_output=True, text=True, timeout=30)
    out = (r.stdout + r.stderr).strip()
    if 'true' not in out:
        raise RuntimeError(f'set_pose failed: {out!r}')
    return out


def sample_poses(n, seed, clearance=0.4):
    m = lab_maps.load_nav2(NAV_YAML)
    sm = sketch.SketchMap(m)
    free = sm.free_cells(margin=clearance)
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        ix, iy = free[rng.randrange(len(free))]
        x, y = sm.cell_centre(ix, iy)
        out.append((x, y, rng.uniform(-math.pi, math.pi)))
    return out


def cmd_scans(node, args, out):
    poses = sample_poses(args.n, args.seed)
    for i, (x, y, yaw) in enumerate(poses):
        node.send(0.0, 0.0)
        reply = teleport(x, y, yaw, node.w2m)
        node.wait_sim(2.0)
        t_tel = node.now()
        got = 0
        seen = set()
        deadline = time.time() + 30
        while got < 3 and time.time() < deadline:
            with node.lock:
                fresh = [s for s in node.scans if stamp(s) > t_tel
                         and stamp(s) not in seen]
            for s in fresh:
                ts = stamp(s)
                seen.add(ts)
                tr = node.truth_at(ts)
                out.write(json.dumps({
                    'kind': 'scan', 'i': i, 'k': got, 'requested': [x, y, yaw],
                    't': ts, 'truth': list(tr), 'frame_id': s.header.frame_id,
                    'angle_min': s.angle_min, 'angle_max': s.angle_max,
                    'angle_increment': s.angle_increment,
                    'range_min': s.range_min, 'range_max': s.range_max,
                    'ranges': [r if math.isfinite(r) else None
                               for r in s.ranges],
                    'gz_reply': reply if got == 0 else None}) + '\n')
                got += 1
                if got >= 3:
                    break
            time.sleep(0.02)
        out.flush()
        print(f'scans: pose {i + 1}/{len(poses)} ({x:.2f}, {y:.2f}, '
              f'{yaw:.2f}) -> {got} scans', flush=True)
        if got < 3:
            raise RuntimeError(f'pose {i}: only {got} scans in 30 s wall')


def cmd_drive(node, args, out):
    sx, sy, syaw = (float(v) for v in args.start.split(','))
    route = [tuple(float(v) for v in p.split(','))
             for p in args.route.split(';')]
    node.send(0.0, 0.0)
    teleport(sx, sy, syaw, node.w2m)
    node.wait_sim(3.0)
    dt = 0.1
    t_start = node.now()
    next_t = t_start
    k = 0
    status = 'timeout'
    while node.now() - t_start < args.timeout:
        while node.now() < next_t:
            time.sleep(0.002)
        next_t += dt
        tr = node.latest_truth()
        with node.lock:
            od, imu = node.odom, node.imu
        if tr is None or od is None:
            continue
        pose = (tr[1], tr[2], tr[3])
        cmd = None
        while route and cmd is None:
            cmd = sketch.drive_command(pose, route[0], args.v_max,
                                       args.w_max, dt)
            if cmd is None:
                route.pop(0)
        if cmd is None:
            status = 'route_done'
            node.send(0.0, 0.0)
            break
        node.send(*cmd)
        out.write(json.dumps({
            'kind': 'drive', 'label': args.label, 'k': k, 't': node.now(),
            'truth': list(tr), 'odom': list(od),
            'imu_wz': None if imu is None else imu[1],
            'cmd': list(cmd)}) + '\n')
        k += 1
    for _ in range(10):
        node.send(0.0, 0.0)
        node.wait_sim(0.1)
    node.wait_sim(1.0)
    tr = node.latest_truth()
    with node.lock:
        od = node.odom
    out.write(json.dumps({'kind': 'drive_end', 'label': args.label,
                          'status': status, 't': node.now(),
                          'truth': list(tr), 'odom': list(od),
                          'ticks': k}) + '\n')
    out.flush()
    print(f'drive {args.label}: {status}, {k} ticks', flush=True)


def cmd_kidnap(node, args, out):
    to = tuple(float(v) for v in args.to.split(','))
    # 1. AMCL localised at spawn
    deadline = time.time() + 120
    while time.time() < deadline:
        with node.lock:
            a = node.amcl
        tr = node.latest_truth()
        if a and tr and math.hypot(a[1] - tr[1], a[2] - tr[2]) < 0.3 \
                and abs(sketch.wrap(a[3] - tr[3])) < 0.2:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError('AMCL never localised at spawn (VOID)')
    t0 = node.now()
    while node.now() - t0 < 10.0:
        time.sleep(0.1)

    def log(phase):
        with node.lock:
            a, n = node.amcl, node.amcl_n
        tr = node.latest_truth()
        out.write(json.dumps({'kind': 'kidnap', 'phase': phase,
                              't': node.now(), 'amcl': list(a),
                              'amcl_n': n, 'truth': list(tr)}) + '\n')

    log('before')
    reply = teleport(*to, node.w2m)
    t_k = node.now()
    out.write(json.dumps({'kind': 'teleport', 't': t_k, 'to': list(to),
                          'gz_reply': reply}) + '\n')
    print(f'kidnap: teleported to {to} at sim {t_k:.1f}', flush=True)
    node.wait_sim(1.0)
    last_n = -1
    dt = 0.1
    next_t = node.now()
    while node.now() - t_k < args.rotate_s:
        while node.now() < next_t:
            time.sleep(0.002)
        next_t += dt
        node.send(0.0, args.w)
        with node.lock:
            n = node.amcl_n
        if n != last_n:
            last_n = n
            log('after')
    for _ in range(10):
        node.send(0.0, 0.0)
        node.wait_sim(0.1)
    log('end')
    out.write(json.dumps({'kind': 'kidnap_end', 't_kidnap': t_k,
                          't_end': node.now()}) + '\n')
    out.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scans')
    s.add_argument('--n', type=int, default=40)
    s.add_argument('--seed', type=int, default=0)
    d = sub.add_parser('drive')
    d.add_argument('--label', required=True)
    d.add_argument('--start', required=True)
    d.add_argument('--route', required=True)
    d.add_argument('--timeout', type=float, default=240.0)
    d.add_argument('--v-max', type=float, default=0.3)
    d.add_argument('--w-max', type=float, default=1.0)
    k = sub.add_parser('kidnap')
    k.add_argument('--to', required=True)
    k.add_argument('--rotate-s', type=float, default=180.0)
    k.add_argument('--w', type=float, default=0.5)
    for p in (s, d, k):
        p.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    w2m = tuple(json.load(open(WORLD_JSON))['world_to_map'])

    rclpy.init()
    node = Probe(w2m)
    ex = SingleThreadedExecutor()
    ex.add_node(node)
    def spin():
        try:
            ex.spin()
        except ExternalShutdownException:
            pass  # the shutdown below, not an error

    th = threading.Thread(target=spin, daemon=True)
    th.start()
    try:
        deadline = time.time() + 60
        while time.time() < deadline and (node.latest_truth() is None
                                          or node.now() == 0.0):
            time.sleep(0.2)
        if node.latest_truth() is None:
            print('VOID: no /model/coco/odometry', file=sys.stderr)
            return 4
        with open(args.out, 'a') as out:
            {'scans': cmd_scans, 'drive': cmd_drive,
             'kidnap': cmd_kidnap}[args.cmd](node, args, out)
        return 0
    finally:
        try:
            node.send(0.0, 0.0)
        except Exception:
            pass
        # Stop the spin thread BEFORE destroying the node: destroying it
        # under a spinning executor aborted the process ("terminate called
        # without an active exception", exit 134) after every subcommand
        # of the first fidelity session -- the data had been written.
        rclpy.try_shutdown()
        th.join(timeout=10)
        ex.shutdown()
        node.destroy_node()


if __name__ == '__main__':
    sys.exit(main())
