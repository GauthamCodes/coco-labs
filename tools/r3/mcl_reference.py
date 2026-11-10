#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R4 Part A (Gautham, 2026-11-10): the "MCL reference" -- a deliberately expensive localiser run on
loc-global-20 and loc-kidnap-20 to test whether the suites can be solved in the model. Labelled a
REFERENCE (never ranked): MCL with augmented injection, 2,000 particles, 24 beams (the 60-particle
built-ins' 0/40 and 0/60 stay as the negative baselines). Same scenarios as the R3.2 baselines:
the public suite and the reference held-out draw.

    python tools/r3/mcl_reference.py [--workers N] [--only SUITE]

Writes docs/v2/r4/data/mcl_reference/<suite>/{public,held_out}/ (the export set of
`coco experiment run`). Every number is reported whatever it is.
"""
import argparse
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
sys.path.insert(0, str(REPO / 'tools' / 'r3'))
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

import make_baselines as mb  # noqa: E402
from coco_lab import experiments as ex  # noqa: E402

OUT = REPO / 'docs' / 'v2' / 'r4' / 'data' / 'mcl_reference'
SUITES = ('loc-global-20', 'loc-kidnap-20')
PARTICLES, BEAMS = 2000, 24
ALGO = {'name': 'mcl_augmented', 'id': 'mcl_reference', 'label': f'MCL reference ({PARTICLES:,} particles)',
        'params': {'mcl.particles': PARTICLES, 'mcl.beams': BEAMS}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    lb = mb._leaderboard()
    for sid in SUITES:
        if a.only and sid not in a.only:
            continue
        held, _ = mb.held_out(sid, lb)
        for which in ('public', 'held_out'):
            d = OUT / sid / which
            if (d / 'manifest.json').exists():
                print(f'{d}: done, skipped', flush=True)
                continue
            s = mb.spec(sid, 'localisation', which, held if which == 'held_out' else None)
            s['algorithms'] = [ALGO]
            s['title'] = f'R4 MCL reference: {sid}, {which}'
            mb.run(s, d, a.workers)
            print(f'{d}: written', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
