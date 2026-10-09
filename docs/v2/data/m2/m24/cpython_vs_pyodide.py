"""
The whole-loop determinism sessions, replayed in native CPython (M2.4; MODEL).

    python3 docs/v2/data/m2/m24/cpython_vs_pyodide.py \
        docs/v2/data/m2/m24/determinism_map \
        --out docs/v2/data/m2/m24/determinism_map/cpython.json

Runs every session of ``sessions.json`` through the same glue the browser
runs (``lab_web/src/arena/arena_glue.py``: init, then one ``step`` per tick
with that tick's inputs), with every pack's module imported, and compares
each tick's state hash with the committed Pyodide-in-Node hashes of the
same directory. The browser engines were compared with Pyodide-in-Node by
``determinism.mjs compare``; this adds the interpreter the tests run on.
"""

import argparse
import gzip
import json
import os
import sys
import time

sys.dont_write_bytecode = True  # keep lab_web/src free of __pycache__ (site.test.ts)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.path.insert(0, os.path.join(REPO, 'lab_web', 'src', 'arena'))

import arena_glue  # noqa: E402
import coco_lab.loc_arena  # noqa: E402,F401
import coco_lab.map_arena  # noqa: E402,F401
import coco_lab.move_arena  # noqa: E402,F401


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    with open(os.path.join(a.dir, 'sessions.json')) as f:
        doc = json.load(f)
    with gzip.open(os.path.join(a.dir, 'hashes_pyodide-node.json.gz')) as f:
        ref = {s['id']: s['hashes'] for s in json.load(f)['sessions']}
    with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')) as f:
        import yaml
        spec = json.dumps(yaml.safe_load(f))
    t0 = time.time()
    ticks = mismatched = 0
    first = []
    for s in doc['sessions']:
        arena_glue.init(spec, s['seed'], s['planner'], lambda *_: None, 4096)
        for k in range(s['ticks']):
            out = arena_glue.step(json.dumps([x for x in s['inputs'] if x['tick'] == k]))
            h = json.loads(out[0])['hash']
            ticks += 1
            if h != ref[s['id']][k]:
                mismatched += 1
                if len(first) < 5:
                    first.append({'session': s['id'], 'tick': k})
    res = {'tool': 'docs/v2/data/m2/m24/cpython_vs_pyodide.py', 'evidence': 'MODEL', 'sessions_dir': os.path.relpath(os.path.abspath(a.dir), REPO),
           'engine': f'CPython {sys.version.split()[0]}', 'sessions': len(doc['sessions']),
           'ticks': ticks, 'mismatched': mismatched, 'first_mismatches': first,
           'seconds': round(time.time() - t0, 1)}
    with open(a.out, 'w') as f:
        json.dump(res, f, indent=1)
        f.write('\n')
    print(json.dumps(res))


if __name__ == '__main__':
    main()
