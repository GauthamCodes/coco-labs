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
Write ``test/golden/share_vectors.json``: the Python half of the share-link
round trip (``src/lab/share.ts``).

- ``golden``: for each committed golden bundle, the trace digest -- sha256
  over the trace columns' bytes in the bundle's column order. The TS
  ``traceDigest`` must give the same (``test/lab.test.ts``).
- ``vectors``: a base bundle, map edits and settings, in the canonical form
  a share link decodes to (free cells, then occupied cells, each in
  row-major order), and the digest of the trace coco_lab's worker glue
  computes for them. The TS side encodes each vector as a link, decodes
  it, and must get the same edits and settings back; this side reruns the
  glue and must get the same digest (``tools/test_glue.py``).

Only committed fixtures are used, so CI can run it before the site data is
built. ``--check`` regenerates in memory and fails on any difference.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from coco_lab import bundle  # noqa: E402
from coco_lab.maps import FREE, OCCUPIED  # noqa: E402
import common  # noqa: E402

sys.path.insert(0, os.path.join(common.LAB_WEB, 'src', 'worker'))
sys.dont_write_bytecode = True  # keep src/ free of __pycache__
import recompute  # noqa: E402

OUT = os.path.join(common.LAB_WEB, 'test', 'golden', 'share_vectors.json')
FIXTURES = os.path.join(common.REPO, 'coco_lab', 'test', 'fixtures', 'bundles')
GOLDEN = ['astar_open', 'dijkstra_cost_field_gz', 'weighted_astar_greedy_trap',
          'bfs_no_path', 'astar_turn_trap_heading']


def trace_digest(b):
    """sha256 hex over the trace columns' bytes, in the bundle's order."""
    raw = b''.join(d for name, _, d in b.arrays() if name.startswith('trace.'))
    return hashlib.sha256(raw).hexdigest()


def files(name):
    d = os.path.join(FIXTURES, name)
    arrays = 'arrays.bin.gz' if os.path.exists(os.path.join(d, 'arrays.bin.gz')) else 'arrays.bin'
    with open(os.path.join(d, 'manifest.json'), 'rb') as f:
        m = f.read()
    with open(os.path.join(d, arrays), 'rb') as f:
        a = f.read()
    return m, arrays, a


def canonical_strokes(base_map, occupy, free):
    """Strokes as a share link decodes them: free, then occupied, sorted."""
    w = base_map.width
    key = lambda c: c[0] * w + c[1]  # noqa: E731
    free = sorted({tuple(c) for c in free if base_map.at(tuple(c)) != FREE}, key=key)
    occupy = sorted({tuple(c) for c in occupy if base_map.at(tuple(c)) != OCCUPIED}, key=key)
    out = []
    if free:
        out.append({'value': 'free', 'cells': [list(c) for c in free]})
    if occupy:
        out.append({'value': 'occupied', 'cells': [list(c) for c in occupy]})
    return out


def run_vector(name, strokes, settings):
    """Run the worker glue on a vector; return the trace digest."""
    spec = {'strokes': strokes, 'connectivity': settings['connectivity'],
            'runs': [{'algorithm': settings['algorithm'],
                      'heuristic': settings['heuristic'],
                      'weight': (settings['weight']
                                 if settings['algorithm'] == 'weighted_astar'
                                 else None),
                      'tie_break': settings['tieBreak']}],
            'optimal': False}
    recompute._CACHE.clear()
    out = recompute.recompute(json.dumps(spec), *files(name))['bundles'][0]
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, 'manifest.json'), 'wb') as f:
            f.write(out['manifest'])
        with open(os.path.join(d, 'arrays.bin'), 'wb') as f:
            f.write(out['arrays_file'])
        return trace_digest(bundle.load_bundle(d))


def vectors():
    """Two edits-plus-settings vectors on committed fixtures."""
    open_map = bundle.load_bundle(os.path.join(FIXTURES, 'astar_open')).lab_map
    trap = bundle.load_bundle(os.path.join(FIXTURES, 'weighted_astar_greedy_trap'))
    walls = [(r, c) for r in range(trap.lab_map.height)
             for c in range(trap.lab_map.width)
             if trap.lab_map.at((r, c)) == OCCUPIED][:6]
    specs = [
        ('astar_open',
         canonical_strokes(open_map, [(r, 9) for r in range(5, 13)] + [(12, 10), (12, 11)], []),
         {'algorithm': 'weighted_astar', 'heuristic': 'manhattan',
          'connectivity': 4, 'tieBreak': 'fifo', 'weight': 2.25}),
        ('weighted_astar_greedy_trap',
         canonical_strokes(trap.lab_map, [(0, 5), (0, 6), (1, 5)], walls),
         {'algorithm': 'astar', 'heuristic': 'octile', 'connectivity': 8,
          'tieBreak': 'low_h', 'weight': 1.0}),
    ]
    return [{'bundle': name, 'strokes': strokes, 'settings': settings,
             'trace_sha256': run_vector(name, strokes, settings)}
            for name, strokes, settings in specs]


def build():
    golden = {name: trace_digest(bundle.load_bundle(os.path.join(FIXTURES, name)))
              for name in GOLDEN}
    return json.dumps({
        'schema': 'lab_web.share_vectors', 'version': '1.0',
        'digest_rule': "sha256 over b''.join(data for name, _, data in "
                       "bundle.arrays() if name.startswith('trace.'))",
        'golden': golden, 'vectors': vectors()}, indent=1, sort_keys=True) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    text = build()
    if args.check:
        with open(OUT) as f:
            if f.read() != text:
                raise SystemExit(f'{OUT} is stale: run {__file__}')
        print('share vectors up to date')
        return
    with open(OUT, 'w') as f:
        f.write(text)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
