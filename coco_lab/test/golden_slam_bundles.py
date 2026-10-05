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

r"""
The golden map bundles, and the one function that writes them.

lab_web's TypeScript decoder is tested against the committed bytes in
``fixtures/slam_bundles/``; ``test_slambundle.py`` rebuilds every one with
:func:`make` and requires byte equality, so the committed set cannot drift
from the writer. To regenerate after an intended format change::

    cd coco_lab && python3 -P test/golden_slam_bundles.py \
        test/fixtures/slam_bundles

Provenance is FIXED (a fixed time, no git, a literal version string). The
runs are small on purpose: short routes, few particles, few snapshots.
``recorded_small_gz`` is a Sketch world RELABELLED as a recording, with one
made-up external run -- a fixture for the decoder's recorded-drive path,
not evidence of anything.
"""

import os
import sys

from coco_lab import loc_teaching, map_teaching, mapworld
from coco_lab.sketch import Scenario
from coco_lab.slambundle import ExternalRun, SlamBundle, write_slam_bundle

FIXED = {
    'coco_lab_version': 'golden',
    'git_commit': None,
    'git_dirty': None,
    'created_utc': '2026-10-05T00:00:00Z',
    'seed': None,
    'episode_spec_hash': None,
    'tool': 'coco_lab/test/golden_slam_bundles.py',
}


def _loop():
    m = map_teaching.loop_map()
    sc = Scenario(start=(2.0, 2.0, 0.0), route=[(6.0, 2.0), (6.0, 1.0)],
                  seed=31, noise=map_teaching.noise())
    w = mapworld.from_sketch(m, sc)
    specs = map_teaching.run_specs(particles=4, snapshots=3)
    prov = dict(FIXED, source_kind='sketch', rosbag=None)
    return SlamBundle.compute(m, w, specs, prov), 'none'


def _recorded():
    m = loc_teaching.landmarks_map()
    sc = Scenario(start=(1.5, 1.5, 0.0), route=[(3.5, 1.5)], seed=32,
                  noise=map_teaching.noise())
    w = mapworld.from_sketch(m, sc)
    w.source, w.scenario = 'recorded', None
    w.recorded = {'note': 'a Sketch world relabelled, for the decoder'}
    gt = w.true_poses()
    cells = bytes([0 if i % 7 else 100 for i in range(40 * 30)])
    ext = ExternalRun('backend', 'slam_toolbox', 'loop',
                      [(x + 0.02, y - 0.01, th) for x, y, th in gt], cells,
                      {'width': 40, 'height': 30, 'resolution': 0.25,
                       'origin': [0.5, 0.25]}, {'run': 'made up'})
    prov = dict(FIXED, source_kind='recorded-run',
                rosbag={'sha256': '0' * 64, 'sim_time_start': 0.0,
                        'sim_time_end': 1.0})
    specs = map_teaching.run_specs(snapshots=2, ids=('known', 'odometry'))
    return SlamBundle.compute(m, w, specs, prov, align=True,
                              external=[ext]), 'gzip'


GOLDEN = {'loop_small': _loop, 'recorded_small_gz': _recorded}


def make(name):
    """Return ``(SlamBundle, compression)`` for golden fixture ``name``."""
    return GOLDEN[name]()


def main(out_dir):
    """Write every golden map bundle under ``out_dir``."""
    for name in sorted(GOLDEN):
        b, compression = make(name)
        digest = write_slam_bundle(b, os.path.join(out_dir, name),
                                   compression)
        print(name, digest)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(os.path.dirname(__file__), 'fixtures', 'slam_bundles'))
