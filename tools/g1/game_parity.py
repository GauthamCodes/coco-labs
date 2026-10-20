#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.6: a played session (spec, seed, input log) replayed in CPython must give
the same per-tick hash chain, last hash and scorecard as it gave in Pyodide.

    tools/g1/game_parity.py PLAYED.json [--out OUT.json]

PLAYED.json is lab_web/tools/g1/game_node.mjs's output (or a record the page
exported): {record, hash_chain, last_hash, scorecard}. The CPython side is
coco_lab.games.play on worlds/coco_depot_v1.json, the same canonical bytes the
browser loads. Exit 0 only if every compared field is identical.
"""
import argparse
import json
import os
import platform
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import games  # noqa: E402


def per_tick(spec, record):
    """Return every tick's state hash, replaying exactly as games.play does."""
    from coco_lab.arena import Arena, InputEvent
    a = Arena(spec, record['seed'], hash_version=record.get('hash_version', 1))
    by = {}
    for e in record['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    return [a.step(by.get(a.tick, ())).state_hash for _ in range(record['ticks'])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('played')
    ap.add_argument('--out')
    a = ap.parse_args()
    with open(a.played, encoding='utf-8') as f:
        played = json.load(f)
    with open(os.path.join(REPO, 'worlds', 'coco_depot_v1.json'), encoding='utf-8') as f:
        spec = json.load(f)
    got = games.play(spec, played['record'])
    first = None
    if played.get('hashes'):
        hashes = per_tick(spec, played['record'])
        first = next((k for k, (x, y) in enumerate(zip(hashes, played['hashes'])) if x != y), None)
    same = {'hash_chain': got['hash_chain'] == played['hash_chain'],
            'last_hash': got['last_hash'] == played['last_hash'],
            'scorecard': got['scorecard'] == played['scorecard']}
    out = {'record_ticks': played['record']['ticks'], 'inputs': len(played['record']['inputs']),
           'hash_version': played['record'].get('hash_version', 1),
           'pyodide': {k: played[k] for k in ('hash_chain', 'last_hash')},
           'cpython': {'hash_chain': got['hash_chain'], 'last_hash': got['last_hash'],
                       'python': platform.python_version()},
           'scorecard_cpython': got['scorecard'], 'identical': same, 'first_differing_tick': first,
           'passed': all(same.values())}
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=1)
            f.write('\n')
    print(json.dumps({'first_differing_tick': first, 'identical': same, 'ticks': out['record_ticks'], 'deliveries': got['scorecard'].get('deliveries')}))
    return 0 if out['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
