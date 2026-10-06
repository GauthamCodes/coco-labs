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
Search bundle format 1.0: one search problem, and searches run on it.

The normative description is ``docs/labs/SEARCH_FORMAT.md``; this module
is its reference implementation. It follows bundle format v1's rules
exactly (``coco_lab.bundle``) and Lab 2's ``locbundle``: a directory
holding ``manifest.json`` and ``arrays.bin`` (or ``arrays.bin.gz``, gzip
mtime 0); canonical JSON; little-endian arrays at contiguous offsets; the
same content hash; every size bounded before allocation; refuse, never
repair.

What it holds:

- the :class:`~coco_lab.regionsearch.SearchProblem` -- regions, travel
  costs, detection, prior: everything the robot knows, identical for
  every run in the bundle by construction;
- one to :data:`MAX_RUNS` runs (:class:`~coco_lab.regionsearch.
  SearchTrace`), each either
  * ``sketch``: :func:`regionsearch.run_search` from a seed and a placed
    truth, or
  * ``recorded``: a real mission's looks, rebuilt by
    :func:`regionsearch.replay_search` -- the policy chooses again from
    the same belief, so a recording that disagrees is refused -- plus its
    FSM timeline and event times on the simulator clock.

A recorded run also carries an ``evaluator`` block: where the target
really stood, from the episode manifest, for the truth/belief display. It
is DATA ABOUT the run, never an input to it: :func:`replay_check`
rebuilds every recorded run from its looks alone and does not read it.
"""

from dataclasses import dataclass
import gzip
import json
import math
import os
import struct
from typing import Dict, List, Optional, Tuple

from . import bundle as _b
from . import regionsearch as rs

SCHEMA = 'coco_lab.search_bundle'
VERSION = '1.0'
MAJOR = 1
MANIFEST = _b.MANIFEST
ARRAYS = _b.ARRAYS
ARRAYS_GZ = _b.ARRAYS_GZ
DTYPES = _b.DTYPES

KINDS = ('sketch', 'recorded')
MAX_RUNS = 32
INT_COLUMNS = ('kind', 'region', 'outcome')
FLOAT_COLUMNS = ('cost',)
#: Recorded runs only: simulator seconds of each event (NaN if unknown).
TIME_COLUMN = 't'
MAX_TIMELINE = 4096


class SearchBundleError(ValueError):
    """A search bundle that does not conform, or fails a check."""


def _ok_id(i) -> bool:
    return isinstance(i, str) and 0 < len(i) <= 32 and \
        all(c.isalnum() or c in '_-' for c in i)


@dataclass
class SearchRun:
    """One run: its trace, and for a recording, what the robot logged."""

    id: str  # noqa: A003
    kind: str
    trace: rs.SearchTrace
    #: recorded only: per event, simulator seconds (NaN if not known)
    t: Optional[List[float]] = None
    #: recorded only: [[t, state, reason], ...] -- the FSM timeline
    timeline: Optional[List[list]] = None
    #: recorded only: provenance of the run (episode id, level, seed,
    #: colour, runner checks, mission outcome, evidence directory)
    record: Optional[Dict[str, object]] = None
    #: recorded only: where the target REALLY stood (manifest). Display
    #: data for the truth/belief toggle; never read by replay.
    evaluator: Optional[Dict[str, object]] = None

    def block(self) -> Dict[str, object]:
        """Return the manifest entry for this run."""
        out = {'id': self.id, 'kind': self.kind,
               'header': self.trace.header, 'summary': self.trace.summary,
               'n_events': self.trace.n_events}
        if self.kind == 'recorded':
            out['timeline'] = self.timeline or []
            out['record'] = self.record or {}
            out['evaluator'] = self.evaluator or {}
        return out


@dataclass
class SearchBundle:
    """A search problem and the runs on it."""

    provenance: Dict[str, object]
    problem: rs.SearchProblem
    runs: List[SearchRun]

    def validate(self) -> None:
        """Raise :class:`SearchBundleError` unless the bundle is consistent."""
        _b._check_provenance(self.provenance)
        try:
            self.problem.validate()
        except rs.SearchError as exc:
            raise SearchBundleError(f'problem: {exc}') from None
        if not 1 <= len(self.runs) <= MAX_RUNS:
            raise SearchBundleError(f'1..{MAX_RUNS} runs, not '
                                    f'{len(self.runs)}')
        ids = [r.id for r in self.runs]
        if len(set(ids)) != len(ids) or not all(_ok_id(i) for i in ids):
            raise SearchBundleError(f'run ids must be unique short words: '
                                    f'{ids}')
        n = self.problem.n
        for r in self.runs:
            if r.kind not in KINDS:
                raise SearchBundleError(f'run {r.id}: kind {r.kind!r}')
            try:
                r.trace.validate(n)
            except rs.SearchError as exc:
                raise SearchBundleError(f'run {r.id}: {exc}') from None
            if r.kind == 'recorded':
                if r.t is None or len(r.t) != r.trace.n_events:
                    raise SearchBundleError(f'run {r.id}: t must have one '
                                            f'value per event')
                if not isinstance(r.timeline, list) or \
                        len(r.timeline) > MAX_TIMELINE:
                    raise SearchBundleError(f'run {r.id}: bad timeline')
                for row in r.timeline:
                    if not (isinstance(row, list) and len(row) == 3
                            and isinstance(row[0], (int, float))
                            and isinstance(row[1], str)
                            and (row[2] is None or isinstance(row[2], str))):
                        raise SearchBundleError(f'run {r.id}: timeline row '
                                                f'{row!r}')
            elif r.t is not None or r.timeline is not None:
                raise SearchBundleError(f'run {r.id}: a sketch has no '
                                        f'recording')

    # -- serialisation -----------------------------------------------------

    def arrays(self) -> List[Tuple[str, str, bytes]]:
        """Return ``(name, dtype, little-endian bytes)`` in wire order."""
        def pack(dtype, values):
            code = DTYPES[dtype][0]
            return struct.pack(f'<{len(values)}{code}', *values)
        out = []
        for r in self.runs:
            tr = r.trace
            for name in INT_COLUMNS:
                out.append((f'run.{r.id}.{name}', 'i32',
                            pack('i32', getattr(tr, name))))
            out.append((f'run.{r.id}.cost', 'f64', pack('f64', tr.cost)))
            out.append((f'run.{r.id}.belief', 'f64', pack('f64', tr.belief)))
            out.append((f'run.{r.id}.candidates', 'f64',
                        pack('f64', tr.candidates)))
            if r.kind == 'recorded':
                out.append((f'run.{r.id}.t', 'f64', pack('f64', r.t)))
        return out

    def manifest(self, compression: str = 'none') -> Dict[str, object]:
        """Return the manifest dict, content hash included."""
        if compression not in ('none', 'gzip'):
            raise SearchBundleError('compression must be none or gzip')
        arrays = self.arrays()
        table, offset = [], 0
        for name, dtype, data in arrays:
            size = DTYPES[dtype][1]
            table.append({'name': name, 'dtype': dtype,
                          'count': len(data) // size, 'offset': offset,
                          'byte_length': len(data)})
            offset += len(data)
        manifest = {
            'schema': SCHEMA, 'version': VERSION,
            'provenance': dict(self.provenance),
            'problem': self.problem.to_dict(),
            'runs': [r.block() for r in self.runs],
            'arrays': table,
            'encoding': {'byte_order': 'little', 'compression': compression},
        }
        manifest = json.loads(_b.canonical_json(manifest))
        manifest['content_hash'] = _b.content_hash(
            manifest, b''.join(d for _, _, d in arrays))
        return manifest

    def to_bytes(self, compression: str = 'none') -> Tuple[bytes, str,
                                                           bytes, str]:
        """Return ``(manifest bytes, arrays file name, arrays file, hash)``."""
        manifest = self.manifest(compression)
        raw = b''.join(d for _, _, d in self.arrays())
        if compression == 'gzip':
            data, name = gzip.compress(raw, compresslevel=9, mtime=0), \
                ARRAYS_GZ
        else:
            data, name = raw, ARRAYS
        return (_b.canonical_json(manifest).encode('utf-8'), name, data,
                manifest['content_hash'])


def write_search_bundle(sb: SearchBundle, out_dir: str,
                        compression: str = 'gzip') -> str:
    """Write ``sb`` into ``out_dir`` (created); return the content hash."""
    sb.validate()
    os.makedirs(out_dir, exist_ok=True)
    mbytes, name, data, digest = sb.to_bytes(compression)
    with open(os.path.join(out_dir, MANIFEST), 'wb') as f:
        f.write(mbytes)
    with open(os.path.join(out_dir, name), 'wb') as f:
        f.write(data)
    return digest


# -- reading ------------------------------------------------------------------

def parse_manifest(text: bytes) -> Dict[str, object]:
    """Parse and structurally check a manifest; refuse an unknown MAJOR."""
    try:
        manifest = json.loads(text.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise SearchBundleError(f'manifest is not JSON: {exc}') from None
    if _b._depth(manifest) > _b.MAX_JSON_DEPTH:
        raise SearchBundleError(f'manifest nests deeper than '
                                f'{_b.MAX_JSON_DEPTH}')
    if not isinstance(manifest, dict):
        raise SearchBundleError('manifest must be an object')
    if manifest.get('schema') != SCHEMA:
        raise SearchBundleError(f'schema is {manifest.get("schema")!r}, '
                                f'not {SCHEMA!r}')
    try:
        major = int(str(manifest.get('version', '')).split('.')[0])
    except ValueError:
        raise SearchBundleError(f'bad version '
                                f'{manifest.get("version")!r}') from None
    if major != MAJOR:
        raise SearchBundleError(f'search bundle major version {major} is '
                                f'not supported (this reader speaks '
                                f'{MAJOR}.x)')
    for key, kind in (('provenance', dict), ('problem', dict),
                      ('runs', list), ('arrays', list), ('encoding', dict),
                      ('content_hash', str)):
        if not isinstance(manifest.get(key), kind):
            raise SearchBundleError(f'manifest.{key} must be a '
                                    f'{kind.__name__}')
    enc = manifest['encoding']
    if enc.get('byte_order') != 'little' or \
            enc.get('compression') not in ('none', 'gzip'):
        raise SearchBundleError('encoding must be little-endian, none or '
                                'gzip')
    offset = 0
    for a in manifest['arrays']:
        if not (isinstance(a, dict) and isinstance(a.get('name'), str)
                and a.get('dtype') in DTYPES):
            raise SearchBundleError(f'bad array entry {a!r}')
        for key in ('count', 'offset', 'byte_length'):
            v = a.get(key)
            if not (isinstance(v, int) and not isinstance(v, bool)
                    and v >= 0):
                raise SearchBundleError(f'array {a["name"]}: {key} must be '
                                        f'an int >= 0')
        if a['offset'] != offset:
            raise SearchBundleError(f'array {a["name"]}: not contiguous')
        if a['byte_length'] != a['count'] * DTYPES[a['dtype']][1]:
            raise SearchBundleError(f'array {a["name"]}: byte_length '
                                    f'disagrees with count x dtype')
        offset += a['byte_length']
    if offset > _b.MAX_ARRAY_BYTES:
        raise SearchBundleError(f'arrays total {offset} bytes')
    return manifest


def load_search_bundle(path: str) -> SearchBundle:
    """Read, bound, decode and validate the bundle directory at ``path``."""
    try:
        with open(os.path.join(path, MANIFEST), 'rb') as f:
            text = f.read(_b.MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise SearchBundleError(f'cannot read the manifest: {exc}') from None
    if len(text) > _b.MAX_MANIFEST_BYTES:
        raise SearchBundleError('manifest too large')
    manifest = parse_manifest(text)
    expected = sum(a['byte_length'] for a in manifest['arrays'])
    gz = manifest['encoding']['compression'] == 'gzip'
    try:
        with open(os.path.join(path, ARRAYS_GZ if gz else ARRAYS), 'rb') as f:
            raw = _b._bounded_gunzip(f, expected) if gz \
                else f.read(expected + 1)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise SearchBundleError(f'cannot read the arrays: {exc}') from None
    return decode(manifest, raw)


def decode(manifest: Dict[str, object], raw: bytes) -> SearchBundle:
    """Build and validate a bundle from a parsed manifest and array bytes."""
    if len(raw) != sum(a['byte_length'] for a in manifest['arrays']):
        raise SearchBundleError('array bytes do not match the table')
    if manifest['content_hash'] != _b.content_hash(manifest, raw):
        raise SearchBundleError('content_hash does not match the content')
    table = {a['name']: a for a in manifest['arrays']}
    if len(table) != len(manifest['arrays']):
        raise SearchBundleError('duplicate array name')
    used = set()

    def take(name, dtype):
        a = table.get(name)
        if a is None:
            raise SearchBundleError(f'missing array {name!r}')
        if a['dtype'] != dtype:
            raise SearchBundleError(f'array {name!r} must be {dtype}')
        used.add(name)
        code = DTYPES[dtype][0]
        return list(struct.unpack_from(f'<{a["count"]}{code}', raw,
                                       a['offset']))

    try:
        problem = rs.SearchProblem.from_dict(manifest['problem'])
    except rs.SearchError as exc:
        raise SearchBundleError(str(exc)) from None
    runs = []
    for r in manifest['runs']:
        if not isinstance(r, dict) or not isinstance(r.get('header'), dict):
            raise SearchBundleError('bad run entry')
        rid, kind = r.get('id'), r.get('kind')
        if not _ok_id(rid) or kind not in KINDS:
            raise SearchBundleError(f'bad run id/kind {rid!r} {kind!r}')
        cols = {c: take(f'run.{rid}.{c}', 'i32') for c in INT_COLUMNS}
        cost = take(f'run.{rid}.cost', 'f64')
        belief = take(f'run.{rid}.belief', 'f64')
        cands = take(f'run.{rid}.candidates', 'f64')
        if not all(math.isfinite(v) for v in cost + belief):
            raise SearchBundleError(f'run {rid}: cost and belief must be '
                                    f'finite')
        tr = rs.SearchTrace(dict(r['header']), cols['kind'], cols['region'],
                            cols['outcome'], cost, belief, cands,
                            dict(r.get('summary') or {}))
        if r.get('n_events') != tr.n_events:
            raise SearchBundleError(f'run {rid}: n_events disagrees')
        if kind == 'recorded':
            runs.append(SearchRun(
                rid, kind, tr, take(f'run.{rid}.t', 'f64'),
                [list(row) for row in r.get('timeline') or []],
                dict(r.get('record') or {}), dict(r.get('evaluator') or {})))
        else:
            runs.append(SearchRun(rid, kind, tr))
    extra = set(table) - used
    if extra:
        raise SearchBundleError(f'unexpected arrays {sorted(extra)}')
    sb = SearchBundle(dict(manifest['provenance']), problem, runs)
    try:
        sb.validate()
    except (rs.SearchError, ValueError) as exc:
        raise SearchBundleError(str(exc)) from None
    return sb


# -- replay ------------------------------------------------------------------------

def outcomes_of(trace: rs.SearchTrace, problem: rs.SearchProblem
                ) -> List[Tuple[str, bool]]:
    """Return a trace's looks as ``(region_id, found)``, in order."""
    return [(problem.ids[trace.region[e]], trace.outcome[e] == 1)
            for e in range(trace.n_events)
            if rs.KINDS[trace.kind[e]] == 'survey']


def rerun(problem: rs.SearchProblem, run: SearchRun) -> rs.SearchTrace:
    """Recompute one run with THIS coco_lab, from its recorded inputs."""
    h = run.trace.header
    given = tuple(problem.index(i) for i in h.get('given_order') or [])
    if run.kind == 'sketch':
        truth = run.trace.summary.get('truth')
        return rs.run_search(
            problem, h['policy'],
            None if truth is None else problem.index(truth),
            seed=h['seed'], true_detection=h.get('true_detection'),
            max_surveys=h.get('max_surveys'), given_order=given,
            passes=h.get('passes', 1))
    return rs.replay_search(problem, h['policy'],
                            outcomes_of(run.trace, problem), given)


def replay_check(sb: SearchBundle) -> None:
    """
    Recompute every run; refuse unless the bytes match.

    A sketch is simulated again from its seed and truth; a recording is
    rebuilt from its looks alone (the evaluator block is not read), and
    the policy must choose every region the robot chose.
    """
    def packed(tr):
        return [struct.pack(f'<{len(v)}{c}', *v) for v, c in (
            (tr.kind, 'i'), (tr.region, 'i'), (tr.outcome, 'i'),
            (tr.cost, 'd'), (tr.belief, 'd'), (tr.candidates, 'd'))]
    for run in sb.runs:
        try:
            again = rerun(sb.problem, run)
        except rs.SearchError as exc:
            raise SearchBundleError(f'replay: run {run.id}: {exc}') from None
        if packed(again) != packed(run.trace):
            raise SearchBundleError(f'replay: run {run.id} differs')
        if json.loads(_b.canonical_json(again.summary)) != \
                json.loads(_b.canonical_json(run.trace.summary)):
            raise SearchBundleError(f'replay: run {run.id} summary differs')
