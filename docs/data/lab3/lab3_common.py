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
Phase 4 (Lab 3) evidence helpers: drives, the ground truth, ROS maps.

No ROS needed: these read ``make_drive.py``'s and ``slam_record.py``'s
files. The ground truth is Phase 1B's: ``docs/data/lab1b/arena_maps.py``
``ground_truth`` -- the arena rasterised from ``navigation_world.json`` at
the LiDAR's scan height, on the saved Nav2 map's placement (500 x 380 at
0.05 m, origin (-6.5, -9.5)), in the MAP frame.
"""

import bisect
import gzip
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path[:0] = [os.path.join(REPO, 'coco_lab'),
                os.path.join(REPO, 'coco_config')]

from coco_lab import maps, mapeval  # noqa: E402
from coco_lab.sketch import wrap  # noqa: E402

NAV_YAML = os.path.join(REPO, 'gazebo_models', 'maps', 'coco_navigation.yaml')
PARAMS = os.path.join(REPO, 'gazebo_models', 'config', 'navigation_world.json')
TOL = mapeval.DEFAULT_TOL
THRESHOLDS = (0.25, 0.65)


def load_drive(drive_dir):
    """Return the recorded drive dict (``make_drive.py``'s drive.json.gz)."""
    with gzip.open(os.path.join(drive_dir, 'drive.json.gz'), 'rt') as f:
        d = json.load(f)
    for r in d['rows']:
        r['ranges'] = [math.inf if v is None else v for v in r['ranges']]
    return d


def ground_truth():
    """Return ``(LabMap, placement LabMap)`` -- Phase 1B's truth raster."""
    spec = importlib.util.spec_from_file_location(
        'arena_maps', os.path.join(REPO, 'docs', 'data', 'lab1b',
                                   'arena_maps.py'))
    am = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(am)
    with open(PARAMS) as f:
        cfg = json.load(f)
    like = maps.load_nav2(NAV_YAML, map_id='coco_navigation/nav2_saved')
    truth, _ = am.ground_truth(cfg, like)
    return truth, like


def ros_grid_to_u8(m):
    """
    Return ``(cells, width, height, resolution, origin)``: a recorded
    ``nav_msgs/OccupancyGrid`` as coco_lab's bytes (NORTH row first,
    ``255`` unknown). ROS's data is row-major from the origin (SOUTH row
    first), int8 with -1 unknown. The origin's yaw must be 0.
    """
    if abs(m['origin'][2]) > 1e-9:
        raise ValueError('rotated map origins are not handled')
    w, h = m['width'], m['height']
    data = m['data']
    out = bytearray(w * h)
    for iy in range(h):
        src = iy * w
        dst = (h - 1 - iy) * w
        for ix in range(w):
            v = data[src + ix]
            out[dst + ix] = 255 if v < 0 else v
    return bytes(out), w, h, m['resolution'], (m['origin'][0],
                                                m['origin'][1])


def compose(a, b):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            wrap(a[2] + b[2]))


def online_poses(drive, map_to_odom):
    """
    The backend's belief at each scan: the LATEST ``map -> odom`` whose
    stamp is at or before the scan, composed with the recorded wheel
    odometry at the scan. Before the first one: identity (the backend has
    said nothing yet). Returns ``(poses, n_before_first)``.
    """
    rows = sorted(map_to_odom, key=lambda r: r[0])
    stamps = [r[0] for r in rows]
    out, before = [], 0
    for r in drive['rows']:
        i = bisect.bisect_right(stamps, r['t'] + 1e-9) - 1
        if i < 0:
            before += 1
            m2o = (0.0, 0.0, 0.0)
        else:
            m2o = rows[i][2:5]
        out.append(compose(m2o, r['odom']))
    return out, before


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()
