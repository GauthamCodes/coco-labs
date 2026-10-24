#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.6, step 1b: Nav2's own AMCL, re-run on a recorded Depot run with chosen parameters (offline).

    source /opt/ros/jazzy/setup.bash && tools/g2/amcl_replay.py RUN_DIR GEN_DIR OUT.json \
        [--set key=value ...] [--rate 2]

The recorded run's /scan, /tf_static, /initialpose and the wheel odometry's TF (odom ->
base_footprint) are played (`ros2 bag play --clock`); the recorded AMCL's own map -> odom is
dropped (a relay passes every other transform), so this AMCL -- `nav2_amcl` with the generated
params plus ``--set`` overrides, on the generated map (`nav2_map_server`) -- localises from the
same evidence the live one had. Every /amcl_pose is compared with the truth
(/model/coco/odometry in the same bag): error over time, at the end, and its largest value.
No simulator runs; ROS domain 83; every process started is stopped.
"""
import argparse
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import diagnose_m6f8 as dg  # noqa: E402


def relay_and_record(out_path, stop_after, truth_odom=False):
    """
    A node: /tf_bag -> /tf without map -> odom; /amcl_pose -> jsonl. ``truth_odom``: the wheel
    odometry's odom -> base_footprint is dropped too and replaced by the truth's (Gazebo's
    /model/coco/odometry as a perfect odometry, odom = the world frame).
    """
    from nav_msgs.msg import Odometry
    from geometry_msgs.msg import TransformStamped
    import rclpy
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from tf2_msgs.msg import TFMessage
    rclpy.init()
    n = Node('g2_amcl_replay_relay', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', value=True)])
    pub = n.create_publisher(TFMessage, '/tf', 100)
    rows = []
    drop = lambda t: (t.header.frame_id == 'map' and t.child_frame_id == 'odom') or (truth_odom and t.child_frame_id == 'base_footprint')
    n.create_subscription(TFMessage, '/tf_bag', lambda m: pub.publish(TFMessage(transforms=[t for t in m.transforms if not drop(t)])), 100)
    if truth_odom:
        def truth(m):
            t = TransformStamped()
            t.header.stamp, t.header.frame_id, t.child_frame_id = m.header.stamp, 'odom', 'base_footprint'
            p = m.pose.pose
            t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = p.position.x, p.position.y, 0.0
            t.transform.rotation = p.orientation
            pub.publish(TFMessage(transforms=[t]))
        n.create_subscription(Odometry, '/model/coco/odometry', truth, 100)
    qos = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)

    def got(m):
        p = m.pose.pose
        rows.append([m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.position.x, p.position.y, dg.yaw(p.orientation), m.pose.covariance[0], m.pose.covariance[7]])
    n.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', got, qos)
    t0 = time.time()
    last = [time.time()]
    while time.time() - t0 < stop_after and rclpy.ok():
        rclpy.spin_once(n, timeout_sec=0.1)
        if os.path.exists(out_path + '.done'):
            break
    with open(out_path, 'w') as f:
        json.dump(rows, f)
    n.destroy_node()
    rclpy.shutdown()


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == '--relay':
        relay_and_record(sys.argv[2], float(sys.argv[3]), len(sys.argv) > 4 and sys.argv[4] == 'truth')
        return 0
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('run'); ap.add_argument('gen'); ap.add_argument('out')
    ap.add_argument('--set', action='append', default=[], help='amcl parameter override, key=value (YAML value)')
    ap.add_argument('--rate', type=float, default=2.0)
    ap.add_argument('--truth-odom', action='store_true', help='replace the wheel odometry with the truth (a perfect odometry)')
    o = ap.parse_args()
    env = dict(os.environ, ROS_DOMAIN_ID='83', PYTHONUNBUFFERED='1')
    # a replay alone: an AMCL left over from any other run would publish into this one's results
    if subprocess.run(['pgrep', '-x', 'amcl'], capture_output=True).returncode == 0:
        sys.exit('REFUSING: another nav2_amcl is running (a replay must be the only one)')
    with open(os.path.join(o.gen, 'nav2', 'nav2_params.yaml')) as f:
        params = yaml.safe_load(f)
    amcl = params['amcl']['ros__parameters']
    overrides = {}
    for kv in o.set:
        k, v = kv.split('=', 1)
        overrides[k] = yaml.safe_load(v)
    amcl.update(overrides)
    amcl['use_sim_time'] = True
    tmp = tempfile.mkdtemp(prefix='g2amcl_')
    pfile = os.path.join(tmp, 'params.yaml')
    with open(pfile, 'w') as f:
        yaml.safe_dump({'amcl': {'ros__parameters': amcl},
                        'map_server': {'ros__parameters': {'yaml_filename': os.path.join(o.gen, 'nav2', 'coco_depot_v1.yaml'), 'use_sim_time': True}},
                        'lifecycle_manager_g2': {'ros__parameters': {'autostart': True, 'node_names': ['map_server', 'amcl'], 'use_sim_time': True}}}, f)
    rec = os.path.join(tmp, 'amcl.json')
    bag = os.path.join(o.run, 'bag')
    dur = float(subprocess.run(['ros2', 'bag', 'info', bag], capture_output=True, text=True, env=env).stdout.split('Duration:')[1].split('s')[0])
    procs = []
    try:
        # each child in its own session: stopping its group stops the node `ros2 run` started too
        # (G2.6: stopping only the `ros2 run` wrapper left the nodes running into later replays)
        spawn = lambda cmd, **kw: subprocess.Popen(cmd, env=env, start_new_session=True, **kw)
        procs.append(spawn([sys.executable, __file__, '--relay', rec, str(dur / o.rate + 60)] + (['truth'] if o.truth_odom else [])))
        for exe, name in (('nav2_map_server', 'map_server'), ('nav2_amcl', 'amcl')):
            procs.append(spawn(['ros2', 'run', exe, name, '--ros-args', '--params-file', pfile], stdout=subprocess.DEVNULL, stderr=open(os.path.join(tmp, f'{name}.log'), 'w')))
        procs.append(spawn(['ros2', 'run', 'nav2_lifecycle_manager', 'lifecycle_manager', '--ros-args', '-r', '__node:=lifecycle_manager_g2', '--params-file', pfile], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(8)
        play = subprocess.run(['ros2', 'bag', 'play', bag, '--clock', '100', '-r', str(o.rate), '--topics', '/scan', '/tf', '/tf_static', '/initialpose'] + (['/model/coco/odometry'] if o.truth_odom else []) + [
                               '--remap', '/tf:=/tf_bag', '--disable-keyboard-controls'], env=env, capture_output=True, text=True, timeout=dur / o.rate + 120)
        time.sleep(3)
        open(rec + '.done', 'w').close()
        procs[0].wait(timeout=30)
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            for p in procs[::-1]:
                try:
                    os.killpg(p.pid, sig)
                except ProcessLookupError:
                    pass
            time.sleep(2)
    with open(rec) as f:
        est = json.load(f)
    data = dg.read(bag)
    truth = (np.array([t for t, _ in data['/model/coco/odometry']]), [dg.pose2d(m) for _, m in data['/model/coco/odometry']])
    rows = []
    for t, x, y, th, cxx, cyy in est:
        g, dt = dg.nearest(truth, t)
        if dt > 0.1:
            continue
        rows.append({'t': round(t, 2), 'dx': round(x - g[0], 4), 'dy': round(y - g[1], 4), 'err': round(math.hypot(x - g[0], y - g[1]), 4),
                     'dth_deg': round(math.degrees(math.atan2(math.sin(th - g[2]), math.cos(th - g[2]))), 2)})
    rows = [r for r in rows if r['t'] > 40]   # after the run's /initialpose (the teleport)
    rep = {'run': os.path.basename(o.run.rstrip('/')), 'overrides': overrides, 'truth_odom': o.truth_odom, 'rate': o.rate, 'updates': len(rows),
           'class': 'STACK component (nav2_amcl) re-run offline on recorded Gazebo data',
           'end': rows[-1] if rows else None, 'max_err_m': max((r['err'] for r in rows), default=None),
           'mean_err_m': round(float(np.mean([r['err'] for r in rows])), 4) if rows else None,
           'play_rc': play.returncode, 'rows': rows}
    with open(o.out, 'w') as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: rep[k] for k in ('run', 'overrides', 'truth_odom', 'updates', 'end', 'max_err_m', 'mean_err_m', 'play_rc')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
