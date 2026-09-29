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
Bundle format v1 (1.0, 1.1): one search run, portable, checkable, replayable.

The normative description is ``docs/labs/BUNDLE_FORMAT.md``; this module is
its reference implementation and the tests pin one to the other.

A bundle is a **directory** holding exactly two files with fixed names:

``manifest.json``
    Canonical JSON: schema and version, provenance, the run's inputs, the
    map's description, the trace's header and summary, the array table,
    the encoding and the content hash.
``arrays.bin`` or ``arrays.bin.gz``
    The trace's event columns and the map's layers as little-endian typed
    arrays, concatenated at the offsets the manifest lists; gzipped
    (``mtime`` 0, so byte-stable) if the manifest says so.

The manifest never names a file, so nothing inside a bundle can steer a
read or a write: :func:`write_bundle` writes those two names into the
directory its caller chose, and :func:`load_bundle` reads those two names
and nothing else.

A bundle is untrusted input. :func:`load_bundle` bounds every size before
it allocates, parses only JSON and fixed-width numbers -- never pickle,
never code -- and validates the trace against the embedded map: every
state in bounds, every parent expanded before its child was pushed, the
path contiguous under the recorded move model, its cost recomputed. It
refuses; it never repairs.

**1.1** (Phase 1C, additive) lets a ``recorded-run`` bundle carry what the
rosbag recorded around the search: a ``recording`` manifest block and
float64 stream arrays (``recording.<group>.<column>``) for the ground-truth
pose, the AMCL pose, the planned path and the wheel commands. A stream
that was not captured is listed in ``recording.missing`` and has no
arrays -- never zero-filled. A bundle without a recording is written as
``1.0``, byte-for-byte what a 1.0 writer produced, so every 1.0 bundle is
also a valid 1.1 bundle. A 1.0 reader refuses a bundle that carries
recording arrays (its array table is exact), with an error, not silently.
"""

from dataclasses import dataclass
import datetime
import gzip
import hashlib
import json
import math
import os
import struct
import subprocess
from typing import Dict, List, Optional, Tuple

from . import __version__
from .maps import LabMap, MapError
from .search import ALGORITHMS, search, TIE_BREAKS
from .trace import COLUMNS, EVENT_KINDS, Trace, TraceError

SCHEMA = 'coco_lab.bundle'
#: What the writer emits for a bundle with no recording (unchanged since
#: 1.0, so 1.0 bundles and the golden fixtures are byte-identical).
VERSION = '1.0'
#: What the writer emits for a recorded-run bundle with a recording.
VERSION_RECORDED = '1.1'
MAJOR = 1

MANIFEST = 'manifest.json'
ARRAYS = 'arrays.bin'
ARRAYS_GZ = 'arrays.bin.gz'

SOURCE_KINDS = ('glass-box', 'recorded-run', 'sketch')

#: Wire types: name -> (struct code, byte size).
DTYPES = {'u8': ('B', 1), 'i32': ('i', 4), 'f64': ('d', 8)}

#: Every trace column's wire type.
TRACE_DTYPES = {
    'kind': 'u8', 'row': 'i32', 'col': 'i32', 'sub': 'i32',
    'g': 'f64', 'h': 'f64', 'f': 'f64',
    'parent_row': 'i32', 'parent_col': 'i32', 'parent_sub': 'i32',
}
assert tuple(TRACE_DTYPES) == COLUMNS

#: Map layers: occupancy always, cost when the map has one.
MAP_ARRAYS = {'map.occupancy': 'u8', 'map.cost': 'f64'}

#: Bundle 1.1 recording streams: group -> columns, all ``f64``, in wire
#: order. ``t`` is seconds on the recording's clock (sim time), and must
#: never decrease. Poses are ``(x, y, yaw)`` in the group's ``frame``;
#: ``cmd`` is ``(t, v, w)``: linear x (m/s) and angular z (rad/s).
RECORDING_GROUPS = {
    'gt': ('t', 'x', 'y', 'yaw'),
    'amcl': ('t', 'x', 'y', 'yaw'),
    'plan': ('x', 'y', 'yaw'),
    'cmd': ('t', 'v', 'w'),
}
RECORDING_KEYS = ('groups', 'missing', 'run_id', 'meta')

#: Resource bounds for an untrusted bundle.
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ARRAY_BYTES = 256 * 1024 * 1024
MAX_EVENTS = 50_000_000
MAX_JSON_DEPTH = 32

#: Graph kinds :func:`replay` can rebuild. ``grid`` is
#: :class:`coco_lab.grid.Grid`; ``heading_grid`` is
#: :class:`coco_lab.heading.HeadingGrid`.
GRAPH_KINDS = ('grid', 'heading_grid')

#: Relative tolerance when a recomputed path cost is compared with the
#: recorded one: the same edges summed in the same order give the same
#: float, so this only absorbs a different summation order.
COST_REL_TOL = 1e-9


class BundleError(ValueError):
    """A bundle that does not conform to the format, or fails a check."""


@dataclass
class Bundle:
    """One run: its provenance, inputs, map and trace."""

    provenance: Dict[str, object]
    run: Dict[str, object]
    lab_map: LabMap
    trace: Trace
    #: 1.1: ``{groups, missing, run_id, meta}`` or None (see
    #: :func:`_check_recording`).
    recording: Optional[Dict[str, object]] = None
    #: 1.1: ``{group: {column: [float, ...]}}`` for every present group.
    streams: Optional[Dict[str, Dict[str, List[float]]]] = None

    # -- construction ------------------------------------------------------

    @classmethod
    def from_run(cls, result, lab_map: LabMap, run: Dict[str, object],
                 provenance: Dict[str, object]) -> 'Bundle':
        """
        Bundle a :class:`coco_lab.search.SearchResult`.

        ``run`` holds the inputs the trace header does not: ``start`` and
        ``goal`` cells, and ``model``, the move model given to
        :meth:`LabMap.to_grid` (or to the heading graph) including the
        unknown-cell policy. The map hash is taken from ``lab_map``.
        ``provenance`` must pass the :func:`make_provenance` checks.
        """
        b = cls(dict(provenance), _run_block(result.trace, run, lab_map),
                lab_map, result.trace)
        b.validate()
        return b

    # -- the graph the trace was searched on --------------------------------

    def graph(self):
        """Rebuild the searched graph from the map and the recorded run."""
        model = self.run['model']
        kind = self.run['graph']['kind']
        if kind == 'grid':
            return self.lab_map.to_grid(**model)
        if kind == 'heading_grid':
            from .heading import HeadingGrid
            return HeadingGrid.from_map(self.lab_map, self.run['start'],
                                        self.run['goal'], **model)
        raise BundleError(f'graph kind {kind!r} cannot be rebuilt; '
                          f'supported: {GRAPH_KINDS}')

    # -- checks ------------------------------------------------------------

    def validate(self) -> None:
        """Raise :class:`BundleError` unless every check passes."""
        _check_provenance(self.provenance)
        try:
            self.trace.validate()
        except TraceError as exc:
            raise BundleError(f'trace: {exc}') from None
        _check_run(self.run, self.trace)
        if self.run['map_hash'] != self.lab_map.content_hash():
            raise BundleError(
                f'run.map_hash {self.run["map_hash"]!r} is not the '
                f'embedded map ({self.lab_map.content_hash()})')
        _check_trace_on_graph(self, self.graph())
        _check_recording(self)

    @property
    def version(self) -> str:
        """Return the version this bundle is written as."""
        return VERSION_RECORDED if self.recording is not None else VERSION

    # -- serialisation -----------------------------------------------------

    def arrays(self) -> List[Tuple[str, str, bytes]]:
        """Return ``(name, dtype, little-endian bytes)`` in wire order."""
        out = []
        for name in COLUMNS:
            dtype = TRACE_DTYPES[name]
            code, _ = DTYPES[dtype]
            values = self.trace.events[name]
            out.append((f'trace.{name}', dtype,
                        struct.pack(f'<{len(values)}{code}', *values)))
        out.append(('map.occupancy', 'u8', self.lab_map.occupancy))
        if self.lab_map.cost is not None:
            out.append(('map.cost', 'f64',
                        struct.pack(f'<{len(self.lab_map.cost)}d',
                                    *self.lab_map.cost)))
        for group, column in recording_arrays(self.recording):
            values = self.streams[group][column]
            out.append((f'recording.{group}.{column}', 'f64',
                        struct.pack(f'<{len(values)}d', *values)))
        return out

    def manifest(self, compression: str = 'none') -> Dict[str, object]:
        """Return the manifest dict, content hash included."""
        if compression not in ('none', 'gzip'):
            raise BundleError(f'compression must be none or gzip, '
                              f'got {compression!r}')
        table, offset = [], 0
        for name, dtype, data in self.arrays():
            size = DTYPES[dtype][1]
            table.append({'name': name, 'dtype': dtype,
                          'count': len(data) // size, 'offset': offset,
                          'byte_length': len(data)})
            offset += len(data)
        m = self.lab_map
        manifest = {
            'schema': SCHEMA,
            'version': self.version,
            'provenance': dict(self.provenance),
            'run': dict(self.run),
            'map': {
                'id': m.id, 'content_hash': m.content_hash(),
                'width': m.width, 'height': m.height,
                'cost_layer': m.cost is not None,
                'geo': None if not m.has_geo else {
                    'resolution': m.resolution, 'origin': list(m.origin),
                    'frame': m.frame},
                'meta': dict(m.meta),
            },
            'trace': {'header': dict(self.trace.header),
                      'summary': dict(self.trace.summary)},
            'arrays': table,
            'encoding': {'byte_order': 'little', 'compression': compression},
        }
        if self.recording is not None:
            manifest['recording'] = json.loads(canonical_json(
                self.recording))
        manifest['content_hash'] = content_hash(
            manifest, b''.join(d for _, _, d in self.arrays()))
        return manifest


# -- the content hash --------------------------------------------------------

def content_hash(manifest: Dict[str, object], raw_arrays: bytes) -> str:
    """
    Return ``'sha256:<hex>'`` over a bundle's content.

    The hashed bytes are the canonical JSON (sorted keys, no whitespace,
    UTF-8) of the manifest with ``content_hash``, ``encoding`` and
    ``provenance.created_utc`` removed, then a newline, then the
    UNCOMPRESSED array bytes. Two bundles of one run made at different
    times, or one gzipped and one not, therefore have the same hash.
    """
    m = {k: v for k, v in manifest.items()
         if k not in ('content_hash', 'encoding')}
    m['provenance'] = {k: v for k, v in manifest['provenance'].items()
                       if k != 'created_utc'}
    text = json.dumps(m, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)
    h = hashlib.sha256(text.encode('utf-8'))
    h.update(b'\n')
    h.update(raw_arrays)
    return 'sha256:' + h.hexdigest()


# -- provenance --------------------------------------------------------------

def make_provenance(source_kind: str, *, seed: Optional[int] = None,
                    git: Optional[Dict[str, object]] = None,
                    episode_spec_hash: Optional[str] = None,
                    rosbag: Optional[Dict[str, object]] = None,
                    created_utc: Optional[str] = None,
                    tool: Optional[str] = None) -> Dict[str, object]:
    """
    Return a provenance block, checked.

    ``git`` is :func:`git_provenance`'s result or ``None`` (then both
    fields are ``null``: unknown, never guessed). ``rosbag`` --
    ``{sha256, sim_time_start, sim_time_end}`` -- is required for a
    ``recorded-run`` and refused otherwise. ``created_utc`` defaults to
    now, ISO 8601 with a ``Z``.
    """
    if created_utc is None:
        created_utc = (datetime.datetime.now(datetime.timezone.utc)
                       .strftime('%Y-%m-%dT%H:%M:%SZ'))
    git = git or {}
    p = {
        'source_kind': source_kind,
        'coco_lab_version': __version__,
        'git_commit': git.get('commit'),
        'git_dirty': git.get('dirty'),
        'created_utc': created_utc,
        'seed': seed,
        'episode_spec_hash': episode_spec_hash,
        'rosbag': rosbag,
        'tool': tool,
    }
    _check_provenance(p)
    return p


def git_provenance(path: str) -> Optional[Dict[str, object]]:
    """
    Return ``{commit, dirty}`` for the git work tree at ``path``.

    ``None`` when git or the repository is unavailable -- the caller then
    records ``null`` rather than a guess.
    """
    def git(*args):
        return subprocess.run(['git', '-C', path, *args],
                              capture_output=True, text=True, timeout=10,
                              check=True).stdout.strip()
    try:
        commit = git('rev-parse', 'HEAD')
        dirty = bool(git('status', '--porcelain', '--untracked-files=no'))
    except (OSError, subprocess.SubprocessError):
        return None
    return {'commit': commit, 'dirty': dirty}


def _check_provenance(p) -> None:
    if not isinstance(p, dict):
        raise BundleError('provenance must be an object')
    kind = p.get('source_kind')
    if kind not in SOURCE_KINDS:
        raise BundleError(f'provenance.source_kind {kind!r} not in '
                          f'{SOURCE_KINDS}')
    for key in ('coco_lab_version', 'created_utc'):
        if not isinstance(p.get(key), str) or not p[key]:
            raise BundleError(f'provenance.{key} must be a non-empty '
                              f'string')
    try:
        datetime.datetime.strptime(p['created_utc'], '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        raise BundleError(f'provenance.created_utc {p["created_utc"]!r} is '
                          f'not YYYY-MM-DDTHH:MM:SSZ') from None
    commit = p.get('git_commit')
    if commit is not None and not (isinstance(commit, str) and len(commit)
                                   == 40 and all(c in '0123456789abcdef'
                                                 for c in commit)):
        raise BundleError(f'provenance.git_commit {commit!r} is not a '
                          f'40-hex SHA or null')
    if p.get('git_dirty') not in (None, True, False):
        raise BundleError('provenance.git_dirty must be a bool or null')
    if (commit is None) != (p.get('git_dirty') is None):
        raise BundleError('git_commit and git_dirty are both known or both '
                          'null')
    seed = p.get('seed')
    if seed is not None and not (isinstance(seed, int)
                                 and not isinstance(seed, bool)):
        raise BundleError('provenance.seed must be an int or null')
    for key in ('episode_spec_hash', 'tool'):
        if p.get(key) is not None and not isinstance(p[key], str):
            raise BundleError(f'provenance.{key} must be a string or null')
    bag = p.get('rosbag')
    if kind == 'recorded-run':
        if not isinstance(bag, dict):
            raise BundleError('a recorded-run needs provenance.rosbag')
        if not (isinstance(bag.get('sha256'), str)
                and len(bag['sha256']) == 64):
            raise BundleError('provenance.rosbag.sha256 must be 64 hex')
        t0, t1 = bag.get('sim_time_start'), bag.get('sim_time_end')
        if not (_num(t0) and _num(t1) and t0 <= t1):
            raise BundleError('provenance.rosbag sim_time_start <= '
                              'sim_time_end, both finite')
    elif bag is not None:
        raise BundleError(f'provenance.rosbag is only for a recorded-run, '
                          f'not {kind!r}')


def _num(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


# -- the run block ------------------------------------------------------------

#: Move-model keys each graph kind accepts, and nothing else.
MODEL_KEYS = {
    'grid': ('connectivity', 'diagonal_cost', 'corner_cutting',
             'cost_weight', 'cost_scale', 'unknown'),
    'heading_grid': ('turn_penalty', 'corner_cutting', 'unknown'),
}


def _run_block(trace: Trace, run: Dict[str, object],
               lab_map: LabMap) -> Dict[str, object]:
    h = trace.header
    return {
        'algorithm': h['algorithm'],
        'heuristic': h['heuristic'],
        'weight': h['weight'],
        'tie_break': h['tie_break'],
        'start': list(run['start']),
        'goal': list(run['goal']),
        'graph': dict(h['graph']),
        'model': dict(run.get('model', {})),
        'map_hash': lab_map.content_hash(),
    }


# -- graph adapters ----------------------------------------------------------
#
# A plain grid's state IS its cell; a heading graph has start and goal
# states distinct from their cells. These adapters let the checks and the
# replay treat both alike without adding methods to Grid.

def start_state(graph, cell):
    """Return the state a search from ``cell`` starts in."""
    f = getattr(graph, 'start_state', None)
    return f(tuple(cell)) if f else tuple(cell)


def goal_state(graph, cell):
    """Return the state a search to ``cell`` ends in."""
    f = getattr(graph, 'goal_state', None)
    return f(tuple(cell)) if f else tuple(cell)


def state_at(graph, loc):
    """Return the state drawn at ``(row, col, sub)``, or ``None``."""
    f = getattr(graph, 'state_at', None)
    if f:
        return f(tuple(loc))
    return (loc[0], loc[1]) if loc[2] == 0 else None


def _check_run(run, trace: Trace) -> None:
    if not isinstance(run, dict):
        raise BundleError('run must be an object')
    for key in ('algorithm', 'heuristic', 'weight', 'tie_break', 'start',
                'goal', 'graph', 'model', 'map_hash'):
        if key not in run:
            raise BundleError(f'run has no {key!r}')
    if run['algorithm'] not in ALGORITHMS:
        raise BundleError(f'run.algorithm {run["algorithm"]!r} unknown')
    if run['tie_break'] not in TIE_BREAKS:
        raise BundleError(f'run.tie_break {run["tie_break"]!r} unknown')
    w = run['weight']
    if run['algorithm'] == 'weighted_astar':
        if not (_num(w) and w >= 0):
            raise BundleError('weighted_astar needs a finite weight >= 0')
    elif w is not None:
        raise BundleError('weight is only for weighted_astar')
    for key in ('start', 'goal'):
        cell = run[key]
        if not (isinstance(cell, list) and len(cell) == 2 and all(
                isinstance(v, int) and not isinstance(v, bool)
                for v in cell)):
            raise BundleError(f'run.{key} must be [row, col]')
    graph, model = run['graph'], run['model']
    if not isinstance(graph, dict) or graph.get('kind') not in GRAPH_KINDS:
        raise BundleError(f'run.graph.kind must be one of {GRAPH_KINDS}')
    if not isinstance(model, dict):
        raise BundleError('run.model must be an object')
    extra = set(model) - set(MODEL_KEYS[graph['kind']])
    if extra:
        raise BundleError(f'run.model has unknown keys {sorted(extra)}')
    h = trace.header
    for key in ('algorithm', 'heuristic', 'weight', 'tie_break', 'graph'):
        if h.get(key) != run[key]:
            raise BundleError(f'run.{key} {run[key]!r} disagrees with the '
                              f'trace header ({h.get(key)!r})')


# -- the 1.1 recording -----------------------------------------------------------

def recording_arrays(recording) -> List[Tuple[str, str]]:
    """Return ``(group, column)`` of every recording array, in wire order."""
    if recording is None:
        return []
    present = recording.get('groups') or {}
    return [(g, c) for g, cols in RECORDING_GROUPS.items() if g in present
            for c in cols]


def _check_recording(bundle: 'Bundle') -> None:
    rec, streams = bundle.recording, bundle.streams
    if rec is None:
        if streams:
            raise BundleError('streams without a recording block')
        return
    if bundle.provenance.get('source_kind') != 'recorded-run':
        raise BundleError('only a recorded-run bundle carries a recording')
    if not isinstance(rec, dict) or set(rec) != set(RECORDING_KEYS):
        raise BundleError(f'recording must have exactly the keys '
                          f'{list(RECORDING_KEYS)}')
    groups, missing = rec['groups'], rec['missing']
    if not isinstance(groups, dict) or not isinstance(missing, list):
        raise BundleError('recording.groups is an object, .missing a list')
    known = set(RECORDING_GROUPS)
    if set(groups) - known or set(missing) - known:
        raise BundleError(f'unknown recording groups; known: '
                          f'{sorted(known)}')
    if set(groups) & set(missing) or \
            set(groups) | set(missing) != known or \
            len(missing) != len(set(missing)):
        raise BundleError('every recording group is present or listed in '
                          'recording.missing, exactly once')
    if not (isinstance(rec['run_id'], str)
            and isinstance(rec['meta'], dict)):
        raise BundleError('recording.run_id is a string, .meta an object')
    streams = streams or {}
    if set(streams) != set(groups):
        raise BundleError('streams must hold exactly the present groups')
    for g, info in groups.items():
        if not (isinstance(info, dict) and isinstance(info.get('frame'), str)
                and isinstance(info.get('source'), str)
                and isinstance(info.get('count'), int)
                and not isinstance(info.get('count'), bool)):
            raise BundleError(f'recording.groups.{g} needs frame, source '
                              f'(strings) and count (int)')
        cols = streams[g]
        if not isinstance(cols, dict) or set(cols) != \
                set(RECORDING_GROUPS[g]):
            raise BundleError(f'stream {g} must have exactly the columns '
                              f'{list(RECORDING_GROUPS[g])}')
        lengths = {len(v) for v in cols.values()}
        if lengths != {info['count']}:
            raise BundleError(f'stream {g}: columns disagree with count '
                              f'{info["count"]}')
        for c, values in cols.items():
            if not all(_num(v) for v in values):
                raise BundleError(f'stream {g}.{c} holds a non-finite value')
        t = cols.get('t')
        if t is not None and any(b < a for a, b in zip(t, t[1:])):
            raise BundleError(f'stream {g}.t decreases')


# -- trace-on-graph checks -----------------------------------------------------

def _check_trace_on_graph(bundle: Bundle, graph) -> None:
    """Check the trace's events and path against the rebuilt graph."""
    ev, trace = bundle.trace.events, bundle.trace
    start, goal = tuple(bundle.run['start']), tuple(bundle.run['goal'])
    m = bundle.lab_map
    for key, cell in (('start', start), ('goal', goal)):
        if not m.in_bounds(cell):
            raise BundleError(f'run.{key} {list(cell)} is outside the map')
    if graph.describe() != trace.header['graph']:
        raise BundleError('the rebuilt graph does not match the trace '
                          "header's graph block")
    s0, g0 = start_state(graph, start), goal_state(graph, goal)
    if not graph.is_valid(s0):
        raise BundleError(f'run.start {list(start)} is blocked')
    if not graph.is_valid(g0):
        raise BundleError(f'run.goal {list(goal)} is blocked')
    if list(graph.locate(s0)) != trace.header['start'] or \
            list(graph.locate(g0)) != trace.header['goal']:
        raise BundleError('trace header start/goal disagree with run')

    pushed, expanded = set(), set()
    path: List[tuple] = []
    for i in range(len(trace)):
        kind = EVENT_KINDS[ev['kind'][i]]
        loc = (ev['row'][i], ev['col'][i], ev['sub'][i])
        par = (ev['parent_row'][i], ev['parent_col'][i],
               ev['parent_sub'][i])
        if not m.in_bounds(loc[:2]):
            raise BundleError(f'event {i}: {list(loc)} is outside the map')
        if kind == 'path':
            path.append((loc, par, ev['g'][i]))
            continue
        if kind == 'push':
            if not pushed and loc != tuple(trace.header['start']):
                raise BundleError('the first push is not the start')
            pushed.add(loc)
        elif loc not in pushed:
            raise BundleError(f'event {i}: {kind} of {list(loc)}, which '
                              f'was never pushed')
        elif loc in expanded:
            raise BundleError(f'event {i}: {kind} of {list(loc)} after it '
                              f'was closed')
        if kind == 'expand':
            expanded.add(loc)
        elif par != (-1, -1, -1) and par not in expanded:
            raise BundleError(
                f'event {i}: {kind} of {list(loc)} names parent '
                f'{list(par)}, which was not expanded before it')

    if not path:
        return
    states = {graph.locate(s): s for s in _path_states(graph, path)}
    prev = None
    total = 0.0
    for j, (loc, par, g) in enumerate(path):
        s = states[loc]
        if j == 0:
            if s != s0 or par != (-1, -1, -1):
                raise BundleError('path does not begin at the start')
        else:
            if par != graph.locate(prev):
                raise BundleError(f'path event {j}: parent {list(par)} is '
                                  f'not the previous path state')
            if s not in set(graph.neighbours(prev)):
                raise BundleError(f'path step {j}: {list(loc)} is not a '
                                  f'neighbour of {list(graph.locate(prev))}')
            total += graph.edge_cost(prev, s)
        if not _close(total, g):
            raise BundleError(f'path event {j}: g={g} but the edges sum to '
                              f'{total}')
        prev = s
    if prev != g0:
        raise BundleError('path does not end at the goal')
    recorded = trace.summary['path_cost']
    if not _close(total, recorded):
        raise BundleError(f'summary.path_cost={recorded} but the path costs '
                          f'{total} on the recorded map and move model')


def _path_states(graph, path):
    for loc, _, _ in path:
        s = state_at(graph, loc)
        if s is None or not graph.is_valid(s):
            raise BundleError(f'path state {list(loc)} is not a free state')
        yield s


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= COST_REL_TOL * max(1.0, abs(a), abs(b))


# -- files ---------------------------------------------------------------------

def write_bundle(bundle: Bundle, out_dir: str,
                 compression: str = 'none') -> str:
    """
    Write ``bundle`` into the directory ``out_dir`` and return its path.

    Creates ``out_dir`` if needed and writes exactly ``manifest.json`` and
    ``arrays.bin`` (or ``arrays.bin.gz``) inside it -- nothing else, and
    never outside it. An existing bundle in ``out_dir`` is refused rather
    than overwritten.
    """
    bundle.validate()
    manifest = bundle.manifest(compression)
    raw = b''.join(d for _, _, d in bundle.arrays())
    os.makedirs(out_dir, exist_ok=True)
    for name in (MANIFEST, ARRAYS, ARRAYS_GZ):
        if os.path.lexists(os.path.join(out_dir, name)):
            raise BundleError(f'{out_dir} already holds {name}')
    if compression == 'gzip':
        data, name = gzip.compress(raw, compresslevel=9, mtime=0), ARRAYS_GZ
    else:
        data, name = raw, ARRAYS
    with open(os.path.join(out_dir, name), 'xb') as f:
        f.write(data)
    with open(os.path.join(out_dir, MANIFEST), 'x', encoding='utf-8') as f:
        f.write(canonical_json(manifest))
    return out_dir


def canonical_json(obj) -> str:
    """Return sorted-key, compact, NaN-free JSON."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def load_bundle(path: str) -> Bundle:
    """
    Read, bound, decode and validate the bundle directory at ``path``.

    Raises :class:`BundleError` for anything that does not conform.
    """
    mpath = os.path.join(path, MANIFEST)
    try:
        with open(mpath, 'rb') as f:
            text = f.read(MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise BundleError(f'cannot read {mpath}: {exc}') from None
    if len(text) > MAX_MANIFEST_BYTES:
        raise BundleError(f'manifest exceeds {MAX_MANIFEST_BYTES} bytes')
    manifest = parse_manifest(text)
    compression = manifest['encoding']['compression']
    name = ARRAYS_GZ if compression == 'gzip' else ARRAYS
    total = sum(a['byte_length'] for a in manifest['arrays'])
    try:
        with open(os.path.join(path, name), 'rb') as f:
            if compression == 'gzip':
                raw = _bounded_gunzip(f, total)
            else:
                raw = f.read(total + 1)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise BundleError(f'cannot read {name}: {exc}') from None
    return decode(manifest, raw)


def _bounded_gunzip(f, expected: int) -> bytes:
    """Decompress at most ``expected + 1`` bytes: a gzip bomb stops here."""
    out = bytearray()
    with gzip.GzipFile(fileobj=f, mode='rb') as gz:
        while len(out) <= expected:
            chunk = gz.read(min(1 << 20, expected + 1 - len(out)))
            if not chunk:
                break
            out += chunk
    return bytes(out)


def parse_manifest(text: bytes) -> Dict[str, object]:
    """Parse and structurally check a manifest; refuse an unknown MAJOR."""
    try:
        manifest = json.loads(text.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise BundleError(f'manifest is not JSON: {exc}') from None
    if _depth(manifest) > MAX_JSON_DEPTH:
        raise BundleError(f'manifest nests deeper than {MAX_JSON_DEPTH}')
    if not isinstance(manifest, dict):
        raise BundleError('manifest must be an object')
    if manifest.get('schema') != SCHEMA:
        raise BundleError(f'schema is {manifest.get("schema")!r}, '
                          f'not {SCHEMA!r}')
    version = str(manifest.get('version', ''))
    try:
        major = int(version.split('.')[0])
    except ValueError:
        raise BundleError(f'bad bundle version {version!r}') from None
    if major != MAJOR:
        raise BundleError(f'bundle major version {major} is not supported '
                          f'(this reader speaks {MAJOR}.x)')
    for key, kind in (('provenance', dict), ('run', dict), ('map', dict),
                      ('trace', dict), ('arrays', list), ('encoding', dict),
                      ('content_hash', str)):
        if not isinstance(manifest.get(key), kind):
            raise BundleError(f'manifest.{key} must be a '
                              f'{kind.__name__}')
    enc = manifest['encoding']
    if enc.get('byte_order') != 'little':
        raise BundleError('encoding.byte_order must be little')
    if enc.get('compression') not in ('none', 'gzip'):
        raise BundleError('encoding.compression must be none or gzip')
    offset = 0
    for a in manifest['arrays']:
        if not (isinstance(a, dict) and isinstance(a.get('name'), str)
                and a.get('dtype') in DTYPES):
            raise BundleError(f'bad array entry {a!r}')
        for key in ('count', 'offset', 'byte_length'):
            v = a.get(key)
            if not (isinstance(v, int) and not isinstance(v, bool)
                    and v >= 0):
                raise BundleError(f'array {a["name"]}: {key} must be an '
                                  f'int >= 0')
        if a['offset'] != offset:
            raise BundleError(f'array {a["name"]}: offset {a["offset"]}, '
                              f'expected {offset} (arrays are contiguous)')
        if a['byte_length'] != a['count'] * DTYPES[a['dtype']][1]:
            raise BundleError(f'array {a["name"]}: byte_length disagrees '
                              f'with count x dtype')
        offset += a['byte_length']
    if offset > MAX_ARRAY_BYTES:
        raise BundleError(f'arrays total {offset} bytes, over '
                          f'{MAX_ARRAY_BYTES}')
    return manifest


def _depth(obj, level: int = 1) -> int:
    if level > MAX_JSON_DEPTH:
        return level
    if isinstance(obj, dict):
        return max([level] + [_depth(v, level + 1) for v in obj.values()])
    if isinstance(obj, list):
        return max([level] + [_depth(v, level + 1) for v in obj])
    return level


def decode(manifest: Dict[str, object], raw: bytes) -> Bundle:
    """Build and validate a bundle from a parsed manifest and array bytes."""
    table = {a['name']: a for a in manifest['arrays']}
    expected = [f'trace.{c}' for c in COLUMNS] + ['map.occupancy']
    if manifest['map'].get('cost_layer'):
        expected.append('map.cost')
    recording = manifest.get('recording')
    try:
        minor = int(str(manifest['version']).split('.')[1])
    except (IndexError, ValueError):
        raise BundleError(f'bad bundle version {manifest["version"]!r}') \
            from None
    if recording is not None:
        if minor < 1:
            raise BundleError('a recording needs bundle version 1.1 or '
                              'later')
        if not isinstance(recording, dict) or not isinstance(
                recording.get('groups'), dict):
            raise BundleError('recording.groups must be an object')
        expected += [f'recording.{g}.{c}'
                     for g, c in recording_arrays(recording)]
    if list(table) != expected:
        raise BundleError(f'arrays must be exactly {expected}, in order; '
                          f'got {list(table)}')
    total = sum(a['byte_length'] for a in manifest['arrays'])
    if len(raw) != total:
        raise BundleError(f'array data is {len(raw)} bytes, the manifest '
                          f'lists {total} (truncated or padded)')
    declared = manifest['content_hash']
    actual = content_hash(manifest, raw)
    if declared != actual:
        raise BundleError(f'content_hash {declared} does not match the '
                          f'content ({actual})')

    def column(name):
        a = table[name]
        if name.startswith('trace.'):
            want = TRACE_DTYPES.get(name[6:])
        elif name.startswith('recording.'):
            want = 'f64'
        else:
            want = MAP_ARRAYS[name]
        if a['dtype'] != want:
            raise BundleError(f'array {name}: dtype {a["dtype"]}, expected '
                              f'{want}')
        code = DTYPES[a['dtype']][0]
        chunk = raw[a['offset']:a['offset'] + a['byte_length']]
        return list(struct.unpack(f'<{a["count"]}{code}', chunk))

    counts = {table[f'trace.{c}']['count'] for c in COLUMNS}
    if len(counts) != 1:
        raise BundleError('trace columns differ in length')
    if counts.pop() > MAX_EVENTS:
        raise BundleError(f'more than {MAX_EVENTS} events')
    events = {c: column(f'trace.{c}') for c in COLUMNS}
    for c in ('g', 'h', 'f'):
        if not all(math.isfinite(v) for v in events[c]):
            raise BundleError(f'trace column {c} holds a non-finite value')

    md = manifest['map']
    try:
        geo = md.get('geo')
        lab_map = LabMap(
            md.get('width'), md.get('height'),
            raw[table['map.occupancy']['offset']:
                table['map.occupancy']['offset']
                + table['map.occupancy']['byte_length']],
            column('map.cost') if 'map.cost' in table else None,
            map_id=md.get('id', ''),
            resolution=None if geo is None else geo.get('resolution'),
            origin=None if geo is None else tuple(geo.get('origin') or ()),
            frame=None if geo is None else geo.get('frame'),
            meta=md.get('meta'))
    except (MapError, TypeError, AttributeError) as exc:
        raise BundleError(f'map: {exc}') from None
    if table['map.occupancy']['dtype'] != 'u8':
        raise BundleError('map.occupancy must be u8')
    if md.get('content_hash') != lab_map.content_hash():
        raise BundleError('map.content_hash does not match the embedded '
                          'map')
    tr = manifest['trace']
    try:
        trace = Trace(dict(tr['header']), events, dict(tr['summary']))
    except (KeyError, TypeError) as exc:
        raise BundleError(f'trace: missing {exc}') from None
    streams = None
    if recording is not None:
        streams = {}
        for g, c in recording_arrays(recording):
            streams.setdefault(g, {})[c] = column(f'recording.{g}.{c}')
    bundle = Bundle(dict(manifest['provenance']), dict(manifest['run']),
                    lab_map, trace, recording, streams)
    bundle.validate()
    return bundle


# -- replay ----------------------------------------------------------------------

@dataclass
class Replay:
    """What :func:`replay` found."""

    reproduced: bool
    first_divergence: Optional[int]
    detail: str


def replay(bundle: Bundle) -> Replay:
    """
    Rerun a glass-box bundle's search and compare traces exactly.

    Only a ``glass-box`` bundle carries every input of its search (a
    recorded run's trace came from a planner on a live costmap), so any
    other source kind is refused with :class:`BundleError` rather than
    reported as "not reproduced".
    """
    kind = bundle.provenance['source_kind']
    if kind != 'glass-box':
        raise BundleError(f'only glass-box bundles can be replayed, not '
                          f'{kind!r}: their inputs are not all recorded')
    graph = bundle.graph()
    run = bundle.run
    result = search(graph, start_state(graph, run['start']),
                    goal_state(graph, run['goal']),
                    run['algorithm'], run['heuristic'],
                    weight=run['weight'], tie_break=run['tie_break'])
    new, old = result.trace, bundle.trace
    if new.header != old.header:
        return Replay(False, None, 'trace headers differ')
    n = min(len(new), len(old))
    for i in range(n):
        if any(new.events[c][i] != old.events[c][i] for c in COLUMNS):
            return Replay(False, i, f'event {i} differs')
    if len(new) != len(old):
        return Replay(False, n, f'{len(new)} events now, {len(old)} '
                                f'recorded')
    if new.summary != old.summary:
        return Replay(False, None, 'summaries differ')
    return Replay(True, None, f'all {len(old)} events identical')
