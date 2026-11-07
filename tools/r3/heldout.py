#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.3 · ADR 0014: held-out scenarios from a secret, generated OUTSIDE the sandbox (trusted side).

    heldout.py generate SUITE --head SHA --out FILE     the secret comes from $COCO_HELDOUT_SECRET
    heldout.py aggregate RUNS.json --out FILE           what may leave: rounded aggregates only

``generate`` draws the suite's held-out scenarios with ``coco_lab.bench_v1.generate`` from
``seed = int(HMAC-SHA256(secret, "coco-bench.held-out.v1|" + suite + "|" + head)[:13], 16)``
and writes only the scenarios (``experiments`` inline form) and their digest. It prints the
digest, never a scenario or the secret.

``aggregate`` reads the sandbox's ``heldout_runs.json`` as UNTRUSTED DATA: every run must be
``{status: short string, success: bool, metric: finite number or None}`` for the family's
metrics, nothing else is read; it writes per family the count, successes, Wilson 95 % interval
and the medians of the headline metrics, every float rounded to 3 significant digits (ADR 0014,
threats T4/T5). Nothing per scenario leaves.
"""
import argparse
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'coco_lab')]
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

SCHEMA = 'coco.bench.heldout.v1'
TAG = 'coco-bench.held-out.v1'
KEEP = ('id', 'start', 'goal', 'seed', 'config', 'kidnap_at_s', 'kidnap')
#: per family, the metrics whose medians may leave
HEADLINE = {'planning': ('path_ratio', 'min_clearance_m'),
            'control': ('time_s', 'min_clearance_m'),
            'localisation': ('final_err_xy_m', 'mean_err_xy_m')}
MAX_RUNS = 200


def seed_of(secret_hex: str, suite: str, head: str) -> int:
    key = bytes.fromhex(secret_hex)
    if len(key) < 16:
        raise SystemExit('the held-out secret is at least 16 bytes (32 hex digits)')
    mac = hmac.new(key, f'{TAG}|{suite}|{head}'.encode(), hashlib.sha256).hexdigest()
    return int(mac[:13], 16)


def scenarios_digest(scen) -> str:
    return hashlib.sha256(json.dumps(scen, sort_keys=True, separators=(',', ':'))
                          .encode()).hexdigest()


def generate(suite: str, head: str, secret_hex: str) -> dict:
    from coco_lab import bench_v1 as B
    d = B.SUITES[suite]
    scen = B.generate(suite, seed=seed_of(secret_hex, suite, head), n=d['heldout_n'])
    scen = [{k: s[k] for k in KEEP if k in s} for s in scen]
    return {'schema': SCHEMA, 'suite': suite, 'version': 1, 'world': d['world'],
            'n': len(scen), 'scenarios': scen, 'digest': scenarios_digest(scen)}


def sig3(v):
    if v is None or v == 0:
        return v
    return float(f'{v:.3g}')


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [sig3(max(0.0, c - h)), sig3(min(1.0, c + h))]


class Invalid(ValueError):
    """The sandbox's output is not what the verifier writes."""


def _num(v):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise Invalid('not a finite number')
    return float(v)


def aggregate(runs_doc: dict) -> dict:
    if not isinstance(runs_doc, dict):
        raise Invalid('not an object')
    fam = runs_doc.get('family')
    if fam not in HEADLINE:
        raise Invalid('family')
    runs = runs_doc.get('runs')
    if not isinstance(runs, list) or not 1 <= len(runs) <= MAX_RUNS:
        raise Invalid('runs')
    clean = []
    for r in runs:
        if not isinstance(r, dict) or not isinstance(r.get('success'), bool):
            raise Invalid('run')
        st = r.get('status')
        if not isinstance(st, str) or len(st) > 40:
            raise Invalid('status')
        m = r.get('metrics')
        if not isinstance(m, dict):
            raise Invalid('metrics')
        clean.append((r['success'], {k: _num(m.get(k)) for k in HEADLINE[fam]}))
    n, k = len(clean), sum(1 for ok, _ in clean if ok)
    out = {'family': fam, 'n': n, 'successes': k, 'wilson95': wilson(k, n)}
    for key in HEADLINE[fam]:
        vals = sorted(m[key] for ok, m in clean if m[key] is not None
                      and (ok or fam == 'localisation'))
        out[key + '_median'] = sig3(vals[len(vals) // 2] if len(vals) % 2 else
                                    (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2) \
            if vals else None
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('generate')
    g.add_argument('suite')
    g.add_argument('--head', required=True)
    g.add_argument('--out', required=True)
    a = sub.add_parser('aggregate')
    a.add_argument('runs')
    a.add_argument('--out', required=True)
    o = ap.parse_args()
    if o.cmd == 'generate':
        secret = os.environ.get('COCO_HELDOUT_SECRET', '')
        if not secret:
            raise SystemExit('COCO_HELDOUT_SECRET is not set')
        doc = generate(o.suite, o.head, secret)
        Path(o.out).write_text(json.dumps(doc, sort_keys=True) + '\n')
        os.chmod(o.out, 0o444)
        print(f'held-out {o.suite}: {doc["n"]} scenarios, digest {doc["digest"]}')
        return 0
    raw = Path(o.runs).read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise SystemExit('held-out runs: too large')
    Path(o.out).write_text(json.dumps(aggregate(json.loads(raw)), sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
