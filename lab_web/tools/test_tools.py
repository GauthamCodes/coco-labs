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
The Python half of lab_web's cross-language tests, plus its guards.

Run from the repository root with ``coco_lab`` importable and no ROS::

    python -P -m pytest lab_web/tools
"""

import json
import os
import re
import shutil
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coco_lab import bundle  # noqa: E402
from coco_lab.bundle import BundleError  # noqa: E402
import common  # noqa: E402
import make_expectations  # noqa: E402

INVALID = make_expectations.INVALID
with open(os.path.join(INVALID, 'index.json')) as _f:
    INDEX = json.load(_f)
SRC = os.path.join(common.LAB_WEB, 'src')


# -- the committed expectations cannot drift from coco_lab ---------------------

def test_expectations_and_corpora_regenerate_byte_identical():
    assert make_expectations.check() == []


def test_the_expectations_cover_all_nine_bundles():
    with open(make_expectations.EXPECTED) as f:
        doc = json.load(f)
    ids = [b['id'] for b in doc['bundles']]
    assert ids == [bid for bid, _ in common.bundle_sources()]
    assert len(ids) == 9
    versions = {b['id']: b['version'] for b in doc['bundles']}
    assert sorted(v for v in versions.values()) == ['1.0'] * 5 + ['1.1'] * 4
    synthetic = next(b for b in doc['bundles']
                     if b['id'] == 'recorded_run_synthetic_1_1')
    assert synthetic['geo'] is None
    assert synthetic['recording']['missing'] == ['cmd']
    for b in doc['bundles']:
        assert b['content_hash'] == b['computed_content_hash']


def test_the_json_corpus_is_large_enough_and_python_agrees():
    with open(make_expectations.JSON_CORPUS) as f:
        doc = json.load(f)
    assert len(doc['cases']) >= 1000
    for case in doc['cases']:
        if case['canonical'] is None:
            with pytest.raises(ValueError):
                bundle.canonical_json(json.loads(case['input']))
        else:
            assert bundle.canonical_json(json.loads(case['input'])) == \
                case['canonical']
    for bits, text in doc['floats']:
        assert repr(struct.unpack('>d', bytes.fromhex(bits))[0]) == text


def test_the_golden_fixtures_are_the_committed_bytes():
    # lab_web reads the fixtures in place; it never copies or rewrites them
    for name in common.GOLDEN:
        path = os.path.join(common.GOLDEN_DIR, name)
        assert sorted(os.listdir(path))[-1] == 'manifest.json'


# -- the invalid corpus: Python refuses (or, once, accepts) every case ---------

@pytest.mark.parametrize('name', sorted(INDEX['cases']))
def test_python_decides_every_invalid_case(name):
    case = INDEX['cases'][name]
    path = os.path.join(INVALID, name)
    if case['python'] == 'accepts':
        assert bundle.load_bundle(path).trace.summary['status'] == 'found'
        return
    with pytest.raises((BundleError, ValueError)) as info:
        bundle.load_bundle(path)
    assert re.search(case['match'], str(info.value)), str(info.value)


def test_python_refuses_the_generated_cases(tmp_path):
    for name, case in INDEX['generated'].items():
        d = tmp_path / name
        shutil.copytree(os.path.join(common.GOLDEN_DIR, case['base']), d)
        with open(d / 'manifest.json', 'wb') as f:
            f.write(b' ' * case['bytes'])
        with pytest.raises(BundleError, match=case['match']):
            bundle.load_bundle(str(d))


def test_every_case_names_a_known_code_and_tier():
    codes = {'json', 'bounds', 'schema', 'version', 'structure', 'table',
             'length', 'hash', 'map', 'map_hash', 'dtype', 'nonfinite',
             'provenance', 'recording', 'run', 'run_header',
             'trace_invariant', 'compression'}
    for name, case in INDEX['cases'].items():
        assert case['tier'] in ('structural', 'semantic'), name
        if case['tier'] == 'semantic':
            assert case['code'] is None and case['python'] == 'refuses'
        else:
            assert case['code'] in codes, name


# -- the catalog ----------------------------------------------------------------

def test_the_catalog_validates_and_replays_what_it_serves(tmp_path):
    import build_catalog
    out = tmp_path / 'generated'
    # Lab 1 checks: the map block is built and checked by its own test
    cat = build_catalog.build(str(out), wheel=None, with_benchmark=False,
                              with_map=False)
    ids = [e['id'] for e in cat['bundles']]
    assert 'recorded_run_synthetic_1_1' not in ids   # a fixture, not evidence
    for e in cat['bundles']:
        d = out / e['path']
        b = bundle.load_bundle(str(d))
        with open(d / 'manifest.json') as f:
            assert json.load(f)['content_hash'] == e['content_hash']
        if e['source_kind'] == 'glass-box':
            assert e['validated']['replay'].startswith('reproduced')
        assert b.provenance['source_kind'] == e['source_kind']
    # served bytes are the source bytes, unmodified
    for bid, rel in build_catalog.SERVED:
        for name in os.listdir(os.path.join(common.REPO, rel)):
            with open(os.path.join(common.REPO, rel, name), 'rb') as f:
                src = f.read()
            with open(out / 'bundles' / bid / name, 'rb') as f:
                assert f.read() == src


# -- guard: the browser never re-implements a search (CLAUDE.md rule 8) ---------

FORBIDDEN = [
    (r'\bpriority\s*queue\b|\bPriorityQueue\b|\bMinHeap\b|\bheapq?\b',
     'a priority queue / heap'),
    (r'\bheappush\b|\bheappop\b|\bsiftUp\b|\bsiftDown\b|\bbubbleUp\b',
     'heap operations'),
    (r'\bneighbou?rs?\s*\(', 'a neighbour generator'),
    (r'\b(manhattan|octile|euclidean|chebyshev)\s*\(',
     'a heuristic function'),
    (r'\bheuristic\s*\(', 'a heuristic function'),
    (r'\b(dijkstra|astar|aStar|bfs|greedyBestFirst)\s*\(',
     'a search function'),
    (r'\bopenSet\b|\bclosedSet\b|\bcameFrom\b|\bopenList\b',
     'search bookkeeping'),
    (r'\bedge_?[Cc]ost\s*\(', 'an edge-cost function'),
    # Lab 2: the browser renders localisation; coco_lab computes it
    (r'\b(ray_?[Cc]ast\w*|castRay\w*|cast_ray\w*)\s*\(', 'a ray caster'),
    (r'\b[Kk]alman\w*\s*\(|\b(ekf|EKF)(Predict|Update|_predict|_update)\w*\s*\(',
     'a Kalman step'),
    (r'\b[Rr]esample\w*\s*\(|\blowVariance\w*\s*\(', 'particle resampling'),
    (r'\b(likelihood\w*|motion_?[Mm]odel\w*|sample_?[Mm]otion\w*)\s*\(',
     'a sensor or motion model'),
    (r'\bgauss(ian)?\s*\(|\brandn\s*\(|\bMath\.random\b',
     'random sampling (filters and Sketch draw from coco_lab\'s seeded RNG)'),
    # Lab 3: the browser renders maps; coco_lab builds and scores them
    (r'\b(log_?[Oo]dds\w*|bresenham\w*|integrate[Ss]can\w*|'
     r'inverse_?[Ss]ensor\w*)\s*\(', 'occupancy mapping'),
    (r'\b(icp|ICP|scan_?[Mm]atch\w*|gauss_?[Nn]ewton\w*|'
     r'optimi[sz]e_?[Gg]raph\w*|loop_?[Cc]losure\w*)\s*\(',
     'scan matching / pose-graph optimisation'),
    (r'\b(ate|alignSe2|align_se2|scoreMap|score_map|diffRaster)\s*\(',
     'a mapping metric (coco_lab.mapeval computes every score)'),
]


def _source_files():
    for root, _, files in os.walk(SRC):
        for name in files:
            if name.endswith(('.ts', '.tsx', '.js', '.py')):
                yield os.path.join(root, name)


def test_loc_expectations_regenerate_byte_identical():
    import make_loc_expectations
    with open(make_loc_expectations.OUT) as f:
        assert f.read() == make_loc_expectations.build()


def test_slam_expectations_regenerate_byte_identical():
    import make_slam_expectations
    with open(make_slam_expectations.OUT) as f:
        assert f.read() == make_slam_expectations.build()


def test_every_lab3_cited_test_exists():
    """Every Lab 3 scene and the challenge name tests; each must exist."""
    import build_map
    src = [list(v) for v in build_map.SCENES.values()] + [build_map.CHALLENGE]
    cited = sorted(set(_cited_tests(src)))
    assert len(cited) >= 8, cited
    for path, name in cited:
        full = os.path.join(common.REPO, path)
        assert os.path.exists(full), path
        with open(full) as f:
            assert re.search(rf'^def {name}\(', f.read(), re.M), \
                f'{path}::{name}'


def test_the_catalog_serves_lab3_validated_and_replayed(tmp_path):
    """Every map bundle in the catalog is coco_lab's, replayed, scored."""
    import build_map
    from coco_lab import slambundle
    out = tmp_path / 'generated'
    block = build_map.map_block(str(out))
    kinds = [e['kind'] for e in block['bundles']]
    assert kinds.count('sketch') == 3 and kinds.count('challenge') == 1
    for e in block['bundles']:
        b = slambundle.load_slam_bundle(str(out / e['path']))
        assert b.manifest()['content_hash'] == e['content_hash']
        assert [r['id'] for r in e['runs']] == [r for r, _ in b.runs]
        if e['kind'] != 'replay':
            assert e['spec']['clicks'] and e['spec']['seed'] == \
                b.provenance['seed']
    assert block['challenge']['score'].startswith('round(100 x F1)')


def test_lab_web_src_has_no_search_implementation():
    files = list(_source_files())
    assert files, 'lab_web/src is empty'
    hits = []
    for path in files:
        with open(path) as f:
            text = f.read()
        for pattern, what in FORBIDDEN:
            for m in re.finditer(pattern, text):
                hits.append(f'{os.path.relpath(path, common.LAB_WEB)}: '
                            f'{what}: {m.group(0)!r}')
    assert hits == []


def test_the_guard_catches_what_it_names():
    samples = ['const pq = new PriorityQueue()', 'heappush(q, x)',
               'function neighbours(s) {', 'octile(dr, dc)',
               'dijkstra(graph, s, g)', 'cameFrom.set(n, c)',
               'edgeCost(a, b)', 'rayCast(map, p, a)', 'kalmanUpdate(mu, P)',
               'ekfPredict(m)', 'resample(w)', 'lowVarianceResample(w, u)',
               'likelihoodField(d)', 'sampleMotion(u)', 'gauss(0, 1)',
               'Math.random()', 'logOdds(p)', 'bresenham(a, b)',
               'integrateScan(g, z)', 'icp(a, b)', 'scanMatch(a, b)',
               'gaussNewton(g)', 'optimiseGraph(g)', 'loopClosure(k)',
               'alignSe2(a, b)', 'scoreMap(t, m)', 'ate(e, t)']
    for s in samples:
        assert any(re.search(p, s) for p, _ in FORBIDDEN), s


def test_lab_web_is_colcon_ignored():
    assert os.path.exists(os.path.join(common.LAB_WEB, 'COLCON_IGNORE'))


# -- every claim cites real evidence (CLAUDE.md "COCO Lab" rule 5) ----------------

CITED_TEST = re.compile(r'([\w/.-]+\.py)::(test_\w+)')


def _cited_tests(obj):
    if isinstance(obj, str):
        yield from CITED_TEST.findall(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _cited_tests(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _cited_tests(v)


def test_every_cited_test_exists():
    """The exhibit, the settings panel and the tracking plot name tests; each must exist."""
    import build_catalog
    src = [build_catalog.exhibit_data(), build_catalog.TRACKING_CITE,
           build_catalog.settings_analysis({build_catalog.SQRT2})['cite']]
    cited = sorted(set(_cited_tests(src)))
    assert len(cited) >= 4, cited
    for path, name in cited:
        full = os.path.join(common.REPO, path)
        assert os.path.exists(full), path
        with open(full) as f:
            assert re.search(rf'^def {name}\(', f.read(), re.M), f'{path}::{name}'


def test_the_catalog_serves_the_exhibit_and_the_tracking_series(tmp_path):
    import build_catalog
    out = tmp_path / 'generated'
    # Lab 1 checks: the map block is built and checked by its own test
    cat = build_catalog.build(str(out), wheel=None, with_benchmark=False,
                              with_map=False)
    ex = json.loads((out / cat['exhibit']).read_text())
    assert ex['c']['label'] == 'reconstruction'
    assert ex['b']['analogue']['paths_recorded'] is False
    tracked = [e for e in cat['bundles'] if e.get('tracking')]
    assert [e['id'] for e in tracked] == ['lab1c_astar', 'lab1c_dijkstra', 'lab1c_greedy']
    for e in tracked:
        s = json.loads((out / e['tracking']).read_text())
        rec = bundle.load_bundle(str(out / e['path'])).recording['meta']
        assert s['stats'] == rec['tracking_error_m']
        assert len(s['t']) == len(s['e']) == rec['tracking_error_m']['n']
