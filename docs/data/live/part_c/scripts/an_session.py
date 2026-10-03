"""Analyse a probe_session run: checks, and what the WHEELS did at each event.

  an_session.py RUNDIR       (ws.jsonl + ros.jsonl, wall clock, same host)

Wheel topic = /diff_drive_controller/cmd_vel, the arbiter's output, recorded
inside the container. "moving" = |lin| > 1e-3 or |ang| > 1e-3.
"""
import json
import sys

run = sys.argv[1]
ws = [json.loads(x) for x in open(f'{run}/ws.jsonl')]
ros = [json.loads(x) for x in open(f'{run}/ros.jsonl')]
wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']
moving = lambda r: abs(r['lin']) > 1e-3 or abs(r['ang']) > 1e-3  # noqa: E731

checks = [r for r in ws if r['kind'] == 'check']
print(f"checks: {sum(c['ok'] for c in checks)}/{len(checks)} pass")
for c in checks:
    if not c['ok']:
        print('  FAIL', c['name'], c['got'], c['want'])

phases = [(r['t'], r['name']) for r in ws if r['kind'] == 'phase']
spans = {name: (t, phases[i + 1][0] if i + 1 < len(phases) else ws[-1]['t'])
         for i, (t, name) in enumerate(phases)}
t0, t1 = spans['spectators']
print('spectator phase: moving wheel commands', sum(moving(r) for r in wheel if t0 <= r['t'] < t1))


drives = sorted(r['t'] for r in ws if r['kind'] == 'tx' and r['frame']['type'] == 'drive'
                and (r['frame']['linear'] or r['frame']['angular']))


def after(label, t_event, window=5.0):
    """
    First zero at/after the event, then moving commands after that zero.

    The window ends at +window or at the next non-zero drive frame any
    client sent after the event (an intentional new drive), whichever is
    first; its length is printed.
    """
    nxt = next((t for t in drives if t > t_event + 0.05), None)
    end = min(t_event + window, nxt) if nxt else t_event + window
    later = [r for r in wheel if t_event <= r['t'] <= end]
    zero = next((r for r in later if not moving(r)), None)
    tz = zero['t'] if zero else None
    mv = sum(moving(r) for r in wheel if tz and tz < r['t'] <= end)
    print(f'{label:34s} first wheel zero +{(tz - t_event) * 1e3:.1f} ms' if tz else f'{label:34s} no zero',
          f'| moving cmds after zero, next {end - (tz or t_event):.2f} s: {mv}')


def first_tele(pred):
    return next((r['t'] for r in ws if r['kind'] == 'tele' and pred(r)), None)


ev = first_tele(lambda r: r['control'].get('last_end') == 'idle_timeout')
if ev:
    # the server ended control one tick before the frame that says so
    after('idle release (telemetry seen)', ev - 0.2)
rel = next(r['t'] for r in ws if r['kind'] == 'tx' and r['frame']['type'] == 'release')
after('explicit release (frame sent)', rel)
disc = spans['B_disconnects_while_driving'][0] + 0.5
after('driver disconnect (close sent)', disc)
exp = next((r['t'] for r in ws if r['kind'] == 'closed' and r['who'] == 'A'), None)
if exp:
    after('session cap (A closed)', exp - 0.2)
kill = spans['KILL'][0]
after('host kill (kill issued)', kill, window=8.0)
for r in ws:
    if r['kind'] in ('closed', 'late', 'after_kill', 'idle'):
        print(r['kind'], {k: v for k, v in r.items() if k not in ('t', 'kind')})
for r in ws:
    if r['kind'] == 'host':
        print('host', r['action'], '->', r['out'])
pc = sorted({(r['wheel'], tuple(r['names'])) for r in ros if r['topic'] == 'pubcount'})
print('wheel publishers', pc)
