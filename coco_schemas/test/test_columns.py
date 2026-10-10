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
coco_lab's columns ARE the schema (ADR 0001).

coco_lab emits SearchEventBatch as plain arrays (``coco_lab.events``),
without protobuf. Filled into the generated message, those arrays must give
the same bytes as the lossless converter's batch for the same search -- so
the dependency-free emitter cannot drift from ``coco.plan.search.events.v1``.
"""

import random

from coco_lab.events import SEARCH_FIELDS, SearchEventColumns, stream
from coco_lab.grid import Grid
from coco_lab.search import search, search_events
from coco_schemas.gen.coco.plan.v1 import search_pb2
from coco_schemas.trace_v1 import search_from_v1


#: SearchEventBatch fields only D* Lite's replanning traces fill (M2.7,
#: additive): coco_lab's A*-family emitter never has them
DSTAR_ONLY = ('rhs', 'round')


def test_the_column_names_and_order_are_the_messages_fields():
    d = search_pb2.SearchEventBatch.DESCRIPTOR
    assert [n for n, _ in SEARCH_FIELDS] == \
        [f.name for f in sorted(d.fields, key=lambda f: f.number)
         if f.name != 'search_id' and f.name not in DSTAR_ONLY]
    assert [f.number for f in d.fields if f.name in DSTAR_ONLY] == [15, 16]


def test_emitted_columns_encode_to_the_converters_bytes():
    rng = random.Random(3)
    for _ in range(40):
        w, h = rng.randint(2, 25), rng.randint(2, 25)
        blocked = [rng.random() < 0.25 for _ in range(w * h)]
        blocked[0] = blocked[-1] = False
        g = Grid(w, h, blocked)
        algo = rng.choice(['bfs', 'dijkstra', 'astar', 'greedy',
                           'weighted_astar'])
        kw = {'heuristic': 'octile'} if algo != 'bfs' else {}
        if algo == 'weighted_astar':
            kw['weight'] = 1.5
        trace = search(g, (0, 0), (h - 1, w - 1), algo, **kw).trace
        _, want, _ = search_from_v1(trace.to_dict(), search_id=5, tick=9,
                                    t_world=0.9)
        cols = SearchEventColumns(search_id=5, tick=9, t_world=0.9)
        batches = list(stream(search_events(g, (0, 0), (h - 1, w - 1), algo,
                                            **kw), cols, batch_size=10 ** 9))
        assert len(batches) == 1
        got = search_pb2.SearchEventBatch(search_id=5)
        for name, _ in SEARCH_FIELDS:
            getattr(got, name).extend(batches[0][name].tolist())
        assert got.SerializeToString() == want.SerializeToString()
