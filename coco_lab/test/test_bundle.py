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

"""Bundle format v1: round trips, integrity, hostile input and replay."""

import gzip
import json
import os
import re
import struct

from coco_lab import bundle
from coco_lab.bundle import Bundle, BundleError
from coco_lab.maps import LabMap
from coco_lab.search import search
import golden_bundles
from hypothesis import given, settings
from lab_maps import cases
import pytest

HERE = os.path.dirname(__file__)
GOLDEN_DIR = os.path.join(HERE, 'fixtures', 'bundles')
DOC = os.path.join(HERE, '..', '..', 'docs', 'labs', 'BUNDLE_FORMAT.md')


def written(tmp_path, name='astar_open', compression=None):
    b, comp = golden_bundles.make(name)
    return bundle.write_bundle(b, str(tmp_path / name),
                               compression or comp), b


def files(path):
    return {n: open(os.path.join(path, n), 'rb').read()
            for n in sorted(os.listdir(path))}


def rewrite(path, manifest_fn=None, raw_fn=None, rehash=True):
    """Tamper with a written bundle; re-sign it unless ``rehash`` is off."""
    with open(os.path.join(path, bundle.MANIFEST), 'rb') as f:
        manifest = json.loads(f.read())
    name = bundle.ARRAYS_GZ if manifest['encoding']['compression'] == \
        'gzip' else bundle.ARRAYS
    with open(os.path.join(path, name), 'rb') as f:
        raw = f.read()
    if name == bundle.ARRAYS_GZ:
        raw = gzip.decompress(raw)
    if manifest_fn:
        manifest_fn(manifest)
    if raw_fn:
        raw = raw_fn(raw)
    if rehash:
        manifest['content_hash'] = bundle.content_hash(manifest, raw)
    with open(os.path.join(path, bundle.MANIFEST), 'w') as f:
        f.write(bundle.canonical_json(manifest))
    with open(os.path.join(path, name), 'wb') as f:
        f.write(gzip.compress(raw, mtime=0) if name == bundle.ARRAYS_GZ
                else raw)


def event_offset(manifest, column, index):
    a = next(a for a in manifest['arrays']
             if a['name'] == f'trace.{column}')
    return a['offset'] + index * bundle.DTYPES[a['dtype']][1]


# -- the golden set ------------------------------------------------------------

@pytest.mark.parametrize('name', sorted(golden_bundles.GOLDEN))
def test_golden_bundles_are_byte_identical_to_the_writer(name, tmp_path):
    b, compression = golden_bundles.make(name)
    fresh = bundle.write_bundle(b, str(tmp_path / name), compression)
    committed = os.path.join(GOLDEN_DIR, name)
    assert os.path.isdir(committed), f'missing golden fixture {committed}'
    assert files(fresh) == files(committed)


@pytest.mark.parametrize('name', sorted(golden_bundles.GOLDEN))
def test_golden_bundles_load_validate_and_replay(name):
    b = bundle.load_bundle(os.path.join(GOLDEN_DIR, name))
    original, _ = golden_bundles.make(name)
    assert b.trace == original.trace and b.lab_map == original.lab_map
    assert b.run == original.run and b.provenance == original.provenance
    r = bundle.replay(b)
    assert r.reproduced, r.detail


def test_the_golden_set_covers_what_1d_needs():
    kinds = {golden_bundles.GOLDEN[n][4] for n in golden_bundles.GOLDEN}
    assert kinds == {'none', 'gzip'}
    loaded = [bundle.load_bundle(os.path.join(GOLDEN_DIR, n))
              for n in golden_bundles.GOLDEN]
    assert {b.trace.summary['status'] for b in loaded} == {'found',
                                                           'no_path'}
    assert any(b.lab_map.cost is not None for b in loaded)
    assert any(b.run['weight'] is not None for b in loaded)


# -- round trips and stability --------------------------------------------------

def test_writing_twice_gives_identical_bytes(tmp_path):
    a, _ = written(tmp_path / 'a')
    b, _ = written(tmp_path / 'b')
    assert files(a) == files(b)


def test_the_content_hash_ignores_time_and_compression_only(tmp_path):
    b, _ = golden_bundles.make('astar_open')
    h = b.manifest()['content_hash']
    assert b.manifest('gzip')['content_hash'] == h
    later = Bundle(dict(b.provenance, created_utc='2030-01-01T00:00:00Z'),
                   b.run, b.lab_map, b.trace)
    assert later.manifest()['content_hash'] == h
    seeded = Bundle(dict(b.provenance, seed=7), b.run, b.lab_map, b.trace)
    assert seeded.manifest()['content_hash'] != h


def test_a_no_path_run_carries_no_path(tmp_path):
    path, b = written(tmp_path, 'bfs_no_path')
    back = bundle.load_bundle(path)
    assert back.trace.summary['status'] == 'no_path'
    assert back.trace.summary['path_cost'] is None
    assert back.trace.cells('path') == []


def grid_case_to_bundle(case):
    grid = case.grid
    occ = bytes(1 if grid.is_blocked((r, c)) else 0
                for r in range(grid.height) for c in range(grid.width))
    layer = grid.describe()['cost_layer']
    cost = [grid.cost_at((r, c)) for r in range(grid.height)
            for c in range(grid.width)] if layer else None
    m = LabMap(grid.width, grid.height, occ, cost, map_id='case')
    d = grid.describe()
    model = {k: d[k] for k in ('connectivity', 'diagonal_cost',
                               'corner_cutting', 'cost_weight',
                               'cost_scale')}
    return m, model


@settings(max_examples=150, derandomize=True, database=None, deadline=None)
@given(cases())
def test_round_trip_and_replay_property(case):
    m, model = grid_case_to_bundle(case)
    graph = m.to_grid(**model)
    for algorithm, heuristic, weight in (('astar', 'octile', None),
                                         ('bfs', 'zero', None),
                                         ('weighted_astar', 'euclidean',
                                          1.5)):
        r = search(graph, case.start, case.goal, algorithm, heuristic,
                   weight=weight)
        b = Bundle.from_run(r, m, {'start': case.start, 'goal': case.goal,
                                   'model': model},
                            golden_bundles.FIXED_PROVENANCE)
        manifest = b.manifest()
        raw = b''.join(d for _, _, d in b.arrays())
        back = bundle.decode(bundle.parse_manifest(
            bundle.canonical_json(manifest).encode()), raw)
        assert back.trace == b.trace and back.lab_map == b.lab_map
        assert bundle.replay(back).reproduced


# -- writing is confined ---------------------------------------------------------

def test_write_creates_only_the_two_files_and_never_overwrites(tmp_path):
    path, b = written(tmp_path / 'deep' / 'er')
    assert sorted(os.listdir(path)) == ['arrays.bin', 'manifest.json']
    with pytest.raises(BundleError, match='already holds'):
        bundle.write_bundle(b, path)
    gz, _ = written(tmp_path / 'gz', compression='gzip')
    assert sorted(os.listdir(gz)) == ['arrays.bin.gz', 'manifest.json']


def test_the_manifest_names_no_file():
    b, _ = golden_bundles.make('astar_open')
    text = bundle.canonical_json(b.manifest())
    assert 'arrays.bin' not in text and '/' not in json.dumps(
        b.manifest()['arrays'])


# -- hostile and broken input ------------------------------------------------------

def _drop(key):
    return lambda m: m.pop(key)


@pytest.mark.parametrize('fn,match', [
    (_drop('run'), 'manifest.run'),
    (_drop('arrays'), 'manifest.arrays'),
    (lambda m: m.update(schema='x'), 'schema'),
    (lambda m: m.update(version='2.0'), 'major version 2'),
    (lambda m: m.update(version='v1'), 'bad bundle version'),
    (lambda m: m.update(trace=[]), 'manifest.trace'),
    (lambda m: m['encoding'].update(byte_order='big'), 'byte_order'),
    (lambda m: m['encoding'].update(compression='zstd'), 'compression'),
    (lambda m: m['arrays'][1].update(offset=0), 'contiguous'),
    (lambda m: m['arrays'][1].update(byte_length=3), 'byte_length'),
    (lambda m: m['arrays'][0].update(dtype='f16'), 'bad array entry'),
    (lambda m: m['arrays'][0].update(count=-1), 'count'),
    (lambda m: m['arrays'].reverse(), 'offset|exactly'),
    (lambda m: m['arrays'][0].update(dtype='i32', byte_length=4 * m[
        'arrays'][0]['count']), 'offset|dtype'),
    (lambda m: m['provenance'].update(source_kind='guess'), 'source_kind'),
    (lambda m: m['provenance'].update(git_commit='abc'), 'git_commit'),
    (lambda m: m['provenance'].update(git_commit='a' * 40), 'both known'),
    (lambda m: m['provenance'].update(created_utc='yesterday'),
     'created_utc'),
    (lambda m: m['provenance'].update(rosbag={'sha256': 'x'}),
     'only for a recorded-run'),
    (lambda m: m['provenance'].update(source_kind='recorded-run'),
     'needs provenance.rosbag'),
    (lambda m: m['provenance'].update(seed='7'), 'seed'),
    (lambda m: m['run'].update(algorithm='dfs'), 'algorithm'),
    (lambda m: m['run'].update(weight=2.0), 'weight'),
    (lambda m: m['run'].update(tie_break='random'), 'tie_break'),
    (lambda m: m['run'].update(start=[0]), r'run\.start'),
    (lambda m: m['run']['model'].update(teleport=True), 'unknown keys'),
    (lambda m: m['run']['graph'].update(kind='hex'), 'graph.kind'),
    (lambda m: m['run'].update(heuristic='manhattan'), 'disagrees'),
    (lambda m: m['run'].update(map_hash='sha256:' + '0' * 64), 'map_hash'),
    (lambda m: m['map'].update(content_hash='sha256:' + '0' * 64),
     'map.content_hash'),
    (lambda m: m['map'].update(width=21), 'map|cells'),
    (lambda m: m['run'].update(start=[0, 40]), 'outside the map'),
    (lambda m: m['run']['model'].update(connectivity=4),
     'rebuilt graph|disagrees'),
    (lambda m: m['trace']['summary'].update(expansions=1), 'trace'),
    (lambda m: m['trace']['summary'].update(path_cost=1.0), 'path_cost'),
])
def test_malformed_manifests_are_refused(tmp_path, fn, match):
    path, _ = written(tmp_path)
    rewrite(path, manifest_fn=fn)
    with pytest.raises(BundleError, match=match):
        bundle.load_bundle(path)


def test_an_edited_map_is_refused(tmp_path):
    path, _ = written(tmp_path)
    m = json.load(open(os.path.join(path, bundle.MANIFEST)))
    occ = next(a for a in m['arrays'] if a['name'] == 'map.occupancy')
    i = occ['offset'] + 5
    rewrite(path, raw_fn=lambda raw: raw[:i] + b'\x01' + raw[i + 1:])
    with pytest.raises(BundleError, match='map.content_hash'):
        bundle.load_bundle(path)


def test_a_blocked_start_is_refused():
    # Hashes made consistent, so only the start check can refuse it.
    b, _ = golden_bundles.make('astar_open')
    occ = bytearray(b.lab_map.occupancy)
    r, c = b.run['start']
    occ[r * b.lab_map.width + c] = 1
    blocked = LabMap(b.lab_map.width, b.lab_map.height, bytes(occ), map_id=b.lab_map.id)
    bad = Bundle(b.provenance, dict(b.run, map_hash=blocked.content_hash()),
                 blocked, b.trace)
    with pytest.raises(BundleError, match='blocked'):
        bad.validate()


def test_the_content_hash_catches_one_flipped_bit(tmp_path):
    path, _ = written(tmp_path)
    rewrite(path, raw_fn=lambda raw: raw[:-1] + bytes([raw[-1] ^ 1]),
            rehash=False)
    with pytest.raises(BundleError, match='content_hash'):
        bundle.load_bundle(path)


@pytest.mark.parametrize('raw_fn,match', [
    (lambda raw: raw[:-5], 'truncated'),
    (lambda raw: raw + b'\x00' * 8, 'truncated or padded'),
])
def test_truncated_and_padded_arrays_are_refused(tmp_path, raw_fn, match):
    path, _ = written(tmp_path)
    rewrite(path, raw_fn=raw_fn, rehash=False)
    with pytest.raises(BundleError, match=match):
        bundle.load_bundle(path)


def test_a_non_finite_cost_value_is_refused(tmp_path):
    path, _ = written(tmp_path)
    m = json.load(open(os.path.join(path, bundle.MANIFEST)))
    i = event_offset(m, 'g', 0)
    rewrite(path, raw_fn=lambda raw: raw[:i] + struct.pack('<d', float(
        'nan')) + raw[i + 8:])
    with pytest.raises(BundleError, match='non-finite'):
        bundle.load_bundle(path)


def test_an_off_grid_event_is_refused(tmp_path):
    path, _ = written(tmp_path)
    m = json.load(open(os.path.join(path, bundle.MANIFEST)))
    i = event_offset(m, 'row', 3)
    rewrite(path, raw_fn=lambda raw: raw[:i] + struct.pack('<i', 999)
            + raw[i + 4:])
    with pytest.raises(BundleError, match='outside the map'):
        bundle.load_bundle(path)


def test_an_impossible_transition_is_refused(tmp_path):
    # Make event 1 (an expand of the start... ) name a never-pushed state.
    b, _ = golden_bundles.make('astar_open')
    ev = {k: list(v) for k, v in b.trace.events.items()}
    k = ev['kind'].index(1, 1)  # the second expand
    ev['row'][k] = (ev['row'][k] + 5) % 20
    bad = Bundle(b.provenance, b.run, b.lab_map,
                 type(b.trace)(b.trace.header, ev, b.trace.summary))
    with pytest.raises(BundleError, match='never pushed|closed|parent'):
        bad.validate()


def test_a_broken_path_is_refused():
    b, _ = golden_bundles.make('astar_open')
    ev = {k: list(v) for k, v in b.trace.events.items()}
    k = len(ev['kind']) - 3  # a path event in the middle
    assert ev['kind'][k] == 3
    ev['col'][k] = (ev['col'][k] + 7) % 20
    bad = Bundle(b.provenance, b.run, b.lab_map,
                 type(b.trace)(b.trace.header, ev, b.trace.summary))
    with pytest.raises(BundleError, match='path'):
        bad.validate()


def test_a_gzip_bomb_stops_at_the_declared_size(tmp_path):
    path, _ = written(tmp_path, compression='gzip')
    bomb = gzip.compress(b'\x00' * (64 * 1024 * 1024), mtime=0)
    with open(os.path.join(path, bundle.ARRAYS_GZ), 'wb') as f:
        f.write(bomb)
    with pytest.raises(BundleError, match='truncated or padded'):
        bundle.load_bundle(path)


def test_corrupt_gzip_and_missing_files_are_refused(tmp_path):
    path, _ = written(tmp_path, compression='gzip')
    with open(os.path.join(path, bundle.ARRAYS_GZ), 'wb') as f:
        f.write(b'not gzip at all')
    with pytest.raises(BundleError, match='cannot read'):
        bundle.load_bundle(path)
    with pytest.raises(BundleError, match='cannot read'):
        bundle.load_bundle(str(tmp_path / 'nothing'))


@pytest.mark.parametrize('text,match', [
    (b'{', 'not JSON'),
    (b'\xff\xfe', 'not JSON'),
    (b'[]', 'object'),
    (b'[' * 100000 + b']' * 100000, 'not JSON|deeper'),
    (b'{"a":' + b'[' * 40 + b'1' + b']' * 40 + b'}', 'deeper'),
])
def test_unparseable_manifests_are_refused(tmp_path, text, match):
    path, _ = written(tmp_path)
    with open(os.path.join(path, bundle.MANIFEST), 'wb') as f:
        f.write(text)
    with pytest.raises(BundleError, match=match):
        bundle.load_bundle(path)


def test_an_oversized_manifest_is_refused_before_parsing(tmp_path):
    path, _ = written(tmp_path)
    with open(os.path.join(path, bundle.MANIFEST), 'wb') as f:
        f.write(b' ' * (bundle.MAX_MANIFEST_BYTES + 10))
    with pytest.raises(BundleError, match='exceeds'):
        bundle.load_bundle(path)


def test_an_oversized_array_table_is_refused_before_reading(tmp_path):
    path, _ = written(tmp_path)

    def huge(m):
        last = m['arrays'][-1]
        last['count'] = last['byte_length'] = bundle.MAX_ARRAY_BYTES + 1
    rewrite(path, manifest_fn=huge, rehash=False)
    with pytest.raises(BundleError, match='over'):
        bundle.load_bundle(path)


def test_minor_versions_and_unknown_fields_are_accepted(tmp_path):
    path, _ = written(tmp_path)

    def newer(m):
        m['version'] = '1.9'
        m['future'] = {'x': [1, 2]}
        m['provenance']['operator'] = 'someone'
    rewrite(path, manifest_fn=newer)
    assert bundle.load_bundle(path).trace.summary['status'] == 'found'


# -- provenance ------------------------------------------------------------------

def test_make_provenance_and_git():
    p = bundle.make_provenance('glass-box', seed=3)
    assert p['coco_lab_version'] and p['created_utc'].endswith('Z')
    assert p['git_commit'] is None and p['git_dirty'] is None
    g = bundle.git_provenance(HERE)
    if g is not None:
        assert len(g['commit']) == 40 and isinstance(g['dirty'], bool)
        p = bundle.make_provenance('glass-box', git=g)
        assert p['git_commit'] == g['commit']
    assert bundle.git_provenance('/nonexistent/path') is None
    rec = bundle.make_provenance(
        'recorded-run', rosbag={'sha256': 'a' * 64, 'sim_time_start': 1.0,
                                'sim_time_end': 2.0})
    assert rec['rosbag']['sim_time_end'] == 2.0
    with pytest.raises(BundleError, match='sim_time'):
        bundle.make_provenance('recorded-run', rosbag={
            'sha256': 'a' * 64, 'sim_time_start': 2.0, 'sim_time_end': 1.0})


# -- replay ----------------------------------------------------------------------

def test_replay_detects_a_changed_input():
    b, _ = golden_bundles.make('astar_open')
    # Claim the other tie-break: the trace is still well-formed, but it is
    # not what that input produces, and replay must say where.
    header = dict(b.trace.header, tie_break='fifo')
    trace = type(b.trace)(header, b.trace.events, b.trace.summary)
    claimed = Bundle(b.provenance, dict(b.run, tie_break='fifo'), b.lab_map,
                     trace)
    claimed.validate()
    r = bundle.replay(claimed)
    assert not r.reproduced and r.first_divergence is not None


def test_replay_refuses_what_it_cannot_reproduce():
    b, _ = golden_bundles.make('astar_open')
    rec = Bundle(dict(b.provenance, source_kind='sketch'), b.run, b.lab_map,
                 b.trace)
    with pytest.raises(BundleError, match='only glass-box'):
        bundle.replay(rec)


# -- the document ------------------------------------------------------------------

def test_the_doc_matches_the_implementation():
    with open(DOC) as f:
        doc = f.read()
    assert f'`{bundle.SCHEMA}`' in doc and f'"{bundle.VERSION}"' in doc
    for name in (bundle.MANIFEST, bundle.ARRAYS, bundle.ARRAYS_GZ):
        assert f'`{name}`' in doc
    for kind in bundle.SOURCE_KINDS:
        assert f'`{kind}`' in doc
    for dtype in bundle.DTYPES:
        assert f'`{dtype}`' in doc
    for column, dtype in bundle.TRACE_DTYPES.items():
        assert re.search(rf'`trace\.{column}`[^\n]*`{dtype}`', doc), column
    for name, dtype in bundle.MAP_ARRAYS.items():
        assert re.search(rf'`{re.escape(name)}`[^\n]*`{dtype}`', doc), name
    for field in ('provenance', 'run', 'map', 'trace', 'arrays', 'encoding',
                  'content_hash', 'git_commit', 'git_dirty', 'created_utc',
                  'seed', 'episode_spec_hash', 'rosbag', 'map_hash',
                  'model'):
        assert f'`{field}`' in doc, field
    for kind, keys in bundle.MODEL_KEYS.items():
        for key in keys:
            assert f'`{key}`' in doc, key
    assert '1 MiB' in doc and '256 MiB' in doc and '50,000,000' in doc
