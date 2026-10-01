"""Phase-by-phase timeline: what the arbiter forwarded, in which mode."""
import json
import sys

D = sys.argv[1]
ws = [json.loads(line) for line in open(f'{D}/ws.jsonl')]
ros = [json.loads(line) for line in open(f'{D}/ros.jsonl')]
phases = [(r['t'], r['name']) for r in ws if r['kind'] == 'phase']
phases.append((phases[-1][0] + 5, 'tail'))


def window(t0, t1):
    return [r for r in ros if t0 <= r['t'] < t1]


def bins(rows, t0, t1, step=0.5):
    """Per half-second: arbiter status, mode topic, wheel cmd, inputs."""
    out = []
    t = t0
    while t < t1:
        sel = [r for r in rows if t <= r['t'] < t + step]
        def last(topic, key):
            v = [r[key] for r in sel if r['topic'] == topic]
            return v[-1] if v else None
        def cnt(topic, moving=False):
            return sum(1 for r in sel if r['topic'] == topic and (
                not moving or abs(r['lin']) > 1e-3 or abs(r['ang']) > 1e-3))
        wheel = [r for r in sel if r['topic'] == '/diff_drive_controller/cmd_vel']
        arb = last('/cmd_vel_arbiter/status', 'data')
        out.append('%6.1f arb[%s] modeTopic=%s wheel n=%d mov=%d last=%s '
                   'teleop=%d gated=%d/%d rl=%d' % (
                       t - t0, (arb or '')[:40], last('/mission/mode', 'data'),
                       len(wheel), cnt('/diff_drive_controller/cmd_vel', True),
                       ('%.2f,%.2f' % (wheel[-1]['lin'], wheel[-1]['ang'])) if wheel else '-',
                       cnt('/cmd_vel_teleop'), cnt('/cmd_vel_gated'),
                       cnt('/cmd_vel_gated', True), cnt('/cmd_vel_rl')))
        t += step
    return out


only = sys.argv[2:] or None
for (t0, name), (t1, _) in zip(phases, phases[1:]):
    if only and name not in only:
        continue
    print(f'=== phase {name} ({t1 - t0:.1f} s)')
    rows = window(t0, t1)
    states = [r['data'][:90] for r in rows if r['topic'] == '/mission/state']
    seen = []
    for s in states:
        key = s.split(' ')[0]
        if not seen or seen[-1][0] != key:
            seen.append((key, s))
    for _, s in seen:
        print('   mission:', s)
    for line in bins(rows, t0, t1):
        print('  ', line)
    rx = [r for r in ws if r['kind'] == 'rx' and t0 <= r['t'] < t1
          and r['frame'].get('type') == 'error']
    for r in rx:
        print('   REFUSED', r['frame'])
