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
Localisation bundle format 1.0: one Sketch world, and filters run on it.

The normative description is ``docs/labs/LOC_BUNDLE_FORMAT.md``; this
module is its reference implementation and the tests pin one to the other.
It follows bundle format v1's rules exactly (``coco_lab.bundle``), and
reuses its content hash, provenance and bounded reading:

- a **directory** holding ``manifest.json`` and ``arrays.bin`` (or
  ``arrays.bin.gz``, gzip ``mtime`` 0), never a file name in the manifest;
- canonical JSON; little-endian arrays at contiguous offsets;
- ``content_hash`` = SHA-256 over the canonical manifest (without
  ``content_hash``, ``encoding`` and ``provenance.created_utc``), a
  newline, and the uncompressed arrays;
- untrusted input: every size bounded before allocation, JSON and fixed
  width numbers only, refused rather than repaired.

What it holds: the map; the :class:`~coco_lab.sketch.Scenario` (seed,
noise, route, kidnap, LiDAR) that produced the world; the world's truth,
odometry, commands, update rows and measured scans; and one to four
filter runs (:class:`~coco_lab.localise.LocTrace`) **on that same world**
-- identical inputs by construction. ``source_kind`` is ``sketch``.

A bundle can be **replayed**: :func:`replay_check` recomputes the world
and every run from the manifest's inputs with this ``coco_lab`` and
requires the arrays to come out byte-identical. ``build_catalog`` refuses
a bundle that does not.
"""

from dataclasses import dataclass
import gzip
import json
import math
import os
import struct
from typing import Dict, List, Optional, Tuple

from . import bundle as _b
from . import localise
from .localise import EKFParams, LocError, LocTrace, MCLParams
from .maps import LabMap, MapError
from .sketch import Scenario, simulate, SketchMap, WorldRun

SCHEMA = 'coco_lab.loc_bundle'
VERSION = '1.0'
MAJOR = 1
MANIFEST = _b.MANIFEST
ARRAYS = _b.ARRAYS
ARRAYS_GZ = _b.ARRAYS_GZ

#: Wire types: bundle v1's plus f32 (particles only).
DTYPES = dict(_b.DTYPES, f32=('f', 4))

WORLD_COLUMNS = ('t', 'gt_x', 'gt_y', 'gt_yaw', 'odom_x', 'odom_y',
                 'odom_yaw', 'cmd_v', 'cmd_w')
MAX_RUNS = 4
MAX_ROWS = 200_000
MAX_PARTICLE_ROWS = 20_000_000
STATUSES = ('route_done', 'timeout', 'stuck')


class LocBundleError(ValueError):
    """A localisation bundle that does not conform, or fails a check."""


def _params_of(kind: str, d: Dict[str, object]):
    if kind == 'mcl':
        p = MCLParams(**{k: (tuple(v) if isinstance(v, list) else v)
                         for k, v in d.items()})
    elif kind == 'ekf':
        p = EKFParams(**{k: (tuple(v) if isinstance(v, list) else v)
                         for k, v in d.items()})
    else:
        raise LocBundleError(f'unknown filter {kind!r}')
    p.check()
    return p


def run_filter(smap: SketchMap, world: WorldRun, kind: str,
               params) -> LocTrace:
    """Run one filter by name."""
    if kind == 'mcl':
        return localise.run_mcl(smap, world, params)
    if kind == 'ekf':
        return localise.run_ekf(smap, world, params)
    raise LocBundleError(f'unknown filter {kind!r}')


@dataclass
class LocBundle:
    """A Sketch world and the filter runs on it."""

    provenance: Dict[str, object]
    lab_map: LabMap
    world: WorldRun
    #: ``[(run_id, trace)]``, ids unique, at most :data:`MAX_RUNS`
    runs: List[Tuple[str, LocTrace]]

    @classmethod
    def compute(cls, lab_map: LabMap, scenario: Scenario,
                runs: List[Tuple[str, str, object]],
                provenance: Dict[str, object],
                smap: Optional[SketchMap] = None) -> 'LocBundle':
        """
        Simulate ``scenario`` once and run every ``(id, kind, params)``.

        Every run reads the same :class:`WorldRun`.
        """
        smap = smap or SketchMap(lab_map)
        world = simulate(smap, scenario)
        out = [(rid, run_filter(smap, world, kind, params))
               for rid, kind, params in runs]
        b = cls(provenance, lab_map, world, out)
        b.validate()
        return b

    def validate(self) -> None:
        """Raise :class:`LocBundleError` unless the bundle is consistent."""
        _b._check_provenance(self.provenance)
        if self.provenance['source_kind'] != 'sketch':
            raise LocBundleError('a localisation bundle is a sketch')
        if not 1 <= len(self.runs) <= MAX_RUNS:
            raise LocBundleError(f'1..{MAX_RUNS} runs, not '
                                 f'{len(self.runs)}')
        ids = [rid for rid, _ in self.runs]
        if len(set(ids)) != len(ids) or not all(
                isinstance(i, str) and 0 < len(i) <= 32 and
                all(c.isalnum() or c in '_-' for c in i) for i in ids):
            raise LocBundleError(f'run ids must be unique short words: '
                                 f'{ids}')
        w = self.world
        n = len(w.t)
        for name, seq in (('gt', w.gt), ('odom', w.odom), ('cmd', w.cmd)):
            if len(seq) != n:
                raise LocBundleError(f'world.{name} has {len(seq)} rows, '
                                     f'expected {n}')
        if any(b <= a for a, b in zip(w.t, w.t[1:])):
            raise LocBundleError('world.t must strictly increase')
        if not w.updates or w.updates[0] != 0 or any(
                b <= a for a, b in zip(w.updates, w.updates[1:])) or \
                w.updates[-1] >= n:
            raise LocBundleError('world.updates must start at 0, strictly '
                                 'increase and index a row')
        nb = w.scenario.lidar.samples
        if len(w.ranges) != len(w.updates) or any(len(r) != nb
                                                  for r in w.ranges):
            raise LocBundleError(f'world.ranges must be n_updates x {nb}')
        if w.kidnap_row is not None and not 0 < w.kidnap_row < n:
            raise LocBundleError('world.kidnap_row out of range')
        if w.status not in STATUSES:
            raise LocBundleError(f'world.status {w.status!r}')
        for rid, tr in self.runs:
            try:
                tr.validate()
            except LocError as exc:
                raise LocBundleError(f'run {rid}: {exc}') from None
            if list(tr.columns['row']) != list(w.updates):
                raise LocBundleError(f"run {rid}: rows are not the world's "
                                     f'update rows')

    # -- serialisation -----------------------------------------------------

    def arrays(self) -> List[Tuple[str, str, bytes]]:
        """Return ``(name, dtype, little-endian bytes)`` in wire order."""
        def pack(dtype, values):
            code = DTYPES[dtype][0]
            return struct.pack(f'<{len(values)}{code}', *values)

        w = self.world
        out = [('map.occupancy', 'u8', self.lab_map.occupancy)]
        cols = {
            't': w.t, 'gt_x': [p[0] for p in w.gt],
            'gt_y': [p[1] for p in w.gt], 'gt_yaw': [p[2] for p in w.gt],
            'odom_x': [p[0] for p in w.odom],
            'odom_y': [p[1] for p in w.odom],
            'odom_yaw': [p[2] for p in w.odom],
            'cmd_v': [c[0] for c in w.cmd], 'cmd_w': [c[1] for c in w.cmd],
        }
        for name in WORLD_COLUMNS:
            out.append((f'world.{name}', 'f64', pack('f64', cols[name])))
        out.append(('world.updates', 'i32', pack('i32', w.updates)))
        flat = [r for scan in w.ranges for r in scan]
        out.append(('world.ranges', 'f64', pack('f64', flat)))
        for rid, tr in self.runs:
            for name in tr.column_names():
                dt = 'i32' if name in localise.INT_COLUMNS else 'f64'
                out.append((f'run.{rid}.{name}', dt,
                            pack(dt, tr.columns[name])))
            if tr.particles is not None:
                p = tr.particles
                out.append((f'run.{rid}.particles.offset', 'i32',
                            pack('i32', p['offset'])))
                for name in localise.PARTICLE_COLUMNS:
                    out.append((f'run.{rid}.particles.{name}', 'f32',
                                pack('f32', p[name])))
        return out

    def manifest(self, compression: str = 'none') -> Dict[str, object]:
        """Return the manifest dict, content hash included."""
        if compression not in ('none', 'gzip'):
            raise LocBundleError('compression must be none or gzip')
        arrays = self.arrays()
        table, offset = [], 0
        for name, dtype, data in arrays:
            size = DTYPES[dtype][1]
            table.append({'name': name, 'dtype': dtype,
                          'count': len(data) // size, 'offset': offset,
                          'byte_length': len(data)})
            offset += len(data)
        m = self.lab_map
        w = self.world
        manifest = {
            'schema': SCHEMA, 'version': VERSION,
            'provenance': dict(self.provenance),
            'map': {
                'id': m.id, 'content_hash': m.content_hash(),
                'width': m.width, 'height': m.height,
                'geo': {'resolution': m.resolution,
                        'origin': list(m.origin), 'frame': m.frame},
                'meta': dict(m.meta),
            },
            'scenario': w.scenario.to_dict(),
            'world': {'status': w.status, 'n_rows': len(w.t),
                      'n_updates': len(w.updates),
                      'kidnap_row': w.kidnap_row},
            'runs': [{'id': rid, 'header': tr.header,
                      'summary': tr.summary} for rid, tr in self.runs],
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


def write_loc_bundle(lb: LocBundle, out_dir: str,
                     compression: str = 'gzip') -> str:
    """Write ``lb`` into ``out_dir`` (created); return the content hash."""
    lb.validate()
    os.makedirs(out_dir, exist_ok=True)
    mbytes, name, data, digest = lb.to_bytes(compression)
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
        raise LocBundleError(f'manifest is not JSON: {exc}') from None
    if _b._depth(manifest) > _b.MAX_JSON_DEPTH:
        raise LocBundleError(f'manifest nests deeper than '
                             f'{_b.MAX_JSON_DEPTH}')
    if not isinstance(manifest, dict):
        raise LocBundleError('manifest must be an object')
    if manifest.get('schema') != SCHEMA:
        raise LocBundleError(f'schema is {manifest.get("schema")!r}, not '
                             f'{SCHEMA!r}')
    try:
        major = int(str(manifest.get('version', '')).split('.')[0])
    except ValueError:
        raise LocBundleError(f'bad version {manifest.get("version")!r}') \
            from None
    if major != MAJOR:
        raise LocBundleError(f'loc bundle major version {major} is not '
                             f'supported (this reader speaks {MAJOR}.x)')
    for key, kind in (('provenance', dict), ('map', dict),
                      ('scenario', dict), ('world', dict), ('runs', list),
                      ('arrays', list), ('encoding', dict),
                      ('content_hash', str)):
        if not isinstance(manifest.get(key), kind):
            raise LocBundleError(f'manifest.{key} must be a {kind.__name__}')
    enc = manifest['encoding']
    if enc.get('byte_order') != 'little' or \
            enc.get('compression') not in ('none', 'gzip'):
        raise LocBundleError('encoding must be little-endian, none or gzip')
    offset = 0
    for a in manifest['arrays']:
        if not (isinstance(a, dict) and isinstance(a.get('name'), str)
                and a.get('dtype') in DTYPES):
            raise LocBundleError(f'bad array entry {a!r}')
        for key in ('count', 'offset', 'byte_length'):
            v = a.get(key)
            if not (isinstance(v, int) and not isinstance(v, bool)
                    and v >= 0):
                raise LocBundleError(f'array {a["name"]}: {key} must be '
                                     f'an int >= 0')
        if a['offset'] != offset:
            raise LocBundleError(f'array {a["name"]}: not contiguous')
        if a['byte_length'] != a['count'] * DTYPES[a['dtype']][1]:
            raise LocBundleError(f'array {a["name"]}: byte_length '
                                 f'disagrees with count x dtype')
        offset += a['byte_length']
    if offset > _b.MAX_ARRAY_BYTES:
        raise LocBundleError(f'arrays total {offset} bytes')
    return manifest


def load_loc_bundle(path: str) -> LocBundle:
    """Read, bound, decode and validate the bundle directory at ``path``."""
    try:
        with open(os.path.join(path, MANIFEST), 'rb') as f:
            text = f.read(_b.MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise LocBundleError(f'cannot read the manifest: {exc}') from None
    if len(text) > _b.MAX_MANIFEST_BYTES:
        raise LocBundleError('manifest too large')
    manifest = parse_manifest(text)
    expected = sum(a['byte_length'] for a in manifest['arrays'])
    gz = manifest['encoding']['compression'] == 'gzip'
    try:
        with open(os.path.join(path, ARRAYS_GZ if gz else ARRAYS), 'rb') as f:
            raw = _b._bounded_gunzip(f, expected) if gz \
                else f.read(expected + 1)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise LocBundleError(f'cannot read the arrays: {exc}') from None
    return decode(manifest, raw)


def decode(manifest: Dict[str, object], raw: bytes) -> LocBundle:
    """Build and validate a bundle from a parsed manifest and array bytes."""
    if len(raw) != sum(a['byte_length'] for a in manifest['arrays']):
        raise LocBundleError('array bytes do not match the table')
    if manifest['content_hash'] != _b.content_hash(manifest, raw):
        raise LocBundleError('content_hash does not match the content')
    table = {a['name']: a for a in manifest['arrays']}
    if len(table) != len(manifest['arrays']):
        raise LocBundleError('duplicate array name')

    def column(name, dtype=None):
        a = table.get(name)
        if a is None:
            raise LocBundleError(f'missing array {name!r}')
        if dtype is not None and a['dtype'] != dtype:
            raise LocBundleError(f'array {name!r} must be {dtype}')
        code = DTYPES[a['dtype']][0]
        return list(struct.unpack_from(f'<{a["count"]}{code}', raw,
                                       a['offset']))

    used = set()

    def take(name, dtype=None):
        used.add(name)
        return column(name, dtype)

    md = manifest['map']
    try:
        geo = md['geo']
        occ = bytes(take('map.occupancy', 'u8'))
        lab_map = LabMap(md['width'], md['height'], occ, map_id=md['id'],
                         resolution=geo['resolution'],
                         origin=tuple(geo['origin']), frame=geo['frame'],
                         meta=md.get('meta'))
    except (KeyError, TypeError, MapError) as exc:
        raise LocBundleError(f'bad map: {exc}') from None
    if md.get('content_hash') != lab_map.content_hash():
        raise LocBundleError('map.content_hash does not match the map')
    try:
        scenario = Scenario.from_dict(manifest['scenario'])
    except (KeyError, TypeError, ValueError) as exc:
        raise LocBundleError(f'bad scenario: {exc}') from None
    wm = manifest['world']
    n = wm.get('n_rows')
    if not (isinstance(n, int) and 0 < n <= MAX_ROWS):
        raise LocBundleError('world.n_rows out of range')
    cols = {c: take(f'world.{c}', 'f64') for c in WORLD_COLUMNS}
    if any(len(v) != n for v in cols.values()):
        raise LocBundleError('world columns disagree with n_rows')
    if not all(math.isfinite(v) for c in cols.values() for v in c):
        raise LocBundleError('world columns must be finite')
    updates = take('world.updates', 'i32')
    flat = take('world.ranges', 'f64')
    nb = scenario.lidar.samples
    if len(flat) != len(updates) * nb:
        raise LocBundleError('world.ranges is not n_updates x n_beams')
    if any(math.isnan(v) or v < 0 for v in flat):
        raise LocBundleError('ranges must be >= 0 or inf')
    world = WorldRun(
        scenario, cols['t'],
        list(zip(cols['gt_x'], cols['gt_y'], cols['gt_yaw'])),
        list(zip(cols['odom_x'], cols['odom_y'], cols['odom_yaw'])),
        list(zip(cols['cmd_v'], cols['cmd_w'])), updates,
        [flat[i * nb:(i + 1) * nb] for i in range(len(updates))],
        wm.get('kidnap_row'), wm.get('status'))
    runs = []
    for r in manifest['runs']:
        if not isinstance(r, dict) or not isinstance(r.get('header'), dict):
            raise LocBundleError('bad run entry')
        rid = r.get('id')
        kind = r['header'].get('filter')
        if kind not in localise.FILTERS:
            raise LocBundleError(f'run {rid}: unknown filter {kind!r}')
        names = localise.COMMON_COLUMNS + localise.FILTER_COLUMNS[kind]
        tcols = {c: take(f'run.{rid}.{c}',
                         'i32' if c in localise.INT_COLUMNS else 'f64')
                 for c in names}
        parts = None
        if kind == 'mcl':
            parts = {'offset': take(f'run.{rid}.particles.offset', 'i32')}
            if parts['offset'] and parts['offset'][-1] > MAX_PARTICLE_ROWS:
                raise LocBundleError('too many particle rows')
            for c in localise.PARTICLE_COLUMNS:
                parts[c] = take(f'run.{rid}.particles.{c}', 'f32')
        runs.append((rid, LocTrace(dict(r['header']), tcols,
                                   dict(r.get('summary') or {}), parts)))
    extra = set(table) - used
    if extra:
        raise LocBundleError(f'unexpected arrays {sorted(extra)}')
    lb = LocBundle(dict(manifest['provenance']), lab_map, world, runs)
    try:
        lb.validate()
    except (LocError, ValueError) as exc:
        raise LocBundleError(str(exc)) from None
    return lb


def run_specs(lb: LocBundle) -> List[Tuple[str, str, object]]:
    """Return ``[(id, kind, params)]`` of the bundle's runs."""
    return [(rid, tr.kind, _params_of(tr.kind, tr.header['params']))
            for rid, tr in lb.runs]


def replay_check(lb: LocBundle) -> None:
    """
    Recompute the world and every run; refuse unless the bytes match.

    The world is simulated again from the scenario and every filter run
    again with its recorded parameters, by THIS coco_lab; the arrays and
    every summary must come out identical.
    """
    again = LocBundle.compute(lb.lab_map, lb.world.scenario, run_specs(lb),
                              lb.provenance)
    a = {n: d for n, _, d in lb.arrays()}
    b = {n: d for n, _, d in again.arrays()}
    if a.keys() != b.keys():
        raise LocBundleError('replay produced different arrays')
    bad = sorted(n for n in a if a[n] != b[n])
    if bad:
        raise LocBundleError(f'replay differs in {bad[:5]}')
    for (rid, t1), (_, t2) in zip(lb.runs, again.runs):
        if json.loads(_b.canonical_json(t1.summary)) != \
                json.loads(_b.canonical_json(t2.summary)):
            raise LocBundleError(f'replay: run {rid} summary differs')
