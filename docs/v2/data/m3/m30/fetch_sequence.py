"""
The seek recording's fetch sequence, in the Python Arena (M3.0): the same settings as
lab_web/tools/perf/seek_check.mjs, seed 1, each next colour started the tick the last fetch
ended. Prints every fetch's outcome and its transitions' reasons.

    python3 fetch_sequence.py REPO [TICKS] [OUT.json]
"""
import collections
import json
import os
import sys

REPO = sys.argv[1]
TICKS = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
import yaml  # noqa: E402
from coco_lab.arena import Arena, InputEvent  # noqa: E402
import coco_lab.loc_arena  # noqa: E402,F401
import coco_lab.map_arena  # noqa: E402,F401
import coco_lab.move_arena  # noqa: E402,F401
import coco_lab.mission_arena  # noqa: E402,F401

SPEC = yaml.safe_load(open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')))
CFG = ['arena.range_sigma=0.02', 'localise.filter=mcl', 'map.algorithm=occupancy', 'map.poses=belief',
       'move.controller=dwa', 'mission.start=red']
COLOURS = ['green', 'blue', 'yellow', 'red']
seen = collections.defaultdict(list)


def fam(ch, tick, cols, scalars):
    if ch == 'coco.mission.fsm.transition.v1':
        for i in range(len(cols['to_state'])):
            seen['t'].append((tick, cols['from_state'][i], cols['to_state'][i], cols['event'][i], cols['reason'][i]))


a = Arena(SPEC, 1, on_family=fam)
a.step([InputEvent(0, 'config', choice=c) for c in CFG])
fetches = [{'colour': 'red', 'started_tick': 0, 'start_pose': list(a.pose)}]
m = a.subsystems['mission']
while a.tick < TICKS:
    if m.state in ('done', 'failed'):
        fetches[-1]['ended'] = {'tick': a.tick, 'state': m.state, 'result': m.result, 'pose': list(a.pose)}
        c = COLOURS[(len(fetches) - 1) % len(COLOURS)]
        a.step([InputEvent(a.tick, 'config', choice=f'mission.start={c}')])
        fetches.append({'colour': c, 'started_tick': a.tick - 1, 'start_pose': list(a.pose)})
    else:
        a.step(())
out = {'seed': 1, 'ticks': a.tick, 'cfg': CFG, 'fetches': fetches,
       'transitions': [dict(zip(('tick', 'from', 'to', 'event', 'reason'), t)) for t in seen['t']]}
for f in fetches:
    e = f.get('ended', {})
    print(f['colour'], f['started_tick'], [round(v, 2) for v in f['start_pose']], '->', e.get('state', 'running'),
          e.get('tick'), e.get('result', ''))
for t in seen['t']:
    if t[2] in ('failed', 'recover', 'done') or t[3] in ('start',):
        print('  ', t[0], t[1], '->', t[2], t[3], '|', t[4][:160])
if len(sys.argv) > 3:
    json.dump(out, open(sys.argv[3], 'w'), indent=1)
