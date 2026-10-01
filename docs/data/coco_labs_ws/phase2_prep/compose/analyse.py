"""Join the browser's actions with the in-container recorder: drives and STOP."""
import json
import sys
from collections import Counter

OUT = sys.argv[1]
rows = [json.loads(l) for l in open(OUT + '/recorder.jsonl') if l.strip()]
acts = {a['action']: a['t'] for a in json.load(open(OUT + '/actions.json'))}
print('recorder rows', dict(Counter(r.get('k') for r in rows)))
graph = [r for r in rows if r.get('k') == 'graph']
print('wheel publishers seen', sorted({tuple(r['wheel_pubs']) for r in graph}),
      '| teleop publishers seen', sorted({tuple(r['teleop_pubs']) for r in graph}))


def odom_at(t):
    best = None
    for r in rows:
        if r.get('k') == 'odom' and r['t'] <= t:
            best = r
    return best


for a, b in [('drive_forward_down', 'drive_forward_up'), ('drive_back_down', 'drive_back_up')]:
    t0, t1 = acts[a], acts[b] + 1.0
    w = [r for r in rows if r.get('k') == 'wheel' and t0 <= r['t'] <= t1]
    tele = [r for r in rows if r.get('k') == 'teleop' and t0 <= r['t'] <= t1]
    moving = [r for r in w if abs(r['lin']) > 1e-3]
    first = round((moving[0]['t'] - t0) * 1000, 1) if moving else None
    o0, o1 = odom_at(t0), odom_at(t1)
    print(f"{a}: teleop {len(tele)}, wheel {len(w)} ({len(moving)} moving, max |lin| "
          f"{max((abs(r['lin']) for r in w), default=0)}), key->first wheel motion {first} ms, "
          f"odom x {o0 and o0['x']} -> {o1 and o1['x']}")

ts = acts['stop_clicked_w_still_held']
before = [r for r in rows if r.get('k') == 'wheel' and acts['stop_test_w_down'] <= r['t'] < ts]
after = [r for r in rows if r.get('k') == 'wheel' and ts <= r['t'] <= acts['stop_test_w_up']]
zero = [r for r in after if abs(r['lin']) <= 1e-3 and abs(r['ang']) <= 1e-3]
late = [r for r in after if (r['t'] - ts) > 0.6 and (abs(r['lin']) > 1e-3 or abs(r['ang']) > 1e-3)]
print(f"STOP: W held before click -> {sum(abs(r['lin']) > 1e-3 for r in before)} moving wheel cmds; "
      f"after click first zero at {round((zero[0]['t'] - ts) * 1000, 1) if zero else None} ms; "
      f"moving cmds later than 600 ms: {len(late)}; odom x at click {odom_at(ts)['x']} -> "
      f"end {odom_at(acts['stop_test_w_up'])['x']}")
