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
Save Nav2's settled global costmap (Experiment C). Publishes nothing.

  lab5_snapshot.py --out F.json [--differ-from G.json] [--timeout 120]

Waits for ``--repeats`` consecutive ``/global_costmap/costmap_raw``
messages with one content hash (Phase 1C's settled rule) and writes it as
the golden-costmap JSON form (width, height, resolution, origin, frame_id,
data, content_hash, stamp). With ``--differ-from``, a settled costmap only
counts once its hash differs from that file's: the "after" snapshot of a
world that has changed.
"""

import argparse
import json
import sys
import threading
import time

from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.nav2_client import Nav2Probe
import rclpy
from rclpy.executors import MultiThreadedExecutor


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--differ-from')
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--timeout', type=float, default=120.0)
    a = ap.parse_args()
    avoid = None
    if a.differ_from:
        avoid = json.load(open(a.differ_from))['content_hash']
    rclpy.init()
    probe = Nav2Probe(name='lab5_snapshot')
    ex = MultiThreadedExecutor(num_threads=2)
    ex.add_node(probe)
    threading.Thread(target=ex.spin, daemon=True).start()
    deadline = time.monotonic() + a.timeout
    try:
        while time.monotonic() < deadline:
            msg, h = probe.wait_settled(repeats=a.repeats,
                                        timeout=deadline - time.monotonic())
            if msg is None:
                break
            if avoid is not None and h == avoid:
                time.sleep(0.5)
                continue
            s = Snapshot.from_msg(msg, probe.costmap_topic)
            doc = {'width': s.width, 'height': s.height,
                   'resolution': s.resolution, 'origin': list(s.origin),
                   'frame_id': s.frame_id, 'data': list(s.data),
                   'content_hash': h, 'stamp': list(s.stamp),
                   'source_topic': probe.costmap_topic,
                   'saved_wall_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                                   time.gmtime())}
            with open(a.out, 'w') as f:
                json.dump(doc, f)
            print(f'saved {a.out}: {s.width} x {s.height} @ {s.resolution}, '
                  f'{h}')
            return 0
        print('no settled costmap' + (' that differs' if avoid else ''))
        return 1
    finally:
        ex.shutdown()
        probe.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
