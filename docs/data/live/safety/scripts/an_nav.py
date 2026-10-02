"""Analyse a Nav2-goal run: per goal, did Nav2's commands reach the wheels."""
import json
import math
import sys


def load(path):
    return [json.loads(line) for line in open(path)]


def moving(r):
    return abs(r['lin']) > 1e-3 or abs(r['ang']) > 1e-3


for run in sys.argv[1:]:
    ws, ros = load(f'{run}/ws.jsonl'), load(f'{run}/ros.jsonl')
    print('==', run.rsplit('/', 1)[-1])
    g = [r for r in ws if r['kind'] == 'goals']
    if g:
        print('goals', g[0]['goals'], 'rejected (not free)', g[0]['rejected'])
    phases = [r for r in ws if r['kind'] == 'phase' and r['name'] in ('goal', 'end')]
    conds = {r['label']: r for r in ws if r['kind'] == 'cond'}
    wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']
    gated = [r for r in ros if r['topic'] == '/cmd_vel_gated']
    plans = [r for r in ros if r['topic'] == '/plan']
    ok_n = 0
    for a, b in zip(phases, phases[1:]):
        if a['name'] != 'goal':
            continue
        tx = next(r['t'] for r in ws if r['kind'] == 'tx'
                  and r['frame']['type'] == 'nav_goal' and r['t'] >= a['t'])
        p1 = next((r for r in plans if r['t'] > tx), None)
        wm = [r for r in wheel if tx < r['t'] < b['t'] and moving(r)]
        gm = [r for r in gated if tx < r['t'] < b['t'] and moving(r)]
        c = conds.get(f"arrive_{a['x']}_{a['y']}", {})
        tele = [r for r in ws if r['kind'] == 'tele' and a['t'] < r['t'] < b['t']]
        modes = sorted({(str(r["arb_mode"]), str(r["arb_active"])) for r in tele})
        end = tele[-1]['pose'] if tele else {}
        err = math.hypot(end.get('x', 0) - a['x'], end.get('y', 0) - a['y'])
        ok_n += bool(c.get('ok'))
        print(f"goal ({a['x']:+.1f},{a['y']:+.1f}): plan +"
              f"{(p1['t'] - tx) * 1e3 if p1 else float('nan'):.0f} ms; "
              f"nav cmds {len(gm)}, wheel moving {len(wm)}; arrived "
              f"{c.get('ok')} in {c.get('after', 0):.1f} s; end err "
              f"{err:.3f} m; arbiter {modes}")
    print('arrived', ok_n, 'of', sum(1 for p in phases if p['name'] == 'goal'))
    pc = {(r['wheel'], tuple(r['names'])) for r in ros if r['topic'] == 'pubcount'}
    print('wheel publishers', sorted(pc))
