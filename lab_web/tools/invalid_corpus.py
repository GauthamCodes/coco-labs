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
The invalid-bundle corpus: tampered copies of golden fixtures.

Each case is a bundle directory under ``test/invalid/<name>/`` plus an
entry in ``test/invalid/index.json``:

``code``
    The ``BundleError`` code the TypeScript decoder must raise, or
    ``null`` when the TS decoder is *meant* to decode it (below).
``python``
    ``refuses`` -- ``coco_lab.bundle.load_bundle`` must raise, with a
    message matching ``match``; or ``accepts`` -- the one documented case
    where TS is stricter than Python (duplicate JSON keys).
``tier``
    ``structural`` -- both sides refuse. ``semantic`` -- only Python can
    refuse it: the check needs the graph's neighbour and cost functions,
    which TS must not re-implement (CLAUDE.md rule 8). The TS decoder
    decodes such a bundle, and the catalog gate refuses to draw it because
    its content hash is not one ``coco_lab`` validated
    (``catalog_mismatch``).

Tampering follows ``coco_lab/test/test_bundle.py``'s ``rewrite``: the
manifest is re-signed (``content_hash`` recomputed) unless the case is
about the hash itself, so each case reaches the check it names.

Two cases are too large to commit and are ``generated`` by both test
suites instead: an oversized manifest.
"""

import gzip
import json
import math
import os
import struct

from coco_lab import bundle

import common

MAX = bundle.MAX_MANIFEST_BYTES


def _load(base):
    path = os.path.join(common.GOLDEN_DIR, base)
    mtext, aname, _, raw = common.read_files(path)
    return json.loads(mtext), aname, raw


def _offset(manifest, name):
    return next(a for a in manifest['arrays'] if a['name'] == name)


def _set_f64(raw, manifest, name, index, value):
    a = _offset(manifest, name)
    off = a['offset'] + 8 * index
    return raw[:off] + struct.pack('<d', value) + raw[off + 8:]


def _set_i32(raw, manifest, name, index, value):
    a = _offset(manifest, name)
    off = a['offset'] + 4 * index
    return raw[:off] + struct.pack('<i', value) + raw[off + 4:]


class Case:
    """One invalid bundle and what each side must say about it."""

    def __init__(self, name, base, note, code, match, *, python='refuses',
                 tier='structural', manifest_fn=None, raw_fn=None,
                 rehash=True, text_fn=None, file_fn=None):
        self.name, self.base, self.note = name, base, note
        self.code, self.match = code, match
        self.python, self.tier = python, tier
        self.manifest_fn, self.raw_fn, self.rehash = (manifest_fn, raw_fn,
                                                      rehash)
        self.text_fn, self.file_fn = text_fn, file_fn

    def write(self, root):
        manifest, aname, raw = _load(self.base)
        if self.manifest_fn:
            self.manifest_fn(manifest)
        if self.raw_fn:
            raw = self.raw_fn(raw, manifest)
        if self.rehash:
            manifest['content_hash'] = bundle.content_hash(manifest, raw)
        text = bundle.canonical_json(manifest).encode('utf-8')
        if self.text_fn:
            text = self.text_fn(text)
        data = gzip.compress(raw, compresslevel=9, mtime=0) \
            if aname.endswith('.gz') else raw
        if self.file_fn:
            data = self.file_fn(data)
        d = os.path.join(root, self.name)
        os.makedirs(d)
        with open(os.path.join(d, 'manifest.json'), 'wb') as f:
            f.write(text)
        with open(os.path.join(d, aname), 'wb') as f:
            f.write(data)

    def index(self):
        return {'base': self.base, 'note': self.note, 'code': self.code,
                'match': self.match, 'python': self.python,
                'tier': self.tier}


def _upd(path, **kw):
    def fn(m):
        target = m
        for key in path:
            target = target[key]
        target.update(kw)
    return fn


def _drop(key):
    return lambda m: m.pop(key)


def _reverse_arrays(m):
    m['arrays'].reverse()


def _occ_hash_off(m):
    m['map']['content_hash'] = 'sha256:' + '0' * 64


def _huge_table(m):
    last = m['arrays'][-1]
    last['count'] = last['byte_length'] = bundle.MAX_ARRAY_BYTES + 1


def _cost_as_i32(m):
    a = _offset(m, 'map.cost')
    a['dtype'] = 'i32'
    a['count'] = a['count'] * 2


def _extra_array(m):
    m['arrays'].append({'name': 'trace.extra', 'dtype': 'u8', 'count': 1,
                        'offset': sum(a['byte_length'] for a in m['arrays']),
                        'byte_length': 1})


def _drop_last_array(m):
    m['arrays'].pop()


def _deep(text):
    return b'{"a":' + b'[' * 40 + b'1' + b']' * 40 + b'}'


def _dup_key(text):
    # the same key twice in provenance with the same value: Python keeps
    # the last and accepts; TS refuses duplicate keys outright.
    return text.replace(b'"provenance":{', b'"provenance":{"seed":null,', 1)


def _nan_literal(text):
    if b'"meta":{}' in text:
        return text.replace(b'"meta":{}', b'"meta":{"x":NaN}', 1)
    return text.replace(b'"meta":{', b'"meta":{"x":NaN,', 1)


def _bom(text):
    return b'\xef\xbb\xbf' + text


def _gt_count(m):
    m['recording']['groups']['gt']['count'] = 2


def _both(m):
    m['recording']['missing'] = ['cmd', 'gt']


def _to_glass_box(m):
    m['provenance']['source_kind'] = 'glass-box'
    m['provenance']['rosbag'] = None


def _version(v):
    return lambda m: m.update(version=v)


def _t_backwards(raw, m):
    return _set_f64(raw, m, 'recording.gt.t', 1, 9.0)


def _nan_g(raw, m):
    return _set_f64(raw, m, 'trace.g', 3, math.nan)


def _row_off_map(raw, m):
    return _set_i32(raw, m, 'trace.row', 2, 99)


def _flip(raw, m):
    b = bytearray(raw)
    b[len(b) // 2] ^= 0x01
    return bytes(b)


def _swap_path_col(raw, m):
    # move one mid-path event one column over: still in bounds, still a
    # well-formed trace, but no longer a neighbour step -- a SEMANTIC fault
    kinds = raw[_offset(m, 'trace.kind')['offset']:][:_offset(
        m, 'trace.kind')['count']]
    path = [i for i, k in enumerate(kinds) if k == 3]
    i = path[len(path) // 2]
    a = _offset(m, 'trace.col')
    col = struct.unpack_from('<i', raw, a['offset'] + 4 * i)[0]
    moved = col + 3 if col + 3 < m['map']['width'] else col - 3
    return _set_i32(raw, m, 'trace.col', i, moved)


CASES = [
    # -- JSON / parse --------------------------------------------------------
    Case('not_json', 'astar_open', 'manifest is not JSON', 'json',
         'not JSON', text_fn=lambda t: b'{'),
    Case('not_utf8', 'astar_open', 'manifest is not UTF-8', 'json',
         'not JSON', text_fn=lambda t: b'\xff\xfe'),
    Case('bom', 'astar_open', 'a UTF-8 byte-order mark before the JSON',
         'json', 'not JSON', text_fn=_bom),
    Case('not_object', 'astar_open', 'manifest is an array', 'structure',
         'object', text_fn=lambda t: b'[]'),
    Case('too_deep', 'astar_open', 'JSON nests 42 deep', 'bounds',
         'deeper', text_fn=_deep),
    Case('nan_literal', 'astar_open', 'a NaN literal in map.meta; Python '
         'parses it and then refuses to hash it', 'json',
         'Out of range float|not JSON compliant', text_fn=_nan_literal),
    Case('duplicate_key', 'astar_open', 'a key repeated with the same '
         'value; Python keeps the last and ACCEPTS (TS is stricter)',
         'json', None, python='accepts', text_fn=_dup_key),
    # -- schema and version --------------------------------------------------
    Case('schema', 'astar_open', 'schema is not coco_lab.bundle', 'schema',
         'schema', manifest_fn=lambda m: m.update(schema='x')),
    Case('major_2', 'astar_open', 'bundle version 2.0', 'version',
         'major version 2', manifest_fn=_version('2.0')),
    Case('bad_version', 'astar_open', 'bundle version "v1"', 'version',
         'bad bundle version', manifest_fn=_version('v1')),
    Case('recording_under_1_0', 'recorded_run_synthetic_1_1',
         'a recording in a bundle that says 1.0', 'recording', '1.1',
         manifest_fn=_version('1.0')),
    # -- structure -----------------------------------------------------------
    Case('no_run', 'astar_open', 'manifest.run missing', 'structure',
         'manifest.run', manifest_fn=_drop('run')),
    Case('trace_is_list', 'astar_open', 'manifest.trace is a list',
         'structure', 'manifest.trace',
         manifest_fn=lambda m: m.update(trace=[])),
    Case('big_endian', 'astar_open', 'encoding.byte_order big', 'structure',
         'byte_order', manifest_fn=_upd(('encoding',), byte_order='big')),
    Case('zstd', 'astar_open', 'encoding.compression zstd', 'structure',
         'compression', manifest_fn=_upd(('encoding',), compression='zstd')),
    # -- the array table -----------------------------------------------------
    Case('arrays_reversed', 'astar_open', 'array table in reverse order',
         'table', 'offset|contiguous', manifest_fn=_reverse_arrays),
    Case('bad_dtype_name', 'astar_open', 'dtype f16', 'table',
         'bad array entry', manifest_fn=lambda m: m['arrays'][0].update(
             dtype='f16')),
    Case('negative_count', 'astar_open', 'count -1', 'table', 'count',
         manifest_fn=lambda m: m['arrays'][0].update(count=-1)),
    Case('byte_length', 'astar_open', 'byte_length != count x size', 'table',
         'byte_length', manifest_fn=lambda m: m['arrays'][1].update(
             byte_length=3)),
    Case('extra_array', 'astar_open', 'an unknown array appended', 'table',
         'exactly', manifest_fn=_extra_array,
         raw_fn=lambda raw, m: raw + b'\x00'),
    Case('dropped_stream', 'recorded_run_synthetic_1_1',
         'the last recording array removed', 'table', 'exactly',
         manifest_fn=_drop_last_array,
         raw_fn=lambda raw, m: raw[:len(raw) - 24]),
    Case('huge_table', 'astar_open', 'arrays total over 256 MiB', 'bounds',
         'over', manifest_fn=_huge_table, rehash=False),
    Case('wrong_dtype', 'dijkstra_cost_field_gz', 'map.cost declared i32 '
         '(twice the count, same bytes)', 'dtype', 'dtype i32, expected f64',
         manifest_fn=_cost_as_i32),
    # -- lengths, compression, hash ------------------------------------------
    Case('truncated', 'astar_open', 'array data one byte short', 'length',
         'truncated or padded', raw_fn=lambda raw, m: raw[:-1],
         rehash=False),
    Case('padded', 'astar_open', 'array data one byte long', 'length',
         'truncated or padded', raw_fn=lambda raw, m: raw + b'\x00',
         rehash=False),
    Case('gzip_bomb', 'dijkstra_cost_field_gz', '64 MiB of zeros behind a '
         'small declared size', 'length', 'truncated or padded',
         file_fn=lambda d: gzip.compress(b'\x00' * (64 * 1024 * 1024),
                                         compresslevel=9, mtime=0),
         rehash=False),
    Case('gzip_claimed_raw', 'dijkstra_cost_field_gz', 'compression gzip '
         'but the file holds raw bytes (what a server that decoded '
         'Content-Encoding hands over)', 'compression', 'cannot read',
         file_fn=lambda d: gzip.decompress(d), rehash=False),
    Case('flipped_bit', 'astar_open', 'one array bit flipped, not re-signed',
         'hash', 'content_hash', raw_fn=_flip, rehash=False),
    Case('unsigned_edit', 'astar_open', 'provenance.seed edited, not '
         're-signed', 'hash', 'content_hash',
         manifest_fn=_upd(('provenance',), seed=7), rehash=False),
    # -- values --------------------------------------------------------------
    Case('nan_in_g', 'astar_open', 'a NaN in trace.g (re-signed)',
         'nonfinite', 'non-finite', raw_fn=_nan_g),
    Case('map_width', 'astar_open', 'map width 21 for 400 cells', 'map',
         'map', manifest_fn=_upd(('map',), width=21)),
    Case('map_hash', 'astar_open', 'map.content_hash wrong', 'map_hash',
         'map.content_hash', manifest_fn=_occ_hash_off),
    # -- provenance, run, trace ----------------------------------------------
    Case('source_kind', 'astar_open', 'source_kind "guess"', 'provenance',
         'source_kind', manifest_fn=_upd(('provenance',),
                                         source_kind='guess')),
    Case('git_commit', 'astar_open', 'git_commit "abc"', 'provenance',
         'git_commit', manifest_fn=_upd(('provenance',), git_commit='abc')),
    Case('recorded_without_bag', 'astar_open', 'recorded-run with no '
         'rosbag', 'provenance', 'needs provenance.rosbag',
         manifest_fn=_upd(('provenance',), source_kind='recorded-run')),
    Case('summary_expansions', 'astar_open', 'summary.expansions wrong',
         'trace_invariant', 'trace', manifest_fn=_upd(
             ('trace', 'summary'), expansions=1)),
    Case('run_algorithm', 'astar_open', 'run.algorithm "dfs"', 'run',
         'algorithm', manifest_fn=_upd(('run',), algorithm='dfs')),
    Case('run_weight', 'astar_open', 'a weight on A*', 'run', 'weight',
         manifest_fn=_upd(('run',), weight=2.0)),
    Case('run_model_key', 'astar_open', 'run.model has an unknown key',
         'run', 'unknown keys', manifest_fn=_upd(('run', 'model'),
                                                 teleport=True)),
    Case('run_header', 'astar_open', 'run.heuristic disagrees with the '
         'trace header', 'run_header', 'disagrees',
         manifest_fn=_upd(('run',), heuristic='manhattan')),
    Case('run_map_hash', 'astar_open', 'run.map_hash is not the map',
         'run_header', 'map_hash', manifest_fn=_upd(
             ('run',), map_hash='sha256:' + '0' * 64)),
    Case('event_off_map', 'astar_open', 'an event at row 99 of 20',
         'trace_invariant', 'outside the map', raw_fn=_row_off_map),
    # -- the 1.1 recording ---------------------------------------------------
    Case('recording_on_glass_box', 'recorded_run_synthetic_1_1',
         'a recording on a glass-box bundle', 'recording', 'recorded-run',
         manifest_fn=_to_glass_box),
    Case('group_present_and_missing', 'recorded_run_synthetic_1_1',
         'gt both present and missing', 'recording', 'exactly once',
         manifest_fn=_both),
    Case('group_count', 'recorded_run_synthetic_1_1', 'groups.gt.count 2 '
         'for 3 samples', 'recording', 'count', manifest_fn=_gt_count),
    Case('t_backwards', 'recorded_run_synthetic_1_1', 'gt.t decreases',
         'recording', 'decreases', raw_fn=_t_backwards),
    # -- semantic: only coco_lab can refuse these ----------------------------
    Case('path_not_neighbours', 'astar_open', 'a mid-path event moved 3 '
         'columns: well-formed, but not a neighbour step', None,
         'path|neighbour|parent', tier='semantic', raw_fn=_swap_path_col),
    Case('blocked_start', 'astar_open', 'the start cell marked occupied '
         '(map hash, run hash and content hash all re-signed)', None,
         'blocked|first push|map', tier='semantic', manifest_fn=None,
         raw_fn=None),
]

#: Too large to commit; each test suite builds these itself.
GENERATED = {
    'oversize_manifest': {
        'note': f'a manifest of {MAX + 10} spaces', 'code': 'bounds',
        'match': 'exceeds', 'python': 'refuses', 'tier': 'structural',
        'base': 'astar_open', 'bytes': MAX + 10},
}


def _blocked_start():
    """Mark astar_open's start occupied, re-signing every hash."""
    from coco_lab.maps import LabMap
    path = os.path.join(common.GOLDEN_DIR, 'astar_open')
    b = bundle.load_bundle(path)
    m = b.lab_map
    occ = bytearray(m.occupancy)
    r, c = b.run['start']
    occ[r * m.width + c] = 1
    return LabMap(m.width, m.height, bytes(occ), m.cost, map_id=m.id,
                  meta=m.meta)


def _fix_blocked(case):
    new_map = _blocked_start()

    def manifest_fn(m):
        m['map']['content_hash'] = new_map.content_hash()
        m['run']['map_hash'] = new_map.content_hash()

    def raw_fn(raw, m):
        a = _offset(m, 'map.occupancy')
        return (raw[:a['offset']] + new_map.occupancy
                + raw[a['offset'] + a['byte_length']:])
    case.manifest_fn, case.raw_fn = manifest_fn, raw_fn


_fix_blocked(next(c for c in CASES if c.name == 'blocked_start'))


def write(root: str) -> None:
    """Write every committed case and ``index.json`` under ``root``."""
    os.makedirs(root)
    index = {'generator': 'lab_web/tools/invalid_corpus.py', 'cases': {},
             'generated': GENERATED}
    for case in CASES:
        case.write(root)
        index['cases'][case.name] = case.index()
    with open(os.path.join(root, 'index.json'), 'w') as f:
        f.write(json.dumps(index, indent=1, sort_keys=True) + '\n')
