#!/usr/bin/env python3
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
Write the cross-language test vectors, once, from the Python reference.

    python3 coco_schemas/scripts/make_vectors.py

- ``test/vectors/run_id.json``: run_id inputs and outputs (Python and
  TypeScript must both reproduce them).
- ``test/vectors/search_batch.json`` + ``.binpb``: a v1 trace's columns and
  the Python protobuf encoding of the same SearchEventBatch, which
  TypeScript's encoders must reproduce byte for byte (ADR 0001).

Re-running it must not change the files (the tests pin them); a change is
a change of method and needs a new major.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from coco_lab.grid import Grid  # noqa: E402
from coco_lab.search import search  # noqa: E402
from coco_schemas.runid import run_id, spec_sha256  # noqa: E402
from coco_schemas.trace_v1 import search_from_v1  # noqa: E402

OUT = os.path.join(PKG, 'test', 'vectors')

RUN_ID_CASES = [
    ('empty spec, seed 0, no engines', '', 0, []),
    ('a small spec, two engines out of order', '{"world":"coco_arena_v1"}', 42,
     [['pyodide', '314.0.7'], ['coco_lab', '0.2.0']]),
    ('largest seed', '{"a":1}', 2 ** 64 - 1, [['coco_lab', 'abc123']]),
    ('non-ASCII spec and engine version', '{"note":"héllo — π"}', 7,
     [['python', '3.14.2'], ['coco_lab', 'déf']]),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    vecs = []
    for note, spec, seed, engines in RUN_ID_CASES:
        b = spec.encode('utf-8')
        vecs.append({'note': note, 'spec_utf8': spec, 'seed': str(seed),
                     'engines': engines, 'spec_sha256': spec_sha256(b),
                     'run_id': run_id(b, seed, engines)})
    with open(os.path.join(OUT, 'run_id.json'), 'w') as f:
        json.dump({'method': 'coco_schemas.runid (docs/v2/SCHEMAS.md)',
                   'note': 'seed is a decimal string: it may exceed 2**53',
                   'vectors': vecs}, f, indent=1, ensure_ascii=False)
        f.write('\n')

    grid = Grid(7, 5, [False] * 17 + [True] * 2 + [False] * 16,
                cost=[0.0] * 30 + [3.5] * 5, connectivity=8,
                diagonal_cost=math.sqrt(2), corner_cutting=False)
    r = search(grid, (0, 0), (4, 6), 'astar', heuristic='octile')
    _, batch, _ = search_from_v1(r.trace.to_dict(), search_id=3, tick=12,
                                 t_world=1.25)
    cols = {f.name: list(getattr(batch, f.name))
            for f in batch.DESCRIPTOR.fields if f.name != 'search_id'}
    with open(os.path.join(OUT, 'search_batch.json'), 'w') as f:
        json.dump({'message': 'coco.plan.v1.SearchEventBatch',
                   'search_id': batch.search_id, 'columns': cols}, f,
                  indent=1)
        f.write('\n')
    with open(os.path.join(OUT, 'search_batch.binpb'), 'wb') as f:
        f.write(batch.SerializeToString())
    print(f'wrote {len(vecs)} run_id vectors and a {len(batch.seq)}-event '
          'search batch')


if __name__ == '__main__':
    main()
