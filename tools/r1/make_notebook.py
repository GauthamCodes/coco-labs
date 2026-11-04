#!/usr/bin/env python3
"""
R1.6: write docs/v2/r1/notebooks/analyse_experiment.ipynb and execute it once (outputs kept).

Needs nbformat + nbclient + ipykernel + pandas + matplotlib (a notebook venv, not the test
venv: ~/coco_labs_ws/r1_nb_venv). The notebook reads an export -- by default the committed
depot-nav-100 planning reference results -- and reproduces the summary from results.csv.

    <nb venv>/bin/python tools/r1/make_notebook.py [--no-execute]
"""
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'docs' / 'v2' / 'r1' / 'notebooks' / 'analyse_experiment.ipynb'
COLAB = ('https://colab.research.google.com/github/GauthamCodes/coco-labs/blob/main/'
         'docs/v2/r1/notebooks/analyse_experiment.ipynb')

CELLS = [
    new_markdown_cell(f"""# Analyse a COCO Lab experiment export

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB})

Every experiment in COCO Lab's Workbench (and `coco experiment run spec.json --out dir/`)
exports the same files: `results.csv` (one row per run, failures and timeouts included),
`summary.json`, `spec.json`, `manifest.json` and `runs.jsonl`. This notebook loads one,
checks its checksums, **recomputes the summary from `results.csv`** with pandas and checks it
against `summary.json`, then draws the summary plots with matplotlib.

Evidence class: **MODEL** (coco_lab, the kinematic model that runs in the browser; not ROS 2,
not a robot). Counts (expansions, lengths, ticks, success) are the same on every device;
`compute_ms` is wall time on the device the manifest names.

Statistics, as COCO Lab computes them (`coco_lab/coco_lab/exp_stats.py`): success rates
with Wilson 95% intervals; medians and IQRs with linear-interpolation quantiles (Hyndman and
Fan type 7, pandas' default) over the runs where a metric is defined; paired comparisons on
shared scenarios with the Wilcoxon signed-rank test (exact up to 50 non-zero pairs), the
rank-biserial correlation and the Hodges-Lehmann shift, McNemar's exact test for success, and
Holm's adjustment across algorithm pairs."""),
    new_code_cell("""import hashlib, json, math, urllib.request
from pathlib import Path
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

# An export directory (unzip a Workbench export here), or the committed reference results.
EXPORT = Path('../bench/depot-nav-100/planning')
RAW = 'https://raw.githubusercontent.com/GauthamCodes/coco-labs/main/docs/v2/r1/bench/depot-nav-100/planning/'
if not (EXPORT / 'results.csv').exists():          # e.g. in Colab: fetch the same files
    EXPORT = Path('export'); EXPORT.mkdir(exist_ok=True)
    for name in ('results.csv', 'summary.json', 'spec.json', 'manifest.json'):
        urllib.request.urlretrieve(RAW + name, EXPORT / name)
results = pd.read_csv(EXPORT / 'results.csv')
summary = json.loads((EXPORT / 'summary.json').read_text())
spec = json.loads((EXPORT / 'spec.json').read_text())
manifest = json.loads((EXPORT / 'manifest.json').read_text())
print(spec['title'] or spec['family'], '|', spec['world'], '|', len(results), 'runs |',
      'algorithms:', [a['id'] for a in spec['algorithms']])
print('digest', manifest['digest'], '| host', manifest['host'].get('runner'), manifest['host'].get('cpu'))"""),
    new_code_cell("""# Checksums: every file is the one the manifest describes.
for name, info in manifest['files'].items():
    p = EXPORT / name
    if p.exists():
        ok = hashlib.sha256(p.read_bytes()).hexdigest() == info['sha256']
        print(f'{name:14s} {info["bytes"]:>9d} B  sha256 {"matches" if ok else "DIFFERS"}')"""),
    new_code_cell("""# Recompute the summary from results.csv and compare with summary.json.
Z = 1.959963984540054
def wilson(k, n):
    if n == 0: return None
    p, z2 = k / n, Z * Z
    den = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / den
    half = Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return (0.0 if k == 0 else max(0.0, centre - half), 1.0 if k == n else min(1.0, centre + half))

metrics = [m['id'] for m in summary['metrics']]
rows, worst = [], 0.0
for g in summary['groups']:
    sel = results[(results.algorithm == g['algorithm']) & (results.sweep_index == g['sweep_index'])]
    k, n = int(sel.success.sum()), len(sel)
    lo, hi = wilson(k, n) or (None, None)
    assert (k, n) == (g['successes'], g['n']), g['algorithm']
    if g['success']:
        worst = max(worst, abs(lo - g['success']['low']), abs(hi - g['success']['high']))
    row = {'algorithm': g['algorithm'], 'sweep': g['sweep_index'], 'N': n, 'success': f'{k}/{n}',
           'wilson95': f'[{lo:.3f}, {hi:.3f}]' if n else '-'}
    for m in metrics:
        v = sel[m].dropna().astype(float)
        mine = (len(v), v.median() if len(v) else None, v.quantile(.25) if len(v) else None, v.quantile(.75) if len(v) else None)
        ref = g['metrics'][m]
        assert mine[0] == ref['n'], (g['algorithm'], m)
        for a, b in zip(mine[1:], (ref['median'], ref['q1'], ref['q3'])):
            if a is not None:
                worst = max(worst, abs(a - b) / max(1.0, abs(b)))
        if m in metrics[:3]:
            row[m] = f'{mine[1]:.4g} [{mine[2]:.4g}, {mine[3]:.4g}]' if mine[0] else '-'
    rows.append(row)
print(f'summary.json reproduced from results.csv: largest relative difference {worst:.2e}')
pd.DataFrame(rows)"""),
    new_code_cell("""# Success rate per algorithm, Wilson 95% interval (sweep point 0).
g0 = [g for g in summary['groups'] if g['sweep_index'] == 0]
fig, ax = plt.subplots(figsize=(7, 0.6 + 0.5 * len(g0)))
for i, g in enumerate(g0):
    s = g['success']
    ax.barh(i, s['rate'] if s else 0, color='#2a78d6', height=0.55)
    if s:
        ax.errorbar(s['rate'], i, xerr=[[s['rate'] - s['low']], [s['high'] - s['rate']]], color='black', capsize=4)
    ax.text(1.01, i, f"{g['successes']}/{g['n']}", va='center')
ax.set_yticks(range(len(g0)), [g['algorithm'] for g in g0]); ax.set_xlim(0, 1)
ax.set_xlabel('success rate (Wilson 95%)'); ax.set_title('Success')
plt.tight_layout(); plt.show()"""),
    new_code_cell("""# Box plots: quartile box, median, whiskers to min and max (as the Workbench draws them).
shown = [m for m in summary['metrics'] if m['test'] and not m['timing']][:3]
fig, axes = plt.subplots(1, len(shown), figsize=(5 * len(shown), 3.4))
for ax, m in zip(axes if len(shown) > 1 else [axes], shown):
    data = [results[(results.algorithm == g['algorithm']) & (results.sweep_index == 0)][m['id']].dropna() for g in g0]
    ax.boxplot(data, vert=False, whis=(0, 100), tick_labels=[f"{g['algorithm']} (N={len(d)})" for g, d in zip(g0, data)])
    ax.set_xlabel(f"{m['label']} ({m['unit']})"); ax.set_title(m['label'])
plt.tight_layout(); plt.show()"""),
    new_code_cell("""# One point per run.
x, y = ('expansions', 'path_length_m') if spec['family'] == 'planning' else (shown[0]['id'], shown[1]['id'])
fig, ax = plt.subplots(figsize=(7, 4.5))
for i, (alg, part) in enumerate(results[results.sweep_index == 0].groupby('algorithm', sort=False)):
    ax.scatter(part[x], part[y], s=22, label=alg, marker='osD^v*'[i % 6])
ax.set_xlabel(x); ax.set_ylabel(y); ax.legend(); ax.set_title('Runs')
plt.tight_layout(); plt.show()"""),
    new_code_cell("""# Paired comparisons on shared scenarios (from summary.json), for one metric.
metric = shown[0]['id']
pd.DataFrame([{'A': p['a'], 'B': p['b'], 'pairs': p['metrics'][metric]['n_pairs'],
               'median diff': p['metrics'][metric]['median_diff'],
               'Hodges-Lehmann': p['metrics'][metric]['hodges_lehmann'],
               'rank-biserial r': p['metrics'][metric]['rank_biserial'],
               'p': p['metrics'][metric]['p'], 'p (Holm)': p['metrics'][metric].get('p_holm'),
               'verdict': p['metrics'][metric].get('verdict'), 'why no test': p['metrics'][metric]['reason']}
              for p in summary['paired'] if p['sweep_index'] == 0])"""),
    new_markdown_cell("""Every run is in `results.csv`, failures and timeouts included; a metric that is
undefined for a run (for example path length when no path was found) is empty there and is
excluded from that metric's N, which is always reported. Re-running the spec — in the
browser from its link, or with `coco experiment run spec.json --out dir/` — gives the same
counts and the same digest."""),
]


def main():
    out, export = OUT, None
    if '--out' in sys.argv:
        out = Path(sys.argv[sys.argv.index('--out') + 1]).resolve()
    if '--export' in sys.argv:          # a trial against another export (the committed default otherwise)
        export = sys.argv[sys.argv.index('--export') + 1]
        CELLS[1].source = CELLS[1].source.replace("Path('../bench/depot-nav-100/planning')", f"Path({export!r})")
    nb = new_notebook(cells=CELLS, metadata={'kernelspec': {'name': 'python3', 'display_name': 'Python 3',
                                                            'language': 'python'},
                                             'language_info': {'name': 'python'}})
    if '--no-execute' not in sys.argv:
        from nbclient import NotebookClient
        NotebookClient(nb, timeout=600, kernel_name='python3',
                       resources={'metadata': {'path': str(OUT.parent)}}).execute()
    out.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, str(out))
    print('wrote', out)


if __name__ == '__main__':
    main()
