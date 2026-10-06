#!/usr/bin/env python3
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
Phase 5: a run's FSM timeline in SIMULATOR seconds, from its rosbag.

    py.sh docs/data/p05_bagtimes.py RUN_DIR...     (needs ROS: rosbag2_py)

writes ``RUN_DIR/bag_timeline.json``: ``{"timeline": [[t, state, reason],
...], "t0_sim": ..., "t_end_sim": ...}``. Every ``/mission/state`` message
in the bag whose state differs from the previous one is a transition (the
executive publishes one on every transition, ``event=enter``, as well as at
2 Hz). Its simulator time is the bag receive time mapped through the
ground-truth odometry's header stamps (``/model/coco/odometry``: receive
time -> stamp, linearly interpolated). ``t`` is seconds from the first
transition out of IDLE. The bag's ``metadata.yaml`` may be missing (the
recorder was stopped before writing it); MCAP files are self-contained.
"""

import bisect
import glob
import json
import os
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry
from std_msgs.msg import String


def _reader(path):
    mcap = sorted(glob.glob(os.path.join(path, '*.mcap')))
    if not mcap:
        raise SystemExit(f'{path}: no .mcap')
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=mcap[0], storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    r.set_filter(rosbag2_py.StorageFilter(
        topics=['/mission/state', '/model/coco/odometry']))
    return r


def _kv(line):
    return dict(p.split('=', 1) for p in line.split() if '=' in p)


def timeline(run_dir):
    r = _reader(os.path.join(run_dir, 'bag'))
    recv, sim, states = [], [], []
    while r.has_next():
        topic, data, t_ns = r.read_next()
        if topic == '/model/coco/odometry':
            m = deserialize_message(data, Odometry)
            recv.append(t_ns)
            sim.append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9)
        else:
            m = deserialize_message(data, String)
            kv = _kv(m.data)
            states.append((t_ns, kv.get('state'), kv.get('reason')))
    if not recv:
        raise SystemExit(f'{run_dir}: no odometry in the bag')
    # Without an index the reader returns file order, not receive order.
    states.sort(key=lambda x: x[0])
    # The recorder can outlive the run by a few seconds and catch the NEXT
    # run's fresh simulator (same ROS domain): everything after this run's
    # first terminal state is cut, odometry included.
    end = next((t for t, st, _ in states if st in ('COMPLETE', 'ABORT')),
               None)
    if end is not None:
        states = [x for x in states if x[0] <= end]
    pairs = sorted((a, b) for a, b in zip(recv, sim)
                   if end is None or a <= end + 2_000_000_000)
    recv = [a for a, _ in pairs]
    sim = [b for _, b in pairs]

    def to_sim(t_ns):
        i = bisect.bisect_left(recv, t_ns)
        if i <= 0:
            return sim[0]
        if i >= len(recv):
            return sim[-1]
        a, b = recv[i - 1], recv[i]
        f = (t_ns - a) / (b - a) if b > a else 0.0
        return sim[i - 1] + f * (sim[i] - sim[i - 1])

    out, last = [], None
    for t_ns, state, reason in states:
        if state and state != last:
            out.append([to_sim(t_ns), state,
                        None if reason in (None, '--') else reason])
            last = state
    t0 = next((t for t, s, _ in out if s != 'IDLE'), out[0][0] if out else 0)
    return {'timeline': [[round(t - t0, 3), s, rsn] for t, s, rsn in out],
            't0_sim': round(t0, 3),
            'cut_after_terminal': end is not None,
            't_end_sim': round(out[-1][0], 3) if out else None}


def main(argv):
    for run_dir in argv:
        tl = timeline(run_dir)
        with open(os.path.join(run_dir, 'bag_timeline.json'), 'w') as f:
            json.dump(tl, f, indent=1)
        print(run_dir, len(tl['timeline']), 'transitions',
              f"{tl['timeline'][-1][0] if tl['timeline'] else 0:.1f} s")


if __name__ == '__main__':
    main(sys.argv[1:])
