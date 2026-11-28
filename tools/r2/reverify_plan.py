#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R6.A7: which leaderboard entries need re-verifying, as a GitHub Actions matrix (one job per suite x entry).

    python3 tools/r2/reverify_plan.py [--all] [--out plan.json] [--github-output FILE]

An entry is re-verified (Gautham, 2026-11-28: "re-checking only entries whose versions changed") when
(a) its recorded ``versions`` differ from today's (``leaderboard._versions``: the suite version, the model's
hash version, the experiment and API versions, the verifier version -- the model and the verifier are covered
here, by their versions), or (b) its OWN inputs changed between the commit it was verified at (``host.git`` in
its result.json) and HEAD -- its suite file, its world, and for a submission its own files -- or (c) that commit
is not in this checkout's history (re-verify: the safe default). Git's own object ids decide "changed" (a tree
or blob id equal at both commits = unchanged). A model change that keeps every version is caught by the
weekly full run (``--all``, the workflow's schedule) and, before that, by the goldens in CI.

Writes the plan (every entry with its decision and reason) to ``--out``, and ``matrix`` / ``count`` to
``--github-output`` for the workflow. ``--all`` re-verifies everything (workflow_dispatch).
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
sys.path.insert(0, str(REPO / 'tools' / 'r2'))

def _git(*args):
    r = subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def object_id(commit, path):
    """Git's id of ``path`` (a tree or a blob) at ``commit``; None if it is not there."""
    return _git('rev-parse', '--verify', '--quiet', f'{commit}:{path}')


def deps(suite, name, kind):
    """The entry's own inputs: its suite file, its world, and a submission's files (versions cover the rest)."""
    out = [f'coco_lab/coco_lab/benchmarks/{suite}.v1.json']
    doc = json.loads((REPO / f'coco_lab/coco_lab/benchmarks/{suite}.v1.json').read_text())
    if doc.get('world'):
        out.append(f'worlds/{doc["world"]}.yaml')
    if kind != 'builtin':
        out.append(f'leaderboard/submissions/{suite}/{name}')
    return out


#: R6.A7: one job per entry must finish within 1 hour. A job re-runs its entry's baseline runs on the runner's
#: CPUs (4 on GitHub's public-repo runners) for at most this many CPU-minutes of the laptop's recorded time.
#: 180 was the first budget: the full matrix (run 46152197199) passed 83 of 84 entries, the longest successful job
#: 45.7 min, but arena-nav-50/mcl_augmented ran past the 60-minute limit (cancelled) -- the runner is slower than
#: the recorded compute times suggest for that entry. 100 leaves the margin.
JOB_CPU_MIN = 100.0


def cost_cpu_min(doc):
    """The entry's runs' CPU time (min) from its own recorded compute_ms: mean ~ 1.5 x median (checked by the run)."""
    total = 0.0
    for part in ('public', 'held_out'):
        s = (doc.get(part) or {}).get('score', {}).get('compute_ms') or {}
        if s.get('median') is not None and s.get('n'):
            total += 1.5 * s['median'] * s['n'] / 60000.0
    return total


def how(doc):
    """How this entry is re-verified: the procedure that made it, sampled to fit one job if it must."""
    if doc['entry']['kind'] != 'builtin' or not doc.get('baseline'):
        return {'mode': 'verify', 'baseline': '', 'family': doc['entry']['family'], 'sample': 1.0, 'cpu_min': 0.0}
    cost = cost_cpu_min(doc)
    sample = 1.0 if cost <= JOB_CPU_MIN else max(0.01, math.floor(JOB_CPU_MIN / cost * 100) / 100)
    return {'mode': 'bench', 'baseline': doc['baseline'].rstrip('/'), 'family': doc['entry']['family'],
            'sample': sample, 'cpu_min': round(cost, 1)}


def plan(force_all=False, only=()):
    import leaderboard as lb
    rows = []
    head = _git('rev-parse', 'HEAD')
    for res in sorted(REPO.glob('leaderboard/results/*/*/result.json')):
        suite, name = res.parent.parent.name, res.parent.name
        if only and f'{suite}/{name}' not in only:
            continue
        doc = json.loads(res.read_text())
        kind = doc['entry']['kind']
        row = {'suite': suite, 'name': name, 'kind': kind, 'merge_base': doc['held_out']['merge_base'], **how(doc)}
        reasons = []
        if force_all:
            reasons.append('all (requested)')
        now = lb._versions(suite)
        if doc.get('versions') != now:
            changed = sorted(k for k in set(now) | set(doc.get('versions') or {})
                             if (doc.get('versions') or {}).get(k) != now.get(k))
            reasons.append('versions: ' + ', '.join(changed))
        at = (doc.get('host') or {}).get('git')
        if not at:   # a result CI wrote (no host.git): the commit that last wrote it was verified against these inputs
            at = _git('log', '-1', '--format=%H', '--', str(res.relative_to(REPO))) or None
            row['verified_at_from'] = 'the commit that last wrote result.json'
        if not at or _git('cat-file', '-e', f'{at}^{{commit}}') is None:
            reasons.append(f'verified at {at or "an unknown commit"}, not in this history')
        else:
            moved = [p for p in deps(suite, name, kind) if object_id(at, p) != object_id(head, p)]
            if moved:
                reasons.append('changed since ' + at[:12] + ': ' + ', '.join(moved))
        row['reverify'] = bool(reasons)
        row['reasons'] = reasons
        rows.append(row)
    return {'schema': 'coco.leaderboard.reverify_plan.v1', 'head': head, 'entries': rows,
            'count': sum(r['reverify'] for r in rows), 'total': len(rows)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--only', default='', help='suite/name,... : just these entries (with --all: re-verify them)')
    ap.add_argument('--out')
    ap.add_argument('--github-output')
    a = ap.parse_args(argv)
    p = plan(a.all, tuple(x for x in a.only.split(',') if x))
    if a.out:
        Path(a.out).write_text(json.dumps(p, indent=1) + '\n')
    keys = ('suite', 'name', 'kind', 'merge_base', 'mode', 'baseline', 'family', 'sample')
    todo = [{k: r[k] for k in keys} for r in p['entries'] if r['reverify']]
    if a.github_output:
        with open(a.github_output, 'a', encoding='utf-8') as f:
            f.write(f'count={len(todo)}\n')
            f.write('matrix=' + json.dumps({'include': todo}, separators=(',', ':')) + '\n')
    sampled = [r for r in p['entries'] if r['reverify'] and r['sample'] < 1.0]
    print(f'{p["count"]} of {p["total"]} entries to re-verify (HEAD {p["head"][:12]}); '
          f'{len(sampled)} sampled to fit one job each')
    for r in p['entries']:
        if r['reverify']:
            print(f'  {r["suite"]}/{r["name"]}: {"; ".join(r["reasons"])[:200]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
