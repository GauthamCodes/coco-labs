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
The golden Lab 5 bundles, and the one function that writes them.

lab_web's TypeScript decoder is tested against the committed bytes in
``fixtures/move_bundles/``; ``test_movebundle.py`` rebuilds every one with
:func:`make` and requires byte equality, so the committed set cannot drift
from the writer. To regenerate after an intended format change::

    cd coco_lab && python3 -P test/golden_move_bundles.py \
        test/fixtures/move_bundles

Provenance is FIXED. ``drive_toy_gz``'s run is MADE UP -- a straight line
typed in, a fixture for the decoder, not evidence of anything -- and says
so in its record block.
"""

import os
import sys

from coco_lab import movebundle as mb
from coco_lab.replan import ReplanWorld, run_replan

FIXED = {
    'coco_lab_version': 'golden',
    'git_commit': None,
    'git_dirty': None,
    'created_utc': '2026-10-07T00:00:00Z',
    'episode_spec_hash': None,
    'tool': 'coco_lab/test/golden_move_bundles.py',
}

SMALL = """
S.......
..####..
......#.
.##...#.
......#G
"""


def small_world():
    """Return an 8 x 5 world whose map lacks two of its obstacles."""
    rows = list(SMALL.strip().splitlines())
    w, h = len(rows[0]), len(rows)
    truth = [rows[r][c] == '#' for r in range(h) for c in range(w)]
    known = list(truth)
    known[2 * w + 6] = False             # the robot does not know these
    known[4 * w + 6] = False
    return ReplanWorld(w, h, known, truth, (0, 0), (4, 7), sense_radius=1.5,
                       connectivity=8, heuristic='octile',
                       schedule=[(3, [(0, 7, True)])])


def drive_toy():
    """Return a made-up straight drive with every optional part."""
    path = [[x / 10, 0.0, 0.0] for x in range(21)]
    scenario = {'id': 'toy', 'title': 'golden fixture (made up)',
                'path': path, 'path_sha256': '0' * 64,
                'start': [0.0, 0.0, 0.0], 'goal': [2.0, 0.0, 0.0],
                'boxes': [[1.0, 0.8, 0.2, 0.2]], 'actor_radius': 0.15,
                'actors_spec': [], 'inject': None}
    gt = [[t / 10, 0.1 * t / 10, 0.01, 0.0] for t in range(21)]
    run = {'id': 'DWB_1', 'controller': 'DWB', 'outcome': 'succeeded',
           'window': [0.0, 2.0],
           'record': {'note': 'MADE UP for the decoder; not a measurement'},
           'gt': gt, 'amcl': [[0.0, 0.0, 0.0, 0.0], [1.0, 0.1, 0.0, 0.0]],
           'cmd': [[t / 10, 0.1, 0.0] for t in range(21)],
           'wheel': [[t / 10, 0.1, 0.0] for t in range(21)],
           'actors': {'actor_0': [[0.0, 1.5, -1.0, 1.5708],
                                  [2.0, 1.5, 1.0, 1.5708]]},
           'chosen': [[0.5, [[0.05, 0.0], [0.2, 0.0]]]],
           'eval': [[0.5, 819, 400], [1.0, 819, 0]],
           'monitor': [[1.0, 2, 'PolygonSlow']],
           'actor_trigger': {'actor_0': 0.0},
           'rollouts': [{'t': 0.5, 'n': 819, 'n_valid': 400, 'candidates': [
               {'pts': [[0.0, 0.0], [0.1, 0.0]], 'total': 3.5,
                'valid': True, 'best': True},
               {'pts': [[0.0, 0.0], [0.1, 0.1]], 'total': -1.0,
                'valid': False, 'best': False}]}]}
    return scenario, [run]


def make(out_root):
    """Write every golden Lab 5 bundle under ``out_root``."""
    res = run_replan(small_world())
    mb.write_replan_bundle(res, dict(FIXED, source_kind='sketch', seed=None,
                                     rosbag=None),
                           os.path.join(out_root, 'replan_small'), 'none')
    scenario, runs = drive_toy()
    mb.write_drive_bundle(
        scenario, runs, dict(FIXED, source_kind='recorded-run', seed=None,
                             rosbag={'sha256': '0' * 64,
                                     'sim_time_start': 0.0,
                                     'sim_time_end': 2.0}),
        os.path.join(out_root, 'drive_toy_gz'), 'gzip')


if __name__ == '__main__':
    make(sys.argv[1])
