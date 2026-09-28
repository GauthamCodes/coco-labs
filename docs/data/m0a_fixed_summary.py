#!/usr/bin/env python3
"""Milestone 0A -- the four FIXED P03C cases on the consolidated main, summarised.

For each run directory written by p03c_episode_run.sh:
  outcome, result, mission sim/wall seconds, runner PASS/FAIL counts,
  home error (final gz pose vs the manifest's robot_start),
  where the target ended (the fetch, physically), and the command path
  over the rows Nav2's safety chain owns (arbiter source == nav):
  monitor authority, gated_zero_moving, bypass rows matching the raw
  controller, STOP breaches, and the monitor-action row counts.

    python3 m0a_fixed_summary.py RUN_DIR [RUN_DIR ...]
"""
import json
import math
import os
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def summarise(run):
    res = load(os.path.join(run, 'result.json'))
    man = res['manifest']
    start = man['robot_start']
    gz = load(os.path.join(run, 'final_gz.json'))['coco']
    colour = man['requested_colour']
    end = load(os.path.join(run, 'readback_end.json'))['models'].get(f'target_{colour}', {})
    tgt = next(t for t in man['targets'] if t['colour'] == colour)
    cp = load(os.path.join(run, 'cmdpath', 'summary.json'))
    nav = cp.get('nav_active_rows', {})
    log = open(os.path.join(run, 'runner.log')).read()
    return {
        'run': os.path.basename(run.rstrip('/')),
        'outcome': res['outcome'],
        'failure_reason': res['failure_reason'],
        'commit': res['software_commit'][:7],
        'mission_sim_s': res['timings'].get('mission_sim_s'),
        'mission_wall_s': res['timings'].get('mission_wall_s'),
        'runner_pass_checks': log.count('PASS '),
        'runner_fail_checks': log.count('FAIL '),
        'home_error_m': round(math.hypot(gz['x'] - start['x'], gz['y'] - start['y']), 3),
        'target_region': tgt['region_id'],
        'target_start_xy': [tgt['x'], tgt['y']],
        'target_end_xy': [round(tgt['x'] + end.get('dx', 0.0), 3), round(tgt['y'] + end.get('dy', 0.0), 3)],
        'nav_rows_monitor_authority': {k: nav.get('monitor_authority', {}).get(k)
                                       for k in ('samples', 'exceeded', 'gated_zero_moving')},
        'bypass_rows': cp.get('bypass_source', {}).get('rows'),
        'bypass_wheel_matches_raw_controller': cp.get('bypass_source', {}).get('wheel_matches_raw_controller'),
        'stop_rows': cp.get('stop_breach', {}).get('stop_rows'),
        'stop_rows_wheels_driven': cp.get('stop_breach', {}).get('stop_rows_wheels_driven'),
        'cm_action_rows_all': cp.get('cm_action_rows'),
    }


if __name__ == '__main__':
    print(json.dumps([summarise(r) for r in sys.argv[1:]], indent=1))
