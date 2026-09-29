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
The golden bundles, and the one function that writes them.

Phase 1D's TypeScript decoder is tested against the committed bytes in
``fixtures/bundles/``; ``test_bundle.py`` rebuilds every one of them with
:func:`build` and requires byte equality, so the committed set can never
drift from the writer. To regenerate after an intended format change::

    cd coco_lab && python3 -P test/golden_bundles.py test/fixtures/bundles

Provenance is FIXED here (a fixed time, no git, a literal version string),
so the bytes do not depend on when, where or by which version they were
built. That is what a fixture needs; it is not what a real run records.
"""

import os
import sys

from coco_lab import bundle, teaching
from coco_lab.heading import HeadingGrid
from coco_lab.search import search

FIXED_PROVENANCE = {
    'source_kind': 'glass-box',
    'coco_lab_version': 'golden',
    'git_commit': None,
    'git_dirty': None,
    'created_utc': '2026-09-29T00:00:00Z',
    'seed': None,
    'episode_spec_hash': None,
    'rosbag': None,
    'tool': 'coco_lab/test/golden_bundles.py',
}

#: name -> (fixture, algorithm, heuristic, weight, compression, model).
GOLDEN = {
    'astar_open': ('open', 'astar', 'octile', None, 'none', None),
    'dijkstra_cost_field_gz': ('cost_field', 'dijkstra', 'octile', None,
                               'gzip', None),
    'weighted_astar_greedy_trap': ('greedy_trap', 'weighted_astar',
                                   'octile', 2.0, 'none', None),
    'bfs_no_path': ('no_path', 'bfs', 'zero', None, 'none', None),
    'astar_turn_trap_heading': ('turn_trap', 'astar', 'octile', None,
                                'none', None),
}

#: Fixtures searched on the (cell, heading) graph rather than a Grid.
HEADING_FIXTURES = ('turn_trap',)


def make(name):
    """Return the golden bundle called ``name`` and its compression."""
    fixture, algorithm, heuristic, weight, compression, model = GOLDEN[name]
    m, s, g = teaching.load(fixture)
    model = dict(model or teaching.FIXTURES[fixture].run)
    if fixture in HEADING_FIXTURES:
        graph = HeadingGrid.from_map(m, s, g, **model)
        result = search(graph, graph.start_state(s), graph.goal_state(g),
                        algorithm, heuristic, weight=weight)
    else:
        graph = m.to_grid(**model)
        result = search(graph, s, g, algorithm, heuristic, weight=weight)
    b = bundle.Bundle.from_run(result, m,
                               {'start': s, 'goal': g, 'model': model},
                               FIXED_PROVENANCE)
    return b, compression


#: Bundle 1.1: a SYNTHETIC recorded-run bundle, so Phase 1D's decoder has
#: recording arrays to test against. Its search is real (cost_field,
#: Dijkstra); its rosbag hash and streams are made up and say so in
#: ``recording.meta``. It is not evidence of any run. ``cmd`` is listed as
#: missing on purpose, to exercise the "not captured" path.
RECORDED = {'recorded_run_synthetic_1_1': 'none'}

RECORDED_PROVENANCE = dict(
    FIXED_PROVENANCE, source_kind='recorded-run',
    rosbag={'sha256': '0' * 64, 'sim_time_start': 10.0,
            'sim_time_end': 12.0})


def make_recorded(name):
    """Return the synthetic 1.1 recorded-run bundle and its compression."""
    b, _ = make('dijkstra_cost_field_gz')
    recording = {
        'groups': {
            'gt': {'frame': 'map', 'source': '/model/coco/odometry',
                   'count': 3},
            'amcl': {'frame': 'map', 'source': '/amcl_pose', 'count': 2},
            'plan': {'frame': 'map', 'source': '/lab/plan', 'count': 3},
        },
        'missing': ['cmd'],
        'run_id': 'golden-synthetic',
        'meta': {'synthetic': True,
                 'note': 'made-up streams for decoder tests; not a run'},
    }
    streams = {
        'gt': {'t': [10.0, 11.0, 12.0], 'x': [0.5, 1.0, 1.5],
               'y': [0.5, 0.5, 0.75], 'yaw': [0.0, 0.0, 0.25]},
        'amcl': {'t': [10.5, 11.5], 'x': [0.75, 1.25], 'y': [0.5, 0.5],
                 'yaw': [0.0, 0.125]},
        'plan': {'x': [0.5, 1.0, 1.5], 'y': [0.5, 0.5, 0.5],
                 'yaw': [0.0, 0.0, 0.0]},
    }
    rb = bundle.Bundle(dict(RECORDED_PROVENANCE), b.run, b.lab_map, b.trace,
                       recording, streams)
    rb.validate()
    return rb, RECORDED[name]


def build(root):
    """Write every golden bundle under ``root``; return their paths."""
    paths = []
    for name in GOLDEN:
        b, compression = make(name)
        paths.append(bundle.write_bundle(b, os.path.join(root, name),
                                         compression))
    for name in RECORDED:
        b, compression = make_recorded(name)
        paths.append(bundle.write_bundle(b, os.path.join(root, name),
                                         compression))
    return paths


if __name__ == '__main__':
    for path in build(sys.argv[1]):
        print(path)
