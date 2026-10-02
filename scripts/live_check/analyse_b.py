"""
analyse_b.py RUN...: join the Live page's send log with the ROS recorder.

Both clocks are this machine's wall clock: the page stamps each frame with
performance.timeOrigin + performance.now() as it leaves (ms), the recorder
with time.time() as each message arrives (s). page.json carries Date.now()
beside that stamp so the offset between the two browser clocks is reported.
"""
import json
import math
import statistics
import sys


def load(run):
    ros = [json.loads(line) for line in open(f'{run}/ros.jsonl')]
    acts = [json.loads(line) for line in open(f'{run}/actions.jsonl')]
    page = json.load(open(f'{run}/page.json'))
    return ros, acts, page


def moving(lin, ang):
    return abs(lin) > 1e-3 or abs(ang) > 1e-3


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100.0
    f, c = math.floor(k), math.ceil(k)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def dist(xs):
    if not xs:
        return {'n': 0}
    return {'n': len(xs), 'min': round(min(xs), 1), 'p50': round(pct(xs, 50), 1),
            'p90': round(pct(xs, 90), 1), 'p99': round(pct(xs, 99), 1),
            'max': round(max(xs), 1), 'mean': round(statistics.mean(xs), 1)}


def analyse(run):
    ros, acts, page = load(run)
    out = {'run': run.rsplit('/', 1)[-1]}
    out['browser_clock_offset_ms'] = round(page['dateNow'] - page['perfNow'], 1)
    wheel = [r for r in ros if r['topic'] == '/diff_drive_controller/cmd_vel']
    log = page['log']
    drives = [r for r in log if r['type'] == 'drive']

    # every non-zero drive frame -> the first wheel message carrying it
    frame_lat, press_lat = [], []
    prev_t, prev_moving = None, False
    j = 0
    for d in drives:
        ts = d['t'] / 1000.0
        mv = moving(d['linear'], d['angular'])
        press_start = mv and (not prev_moving or prev_t is None or ts - prev_t > 0.5)
        prev_t, prev_moving = ts, mv
        if not mv:
            continue
        while j < len(wheel) and wheel[j]['t'] < ts - 0.05:
            j += 1
        hit = next((wv for wv in wheel[j:j + 60] if wv['t'] >= ts and
                    abs(wv['lin'] - d['linear']) < 1e-6 and
                    abs(wv['ang'] - d['angular']) < 1e-6 and wv['t'] - ts < 1.0), None)
        if hit:
            lat = (hit['t'] - ts) * 1e3
            frame_lat.append(lat)
            if press_start:
                press_lat.append(lat)
    out['drive_frame_to_wheel_ms'] = dist(frame_lat)
    out['press_to_first_wheel_ms'] = dist(press_lat)

    # STOP clicked while a key was held
    stops = [a for a in acts if a['kind'] == 'click' and a['target'] == 'live-stop']
    if stops:
        stop_sends = [r for r in log if r['type'] == 'stop']
        ts = stop_sends[0]['t'] / 1000.0 if stop_sends else stops[0]['t_page'] / 1000.0
        z = next((wv for wv in wheel if wv['t'] > ts and not moving(wv['lin'], wv['ang'])), None)
        mv = [wv for wv in wheel if ts + 0.2 < wv['t'] < ts + 3.3 and moving(wv['lin'], wv['ang'])]
        out['stop'] = {'stop_frame_to_wheel_zero_ms': round((z['t'] - ts) * 1e3, 1) if z else None,
                       'moving_cmds_0.2_to_3.3s': len(mv)}
        after = [a for a in acts if a['kind'] == 'dom_after_stop']
        if after:
            out['stop']['latched_banner'] = after[0]['dom']['latched']

    # Nav2 goals: page send -> first /plan, and Nav2's own verdict
    plans = [r for r in ros if r['topic'] == '/plan']
    sends = [r for r in log if r['type'] == 'nav_goal']
    done = [a for a in acts if a['kind'] == 'goal_done']
    goals = []
    for s, d in zip(sends, done):
        ts = s['t'] / 1000.0
        p1 = next((p for p in plans if p['t'] > ts), None)
        tr = d.get('truth') or {}
        goals.append({'goal': (d['x'], d['y']), 'status': d['status'],
                      'goal_to_first_plan_ms': round((p1['t'] - ts) * 1e3, 1) if p1 else None,
                      'truth_error_m': round(math.hypot(tr.get('x', 0) - d['x'], tr.get('y', 0) - d['y']), 3)
                      if tr else None})
    if goals:
        out['goals'] = goals
        out['goal_to_first_plan_ms'] = dist([g['goal_to_first_plan_ms'] for g in goals
                                             if g['goal_to_first_plan_ms'] is not None])
        out['goals_succeeded'] = f"{sum(g['status'] == 'succeeded' for g in goals)}/{len(goals)}"

    # telemetry actually received by the page
    rx = sorted(page['telemetryRx'])
    if len(rx) > 2:
        gaps = [b - a for a, b in zip(rx, rx[1:])]
        out['telemetry_received'] = {
            'frames': len(rx), 'span_s': round((rx[-1] - rx[0]) / 1000, 1),
            'rate_hz': round((len(rx) - 1) / ((rx[-1] - rx[0]) / 1000), 2),
            'gap_ms': dist(gaps)}

    # mission, as the executive reported it
    states = []
    for r in ros:
        if r['topic'] == '/mission/state':
            s = r['data'].split(' ')[0].split('=')[1]
            if not states or states[-1] != s:
                states.append(s)
    if len(states) > 1:
        out['mission_states'] = ' > '.join(states)
        out['recoveries'] = states.count('RECOVERY')
        out['relocalisations'] = states.count('RELOCALIZE')
    pre = [a for a in acts if a['kind'] == 'preempt']
    if pre:
        ph = next(a for a in acts if a['kind'] == 'phase' and a['name'] == 'preempt')
        tp = ph['t']
        teleop_on_wheels = [wv for wv in wheel if tp < wv['t'] < tp + 2.6
                            and abs(wv['lin']) < 1e-6 and wv['ang'] > 0.1]
        firsts = [r for r in log if r['type'] == 'drive' and r['t'] / 1000 > tp
                  and moving(r['linear'], r['angular'])]
        out['preempt'] = {'override_banner_after_s': pre[0]['override_banner_after_s'],
                          'wheel_cmds_carrying_the_turn': len(teleop_on_wheels),
                          'first_turn_frame_to_wheel_ms': None}
        if firsts and teleop_on_wheels:
            out['preempt']['first_turn_frame_to_wheel_ms'] = round(
                (teleop_on_wheels[0]['t'] - firsts[0]['t'] / 1000) * 1e3, 1)
        rel = [a for a in acts if a['kind'] == 'dom_after_release']
        if rel:
            out['preempt']['after_release'] = {k: rel[0]['dom'][k] for k in ('source', 'override', 'mission')}
    end = [a for a in acts if a['kind'] == 'dom_end']
    if end:
        out['page_end'] = {k: end[0]['dom'][k] for k in ('badge', 'mission', 'fallback', 'lane')}
    pubs = {(r['wheel'], tuple(r['names'])) for r in ros if r['topic'] == 'pubcount'}
    out['wheel_publishers'] = sorted(pubs)
    return out


for run in sys.argv[1:]:
    print(json.dumps(analyse(run), indent=1, default=str))
