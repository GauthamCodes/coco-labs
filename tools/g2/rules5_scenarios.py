#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2 rules 5: the actor scenarios, before (rules 4's setup) and after (rules 5's), measured (MODEL).

    tools/g2/rules5_scenarios.py [--out docs/v2/g2/data/rules5/scenarios.json]

Each scenario kidnaps COCO to a start on the Depot (hash v3), applies Fetch Rush's setup inputs
(rules 4: actors.on=1, assist.target=any; rules 5: + actors.yield=1, avoid.on=1), optionally a
goal (AUTO's input), and steps. Per run: the minimum clearance of COCO's circle to any actor box
(< 0: overlap), the overlap ticks, the refused (blocked) ticks, arrival, the actors' held ticks,
AUTO's states and re-plans, and the step times (CPython, wall clock: this laptop, shared) --
the worst step overall and the worst re-plan (ActorAvoid._replan, one search each).
"""
import argparse
import json
import os
import platform
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import games, numerics  # noqa: E402
from coco_lab.arena import Arena, InputEvent  # noqa: E402

SCENARIOS = [
    # name, start (x, y, theta), goal or None, ticks, ticks to wait before the goal
    ('parked_in_lane', (30.0, 11.0, 0.0), None, 400, 0),
    ('cross_lane_t0', (28.0, 8.0, 1.5708), (28.0, 14.3), 1500, 0),
    ('cross_lane_t4', (28.0, 8.0, 1.5708), (28.0, 14.3), 1500, 40),
    ('cross_lane_t10', (28.0, 8.0, 1.5708), (28.0, 14.3), 1500, 100),
    ('cross_lane_t15', (28.0, 8.0, 1.5708), (28.0, 14.3), 1500, 150),
    ('head_on_in_lane', (24.0, 11.0, 3.1416), (18.0, 11.0), 2500, 0),
    ('along_walker_path', (24.2, 7.5, 1.5708), (24.2, 14.3), 2500, 0),
    ('across_walker_path', (22.0, 9.5, 0.0), (26.5, 9.5), 2500, 0),
]


def run(spec, rules, start, goal, ticks, wait):
    a = Arena(spec, 1, hash_version=3)
    rows = [{'tick': 0, 'kind': 'kidnap', 'x': start[0], 'y': start[1], 'theta': start[2],
             'has_theta': True}] + games.setup_inputs('fetch_rush', 0, 1,
                                                      yielding=rules >= games.YIELD_RULES)
    a.step([InputEvent(**r) for r in rows])
    for _ in range(wait):
        a.step([])
    act = a.subsystems['actors']
    av = a.subsystems.get('avoid')
    replan_ms = []
    if av is not None:
        orig = av._replan

        def timed(*args, **kw):
            t0 = time.perf_counter()
            try:
                return orig(*args, **kw)
            finally:
                replan_ms.append((time.perf_counter() - t0) * 1000)
        av._replan = timed
    out = {'min_clearance_m': act.clearance(a.pose[0], a.pose[1], a.radius), 'overlap_ticks': 0,
           'blocked_ticks': 0, 'arrived_s': None, 'actor_held_ticks': 0, 'avoid_states': {},
           'worst_step_ms': 0.0, 'mean_step_ms': 0.0}
    if goal is not None:
        a.step([InputEvent(a.tick, 'goal', x=goal[0], y=goal[1])])
    t_goal, total, n = a.t_world, 0.0, 0
    for _ in range(ticks):
        t0 = time.perf_counter()
        t = a.step([])
        ms = (time.perf_counter() - t0) * 1000
        total, n = total + ms, n + 1
        out['worst_step_ms'] = max(out['worst_step_ms'], ms)
        c = act.clearance(a.pose[0], a.pose[1], a.radius)
        out['min_clearance_m'] = min(out['min_clearance_m'], c)
        out['overlap_ticks'] += c < 0
        out['blocked_ticks'] += t.blocked
        out['actor_held_ticks'] += any(act.holding())
        if av is not None:
            out['avoid_states'][av.state] = out['avoid_states'].get(av.state, 0) + 1
        if goal is not None and t.arrived:
            out['arrived_s'] = round(a.t_world - t_goal, 1)
            break
    out['ticks'] = n
    out['mean_step_ms'] = total / n if n else 0.0
    out['replans'] = av.replans if av is not None else None
    out['replan_ms'] = [round(x, 1) for x in replan_ms]
    out['actor_lag_ticks'] = list(act.lag) if act.yielding() else None
    out['min_clearance_m'] = round(out['min_clearance_m'], 4)
    out['worst_step_ms'] = round(out['worst_step_ms'], 1)
    out['mean_step_ms'] = round(out['mean_step_ms'], 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', default=os.path.join(REPO, 'docs', 'v2', 'g2', 'data', 'rules5',
                                                  'scenarios.json'))
    o = ap.parse_args()
    spec = json.load(open(os.path.join(REPO, 'worlds', 'coco_depot_v1.json')))
    rows = []
    for name, start, goal, ticks, wait in SCENARIOS:
        for rules in (4, 5):
            r = dict(scenario=name, rules=rules, start=list(start),
                     goal=list(goal) if goal else None, wait_ticks=wait,
                     **run(spec, rules, start, goal, ticks, wait))
            rows.append(r)
            print(json.dumps(r), flush=True)
    doc = {'about': 'G2 rules 5 scenarios, before (rules 4 setup) and after (rules 5): '
                    'tools/g2/rules5_scenarios.py',
           'evidence': 'MODEL', 'hash_version': 3, 'python': platform.python_version(),
           'machine': platform.machine(), 'note': 'step times are wall clock on a shared laptop',
           'overlap': 'COCO circle (truth centre, radius) intersects an actor box: clearance < 0',
           'actor_stop_margin_m': games.ACTOR_STOP_MARGIN, 'runs': rows}
    with open(o.out, 'w') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    print('wrote', o.out)
    return 0


if __name__ == '__main__':
    with numerics.version(3):
        sys.exit(main())
