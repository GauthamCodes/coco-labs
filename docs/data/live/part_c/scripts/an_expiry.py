"""Analyse a probe_expiry run: what the wheels did when the cap ended a drive.

  an_expiry.py RUNDIR
"""
import json
import sys

run = sys.argv[1]
ws = [json.loads(x) for x in open(f'{run}/ws.jsonl')]
ros = [json.loads(x) for x in open(f'{run}/ros.jsonl')]
wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']
moving = lambda r: abs(r['lin']) > 1e-3 or abs(r['ang']) > 1e-3  # noqa: E731
closed = next(r for r in ws if r['kind'] == 'closed')
t = closed['t']
print('socket closed by server:', closed['code'], closed['reason'])
before = [r for r in wheel if t - 1.0 <= r['t'] < t]
print(f'moving wheel cmds in the 1 s before the close: {sum(map(moving, before))} of {len(before)}')
last_mv = max(r['t'] for r in wheel if moving(r) and r['t'] < t + 1)
zero = next(r for r in wheel if r['t'] > last_mv and not moving(r))
print(f'last moving wheel cmd at close{(last_mv - t) * 1e3:+.1f} ms; '
      f'first zero {(zero["t"] - last_mv) * 1e3:.1f} ms after it')
print('moving wheel cmds from the close to +10 s:',
      sum(moving(r) for r in wheel if t < r['t'] <= t + 10))
last_tx = max(r['t'] for r in ws if r['kind'] == 'tx' and r['frame']['type'] == 'drive')
print(f'last drive frame sent at close{(last_tx - t) * 1e3:+.1f} ms')
for r in [r for r in ros if r['topic'] == 'truth' and t - 0.5 <= r['t'] <= t + 2.0][::5]:
    print(f'  truth t{r["t"] - t:+.2f} s  vx {r["vx"]:+.3f} m/s')
for r in ws:
    if r['kind'] == 'host':
        print('host', r['action'], '->', r['out'])
print('wheel publishers', sorted({(r['wheel'], tuple(r['names'])) for r in ros
                                  if r['topic'] == 'pubcount'}))
