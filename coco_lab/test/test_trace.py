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

"""Trace schema v1: round trip, validation, versioning, and the doc."""

import copy
import os
import re

from coco_lab import trace as tr
from coco_lab.grid import Grid
from coco_lab.search import search
import pytest

DOC = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'labs',
                   'TRACE_SCHEMA.md')


@pytest.fixture
def found():
    grid, m = Grid.from_ascii("""
        S....
        .###.
        ...#G
    """)
    return search(grid, m['S'], m['G'], 'astar', heuristic='octile').trace


@pytest.fixture
def missing():
    grid, m = Grid.from_ascii('S#G')
    return search(grid, m['S'], m['G'], 'dijkstra').trace


def test_json_round_trip(found, missing):
    for t in (found, missing):
        back = tr.Trace.from_json(t.to_json())
        assert back == t
        assert back.to_json() == t.to_json()


def test_columns_are_equal_length_and_typed(found):
    n = len(found)
    assert n > 0
    for name in tr.COLUMNS:
        assert len(found.events[name]) == n
    assert all(isinstance(v, int) for v in found.events['row'])
    assert all(isinstance(v, float) for v in found.events['g'])


def test_summary_counts_match_events(found):
    kinds = found.events['kind']
    assert found.summary['expansions'] == kinds.count(tr.EXPAND)
    assert found.summary['pushes'] == kinds.count(tr.PUSH)
    assert found.summary['relaxes'] == kinds.count(tr.RELAX)
    assert kinds.count(tr.PATH) == found.summary['path_steps'] + 1


def test_a_reader_accepts_a_newer_minor_and_ignores_extras(found):
    data = found.to_dict()
    data['header']['version'] = '1.7'
    data['header']['something_new'] = 'ignored'
    data['summary']['also_new'] = 3
    tr.Trace.from_dict(data)


@pytest.mark.parametrize('version', ['2.0', '0.9', 'x', ''])
def test_a_reader_refuses_another_major(found, version):
    data = found.to_dict()
    data['header']['version'] = version
    with pytest.raises(tr.TraceError):
        tr.Trace.from_dict(data)


def mutate(t, fn):
    data = copy.deepcopy(t.to_dict())
    fn(data)
    return data


@pytest.mark.parametrize('breakage', [
    lambda d: d['header'].__setitem__('schema', 'other'),
    lambda d: d['events']['g'].pop(),
    lambda d: d['events']['kind'].__setitem__(0, 9),
    lambda d: d['events']['row'].__setitem__(0, 1.5),
    lambda d: d['events']['g'].__setitem__(0, float('nan')),
    lambda d: d['summary'].__setitem__('expansions', -1),
    lambda d: d['summary'].__setitem__('status', 'maybe'),
    lambda d: d['summary'].__setitem__('path_cost', None),
    lambda d: d['summary'].__setitem__('path_steps', 0),
    lambda d: d.pop('summary'),
])
def test_validation_catches_breakage(found, breakage):
    with pytest.raises(tr.TraceError):
        tr.Trace.from_dict(mutate(found, breakage))


def test_a_no_path_trace_must_not_carry_a_path(missing):
    def add_path(d):
        d['summary']['path_cost'] = 1.0
    with pytest.raises(tr.TraceError):
        tr.Trace.from_dict(mutate(missing, add_path))


def test_the_doc_matches_the_implementation():
    """docs/labs/TRACE_SCHEMA.md is normative; pin it to this module."""
    with open(DOC) as f:
        doc = f.read()
    assert f'`{tr.SCHEMA}`' in doc
    assert f'version `"{tr.VERSION}"`' in doc
    columns = doc.split('## Event columns')[1].split('## Event kinds')[0]
    table = re.findall(r'^\| `(\w+)` \| (\w+) \|', columns, flags=re.M)
    assert [name for name, _ in table] == list(tr.COLUMNS)
    for code, kind in enumerate(tr.EVENT_KINDS):
        assert f'| {code} | `{kind}` |' in doc
    for field in ('status', 'expansions', 'pushes', 'relaxes', 'path_cost',
                  'path_length', 'path_steps'):
        assert f'`{field}`' in doc
