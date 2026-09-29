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
Bundle 1.1: the recorded-run streams (owner decision D-5, Phase 1C).

Additive and backward compatible: a bundle without a recording is still
written as 1.0, byte-for-byte (the five 1.0 golden fixtures are
re-derived by test_bundle.py and unchanged); a recording is refused on
anything but a recorded-run, and a stream that was not captured must be
listed as missing rather than zero-filled.
"""

import json
import math
import os

from coco_lab import bundle
from coco_lab.bundle import Bundle, BundleError
import golden_bundles
import pytest
from test_bundle import files, GOLDEN_DIR, rewrite

NAME = 'recorded_run_synthetic_1_1'


def recorded():
    return golden_bundles.make_recorded(NAME)[0]


def with_(b, recording=None, streams=None, provenance=None):
    return Bundle(provenance or b.provenance, b.run, b.lab_map, b.trace,
                  recording if recording is not None else b.recording,
                  streams if streams is not None else b.streams)


def test_the_recorded_golden_is_byte_identical_to_the_writer(tmp_path):
    b, compression = golden_bundles.make_recorded(NAME)
    fresh = bundle.write_bundle(b, str(tmp_path / NAME), compression)
    assert files(fresh) == files(os.path.join(GOLDEN_DIR, NAME))


def test_the_recorded_golden_loads_with_its_streams_and_is_1_1():
    b = bundle.load_bundle(os.path.join(GOLDEN_DIR, NAME))
    assert b == recorded()
    assert b.version == '1.1'
    with open(os.path.join(GOLDEN_DIR, NAME, bundle.MANIFEST)) as f:
        m = json.load(f)
    assert m['version'] == bundle.VERSION_RECORDED == '1.1'
    assert m['recording']['missing'] == ['cmd']
    names = [a['name'] for a in m['arrays']]
    assert names[-11:] == ['recording.gt.t', 'recording.gt.x',
                           'recording.gt.y', 'recording.gt.yaw',
                           'recording.amcl.t', 'recording.amcl.x',
                           'recording.amcl.y', 'recording.amcl.yaw',
                           'recording.plan.x', 'recording.plan.y',
                           'recording.plan.yaw']
    assert not any(n.startswith('recording.cmd') for n in names)


def test_a_recorded_run_is_still_not_replayable():
    with pytest.raises(BundleError, match='glass-box'):
        bundle.replay(recorded())


def test_without_a_recording_the_writer_still_writes_1_0():
    b, _ = golden_bundles.make('astar_open')
    assert b.version == '1.0' and b.manifest()['version'] == '1.0'
    assert 'recording' not in b.manifest()


def test_gzip_round_trip_and_the_hash_covers_the_streams(tmp_path):
    b = recorded()
    back = bundle.load_bundle(bundle.write_bundle(b, str(tmp_path / 'g'),
                                                  'gzip'))
    assert back == b
    h = b.manifest()['content_hash']
    s = json.loads(json.dumps(b.streams))
    s['gt']['x'][1] += 1e-9
    assert with_(b, streams=s).manifest()['content_hash'] != h


def bad_recordings():
    b = recorded()
    rec = json.loads(json.dumps(b.recording))
    st = json.loads(json.dumps(b.streams))
    out = []

    r = json.loads(json.dumps(rec))
    r['missing'] = []
    out.append(('a group neither present nor missing', r, st, None))
    r = json.loads(json.dumps(rec))
    r['missing'] = ['cmd', 'gt']
    out.append(('present and missing at once', r, st, None))
    r = json.loads(json.dumps(rec))
    r['groups']['odd'] = {'frame': 'map', 'source': '/x', 'count': 0}
    out.append(('unknown group', r, dict(st, odd={}), None))
    s = json.loads(json.dumps(st))
    s['gt']['t'] = [10.0, 9.0, 12.0]
    out.append(('time goes backwards', rec, s, None))
    s = json.loads(json.dumps(st))
    s['amcl']['x'] = [0.75]
    out.append(('column length differs from count', rec, s, None))
    s = json.loads(json.dumps(st))
    s['plan']['yaw'] = [0.0, math.nan, 0.0]
    out.append(('a NaN', rec, s, None))
    s = json.loads(json.dumps(st))
    del s['gt']['yaw']
    out.append(('a missing column', rec, s, None))
    r = json.loads(json.dumps(rec))
    del r['run_id']
    out.append(('a missing key', r, st, None))
    out.append(('on a glass-box bundle', rec, st,
                dict(b.provenance, source_kind='glass-box', rosbag=None)))
    return out


@pytest.mark.parametrize('why,rec,streams,prov', bad_recordings(),
                         ids=[c[0] for c in bad_recordings()])
def test_bad_recordings_are_refused(why, rec, streams, prov):
    b = with_(recorded(), rec, streams, prov)
    with pytest.raises(BundleError):
        b.validate()


def test_a_recording_under_version_1_0_is_refused(tmp_path):
    path = bundle.write_bundle(recorded(), str(tmp_path / 'r'))

    def older(m):
        m['version'] = '1.0'
    rewrite(path, manifest_fn=older)
    with pytest.raises(BundleError, match='1.1'):
        bundle.load_bundle(path)


def test_recording_arrays_without_the_block_are_refused(tmp_path):
    path = bundle.write_bundle(recorded(), str(tmp_path / 'r'))

    def drop(m):
        del m['recording']
    rewrite(path, manifest_fn=drop)
    with pytest.raises(BundleError, match='exactly'):
        bundle.load_bundle(path)


def test_a_dropped_stream_array_is_refused(tmp_path):
    path = bundle.write_bundle(recorded(), str(tmp_path / 'r'))
    cut = {}

    def drop(m):
        last = m['arrays'].pop()
        cut['n'] = last['byte_length']
    rewrite(path, manifest_fn=drop,
            raw_fn=lambda raw: raw[:len(raw) - 24])
    with pytest.raises(BundleError):
        bundle.load_bundle(path)
    assert cut['n'] == 24


def test_the_doc_describes_1_1():
    from test_bundle import DOC
    with open(DOC) as f:
        doc = f.read()
    assert f'"{bundle.VERSION_RECORDED}"' in doc
    assert '`recording`' in doc and NAME in doc
    for key in bundle.RECORDING_KEYS:
        assert f'`{key}`' in doc, key
    for group, cols in bundle.RECORDING_GROUPS.items():
        line = next(ln for ln in doc.splitlines()
                    if ln.startswith(f'| `{group}` |'))
        for c in cols:
            assert f'`recording.{group}.{c}`' in line, (group, c)
