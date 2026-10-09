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
coco_lab's v1 traces <-> v2 messages, with nothing lost.

A v1 search trace (``coco_lab.trace``: header, ten event columns, summary;
the dict :meth:`Trace.to_dict` returns) becomes ``SearchHeader`` +
``SearchEventBatch`` + ``SearchSummary``; :func:`search_to_v1` gives back a
dict equal to the original, value for value and type for type (int stays
int, float stays float, ``None`` stays ``None``). A D* Lite trace
(``coco_lab.dstarlite.ReplanTrace`` columns) becomes an
``IncrementalEventBatch``, with v1's ``-1`` infinity sentinel as IEEE
``+inf``, and back.

The clocks: a v1 trace has none. Converted events get ``seq`` 0..n-1 (the
event order), and the ``tick`` / ``t_world`` the caller passes (one search
runs within one control tick).
"""

import math
from typing import Dict

from .gen.coco.common.v1 import common_pb2
from .gen.coco.plan.v1 import incremental_pb2, search_pb2

#: v1 column order (coco_lab.trace.COLUMNS) and kinds (EVENT_KINDS).
SEARCH_COLUMNS = ('kind', 'row', 'col', 'sub', 'g', 'h', 'f',
                  'parent_row', 'parent_col', 'parent_sub')
SEARCH_KINDS = ('push', 'expand', 'relax', 'path')
STATUSES = {'found': search_pb2.SEARCH_STATUS_FOUND,
            'no_path': search_pb2.SEARCH_STATUS_NO_PATH}
INCREMENTAL_COLUMNS = ('kind', 'row', 'col', 'sub', 'g', 'rhs', 'round')
INCREMENTAL_KINDS = ('expand', 'raise', 'update', 'change', 'path', 'move')
INF_SENTINEL = -1.0


# -- scalars and params -----------------------------------------------------

def scalar(v) -> common_pb2.Scalar:
    """Wrap a Python scalar, keeping its type."""
    if isinstance(v, bool):
        return common_pb2.Scalar(bool_value=v)
    if isinstance(v, int):
        return common_pb2.Scalar(int_value=v)
    if isinstance(v, float):
        return common_pb2.Scalar(double_value=v)
    if isinstance(v, str):
        return common_pb2.Scalar(string_value=v)
    raise TypeError(f'not a scalar: {v!r} ({type(v).__name__})')


def unscalar(s: common_pb2.Scalar):
    """Unwrap a Scalar into the Python value it was made from."""
    which = s.WhichOneof('value')
    if which is None:
        raise ValueError('empty Scalar')
    return getattr(s, which)


def params(d: Dict[str, object]) -> common_pb2.Params:
    """Encode a flat dict, in its own key order."""
    return common_pb2.Params(items=[common_pb2.Param(key=k, value=scalar(v))
                                    for k, v in d.items()])


def unparams(p: common_pb2.Params) -> Dict[str, object]:
    """Decode Params back into a dict, in the stored order."""
    out = {}
    for item in p.items:
        if item.key in out:
            raise ValueError(f'duplicate key {item.key!r}')
        out[item.key] = unscalar(item.value)
    return out


def loc(v) -> common_pb2.Loc:
    """Encode a v1 location ``[row, col, sub]``."""
    r, c, s = v
    return common_pb2.Loc(row=r, col=c, sub=s)


def unloc(m: common_pb2.Loc):
    """Decode a Loc into v1's ``[row, col, sub]``."""
    return [m.row, m.col, m.sub]


# -- search -----------------------------------------------------------------

def search_from_v1(trace: Dict[str, object], search_id: int = 0,
                   tick: int = 0, t_world: float = 0.0):
    """Return ``(SearchHeader, SearchEventBatch, SearchSummary)``."""
    h, ev, sm = trace['header'], trace['events'], trace['summary']
    known = {'schema', 'version', 'algorithm', 'heuristic', 'weight',
             'tie_break', 'start', 'goal', 'graph'}
    if set(h) - known:
        raise ValueError(f'header fields v2 does not carry: {set(h) - known}')
    header = search_pb2.SearchHeader(
        search_id=search_id, source_schema=h['schema'],
        source_version=h['version'], algorithm=h['algorithm'],
        heuristic=h['heuristic'], tie_break=h['tie_break'],
        start=loc(h['start']), goal=loc(h['goal']), graph=params(h['graph']),
        tick=tick, t_world=t_world)
    if h['weight'] is not None:
        header.weight = h['weight']
    n = len(ev['kind'])
    events = search_pb2.SearchEventBatch(
        search_id=search_id, seq=range(n), tick=[tick] * n,
        t_world=[t_world] * n, kind=[k + 1 for k in ev['kind']])
    for name in SEARCH_COLUMNS[1:]:
        getattr(events, name).extend(ev[name])
    known = {'status', 'expansions', 'pushes', 'relaxes', 'path_cost',
             'path_length', 'path_steps'}
    if set(sm) - known:
        raise ValueError(f'summary fields v2 does not carry: {set(sm) - known}')
    summary = search_pb2.SearchSummary(
        search_id=search_id, status=STATUSES[sm['status']],
        expansions=sm['expansions'], pushes=sm['pushes'],
        relaxes=sm['relaxes'])
    for name in ('path_cost', 'path_length', 'path_steps'):
        if sm[name] is not None:
            setattr(summary, name, sm[name])
    return header, events, summary


def search_to_v1(header, events, summary) -> Dict[str, object]:
    """Return the v1 trace dict the three messages were made from."""
    h = {
        'schema': header.source_schema,
        'version': header.source_version,
        'algorithm': header.algorithm,
        'heuristic': header.heuristic,
        'weight': header.weight if header.HasField('weight') else None,
        'tie_break': header.tie_break,
        'start': unloc(header.start),
        'goal': unloc(header.goal),
        'graph': unparams(header.graph),
    }
    ev = {'kind': [k - 1 for k in events.kind]}
    for name in SEARCH_COLUMNS[1:]:
        ev[name] = list(getattr(events, name))
    status = {v: k for k, v in STATUSES.items()}[summary.status]
    sm = {'status': status, 'expansions': summary.expansions,
          'pushes': summary.pushes, 'relaxes': summary.relaxes}
    for name in ('path_cost', 'path_length', 'path_steps'):
        sm[name] = getattr(summary, name) if summary.HasField(name) else None
    return {'header': h, 'events': ev, 'summary': sm}


# -- incremental (D* Lite) ----------------------------------------------------

def _inf(v: float) -> float:
    return math.inf if v == INF_SENTINEL else v


def _sentinel(v: float) -> float:
    return INF_SENTINEL if v == math.inf else v


def incremental_from_v1(columns: Dict[str, list], search_id: int = 0,
                        tick: int = 0, t_world: float = 0.0):
    """Encode ReplanTrace columns; ``-1`` becomes ``+inf``."""
    n = len(columns['kind'])
    b = incremental_pb2.IncrementalEventBatch(
        search_id=search_id, seq=range(n), tick=[tick] * n,
        t_world=[t_world] * n, kind=[k + 1 for k in columns['kind']],
        row=columns['row'], col=columns['col'], sub=columns['sub'],
        g=[_inf(v) for v in columns['g']],
        rhs=[_inf(v) for v in columns['rhs']], round=columns['round'])
    return b


def incremental_to_v1(batch) -> Dict[str, list]:
    """Decode an IncrementalEventBatch into ReplanTrace columns."""
    return {
        'kind': [k - 1 for k in batch.kind],
        'row': list(batch.row), 'col': list(batch.col),
        'sub': list(batch.sub),
        'g': [_sentinel(v) for v in batch.g],
        'rhs': [_sentinel(v) for v in batch.rhs],
        'round': list(batch.round),
    }
