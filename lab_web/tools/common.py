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
Shared by the lab_web Python tools: where the bundles are, and the oracle.

These tools run wherever ``coco_lab`` is importable (a plain venv, or the
colcon overlay). They never import ``rclpy``.

The *display rule* lives here as the Python oracle the TypeScript cursor is
tested against (``test/golden/expected.json``). It is a presentation
choice over the event log, not search logic:

    state(cell, k) = max over events i < k at that cell of
                     {push: 1 (open), expand: 2 (closed),
                      relax: 1 (open), path: 3 (path)}

A search state only ever moves open -> closed -> path, so for a plain grid
this is exactly the state after ``k`` events; for a heading grid (several
``sub`` states per cell) it gives the cell the highest-precedence state of
any of its subs, path > closed > open.
"""

import gzip
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LAB_WEB = os.path.dirname(HERE)
REPO = os.path.dirname(LAB_WEB)

GOLDEN_DIR = os.path.join(REPO, 'coco_lab', 'test', 'fixtures', 'bundles')
LAB1C_DIR = os.path.join(REPO, 'docs', 'data', 'lab1c', 'bundles')

#: The six golden fixtures (five 1.0, one 1.1) and the three 1C runs:
#: id -> repository-relative directory. The decoder must agree with Python
#: on every one of them.
GOLDEN = ('astar_open', 'dijkstra_cost_field_gz',
          'weighted_astar_greedy_trap', 'bfs_no_path',
          'astar_turn_trap_heading', 'recorded_run_synthetic_1_1')
LAB1C = ('astar', 'dijkstra', 'greedy')


def bundle_sources():
    """Return ``[(id, repo-relative dir)]`` for all nine decoder bundles."""
    out = [(n, f'coco_lab/test/fixtures/bundles/{n}') for n in GOLDEN]
    out += [(f'lab1c_{n}', f'docs/data/lab1c/bundles/{n}') for n in LAB1C]
    return out


def read_files(path):
    """Return ``(manifest bytes, arrays file name, arrays file bytes, raw)``."""
    with open(os.path.join(path, 'manifest.json'), 'rb') as f:
        manifest = f.read()
    for name in ('arrays.bin', 'arrays.bin.gz'):
        p = os.path.join(path, name)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                data = f.read()
            raw = gzip.decompress(data) if name.endswith('.gz') else data
            return manifest, name, data, raw
    raise FileNotFoundError(f'no arrays file in {path}')


def sha256_hex(data: bytes) -> str:
    """Return the hex sha256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


#: Display value of each event kind code (push, expand, relax, path).
KIND_STATE = (1, 2, 1, 3)
STATE_NAMES = {1: 'open', 2: 'closed', 3: 'path'}


def cell_states(events, width: int, height: int, k: int) -> bytearray:
    """Return the display state of every cell after ``k`` events."""
    s = bytearray(width * height)
    kinds, rows, cols = events['kind'], events['row'], events['col']
    for i in range(k):
        idx = rows[i] * width + cols[i]
        v = KIND_STATE[kinds[i]]
        if v > s[idx]:
            s[idx] = v
    return s


def hover(events, row: int, col: int, k: int):
    """
    Return what hovering ``(row, col)`` at cursor ``k`` shows.

    For every ``sub`` state at that cell that has an event before ``k``,
    the LAST such event: its index, kind, g, h, f and parent. Sorted by
    ``sub``. Values are as stored; nothing is recomputed.
    """
    last = {}
    for i in range(k):
        if events['row'][i] == row and events['col'][i] == col:
            last[events['sub'][i]] = i
    out = []
    for sub in sorted(last):
        i = last[sub]
        out.append({
            'sub': sub, 'index': i,
            'kind': ('push', 'expand', 'relax', 'path')[events['kind'][i]],
            'g': events['g'][i], 'h': events['h'][i], 'f': events['f'][i],
            'parent': [events['parent_row'][i], events['parent_col'][i],
                       events['parent_sub'][i]],
        })
    return out
