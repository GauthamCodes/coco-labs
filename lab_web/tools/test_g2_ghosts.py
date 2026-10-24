# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.6: Race Nav2's ghosts (lab_web/public/stack/ghosts/) say what they are: recorded Gazebo +
Nav2 runs (STACK), with what they are not (no grasp, actors parked, never hardware) and where
they came from (the bag's sha256); the index is current, its checksums match, and a seed is
offered only for a recording whose every leg succeeded.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIR = REPO / 'lab_web' / 'public' / 'stack' / 'ghosts'


def test_the_index_is_current():
    r = subprocess.run([sys.executable, str(REPO / 'tools/g2/ghost_index.py'), '--check'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_ghost_says_what_it_is():
    idx = json.loads((DIR / 'index.json').read_text())
    assert idx['evidence'] == 'STACK'
    for e in idx['ghosts']:
        raw = (DIR / e['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == e['sha256'] and len(raw) == e['bytes']
        g = json.loads(raw)
        assert g['evidence'] == 'STACK' and g['schema'] == 'coco_lab.stack_ghost'
        assert any('no grasp' in n for n in g['not']) and any('parked' in n for n in g['not']) and any('hardware' in n for n in g['not'])
        assert g['source']['bag_sha256'] and all(len(v) == 64 for v in g['source']['bag_sha256'].values())
        assert e['all_succeeded'] == all(L['status'] == 'SUCCEEDED' for L in g['legs'])
        # times count from the first leg's start; its first truth pose follows within one 0.1 s sample
        assert g['round']['rules'] == 4 and g['track'] and 0 <= g['track'][0][0] <= 0.1
        ts = [p[0] for p in g['track']]
        assert ts == sorted(ts)
