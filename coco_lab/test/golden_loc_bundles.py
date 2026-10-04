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
The golden localisation bundles, and the one function that writes them.

lab_web's TypeScript decoder is tested against the committed bytes in
``fixtures/loc_bundles/``; ``test_locbundle.py`` rebuilds every one with
:func:`make` and requires byte equality, so the committed set cannot drift
from the writer. To regenerate after an intended format change::

    cd coco_lab && python3 -P test/golden_loc_bundles.py \
        test/fixtures/loc_bundles

Provenance is FIXED (a fixed time, no git, a literal version string), as
for ``golden_bundles.py``. The runs are small on purpose: few particles,
short routes -- a fixture is for a decoder, not a demonstration.
"""

import math
import os
import sys

from coco_lab import loc_teaching
from coco_lab.localise import EKFParams, MCLParams
from coco_lab.locbundle import LocBundle, write_loc_bundle
from coco_lab.sketch import Kidnap, Scenario

FIXED_PROVENANCE = {
    'source_kind': 'sketch',
    'coco_lab_version': 'golden',
    'git_commit': None,
    'git_dirty': None,
    'created_utc': '2026-10-04T00:00:00Z',
    'seed': None,
    'episode_spec_hash': None,
    'rosbag': None,
    'tool': 'coco_lab/test/golden_loc_bundles.py',
}


def _twins():
    sc = Scenario(start=(1.5, 2.0, math.pi / 2),
                  route=[(2.0, 3.0), (3.0, 3.6)], seed=21)
    runs = [('mcl', 'mcl', MCLParams(particles=40, init='global', seed=1)),
            ('ekf', 'ekf', EKFParams(init='global'))]
    return loc_teaching.twins_map(), sc, runs, 'none'


def _kidnap():
    sc = Scenario(start=(1.5, 1.5, 0.0), route=[(4.0, 1.5), (4.0, 3.5)],
                  seed=22, kidnap=Kidnap(t=6.0, to=(9.0, 4.5, math.pi)))
    runs = [('mcl_off', 'mcl', MCLParams(particles=30, seed=2)),
            ('mcl_aug', 'mcl', MCLParams(particles=30, seed=2,
                                         injection='augmented')),
            ('ekf', 'ekf', EKFParams())]
    return loc_teaching.landmarks_map(), sc, runs, 'gzip'


GOLDEN = {'twins_small': _twins, 'kidnap_small_gz': _kidnap}


def make(name):
    """Return ``(LocBundle, compression)`` for golden fixture ``name``."""
    lab_map, sc, runs, compression = GOLDEN[name]()
    return LocBundle.compute(lab_map, sc, runs,
                             dict(FIXED_PROVENANCE)), compression


def main(out_dir):
    """Write every golden loc bundle under ``out_dir``."""
    for name in sorted(GOLDEN):
        b, compression = make(name)
        digest = write_loc_bundle(b, os.path.join(out_dir, name),
                                  compression)
        print(name, digest)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(os.path.dirname(__file__), 'fixtures', 'loc_bundles'))
