"""Analyse one STOP run: time to zero, zero at +10 s, modes, rollback."""
import json
import math
import sys

MOVING = {'nav', 'auto', 'autonomous', 'nav2', 'rl', 'ramp', 'approach'}


def load(path):
    return [json.loads(line) for line in open(path)]


def moving(r):
    return abs(r['lin']) > 1e-3 or abs(r['ang']) > 1e-3


def analyse(run):
    ws, ros = load(f'{run}/ws.jsonl'), load(f'{run}/ros.jsonl')
    out = {'run': run.rsplit('/', 1)[-1]}
    loc = [r for r in ws if r['kind'] == 'localised_after']
    out['localised_after_s'] = round(loc[0]['s'], 2) if loc else None
    stop_phase = [r for r in ws if r['kind'] == 'phase' and r['name'] == 'STOP']
    if not stop_phase:
        out['error'] = 'stage never reached'
        conds = [r for r in ws if r['kind'] == 'cond']
        out['conds'] = conds
        return out
    out['state_at_stop'] = stop_phase[0]['state']
    ts = next(r['t'] for r in ws if r['kind'] == 'tx'
              and r['frame']['type'] == 'stop' and r['t'] >= stop_phase[0]['t'])
    wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']
    before = [r for r in wheel if ts - 1.0 < r['t'] < ts]
    out['moving_cmds_in_1s_before'] = sum(moving(r) for r in before)
    z = next((r for r in wheel if r['t'] > ts and not moving(r)), None)
    out['cmd_zero_ms'] = round((z['t'] - ts) * 1e3, 1) if z else None
    after = [r for r in wheel if ts < r['t'] <= ts + 10.0]
    mv_after = [r for r in after if z and r['t'] > z['t'] and moving(r)]
    out['moving_cmds_after_zero_to_10s'] = len(mv_after)
    out['wheel_cmds_0_10s'] = len(after)
    truth = [r for r in ros if r['topic'] == 'truth']
    rest = None
    for i, r in enumerate(truth):
        if r['t'] <= ts:
            continue
        window = [q for q in truth[i:] if q['t'] <= r['t'] + 0.5]
        if all(abs(q['vx']) < 0.02 and abs(q['wz']) < 0.05 for q in window):
            rest = r
            break
    out['body_rest_ms'] = round((rest['t'] - ts) * 1e3, 1) if rest else None
    at10 = [r for r in truth if ts + 9.5 <= r['t'] <= ts + 10.5]
    if at10:
        out['speed_at_10s'] = round(max(abs(r['vx']) for r in at10), 4)
    if rest and at10:
        a, b = rest, at10[-1]
        out['drift_rest_to_10s_m'] = round(
            math.dist((a['x'], a['y'], a['z']), (b['x'], b['y'], b['z'])), 4)
        out['dx_rest_to_10s_m'] = round(b['x'] - a['x'], 4)
        out['z_at_stop'] = round(a['z'], 3)
    modes = [(round((r['t'] - ts) * 1e3), r['data']) for r in ros
             if r['topic'] == '/mission/mode' and r['t'] > ts]
    out['modes_after_stop'] = modes[:8]
    out['moving_mode_after_stop'] = any(m in MOVING for _, m in modes)
    states, last = [], None
    for r in ros:
        if r['topic'] == '/mission/state' and r['t'] > ts - 0.5:
            s = r['data'].split(' ')[0]
            if s != last:
                states.append((round((r['t'] - ts) * 1e3), s))
                last = s
    out['states'] = states
    tele = [r for r in ws if r['kind'] == 'tele' and ts + 9.5 <= r['t'] <= ts + 10.5]
    if tele:
        out['latch_at_10s'] = tele[-1]['stop']
        out['arbiter_at_10s'] = (tele[-1]['arb_mode'], tele[-1]['arb_active'])
    pc = {(r['wheel'], tuple(r['names'])) for r in ros if r['topic'] == 'pubcount'}
    out['wheel_publishers'] = sorted(pc)
    return out


for run in sys.argv[1:]:
    print(json.dumps(analyse(run), indent=1))
