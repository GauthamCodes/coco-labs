"""A.2.6: the same drives as map_pyodide.mjs, scored by CPython; diff every metric."""
import json, sys, platform
sys.path.insert(0, '/home/gautham/rv3/coco_lab')
from coco_lab import play
WEB = '/home/gautham/rv3/lab_web'
LEVELS = json.load(open(f'{WEB}/play/levels.json'))
SPEC = json.load(open(f'{WEB}/public/generated/arena/coco_arena_v1.json'))
P = json.load(open(sys.argv[1]))
rows, worst = [], {}
for sub, pr in zip(P['subs'], P['rows']):
    r = play.score(LEVELS, sub, SPEC)
    m = {x['name']: x['value'] for x in r['metrics']}
    d = {}
    for k in ('f1', 'ate', 'path_m', 'ticks'):
        a, b = m[k], pr['metrics'][k]
        d[k] = None if a is None or b is None else abs(a - b)
        if d[k] is not None: worst[k] = max(worst.get(k, 0.0), d[k])
    rows.append({'name': pr['name'], 'level': sub['level'], 'stars_cpython': r['stars'], 'stars_pyodide': pr['stars'],
                 'hash_same': r['hash'] == pr['hash'], 'cpython': {k: m[k] for k in d}, 'pyodide': {k: pr['metrics'][k] for k in d},
                 'abs_diff': d})
out = {'what': 'map-the-arena: CPython vs Pyodide (Node) on the same drives',
       'cpython': platform.python_version(), 'pyodide': P['engine'], 'drives': len(rows),
       'hash_same': sum(r['hash_same'] for r in rows), 'stars_same': sum(r['stars_cpython'] == r['stars_pyodide'] for r in rows),
       'worst_abs_diff': worst,
       'reference_worst_abs_diff': {k: max(r['abs_diff'][k] for r in rows if r['name'].startswith('reference')) for k in worst},
       'rows': rows}
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print({k: out[k] for k in ('drives', 'hash_same', 'stars_same', 'worst_abs_diff', 'reference_worst_abs_diff')})
