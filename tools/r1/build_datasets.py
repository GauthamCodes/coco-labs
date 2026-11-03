#!/usr/bin/env python3
"""
R1.6: write docs/v2/r1/datasets/index.json -- the committed datasets the Workbench lists.

Every file is named with its sha256 and size, its evidence class, and where to get it:
served by the site (``served``: a path under the site root) when the build ships it,
otherwise its GitHub path. Two kinds:

- the COCO-Bench v0 reference results (docs/v2/r1/bench/<suite>/<family>/), MODEL;
- the paired model-vs-Gazebo runs that exist: each pair names its MODEL side and its
  STACK side (Gazebo + Nav2, simulation; no physical robot exists), and what is and
  is not comparable between them.

    python tools/r1/build_datasets.py [--check]
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'docs' / 'v2' / 'r1' / 'datasets' / 'index.json'
BLOB = 'https://github.com/GauthamCodes/coco-labs/blob/main/'


def entry(rel, evidence, served=None):
    p = REPO / rel
    data = p.read_bytes()
    out = {'path': rel, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
           'evidence': evidence, 'github': BLOB + rel}
    if served:
        out['served'] = served
    return out


def bench():
    out = []
    root = REPO / 'docs' / 'v2' / 'r1' / 'bench'
    for d in sorted(p for p in root.glob('*/*') if p.is_dir()):
        suite, family = d.parent.name, d.name
        files = [entry(str((d / f).relative_to(REPO)), 'MODEL',
                       f'generated/r1/bench/{suite}/{family}/{f}' if f != 'runs.jsonl' else None)
                 for f in ('results.csv', 'summary.json', 'spec.json', 'manifest.json', 'runs.jsonl')
                 if (d / f).exists()]
        man = json.loads((d / 'manifest.json').read_text())
        out.append({'id': f'bench-{suite}-{family}', 'kind': 'benchmark',
                    'title': f'COCO-Bench v0 · {suite} · {family}: reference results',
                    'description': f'{man["n_runs"]} runs, every built-in {family} algorithm at its '
                                   'default parameters (coco experiment run, hash version 3). '
                                   f'Digest {man["digest"]}.',
                    'evidence': 'MODEL', 'files': files})
    return out


def ghosts(prefix):
    return [entry(f'lab_web/public/stack/ghosts/{p.name}', 'STACK', f'stack/ghosts/{p.name}')
            for p in sorted((REPO / 'lab_web' / 'public' / 'stack' / 'ghosts').glob(prefix + '*.json'))]


def paired():
    return [
        {'id': 'paired-fetch-colour', 'kind': 'paired',
         'title': 'Fetch by colour, four rods: the model bot and Gazebo + Nav2',
         'description': ('MODEL: the reference bot\'s rounds (rules 2; levels file) and the colour-fetch-4 '
                         'reference results. STACK: Nav2 driving the same rounds in Gazebo (the "Race '
                         'Nav2" ghosts; driving legs only, no grasp; actors under a scenario rule that '
                         'stops them for COCO). Times are comparable leg by leg; grasp time is model-only.'),
         'evidence': 'MODEL + STACK',
         'files': [entry('coco_lab/coco_lab/levels/coco_depot_colours_v1.fetch_colour.r2.json', 'MODEL')]
         + ghosts('g2_colour_')},
        {'id': 'paired-fetch-rush-r5', 'kind': 'paired',
         'title': 'Fetch Rush rules 5, phone rounds 1, 2, 3 and 6: the model bot and Gazebo + Nav2',
         'description': ('MODEL: the rules-5 rounds and their reference results (levels file). STACK: Nav2 '
                         'driving the same rounds in Gazebo (Race Nav2 ghosts r5_phone_seed*). Driving '
                         'legs only on the STACK side.'),
         'evidence': 'MODEL + STACK',
         'files': [entry('coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r5.json', 'MODEL')]
         + ghosts('r5_phone_seed')},
        {'id': 'paired-lab5-move', 'kind': 'paired',
         'title': 'Lab 5 local control: 54 Gazebo runs and the model\'s re-runs (M2.5)',
         'description': ('STACK: Lab 5\'s 54 Gazebo + Nav2 runs (DWB, RPP, MPPI over four scenarios; actors '
                         'visual-only, so contact was measured as clearance 0). MODEL: the same scenarios '
                         'in the Arena (actors have collision bodies there), seeds 1-5 per controller. '
                         'See docs/v2/M2_MOVE_COMPARISON.md before comparing.'),
         'evidence': 'MODEL + STACK',
         'files': [entry('docs/data/lab5/results.json', 'STACK'),
                   entry('docs/v2/data/m2/m25/move_comparison.json', 'MODEL')]},
    ]


def build():
    return {'about': 'R1.6: the committed datasets the Workbench lists (tools/r1/build_datasets.py); '
                     'sha256 and size of every file; STACK is Gazebo + Nav2 (simulation), never hardware',
            'datasets': bench() + paired()}


def text():
    return json.dumps(build(), indent=1, sort_keys=True) + '\n'


if __name__ == '__main__':
    t = text()
    if '--check' in sys.argv:
        ok = OUT.exists() and OUT.read_text() == t
        print('datasets index is current' if ok else 'datasets index is STALE')
        sys.exit(0 if ok else 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(t)
    print('wrote', OUT, len(build()['datasets']), 'datasets')
