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
Map bundle format 1.0: one world, the mapping runs on it, and their scores.

The normative description is ``docs/labs/SLAM_FORMAT.md``; this module is
its reference implementation. It follows bundle format v1's rules exactly
(``coco_lab.bundle``) and Lab 2's ``locbundle``: a directory holding
``manifest.json`` and ``arrays.bin`` (or ``arrays.bin.gz``, gzip mtime 0);
canonical JSON; little-endian arrays at contiguous offsets; the same
content hash; every size bounded before allocation; refuse, never repair.

What it holds:

- the TRUTH map (the Sketch world, or Phase 1B's ground-truth raster of the
  arena for a recorded drive);
- one :class:`coco_lab.mapworld.MapWorld` -- truth and odometry per row,
  update rows, scans and idealised landmark observations at the updates;
- one to six coco_lab runs (:class:`coco_lab.slam.SlamTrace`) ON THAT
  WORLD -- identical inputs by construction -- each SCORED here by
  :mod:`coco_lab.mapeval` (summary + per-update errors + a map-vs-truth
  raster);
- for a recorded drive, up to four EXTERNAL runs: a ROS backend's online
  trajectory at the same updates and its final map, as measured
  (``docs/data/lab3``), scored by the same code. coco_lab cannot rerun
  them, so they are data with provenance.

``replay_check`` recomputes the world (Sketch: simulated again from its
scenario) and every coco_lab run, requires the arrays to come out byte
for byte, and re-scores every run, external ones included.
"""

from dataclasses import dataclass, field
import gzip
import json
import math
import os
import struct
from typing import Dict, List, Optional, Tuple

from . import bundle as _b
from . import mapeval, mapping, mapworld, slam
from .landmarks import Observation
from .maps import LabMap, MapError
from .occgrid import GridParams, u8_to_labmap
from .sketch import LidarSpec, Scenario

SCHEMA = 'coco_lab.slam_bundle'
VERSION = '1.0'
MAJOR = 1
MANIFEST = _b.MANIFEST
ARRAYS = _b.ARRAYS
ARRAYS_GZ = _b.ARRAYS_GZ
DTYPES = dict(_b.DTYPES, f32=('f', 4))

WORLD_COLUMNS = ('t', 'gt_x', 'gt_y', 'gt_yaw', 'odom_x', 'odom_y',
                 'odom_yaw')
MAX_RUNS = 6
MAX_EXTERNAL = 4
MAX_ROWS = 200_000
STATUSES = ('route_done', 'timeout', 'stuck')
SOURCE_KIND = {'sketch': 'sketch', 'recorded': 'recorded-run'}


class SlamBundleError(ValueError):
    """A map bundle that does not conform, or fails a check."""


def _pack(dtype, values):
    code = DTYPES[dtype][0]
    if dtype == 'u8':
        return bytes(values)
    return struct.pack(f'<{len(values)}{code}', *values)


def _ok_id(i) -> bool:
    return isinstance(i, str) and 0 < len(i) <= 32 and \
        all(c.isalnum() or c in '_-' for c in i)


# -- scoring ---------------------------------------------------------------------

def score_trace(tr: slam.SlamTrace, truth: mapeval.Truth, true_poses,
                align: bool, tol: float = mapeval.DEFAULT_TOL) -> None:
    """
    Score ``tr`` in place: ``summary`` and the ``score.*`` arrays.

    ``ate_online`` scores the estimate as it ran, ``ate_final`` the
    trajectory at the end; the final map is moved by ``ate_final``'s
    alignment (identity unless ``align``), resampled onto the truth's grid
    and scored by :func:`mapeval.score_map` (tolerance ``tol``).
    """
    est = tr.estimates()
    fin = tr.final_trajectory()
    a_on = mapeval.ate(est, true_poses, align=align)
    a_fin = mapeval.ate(fin, true_poses, align=align)
    T = tuple(a_fin['alignment'])
    g = tr.header['grid']
    th = tr.header.get('grid_params', {})
    gp = GridParams(free_thresh=th.get('free_thresh', 0.25),
                    occupied_thresh=th.get('occupied_thresh', 0.65))
    tm = truth.map
    on = mapeval.resample_onto(tm, tr.maps[-1], g['width'], g['height'],
                               g['resolution'], tuple(g['origin']), T)
    lm = u8_to_labmap(on, tm.width, tm.height, tm.resolution, tm.origin, gp)
    tr.summary = mapeval.round_floats({
        'ate_online': a_on, 'ate_final': a_fin,
        'map': mapeval.score_map(truth, lm, tol)})
    tr.arrays['score.err_online'] = ('f64', mapeval.errors(
        est, true_poses, tuple(a_on['alignment'])))
    tr.arrays['score.err_final'] = ('f64', mapeval.errors(
        fin, true_poses, T))
    tr.arrays['score.diff'] = ('u8', list(mapeval.diff_raster(truth, lm,
                                                              tol)))


@dataclass
class ExternalRun:
    """A ROS backend's measured output on a recorded drive (data, not code)."""

    id: str  # noqa: A003 -- the run id, as every run in a bundle has
    backend: str
    arm: str
    #: per update, the backend's ONLINE belief (map frame of its own)
    est: List[Tuple[float, float, float]]
    #: its final map: OccupancyGrid bytes, north row first, 255 unknown
    cells: bytes
    grid: Dict[str, object]
    source: Dict[str, object]
    summary: Dict[str, object] = field(default_factory=dict)
    err_online: List[float] = field(default_factory=list)
    diff: bytes = b''

    def score(self, truth: mapeval.Truth, true_poses,
              tol: float = mapeval.DEFAULT_TOL) -> None:
        """Score with the SAME definitions as a coco_lab run (aligned)."""
        a = mapeval.ate(self.est, true_poses, align=True)
        T = tuple(a['alignment'])
        tm = truth.map
        g = self.grid
        on = mapeval.resample_onto(tm, self.cells, g['width'], g['height'],
                                   g['resolution'], tuple(g['origin']), T)
        lm = u8_to_labmap(on, tm.width, tm.height, tm.resolution, tm.origin)
        self.summary = mapeval.round_floats({
            'ate_online': a, 'map': mapeval.score_map(truth, lm, tol)})
        self.err_online = mapeval.errors(self.est, true_poses, T)
        self.diff = mapeval.diff_raster(truth, lm, tol)


@dataclass
class SlamBundle:
    """A world, the runs on it, and how they score."""

    provenance: Dict[str, object]
    lab_map: LabMap
    world: mapworld.MapWorld
    runs: List[Tuple[str, slam.SlamTrace]]
    external: List[ExternalRun] = field(default_factory=list)
    #: score with a rigid alignment (recorded drives) or in the given frame
    align: bool = False
    tol: float = mapeval.DEFAULT_TOL

    @classmethod
    def compute(cls, lab_map: LabMap, world: mapworld.MapWorld,
                specs: List[Tuple[str, str, object]],
                provenance: Dict[str, object], align: bool = False,
                external: Optional[List[ExternalRun]] = None,
                tol: float = mapeval.DEFAULT_TOL,
                truth: Optional[mapeval.Truth] = None) -> 'SlamBundle':
        """Run every ``(id, algorithm, params)`` on ``world``; score all."""
        inp = world.inputs()
        tp = world.true_poses()
        truth = truth or mapeval.Truth(lab_map, world.start[:2])
        runs = []
        for rid, alg, params in specs:
            tr = mapping.run(alg, inp, lab_map, params, true_poses=tp)
            score_trace(tr, truth, tp, align, tol)
            runs.append((rid, tr))
        ext = list(external or [])
        for e in ext:
            e.score(truth, tp, tol)
        b = cls(provenance, lab_map, world, runs, ext, align, tol)
        b.validate()
        return b

    def validate(self) -> None:
        """Raise :class:`SlamBundleError` unless the bundle is consistent."""
        _b._check_provenance(self.provenance)
        w = self.world
        if w.source not in mapworld.SOURCES:
            raise SlamBundleError(f'world.source {w.source!r}')
        if self.provenance['source_kind'] != SOURCE_KIND[w.source]:
            raise SlamBundleError('provenance.source_kind does not match '
                                  'the world')
        if not 1 <= len(self.runs) <= MAX_RUNS:
            raise SlamBundleError(f'1..{MAX_RUNS} runs')
        if len(self.external) > MAX_EXTERNAL:
            raise SlamBundleError(f'at most {MAX_EXTERNAL} external runs')
        if self.external and w.source != 'recorded':
            raise SlamBundleError('external runs belong to recorded drives')
        ids = [rid for rid, _ in self.runs] + [e.id for e in self.external]
        if len(set(ids)) != len(ids) or not all(_ok_id(i) for i in ids):
            raise SlamBundleError(f'run ids must be unique short words: '
                                  f'{ids}')
        n = len(w.t)
        if not 0 < n <= MAX_ROWS:
            raise SlamBundleError('world rows out of range')
        for name, seq in (('gt', w.gt), ('odom', w.odom)):
            if len(seq) != n:
                raise SlamBundleError(f'world.{name} has {len(seq)} rows')
        if any(b <= a for a, b in zip(w.t, w.t[1:])):
            raise SlamBundleError('world.t must strictly increase')
        u = w.updates
        if not u or u[0] != 0 or u[-1] >= n or any(
                b <= a for a, b in zip(u, u[1:])):
            raise SlamBundleError('world.updates must start at 0, strictly '
                                  'increase and index a row')
        nb = w.lidar.samples
        if len(w.ranges) != len(u) or any(len(r) != nb for r in w.ranges):
            raise SlamBundleError(f'world.ranges must be n_updates x {nb}')
        if len(w.observations) != len(u):
            raise SlamBundleError('one observation list per update')
        ids_lm = {lid for lid, _, _ in w.landmarks}
        if any(o[0] not in ids_lm for obs in w.observations for o in obs):
            raise SlamBundleError('an observation names an unknown landmark')
        if w.status not in STATUSES:
            raise SlamBundleError(f'world.status {w.status!r}')
        for rid, tr in self.runs:
            try:
                tr.validate()
            except slam.SlamError as exc:
                raise SlamBundleError(f'run {rid}: {exc}') from None
            if list(tr.columns['row']) != list(u):
                raise SlamBundleError(f"run {rid}: rows are not the world's "
                                      f'update rows')
            if not tr.summary:
                raise SlamBundleError(f'run {rid} is not scored')
        cells = self.lab_map.width * self.lab_map.height
        for e in self.external:
            if len(e.est) != len(u):
                raise SlamBundleError(f'external {e.id}: one pose per update')
            g = e.grid
            if len(e.cells) != g['width'] * g['height'] or \
                    len(e.diff) != cells:
                raise SlamBundleError(f'external {e.id}: map sizes')

    # -- serialisation -----------------------------------------------------

    def arrays(self) -> List[Tuple[str, str, bytes]]:
        """Return ``(name, dtype, little-endian bytes)`` in wire order."""
        w = self.world
        out = [('map.occupancy', 'u8', self.lab_map.occupancy)]
        cols = {
            't': w.t, 'gt_x': [p[0] for p in w.gt],
            'gt_y': [p[1] for p in w.gt], 'gt_yaw': [p[2] for p in w.gt],
            'odom_x': [p[0] for p in w.odom],
            'odom_y': [p[1] for p in w.odom],
            'odom_yaw': [p[2] for p in w.odom],
        }
        for name in WORLD_COLUMNS:
            out.append((f'world.{name}', 'f64', _pack('f64', cols[name])))
        out.append(('world.updates', 'i32', _pack('i32', w.updates)))
        out.append(('world.ranges', 'f64',
                    _pack('f64', [r for scan in w.ranges for r in scan])))
        off, oid, orr, ob = [0], [], [], []
        for obs in w.observations:
            for lid, r, b in obs:
                oid.append(lid)
                orr.append(r)
                ob.append(b)
            off.append(len(oid))
        out += [('world.obs.offset', 'i32', _pack('i32', off)),
                ('world.obs.id', 'i32', _pack('i32', oid)),
                ('world.obs.r', 'f64', _pack('f64', orr)),
                ('world.obs.b', 'f64', _pack('f64', ob))]
        for rid, tr in self.runs:
            for name in sorted(tr.columns):
                dt = 'i32' if name in tr.int_columns else 'f64'
                out.append((f'run.{rid}.col.{name}', dt,
                            _pack(dt, tr.columns[name])))
            for name in sorted(tr.arrays):
                dt, vals = tr.arrays[name]
                out.append((f'run.{rid}.arr.{name}', dt, _pack(dt, vals)))
            out.append((f'run.{rid}.snap.k', 'i32', _pack('i32',
                                                          tr.snapshots)))
            out.append((f'run.{rid}.snap.cells', 'u8', b''.join(tr.maps)))
        for e in self.external:
            for c, i in (('x', 0), ('y', 1), ('yaw', 2)):
                out.append((f'ext.{e.id}.est_{c}', 'f64',
                            _pack('f64', [p[i] for p in e.est])))
            out.append((f'ext.{e.id}.cells', 'u8', bytes(e.cells)))
            out.append((f'ext.{e.id}.err_online', 'f64',
                        _pack('f64', e.err_online)))
            out.append((f'ext.{e.id}.diff', 'u8', bytes(e.diff)))
        return out

    def manifest(self, compression: str = 'none') -> Dict[str, object]:
        """Return the manifest dict, content hash included."""
        if compression not in ('none', 'gzip'):
            raise SlamBundleError('compression must be none or gzip')
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
            'world': {
                'source': w.source, 'status': w.status, 'n_rows': len(w.t),
                'n_updates': len(w.updates), 'lidar': w.lidar.to_dict(),
                'start': list(w.start),
                'landmark_spec': w.landmark_spec.to_dict(),
                'landmarks': [list(lm) for lm in w.landmarks],
                'scenario': None if w.scenario is None
                else w.scenario.to_dict(),
                'recorded': w.recorded,
            },
            'scoring': {'align': self.align, 'tol_m': self.tol,
                        'definitions': 'coco_lab.mapeval'},
            'runs': [{'id': rid, 'header': tr.header,
                      'int_columns': list(tr.int_columns),
                      'arrays': {n: d for n, (d, _) in tr.arrays.items()},
                      'summary': tr.summary} for rid, tr in self.runs],
            'external': [{'id': e.id, 'backend': e.backend, 'arm': e.arm,
                          'grid': e.grid, 'source': e.source,
                          'summary': e.summary} for e in self.external],
            'arrays': table,
            'encoding': {'byte_order': 'little', 'compression': compression},
        }
        manifest = json.loads(_b.canonical_json(manifest))
        manifest['content_hash'] = _b.content_hash(
            manifest, b''.join(d for _, _, d in arrays))
        return manifest

    def to_bytes(self, compression: str = 'none'):
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


def write_slam_bundle(sb: SlamBundle, out_dir: str,
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
        raise SlamBundleError(f'manifest is not JSON: {exc}') from None
    if _b._depth(manifest) > _b.MAX_JSON_DEPTH:
        raise SlamBundleError('manifest nests too deep')
    if not isinstance(manifest, dict):
        raise SlamBundleError('manifest must be an object')
    if manifest.get('schema') != SCHEMA:
        raise SlamBundleError(f'schema is {manifest.get("schema")!r}, not '
                              f'{SCHEMA!r}')
    try:
        major = int(str(manifest.get('version', '')).split('.')[0])
    except ValueError:
        raise SlamBundleError('bad version') from None
    if major != MAJOR:
        raise SlamBundleError(f'map bundle major version {major} is not '
                              f'supported (this reader speaks {MAJOR}.x)')
    for key, kind in (('provenance', dict), ('map', dict), ('world', dict),
                      ('scoring', dict), ('runs', list), ('external', list),
                      ('arrays', list), ('encoding', dict),
                      ('content_hash', str)):
        if not isinstance(manifest.get(key), kind):
            raise SlamBundleError(f'manifest.{key} must be a '
                                  f'{kind.__name__}')
    enc = manifest['encoding']
    if enc.get('byte_order') != 'little' or \
            enc.get('compression') not in ('none', 'gzip'):
        raise SlamBundleError('encoding must be little-endian, none or gzip')
    offset = 0
    for a in manifest['arrays']:
        if not (isinstance(a, dict) and isinstance(a.get('name'), str)
                and a.get('dtype') in DTYPES):
            raise SlamBundleError(f'bad array entry {a!r}')
        for key in ('count', 'offset', 'byte_length'):
            v = a.get(key)
            if not (isinstance(v, int) and not isinstance(v, bool)
                    and v >= 0):
                raise SlamBundleError(f'array {a["name"]}: {key} must be '
                                      f'an int >= 0')
        if a['offset'] != offset:
            raise SlamBundleError(f'array {a["name"]}: not contiguous')
        if a['byte_length'] != a['count'] * DTYPES[a['dtype']][1]:
            raise SlamBundleError(f'array {a["name"]}: byte_length '
                                  f'disagrees with count x dtype')
        offset += a['byte_length']
    if offset > _b.MAX_ARRAY_BYTES:
        raise SlamBundleError(f'arrays total {offset} bytes')
    return manifest


def load_slam_bundle(path: str) -> SlamBundle:
    """Read, bound, decode and validate the bundle directory at ``path``."""
    try:
        with open(os.path.join(path, MANIFEST), 'rb') as f:
            text = f.read(_b.MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise SlamBundleError(f'cannot read the manifest: {exc}') from None
    if len(text) > _b.MAX_MANIFEST_BYTES:
        raise SlamBundleError('manifest too large')
    manifest = parse_manifest(text)
    expected = sum(a['byte_length'] for a in manifest['arrays'])
    gz = manifest['encoding']['compression'] == 'gzip'
    try:
        with open(os.path.join(path, ARRAYS_GZ if gz else ARRAYS), 'rb') as f:
            raw = _b._bounded_gunzip(f, expected) if gz \
                else f.read(expected + 1)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise SlamBundleError(f'cannot read the arrays: {exc}') from None
    return decode(manifest, raw)


def decode(manifest: Dict[str, object], raw: bytes) -> SlamBundle:
    """Build and validate a bundle from a parsed manifest and array bytes."""
    if len(raw) != sum(a['byte_length'] for a in manifest['arrays']):
        raise SlamBundleError('array bytes do not match the table')
    if manifest['content_hash'] != _b.content_hash(manifest, raw):
        raise SlamBundleError('content_hash does not match the content')
    table = {a['name']: a for a in manifest['arrays']}
    if len(table) != len(manifest['arrays']):
        raise SlamBundleError('duplicate array name')
    used = set()

    def take(name, dtype=None):
        a = table.get(name)
        if a is None:
            raise SlamBundleError(f'missing array {name!r}')
        if dtype is not None and a['dtype'] != dtype:
            raise SlamBundleError(f'array {name!r} must be {dtype}')
        used.add(name)
        if a['dtype'] == 'u8':
            return raw[a['offset']:a['offset'] + a['count']]
        code = DTYPES[a['dtype']][0]
        return list(struct.unpack_from(f'<{a["count"]}{code}', raw,
                                       a['offset']))

    try:
        md = manifest['map']
        geo = md['geo']
        lab_map = LabMap(md['width'], md['height'],
                         bytes(take('map.occupancy', 'u8')), map_id=md['id'],
                         resolution=geo['resolution'],
                         origin=tuple(geo['origin']), frame=geo['frame'],
                         meta=md.get('meta'))
    except (KeyError, TypeError, MapError) as exc:
        raise SlamBundleError(f'bad map: {exc}') from None
    if md.get('content_hash') != lab_map.content_hash():
        raise SlamBundleError('map.content_hash does not match the map')
    wm = manifest['world']
    try:
        n = wm['n_rows']
        if not (isinstance(n, int) and 0 < n <= MAX_ROWS):
            raise SlamBundleError('world.n_rows out of range')
        lidar = LidarSpec.from_dict(wm['lidar'])
        spec = mapworld.LandmarkSpec.from_dict(wm['landmark_spec'])
        scenario = None if wm.get('scenario') is None \
            else Scenario.from_dict(wm['scenario'])
        marks = [(int(i), float(x), float(y)) for i, x, y in
                 wm['landmarks']]
        start = tuple(float(v) for v in wm['start'])
    except (KeyError, TypeError, ValueError) as exc:
        raise SlamBundleError(f'bad world: {exc}') from None
    cols = {c: take(f'world.{c}', 'f64') for c in WORLD_COLUMNS}
    if any(len(v) != n for v in cols.values()):
        raise SlamBundleError('world columns disagree with n_rows')
    if not all(math.isfinite(v) for c in cols.values() for v in c):
        raise SlamBundleError('world columns must be finite')
    updates = take('world.updates', 'i32')
    flat = take('world.ranges', 'f64')
    nb = lidar.samples
    if len(flat) != len(updates) * nb:
        raise SlamBundleError('world.ranges is not n_updates x n_beams')
    if any(math.isnan(v) or v < 0 for v in flat):
        raise SlamBundleError('ranges must be >= 0 or inf')
    off = take('world.obs.offset', 'i32')
    oid = take('world.obs.id', 'i32')
    orr = take('world.obs.r', 'f64')
    ob = take('world.obs.b', 'f64')
    if len(off) != len(updates) + 1 or off[0] != 0 or off[-1] != len(oid) \
            or any(b < a for a, b in zip(off, off[1:])) or \
            not len(oid) == len(orr) == len(ob):
        raise SlamBundleError('bad landmark observation arrays')
    if not all(math.isfinite(v) for v in orr + ob):
        raise SlamBundleError('observations must be finite')
    obs: List[List[Observation]] = [
        [(oid[j], orr[j], ob[j]) for j in range(off[i], off[i + 1])]
        for i in range(len(updates))]
    world = mapworld.MapWorld(
        wm.get('source'), cols['t'],
        list(zip(cols['gt_x'], cols['gt_y'], cols['gt_yaw'])),
        list(zip(cols['odom_x'], cols['odom_y'], cols['odom_yaw'])),
        updates, [flat[i * nb:(i + 1) * nb] for i in range(len(updates))],
        lidar, start, spec, marks, obs, wm.get('status'), scenario,
        wm.get('recorded'))
    runs = []
    for r in manifest['runs']:
        if not (isinstance(r, dict) and isinstance(r.get('header'), dict)
                and isinstance(r.get('arrays'), dict)
                and isinstance(r.get('int_columns'), list)):
            raise SlamBundleError('bad run entry')
        rid = r.get('id')
        if not _ok_id(rid):
            raise SlamBundleError(f'bad run id {rid!r}')
        prefix = f'run.{rid}.col.'
        names = sorted(k[len(prefix):] for k in table if k.startswith(prefix))
        ints = tuple(r['int_columns'])
        tcols = {c: take(prefix + c, 'i32' if c in ints else 'f64')
                 for c in names}
        arrs = {}
        for name, dt in r['arrays'].items():
            if dt not in slam.ARRAY_DTYPES:
                raise SlamBundleError(f'run {rid}: dtype {dt!r}')
            v = take(f'run.{rid}.arr.{name}', dt)
            arrs[name] = (dt, list(v))
        snaps = take(f'run.{rid}.snap.k', 'i32')
        cells = take(f'run.{rid}.snap.cells', 'u8')
        g = r['header'].get('grid') or {}
        size = g.get('width', 0) * g.get('height', 0)
        if size <= 0 or len(cells) != size * len(snaps):
            raise SlamBundleError(f'run {rid}: snapshot sizes')
        maps = [bytes(cells[i * size:(i + 1) * size])
                for i in range(len(snaps))]
        runs.append((rid, slam.SlamTrace(dict(r['header']), tcols, ints,
                                         arrs, snaps, maps,
                                         dict(r.get('summary') or {}))))
    ext = []
    cells_truth = lab_map.width * lab_map.height
    for e in manifest['external']:
        try:
            eid = e['id']
            est = list(zip(take(f'ext.{eid}.est_x', 'f64'),
                           take(f'ext.{eid}.est_y', 'f64'),
                           take(f'ext.{eid}.est_yaw', 'f64')))
            ex = ExternalRun(eid, e['backend'], e['arm'], est,
                             bytes(take(f'ext.{eid}.cells', 'u8')),
                             dict(e['grid']), dict(e['source']),
                             dict(e['summary']),
                             take(f'ext.{eid}.err_online', 'f64'),
                             bytes(take(f'ext.{eid}.diff', 'u8')))
        except (KeyError, TypeError) as exc:
            raise SlamBundleError(f'bad external run: {exc}') from None
        if len(ex.diff) != cells_truth:
            raise SlamBundleError(f'external {eid}: diff size')
        ext.append(ex)
    extra = set(table) - used
    if extra:
        raise SlamBundleError(f'unexpected arrays {sorted(extra)[:5]}')
    sc = manifest['scoring']
    sb = SlamBundle(dict(manifest['provenance']), lab_map, world, runs, ext,
                    bool(sc.get('align')), float(sc.get('tol_m',
                                                        mapeval.DEFAULT_TOL)))
    try:
        sb.validate()
    except (slam.SlamError, ValueError) as exc:
        raise SlamBundleError(str(exc)) from None
    return sb


def run_specs(sb: SlamBundle) -> List[Tuple[str, str, object]]:
    """Return ``[(id, algorithm, params)]`` of the bundle's coco_lab runs."""
    return [(rid, tr.algorithm, mapping.params_from_dict(
        tr.algorithm, tr.header['params'])) for rid, tr in sb.runs]


def replay_check(sb: SlamBundle) -> None:
    """
    Recompute and re-score; refuse unless every byte and summary matches.

    A Sketch world is simulated again from its scenario; a recorded world
    is taken as recorded. Every coco_lab run is run again with its
    recorded parameters; every run, external ones too, is scored again.
    """
    w = sb.world
    if w.source == 'sketch':
        w2 = mapworld.from_sketch(sb.lab_map, w.scenario, w.landmark_spec)
    else:
        w2 = w
    ext = [ExternalRun(e.id, e.backend, e.arm, e.est, e.cells, e.grid,
                       e.source) for e in sb.external]
    again = SlamBundle.compute(sb.lab_map, w2, run_specs(sb), sb.provenance,
                               sb.align, ext, sb.tol)
    a = {n: d for n, _, d in sb.arrays()}
    b = {n: d for n, _, d in again.arrays()}
    if a.keys() != b.keys():
        raise SlamBundleError('replay produced different arrays')
    bad = sorted(n for n in a if a[n] != b[n])
    if bad:
        raise SlamBundleError(f'replay differs in {bad[:5]}')
    for (rid, t1), (_, t2) in zip(sb.runs, again.runs):
        if _b.canonical_json(t1.summary) != _b.canonical_json(t2.summary):
            raise SlamBundleError(f'replay: run {rid} summary differs')
    for e1, e2 in zip(sb.external, again.external):
        if _b.canonical_json(e1.summary) != _b.canonical_json(e2.summary):
            raise SlamBundleError(f'replay: external {e1.id} score differs')
