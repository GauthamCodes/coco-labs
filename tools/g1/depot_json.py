#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Write worlds/coco_depot_v1.json: the Depot's canonical World Spec bytes (G1.5).

The browser's Arena worker loads a level as canonical JSON (no YAML parser in
Pyodide's trimmed stdlib), exactly as it loads worlds/coco_arena_v1.json and
_v2.json. The bytes are coco_lab.worldspec.canonical_bytes of the generated
YAML: the v3 reader's own normalised form, with the lowered boxes and
elevation it derives. Nothing is added or edited here.

    tools/g1/depot_json.py [--check]
"""

import argparse
import os
import sys

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab.worldspec import canonical_bytes  # noqa: E402

SRC = os.path.join(REPO, 'worlds', 'coco_depot_v1.yaml')
OUT = os.path.join(REPO, 'worlds', 'coco_depot_v1.json')


def build() -> bytes:
    """Return the canonical bytes of the committed Depot YAML."""
    with open(SRC, encoding='utf-8') as f:
        return canonical_bytes(yaml.safe_load(f))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    data = build()
    if args.check:
        with open(OUT, 'rb') as f:
            same = f.read() == data
        print('coco_depot_v1.json', 'current' if same else 'STALE')
        return 0 if same else 1
    with open(OUT, 'wb') as f:
        f.write(data)
    print(OUT, len(data))
    return 0


if __name__ == '__main__':
    sys.exit(main())
