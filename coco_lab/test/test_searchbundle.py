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

"""Search bundle 1.0: round trip, byte stability, replay, refusals."""

import json
import os

from coco_lab import regionsearch as rs, searchbundle as sbm
import golden_search_bundles as golden
import pytest

HERE = os.path.dirname(__file__)
FIXTURES = os.path.join(HERE, 'fixtures', 'search_bundles')


@pytest.mark.parametrize('name', sorted(golden.GOLDEN))
def test_it_round_trips_and_replays(name, tmp_path):
    b, compression = golden.make(name)
    digest = sbm.write_search_bundle(b, str(tmp_path / 'b'), compression)
    back = sbm.load_search_bundle(str(tmp_path / 'b'))
    assert back.manifest(compression)['content_hash'] == digest
    assert [r.id for r in back.runs] == [r.id for r in b.runs]
    sbm.replay_check(back)


@pytest.mark.parametrize('name', sorted(golden.GOLDEN))
def test_the_committed_golden_bytes_are_what_the_writer_writes(
        name, tmp_path):
    b, compression = golden.make(name)
    sbm.write_search_bundle(b, str(tmp_path / name), compression)
    for f in sorted(os.listdir(os.path.join(FIXTURES, name))):
        with open(os.path.join(FIXTURES, name, f), 'rb') as a, \
                open(tmp_path / name / f, 'rb') as c:
            assert a.read() == c.read(), f'{name}/{f}'


def test_a_recording_is_rebuilt_from_its_looks_alone():
    p = golden.arena_problem()
    tr = rs.replay_search(p, 'expected_cost',
                          [('bay_3', False), ('bay_4', False),
                           ('bay_2', True)])
    assert tr.summary['order'] == ['bay_3', 'bay_4', 'bay_2']
    assert tr.summary['discovered'] == 'bay_2'
    assert tr.summary['truth'] is None
    # The same looks, simulated: the same choices and beliefs.
    sim = rs.run_search(p, 'expected_cost', 1, true_detection=[1.0] * 4)
    assert (sim.kind, sim.region, sim.belief) == \
        (tr.kind, tr.region, tr.belief)


def test_a_recording_that_disagrees_with_the_policy_is_refused():
    p = golden.arena_problem()
    with pytest.raises(rs.SearchError, match='policy expected_cost '
                       'chooses bay_3'):
        rs.replay_search(p, 'expected_cost', [('bay_1', True)])


def test_a_recording_that_ends_mid_search_ends_stopped():
    p = golden.arena_problem()
    tr = rs.replay_search(p, 'expected_cost', [('bay_3', False)])
    assert tr.summary['status'] == 'stopped'
    assert not rs.challenge_passed(tr)


def test_replay_does_not_read_the_evaluator_block(tmp_path):
    b, _ = golden.make('arena_recorded_gz')
    b.runs[0].evaluator = {'truth_region': 'bay_4', 'lie': True}
    sbm.replay_check(b)
    b.runs[0].evaluator = None
    sbm.replay_check(b)


def test_a_tampered_trace_fails_replay():
    b, _ = golden.make('line_small')
    b.runs[0].trace.belief[0] += 1e-6
    with pytest.raises(sbm.SearchBundleError):
        sbm.replay_check(b)


def test_a_tampered_array_fails_the_content_hash(tmp_path):
    b, _ = golden.make('line_small')
    d = str(tmp_path / 'b')
    sbm.write_search_bundle(b, d, 'none')
    path = os.path.join(d, sbm.ARRAYS)
    data = bytearray(open(path, 'rb').read())
    data[0] ^= 1
    open(path, 'wb').write(bytes(data))
    with pytest.raises(sbm.SearchBundleError, match='content_hash'):
        sbm.load_search_bundle(d)


def test_an_unknown_major_version_is_refused(tmp_path):
    b, _ = golden.make('line_small')
    m = b.manifest()
    m['version'] = '2.0'
    with pytest.raises(sbm.SearchBundleError, match='major version 2'):
        sbm.parse_manifest(json.dumps(m).encode())


def test_a_sketch_may_not_carry_a_recording():
    b, _ = golden.make('line_small')
    b.runs[0].timeline = []
    with pytest.raises(sbm.SearchBundleError):
        b.validate()


def test_a_recording_needs_a_time_per_event():
    b, _ = golden.make('arena_recorded_gz')
    b.runs[0].t = b.runs[0].t[:-1]
    with pytest.raises(sbm.SearchBundleError):
        b.validate()


def test_the_learner_and_the_policy_share_one_problem():
    """Rule 6: comparisons hold inputs fixed -- one problem per bundle."""
    b, _ = golden.make('line_small')
    m = b.manifest()
    assert 'problem' in m and all('problem' not in r for r in m['runs'])
    assert {r.trace.summary['truth'] for r in b.runs} == {'r2'}


def test_the_format_document_matches_the_code():
    doc = open(os.path.join(HERE, '..', '..', 'docs', 'labs',
                            'SEARCH_FORMAT.md')).read()
    assert f'`{sbm.SCHEMA}`' in doc and f'`{sbm.VERSION}`' in doc
    assert f'`MAX_RUNS` = {sbm.MAX_RUNS}' in doc
    assert ', '.join(rs.KINDS) in doc
    for kind in sbm.KINDS:
        assert f'`{kind}`' in doc
    for col in sbm.INT_COLUMNS + ('cost', 'belief', 'candidates', 't'):
        assert f'`run.<id>.{col}`' in doc, col
    assert f'`{rs.SCHEMA}`' in doc
