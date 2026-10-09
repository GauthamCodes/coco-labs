"""
Inventory every learner-facing claim the v1 Lab 1-5 pages show (M2.8).

    python3 docs/v2/data/m2/m28/v1_claims.py --out docs/v2/data/m2/m28/v1_claims.json

The v1 pages show a claim wherever they show a citation: the site's data
puts a ``cite`` / ``cites`` / ``citation`` beside every number and statement
it serves (lab_web/tools/build_*.py), and the views add a few of their own
in ``className="cite"`` paragraphs. So the inventory is:

1. every object in the generated site data (catalog.json, exhibit.json,
   loc_exhibits.json) that carries a cite key -- its id is its JSON path,
   its text the object's own words (text / lesson / title / note / claim /
   status ...) and the numbers beside them;
2. every ``className="cite"`` element in the v1 views (lab_web/src/ui/**),
   its id ``ui:<file>:<line>``, its text the JSX around it.

Run after build_catalog.py (the site data must exist). The ids are stable
for a given site build; docs/v2/M2_CLAIMS_COVERAGE.md maps every one to the
mission beat that carries it.
"""

import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
GEN = os.path.join(REPO, 'lab_web', 'public', 'generated')
UI = os.path.join(REPO, 'lab_web', 'src', 'ui')
CITE_KEYS = ('cite', 'cites', 'citation', 'mechanism_cite')
TEXT_KEYS = ('text', 'claim', 'lesson', 'title', 'note', 'status', 'task', 'question', 'id')
LAB_OF = {'bundles': 'lab1', 'exhibit': 'lab1', 'settings': 'lab1', 'ladder': 'lab1', 'footprint': 'lab1',
          'localise': 'lab2', 'loc_exhibits': 'lab2', 'map': 'lab3', 'search': 'lab4', 'move': 'lab5'}
UI_LAB = {'loc': 'lab2', 'map': 'lab3', 'search': 'lab4', 'move': 'lab5'}


def scalars(o, depth=0):
    """Short summary of an object's numbers and words, for the inventory."""
    out = []
    for k, v in o.items():
        if k in CITE_KEYS:
            continue
        if isinstance(v, (int, float, str, bool)) and not (isinstance(v, str) and len(v) > 400):
            out.append(f'{k}={v}')
        elif isinstance(v, dict) and depth < 1:
            out += [f'{k}.{s}' for s in scalars(v, depth + 1)][:6]
    return out[:12]


def walk(node, path, lab, out):
    if isinstance(node, dict):
        cite = [node[k] for k in CITE_KEYS if k in node]
        if cite:
            text = next((node[k] for k in TEXT_KEYS if isinstance(node.get(k), str) and k != 'id'), None)
            out.append({'id': path, 'lab': lab, 'source': 'site data',
                        'text': text or '; '.join(scalars(node)),
                        'cites': [c for x in cite for c in (x if isinstance(x, list) else [x])]})
        for k, v in node.items():
            if k in CITE_KEYS:
                continue
            # the lab is set by the catalog's top-level section (catalog.localise -> lab2 ...)
            walk(v, f'{path}.{k}', LAB_OF.get(k, lab) if path.count('.') == 0 else lab, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            key = v.get('id') if isinstance(v, dict) and isinstance(v.get('id'), str) else str(i)
            walk(v, f'{path}[{key}]', lab, out)


def ui_claims(out):
    for root, _, files in os.walk(UI):
        for f in sorted(files):
            if not f.endswith('.tsx'):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, REPO)
            sub = os.path.relpath(root, UI)
            lab = UI_LAB.get(sub.split(os.sep)[0], 'lab1')
            lines = open(p, encoding='utf-8').read().split('\n')
            for i, line in enumerate(lines):
                if 'className="cite"' not in line:
                    continue
                ctx = ' '.join(x.strip() for x in lines[max(0, i - 3):i + 3])
                ctx = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', ctx))[:400]
                out.append({'id': f'ui:{rel}:{i + 1}', 'lab': lab, 'source': 'v1 view', 'text': ctx, 'cites': []})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = []
    for name in ('catalog', 'exhibit', 'loc_exhibits'):
        with open(os.path.join(GEN, f'{name}.json')) as f:
            data = json.load(f)
        walk(data, name, LAB_OF.get(name, 'lab1'), out)
    ui_claims(out)
    seen = set()
    for c in out:
        if c['id'] in seen:
            raise SystemExit(f'duplicate claim id {c["id"]}')
        seen.add(c['id'])
    doc = {'tool': 'docs/v2/data/m2/m28/v1_claims.py', 'n': len(out),
           'by_lab': {lab: sum(1 for c in out if c['lab'] == lab) for lab in ('lab1', 'lab2', 'lab3', 'lab4', 'lab5')},
           'claims': out}
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    print(doc['n'], doc['by_lab'])


if __name__ == '__main__':
    main()
