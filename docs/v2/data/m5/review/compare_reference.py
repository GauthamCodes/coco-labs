# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""Diff captured browser panes against fresh CPython coco_lab outputs."""
import importlib.util
import json
import gzip
import math
import os
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[5]
out = Path(sys.argv[1])
module_spec = importlib.util.spec_from_file_location('review_glue', repo / 'lab_web/src/arena/arena_glue.py')
glue = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(glue)
world = (repo / 'lab_web/public/generated/arena/coco_arena_v1.json').read_text()
results = []
def magnitude(a,b):
    r={'numeric_differences':0,'max_absolute_difference':0.0,'hash_differences':0,'other_differences':0}
    def visit(x,y,p=''):
        if isinstance(x,dict) and isinstance(y,dict):
            for k in set(x)|set(y):visit(x.get(k),y.get(k),p+'/'+str(k))
        elif isinstance(x,list) and isinstance(y,list):
            if len(x)!=len(y):r['other_differences']+=1
            for i,(v,w) in enumerate(zip(x,y)):visit(v,w,p+'/'+str(i))
        elif x!=y:
            if p.endswith('/hash'):r['hash_differences']+=1
            elif isinstance(x,(int,float)) and not isinstance(x,bool) and isinstance(y,(int,float)) and not isinstance(y,bool):
                r['numeric_differences']+=1;d=abs(x-y)
                if d>r['max_absolute_difference']:r['max_absolute_difference']=d;r['maximum_example']={'path':p,'actual':x,'expected':y}
            else:r['other_differences']+=1
    visit(a,b)
    return r

def first_differences(a, b, path='', limit=8):
    rows=[]
    def visit(x,y,p):
        if len(rows)>=limit:return
        if isinstance(x,dict) and isinstance(y,dict):
            for key in sorted(set(x)|set(y)):visit(x.get(key),y.get(key),p+'/'+str(key))
        elif isinstance(x,list) and isinstance(y,list):
            if len(x)!=len(y):rows.append({'path':p,'actual_length':len(x),'expected_length':len(y)})
            for i,(v,w) in enumerate(zip(x,y)):visit(v,w,p+'/'+str(i))
        elif x!=y:rows.append({'path':p,'actual':x,'expected':y})
    visit(a,b,path)
    return rows

paths = {str(p).removesuffix('.gz'): p for p in sorted(out.glob('compare-*-events.json*'), reverse=True)}
for path in sorted(paths.values()):
    if len(sys.argv)>2 and not any(name in path.name for name in sys.argv[2:]):
        continue
    captured = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_text())
    workers = [w for w in captured['workers'] if any(x['type'] in ('compare', 'compare_loop') for x in w['sent'])]
    worker = workers[-1]
    request = [x for x in worker['sent'] if x['type'] in ('compare', 'compare_loop')][-1]
    glue.init(world, 1, 'astar', lambda *_: None, hash_version=2)
    if request['type'] == 'compare':
        names = request.get('planners', [request['a'], request['b']])
        expected = []
        def batch(columns, meta):
            m = json.loads(meta)
            expected.append({'meta': m, 'columns': {k: list(v) for k, v in columns.items()}})
        glue.compare(request['a'], request['b'], request['x'], request['y'], batch,
                     2048, json.dumps(request['inflation']), json.dumps(names))
        # Keep only the final comparison (messages also retain earlier UI choices).
        messages = worker['messages']
        last_done = max(i for i, m in enumerate(messages) if m['type'] == 'compare_done')
        previous_done = max((i for i, m in enumerate(messages[:last_done]) if m['type'] == 'compare_done'), default=-1)
        actual = [{'meta': m['meta'], 'columns': m['columns']} for m in messages[previous_done + 1:last_done] if m['type'] == 'plan_batch']
        panes = []
        for i, name in enumerate(names):
            side = 'ABCD'[i]
            a = [b for b in actual if b['meta']['compare'] == side]
            e = [b for b in expected if b['meta']['compare'] == side]
            panes.append({'pane': side, 'algorithm': name, 'batches': len(a),
                          'events': sum(len(b['columns']['seq']) for b in a), 'equal': a == e})
        results.append({'file': path.name, 'labels': captured['labels'], 'panes': panes,
                        'passed': all(p['equal'] for p in panes)})
    else:
        glue.loop_compare_begin(json.dumps({k: v for k, v in request.items() if k != 'type'}))
        expected = [json.loads(glue.loop_compare_advance()) for _ in range(request['steps'])]
        messages = worker['messages']
        # Only the latest family was requested on this page.
        loop_batches = [m for m in messages if m['type'] == 'compare_loop_batch']
        last_done = max(i for i, m in enumerate(loop_batches) if m['done'])
        previous_done = max((i for i, m in enumerate(loop_batches[:last_done]) if m['done']), default=-1)
        actual = [frame for m in loop_batches[previous_done + 1:last_done + 1] for frame in m['frames']]
        def scientific(value):
            if isinstance(value, dict):
                return {k: scientific(v) for k, v in value.items() if k != 'compute_ms'}
            if isinstance(value, list):
                return [scientific(v) for v in value]
            return value
        a, e = scientific(actual), scientific(expected)
        panes = []
        for i, name in enumerate(request['names']):
            panes.append({'pane': 'ABCD'[i], 'algorithm': name, 'ticks': len(actual),
                          'equal': len(a) == len(e) and all(x[i] == y[i] for x, y in zip(a, e)), 'first_differences':first_differences([x[i] for x in a],[y[i] for y in e])})
        results.append({'file': path.name, 'labels': captured['labels'], 'panes': panes,
                        'excluded': 'wall-clock compute_ms only', 'magnitude':magnitude(a,e), 'per_pane_magnitude':{name:magnitude([x[i] for x in a],[y[i] for y in e]) for i,name in enumerate(request['names'])}, 'native_python':sys.version, 'passed': all(p['equal'] for p in panes)})
(out / ('reference-diff-magnitude.json' if os.getenv('COMPARE_MAGNITUDE') else 'reference-diff-diagnostic.json' if len(sys.argv)>2 else 'reference-diff.json')).write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
if not all(r['passed'] for r in results):
    sys.exit(1)
