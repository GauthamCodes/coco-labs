"""Exact timings for preemption, STOP-during-mission, Nav2 mode, teleop."""
import json
import sys

D = sys.argv[1]
ws = [json.loads(line) for line in open(f'{D}/ws.jsonl')]
ros = [json.loads(line) for line in open(f'{D}/ros.jsonl')]
ph = {r['name']: r['t'] for r in ws if r['kind'] == 'phase'}
wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']


def tx(kind, after=0.0):
    return [r['t'] for r in ws if r['kind'] == 'tx'
            and r['frame']['type'] == kind and r['t'] > after]


def moving(r):
    return abs(r['lin']) > 1e-3 or abs(r['ang']) > 1e-3


t_first = tx('drive', ph['P'])[0]
w1 = next(r for r in wheel if r['t'] > t_first and abs(r['ang'] - 0.8) < 1e-6)
print('preempt: first drive tx -> wheel (0, 0.8): %.1f ms'
      % ((w1['t'] - t_first) * 1e3))

ts = tx('stop', ph['S'])[0]
z = next(r for r in wheel if r['t'] > ts and not moving(r))
mv = next(r for r in wheel if r['t'] > ts + 0.05 and moving(r))
print('STOP during mission: tx -> first wheel zero %.1f ms; '
      '-> first MOVING wheel cmd again %.1f ms (%.2f, %.2f)'
      % ((z['t'] - ts) * 1e3, (mv['t'] - ts) * 1e3, mv['lin'], mv['ang']))
modes = [(round((r['t'] - ts) * 1e3), r['data']) for r in ros
         if r['topic'] == '/mission/mode' and ts - 0.1 < r['t'] < ts + 1.5]
print('  /mission/mode around STOP (ms after, value):', modes)
mov = [r for r in wheel if ts + 0.6 < r['t'] < ph['A'] and moving(r)]
print('  moving wheel cmds from STOP+0.6 s to abort: %d over %.1f s'
      % (len(mov), ph['A'] - ts - 0.6))

ta = tx('mission', ph['A'])[0]
last_mv = [r for r in wheel if ta < r['t'] < ph['N'] and moving(r)]
print('abort: moving wheel cmds after abort tx: %d; last at +%.0f ms'
      % (len(last_mv), (last_mv[-1]['t'] - ta) * 1e3 if last_mv else -1))

# Nav2 mode with the executive idle
tg = tx('nav_goal', ph['N'])[0]
plans = [r for r in ros if r['topic'] == '/plan' and r['t'] > tg
         and r['t'] < ph['T']]
goal = [r for r in ros if r['topic'] == '/goal_pose' and r['t'] > tg]
print('nav_goal: /goal_pose seen +%.1f ms; plans in window: %d, first +%s ms'
      % ((goal[0]['t'] - tg) * 1e3 if goal else -1, len(plans),
         round((plans[0]['t'] - tg) * 1e3, 1) if plans else None))
modes = [(round((r['t'] - ph['N']) * 1e3), r['data']) for r in ros
         if r['topic'] == '/mission/mode' and ph['N'] < r['t'] < ph['N'] + 3]
print('  /mission/mode after set_mode auto (ms after, value):', modes)
gated = [r for r in ros if r['topic'] == '/cmd_vel_gated'
         and tg < r['t'] < ph['T'] and moving(r)]
wmov = [r for r in wheel if tg < r['t'] < ph['T'] and moving(r)]
print('  moving /cmd_vel_gated (Nav2 output) msgs: %d; moving wheel cmds: %d'
      % (len(gated), len(wmov)))
arb = [r['data'] for r in ros if r['topic'] == '/cmd_vel_arbiter/status'
       and tg < r['t'] < ph['T']]
print('  arbiter status samples:', sorted(set(a.split(' teleop')[0]
                                               for a in arb)))
tele = [r for r in ws if r['kind'] == 'tele' and tg < r['t'] < ph['T']]
if tele:
    print('  pose at goal tx %s, at end %s' % (tele[0]['pose'],
                                               tele[-1]['pose']))

tt = tx('drive', ph['T'])[0]
w2 = next((r for r in wheel if r['t'] > tt and abs(r['lin'] - 0.15) < 1e-6),
          None)
print('teleop (no mission): first drive tx -> wheel 0.15: %s ms'
      % (round((w2['t'] - tt) * 1e3, 1) if w2 else None))

pc = [r for r in ros if r['topic'] == 'pubcount']
print('wheel publisher counts seen:', sorted(set((r['wheel'],
                                                  tuple(r['names']))
                                                 for r in pc)))
tele_all = [r for r in ws if r['kind'] == 'tele']
span = tele_all[-1]['t'] - tele_all[0]['t']
print('telemetry received: %d frames over %.1f s = %.2f Hz'
      % (len(tele_all), span, (len(tele_all) - 1) / span))
