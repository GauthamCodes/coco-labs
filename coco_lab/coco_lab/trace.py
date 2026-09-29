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
Trace schema v1: what a search did, event by event, in columns.

The normative description is ``docs/labs/TRACE_SCHEMA.md``; this module is
its reference implementation and the tests pin one to the other.

A trace is three parts:

``header``
    What was searched, and how: schema name and version, algorithm,
    heuristic, weight, tie-break, start, goal, and the graph's parameters.
``events``
    Columns of equal length, one row per event, in the order the events
    happened. ``kind`` is an index into :data:`EVENT_KINDS`.
``summary``
    status, expansions, pushes, relaxes, path cost, path length and path
    steps.

**Versioning.** ``version`` is ``"MAJOR.MINOR"``. Adding a column, an event
kind, or a header or summary field bumps MINOR; a reader of the same MAJOR
must ignore what it does not know. Anything that changes the meaning of an
existing field bumps MAJOR, and a reader refuses a MAJOR it does not know.
"""

import json
import math
from typing import Dict, List, Optional

SCHEMA = 'coco_lab.trace'
VERSION = '1.0'
MAJOR = 1

#: Event kinds, in code order: ``kind`` column value ``i`` means
#: ``EVENT_KINDS[i]``.
EVENT_KINDS = ('push', 'expand', 'relax', 'path')
PUSH, EXPAND, RELAX, PATH = range(len(EVENT_KINDS))

#: The event columns, in order. ``parent_*`` are ``-1`` for no parent.
COLUMNS = ('kind', 'row', 'col', 'sub', 'g', 'h', 'f',
           'parent_row', 'parent_col', 'parent_sub')

INT_COLUMNS = ('kind', 'row', 'col', 'sub',
               'parent_row', 'parent_col', 'parent_sub')
FLOAT_COLUMNS = ('g', 'h', 'f')

STATUSES = ('found', 'no_path')

NO_PARENT = (-1, -1, -1)


class TraceError(ValueError):
    """A trace that does not conform to the schema."""


class Trace:
    """A search trace: ``header``, columnar ``events`` and ``summary``."""

    def __init__(self, header: Dict[str, object],
                 events: Dict[str, List], summary: Dict[str, object]):
        """Wrap the three parts; call :meth:`validate` to check them."""
        self.header = header
        self.events = events
        self.summary = summary

    def __len__(self) -> int:
        """Return the number of events."""
        return len(self.events['kind'])

    def __eq__(self, other) -> bool:
        """Compare by content."""
        return isinstance(other, Trace) and self.to_dict() == other.to_dict()

    def rows(self, kind: Optional[str] = None):
        """Yield events as dicts, optionally only those of one kind."""
        code = None if kind is None else EVENT_KINDS.index(kind)
        cols = self.events
        for i in range(len(self)):
            if code is None or cols['kind'][i] == code:
                yield {name: cols[name][i] for name in COLUMNS}

    def cells(self, kind: str) -> List[tuple]:
        """Return ``(row, col, sub)`` of every event of ``kind``, in order."""
        return [(e['row'], e['col'], e['sub']) for e in self.rows(kind)]

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return {
            'header': dict(self.header),
            'events': {name: list(self.events[name]) for name in COLUMNS},
            'summary': dict(self.summary),
        }

    def to_json(self) -> str:
        """Return canonical JSON: sorted keys, no whitespace, no NaN."""
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(',', ':'), allow_nan=False)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> 'Trace':
        """Build and validate a trace, refusing an unknown MAJOR version."""
        try:
            header = dict(data['header'])
            events = {name: list(data['events'][name]) for name in COLUMNS}
            summary = dict(data['summary'])
        except (KeyError, TypeError) as exc:
            raise TraceError(f'not a trace: missing {exc}') from None
        trace = cls(header, events, summary)
        trace.validate()
        return trace

    @classmethod
    def from_json(cls, text: str) -> 'Trace':
        """Parse and validate JSON produced by :meth:`to_json`."""
        return cls.from_dict(json.loads(text))

    def validate(self) -> None:
        """Raise :class:`TraceError` unless this trace conforms to v1."""
        h = self.header
        if h.get('schema') != SCHEMA:
            raise TraceError(f'schema is {h.get("schema")!r}, not {SCHEMA!r}')
        version = str(h.get('version', ''))
        try:
            major = int(version.split('.')[0])
        except ValueError:
            raise TraceError(f'bad version {version!r}') from None
        if major != MAJOR:
            raise TraceError(
                f'trace major version {major} is not supported '
                f'(this reader speaks {MAJOR}.x)')
        n = len(self.events['kind'])
        for name in COLUMNS:
            if len(self.events[name]) != n:
                raise TraceError(
                    f'column {name!r} has {len(self.events[name])} rows, '
                    f'expected {n}')
        for name in INT_COLUMNS:
            if not all(isinstance(v, int) for v in self.events[name]):
                raise TraceError(f'column {name!r} must be integers')
        for name in FLOAT_COLUMNS:
            if not all(isinstance(v, (int, float)) and math.isfinite(v)
                       for v in self.events[name]):
                raise TraceError(f'column {name!r} must be finite numbers')
        if not all(0 <= k < len(EVENT_KINDS) for k in self.events['kind']):
            raise TraceError('kind column has an unknown event code')

        s = self.summary
        if s.get('status') not in STATUSES:
            raise TraceError(f'status {s.get("status")!r} not in {STATUSES}')
        counts = {k: 0 for k in EVENT_KINDS}
        for code in self.events['kind']:
            counts[EVENT_KINDS[code]] += 1
        for kind, field in (('expand', 'expansions'), ('push', 'pushes'),
                            ('relax', 'relaxes')):
            if s.get(field) != counts[kind]:
                raise TraceError(
                    f'summary {field}={s.get(field)!r} but the events hold '
                    f'{counts[kind]}')
        if s['status'] == 'found':
            if counts['path'] != s.get('path_steps', -1) + 1:
                raise TraceError('path events != path_steps + 1')
            for field in ('path_cost', 'path_length'):
                v = s.get(field)
                if not (isinstance(v, (int, float)) and math.isfinite(v)):
                    raise TraceError(f'{field} must be finite when found')
        else:
            if counts['path']:
                raise TraceError('a no_path trace has path events')
            for field in ('path_cost', 'path_length', 'path_steps'):
                if s.get(field) is not None:
                    raise TraceError(f'{field} must be null when no_path')


class TraceBuilder:
    """Accumulate events column by column while a search runs."""

    def __init__(self):
        """Start with empty columns."""
        self.columns: Dict[str, List] = {name: [] for name in COLUMNS}

    def add(self, kind: int, loc: tuple, g: float, h: float, f: float,
            parent: tuple = NO_PARENT) -> None:
        """Append one event."""
        cols = self.columns
        cols['kind'].append(kind)
        cols['row'].append(int(loc[0]))
        cols['col'].append(int(loc[1]))
        cols['sub'].append(int(loc[2]))
        cols['g'].append(float(g))
        cols['h'].append(float(h))
        cols['f'].append(float(f))
        cols['parent_row'].append(int(parent[0]))
        cols['parent_col'].append(int(parent[1]))
        cols['parent_sub'].append(int(parent[2]))

    def count(self, kind: int) -> int:
        """Return how many events of ``kind`` have been added."""
        return sum(1 for k in self.columns['kind'] if k == kind)
