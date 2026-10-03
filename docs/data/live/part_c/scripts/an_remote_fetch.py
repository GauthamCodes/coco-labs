"""Analyse a probe_remote_fetch run: lease, idle release, wheels, Nav2.

  an_remote_fetch.py RUNDIR
"""
import json
import sys

run = sys.argv[1]
ws = [json.loads(line) for line in open(f'{run}/ws.jsonl')]
ros = [json.loads(line) for line in open(f'{run}/ros.jsonl')]
wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']
tele = [r for r in ws if r['kind'] == 'tele' and r['who'] == 'A']


def first(pred, rows, after=0.0):
    return next((r for r in rows if r['t'] >= after and pred(r)), None)


checks = [r for r in ws if r['kind'] == 'check']
print(f'checks {sum(c["ok"] for c in checks)}/{len(checks)}; failed:',
      [c['name'] for c in checks if not c['ok']])

# Lease: how long autonomy held it, and the peak driver inactivity.
auto = [r for r in tele if (r['control'] or {}).get('lease') == 'autonomy']
li = [r['control'].get('last_input_s') or 0 for r in tele if r['control']]
print(f'lease=autonomy telemetry rows {len(auto)}; peak last_input_s {max(li):.1f} s; '
      f'idle_s {tele[-1]["control"].get("idle_s")}')

# Nav2: tx nav_goal -> first /plan, and its lease.
g = first(lambda r: r['kind'] == 'tx' and r['frame']['type'] == 'nav_goal', ws)
if g:
    p = first(lambda r: r['topic'] == '/plan', ros, g['t'])
    gp = first(lambda r: r['topic'] == '/goal_pose', ros, g['t'])
    print(f'nav_goal tx -> /goal_pose {1e3 * (gp["t"] - g["t"]):.1f} ms; '
          f'-> first /plan {1e3 * (p["t"] - g["t"]):.1f} ms' if p and gp else 'nav: no plan')

# After the mission: lease back -> idle release; wheels after release.
end = first(lambda r: r['kind'] == 'phase' and r['name'] == 'end', ws)
back = first(lambda r: (r['control'] or {}).get('lease') == 'driver', tele, end['t'])
rel = first(lambda r: (r['control'] or {}).get('last_end') == 'idle_timeout'
            and not r['control'].get('driver'), tele, end['t'])
if back and rel:
    print(f'mission end -> lease back {back["t"] - end["t"]:.2f} s; lease back -> idle release '
          f'{rel["t"] - back["t"]:.2f} s (telemetry, 10 Hz)')
    after = [r for r in wheel if r['t'] >= rel['t']]
    nxt = first(lambda r: r['kind'] == 'tx', ws, rel['t'])
    window = [r for r in after if r['t'] < (nxt['t'] if nxt else 1e18)]
    moving = [r for r in window if abs(r['lin']) > 1e-6 or abs(r['ang']) > 1e-6]
    span = (window[-1]['t'] - rel['t']) if window else 0.0
    print(f'wheel cmds from idle release to the next client frame: {len(window)} '
          f'over {span:.1f} s, moving {len(moving)}')

# Kill: last moving wheel command overall vs the kill.
k = first(lambda r: r['kind'] == 'host' and r['action'] == 'kill', ws)
if k:
    mv = [r for r in wheel if r['t'] >= k['t'] and (abs(r['lin']) > 1e-6 or abs(r['ang']) > 1e-6)]
    print(f'moving wheel cmds after kill: {len(mv)}')
pubs = {(r['wheel'], tuple(r['names'])) for r in ros if r['topic'] == 'pubcount'}
print('wheel publisher samples', len([r for r in ros if r['topic'] == 'pubcount']), sorted(pubs))
fl = first(lambda r: r['kind'] == 'flood', ws)
bu = first(lambda r: r['kind'] == 'burst', ws)
if bu:
    c = bu['codes']
    print(f'driver burst of {len(c)} drive: ack {c.count("ack")}, rate_limited {c.count("rate_limited")}')
if fl:
    print(f'spectator flood: replies {fl["replies"]}, spectator {fl["spectator"]}, '
          f'rate_limited {fl["rate_limited"]}, close {fl["closed"]}')
