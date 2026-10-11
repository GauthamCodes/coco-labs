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
Cut the adapter's short fixture bags from the raw recordings (M3.1).

    python3 coco_lab_ros/test/fixtures/make_case_bags.py [RUNS_ROOT]

Each fixture is a slice of a real recording in ``~/coco_lab_runs`` (never
modified): the messages of the listed topics whose LOG time falls in the
window, copied byte for byte (serialised CDR, not re-encoded) with rosbag2's
own reader and writer, into ``bags/<name>/``. ``FIXTURES.json`` records the
source bag's sha256 for each, so a fixture can be traced to its recording.
"""

import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1_000_000_000

#: name -> (source bag under the runs root, log-time window [s], topics)
CUTS = {
    'lab5_crossing_dwb_1': ('lab5/matrix/crossing_DWB_1/bag', (80.5, 82.5), [
        '/model/coco/odometry', '/amcl_pose', '/scan', '/tf', '/tf_static', '/local_plan',
        '/received_global_plan', '/lab/plan', '/cmd_vel_nav', '/diff_drive_controller/cmd_vel',
        '/lab/actors', '/lab/status', '/collision_monitor_state', '/cmd_vel_arbiter/status']),
    'lab4_a1_fixed_red': ('lab4/matrix/A1_fixed_red/bag', (1791292200.5, 1791292202.5), [
        '/model/coco/odometry', '/mission/state', '/mission/search', '/mission/search_region']),
    'lab2_kidnap_recovery_k1': ('lab2/kidnap_recovery_K1/bag', (50.0, 53.0), [
        '/model/coco/odometry', '/amcl_pose', '/scan', '/tf', '/tf_static',
        '/diff_drive_controller/odom', '/cmd_vel_teleop', '/diff_drive_controller/cmd_vel']),
    'lab2_rl_fidelity_s1': ('lab2/rl_fidelity_s1/rl_bag', None, ['/odometry/filtered']),
}
#: the rl bag has no clock to pick a window by: its first this many seconds of log time
FIRST_SECONDS = 2.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def cut(src, dst, window, topics):
    import rosbag2_py
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=src, storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t for t in r.get_all_topics_and_types()}
    want = [t for t in topics if t in types]
    r.set_filter(rosbag2_py.StorageFilter(topics=want))
    rows = []
    while r.has_next():
        rows.append(r.read_next())
    rows.sort(key=lambda x: x[2])
    if window is None:
        start = rows[0][2]
        lo, hi = start, start + int(FIRST_SECONDS * S)
    else:
        lo, hi = int(window[0] * S), int(window[1] * S)
    keep = [x for x in rows if lo <= x[2] <= hi or x[0] == '/tf_static']
    if os.path.exists(dst):
        shutil.rmtree(dst)
    w = rosbag2_py.SequentialWriter()
    w.open(rosbag2_py.StorageOptions(uri=dst, storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    for t in want:
        w.create_topic(types[t])
    for topic, data, ts in keep:
        w.write(topic, data, ts)
    del w
    counts = {}
    for topic, _, _ in keep:
        counts[topic] = counts.get(topic, 0) + 1
    return counts


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/coco_lab_runs')
    out = {}
    for name, (rel, window, topics) in CUTS.items():
        src = os.path.join(root, rel)
        dst = os.path.join(HERE, 'bags', name)
        counts = cut(src, dst, window, topics)
        mcap = [f for f in os.listdir(src) if f.endswith('.mcap')][0]
        out[name] = {'source': rel, 'source_mcap': mcap,
                     'source_sha256': sha256(os.path.join(src, mcap)),
                     'window_log_s': list(window) if window else f'first {FIRST_SECONDS} s',
                     'messages': counts}
        print(name, sum(counts.values()), 'messages')
    with open(os.path.join(HERE, 'bags', 'FIXTURES.json'), 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write('\n')


if __name__ == '__main__':
    main()
