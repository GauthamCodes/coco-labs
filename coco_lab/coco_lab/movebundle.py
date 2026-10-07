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
Lab 5's two bundle formats, 1.0: replanning episodes and recorded drives.

The normative description is ``docs/labs/MOVE_FORMAT.md``; this module is
its reference implementation. Both follow bundle format v1's rules
exactly (``coco_lab.bundle``), as Lab 2's, 3's and 4's do: a directory
holding ``manifest.json`` and ``arrays.bin`` (or ``arrays.bin.gz``, gzip
mtime 0); canonical JSON; little-endian arrays at contiguous offsets, in
the order the manifest's table lists them; the same content hash; every
size bounded before allocation; refuse, never repair.

``coco_lab.replan_bundle`` -- one :class:`coco_lab.replan.ReplanWorld`
and the episode :func:`coco_lab.replan.run_replan` drove in it: the
robot's walk, every round (cost, path, D* Lite's and A*'s work) and D*
Lite's event trace. :func:`replay_replan` runs the episode again from the
world alone and refuses unless every array and the summary match byte for
byte. Source kind ``sketch`` (a seeded teaching world) or ``glass-box``
(a world built from two recorded Nav2 costmaps).

``coco_lab.drive_bundle`` -- one Lab 5 scenario (its frozen path, start,
goal, actors, injection) and the controller runs recorded on it in
Gazebo: per run the full-rate ground truth, AMCL, the controller's and
the wheels' commands, actor tracks, the controller's own chosen
trajectories and, for some runs, its sampled candidates. Each run's
manifest block carries the four metrics; :func:`replay_drive` recomputes
them with :mod:`coco_lab.movemetrics` from the bundle's own arrays and
refuses unless they match exactly. Source kind ``recorded-run``.
"""

import gzip
import json
import math
import os
import struct
from typing import Dict, List, Optional, Tuple

from . import bundle as _b
from . import movemetrics as mm
from .dstarlite import COLUMNS as TRACE_COLUMNS, ReplanError
from .replan import ReplanWorld, run_replan

REPLAN_SCHEMA = 'coco_lab.replan_bundle'
DRIVE_SCHEMA = 'coco_lab.drive_bundle'
VERSION = '1.0'
MAJOR = 1
DTYPES = _b.DTYPES
MAX_RUNS = 64
CONTROLLERS = ('DWB', 'MPPI', 'RPP')
OUTCOMES = ('succeeded', 'follow_failed', 'failed', 'error')

TRACE_INT = ('kind', 'row', 'col', 'sub', 'round')
TRACE_FLOAT = ('g', 'rhs')


class MoveBundleError(ValueError):
    """A Lab 5 bundle that does not conform, or fails its replay."""


# -- shared array I/O ---------------------------------------------------------

def _pack(dtype: str, values) -> bytes:
    code = DTYPES[dtype][0]
    return struct.pack(f'<{len(values)}{code}', *values)


def _manifest(body: Dict[str, object], arrays, compression: str
              ) -> Dict[str, object]:
    if compression not in ('none', 'gzip'):
        raise MoveBundleError('compression must be none or gzip')
    table, offset = [], 0
    for name, dtype, data in arrays:
        size = DTYPES[dtype][1]
        table.append({'name': name, 'dtype': dtype,
                      'count': len(data) // size, 'offset': offset,
                      'byte_length': len(data)})
        offset += len(data)
    m = dict(body)
    m['arrays'] = table
    m['encoding'] = {'byte_order': 'little', 'compression': compression}
    m = json.loads(_b.canonical_json(m))
    m['content_hash'] = _b.content_hash(m, b''.join(d for _, _, d in arrays))
    return m


def _write(body, arrays, out_dir: str, compression: str) -> str:
    m = _manifest(body, arrays, compression)
    raw = b''.join(d for _, _, d in arrays)
    os.makedirs(out_dir, exist_ok=True)
    if compression == 'gzip':
        data, name = gzip.compress(raw, compresslevel=9, mtime=0), \
            _b.ARRAYS_GZ
    else:
        data, name = raw, _b.ARRAYS
    with open(os.path.join(out_dir, _b.MANIFEST), 'wb') as f:
        f.write(_b.canonical_json(m).encode('utf-8'))
    with open(os.path.join(out_dir, name), 'wb') as f:
        f.write(data)
    return m['content_hash']


def parse_manifest(text: bytes, schema: str) -> Dict[str, object]:
    """Parse and structurally check a manifest of ``schema``."""
    try:
        m = json.loads(text.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise MoveBundleError(f'manifest is not JSON: {exc}') from None
    if _b._depth(m) > _b.MAX_JSON_DEPTH:
        raise MoveBundleError('manifest nests too deep')
    if not isinstance(m, dict) or m.get('schema') != schema:
        raise MoveBundleError(f'schema must be {schema!r}')
    try:
        major = int(str(m.get('version', '')).split('.')[0])
    except ValueError:
        raise MoveBundleError(f'bad version {m.get("version")!r}') from None
    if major != MAJOR:
        raise MoveBundleError(f'major version {major} is not supported '
                              f'(this reader speaks {MAJOR}.x)')
    for key, kind in (('provenance', dict), ('arrays', list),
                      ('encoding', dict), ('content_hash', str)):
        if not isinstance(m.get(key), kind):
            raise MoveBundleError(f'manifest.{key} must be a '
                                  f'{kind.__name__}')
    enc = m['encoding']
    if enc.get('byte_order') != 'little' or \
            enc.get('compression') not in ('none', 'gzip'):
        raise MoveBundleError('encoding must be little-endian, none or gzip')
    offset = 0
    for a in m['arrays']:
        if not (isinstance(a, dict) and isinstance(a.get('name'), str)
                and a.get('dtype') in DTYPES):
            raise MoveBundleError(f'bad array entry {a!r}')
        for key in ('count', 'offset', 'byte_length'):
            v = a.get(key)
            if not (isinstance(v, int) and not isinstance(v, bool)
                    and v >= 0):
                raise MoveBundleError(f'array {a["name"]}: bad {key}')
        if a['offset'] != offset:
            raise MoveBundleError(f'array {a["name"]}: not contiguous')
        if a['byte_length'] != a['count'] * DTYPES[a['dtype']][1]:
            raise MoveBundleError(f'array {a["name"]}: byte_length '
                                  f'disagrees with count x dtype')
        offset += a['byte_length']
    if offset > _b.MAX_ARRAY_BYTES:
        raise MoveBundleError(f'arrays total {offset} bytes')
    return m


def _read(path: str, schema: str):
    try:
        with open(os.path.join(path, _b.MANIFEST), 'rb') as f:
            text = f.read(_b.MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise MoveBundleError(f'cannot read the manifest: {exc}') from None
    if len(text) > _b.MAX_MANIFEST_BYTES:
        raise MoveBundleError('manifest too large')
    m = parse_manifest(text, schema)
    expected = sum(a['byte_length'] for a in m['arrays'])
    gz = m['encoding']['compression'] == 'gzip'
    try:
        with open(os.path.join(path, _b.ARRAYS_GZ if gz else _b.ARRAYS),
                  'rb') as f:
            raw = _b._bounded_gunzip(f, expected) if gz \
                else f.read(expected + 1)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise MoveBundleError(f'cannot read the arrays: {exc}') from None
    if len(raw) != expected:
        raise MoveBundleError('array bytes do not match the table')
    if m['content_hash'] != _b.content_hash(m, raw):
        raise MoveBundleError('content_hash does not match the content')
    return m, raw


class _Taker:
    """Take named arrays out of a decoded bundle, then insist all were."""

    def __init__(self, manifest, raw):
        self.table = {a['name']: a for a in manifest['arrays']}
        if len(self.table) != len(manifest['arrays']):
            raise MoveBundleError('duplicate array name')
        self.raw = raw
        self.used = set()

    def has(self, name):
        return name in self.table

    def __call__(self, name, dtype):
        a = self.table.get(name)
        if a is None:
            raise MoveBundleError(f'missing array {name!r}')
        if a['dtype'] != dtype:
            raise MoveBundleError(f'array {name!r} must be {dtype}')
        self.used.add(name)
        code = DTYPES[dtype][0]
        return list(struct.unpack_from(f'<{a["count"]}{code}', self.raw,
                                       a['offset']))

    def done(self):
        extra = set(self.table) - self.used
        if extra:
            raise MoveBundleError(f'unexpected arrays {sorted(extra)}')


def _rows(flat, width, what):
    if len(flat) % width:
        raise MoveBundleError(f'{what}: length not a multiple of {width}')
    return [tuple(flat[i:i + width]) for i in range(0, len(flat), width)]


def _finite(values, what):
    if not all(math.isfinite(v) for v in values):
        raise MoveBundleError(f'{what} must be finite')


# -- replan bundle -----------------------------------------------------------------

def replan_arrays(result) -> List[Tuple[str, str, bytes]]:
    """Return a replan result's arrays, in wire order."""
    w = result.world
    out = [('known', 'u8', _pack('u8', [1 if b else 0 for b in w.known])),
           ('truth', 'u8', _pack('u8', [1 if b else 0 for b in w.truth])),
           ('known_final', 'u8', _pack('u8', [1 if b else 0
                                              for b in result.known_final]))]
    if w.cost is not None:
        out.append(('cost', 'f64', _pack('f64', w.cost)))
    out.append(('walk', 'i32', _pack('i32', [v for c in result.walk
                                             for v in c])))
    out.append(('paths', 'i32', _pack('i32', [v for r in result.rounds
                                              for c in r.path for v in c])))
    cols = result.trace.columns
    for name in TRACE_COLUMNS:
        dtype = 'f64' if name in TRACE_FLOAT else 'i32'
        out.append((f'trace.{name}', dtype, _pack(dtype, cols[name])))
    return out


def replan_body(result, provenance) -> Dict[str, object]:
    """Return a replan bundle's manifest body (no array table)."""
    rounds, off = [], 0
    for r in result.rounds:
        rounds.append({
            'step': r.step, 'robot': list(r.robot),
            'changed': [list(c) for c in r.changed], 'found': r.found,
            'cost': r.cost, 'path_offset': off, 'path_len': len(r.path),
            'dstar_expansions': r.dstar_expansions,
            'dstar_reexpansions': r.dstar_reexpansions,
            'astar_expansions': r.astar_expansions,
            'astar_cost': r.astar_cost})
        off += len(r.path)
    return {'schema': REPLAN_SCHEMA, 'version': VERSION,
            'provenance': dict(provenance), 'world': result.world.to_dict(),
            'status': result.status, 'summary': result.summary(),
            'rounds': rounds, 'n_events': len(result.trace)}


def write_replan_bundle(result, provenance, out_dir: str,
                        compression: str = 'gzip') -> str:
    """Write an episode as a replan bundle; return its content hash."""
    _b._check_provenance(provenance)
    if provenance.get('source_kind') not in ('sketch', 'glass-box'):
        raise MoveBundleError('a replan bundle is a sketch or glass-box')
    return _write(replan_body(result, provenance), replan_arrays(result),
                  out_dir, compression)


def load_replan_bundle(path: str) -> Tuple[Dict[str, object],
                                           ReplanWorld]:
    """Read and check a replan bundle; return ``(manifest, world)``."""
    m, raw = _read(path, REPLAN_SCHEMA)
    take = _Taker(m, raw)
    wd = m.get('world')
    if not isinstance(wd, dict):
        raise MoveBundleError('manifest.world must be an object')
    known = [bool(v) for v in take('known', 'u8')]
    truth = [bool(v) for v in take('truth', 'u8')]
    take('known_final', 'u8')
    cost = take('cost', 'f64') if wd.get('has_cost') else None
    take('walk', 'i32')
    take('paths', 'i32')
    for name in TRACE_COLUMNS:
        take(f'trace.{name}', 'f64' if name in TRACE_FLOAT else 'i32')
    take.done()
    try:
        world = ReplanWorld(
            int(wd['width']), int(wd['height']), known, truth,
            tuple(wd['start']), tuple(wd['goal']),
            sense_radius=wd['sense_radius'],
            connectivity=int(wd['connectivity']),
            heuristic=str(wd['heuristic']), cost=cost,
            schedule=[(int(s), [(int(c[0]), int(c[1]), bool(c[2]))
                                for c in cells])
                      for s, cells in wd.get('schedule', [])],
            max_steps=int(wd['max_steps']))
        world.validate()
    except (KeyError, TypeError, ValueError) as exc:
        raise MoveBundleError(f'world: {exc}') from None
    _b._check_provenance(m['provenance'])
    return m, world


def replay_replan(path: str) -> Dict[str, object]:
    """Run a replan bundle's episode again; refuse unless identical."""
    m, world = load_replan_bundle(path)
    try:
        again = run_replan(world)
    except ReplanError as exc:
        raise MoveBundleError(f'replay: {exc}') from None
    body = json.loads(_b.canonical_json(replan_body(again, m['provenance'])))
    for key in ('status', 'summary', 'rounds', 'n_events', 'world'):
        if body[key] != m[key]:
            raise MoveBundleError(f'replay: {key} differs')
    _, raw = _read(path, REPLAN_SCHEMA)
    mine = b''.join(d for _, _, d in replan_arrays(again))
    if mine != raw:
        raise MoveBundleError('replay: arrays differ')
    return m


# -- drive bundle -----------------------------------------------------------------

#: Per-run time series: name -> row width.
SERIES = {'gt': 4, 'amcl': 4, 'cmd': 3, 'wheel': 3}


def _ok_id(i) -> bool:
    return isinstance(i, str) and 0 < len(i) <= 48 and \
        all(c.isalnum() or c in '_-' for c in i)


def drive_arrays(scenario, runs) -> List[Tuple[str, str, bytes]]:
    """Return a drive bundle's arrays, in wire order."""
    out = [('path', 'f64', _pack('f64', [v for q in scenario['path']
                                         for v in q]))]
    for r in runs:
        rid = r['id']
        for name, width in SERIES.items():
            rows = r[name]
            out.append((f'run.{rid}.{name}', 'f64',
                        _pack('f64', [v for row in rows for v in row])))
        for aid in sorted(r.get('actors', {})):
            out.append((f'run.{rid}.actor.{aid}', 'f64', _pack(
                'f64', [v for row in r['actors'][aid] for v in row])))
        ch = r.get('chosen', [])
        out.append((f'run.{rid}.chosen.t', 'f64',
                    _pack('f64', [c[0] for c in ch])))
        offs, pts = [0], []
        for c in ch:
            pts.extend(v for p in c[1] for v in p)
            offs.append(len(pts) // 2)
        out.append((f'run.{rid}.chosen.off', 'i32', _pack('i32', offs)))
        out.append((f'run.{rid}.chosen.pts', 'f64', _pack('f64', pts)))
        ev = r.get('eval', [])
        out.append((f'run.{rid}.eval', 'f64', _pack(
            'f64', [v for e in ev for v in e])))
        ro = r.get('rollouts')
        if ro is not None:
            ft, fn, coff, poff, pts, flags, total = [], [], [0], [0], [], \
                [], []
            for fr in ro:
                ft.append(fr['t'])
                fn.extend([fr['n'], -1 if fr['n_valid'] is None
                           else fr['n_valid']])
                for c in fr['candidates']:
                    pts.extend(v for p in c['pts'] for v in p)
                    poff.append(len(pts) // 2)
                    valid = 2 if c['valid'] is None else int(c['valid'])
                    flags.append(valid | (4 if c['best'] else 0))
                    total.append(math.nan if c['total'] is None
                                 else c['total'])
                coff.append(len(flags))
            out += [(f'run.{rid}.roll.t', 'f64', _pack('f64', ft)),
                    (f'run.{rid}.roll.n', 'i32', _pack('i32', fn)),
                    (f'run.{rid}.roll.coff', 'i32', _pack('i32', coff)),
                    (f'run.{rid}.roll.poff', 'i32', _pack('i32', poff)),
                    (f'run.{rid}.roll.pts', 'f64', _pack('f64', pts)),
                    (f'run.{rid}.roll.flags', 'u8', _pack('u8', flags)),
                    (f'run.{rid}.roll.total', 'f64', _pack('f64', total))]
    return out


def run_metrics(scenario, run) -> Dict[str, object]:
    """Recompute a run's four metrics from its arrays (movemetrics)."""
    boxes = [tuple(b) for b in scenario['boxes']]
    actors = [{'radius': scenario['actor_radius'],
               'track': [(t, x, y) for t, x, y, *_ in run['actors'][aid]]}
              for aid in sorted(run.get('actors', {}))]
    t0, t1 = run['window']
    return json.loads(_b.canonical_json(mm.evaluate(
        scenario['path'], run['gt'], (t0, t1), run['cmd'], boxes, actors)))


def drive_body(scenario, runs, provenance) -> Dict[str, object]:
    """Return a drive bundle's manifest body (no array table)."""
    blocks = []
    for r in runs:
        b = {k: r[k] for k in ('id', 'controller', 'outcome', 'window',
                               'record')}
        b['metrics'] = run_metrics(scenario, r)
        b['has_rollouts'] = r.get('rollouts') is not None
        b['actors'] = sorted(r.get('actors', {}))
        b['monitor'] = r.get('monitor', [])
        b['actor_trigger'] = r.get('actor_trigger', {})
        b['n'] = {k: len(r[k]) for k in SERIES}
        blocks.append(b)
    sc = {k: v for k, v in scenario.items() if k != 'path'}
    sc['path_len'] = len(scenario['path'])
    return {'schema': DRIVE_SCHEMA, 'version': VERSION,
            'provenance': dict(provenance), 'scenario': sc, 'runs': blocks}


def validate_drive(scenario, runs) -> None:
    """Raise :class:`MoveBundleError` unless the drive data is consistent."""
    if not 1 <= len(runs) <= MAX_RUNS:
        raise MoveBundleError(f'1..{MAX_RUNS} runs, not {len(runs)}')
    ids = [r['id'] for r in runs]
    if len(set(ids)) != len(ids) or not all(_ok_id(i) for i in ids):
        raise MoveBundleError(f'run ids must be unique short words: {ids}')
    if len(scenario['path']) < 2:
        raise MoveBundleError('the path needs two poses')
    _finite([v for q in scenario['path'] for v in q], 'path')
    for r in runs:
        if r['controller'] not in CONTROLLERS:
            raise MoveBundleError(f'run {r["id"]}: controller '
                                  f'{r["controller"]!r}')
        if r['outcome'] not in OUTCOMES:
            raise MoveBundleError(f'run {r["id"]}: outcome {r["outcome"]!r}')
        t0, t1 = r['window']
        if not (math.isfinite(t0) and math.isfinite(t1) and t0 <= t1):
            raise MoveBundleError(f'run {r["id"]}: bad window')
        for name, width in SERIES.items():
            rows = r[name]
            if any(len(row) != width for row in rows):
                raise MoveBundleError(f'run {r["id"]}: {name} rows')
            _finite([v for row in rows for v in row], f'{name}')
            ts = [row[0] for row in rows]
            if any(b < a for a, b in zip(ts, ts[1:])):
                raise MoveBundleError(f'run {r["id"]}: {name} goes back '
                                      f'in time')


def write_drive_bundle(scenario, runs, provenance, out_dir: str,
                       compression: str = 'gzip') -> str:
    """Write a scenario's runs as a drive bundle; return its hash."""
    _b._check_provenance(provenance)
    if provenance.get('source_kind') != 'recorded-run':
        raise MoveBundleError('a drive bundle is a recorded-run bundle')
    validate_drive(scenario, runs)
    return _write(drive_body(scenario, runs, provenance),
                  drive_arrays(scenario, runs), out_dir, compression)


def load_drive_bundle(path: str):
    """Read and check a drive bundle; return ``(manifest, scenario, runs)``."""
    m, raw = _read(path, DRIVE_SCHEMA)
    take = _Taker(m, raw)
    sc = m.get('scenario')
    if not isinstance(sc, dict) or not isinstance(m.get('runs'), list):
        raise MoveBundleError('manifest.scenario / runs missing')
    scenario = dict(sc)
    scenario.pop('path_len', None)
    path = _rows(take('path', 'f64'), 3, 'path')
    scenario['path'] = [list(q) for q in path]
    if len(scenario['path']) != sc.get('path_len'):
        raise MoveBundleError('path_len disagrees')
    runs = []
    for b in m['runs']:
        if not isinstance(b, dict) or not _ok_id(b.get('id')):
            raise MoveBundleError('bad run entry')
        rid = b['id']
        r = {k: b[k] for k in ('id', 'controller', 'outcome', 'window',
                               'record')}
        for name, width in SERIES.items():
            r[name] = [list(x) for x in _rows(
                take(f'run.{rid}.{name}', 'f64'), width, name)]
            if len(r[name]) != b['n'][name]:
                raise MoveBundleError(f'run {rid}: {name} count disagrees')
        r['actors'] = {aid: [list(x) for x in _rows(
            take(f'run.{rid}.actor.{aid}', 'f64'), 4, 'actor')]
            for aid in b.get('actors', [])}
        ct = take(f'run.{rid}.chosen.t', 'f64')
        co = take(f'run.{rid}.chosen.off', 'i32')
        cp = take(f'run.{rid}.chosen.pts', 'f64')
        if len(co) != len(ct) + 1 or co[0] != 0 or co[-1] * 2 != len(cp) \
                or any(b2 < a2 for a2, b2 in zip(co, co[1:])):
            raise MoveBundleError(f'run {rid}: chosen offsets')
        r['chosen'] = [[ct[i], [[cp[2 * j], cp[2 * j + 1]]
                                for j in range(co[i], co[i + 1])]]
                       for i in range(len(ct))]
        r['eval'] = [list(x) for x in _rows(take(f'run.{rid}.eval', 'f64'),
                                            3, 'eval')]
        if b.get('has_rollouts'):
            names = ('t', 'n', 'coff', 'poff', 'pts', 'flags', 'total')
            dt = {'t': 'f64', 'n': 'i32', 'coff': 'i32', 'poff': 'i32',
                  'pts': 'f64', 'flags': 'u8', 'total': 'f64'}
            ro = {k: take(f'run.{rid}.roll.{k}', dt[k]) for k in names}
            nf, nc = len(ro['t']), len(ro['flags'])
            if (len(ro['n']) != 2 * nf or len(ro['coff']) != nf + 1
                    or ro['coff'][-1] != nc or len(ro['poff']) != nc + 1
                    or ro['poff'][-1] * 2 != len(ro['pts'])
                    or len(ro['total']) != nc):
                raise MoveBundleError(f'run {rid}: rollout tables')
            r['rollouts'] = ro
        r['monitor'] = b.get('monitor', [])
        r['actor_trigger'] = b.get('actor_trigger', {})
        r['metrics'] = b.get('metrics')
        runs.append(r)
    take.done()
    _b._check_provenance(m['provenance'])
    try:
        validate_drive(scenario, runs)
    except (KeyError, TypeError) as exc:
        raise MoveBundleError(str(exc)) from None
    return m, scenario, runs


def replay_drive(path: str) -> Dict[str, object]:
    """Recompute every run's metrics; refuse unless they match exactly."""
    m, scenario, runs = load_drive_bundle(path)
    for r in runs:
        if run_metrics(scenario, r) != r['metrics']:
            raise MoveBundleError(f'replay: run {r["id"]} metrics differ')
    return m


def ensure(path: str) -> Optional[str]:
    """Return the schema of the bundle at ``path`` (or None)."""
    try:
        with open(os.path.join(path, _b.MANIFEST), 'rb') as f:
            return json.loads(f.read(_b.MAX_MANIFEST_BYTES)).get('schema')
    except (OSError, ValueError):
        return None
