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

    tools/g1/depot_json.py [--check] [--variant colours]

``--variant colours`` writes worlds/coco_depot_colours_v1.json from
worlds/coco_depot_colours_v1.yaml (the Depot plus four colour rods; owner request
2026-10-24) the same way; the Depot's own bytes are untouched.
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
VARIANTS = {'': 'coco_depot_v1', 'colours': 'coco_depot_colours_v1'}


def build(variant: str = '') -> bytes:
    """Return the canonical bytes of the committed Depot YAML (or a variant's)."""
    src = os.path.join(REPO, 'worlds', f'{VARIANTS[variant]}.yaml')
    with open(src, encoding='utf-8') as f:
        return canonical_bytes(yaml.safe_load(f))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--variant', default='', choices=sorted(VARIANTS))
    args = ap.parse_args()
    data = build(args.variant)
    out = os.path.join(REPO, 'worlds', f'{VARIANTS[args.variant]}.json')
    if args.check:
        with open(out, 'rb') as f:
            same = f.read() == data
        print(os.path.basename(out), 'current' if same else 'STALE')
        return 0 if same else 1
    with open(out, 'wb') as f:
        f.write(data)
    print(out, len(data))
    return 0


if __name__ == '__main__':
    sys.exit(main())
