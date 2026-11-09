#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.4/R3.5: commit the Gazebo + Nav2 baselines' evidence and the model-vs-ROS 2 comparison.

    tools/r3/finalize_r34.py [RUNS_DIR]        (default ~/coco_lab_runs/r3/r34; read only)

- docs/v2/r3/data/r34/sessions/<session>/: each FINISHED session's small files (results.jsonl,
  session.json, meta.json, scenarios.json); the raw files (bags, logs) stay in RUNS_DIR, each
  named with its SHA-256 in docs/v2/r3/data/r34/raw_checksums.sha256. Unfinished/void sessions are
  listed, not copied.
- docs/v2/r3/data/r35/gap.json: tools/r3/gap.py over RUNS_DIR, plus the downloads it offers.
- docs/v2/r3/data/r35/paired/<family>.jsonl: per pair and scenario, the model run and every STACK
  repeat side by side (what the Workbench "Model vs ROS 2" tab offers for download).
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / 'docs' / 'v2' / 'r3' / 'data'
SMALL = ('results.jsonl', 'session.json', 'meta.json', 'scenarios.json')


def _gap():
    spec = importlib.util.spec_from_file_location('r3_gap', Path(__file__).with_name('gap.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sessions(runs: Path):
    out_dir = DATA / 'r34' / 'sessions'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    done, other, sums = [], [], []
    for d in sorted(p for p in runs.iterdir() if p.is_dir()):
        for f in sorted(x for x in d.rglob('*') if x.is_file()):
            sums.append(f'{sha256(f)}  {f.relative_to(runs)}')
        if not (d / 'DONE').exists() or not (d / 'results.jsonl').exists():
            other.append(d.name)
            continue
        dst = out_dir / d.name
        dst.mkdir(parents=True)
        for name in SMALL:
            if (d / name).exists():
                shutil.copyfile(d / name, dst / name)
        done.append(d.name)
    if (runs / 'queue.log').exists():
        shutil.copyfile(runs / 'queue.log', DATA / 'r34' / 'queue.log')
        sums.append(f"{sha256(runs / 'queue.log')}  queue.log")
    (DATA / 'r34' / 'raw_checksums.sha256').write_text('\n'.join(sums) + '\n')
    return done, other


def paired(G, runs: Path):
    """Rows: {family, suite, pair, scenario, model: {...}, stack: [{session, ...}]}."""
    fam_rows = {'planning': [], 'control': [], 'localisation': []}

    def slim(r, keys):
        return {k: r.get(k) for k in keys}
    for suite in ('depot-nav-100', 'depot-narrow-30', 'depot-long-50', 'depot-clutter-50'):
        model = G.model_runs(suite, 'planning')
        rows = G.stack_rows(runs, f'{suite}_plan')
        for m_alg, server, _ in G.PLAN_PAIRS:
            for sid in sorted({r['id'] for r in rows if r.get('server') == server}):
                m = model.get((m_alg, sid))
                if m is None:
                    continue
                fam_rows['planning'].append({
                    'suite': suite, 'pair': f'{m_alg} | {server}', 'scenario': sid,
                    'model': {'algorithm': m_alg, 'success': m['success'], 'status': m['status'],
                              'path_length_m': m['metrics'].get('path_length_m'), 'chain': m['chain']},
                    'stack': [slim(r, ('session', 'status', 'error_code', 'length_m', 'poses'))
                              for r in rows if r.get('server') == server and r['id'] == sid]})
    for suite, rule in (('ctrl-corridor-30', ''), ('ctrl-corners-30', ''), ('ctrl-dynamic-30', ''),
                        ('ctrl-dynamic-30', '-noyield')):
        model = G.model_runs(suite, 'control')
        for m_alg, s_ctrl in G.CTRL_PAIRS:
            rows = G.stack_rows(runs, f'{suite}{rule}_{s_ctrl}')
            for sid in sorted({r['id'] for r in rows}):
                m = model.get((m_alg, sid))
                if m is None:
                    continue
                fam_rows['control'].append({
                    'suite': suite + (' (actors keep schedule)' if rule else ''),
                    'pair': f'{m_alg} | {s_ctrl}', 'scenario': sid,
                    'model': {'algorithm': m_alg, 'success': m['success'], 'status': m['status'],
                              'time_s': m['metrics'].get('time_s'), 'contacts': m['metrics'].get('contacts'),
                              'chain': m['chain']},
                    'stack': [slim(r, ('session', 'status', 'sim_s', 'driven_m', 'truth_to_goal_m'))
                              for r in rows if r['id'] == sid]})
    model = G.model_runs('loc-track-30', 'localisation')
    for m_alg, s_loc, _ in G.LOC_PAIRS:
        rows = G.stack_rows(runs, f'loc-track-30_{s_loc}')
        for sid in sorted({r['id'] for r in rows}):
            m = model.get((m_alg, sid))
            if m is None:
                continue
            fam_rows['localisation'].append({
                'suite': 'loc-track-30', 'pair': f'{m_alg} | {s_loc}', 'scenario': sid,
                'model': {'algorithm': m_alg, 'success': m['success'], 'status': m['status'],
                          'time_s': m['metrics'].get('time_s'),
                          'final_err_xy_m': m['metrics'].get('final_err_xy_m'), 'chain': m['chain']},
                'stack': [slim(r, ('session', 'status', 'sim_s', 'driven_m', 'truth_to_goal_m'))
                          for r in rows if r['id'] == sid]})
    out = DATA / 'r35' / 'paired'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    downloads = []
    for fam, rows in fam_rows.items():
        if not rows:
            continue
        (out / f'{fam}.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
        downloads.append({'label': f'{fam} ({len(rows)} pairs)', 'path': f'r3/paired/{fam}.jsonl'})
    return downloads


def main():
    runs = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / 'coco_lab_runs' / 'r3' / 'r34'
    (DATA / 'r34').mkdir(parents=True, exist_ok=True)
    done, other = sessions(runs)
    G = _gap()
    gap_json = DATA / 'r35' / 'gap.json'
    sys_argv = sys.argv
    sys.argv = ['gap.py', str(runs), str(gap_json)]
    try:
        G.main()
    finally:
        sys.argv = sys_argv
    doc = json.loads(gap_json.read_text())
    doc['downloads'] = paired(G, runs)
    reps = {}
    for name in done:
        base, _, rep = name.rpartition('_rep')
        reps.setdefault(base, []).append(int(rep))
    doc['repeats'] = {k: sorted(v) for k, v in sorted(reps.items())}
    doc['sessions_not_used'] = other
    gap_json.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    print(f'{len(done)} finished sessions copied; not used: {other}')
    print('repeats per session kind:', {k: len(v) for k, v in doc['repeats'].items()})
    return 0


if __name__ == '__main__':
    sys.exit(main())
