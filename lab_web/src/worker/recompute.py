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
Glue ONLY: the Pyodide worker's bridge to coco_lab.

This file contains no search logic. It hands bytes to ``coco_lab``'s own
``load_bundle`` (full structural + semantic validation), toggles one cell
of the map, reruns ``coco_lab.search.search`` with the bundle's recorded
run inputs (algorithm, heuristic, weight, tie-break, start, goal, move
model), and writes the result with ``coco_lab``'s own ``write_bundle``
(which validates again) as a ``glass-box`` bundle whose provenance says
``tool='lab_web/pyodide'``. The page then decodes those bytes with the
same TypeScript decoder as every other bundle.
"""

import json
import os
import shutil
import sys
import tempfile
import time

import coco_lab
from coco_lab import bundle
from coco_lab.maps import LabMap
from coco_lab.search import search

TOOL = 'lab_web/pyodide'


def _ms(t0):
    return (time.perf_counter() - t0) * 1000.0


def _bytes(data):
    """Bytes from a JS Uint8Array proxy (one memcpy) or a bytes-like."""
    to_bytes = getattr(data, 'to_bytes', None)
    # bytes(proxy) would copy element by element across the JS boundary:
    # measured ~10x slower than CPython's whole load for a 3.5 MB bundle
    return to_bytes() if to_bytes is not None else bytes(data)


def edit(manifest, arrays_name, arrays_file, row, col):
    """Toggle ``(row, col)`` and recompute; return the new bundle's files."""
    work = tempfile.mkdtemp(prefix='lab_edit_')
    try:
        return _edit(work, manifest, arrays_name, arrays_file, row, col)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _edit(work, manifest, arrays_name, arrays_file, row, col):
    t_all = time.perf_counter()
    t0 = time.perf_counter()
    d = os.path.join(work, 'in')
    os.makedirs(d)
    with open(os.path.join(d, 'manifest.json'), 'wb') as f:
        f.write(_bytes(manifest))
    with open(os.path.join(d, arrays_name), 'wb') as f:
        f.write(_bytes(arrays_file))
    b = bundle.load_bundle(d)
    load_ms = _ms(t0)

    m = b.lab_map
    occ = bytearray(m.occupancy)
    i = row * m.width + col
    occ[i] = 0 if occ[i] == 1 else 1
    new_map = LabMap(m.width, m.height, bytes(occ), m.cost, map_id=m.id,
                     resolution=m.resolution, origin=m.origin, frame=m.frame,
                     meta=m.meta)
    run = b.run
    probe = bundle.Bundle(b.provenance, run, new_map, b.trace)
    graph = probe.graph()
    t0 = time.perf_counter()
    result = search(graph, bundle.start_state(graph, run['start']),
                    bundle.goal_state(graph, run['goal']), run['algorithm'],
                    run['heuristic'], weight=run['weight'],
                    tie_break=run['tie_break'])
    search_ms = _ms(t0)

    t0 = time.perf_counter()
    prov = bundle.make_provenance('glass-box', tool=TOOL)
    out = bundle.Bundle.from_run(
        result, new_map, {'start': run['start'], 'goal': run['goal'],
                          'model': run['model']}, prov)
    od = os.path.join(work, 'out')
    bundle.write_bundle(out, od, 'none')
    with open(os.path.join(od, 'manifest.json'), 'rb') as f:
        m_out = f.read()
    with open(os.path.join(od, 'arrays.bin'), 'rb') as f:
        a_out = f.read()
    write_ms = _ms(t0)
    return {
        'manifest': m_out, 'arrays_file': a_out, 'arrays_name': 'arrays.bin',
        'content_hash': json.loads(m_out)['content_hash'],
        'coco_lab_version': coco_lab.__version__,
        'python_version': sys.version.split()[0],
        'timings': {'load_bundle_ms': load_ms, 'search_ms': search_ms,
                    'write_bundle_ms': write_ms, 'total_ms': _ms(t_all)},
    }
