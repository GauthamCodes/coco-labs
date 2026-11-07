#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R2.6: the leaderboard verifier (ADR 0012; leaderboard/CONTRIBUTING.md). MODEL evidence.

    leaderboard.py verify SUBMISSION_DIR --out OUT_DIR [--merge-base SHA] [--workers N]
    leaderboard.py claim SUBMISSION_DIR            (writes its summary.json: the claim)
    leaderboard.py builtin SUITE NAME --out OUT_DIR [--workers N]
    leaderboard.py index --out lab_web/public/generated/r2/leaderboard.json

``verify`` checks a submission (``algorithm.py``, ``meta.yaml``, ``summary.json``), re-runs it
natively on the suite's public scenarios and on held-out scenarios, runs every run twice
(determinism), checks the contract and the claim, and writes ``result.json``
(``coco.leaderboard.entry.v1``) and ``report.md`` to OUT_DIR. ``builtin`` writes the same for a
built-in reference entry. Nothing here reads the network, a secret or the wall clock except
the reported compute times.

**Held-out scenarios.** ``seed = int(sha256(SALT || suite id || merge-base sha)[:13], 16)``;
the scenarios are drawn by the suite's own generator settings (``coco_lab.exp_scenarios``) with
that seed. The salt is committed in this file and the verifier workflow, so anyone can compute
the held-out set once they know the merge-base: this is NOT a secret. It catches overfitting
to the published scenarios by chance or habit, not a determined cheat (which code review must:
CONTRIBUTING forbids hard-coded scenarios). Stated in ADR 0012.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'coco_lab'), str(REPO / 'coco_schemas'), str(REPO / 'coco_config')]

from coco_lab import bench_v1 as B, experiments as ex, exp_stats, exp_user  # noqa: E402
from coco_lab.user_code import load  # noqa: E402

#: 2 (R3.6, Leaderboard v1): judged on COCO-Bench v1 -- every v1 suite, every family it serves;
#: the held-out draw comes from the suite's own v1 generator (coco_lab.bench_v1)
VERIFIER_VERSION = 2
SUITE_VERSION = 1
SCHEMA = 'coco.leaderboard.entry.v1'
SALT = 'coco-lab.leaderboard.held-out.v1'
LICENCES = ('MIT', 'Apache-2.0')
HELD_OUT_N = {sid: d['heldout_n'] for sid, d in B.SUITES.items()}
FAMILY_SUITES = {fam: tuple(sid for sid, d in B.SUITES.items() if fam in d['families'])
                 for fam in ('planning', 'control', 'localisation')}
#: the reference entries' held-out label: the same draw as the R3.2 baselines (make_baselines.py)
REFERENCE = 'reference-v1'
INLINE = ('id', 'start', 'goal', 'seed', 'config', 'kidnap_at_s', 'kidnap')
NAME = re.compile(r'^[a-z0-9][a-z0-9_-]{1,39}$')
WALL = ('call_ms_max', 'call_ms_total', 'max_call_index')


class SubmissionError(ValueError):
    """The submission is not well formed (reported on the PR)."""


def held_out_seed(suite_id: str, merge_base: str) -> int:
    """Return the held-out scenarios' seed (53 bits, as every experiment seed)."""
    h = hashlib.sha256(f'{SALT}|{suite_id}|{merge_base}'.encode()).hexdigest()
    return int(h[:13], 16)


def read_meta(d: Path) -> dict:
    """Read and check meta.yaml."""
    import yaml
    try:
        meta = yaml.safe_load((d / 'meta.yaml').read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as e:
        raise SubmissionError(f'meta.yaml: {e}') from None
    if not isinstance(meta, dict):
        raise SubmissionError('meta.yaml is a mapping')
    need = ('author', 'display_name', 'description', 'licence')
    missing = [k for k in need if not isinstance(meta.get(k), str) or not meta[k].strip()]
    if missing:
        raise SubmissionError(f'meta.yaml needs {missing}')
    if meta['licence'] not in LICENCES:
        raise SubmissionError(f'licence must be one of {LICENCES} (got {meta["licence"]!r})')
    paper = meta.get('paper')
    if paper is not None and not (isinstance(paper, str) and paper.startswith('https://')):
        raise SubmissionError('paper, when given, is an https:// link')
    extra = set(meta) - {*need, 'paper', 'params'}
    if extra:
        raise SubmissionError(f'meta.yaml has unknown keys {sorted(extra)}')
    params = meta.get('params') or {}
    if not isinstance(params, dict):
        raise SubmissionError('params is a mapping of user.<name> parameters')
    return {**{k: meta[k].strip() for k in need}, 'paper': paper, 'params': params}


def _spec(family, suite_id, algos, scenarios, max_ticks=3000):
    st = ex.suite(suite_id, SUITE_VERSION)
    return {'schema': ex.SCHEMA, 'family': family, 'world': st['world'], 'seed': 1,
            'algorithms': algos, 'scenarios': scenarios, 'limits': {'max_ticks': max_ticks}}


def _run(p, workers, codes):
    if workers > 1 or codes:
        return ex._pool_run(p, workers, codes)
    return ex.run_all(p)


def _q(values):
    d = exp_stats.describe(values)
    return {'n': d['n'], 'median': d['median'], 'q1': d['q1'], 'q3': d['q3']}


def score(family: str, records: list, optimal: dict) -> dict:
    """Return the ranking metrics (deterministic: no wall time) of one algorithm's records."""
    n = len(records)
    k = sum(1 for r in records if r['success'])
    w = exp_stats.wilson(k, n) if n else None
    out = {'n': n, 'successes': k, 'success_rate': k / n if n else None,
           'wilson95': [w['low'], w['high']] if w else None}
    ok = [r for r in records if r['success']]
    if family == 'planning':
        ratios = [r['metrics']['path_length_m'] / optimal[r['scenario']] for r in ok
                  if optimal.get(r['scenario'])]
        out['path_ratio'] = _q(ratios)
        out['expansions'] = _q([r['metrics']['expansions'] for r in ok
                                if r['metrics']['expansions'] is not None])
        out['min_clearance_m'] = _q([r['metrics']['min_clearance_m'] for r in ok])
    elif family == 'control':
        out['time_s'] = _q([r['metrics']['time_s'] for r in ok])
        out['min_clearance_m'] = _q([r['metrics']['min_clearance_m'] for r in ok])
        out['contacts'] = sum(r['metrics']['contacts'] or 0 for r in records)
    else:
        out['final_err_xy_m'] = _q([r['metrics']['final_err_xy_m'] for r in records
                                    if r['metrics'].get('final_err_xy_m') is not None])
        out['mean_err_xy_m'] = _q([r['metrics']['mean_err_xy_m'] for r in records
                                   if r['metrics'].get('mean_err_xy_m') is not None])
    out['compute_ms'] = _q([r['metrics'].get('compute_ms') for r in records])
    out['failures'] = [{'scenario': r['scenario'], 'scenario_index': r['scenario_index'],
                        'status': r['status']} for r in records if not r['success']]
    return out


def worst(family: str, records: list, optimal: dict):
    """The run to replay: the first failure, else the worst on the family's headline metric."""
    bad = [r for r in records if not r['success']]
    if bad:
        return {'scenario_index': bad[0]['scenario_index'], 'scenario': bad[0]['scenario'],
                'why': bad[0]['status']}
    if family == 'planning':
        key = lambda r: r['metrics']['path_length_m'] / (optimal.get(r['scenario']) or 1)  # noqa: E731
    elif family == 'control':
        key = lambda r: r['metrics']['time_s']  # noqa: E731
    else:
        key = lambda r: r['metrics'].get('final_err_xy_m') or 0  # noqa: E731
    r = max(records, key=key) if records else None
    return r and {'scenario_index': r['scenario_index'], 'scenario': r['scenario'],
                  'why': 'worst ' + {'planning': 'path ratio', 'control': 'time',
                                     'localisation': 'final error'}[family]}


def scenario_sets(suite_id: str, merge_base: str) -> dict:
    """The public scenarios (the frozen suite) and the held-out ones (see the module)."""
    held = B.generate(suite_id, seed=held_out_seed(suite_id, merge_base), n=HELD_OUT_N[suite_id])
    return {'public': {'kind': 'suite', 'id': suite_id, 'version': SUITE_VERSION},
            'held_out': {'kind': 'inline',
                         'scenarios': [{k: x[k] for k in INLINE if k in x} for x in held]}}


def canonical_spec(family: str, suite_id: str, algo: dict, scenarios: dict) -> dict:
    """The one spec an entry is run with: anyone can run it (`coco experiment run`)."""
    return _spec(family, suite_id, [algo], scenarios)


def evaluate(family, suite_id, algo, codes, workers, merge_base):
    """Run public and held-out scenarios; return {public, held_out} with scores."""
    out = {}
    for which, scenarios in scenario_sets(suite_id, merge_base).items():
        p = ex.plan(canonical_spec(family, suite_id, algo, scenarios))
        mine = _run(p, workers, codes)
        optimal = {}
        if family == 'planning':
            # the grid-optimal length: Dijkstra with no cost term, 8-connected, same costmap
            q = ex.plan(_spec(family, suite_id, [{'name': 'dijkstra', 'id': 'grid_optimal',
                                                   'params': {'cost_weight': 0.0}}], scenarios))
            optimal = {r['scenario']: r['metrics']['path_length_m'] for r in _run(q, workers, {})
                       if r['success']}
        out[which] = {'spec_id': p['id'], 'digest': ex.digest(mine), 'records': mine,
                      'score': score(family, mine, optimal), 'worst': worst(family, mine, optimal),
                      'scenarios': len(p['scenarios'])}
        if which == 'public':
            out[which]['tiers'] = tier_scores(suite_id, mine)
    return out


#: R3 (ADR 0014): per family, the only per-run numbers the held-out run writes
HELDOUT_METRICS = {'planning': ('path_ratio', 'min_clearance_m'),
                   'control': ('time_s', 'min_clearance_m'),
                   'localisation': ('final_err_xy_m', 'mean_err_xy_m')}


def heldout(d: Path, scenarios_file: Path, out: Path, workers: int) -> int:
    """
    Run a submission on a held-out scenario file (ADR 0014; inside the sandbox).

    Writes ``out/heldout_runs.json``: per run its status, success and the family's two headline
    numbers -- nothing about the scenarios. The trusted workflow reads it as data and publishes
    rounded aggregates only (tools/r3/heldout.py aggregate).
    """
    doc = json.loads(scenarios_file.read_text(encoding='utf-8'))
    meta, src, family, algo = user_entry(d)
    world = doc['world']
    spec = {'schema': ex.SCHEMA, 'family': family, 'world': world, 'seed': 1,
            'algorithms': [algo], 'limits': {'max_ticks': 3000},
            'scenarios': {'kind': 'inline', 'scenarios': doc['scenarios']}}
    p = ex.plan(spec)
    recs = _run(p, workers, {algo['code_sha256']: src})
    optimal = {}
    if family == 'planning':
        q = ex.plan(dict(spec, algorithms=[{'name': 'dijkstra', 'id': 'grid_optimal',
                                            'params': {'cost_weight': 0.0}}]))
        optimal = {r['scenario']: r['metrics']['path_length_m'] for r in _run(q, workers, {})
                   if r['success']}
    runs = []
    for r in recs:
        m = dict(r['metrics'])
        if family == 'planning':
            opt = optimal.get(r['scenario'])
            m['path_ratio'] = (m['path_length_m'] / opt) if (r['success'] and opt) else None
        runs.append({'status': r['status'], 'success': r['success'],
                     'metrics': {k: m.get(k) for k in HELDOUT_METRICS[family]}})
    out.mkdir(parents=True, exist_ok=True)
    (out / 'heldout_runs.json').write_text(json.dumps(
        ex.plain({'family': family, 'runs': runs}), sort_keys=True, allow_nan=False) + '\n')
    return len(runs)


def user_entry(d: Path):
    """Return (meta, source, module kind -> family, the canonical algorithm entry)."""
    meta = read_meta(d)
    src = (d / 'algorithm.py').read_text(encoding='utf-8')
    mod = load(src)
    family = {'planner': 'planning', 'controller': 'control', 'localiser': 'localisation'}[mod.kind]
    sha = exp_user.register(src)
    algo = {'name': 'user', 'id': d.name, 'label': meta['display_name'], 'api': 1,
            'code_sha256': sha, 'params': {f'user.{k}': v for k, v in meta['params'].items()}}
    return meta, src, family, algo


def claim(d: Path, workers: int) -> dict:
    """Write the submission's summary.json: the canonical public run's summary (the claim)."""
    meta, src, family, algo = user_entry(d)
    p = ex.plan(canonical_spec(family, d.parent.name, algo, {'kind': 'suite', 'id': d.parent.name}))
    recs = _run(p, workers, {algo['code_sha256']: src})
    summ = ex.plain(ex.summarise(p, recs))
    (d / 'summary.json').write_text(json.dumps(summ, indent=1, sort_keys=True,
                                               allow_nan=False) + '\n')
    return summ


def verify(d: Path, out: Path, merge_base: str, workers: int) -> dict:
    """Verify one submission directory: leaderboard/submissions/<suite>/<name>/."""
    suite_id, name = d.parent.name, d.name
    problems = []
    result = {'schema': SCHEMA, 'verified': False, 'problems': problems}
    try:
        if not NAME.match(name):
            raise SubmissionError(f'the directory name {name!r}: lower-case letters, digits, _ -')
        if suite_id not in HELD_OUT_N:
            raise SubmissionError(f'suite {suite_id!r}: one of {sorted(HELD_OUT_N)}')
        files = sorted(p.name for p in d.iterdir())
        if files != ['algorithm.py', 'meta.yaml', 'summary.json']:
            raise SubmissionError(f'a submission holds exactly algorithm.py, meta.yaml and '
                                  f'summary.json (found {files})')
        meta, src, family, algo = user_entry(d)
        sha = algo['code_sha256']
        if suite_id not in FAMILY_SUITES[family]:
            raise SubmissionError(f'{suite_id} has no {family} board')
        try:
            claimed_summary = json.loads((d / 'summary.json').read_text(encoding='utf-8'))
        except ValueError as e:
            raise SubmissionError(f'summary.json: {e}') from None
        ev = evaluate(family, suite_id, algo, {sha: src}, workers, merge_base)
        nondet = [r['index'] for w in ev.values() for r in w['records']
                  if r.get('deterministic') is False]
        contract = sum((r.get('report') or {}).get('n_problems', 0)
                       for w in ev.values() for r in w['records'])
        clamped = sum((r.get('report') or {}).get('clamped', 0)
                      for w in ev.values() for r in w['records'])
        claimed = claimed_summary.get('digest') if isinstance(claimed_summary, dict) else None
        if nondet:
            problems.append(f'{len(nondet)} run(s) are not deterministic (two runs, different '
                            'hash chains): a non-deterministic algorithm cannot be submitted')
        if claimed != ev['public']['digest']:
            problems.append(f'the claimed summary.json digest {str(claimed)[:16]}... is not the '
                            f'verified {ev["public"]["digest"][:16]}... (run `coco experiment run` '
                            'on the suite and commit its summary.json)')
        result.update({
            'versions': _versions(suite_id),
            'entry': {'suite': suite_id, 'name': name, 'kind': 'submission', 'family': family,
                      'code_sha256': sha, 'code_path': f'leaderboard/submissions/{suite_id}/'
                      f'{name}/algorithm.py', **meta},
            'public': _public(ev['public']),
            'held_out': dict(_public(ev['held_out']), merge_base=merge_base,
                             seed=held_out_seed(suite_id, merge_base),
                             n=HELD_OUT_N[suite_id]),
            'checks': {'deterministic': not nondet, 'nondeterministic_runs': nondet[:20],
                       'contract_problems': contract, 'clamped_outputs': clamped,
                       'claimed_digest': claimed, 'claim_matches': claimed ==
                       ev['public']['digest']},
            'host': ex._host(workers),
        })
        result['verified'] = not problems
    except SubmissionError as e:
        problems.append(str(e))
    except Exception as e:  # the file's own top level, or a guard refusal
        problems.append(f'{type(e).__name__}: {e}')
    _write(out, result)
    return result


BENCH = REPO / 'docs' / 'v2' / 'r3' / 'bench'


def builtins_from_bench(suite_id: str, family: str, root: Path, workers: int) -> list:
    """
    R3.6: every built-in's reference entry for one v1 suite and family, from the R3.2 baseline runs.

    The baselines ran the same public suite and the same held-out draw (``REFERENCE``), so their
    records ARE these entries' runs; nothing is recomputed but the grid-optimal lengths (planning).
    The entry names the baseline's spec (``spec_id``): re-running that committed spec reproduces
    every chain. Written to ROOT/<suite>/<name>/result.json + report.md.
    """
    base = BENCH / suite_id / family
    held = scenario_sets(suite_id, REFERENCE)['held_out']['scenarios']
    spec_held = json.loads((base / 'held_out' / 'spec.json').read_text())['scenarios']['scenarios']
    if spec_held != held:
        raise SystemExit(f'{suite_id}/{family}: the baseline held-out draw is not REFERENCE\'s')
    sets = {'public': {'kind': 'suite', 'id': suite_id, 'version': SUITE_VERSION},
            'held_out': {'kind': 'inline', 'scenarios': held}}
    optimal = {}
    if family == 'planning':
        for which, sc in sets.items():
            q = ex.plan(_spec(family, suite_id, [{'name': 'dijkstra', 'id': 'grid_optimal',
                                                  'params': {'cost_weight': 0.0}}], sc))
            optimal[which] = {r['scenario']: r['metrics']['path_length_m']
                              for r in _run(q, workers, {}) if r['success']}
    recs = {w: [json.loads(x) for x in (base / w / 'runs.jsonl').read_text().splitlines()]
            for w in sets}
    spec_ids = {w: json.loads((base / w / 'spec.json').read_text()) for w in sets}
    names = sorted({r['algorithm'] for r in recs['public']}, key=ex.ALGORITHMS[family].index)
    out = []
    for name in names:
        ev = {}
        for w in sets:
            mine = [r for r in recs[w] if r['algorithm'] == name]
            ev[w] = {'spec_id': ex.spec_id(spec_ids[w]), 'digest': ex.digest(mine),
                     'records': mine, 'scenarios': len(mine),
                     'score': score(family, mine, optimal.get(w, {})),
                     'worst': worst(family, mine, optimal.get(w, {}))}
            if w == 'public':
                ev[w]['tiers'] = tier_scores(suite_id, mine)
        result = {'schema': SCHEMA, 'verified': True, 'problems': [], 'versions': _versions(suite_id),
                  'entry': {'suite': suite_id, 'name': name, 'kind': 'builtin', 'family': family,
                            'display_name': ex.LABELS[name],
                            'author': 'COCO Lab (built-in reference)',
                            'description': f'The built-in {ex.LABELS[name]}, as the Workbench runs '
                                           f'it (COCO-Bench v1 baseline, R3.2).',
                            'licence': 'Apache-2.0', 'paper': None, 'code_sha256': None,
                            'code_path': 'coco_lab/coco_lab/'},
                  'public': _public(ev['public']),
                  'held_out': dict(_public(ev['held_out']), merge_base=REFERENCE,
                                   seed=held_out_seed(suite_id, REFERENCE), n=HELD_OUT_N[suite_id]),
                  'checks': {'deterministic': True, 'contract_problems': 0, 'clamped_outputs': 0,
                             'claimed_digest': None, 'claim_matches': None},
                  'baseline': f'docs/v2/r3/bench/{suite_id}/{family}/'}
        _write(root / suite_id / name, result)   # algorithm names are unique across families
        out.append(result)
    return out


def builtin(suite_id: str, name: str, out: Path, workers: int) -> dict:
    """A built-in as a reference entry (held-out at the label REFERENCE, the baselines' draw)."""
    family = next(f for f, algos in ex.ALGORITHMS.items() if name in algos and f != 'fulltask')
    algo = {'name': name, 'id': name, 'label': ex.LABELS[name]}
    ev = evaluate(family, suite_id, algo, {}, workers, REFERENCE)
    result = {'schema': SCHEMA, 'verified': True, 'problems': [], 'versions': _versions(suite_id),
              'entry': {'suite': suite_id, 'name': name, 'kind': 'builtin', 'family': family,
                        'display_name': ex.LABELS[name], 'author': 'COCO Lab (built-in reference)',
                        'description': f'The built-in {ex.LABELS[name]}, as the Workbench runs it.',
                        'licence': 'Apache-2.0', 'paper': None, 'code_sha256': None,
                        'code_path': 'coco_lab/coco_lab/'},
              'public': _public(ev['public']),
              'held_out': dict(_public(ev['held_out']), merge_base=REFERENCE,
                               seed=held_out_seed(suite_id, REFERENCE), n=HELD_OUT_N[suite_id]),
              'checks': {'deterministic': True, 'contract_problems': 0, 'clamped_outputs': 0,
                         'claimed_digest': None, 'claim_matches': None},
              'host': ex._host(workers)}
    _write(out, result)
    return result


def _versions(suite_id):
    st = ex.suite(suite_id, SUITE_VERSION)
    return {'suite': suite_id, 'suite_version': st['version'], 'model_hash_version':
            ex.MODEL['hash_version'], 'experiment': ex.MODEL['experiment'],
            'api': ex.API_VERSION, 'verifier': VERIFIER_VERSION}


def tier_scores(suite_id: str, records: list) -> dict:
    """R3.6: success per difficulty tier of the v1 suite (public scenarios only; held-out has none)."""
    tier = {x['id']: x['tier'] for x in ex.suite(suite_id, SUITE_VERSION)['scenarios']}
    out = {}
    for t in B.TIERS:
        rs = [r for r in records if tier.get(r['scenario']) == t]
        k = sum(1 for r in rs if r['success'])
        w = exp_stats.wilson(k, len(rs)) if rs else None
        out[t] = {'n': len(rs), 'successes': k, 'wilson95': [w['low'], w['high']] if w else None}
    return out


def _public(w):
    return {'spec_id': w['spec_id'], 'digest': w['digest'], 'scenarios': w['scenarios'],
            'score': w['score'], 'worst': w['worst'],
            **({'tiers': w['tiers']} if 'tiers' in w else {}),
            'runs': [{'scenario_index': r['scenario_index'], 'scenario': r['scenario'],
                      'status': r['status'], 'chain': r['chain'],
                      'counts': ex.counts(r)} for r in w['records']]}


def _write(out: Path, result: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / 'result.json').write_text(json.dumps(ex.plain(result), indent=1, sort_keys=True,
                                                allow_nan=False) + '\n')
    (out / 'report.md').write_text(report_md(result))


def report_md(r: dict) -> str:
    """The PR comment: verdict, checks and the headline numbers."""
    e = r.get('entry') or {}
    lines = [f"## Leaderboard verification: {'VERIFIED' if r['verified'] else 'NOT VERIFIED'}",
             '', f"`{e.get('suite', '?')}/{e.get('name', '?')}` · {e.get('family', '?')} · "
             f"verifier {VERIFIER_VERSION} · MODEL (coco_lab, natively; in CI inside the sandboxed container)", '']
    if r['problems']:
        lines += ['**Problems**', ''] + [f'- {p}' for p in r['problems']] + ['']
    for part in ('public', 'held_out'):
        s = (r.get(part) or {}).get('score')
        if not s:
            continue
        w = s['wilson95']
        row = f"- **{part.replace('_', '-')}** ({s['n']} scenarios): success {s['successes']}/{s['n']}"
        if w:
            row += f' (Wilson 95% {w[0]:.3f}–{w[1]:.3f})'
        for k in ('path_ratio', 'expansions', 'min_clearance_m', 'time_s', 'final_err_xy_m'):
            if k in s and s[k]['median'] is not None:
                row += f"; {k} median {s[k]['median']:.4g}"
        lines.append(row)
    c = r.get('checks')
    if c:
        lines += ['', f"- deterministic (every run twice): {c['deterministic']}",
                  f"- contract problems: {c['contract_problems']}; clamped outputs: "
                  f"{c['clamped_outputs']}", f"- claim matches: {c['claim_matches']}"]
    return '\n'.join(lines) + '\n'


def index(out: Path) -> None:
    """Gather leaderboard/results/**/result.json into the page's one file (ranked per suite)."""
    rows = []
    stack_file = REPO / 'docs' / 'v2' / 'r2' / 'data' / 'r27' / 'stack.json'
    stack = json.loads(stack_file.read_text())['entries'] if stack_file.exists() else {}
    for p in sorted((REPO / 'leaderboard' / 'results').glob('*/*/result.json')):
        r = json.loads(p.read_text())
        if r.get('verified'):
            sha = r['entry'].get('code_sha256')
            if sha in stack:   # R2.7: the same file, run as a ROS 2 node (MODEL beside STACK)
                r['stack'] = stack[sha]
            rows.append(r)
    boards = {}
    for r in rows:
        e = r['entry']
        boards.setdefault(f"{e['suite']}:{e['family']}", []).append(r)

    def rank(r):
        s, fam = r['public']['score'], r['entry']['family']
        med = lambda k: (s.get(k) or {}).get('median')  # noqa: E731
        inf = float('inf')
        if fam == 'planning':
            return (-(s['success_rate'] or 0), med('path_ratio') or inf, -(med('min_clearance_m') or 0),
                    med('expansions') or inf, r['entry']['name'])
        if fam == 'control':
            return (-(s['success_rate'] or 0), med('time_s') or inf, -(med('min_clearance_m') or 0),
                    r['entry']['name'])
        return (-(s['success_rate'] or 0), med('final_err_xy_m') or inf, r['entry']['name'])
    for k in boards:
        boards[k].sort(key=rank)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ex.plain({'schema': 'coco.leaderboard.v1', 'boards': boards,
                                        'verifier': VERIFIER_VERSION}), sort_keys=True) + '\n')
    print(f'{out}: {len(rows)} entries on {len(boards)} boards')


def main(argv=None):
    """Run the command line."""
    ap = argparse.ArgumentParser(prog='leaderboard.py')
    sub = ap.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('verify')
    v.add_argument('dir')
    v.add_argument('--out', required=True)
    v.add_argument('--merge-base', default=os.environ.get('MERGE_BASE', 'local'))
    v.add_argument('--workers', type=int, default=2)
    b = sub.add_parser('builtin')
    b.add_argument('suite')
    b.add_argument('name')
    b.add_argument('--out', required=True)
    b.add_argument('--workers', type=int, default=2)
    bb = sub.add_parser('builtin-bench', help='R3.6: reference entries from the v1 baselines')
    bb.add_argument('suite')
    bb.add_argument('family')
    bb.add_argument('--root', default=str(REPO / 'leaderboard' / 'results'))
    bb.add_argument('--workers', type=int, default=2)
    c = sub.add_parser('claim', help="write a submission's summary.json (the claim)")
    c.add_argument('dir')
    c.add_argument('--workers', type=int, default=2)
    i = sub.add_parser('index')
    i.add_argument('--out', required=True)
    h = sub.add_parser('heldout', help='R3 (ADR 0014): run on a held-out file, write numbers only')
    h.add_argument('dir')
    h.add_argument('--scenarios', required=True)
    h.add_argument('--out', required=True)
    h.add_argument('--workers', type=int, default=2)
    a = ap.parse_args(argv)
    if a.cmd == 'index':
        index(Path(a.out))
        return 0
    os.environ['PYTHONHASHSEED'] = '0'
    if a.cmd == 'heldout':
        n = heldout(Path(a.dir), Path(a.scenarios), Path(a.out), a.workers)
        print(f'held-out: {n} runs written')   # no scenario, no number: the log is public
        return 0
    if a.cmd == 'claim':
        summ = claim(Path(a.dir), a.workers)
        print(f"wrote {Path(a.dir) / 'summary.json'}: digest {summ['digest']}")
        return 0
    if a.cmd == 'builtin-bench':
        for r in builtins_from_bench(a.suite, a.family, Path(a.root), a.workers):
            sc = r['public']['score']
            print(f"{r['entry']['suite']}/{r['entry']['name']}: {sc['successes']}/{sc['n']}")
        return 0
    if a.cmd == 'builtin':
        r = builtin(a.suite, a.name, Path(a.out), a.workers)
    else:
        r = verify(Path(a.dir), Path(a.out), a.merge_base, a.workers)
    print(report_md(r))
    return 0 if r['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
