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
Event batches as columns (ADR 0001, docs/v2/adr/0001-event-transport.md).

coco_lab never imports protobuf. It fills Python ``array`` columns whose
names, order and meaning are the fields of the v2 ``*Batch`` messages in
``coco_schemas`` (``coco.plan.search.events.v1`` = ``SearchEventBatch``);
the Web Worker posts the arrays as transferable buffers and TypeScript
encodes them only when a run is stored. ``coco_schemas`` tests that these
columns encode to exactly the bytes protobuf writes.

:class:`SearchEventColumns` takes :func:`coco_lab.search.search_events`
rows; :func:`stream` runs a search and hands back one batch per
``batch_size`` events, so a caller can render between batches.
"""

from array import array
from typing import Dict, Iterator, Tuple

#: SearchEventBatch's columns, in field order (fields 1-13), and their
#: array typecodes: u64 clocks, f64 time and costs, i32 locations.
SEARCH_FIELDS = (('seq', 'Q'), ('tick', 'Q'), ('t_world', 'd'),
                 ('kind', 'i'), ('row', 'i'), ('col', 'i'), ('sub', 'i'),
                 ('g', 'd'), ('h', 'd'), ('f', 'd'),
                 ('parent_row', 'i'), ('parent_col', 'i'),
                 ('parent_sub', 'i'))


class SearchEventColumns:
    """Columns of ``coco.plan.search.events.v1`` for one search."""

    def __init__(self, search_id: int = 0, tick: int = 0,
                 t_world: float = 0.0):
        """Start empty; every row gets this search's tick and time."""
        self.search_id = search_id
        self.tick = tick
        self.t_world = t_world
        self.seq = 0
        self._new()

    def _new(self):
        self.columns: Dict[str, array] = {n: array(t) for n, t in
                                          SEARCH_FIELDS}

    def __len__(self) -> int:
        """Return the number of rows not yet drained."""
        return len(self.columns['seq'])

    def add(self, row: Tuple) -> None:
        """Append one search_events row (v1 kind; stored as v2 kind + 1)."""
        c = self.columns
        c['seq'].append(self.seq)
        c['tick'].append(self.tick)
        c['t_world'].append(self.t_world)
        c['kind'].append(row[0] + 1)
        c['row'].append(row[1])
        c['col'].append(row[2])
        c['sub'].append(row[3])
        c['g'].append(row[4])
        c['h'].append(row[5])
        c['f'].append(row[6])
        c['parent_row'].append(row[7])
        c['parent_col'].append(row[8])
        c['parent_sub'].append(row[9])
        self.seq += 1

    def drain(self) -> Dict[str, array]:
        """Return the rows so far and start a new batch (seq continues)."""
        out = self.columns
        self._new()
        return out


def stream(events, columns: SearchEventColumns,
           batch_size: int = 4096) -> Iterator[Dict[str, array]]:
    """
    Drain ``events`` into batches of at most ``batch_size`` rows.

    Yields each batch as it fills, then the remainder; the search's
    :class:`coco_lab.search.SearchOutcome` is the generator's return value.
    """
    if batch_size < 1:
        raise ValueError(f'batch_size must be >= 1, got {batch_size!r}')
    add = columns.add
    try:
        while True:
            add(next(events))
            if len(columns) >= batch_size:
                yield columns.drain()
    except StopIteration as stop:
        outcome = stop.value
    if len(columns):
        yield columns.drain()
    return outcome
