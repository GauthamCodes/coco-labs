#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R5.1: one level of the image's index as shell assignments, for the entrypoint.

    level_env.py INDEX.json ALIAS_OR_ID     -> LEVEL_ALIAS=... LEVEL_ID=... (shell-quoted)
    level_env.py INDEX.json --list          -> one line per level

Exit 2 (and the known levels on stderr) for an unknown level.
"""
import json
import math
import shlex
import sys


def main(argv):
    with open(argv[1], encoding='utf-8') as f:
        levels = json.load(f)['levels']
    if argv[2] == '--list':
        for alias, e in sorted(levels.items()):
            print(f'{alias:>14}  {e["id"]:<24} {e["kind"]:<10} {e["verification"]["result"]}')
        return 0
    want = argv[2]
    hit = [(a, e) for a, e in levels.items() if want in (a, e['id'])]
    if not hit:
        print(f'unknown level {want!r}; known: {", ".join(sorted(levels))}', file=sys.stderr)
        return 2
    alias, e = hit[0]
    start = e.get('start') or {}
    theta = float(start.get('theta', 0.0))
    out = {
        'LEVEL_ALIAS': alias, 'LEVEL_ID': e['id'], 'LEVEL_KIND': e['kind'],
        'LEVEL_TELEPORT': 'true' if e.get('teleport') else 'false',
        'LEVEL_WORLD': e.get('world') or '', 'LEVEL_MAP': e.get('map') or '',
        'LEVEL_PARAMS': e.get('params') or '', 'LEVEL_CALIBRATION': e.get('calibration') or '',
        'LEVEL_MULTIPLIER': '' if e.get('wheel_separation_multiplier') is None
        else repr(e['wheel_separation_multiplier']),
        'LEVEL_VERIFIED': e['verification']['result'],
        'START_X': repr(float(start.get('x', 0.0))), 'START_Y': repr(float(start.get('y', 0.0))),
        'START_THETA': repr(theta),
        'START_QZ': repr(math.sin(theta / 2)), 'START_QW': repr(math.cos(theta / 2)),
    }
    for k, v in out.items():
        print(f'{k}={shlex.quote(str(v))}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
