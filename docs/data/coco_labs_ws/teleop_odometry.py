"""What reached the wheels, and where the robot went, during each browser drive action."""
import json
from collections import Counter

import sys
J = sys.argv[1]
rows = [json.loads(l) for l in open(J + '/recorder.jsonl') if l.strip()]
print('recorder kinds', Counter(r.get('k') for r in rows))
print('first rows by kind:')
seen = set()
for r in rows:
    if r.get('k') not in seen:
        seen.add(r.get('k'))
        print('  ', r)
acts = json.load(open(J + '/actions.json'))
win = {a['action']: a['t'] for a in acts}


def odom_at(t):
    best = None
    for r in rows:
        if r.get('k') == 'odom' and r['t'] <= t:
            best = r
    return best


for a, b in [('drive_forward_down', 'drive_forward_up'), ('drive_back_down', 'drive_back_up'),
             ('joy_forward_down', 'joy_forward_up'), ('joy_back_down', 'joy_back_up')]:
    if a not in win:
        print(a, 'missing')
        continue
    t0, t1 = win[a], win[b] + 1.0
    o0, o1 = odom_at(t0), odom_at(t1)
    by = Counter(r.get('k') for r in rows if t0 <= r['t'] <= t1)
    print(a, dict(by), 'odom', o0 and (o0['x'], o0['y']), '->', o1 and (o1['x'], o1['y']))
