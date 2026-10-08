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
Golden traces (M1.4): the event API reproduces Lab 1, on all 1,000 maps.

``golden_traces_v1.json.gz`` froze Lab 1's search (identical to the tag
``coco-lab-v1-final``) on the corpus of ``test_all_five_agree_on_no_path``:
1,000 maps, five algorithms each, with the property's own heuristic,
tie-break and weight. Every one of the 5,000 searches is re-run here
through :func:`coco_lab.search.search_events` and must give the same trace
-- the same expansion order, the same g, h and f, the same parents and
path, the same summary -- checked as the sha256 of the canonical JSON.
"""

import gzip
import hashlib
import json
import math
import os

from coco_lab.events import SEARCH_FIELDS, SearchEventColumns, stream
from coco_lab.search import search, search_events
from coco_lab.trace import COLUMNS, Trace, TraceBuilder
from lab_maps import build_case
import pytest

GOLDEN = os.path.join(os.path.dirname(__file__), 'golden_traces_v1.json.gz')

with gzip.open(GOLDEN, 'rt', encoding='utf-8') as _f:
    DOC = json.load(_f)


def kwargs(run):
    kw = {'heuristic': run['heuristic'], 'tie_break': run['tie_break']}
    if run['algorithm'] == 'weighted_astar':
        kw['weight'] = run['weight']
    return kw


def trace_from_events(graph, start, goal, algorithm, **kw) -> Trace:
    """Collect search_events by hand, independently of search()."""
    events = search_events(graph, start, goal, algorithm, **kw)
    tb = TraceBuilder()
    while True:
        try:
            e = next(events)
        except StopIteration as stop:
            out = stop.value
            break
        tb.add(e[0], e[1:4], e[4], e[5], e[6], e[7:10])
    t = Trace(out.header, tb.columns, out.summary)
    t.validate()
    return t


def digest(t: Trace) -> str:
    return hashlib.sha256(t.to_json().encode('utf-8')).hexdigest()


def test_the_golden_file_is_the_whole_corpus():
    assert DOC['maps'] == 1000 and DOC['searches'] == 5000
    assert DOC['coco_lab_dirty'] is False
    algos = [r['algorithm'] for c in DOC['cases'] for r in c['runs']]
    for a in ('bfs', 'dijkstra', 'astar', 'greedy', 'weighted_astar'):
        assert algos.count(a) == 1000
    statuses = {r['status'] for c in DOC['cases'] for r in c['runs']}
    assert statuses == {'found', 'no_path'}


@pytest.mark.parametrize('block', range(10))
def test_all_5000_searches_reproduce_lab1_exactly(block):
    """Ten blocks of 100 maps, so a failure names its neighbourhood."""
    for i, case in enumerate(DOC['cases'][block * 100:(block + 1) * 100]):
        c = build_case(**case['params'])
        assert [c.start[0], c.start[1]] == case['start']
        assert [c.goal[0], c.goal[1]] == case['goal']
        for run in case['runs']:
            t = trace_from_events(c.grid, c.start, c.goal, run['algorithm'],
                                  **kwargs(run))
            where = (block * 100 + i, run['algorithm'])
            assert digest(t) == run['trace_sha256'], where
            assert t.summary['expansions'] == run['expansions'], where
            assert t.summary['status'] == run['status'], where
            assert len(t) == run['events'], where
            r = search(c.grid, c.start, c.goal, run['algorithm'],
                       **kwargs(run))
            assert digest(r.trace) == run['trace_sha256'], where
            assert r.cost == run['cost'], where


def test_streamed_columns_are_the_trace_in_v2_form():
    """events.stream batches carry exactly the trace's rows (kind + 1)."""
    checked = 0
    for case in DOC['cases'][::25]:
        c = build_case(**case['params'])
        for run in case['runs']:
            t = search(c.grid, c.start, c.goal, run['algorithm'],
                       **kwargs(run)).trace
            cols = SearchEventColumns(search_id=7, tick=3, t_world=0.3)
            gen = stream(search_events(c.grid, c.start, c.goal,
                                       run['algorithm'], **kwargs(run)),
                         cols, batch_size=17)
            batches = list(gen)
            n = len(t)
            assert sum(len(b['seq']) for b in batches) == n
            assert all(len(b['seq']) <= 17 for b in batches)
            merged = {name: [v for b in batches for v in b[name]]
                      for name, _ in SEARCH_FIELDS}
            assert merged['seq'] == list(range(n))
            assert set(merged['tick']) <= {3} and set(merged['t_world']) <= {0.3}
            assert merged['kind'] == [k + 1 for k in t.events['kind']]
            for name in COLUMNS[1:]:
                assert merged[name] == list(t.events[name]), name
            checked += 1
    assert checked == 200


def test_search_events_validates_at_the_call():
    c = build_case(**DOC['cases'][0]['params'])
    with pytest.raises(ValueError):
        search_events(c.grid, c.start, c.goal, 'dfs')
    with pytest.raises(ValueError):
        search_events(c.grid, c.start, c.goal, 'astar', weight=2.0)


def test_events_are_produced_lazily():
    """The first event exists before the search has finished (streaming)."""
    case = max(DOC['cases'], key=lambda k: max(r['events'] for r in k['runs']))
    run = max(case['runs'], key=lambda r: r['events'])
    c = build_case(**case['params'])
    gen = search_events(c.grid, c.start, c.goal, run['algorithm'],
                        **kwargs(run))
    first = next(gen)
    assert first[0] == 0 and first[4] == 0.0  # the start is pushed first
    rest = sum(1 for _ in gen)
    assert rest == run['events'] - 1 and not math.isnan(first[6])
