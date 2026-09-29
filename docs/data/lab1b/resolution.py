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
Phase 1B.3: full-arena Dijkstra at native resolution and at 0.10 m.

Map: the saved Nav2 map ``gazebo_models/maps/coco_navigation`` (0.05 m,
500 x 380), and its conservative 2 x 2 downsample (``LabMap.downsample``,
any occupied -> occupied, else any unknown -> unknown) at 0.10 m.
Unknown is blocked, 8-connected, no corner cutting. Start and goal are the
free cells nearest two fixed map-frame points far apart in the arena, the
SAME points at both resolutions.

Measured per resolution: Dijkstra's compute time (the ``search`` call,
trace included -- the trace IS the product), expansions and events, and
the bundle's size raw and gzipped, plus the time to write and to load it.
Times are the median of ``--repeats`` runs on this machine.

Usage (from the repository root, no ROS needed)::

    python3 docs/data/lab1b/resolution.py [--out docs/data/lab1b/resolution.json]
"""

import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab import bundle, maps  # noqa: E402
from coco_lab.maps import FREE  # noqa: E402
from coco_lab.search import search  # noqa: E402

NAV_YAML = os.path.join(REPO, 'gazebo_models', 'maps',
                        'coco_navigation.yaml')
#: Map-frame (x, y) of the two endpoints: the arena's south-west and
#: north-east interior corners, well inside the walls.
START_XY = (-5.0, -7.5)
GOAL_XY = (16.5, 7.5)
MODEL = {'connectivity': 8, 'corner_cutting': False, 'unknown': 'blocked'}


def nearest_free(m, xy):
    r0, c0 = m.cell_at(*xy)
    best = None
    for r in range(max(0, r0 - 20), min(m.height, r0 + 21)):
        for c in range(max(0, c0 - 20), min(m.width, c0 + 21)):
            if m.at((r, c)) == FREE:
                d = (r - r0) ** 2 + (c - c0) ** 2
                if best is None or d < best[0]:
                    best = (d, (r, c))
    return best[1]


def measure(m, repeats):
    s, g = nearest_free(m, START_XY), nearest_free(m, GOAL_XY)
    grid = m.to_grid(**{k: v for k, v in MODEL.items() if k != 'unknown'},
                     unknown=MODEL['unknown'])
    times, result = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = search(grid, s, g, 'dijkstra')
        times.append(time.perf_counter() - t0)
    prov = bundle.make_provenance('glass-box', tool='resolution.py',
                                  created_utc='2026-09-29T00:00:00Z')
    b = bundle.Bundle.from_run(result, m, {'start': s, 'goal': g,
                                           'model': MODEL}, prov)
    out = {'map': m.id, 'resolution_m': m.resolution,
           'size': [m.width, m.height], 'start': list(s), 'goal': list(g),
           'start_xy': list(m.cell_centre(*s)),
           'goal_xy': list(m.cell_centre(*g)),
           'status': result.status,
           'path_cost_cells': result.cost,
           'path_length_m': result.trace.summary['path_length']
           * m.resolution if result.found else None,
           'expansions': result.trace.summary['expansions'],
           'events': len(result.trace),
           'search_seconds_median': statistics.median(times),
           'search_seconds_all': times}
    for comp in ('none', 'gzip'):
        d = tempfile.mkdtemp()
        try:
            t0 = time.perf_counter()
            bundle.write_bundle(b, os.path.join(d, 'b'), comp)
            t_write = time.perf_counter() - t0
            size = sum(os.path.getsize(os.path.join(d, 'b', f))
                       for f in os.listdir(os.path.join(d, 'b')))
            t0 = time.perf_counter()
            bundle.load_bundle(os.path.join(d, 'b'))
            t_load = time.perf_counter() - t0
        finally:
            shutil.rmtree(d)
        out[f'bundle_{comp}'] = {'bytes': size, 'write_seconds': t_write,
                                 'load_and_validate_seconds': t_load}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--out')
    ap.add_argument('--repeats', type=int, default=3)
    args = ap.parse_args(argv)
    native = maps.load_nav2(NAV_YAML, map_id='coco_navigation/nav2_saved')
    coarse = native.downsample(2)
    result = {'model': MODEL, 'start_xy': START_XY, 'goal_xy': GOAL_XY,
              'load_average': open('/proc/loadavg').read().split()[:3],
              'native': measure(native, args.repeats),
              'coarse_0.10': measure(coarse, args.repeats)}
    text = json.dumps(result, indent=1, sort_keys=True)
    print(text)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(text + '\n')


if __name__ == '__main__':
    main()
