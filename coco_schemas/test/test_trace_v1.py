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
The schemas express every existing Lab 1 trace without loss.

M1_PROMPT B.6 makes a loss here a stop condition, so this is checked on
every Lab 1 bundle in the repository (the recorded full-stack runs and the
teaching and fixture bundles) and on 1,000 seeded maps x 5 algorithms.
"Without loss" is strict: the v1 dict comes back equal AND its canonical
JSON is byte-identical (so 1 stays 1, 1.0 stays 1.0, None stays None),
after a real protobuf serialize/parse.
"""

import glob
import json
import math
import os
import random

from coco_lab.bundle import BundleError, load_bundle
from coco_lab.dstarlite import DStarLite, grid_changes
from coco_lab.graph import HEURISTICS
from coco_lab.grid import Grid
from coco_lab.search import ALGORITHMS, search, TIE_BREAKS
from coco_lab.trace import Trace
from coco_schemas.gen.coco.plan.v1 import incremental_pb2, search_pb2
from coco_schemas.trace_v1 import (incremental_from_v1, incremental_to_v1,
                                   search_from_v1, search_to_v1)
from conftest import REPO
import pytest

CORPUS = 1000


def canonical(d):
    return json.dumps(d, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def round_trip(v1: dict, **kw) -> dict:
    """v1 dict -> three messages -> bytes -> messages -> v1 dict."""
    h, e, s = search_from_v1(v1, **kw)
    h2 = search_pb2.SearchHeader.FromString(h.SerializeToString())
    e2 = search_pb2.SearchEventBatch.FromString(e.SerializeToString())
    s2 = search_pb2.SearchSummary.FromString(s.SerializeToString())
    return search_to_v1(h2, e2, s2)


def assert_lossless(v1: dict):
    back = round_trip(v1)
    assert back == v1
    assert canonical(back) == canonical(v1)
    Trace.from_dict(back)  # and it is still a valid v1 trace


def lab1_bundles():
    dirs = set()
    for pattern in ('coco_lab/test/fixtures/bundles/*/manifest.json',
                    'docs/data/lab1*/**/manifest.json'):
        dirs |= {os.path.dirname(p) for p in
                 glob.glob(os.path.join(REPO, pattern), recursive=True)}
    out = []
    for d in sorted(dirs):
        try:
            out.append((os.path.relpath(d, REPO), load_bundle(d)))
        except BundleError:
            continue  # not a Lab 1 bundle (another lab's format)
    return out


BUNDLES = lab1_bundles()


def test_the_lab1_bundles_were_found():
    names = [n for n, _ in BUNDLES]
    # the three recorded full-stack runs (Phase 1C) and the six fixtures
    for algo in ('astar', 'dijkstra', 'greedy'):
        assert f'docs/data/lab1c/bundles/{algo}' in names, names
    assert sum(n.startswith('coco_lab/test/fixtures/') for n in names) >= 6


@pytest.mark.parametrize('name,bundle', BUNDLES, ids=[n for n, _ in BUNDLES])
def test_every_lab1_bundle_trace_round_trips_exactly(name, bundle):
    assert_lossless(bundle.trace.to_dict())


def random_case(rng: random.Random):
    """One seeded random map, start and goal (sizes 1-30 a side)."""
    w, h = rng.randint(1, 30), rng.randint(1, 30)
    density = rng.uniform(0, 0.6)
    blocked = [rng.random() < density for _ in range(w * h)]
    free = [i for i, b in enumerate(blocked) if not b]
    if not free:
        blocked[0] = False
        free = [0]
    cost = ([rng.choice([0.0, 0.0, rng.uniform(0, 100)]) for _ in range(w * h)]
            if rng.random() < 0.3 else None)
    grid = Grid(w, h, blocked, cost=cost,
                connectivity=rng.choice([4, 8]),
                diagonal_cost=rng.choice([math.sqrt(2), 1.0]),
                corner_cutting=rng.random() < 0.5)
    s, g = rng.choice(free), rng.choice(free)
    return grid, divmod(s, w), divmod(g, w)


def test_1000_seeded_maps_times_five_algorithms_round_trip_exactly():
    rng = random.Random(20261008)
    checked = {a: 0 for a in ALGORITHMS}
    statuses = set()
    for _ in range(CORPUS):
        grid, s, g = random_case(rng)
        for algo in ALGORITHMS:
            kw = {'tie_break': rng.choice(TIE_BREAKS)}
            if algo != 'bfs':
                kw['heuristic'] = rng.choice(HEURISTICS)
            if algo == 'weighted_astar':
                kw['weight'] = rng.choice([0, 0.5, 1, 1.5, 2, 5])
            r = search(grid, s, g, algo, **kw)
            assert_lossless(r.trace.to_dict())
            checked[algo] += 1
            statuses.add(r.status)
    assert statuses == {'found', 'no_path'}
    assert checked == {a: CORPUS for a in ALGORITHMS}


def test_dstar_lite_columns_round_trip_with_infinity():
    rng = random.Random(7)
    seen_inf = False
    for _ in range(50):
        w = h = rng.randint(4, 14)
        blocked = [rng.random() < 0.25 for _ in range(w * h)]
        blocked[0] = blocked[-1] = False
        grid = Grid(w, h, blocked)
        d = DStarLite(grid, (0, 0), (h - 1, w - 1), 'octile')
        d.compute()
        new_blocked = list(blocked)
        for _ in range(3):
            i = rng.randrange(1, w * h - 1)
            new_blocked[i] = not new_blocked[i]
        new = Grid(w, h, new_blocked)
        _, aff = grid_changes(grid, new)
        d.apply_changes(new, aff)
        d.compute()
        cols = d.trace.columns
        seen_inf |= -1.0 in cols['g'] or -1.0 in cols['rhs']
        b = incremental_from_v1(cols)
        b2 = incremental_pb2.IncrementalEventBatch.FromString(
            b.SerializeToString())
        assert incremental_to_v1(b2) == cols
        assert all(v == math.inf or v >= 0 for v in b2.g)
    assert seen_inf  # the -1 <-> +inf mapping was exercised


def test_unknown_v1_fields_are_refused_not_dropped():
    t = BUNDLES[0][1].trace.to_dict()
    t['header'] = dict(t['header'], novel=1)
    with pytest.raises(ValueError):
        search_from_v1(t)
