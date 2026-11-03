#!/usr/bin/env python3
"""
R1.5: write docs/v2/r1/bench/<suite>/README.md from the frozen suite and its committed
reference results (summary.json of every family). Run after tools/r1/make_references.py.

    python tools/r1/bench_readmes.py [--check]
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUITES = REPO / 'coco_lab' / 'coco_lab' / 'benchmarks'
BENCH = REPO / 'docs' / 'v2' / 'r1' / 'bench'
KEY = {'planning': ['expansions', 'path_length_m', 'path_cost'],
       'control': ['time_s', 'path_length_m', 'contacts'],
       'localisation': ['final_err_xy_m', 'mean_err_xy_m', 'converged_s'],
       'fulltask': ['time_to_complete_s', 'path_efficiency', 'contacts']}


def fmt(v):
    if v is None:
        return '—'
    if isinstance(v, int) or (isinstance(v, float) and v.is_integer() and abs(v) < 1e15):
        return f'{int(v):,}'
    return f'{v:,.1f}' if abs(v) >= 1000 else f'{v:.4g}'


def readme(suite):
    sid = suite['id']
    lines = [f'# COCO-Bench v0 · {sid} (v{suite["version"]}, draft for R3)', '',
             f'**{suite["title"]}.** {suite["tests"]}', '',
             f'- World: `{suite["world"]}` (World Spec sha256 `{suite["world_sha256"]}`)',
             f'- Scenarios: {len(suite["scenarios"])} (frozen in '
             f'[`coco_lab/coco_lab/benchmarks/{sid}.v0.json`](../../../../../coco_lab/coco_lab/benchmarks/{sid}.v0.json); '
             f'generator `{suite["generator"]["tool"]}`, {json.dumps({k: v for k, v in suite["generator"].items() if k != "tool"})})',
             f'- Families: {", ".join(suite["families"])}; metrics fixed per family in the suite file. Reference '
             f'results committed for: {", ".join(p.name for p in sorted((BENCH / sid).glob("*")) if p.is_dir())}.', '',
             'Reference results: MODEL (coco_lab, hash version 3), every built-in algorithm at its default parameters '
             '(localisation: MCL 60 particles / 12 beams, EKF 12 beams), computed natively with `coco experiment run` '
             '(`tools/r1/make_references.py`). Counts are device-independent; `compute_ms` is wall time on the machine in '
             'each manifest. Success: Wilson 95% interval; metrics: median [IQR] (type-7 quantiles) over the runs where '
             'the metric is defined, with that N.', '']
    for fam_dir in sorted(p for p in (BENCH / sid).glob('*') if p.is_dir()):
        s = json.loads((fam_dir / 'summary.json').read_text())
        man = json.loads((fam_dir / 'manifest.json').read_text())
        mdefs = {m['id']: m for m in s['metrics']}
        keys = KEY[s['family']]
        lines += [f'## {s["family"]} — {s["n_runs"]} runs, digest `{s["digest"][:16]}…`', '',
                  '| Algorithm | N | Success (Wilson 95%) | Outcomes | ' +
                  ' | '.join(f'{mdefs[k]["label"]} ({mdefs[k]["unit"]}): median [IQR] · N' for k in keys) + ' |',
                  '| --- | --- | --- | --- | ' + ' | '.join('---' for _ in keys) + ' |']
        for g in s['groups']:
            w = g['success']
            sr = f'{g["successes"]}/{g["n"]} · {100 * w["rate"]:.1f}% [{100 * w["low"]:.1f}, {100 * w["high"]:.1f}]' if w else '—'
            out = ', '.join(f'{k} {v}' for k, v in sorted(g['status'].items()))
            cells = [f'{fmt(g["metrics"][k]["median"])} [{fmt(g["metrics"][k]["q1"])}, {fmt(g["metrics"][k]["q3"])}] · {g["metrics"][k]["n"]}'
                     for k in keys]
            lines.append(f'| {g["algorithm"]} | {g["n"]} | {sr} | {out} | ' + ' | '.join(cells) + ' |')
        lines += ['', f'Files: [results.csv]({fam_dir.name}/results.csv) · [summary.json]({fam_dir.name}/summary.json) · '
                  f'[spec.json]({fam_dir.name}/spec.json) · [manifest.json]({fam_dir.name}/manifest.json) · '
                  f'[runs.jsonl]({fam_dir.name}/runs.jsonl). Host: {man["host"].get("cpu")}, '
                  f'{man["host"].get("workers")} workers (the manifest\'s wall_s includes time the laptop was '
                  'suspended; per-run compute_ms uses a monotonic clock that does not).', '']
    if suite.get('stack'):
        lines += ['## Gazebo + Nav2 (STACK)', '',
                  'Nav2 driving these rounds in Gazebo (simulation; no physical robot exists), recorded in G2: '
                  'driving legs only, no grasp. Watch one against the model in Play: "Race Nav2".', '']
        lines += [f'- {c}: [`{p}`](../../../../../{p})' for c, p in suite['stack'].items()]
    else:
        lines += ['## Gazebo + Nav2', '', 'No Gazebo + Nav2 recording of these scenarios exists yet.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    bad = 0
    for p in sorted(SUITES.glob('*.v0.json')):
        suite = json.loads(p.read_text())
        out = BENCH / suite['id'] / 'README.md'
        text = readme(suite)
        if '--check' in sys.argv:
            ok = out.exists() and out.read_text() == text
            bad += not ok
            print(suite['id'], 'current' if ok else 'STALE')
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text)
            print('wrote', out)
    sys.exit(1 if bad else 0)
