#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2 rules 5: an AUTO-only player through the browser's glue (CPython; MODEL).

    tools/g2/auto_player_r5.py SEED:RULES:MODE ...   (e.g. 1:5:phone 1:4:phone)

Plays a Fetch Rush round as a person pressing only AUTO, GRAB (when Grasp Assist can pick the
order's object) and DROP (in the drop zone): AUTO's goal is the glue's own (game_op auto_goal),
re-sent at most every 3 s while COCO is idle. RULES 4 sets games.FETCH_RUSH_RULES = 4 for the
glue (the before), 5 the current rules. One JSON line per run: deliveries, contacts, time used,
the minimum clearance to any actor box, overlap ticks, refused ticks, ticks with an actor held
for COCO, AUTO's states and the worst step (wall clock, this laptop).
"""
import importlib.util
import json
from pathlib import Path
import sys
import time
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / 'coco_lab'))
from coco_lab import games
def glue_mod():
    spec = importlib.util.spec_from_file_location('g', W / 'lab_web/src/arena/arena_glue.py')
    g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g); return g
def step(glue, rows):
    glue.begin(json.dumps(rows))
    while not glue.advance(4096): pass
    t, _ = glue.finish(); return json.loads(t)
def play(seed, rules, mode='phone', planner=None, max_ticks=4000):
    games.FETCH_RUSH_RULES = rules
    glue = glue_mod()
    world, _ = glue.game_init((W / 'worlds/coco_depot_v1.json').read_text(), 'fetch_rush', seed, 1, lambda *_: None, hash_version=3, mode=mode)
    info = json.loads(world)['game']
    setup = list(info['setup']) + ([{'kind': 'planner', 'choice': planner}] if planner else [])
    t = step(glue, setup)
    a = glue._arena
    worst_ms, min_clear, overlap_ticks, refused, held_ticks = 0.0, 9.0, 0, 0, 0
    states = {}; frames = []; pending = None; last_goal_tick = -999
    for k in range(max_ticks):
        f = t['game'].get('fetch') or {}
        if f.get('over'): break
        rows = []
        assist = t['game']['assist']
        if a.mode != 'goal' and assist['phase'] in ('idle', 'carry'):
            g = json.loads(glue.game_op('auto_goal'))
            if g is not None:
                if g['why'] == 'pick':
                    rowsp = json.loads(glue.game_op('preview'))['rows']
                    ok = [r for r in rowsp if not r['reason'] and r['object_id'] == g['object']]
                    if ok: rows = [{'kind': 'config', 'choice': f"assist.target={g['object']}"}, {'kind': 'config', 'choice': 'assist.grasp=go'}]
                else:
                    z = games.zone_rect(a.spec, f['order'][1])
                    if games.in_rect(a.pose[:2], z) and assist['phase'] == 'carry': rows = [{'kind': 'config', 'choice': 'assist.grasp=go'}]
                if not rows and k - last_goal_tick > 30:
                    rows = [{'kind': 'goal', 'x': g['x'], 'y': g['y']}]; last_goal_tick = k
        t0 = time.perf_counter(); t = step(glue, rows); ms = (time.perf_counter() - t0) * 1000
        worst_ms = max(worst_ms, ms)
        act = a.subsystems['actors']
        c = act.clearance(a.pose[0], a.pose[1], a.radius)
        min_clear = min(min_clear, c); overlap_ticks += c < 0; refused += t['blocked']
        held_ticks += bool(t['game'].get('actors_held'))
        av = t['game'].get('avoid')
        if av: states[av['state']] = states.get(av['state'], 0) + 1
    f = t['game'].get('fetch') or {}
    card = json.loads(glue.game_op('stars', None))['card']
    return {'seed': seed, 'rules': rules, 'mode': mode, 'ticks': k + 1, 'deliveries': f.get('deliveries'), 'contacts': f.get('contacts'),
            'time_used': card['time_used'], 'timer': f.get('seconds'), 'min_clearance_m': round(min_clear, 3), 'overlap_ticks': overlap_ticks,
            'refused_steps': refused, 'actor_held_ticks': held_ticks, 'avoid_states': states, 'worst_step_ms': round(worst_ms, 1)}
if __name__ == '__main__':
    out = []
    for arg in sys.argv[1:]:
        seed, rules, mode = arg.split(':')
        r = play(int(seed), int(rules), mode); print(json.dumps(r), flush=True); out.append(r)
