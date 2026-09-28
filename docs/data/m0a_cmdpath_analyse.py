#!/usr/bin/env python3
"""Milestone 0A -- does the collision monitor's gating reach the wheels?

Reads one or more run directories written by m0a_cmdpath_run.sh and reports,
per run and pooled:

  rates     `ros2 topic hz` averages for the monitor output (/cmd_vel), the
            relay output (/cmd_vel_gated) and the wheel topic, as recorded
            during the drive.
  SLOWDOWN  trace rows (10 Hz resample, zero-order hold, c2nav42_cmdpath's
            own trace) whose collision-monitor action is 2 = SLOWDOWN, while
            the raw command on /cmd_vel_nav is the probe's 0.30 m/s:
              cap        slowdown_ratio x the smoother's output on that row
              wheel v    distribution (p50 / p90 / p99 / max)
              over cap   fraction of rows with |v_wheel| > cap + TOL
  messages  every wheel MESSAGE (events.csv) inside the drive window,
            compared with the most recent gated and monitor message:
            fraction equal to the gated command, fraction above the
            monitor's command.

TOL is 0.005 m/s: below any real leak (the C2-M5.0 leak was 0.21 m/s over
the cap) and above float noise in the restamped copies.

    python3 m0a_cmdpath_analyse.py RUN_DIR [RUN_DIR ...]
"""
import csv
import json
import os
import re
import statistics
import sys

TOL = 0.005
RAW = 0.30
SLOWDOWN = '2'


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)


def dist(vals):
    return {'n': len(vals), 'p50': pct(vals, 0.5), 'p90': pct(vals, 0.9),
            'p99': pct(vals, 0.99), 'max': round(max(vals), 4) if vals else None}


def hz(path):
    if not os.path.exists(path):
        return None
    rates = re.findall(r'average rate: ([0-9.]+)', open(path).read())
    return float(rates[-1]) if rates else None


def analyse(run):
    cp = os.path.join(run, 'cmdpath')
    ratio = fnum(re.findall(r'[0-9.]+', open(os.path.join(run, 'slowdown_ratio.txt')).read())[-1])
    rows = list(csv.DictReader(open(os.path.join(cp, 'trace.csv'))))
    slow = [r for r in rows if r.get('cm_action') == SLOWDOWN
            and fnum(r['v_nav']) is not None and abs(fnum(r['v_nav']) - RAW) < 1e-6
            and fnum(r['v_wheel']) is not None and fnum(r['v_smoothed']) is not None]
    wheel = [abs(fnum(r['v_wheel'])) for r in slow]
    caps = [ratio * abs(fnum(r['v_smoothed'])) for r in slow]
    over = sum(1 for w, c in zip(wheel, caps) if w > c + TOL)
    over_fixed = sum(1 for w in wheel if w > ratio * RAW + TOL)

    # Message level, inside the window where the raw command was the probe's.
    ev = list(csv.DictReader(open(os.path.join(cp, 'events.csv'))))
    drive = [e for e in ev if fnum(e['v_nav']) is not None and abs(fnum(e['v_nav']) - RAW) < 1e-6
             and fnum(e['v_wheel']) is not None]
    eq_gated = sum(1 for e in drive if fnum(e['v_gated']) is not None
                   and abs(fnum(e['v_wheel']) - fnum(e['v_gated'])) <= TOL)
    above_mon = sum(1 for e in drive if fnum(e['v_cmdvel']) is not None
                    and abs(fnum(e['v_wheel'])) > abs(fnum(e['v_cmdvel'])) + TOL)
    drive_wheel = [abs(fnum(e['v_wheel'])) for e in drive]
    summ = json.load(open(os.path.join(cp, 'summary.json')))
    return {
        'run': os.path.basename(run.rstrip('/')),
        'rates_hz': {'monitor_/cmd_vel': hz(os.path.join(run, 'hz__cmd_vel.txt')),
                     'relay_/cmd_vel_gated': hz(os.path.join(run, 'hz__cmd_vel_gated.txt')),
                     'wheel': hz(os.path.join(run, 'hz__diff_drive_controller_cmd_vel.txt'))},
        'slowdown_ratio': ratio,
        'cap_ms_at_raw': round(ratio * RAW, 4),
        'slowdown_rows': len(slow),
        'cap_ms_observed': dist(caps),
        'wheel_ms_in_slowdown': dist(wheel),
        'rows_over_cap': over,
        'rows_over_cap_frac': round(over / len(slow), 4) if slow else None,
        'rows_over_fixed_cap_frac': round(over_fixed / len(slow), 4) if slow else None,
        'wheel_messages_in_drive': len(drive),
        'wheel_ms_all_drive_messages': dist(drive_wheel),
        'wheel_msgs_equal_latest_gated_frac': round(eq_gated / len(drive), 4) if drive else None,
        'wheel_msgs_above_latest_monitor': above_mon,
        'cm_action_rows': summ.get('cm_action_rows'),
        'monitor_authority_exceeded': summ.get('monitor_authority', {}).get('exceeded'),
        'monitor_authority_samples': summ.get('monitor_authority', {}).get('samples'),
        'bypass_rows': summ.get('bypass_source', {}).get('rows'),
        'stop_rows_wheels_driven': summ.get('stop_breach', {}).get('stop_rows_wheels_driven'),
        'min_scan_m': summ.get('min_scan_m'),
        '_wheel': wheel, '_caps': caps,
    }


def main(argv):
    runs = [analyse(r) for r in argv[1:]]
    pooled_w = [w for r in runs for w in r['_wheel']]
    pooled_c = [c for r in runs for c in r['_caps']]
    over = sum(1 for w, c in zip(pooled_w, pooled_c) if w > c + TOL)
    for r in runs:
        r.pop('_wheel'), r.pop('_caps')
    out = {'tol_ms': TOL, 'runs': runs,
           'pooled_slowdown': {'rows': len(pooled_w), 'wheel_ms': dist(pooled_w),
                               'rows_over_cap': over,
                               'rows_over_cap_frac': round(over / len(pooled_w), 4) if pooled_w else None}}
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main(sys.argv)
