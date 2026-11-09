#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.7: "Reproduce this paper" -- one Workbench link carrying the paper's browser experiment (the
COCO-Bench v1 depot-nav-100 planning baseline: every built-in planner on the 100 public scenarios)
and its committed digest; the Workbench runs it in the visitor's browser and checks the digest.

    python tools/r3/paper_link.py [--check]

Writes docs/paper/generated/reproduce.json {url, digest, runs, spec, source}. The spec is exactly
make_baselines.py's input spec, so the digest is the committed baseline's (summary.json).
"""
import argparse
import base64
import importlib.util
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
SITE = 'https://gauthamcodes.github.io/coco-labs/'
SUITE, FAMILY = 'depot-nav-100', 'planning'
OUT = REPO / 'docs' / 'paper' / 'generated' / 'reproduce.json'


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def build():
    spec_mod = importlib.util.spec_from_file_location('mb', REPO / 'tools/r3/make_baselines.py')
    mb = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mb)
    spec = mb.spec(SUITE, FAMILY, 'public')
    base = REPO / 'docs/v2/r3/bench' / SUITE / FAMILY / 'public'
    summary = json.loads((base / 'summary.json').read_text())
    js = json.dumps(spec, separators=(',', ':'))
    url = f"{SITE}?view=workbench&exp={b64(js.encode())}&d={summary['digest']}"
    if len(url) > 1800:   # lab_web/src/workbench/links.ts SHORT_LINK: the deflated form
        import zlib
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        url = f"{SITE}?view=workbench&d={summary['digest']}#expz={b64(c.compress(js.encode()) + c.flush())}"
    return {'url': url, 'digest': summary['digest'], 'runs': summary['n_runs'], 'spec': spec,
            'source': str(base.relative_to(REPO)) + '/summary.json'}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    text = json.dumps(build(), indent=1, sort_keys=True) + '\n'
    if a.check:
        same = OUT.is_file() and OUT.read_text() == text
        print('reproduce.json up to date' if same else 'reproduce.json DIFFERS')
        return 0 if same else 1
    OUT.write_text(text)
    print(json.loads(text)['url'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
