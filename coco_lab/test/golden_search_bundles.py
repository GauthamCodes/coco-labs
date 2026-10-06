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
The golden search bundles, and the one function that writes them.

lab_web's TypeScript decoder is tested against the committed bytes in
``fixtures/search_bundles/``; ``test_searchbundle.py`` rebuilds every one
with :func:`make` and requires byte equality, so the committed set cannot
drift from the writer. To regenerate after an intended format change::

    cd coco_lab && python3 -P test/golden_search_bundles.py \
        test/fixtures/search_bundles

Provenance is FIXED. ``arena_recorded_gz``'s recorded run is MADE UP --
looks typed in by hand, a fixture for the decoder's recorded path, not
evidence of anything -- and says so in its record block.
"""

import os
import sys

from coco_lab import regionsearch as rs
from coco_lab.searchbundle import (SearchBundle, SearchRun,
                                   write_search_bundle)

FIXED = {
    'coco_lab_version': 'golden',
    'git_commit': None,
    'git_dirty': None,
    'created_utc': '2026-10-06T00:00:00Z',
    'seed': None,
    'episode_spec_hash': None,
    'tool': 'coco_lab/test/golden_search_bundles.py',
}

#: The arena's travel table (coco_lab test_regionsearch.ARENA_TRAVEL).
ARENA_TRAVEL = {
    'home': {'bay_1': 7.797056, 'bay_2': 3.826346, 'bay_3': 3.767767,
             'bay_4': 7.767767},
    'bay_1': {'bay_1': 0.0, 'bay_2': 6.943503, 'bay_3': 10.943503,
              'bay_4': 14.943503},
    'bay_2': {'bay_1': 6.943503, 'bay_2': 0.0, 'bay_3': 6.972792,
              'bay_4': 10.972792},
    'bay_3': {'bay_1': 10.943503, 'bay_2': 6.972792, 'bay_3': 0.0,
              'bay_4': 6.972792},
    'bay_4': {'bay_1': 14.943503, 'bay_2': 10.972792, 'bay_3': 6.972792,
              'bay_4': 0.0},
}


def line_problem():
    """Three regions on a line, the robot nearest the first."""
    regs = tuple(rs.Region(f'r{k}', f'R{k}', (0.0, float(k)),
                           (1.0, 2.0, k - 0.4, k + 0.4), (0.9, float(k), 0.0),
                           (0.0, float(k)), 1.5) for k in range(3))
    travel = {'home': {'r0': 1.0, 'r1': 2.0, 'r2': 3.0},
              'r0': {'r0': 0.0, 'r1': 1.0, 'r2': 2.0},
              'r1': {'r0': 1.0, 'r1': 0.0, 'r2': 1.0},
              'r2': {'r0': 2.0, 'r1': 1.0, 'r2': 0.0}}
    return rs.SearchProblem(regs, 'home', (-1.0, 0.0), travel,
                            (0.8, 0.8, 0.8), rs.uniform(3))


class _Region:

    def __init__(self, k, y):
        self.region_id = f'bay_{k}'
        self.bay_y = y
        self.pre_ramp_pose = (0.5, y, 0.0)
        self.platform_bounds = (3.0, 4.2, y - 1.25, y + 1.25)


def arena_problem(detection=0.9):
    """Return the arena problem, from literal geometry (no coco_config)."""
    regs = rs.bay_regions([_Region(k, y) for k, y in
                           enumerate((-6.0, -2.0, 2.0, 6.0), start=1)],
                          2.95)
    return rs.bay_problem(regs, (-2.0, 0.0), ARENA_TRAVEL, detection)


def _line():
    p = line_problem()
    runs = [
        SearchRun('policy', 'sketch',
                  rs.run_search(p, 'expected_cost', 2, seed=5)),
        SearchRun('mine', 'sketch',
                  rs.run_search(p, 'given', 2, seed=5,
                                given_order=(2, 0, 1))),
        SearchRun('gave_up', 'sketch',
                  rs.run_search(p, 'expected_cost', 2, seed=5,
                                max_surveys=1)),
    ]
    return SearchBundle(dict(FIXED, source_kind='sketch'), p, runs), 'none'


def _arena_recorded():
    p = arena_problem()
    tr = rs.replay_search(p, 'expected_cost',
                          [('bay_3', False), ('bay_4', False),
                           ('bay_2', True)])
    t = [float(10 * e) for e in range(tr.n_events)]
    timeline = [[0.0, 'LOCALIZE', None], [1.0, 'SELECT_SEARCH_REGION', None],
                [2.0, 'NAVIGATE_TO_RAMP', None], [9.0, 'SURVEY_REGION', None],
                [30.0, 'MARK_REGION_SEARCHED', None],
                [31.0, 'LEAVE_REGION', None],
                [50.0, 'ABORT', 'OPERATOR_ABORT']]
    rec = SearchRun('made_up', 'recorded', tr, t, timeline,
                    {'note': 'MADE UP for the decoder; not a run'},
                    {'truth_region': 'bay_2', 'source': 'typed by hand'})
    sk = SearchRun('sketch_bay_1', 'sketch',
                   rs.run_search(p, 'expected_cost', 0, seed=1))
    prov = dict(FIXED, source_kind='recorded-run',
                rosbag={'sha256': '0' * 64, 'sim_time_start': 0.0,
                        'sim_time_end': 50.0})
    return SearchBundle(prov, p, [rec, sk]), 'gzip'


GOLDEN = {'line_small': _line, 'arena_recorded_gz': _arena_recorded}


def make(name):
    """Return ``(SearchBundle, compression)`` for golden fixture ``name``."""
    return GOLDEN[name]()


def main(out_dir):
    """Write every golden search bundle under ``out_dir``."""
    for name in sorted(GOLDEN):
        b, compression = make(name)
        digest = write_search_bundle(b, os.path.join(out_dir, name),
                                     compression)
        print(name, digest)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(os.path.dirname(__file__), 'fixtures',
                      'search_bundles'))
