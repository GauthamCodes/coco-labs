#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.2: a carried-over v1 suite has v0's scenarios exactly, so its v1 baseline must reproduce R1's v0
reference results run for run: the same status and every metric but wall time.

    tools/r3/check_carried.py SUITE FAMILY     (exit 1 on any difference)
"""
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]


def runs(p):
    out = {}
    for line in p.read_text().splitlines():
        r = json.loads(line)
        out[(r['algorithm'], r['scenario'])] = (r['status'], {k: v for k, v in r['metrics'].items()
                                                              if k != 'compute_ms'})
    return out


def main():
    suite, family = sys.argv[1], sys.argv[2]
    v0 = runs(REPO / 'docs/v2/r1/bench' / suite / family / 'runs.jsonl')
    v1 = runs(REPO / 'docs/v2/r3/bench' / suite / family / 'public' / 'runs.jsonl')
    common = sorted(set(v0) & set(v1))
    diff = [k for k in common if v0[k] != v1[k]]
    print(f'{suite}/{family}: v0 {len(v0)} runs, v1 {len(v1)}, compared {len(common)}, '
          f'differing {len(diff)}' + (f' e.g. {diff[:3]}' if diff else ''))
    return 1 if diff or not common else 0


if __name__ == '__main__':
    sys.exit(main())
