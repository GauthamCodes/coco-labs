"""
The Arena's wheel-slip option against the recorded Gazebo drives (M2.3).

    python3 docs/v2/data/m2/m23/slip_fidelity.py \
        --sessions ~/coco_lab_runs/lab2/fidelity_1 ~/coco_lab_runs/lab2/fidelity_s1 \
        --out docs/v2/data/m2/m23/slip_fidelity.json

For each recorded drive (Lab 2's straight, square and 120 m tour; STACK:
the full ROS 2 stack in Gazebo), the commands Gazebo was sent are replayed
tick for tick through the Arena's motion law (coco_lab.sketch.step_pose,
the Arena's) with the slip option OFF (the body does what the wheels do)
and ON (in turns the body rotates coco_lab.arena.SLIP_TURN of what the
wheels report), noise-free. Reported per drive, MODEL vs STACK:

- odometry error: wheel odometry against the body's true pose at the end
  (position, yaw) -- the model's, slip off and on, beside Gazebo's own
  wheel odometry against Gazebo's truth;
- truth error: the model's true end pose against Gazebo's true end pose.

Slip off, the model's odometry IS its truth (error 0), while Gazebo's wheel
odometry drifts in turns -- the known divergence. The question the option
answers: with slip on, is the model's odometry error closer to Gazebo's?
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab.arena import SLIP_TURN  # noqa: E402
from coco_lab.sketch import step_pose, wrap  # noqa: E402


def compose(a, b):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            wrap(a[2] + b[2]))


def inverse(a):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-c * a[0] - s * a[1], s * a[0] - c * a[1], -a[2])


def replay(start, cmds, dts, slip):
    body = wheels = start
    for (v, w), dt in zip(cmds, dts):
        wheels_next = step_pose(wheels, v, w, dt)
        body = step_pose(body, v, w * (SLIP_TURN if slip else 1.0), dt)
        wheels = wheels_next
    return body, wheels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sessions', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = []
    for sess in a.sessions:
        path = os.path.join(os.path.expanduser(sess), 'drives.jsonl')
        if not os.path.exists(path):
            continue
        rows = [json.loads(line) for line in open(path)]
        for label in dict.fromkeys(r['label'] for r in rows):
            ticks = [r for r in rows if r['label'] == label and r['kind'] == 'drive']
            end = [r for r in rows if r['label'] == label and r['kind'] == 'drive_end']
            if not ticks or not end:
                continue
            end = end[0]
            gt0 = tuple(ticks[0]['truth'][1:4])
            od0 = tuple(ticks[0]['odom'][1:4])
            place = compose(gt0, inverse(od0))
            gt_end = tuple(end['truth'][1:4])
            od_end = compose(place, tuple(end['odom'][1:4]))
            rot = sum(abs(wrap(b['truth'][3] - c['truth'][3]))
                      for c, b in zip(ticks + [end], (ticks + [end])[1:]))
            cmds = [tuple(r['cmd']) for r in ticks]
            dts = [b['t'] - c['t'] for c, b in zip(ticks, ticks[1:])] + [0.1]
            rec = {'session': os.path.basename(os.path.expanduser(sess)),
                   'drive': label, 'ticks': len(ticks),
                   'truth_rotation_rad': rot,
                   'stack': {'odom_pos_err_m': math.hypot(od_end[0] - gt_end[0], od_end[1] - gt_end[1]),
                             'odom_yaw_err_rad': abs(wrap(od_end[2] - gt_end[2]))}}
            for slip in (False, True):
                body, wheels = replay(gt0, cmds, dts, slip)
                rec['model_slip_on' if slip else 'model_slip_off'] = {
                    'odom_pos_err_m': math.hypot(wheels[0] - body[0], wheels[1] - body[1]),
                    'odom_yaw_err_rad': abs(wrap(wheels[2] - body[2])),
                    'truth_vs_stack_truth_m': math.hypot(body[0] - gt_end[0], body[1] - gt_end[1]),
                    'truth_yaw_vs_stack_rad': abs(wrap(body[2] - gt_end[2]))}
            out.append(rec)
    doc = {'tool': 'docs/v2/data/m2/m23/slip_fidelity.py', 'slip_turn': SLIP_TURN,
           'evidence': 'MODEL (the Arena motion law) vs STACK (recorded Gazebo drives, Lab 2)',
           'sessions': a.sessions, 'drives': out}
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    for r in out:
        print(r['session'], r['drive'], 'STACK odom', round(r['stack']['odom_pos_err_m'], 3), round(r['stack']['odom_yaw_err_rad'], 3),
              '| off', round(r['model_slip_off']['odom_pos_err_m'], 3), round(r['model_slip_off']['truth_vs_stack_truth_m'], 3),
              '| on', round(r['model_slip_on']['odom_pos_err_m'], 3), round(r['model_slip_on']['odom_yaw_err_rad'], 3),
              round(r['model_slip_on']['truth_vs_stack_truth_m'], 3))


if __name__ == '__main__':
    main()
