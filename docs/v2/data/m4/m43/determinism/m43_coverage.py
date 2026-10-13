"""What the M4.3 terrain sessions exercise, run in CPython (coverage only; the
determinism verdict is the four engines'). Usage: m43_coverage.py SESSIONS OUT."""
import collections
import json
import sys

import yaml

from coco_lab.arena import Arena, InputEvent

REPO = '/home/gautham/coco_labs_ws/src/coco-labs/.claude/worktrees/v2-m4-3d-arena'
spec = yaml.safe_load(open(f'{REPO}/worlds/coco_arena_v2.yaml'))
sessions = json.load(open(sys.argv[1]))['sessions']
out = {'sessions': len(sessions), 'per_session': [], 'totals': collections.Counter()}
for s in sessions:
    a = Arena(spec, seed=s['seed'], planner=s['planner'])
    zmax, phases, sources, contacts, tilted = 0.0, set(), collections.Counter(), 0, 0
    hashes = []
    for k in range(s['ticks']):
        t = a.step([InputEvent(**{kk: v for kk, v in e.items()}) for e in s['inputs'] if e['tick'] == k])
        zmax = max(zmax, t.z)
        sources[t.source] += 1
        contacts += t.contact
        tilted += t.pitch != 0.0 or t.roll != 0.0
        if t.grasp:
            phases.add(t.grasp['phase'])
        hashes.append(t.state_hash)
    row = {'id': s['id'], 'z_max': round(zmax, 4), 'phases': sorted(phases), 'sources': dict(sources),
           'contact_ticks': contacts, 'tilted_ticks': tilted, 'final_hash': hashes[-1]}
    out['per_session'].append(row)
    out['totals']['reached_platform'] += zmax > 0.6
    out['totals']['climbed_any'] += zmax > 0.0
    out['totals']['grasp_carry'] += 'carry' in phases
    out['totals']['grasp_approach'] += 'approach' in phases
    out['totals']['grasp_release'] += 'release' in phases
    out['totals']['any_contact'] += contacts > 0
    for src in sources:
        out['totals'][f'source_{src}'] += 1
out['totals'] = dict(out['totals'])
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print(json.dumps(out['totals']))
