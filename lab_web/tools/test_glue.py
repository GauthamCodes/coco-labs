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
The Pyodide worker's glue (src/worker/recompute.py), run under CPython.

It is the same file the browser runs; here every output is re-read with
coco_lab's own ``load_bundle``, so what the page draws is a bundle coco_lab
accepts, computed by coco_lab.
"""

import json
import os
import sys

from coco_lab import bundle
from coco_lab.maps import FREE, OCCUPIED
from coco_lab.search import search
import common
import pytest

sys.path.insert(0, os.path.join(common.LAB_WEB, 'src', 'worker'))
# no __pycache__ inside the site's source tree: test/site.test.ts reads every
# file under src/, and a .pyc embeds this checkout's path (measured: on the
# CI runner the path holds the repository name, which that test forbids)
_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True
import recompute  # noqa: E402
sys.dont_write_bytecode = _dont_write

FIXTURES = os.path.join(common.REPO, 'coco_lab', 'test', 'fixtures',
                        'bundles')


def files(name):
    d = os.path.join(FIXTURES, name)
    arrays = 'arrays.bin.gz' if os.path.exists(
        os.path.join(d, 'arrays.bin.gz')) else 'arrays.bin'
    with open(os.path.join(d, 'manifest.json'), 'rb') as f:
        m = f.read()
    with open(os.path.join(d, arrays), 'rb') as f:
        a = f.read()
    return m, arrays, a


def call(name, **req):
    m, arrays, a = files(name) if isinstance(name, str) else name
    return recompute.recompute(json.dumps(req), m, arrays, a)


def reload(out, tmp_path, i=0):
    d = tmp_path / f'b{i}'
    d.mkdir()
    (d / 'manifest.json').write_bytes(out['bundles'][i]['manifest'])
    (d / 'arrays.bin').write_bytes(out['bundles'][i]['arrays_file'])
    return bundle.load_bundle(str(d))


@pytest.fixture(autouse=True)
def empty_cache():
    recompute._CACHE.clear()


def test_no_change_reruns_the_recorded_search(tmp_path):
    src = bundle.load_bundle(os.path.join(FIXTURES, 'astar_open'))
    out = call('astar_open')
    b = reload(out, tmp_path)
    assert b.provenance['tool'] == 'lab_web/pyodide'
    assert b.provenance['source_kind'] == 'glass-box'
    assert b.trace.summary == src.trace.summary
    assert b.trace.events == src.trace.events


def test_the_bytes_are_write_bundles_bytes(tmp_path):
    out = call('astar_open')
    b = reload(out, tmp_path)
    bundle.write_bundle(b, str(tmp_path / 'w'), 'none')
    assert (tmp_path / 'w' / 'manifest.json').read_bytes() == \
        out['bundles'][0]['manifest']
    assert (tmp_path / 'w' / 'arrays.bin').read_bytes() == \
        out['bundles'][0]['arrays_file']


def test_strokes_paint_and_erase(tmp_path):
    out = call('astar_open', strokes=[
        {'value': 'occupied', 'cells': [[10, 10], [10, 11]]},
        {'value': 'free', 'cells': [[10, 11]]}])
    m = reload(out, tmp_path).lab_map
    assert m.at((10, 10)) == OCCUPIED
    assert m.at((10, 11)) == FREE


@pytest.mark.parametrize('what', ['start', 'goal'])
def test_a_stroke_over_the_start_or_goal_is_refused_clearly(what):
    src = bundle.load_bundle(os.path.join(FIXTURES, 'astar_open'))
    r, c = src.run[what][:2]
    with pytest.raises(recompute.Refused, match=f'covered the {what} cell'):
        call('astar_open', strokes=[{'value': 'occupied',
                                     'cells': [[r, c]]}])


def test_settings_change_the_search_and_the_model(tmp_path):
    out = call('astar_open', connectivity=4, runs=[
        {'algorithm': 'weighted_astar', 'heuristic': 'manhattan',
         'weight': 2.5, 'tie_break': 'fifo'}])
    b = reload(out, tmp_path)
    assert b.run['model']['connectivity'] == 4
    h = b.trace.header
    assert (h['algorithm'], h['heuristic'], h['weight'], h['tie_break']) == \
        ('weighted_astar', 'manhattan', 2.5, 'fifo')
    again = search(b.graph(), tuple(b.run['start']), tuple(b.run['goal']),
                   'weighted_astar', 'manhattan', weight=2.5,
                   tie_break='fifo')
    assert again.trace.events == b.trace.events


def test_a_race_runs_each_algorithm_on_identical_inputs(tmp_path):
    algs = ['bfs', 'dijkstra', 'astar', 'greedy']
    out = call('astar_open', optimal=True, runs=[
        {'algorithm': a, 'heuristic': 'octile', 'weight': None,
         'tie_break': 'low_h'} for a in algs])
    assert len(out['bundles']) == 4
    loaded = [reload(out, tmp_path, i) for i in range(4)]
    assert {b.run['map_hash'] for b in loaded} == {loaded[0].run['map_hash']}
    assert [b.trace.header['algorithm'] for b in loaded] == algs
    assert out['optimal_cost'] == loaded[1].trace.summary['path_cost']


def test_more_than_four_runs_are_refused():
    run = {'algorithm': 'bfs', 'heuristic': 'zero', 'weight': None,
           'tie_break': 'low_h'}
    with pytest.raises(recompute.Refused, match='one to four'):
        call('astar_open', runs=[run] * 5)


def test_a_bundle_the_worker_wrote_is_not_reloaded():
    first = call('astar_open', strokes=[{'value': 'occupied',
                                         'cells': [[10, 10]]}])
    assert first['timings']['load_bundle_ms'] > 0
    b = first['bundles'][0]
    second = call((b['manifest'], b['arrays_name'], b['arrays_file']),
                  strokes=[{'value': 'occupied', 'cells': [[11, 10]]}])
    assert second['timings']['load_bundle_ms'] == 0.0


def test_connectivity_is_refused_on_the_heading_graph():
    with pytest.raises(recompute.Refused, match='grid maps'):
        call('astar_turn_trap_heading', connectivity=4)


def test_painting_works_on_the_heading_graph(tmp_path):
    out = call('astar_turn_trap_heading', strokes=[
        {'value': 'occupied', 'cells': [[0, 0]]}])
    b = reload(out, tmp_path)
    assert b.run['graph']['kind'] == 'heading_grid'
    assert b.lab_map.at((0, 0)) == OCCUPIED


def test_share_vectors_reproduce_their_trace_digests():
    """
    The Python half of the share-link round trip (src/lab/share.ts).

    Regenerating test/golden/share_vectors.json reruns the glue on each
    vector's edits and settings; the digests must equal the committed ones,
    which is what a browser opening the link compares against.
    """
    import make_share_vectors
    with open(make_share_vectors.OUT) as f:
        assert f.read() == make_share_vectors.build()
