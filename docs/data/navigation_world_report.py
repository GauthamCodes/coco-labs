#!/usr/bin/env python3
"""Validate recorded fetch outcomes, beyond Nav2 action success.

Usage: python3 navigation_world_report.py RUN_DIR [RUN_DIR ...] --out report.json
"""
import argparse
import json
import math
from pathlib import Path


def assess(directory):
    metadata = dict(line.split('=', 1) for line in
                    (directory/'meta.txt').read_text().splitlines() if '=' in line)
    evidence = json.loads((directory/'visual_topics.json').read_text())
    colour = metadata['colour']
    final = (directory/'final_state.txt').read_text().strip()
    state = evidence.get('/mission/state', {})
    phases = state.get('states', [])
    grasp = evidence.get('/grasp/status', {})
    magnet = evidence.get(f'/magnet/target_{colour}/state', {}).get('states', [])
    odom = evidence.get('/model/coco/odometry', {})
    position = odom.get('last_position')
    home_error = math.hypot(position[0]+2, position[1]) if position else None
    checks = {
        'terminal_fetch': 'state=COMPLETE ' in final and 'result=fetch' in final,
        'left_home': odom.get('max_distance_from_home', 0) > 1,
        'mission_gates': all(f'state={phase}' in phases for phase in (
            'ALIGN_FOR_CLIMB', 'VERIFY_CLIMB', 'SEARCH_TARGET', 'APPROACH_TARGET',
            'GRASP', 'VERIFY_GRASP', 'DESCEND', 'RETURN_HOME', 'PLACE',
            'VERIFY_PLACEMENT', 'COMPLETE')),
        'grasp_and_place': grasp.get('lifted_seen', False) and grasp.get('placed_seen', False),
        'physical_magnet_attach_detach': 'attached' in magnet and magnet[-1:] == ['detached'],
        'home_ground_truth': home_error is not None and home_error <= .5,
        'large_map': evidence.get('/map', {}).get('size') == [500, 380],
        'global_costmap': evidence.get('/global_costmap/costmap', {}).get('size') == [500, 380],
        'local_costmap': evidence.get('/local_costmap/costmap', {}).get('count', 0) > 0,
        'global_path_received': evidence.get('/plan', {}).get('max_poses', 0) > 1,
        'local_trajectory_received': evidence.get('/local_plan', {}).get('max_poses', 0) > 1,
        'scan_received': evidence.get('/scan', {}).get('count', 0) > 0,
        'footprint_received': evidence.get('/local_costmap/published_footprint', {}).get('count', 0) > 0,
        'runner_checks': 'torn down; runner checks PASS' in (directory/'runner.log').read_text(),
    }
    return {'directory': str(directory), 'metadata': metadata, 'colour': colour,
            'passed': all(checks.values()), 'checks': checks, 'final_state': final,
            'home_error_m': home_error, 'final_ground_truth': position,
            'max_distance_from_home_m': odom.get('max_distance_from_home'),
            'localization_recoveries': phases.count('state=RELOCALIZE'),
            'magnet_states': magnet, 'grasp_final': grasp.get('last'),
            'global_path_messages': evidence.get('/plan', {}).get('count', 0),
            'local_path_messages': evidence.get('/local_plan', {}).get('count', 0),
            'phases': phases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=Path, nargs='+')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    results = [assess(directory) for directory in args.runs]
    args.out.write_text(json.dumps(results, indent=2)+'\n')
    for result in results:
        print(result['colour'], 'PASS' if result['passed'] else 'FAIL',
              [key for key, value in result['checks'].items() if not value])
    raise SystemExit(0 if all(result['passed'] for result in results) else 1)
