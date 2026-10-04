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
Localisation bundle 1.0: written, read, refused and replayed.

The golden fixtures are what lab_web's decoder is tested against
(``lab_web/test/locdecode.test.ts``); here they must be byte-identical to
the writer and must replay. Every run in a bundle reads one world, so a
race is on identical inputs by construction -- tested on the bytes.
"""

import gzip
import json
import os
import shutil

from coco_lab import bundle, locbundle as LB
import golden_loc_bundles
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, 'fixtures', 'loc_bundles')


def files(d):
    return {n: open(os.path.join(d, n), 'rb').read()
            for n in sorted(os.listdir(d))}


@pytest.mark.parametrize('name', sorted(golden_loc_bundles.GOLDEN))
def test_golden_loc_bundles_are_byte_identical_to_the_writer(name,
                                                             tmp_path):
    b, compression = golden_loc_bundles.make(name)
    LB.write_loc_bundle(b, str(tmp_path / name), compression)
    committed = os.path.join(GOLDEN_DIR, name)
    assert os.path.isdir(committed), f'missing golden fixture {committed}'
    assert files(str(tmp_path / name)) == files(committed)


@pytest.mark.parametrize('name', sorted(golden_loc_bundles.GOLDEN))
def test_golden_loc_bundles_load_and_replay(name):
    b = LB.load_loc_bundle(os.path.join(GOLDEN_DIR, name))
    LB.replay_check(b)
    assert b.provenance['source_kind'] == 'sketch'


def test_the_golden_set_covers_what_the_decoder_needs():
    loaded = {n: LB.load_loc_bundle(os.path.join(GOLDEN_DIR, n))
              for n in golden_loc_bundles.GOLDEN}
    kinds = {tr.kind for b in loaded.values() for _, tr in b.runs}
    assert kinds == {'mcl', 'ekf'}
    comps = {json.load(open(os.path.join(GOLDEN_DIR, n, 'manifest.json')))
             ['encoding']['compression'] for n in loaded}
    assert comps == {'none', 'gzip'}
    assert any(b.world.kidnap_row is not None for b in loaded.values())
    assert any(len(b.runs) == 3 for b in loaded.values())


def test_every_run_reads_the_same_world():
    b = LB.load_loc_bundle(os.path.join(GOLDEN_DIR, 'kidnap_small_gz'))
    rows = {tuple(tr.columns['row']) for _, tr in b.runs}
    assert rows == {tuple(b.world.updates)}


def test_gzip_and_raw_have_one_content_hash(tmp_path):
    b, _ = golden_loc_bundles.make('twins_small')
    h1 = LB.write_loc_bundle(b, str(tmp_path / 'a'), 'none')
    h2 = LB.write_loc_bundle(b, str(tmp_path / 'b'), 'gzip')
    assert h1 == h2
    raw = open(tmp_path / 'a' / 'arrays.bin', 'rb').read()
    assert gzip.decompress(open(tmp_path / 'b' / 'arrays.bin.gz',
                                'rb').read()) == raw


def _copy(tmp_path, name='twins_small'):
    d = tmp_path / name
    shutil.copytree(os.path.join(GOLDEN_DIR, name), d)
    return d


def test_a_flipped_array_byte_is_refused(tmp_path):
    d = _copy(tmp_path)
    p = d / 'arrays.bin'
    data = bytearray(p.read_bytes())
    data[len(data) // 2] ^= 0x01
    p.write_bytes(bytes(data))
    with pytest.raises(LB.LocBundleError, match='content_hash'):
        LB.load_loc_bundle(str(d))


def test_an_edited_manifest_is_refused(tmp_path):
    d = _copy(tmp_path)
    m = json.loads((d / 'manifest.json').read_text())
    m['runs'][0]['summary']['mean_err_xy'] = 0.0
    (d / 'manifest.json').write_text(bundle.canonical_json(m))
    with pytest.raises(LB.LocBundleError, match='content_hash'):
        LB.load_loc_bundle(str(d))


def test_an_unknown_major_version_is_refused(tmp_path):
    d = _copy(tmp_path)
    m = json.loads((d / 'manifest.json').read_text())
    m['version'] = '2.0'
    (d / 'manifest.json').write_text(bundle.canonical_json(m))
    with pytest.raises(LB.LocBundleError, match='major version 2'):
        LB.load_loc_bundle(str(d))


def test_a_search_bundle_is_not_a_loc_bundle():
    path = os.path.join(HERE, 'fixtures', 'bundles', 'astar_open')
    with pytest.raises(LB.LocBundleError, match='schema'):
        LB.load_loc_bundle(path)


def test_non_contiguous_arrays_are_refused(tmp_path):
    d = _copy(tmp_path)
    m = json.loads((d / 'manifest.json').read_text())
    m['arrays'][1]['offset'] += 8
    with pytest.raises(LB.LocBundleError, match='contiguous'):
        LB.parse_manifest(bundle.canonical_json(m).encode())


def test_a_replay_that_differs_is_refused():
    b = LB.load_loc_bundle(os.path.join(GOLDEN_DIR, 'twins_small'))
    b.world.scenario.seed += 1  # a different world from the same scenario
    with pytest.raises(LB.LocBundleError, match='replay'):
        LB.replay_check(b)


def test_a_bundle_needs_one_to_four_unique_runs():
    b, _ = golden_loc_bundles.make('kidnap_small_gz')
    b.runs = b.runs + [b.runs[0]]
    with pytest.raises(LB.LocBundleError, match='unique'):
        b.validate()
    b.runs = []
    with pytest.raises(LB.LocBundleError, match='runs'):
        b.validate()


def test_the_doc_matches_the_implementation():
    """docs/labs/LOC_FORMAT.md is normative; pin its names to the code."""
    from coco_lab import localise as L
    doc = open(os.path.join(HERE, '..', '..', 'docs', 'labs',
                            'LOC_FORMAT.md'), encoding='utf-8').read()
    for name in (L.SCHEMA, LB.SCHEMA, f'"{L.VERSION}"', f'"{LB.VERSION}"'):
        assert name in doc, name
    for name in L.COMMON_COLUMNS + L.FILTER_COLUMNS['mcl'] + \
            L.FILTER_COLUMNS['ekf'] + L.PARTICLE_COLUMNS:
        assert f'`{name}`' in doc or f'`{name},' in doc or \
            f'{name}`' in doc, name
    for name in LB.WORLD_COLUMNS:
        assert f'world.{name}' in doc, name
    for key in ('n_updates', 'mean_err_xy', 'max_err_xy', 'final_err_xy',
                'final_err_yaw', 'converged_s', 'kidnap_s', 'recovered',
                'recovery_s'):
        assert f'`{key}`' in doc, key
    assert f'`ok_xy` {L.OK_XY}' in doc and f'`ok_yaw` {L.OK_YAW}' in doc
    assert f'`ok_hold` {L.OK_HOLD}' in doc


def test_unexpected_arrays_are_refused(tmp_path):
    b, _ = golden_loc_bundles.make('twins_small')
    arrays = b.arrays() + [('extra.thing', 'u8', b'\x00')]
    m = b.manifest('none')
    m['arrays'].append({'name': 'extra.thing', 'dtype': 'u8', 'count': 1,
                        'offset': sum(len(d) for _, _, d in b.arrays()),
                        'byte_length': 1})
    raw = b''.join(d for _, _, d in arrays)
    m['content_hash'] = bundle.content_hash(m, raw)
    with pytest.raises(LB.LocBundleError, match='unexpected'):
        LB.decode(m, raw)
