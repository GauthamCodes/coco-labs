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
Phase 1B.2: the arena's two maps, exported, and compared.

(a) The saved Nav2 map, ``gazebo_models/maps/coco_navigation.{yaml,pgm}``,
    read with ``coco_lab.maps.load_nav2``.
(b) A ground-truth occupancy map rasterised from the parameters that
    generate the arena -- ``gazebo_models/config/navigation_world.json``
    and the ramp constants in ``coco_config.robot`` -- at (a)'s resolution,
    origin and frame.

READ THIS BEFORE QUOTING THE NUMBER. (a) is not a SLAM map. It is written
by ``gazebo_models/scripts/gen_navigation_world.py`` from the same
parameter file, and ``test_navigation_world.py`` pins it byte for byte. So
(a) versus (b) measures how two *declared rasterisations of one geometry*
differ -- the generator's conservative ``overlap`` rule and its
outline-only ramps, against a ``centre`` rule and solid ramp bodies. It is
a rasterisation-consistency number, NOT a map-quality number. The honest
map-quality number needs a map *built by the robot* (slam_toolbox) of this
arena; the first phase that runs the simulator is 1C.

Ground-truth definition (b): a cell is occupied iff its centre lies in the
footprint of something solid at the LiDAR scan height,
``CHASSIS_GROUND_CLEARANCE + LIDAR_MOUNT_XYZ[2]`` (the height the generator
itself uses). That is every box whose z-extent contains the scan height,
and each ramp-and-platform body over the x-range where its surface is above
the scan plane (the generator's inset rectangle), in full -- the body is
solid there, not just its outline. Everything else is free. Map frame =
world + ``world_to_map``.

Usage (from the repository root, no ROS needed)::

    python3 docs/data/lab1b/arena_maps.py [--out docs/data/lab1b/arena_maps.json]
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path[:0] = [os.path.join(REPO, 'coco_lab'),
                os.path.join(REPO, 'coco_config')]

from coco_config.robot import (CHASSIS_GROUND_CLEARANCE,  # noqa: E402
                               LIDAR_MOUNT_XYZ, RAMP_ANGLE_DEG)
from coco_lab import maps  # noqa: E402
from coco_lab.maps import FREE, OCCUPIED, UNKNOWN  # noqa: E402

PARAMS = os.path.join(REPO, 'gazebo_models', 'config',
                      'navigation_world.json')
NAV_YAML = os.path.join(REPO, 'gazebo_models', 'maps',
                        'coco_navigation.yaml')


def ground_truth(cfg, like, parts=('boxes', 'ramps')):
    """Rasterise (b) at ``like``'s placement; return (map, counts)."""
    scan = CHASSIS_GROUND_CLEARANCE + LIDAR_MOUNT_XYZ[2]
    dx, dy = cfg['world_to_map']
    r = maps.Raster(like.width, like.height, like.resolution, like.origin)
    counts = {'boxes_used': 0, 'boxes_not_at_scan_height': [],
              'ramps_used': 0, 'scan_height_m': scan}
    if 'boxes' in parts:
        for box in cfg['boxes']:
            (x, y, z), (sx, sy, sz) = box['pose'], box['size']
            if not z - sz / 2 <= scan <= z + sz / 2:
                counts['boxes_not_at_scan_height'].append(box['name'])
                continue
            r.paint(x - sx / 2 + dx, x + sx / 2 + dx,
                    y - sy / 2 + dy, y + sy / 2 + dy, OCCUPIED, 'centre')
            counts['boxes_used'] += 1
    if 'ramps' in parts:
        bay = cfg['ramp_bays']
        inset = scan / math.tan(math.radians(RAMP_ANGLE_DEG))
        for y in bay['centres_y']:
            x0 = bay['foot_x'] + inset
            x1 = (bay['foot_x'] + 2 * bay['run'] + bay['platform_length']
                  - inset)
            r.paint(x0 + dx, x1 + dx, y - bay['width'] / 2 + dy,
                    y + bay['width'] / 2 + dy, OCCUPIED, 'centre')
            counts['ramps_used'] += 1
    m = r.build(map_id='coco_navigation/ground_truth_scan_height',
                frame=like.frame,
                meta={'rule': 'centre', 'parts': list(parts),
                      'source': os.path.relpath(PARAMS, REPO)})
    return m, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)
    with open(PARAMS) as f:
        cfg = json.load(f)
    a = maps.load_nav2(NAV_YAML, map_id='coco_navigation/nav2_saved')
    b, counts = ground_truth(cfg, a)
    b_boxes, _ = ground_truth(cfg, a, parts=('boxes',))
    b_ramps, _ = ground_truth(cfg, a, parts=('ramps',))

    ramp_cells = [i for i, v in enumerate(b_ramps.occupancy)
                  if v == OCCUPIED]
    in_a = [a.occupancy[i] for i in ramp_cells]
    result = {
        'label': 'rasterisation consistency, NOT map quality: (a) is '
                 'generated from the same parameters as (b)',
        'a': {'id': a.id, 'content_hash': a.content_hash(),
              'size': [a.width, a.height], 'resolution': a.resolution,
              'origin': list(a.origin),
              'occupied': a.count(OCCUPIED), 'free': a.count(FREE),
              'unknown': a.count(UNKNOWN)},
        'b': {'id': b.id, 'content_hash': b.content_hash(),
              'occupied': b.count(OCCUPIED), **counts},
        'all': maps.compare_occupied(b, a),
        'boxes_only_truth': maps.compare_occupied(b_boxes, a),
        'ramp_bodies': {
            'truth_cells': len(ramp_cells),
            'a_occupied': in_a.count(OCCUPIED),
            'a_unknown': in_a.count(UNKNOWN),
            'a_free': in_a.count(FREE),
        },
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(text + '\n')


if __name__ == '__main__':
    main()
