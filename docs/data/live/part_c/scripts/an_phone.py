"""Analyse the phone session: what the INSTRUMENTS saw, nothing else.

  an_phone.py RUNDIR

Inputs (RUNDIR): watch.jsonl (session_watch.py, a read-only loopback
spectator; every telemetry frame's session block), ros.jsonl (recorder.py
inside the container: wheel topic, arbiter inputs, modes, mission state,
/goal_pose, /plan, ground truth, wheel-publisher count), stack.log
(the platform's HTTP log: every /ws handshake), session_new.txt.

The phone's own clock and page log are NOT available: nothing here is a
phone-side latency. Server-side intervals are on one clock (the host's).
"""
import json
import re
import sys
from collections import Counter

run = sys.argv[1]
watch = [json.loads(line) for line in open(f'{run}/watch.jsonl')]
ros = [json.loads(line) for line in open(f'{run}/ros.jsonl')]
tele = [r for r in watch if r['kind'] == 'tele']
t_new = None
for line in open(f'{run}/session_new.txt'):
    m = re.search(r'session started (\S+)', line)
    if m:
        t_new = m.group(1)


def ts(t):
    import time
    return time.strftime('%H:%M:%S', time.gmtime(t)) + f'.{int((t % 1) * 1000):03d}Z'


def moving(r):
    return abs(r.get('lin', 0)) > 1e-6 or abs(r.get('ang', 0)) > 1e-6


print(f'== window: watcher {ts(tele[0]["t"])} .. {ts(tele[-1]["t"])} '
      f'({tele[-1]["t"] - tele[0]["t"]:.0f} s, {len(tele)} telemetry frames); session started {t_new}')

# ── control: who drove, how control ended, how many clients ────────────
print('\n== control timeline (changes only)')
prev = None
drivers = []
for r in tele:
    c = r['control'] or {}
    key = (c.get('driver_id'), c.get('last_end'), c.get('lease'), c.get('over'), r.get('latched'),
           c.get('clients'))
    if key != prev:
        print(f'  {ts(r["t"])} driver_id={c.get("driver_id")} lease={c.get("lease")} '
              f'last_end={c.get("last_end")} over={c.get("over")} latched={r.get("latched")} '
              f'clients={c.get("clients")} left={c.get("session_left_s") and round(c["session_left_s"])}')
        prev = key
    if c.get('driver_id') and (not drivers or drivers[-1] != c['driver_id']):
        drivers.append(c['driver_id'])
print(f'  distinct driver ids, in order: {drivers}')
print(f'  max clients seen: {max((r["control"] or {}).get("clients") or 0 for r in tele)}')
both = [r for r in tele if (r['control'] or {}).get('driver') and not (r['control'] or {}).get('driver_id')]
print(f'  frames with a driver but no driver id: {len(both)}')

# ── mission ────────────────────────────────────────────────────────────
print('\n== mission (executive, /mission/state)')
seen, first = [], {}
for r in ros:
    if r['topic'] == '/mission/state':
        s = r['data'].split(' ')[0].split('=')[1]
        if not seen or seen[-1] != s:
            seen.append(s)
            first.setdefault(len(seen), r['t'])
            print(f'  {ts(r["t"])} {s}  ({r["data"][:140]})')
print('  sequence:', ' > '.join(seen))

# ── Nav2 goals from the browser ────────────────────────────────────────
print('\n== Nav2: /goal_pose -> first /plan (server side)')
plans = [r for r in ros if r['topic'] == '/plan']
for g in [r for r in ros if r['topic'] == '/goal_pose']:
    p = next((p for p in plans if p['t'] >= g['t']), None)
    print(f'  {ts(g["t"])} goal ({g["x"]:.2f}, {g["y"]:.2f}) -> plan '
          f'{(1e3 * (p["t"] - g["t"])):.1f} ms ({p["n"]} poses)' if p else '  no plan')
st = []
for r in tele:
    g = r.get('goal') or {}
    k = (g.get('x'), g.get('y'), g.get('status'))
    if g and (not st or st[-1][1:] != k):
        st.append((r['t'],) + k)
for t, x, y, s in st:
    print(f'  {ts(t)} browser goal ({x}, {y}) status {s}')

# ── teleop: commands that reached the arbiter, and the wheels ──────────
tel = [r for r in ros if r['topic'] == '/cmd_vel_teleop']
wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']
mt = [r for r in tel if moving(r)]
print(f'\n== teleop: /cmd_vel_teleop messages {len(tel)} (moving {len(mt)}); '
      f'wheel messages {len(wheel)} (moving {sum(moving(r) for r in wheel)})')
lat = []
j = 0
for r in mt:
    while j < len(wheel) and wheel[j]['t'] < r['t'] - 0.01:
        j += 1
    hit = next((wv for wv in wheel[j:j + 40] if wv['t'] >= r['t'] and abs(wv['lin'] - r['lin']) < 1e-6
                and abs(wv['ang'] - r['ang']) < 1e-6 and wv['t'] - r['t'] < 0.5), None)
    if hit:
        lat.append(1e3 * (hit['t'] - r['t']))
if lat:
    lat.sort()
    q = lambda f: lat[min(len(lat) - 1, int(f * len(lat)))]
    print(f'  teleop topic -> wheel (in the container, NOT phone-side): n={len(lat)} '
          f'p50 {q(.5):.1f} p95 {q(.95):.1f} max {lat[-1]:.1f} ms')
if mt:
    bursts, last = [], None
    for r in mt:
        if last is None or r['t'] - last > 1.0:
            bursts.append([r['t'], r['t']])
        bursts[-1][1] = r['t']
        last = r['t']
    print(f'  teleop bursts (gap > 1 s): {len(bursts)}; first {ts(bursts[0][0])}, last {ts(bursts[-1][1])}')

# ── STOP: every latch false -> true, and the wheels after it ───────────
print('\n== STOP latch events (telemetry 5 Hz) and wheels after')
prev = None
for r in tele:
    L = r.get('latched')
    if prev is False and L is True:
        c = r['control'] or {}
        mv = [w for w in wheel if r['t'] < w['t'] < r['t'] + 10 and moving(w)]
        before = [w for w in wheel if r['t'] - 2 < w['t'] < r['t'] and moving(w)]
        tr = [x for x in ros if x['topic'] == 'truth' and r['t'] - 0.3 < x['t'] < r['t'] + 3]
        v0 = next((abs(x['vx']) for x in tr), None)
        rest = next((x['t'] - r['t'] for x in tr if x['t'] > r['t'] and abs(x['vx']) < 0.01 and abs(x['wz']) < 0.02), None)
        print(f'  {ts(r["t"])} latched (last_end={c.get("last_end")}, driver_id={c.get("driver_id")}); '
              f'moving wheel cmds in the 2 s before: {len(before)}, in the 10 s after: {len(mv)}; '
              f'truth |vx| near the latch {v0 if v0 is None else round(v0, 3)} m/s, at rest after '
              f'{rest if rest is None else round(rest, 2)} s')
    prev = L

# ── /ws handshakes: through the tunnel vs loopback ─────────────────────
# The platform logs only REFUSED handshakes (4xx), not 101s, so the client
# count in telemetry is the record of who connected.
refused = [line for line in open(f'{run}/stack.log', errors='replace') if ' GET /ws ' in line]
print(f'\n== refused /ws handshakes in the platform log: {len(refused)}')

# ── invariant ──────────────────────────────────────────────────────────
pc = Counter((r['wheel'], tuple(r['names'])) for r in ros if r['topic'] == 'pubcount')
print(f'\n== wheel publishers: {dict(pc)}')
modes = Counter(r['data'] for r in ros if r['topic'] == '/mission/mode')
print(f'== /mission/mode values seen: {dict(modes)}')
