#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Score the browser's Play links again in native CPython (M3.6), and say which agree.

    python3 lab_web/tools/play_cpython_check.py LINKS.json OUT.json

LINKS.json is tools/perf/play_verify.mjs's output: each submission with the
result hash Chromium's page (Pyodide) gave. ``coco verify`` re-scores them
under Pyodide in Node; this re-scores them under the CPython the tests run,
to measure whether one Python, compiled two ways, gives the same results.
It is a measurement, not a gate: Pyodide is what the page and coco verify
both run.
"""

import base64
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'coco_lab'))

from coco_lab import play  # noqa: E402
import yaml  # noqa: E402


def decode(link):
    q = parse_qs(urlparse(link).query)
    s = q['s'][0]
    j = json.loads(base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)))
    return {'v': 1, 'challenge': q['c'][0], 'level': q['l'][0], 'level_hash': j['h'], 'inputs': j['i']}, j['r']


def main():
    links = json.load(open(sys.argv[1]))['links']
    with open(os.path.join(HERE, '..', 'play', 'levels.json'), encoding='utf-8') as f:
        levels = json.load(f)
    with open(os.path.join(HERE, '..', '..', 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    rows = []
    for link in links:
        sub, want = decode(link)
        r = play.score(levels, sub, spec)
        rows.append({'challenge': sub['challenge'], 'level': sub['level'], 'pyodide': want, 'cpython': r['hash'],
                     'same': r['hash'] == want})
    by = {}
    for r in rows:
        b = by.setdefault(r['challenge'], [0, 0])
        b[0] += r['same']
        b[1] += 1
    out = {'what': 'Chromium (Pyodide 314.0.7) vs native CPython result hashes for the same Play links',
           'python': sys.version.split()[0], 'same': sum(r['same'] for r in rows), 'links': len(rows),
           'by_challenge': {k: f'{a} of {n}' for k, (a, n) in by.items()}, 'rows': rows}
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(out['same'], 'of', out['links'], 'identical;', out['by_challenge'])


if __name__ == '__main__':
    main()
