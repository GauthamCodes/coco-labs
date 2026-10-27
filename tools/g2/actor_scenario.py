#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.9 (Gautham, 2026-10-27): Gazebo's actors stop for COCO, as Fetch Rush rules 5's do in the model.
A SCENARIO RULE, not physics: the generated ``gazebo/actors.json`` (``tools/m6/gen_level.py
--derivation 5``) carries the actors' schedules and ``scenario_rule``; this drives them by it.

    actor_scenario.py WORLD ACTORS_JSON OUT_JSONL [--summary OUT.json] [--max-s SECONDS]

Each step of ``step_s`` simulation seconds (Gazebo's clock: the truth odometry's stamps), every actor
advances along its schedule (``coco_lab.worldspec_v3.actor_pose``) unless that step would bring its box
within ``robot_radius_m + stop_margin_m`` of COCO's centre and closer than now; then it holds and its
own clock falls one step behind -- ``coco_lab.games.DepotActors.world_step``'s rule with Gazebo's truth
for COCO's pose. Every actor's pose is set in one call to the world's ``set_pose_vector`` (its models
are kinematic, moved by set_pose only). Before the first step the actors stand at their t = 0 poses
(where the world spawns them). Writes one line per second of simulation and every hold start/end to
OUT_JSONL, and on exit (SIGINT/SIGTERM or --max-s) a summary: steps, holds per actor, and the least
clearance between COCO's circle and each actor's box (< 0 = overlap; counted).
"""
import argparse
import json
import math
import os
import signal
import sys
import threading
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab.games import box_distance  # noqa: E402
from coco_lab.worldspec_v3 import actor_pose  # noqa: E402

WATCHDOG_S = 30.0         # wall seconds without truth odometry: the simulator is gone
_APPROACH_EPS = 1e-9      # coco_lab.games._APPROACH_EPS: a step closer than this is no approach


def hold_step(actor, x, y, t_now, t_next, near):
    """Rules 5's hold (coco_lab.games.DepotActors.world_step): ``(hold, box distance now)`` for COCO at (x, y)."""
    d_now = box_distance(x, y, actor, t_now)
    d_next = box_distance(x, y, actor, t_next)
    return d_next < near and d_next < d_now - _APPROACH_EPS, d_now


class Scenario:
    def __init__(self, world, doc, log):
        self.world, self.log = world, log
        self.actors = doc['actors']
        r = doc['scenario_rule']
        self.rule = r
        self.near = r['robot_radius_m'] + r['stop_margin_m']
        self.radius = r['robot_radius_m']
        self.dt = r['step_s']
        self.lag = [0] * len(self.actors)
        self.held = [False] * len(self.actors)
        self.hold_steps = [0] * len(self.actors)
        self.holds = [0] * len(self.actors)
        self.min_clear = [math.inf] * len(self.actors)
        self.overlap_steps = 0
        self.step = 0
        self.t0 = None
        self.coco = None          # (sim t, x, y)
        self.heard = time.monotonic()
        self.lock = threading.Lock()
        from gz.transport13 import Node
        self.node = Node()
        self.set_calls = self.set_failed = 0

    def on_odom(self, msg):
        st = msg.header.stamp
        with self.lock:
            self.coco = (st.sec + st.nsec * 1e-9, msg.pose.position.x, msg.pose.position.y)
            self.heard = time.monotonic()

    def write(self, row):
        self.log.write(json.dumps(row) + '\n')
        self.log.flush()

    def advance(self):
        """One step: the hold rule for each actor, then their poses set in one call."""
        with self.lock:
            t, x, y = self.coco
        self.step += 1
        for i, ac in enumerate(self.actors):
            hold, d_now = hold_step(ac, x, y, (self.step - 1 - self.lag[i]) * self.dt, (self.step - self.lag[i]) * self.dt, self.near)
            if hold:
                self.lag[i] += 1
                self.hold_steps[i] += 1
            if hold != self.held[i]:
                if hold:
                    self.holds[i] += 1
                self.write({'event': 'hold' if hold else 'go', 'actor': ac['id'], 'sim_t': round(t, 3),
                            'coco': [round(x, 3), round(y, 3)], 'box_to_coco_centre_m': round(d_now, 3)})
            self.held[i] = hold
            clear = box_distance(x, y, ac, (self.step - self.lag[i]) * self.dt) - self.radius
            self.min_clear[i] = min(self.min_clear[i], clear)
            if clear < 0:
                self.overlap_steps += 1
        from gz.msgs10.boolean_pb2 import Boolean
        from gz.msgs10.pose_v_pb2 import Pose_V
        poses = [actor_pose(ac, (self.step - self.lag[i]) * self.dt) for i, ac in enumerate(self.actors)]
        req = Pose_V()
        for ac, (px, py, yaw) in zip(self.actors, poses):
            p = req.pose.add()
            p.name = ac['id']
            p.position.x, p.position.y, p.position.z = px, py, 0.0
            p.orientation.z, p.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        ok, rep = self.node.request(f'/world/{self.world}/set_pose_vector', req, Pose_V, Boolean, 1000)
        self.set_calls += 1
        if not (ok and rep.data):
            self.set_failed += 1
        if self.step % round(1 / self.dt) == 0:
            self.write({'sim_t': round(t, 3), 'step': self.step, 'coco': [round(x, 3), round(y, 3)],
                        'actors': {ac['id']: [round(v, 3) for v in p] for ac, p in zip(self.actors, poses)},
                        'lag_steps': list(self.lag), 'held': list(self.held)})

    def summary(self):
        return {'evidence_class': 'STACK (Gazebo + Nav2, headless); the actors follow a SCENARIO RULE, not physics',
                'world': self.world, 'rule': self.rule, 'sim_t0': self.t0, 'steps': self.step,
                'simulated_s': round(self.step * self.dt, 2),
                'actors': {ac['id']: {'holds': self.holds[i], 'held_steps': self.hold_steps[i],
                                      'held_s': round(self.hold_steps[i] * self.dt, 2),
                                      'min_clearance_m': None if math.isinf(self.min_clear[i]) else round(self.min_clear[i], 3)}
                           for i, ac in enumerate(self.actors)},
                'overlap_steps': self.overlap_steps, 'set_pose_vector_calls': self.set_calls,
                'set_pose_vector_failed': self.set_failed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('world')
    ap.add_argument('actors_json')
    ap.add_argument('out_jsonl')
    ap.add_argument('--summary')
    ap.add_argument('--max-s', type=float, default=None, help='stop after this much simulation time')
    a = ap.parse_args()
    with open(a.actors_json, encoding='utf-8') as f:
        doc = json.load(f)
    if 'scenario_rule' not in doc:
        print('actor_scenario: no scenario_rule in', a.actors_json, '(derivation < 5): nothing to drive')
        return 2
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    with open(a.out_jsonl, 'w', encoding='utf-8') as log:
        sc = Scenario(a.world, doc, log)
        from gz.msgs10.odometry_pb2 import Odometry
        if not sc.node.subscribe(Odometry, '/model/coco/odometry', sc.on_odom):
            print('actor_scenario: cannot subscribe to /model/coco/odometry')
            return 3
        while not stop.is_set() and sc.coco is None:
            time.sleep(0.05)
        if sc.coco is None:
            return 3
        sc.t0 = sc.coco[0]
        sc.write({'event': 'start', 'sim_t0': sc.t0, 'wall': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  'rule': sc.rule['id'], 'actors': [ac['id'] for ac in sc.actors]})
        print(f'actor_scenario: driving {len(sc.actors)} actors in {a.world} from sim t {sc.t0:.2f} s', flush=True)
        while not stop.is_set():
            with sc.lock:
                now = sc.coco[0]
            while now - sc.t0 >= (sc.step + 1) * sc.dt and not stop.is_set():
                sc.advance()
            if a.max_s is not None and sc.step * sc.dt >= a.max_s:
                break
            if time.monotonic() - sc.heard > WATCHDOG_S:   # the simulator is gone: stop, with a summary
                sc.write({'event': 'watchdog', 'note': f'no truth odometry for {WATCHDOG_S} s (wall)'})
                break
            time.sleep(0.005)
        rep = sc.summary()
    if a.summary:
        with open(a.summary, 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=1)
            f.write('\n')
    print('actor_scenario:', json.dumps({k: rep[k] for k in ('steps', 'overlap_steps', 'set_pose_vector_failed')}), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
