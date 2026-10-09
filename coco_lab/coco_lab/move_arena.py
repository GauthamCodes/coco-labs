# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Local control in the Arena (M2.5; MODEL): the ``move`` subsystem.

``config`` keys:

- ``move.controller=builtin|dwa|rpp|mppi`` -- who turns the path into
  wheel commands. ``builtin`` is M1's waypoint driver; the other three are
  :mod:`coco_lab.control`'s teaching implementations, each fed the local
  window of :class:`coco_lab.control.LocalWindow` built from the current
  scan around the BELIEVED pose.
- ``move.scenario=static_room|crossing|oncoming|mislocalised|none`` --
  Lab 5's scenarios rebuilt from their definitions
  (:mod:`coco_lab.move_scenarios`): the robot is put at the start, handed
  the scenario's FROZEN path (not the Arena's own plan), and its actors
  stand at their first waypoint until the robot's TRUE pose passes the
  trigger line, then walk their waypoints once at their speed and stop.
- ``move.belief_offset=dx,dy,dyaw`` -- the robot believes it is that far
  from the truth, and nothing corrects it (``mislocalised`` sets 3.4 m
  north, Lab 5's operator ``/initialpose``). Only when no localiser runs:
  a localiser's own estimate is the belief otherwise.

**Actors have collision bodies** here: the LiDAR sees them, the robot
cannot drive into one, and an actor waits while its next step would walk
into the robot. Lab 5's Gazebo actors were visual-only -- the LiDAR saw
them, nothing collided, and contact was measured as clearance 0 -- so a
comparison of the two must say so.

FollowPath's outcomes are Nav2's: SUCCEEDED inside the goal checker's
0.25 m (then the robot turns to the goal's heading, within 0.25 rad, by
a plain proportional turn -- the same for all three; simplified);
INVALID_PATH (103) when the path has no pose in the window; NO_VALID_CONTROL
(104) after more than ``failure_tolerance`` 0.3 s without a valid
command; FAILED_TO_MAKE_PROGRESS (105) when the robot moves less than
0.1 m in 10 s.
"""

import math
import struct
from typing import List, Optional, Tuple

from . import move_scenarios
from .arena import ArenaError, Q_STATE, SUBSYSTEMS
from .columns import Batch
from .control import (DWA, LocalWindow, MPPI, PathTracker, RPP,
                      WindowParams)
from .sketch import wrap

CONTROLLERS = ('builtin', 'dwa', 'rpp', 'mppi')
SCENARIOS = ('none',) + tuple(move_scenarios.SCENARIOS)
OUTCOMES = ('', 'succeeded', 'invalid_path', 'no_valid_control',
            'failed_to_make_progress')
#: Nav2's FollowPath result codes for the outcomes Lab 5 recorded
CODES = {'invalid_path': 103, 'no_valid_control': 104,
         'failed_to_make_progress': 105}
ACTOR_RADIUS = 0.15
GOAL_XY = 0.25
GOAL_YAW = 0.25
FAILURE_TOLERANCE = 0.3
PROGRESS_RADIUS = 0.1
PROGRESS_TIME = 10.0
#: every n-th trajectory point goes to the lens
TRAJ_STRIDE = 3


def _q(v: float) -> int:
    return round(v * Q_STATE)


class Actor:
    """A robot-triggered walker with a collision body (Lab 5's, made solid)."""

    def __init__(self, d):
        """Stand at the first waypoint, untriggered."""
        self.id = d['id']
        self.waypoints = [tuple(w) for w in d['waypoints']]
        self.speed = float(d['speed'])
        self.trigger = d['trigger']
        self.r = ACTOR_RADIUS
        self.s = 0.0
        self.triggered = False
        self.held = 0
        self.x, self.y = self.waypoints[0]

    def at(self, s: float) -> Tuple[float, float]:
        """Return the point ``s`` metres along the waypoints (parked at the end)."""
        w = self.waypoints
        for a, b in zip(w, w[1:]):
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            if s <= d:
                f = s / d if d > 0 else 0.0
                return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            s -= d
        return w[-1]

    def step(self, robot, robot_radius: float, dt: float) -> None:
        """Trigger on the robot's TRUE pose; walk unless blocked by it."""
        tr = self.trigger
        if not self.triggered:
            v = robot[0] if tr['axis'] == 'x' else robot[1]
            if (v < tr['value']) if tr['op'] == '<' else (v > tr['value']):
                self.triggered = True
        if not self.triggered:
            return
        s = self.s + self.speed * dt
        nx, ny = self.at(s)
        if math.hypot(nx - robot[0], ny - robot[1]) < robot_radius + self.r:
            self.held += 1
            return
        self.s, self.x, self.y = s, nx, ny


class ArenaMover:
    """The Arena's ``move`` subsystem: a local controller, actors, outcomes."""

    def __init__(self, arena):
        """Attach with M1's driver and no scenario."""
        self.arena = arena
        self.rng = arena.rng.split()
        self.controller = 'builtin'
        self.scenario = 'none'
        self.offset: Optional[Tuple[float, float, float]] = None
        self.window_params = WindowParams()
        self.actors: List[Actor] = []
        self.engine = None
        self._clear_run()

    def _clear_run(self):
        self._given = None
        self.tracker: Optional[PathTracker] = None
        self._wp_ref = None
        self.outcome = ''
        self.cycle = 0
        self.bad_since: Optional[float] = None
        self.prog_xy: Optional[Tuple[float, float]] = None
        self.prog_t = 0.0
        self.last: Optional[object] = None

    # -- config ----------------------------------------------------------------

    def config(self, key: str, value: str) -> None:
        """Apply ``move.<key>=<value>``."""
        a = self.arena
        if key == 'controller':
            if value not in CONTROLLERS:
                raise ArenaError(f'move.controller must be one of {CONTROLLERS}')
            self.controller = value
            self.engine = {'builtin': None, 'dwa': DWA(), 'rpp': RPP(),
                           'mppi': MPPI(self.rng)}[value]
            self._clear_run()
            if self.engine is not None:
                e = self.engine
                a.emit_header('coco.control.local.header.v1', {
                    'controller_id': value, 'kind': e.kind,
                    'critics': list(e.critics),
                    'params': dict(e.params.to_dict(),
                                   window=self.window_params.size),
                    'evidence': 'MODEL'})
        elif key == 'scenario':
            if value not in SCENARIOS:
                raise ArenaError(f'move.scenario must be one of {SCENARIOS}')
            self.scenario = value
            self._start_scenario()
        elif key == 'belief_offset':
            v = tuple(float(x) for x in value.split(','))
            if len(v) != 3 or not all(math.isfinite(x) for x in v):
                raise ArenaError('move.belief_offset: dx,dy,dyaw')
            self.offset = None if v == (0.0, 0.0, 0.0) else v
        else:
            raise ArenaError(f'unknown move setting {key!r}')

    def _start_scenario(self):
        a = self.arena
        self._clear_run()
        self.actors = []
        if self.scenario == 'none':
            self.offset = None
            return
        sc = move_scenarios.SCENARIOS[self.scenario]
        poses = move_scenarios.PATHS[sc['path']]
        a._reset_robot()
        sx, sy, sth = sc['start']
        a.pose = (sx, sy, sth)
        a.waypoints = [(q[0], q[1]) for q in poses]
        a.wp_index = 0
        a.goal = a.waypoints[-1]
        a.mode = 'goal'
        self.tracker = PathTracker(a.waypoints, goal_yaw=sc['goal'][2])
        self._wp_ref = a.waypoints
        self._given = a.waypoints
        self.actors = [Actor(d) for d in sc['actors']]
        inj = sc['inject']
        self.offset = (inj['dx'], inj['dy'], inj['dyaw']) if inj else None

    def on_reset(self, arena) -> None:
        """End the scenario on a reset (its actors go with it)."""
        self.scenario = 'none'
        self.actors = []
        self.offset = None
        self._clear_run()

    def take_path(self):
        """Return a path given whole since the last call (once), or None."""
        p, self._given = self._given, None
        return p

    # -- hooks the Arena calls -------------------------------------------------

    def belief(self):
        """Return truth plus the injected offset, when one is set."""
        if self.offset is None:
            return None
        x, y, th = self.arena.pose
        return (x + self.offset[0], y + self.offset[1],
                wrap(th + self.offset[2]))

    def discs(self):
        """Return the actors' bodies."""
        return [(ac.x, ac.y, ac.r) for ac in self.actors]

    def on_tick(self, arena) -> None:
        """Do nothing after the scan: the controller runs in ``command``."""

    def world_step(self, arena) -> None:
        """Walk the actors one ``dt``."""
        for ac in self.actors:
            ac.step(arena.pose, arena.radius, arena.dt)

    def command(self, arena):
        """Return (v, w, arrived) from the local controller, or None."""
        if self.engine is None:
            return None
        if arena.waypoints is not self._wp_ref:
            # a new plan from the Arena's planner: follow it from the belief
            b = arena.belief()
            self.tracker = PathTracker([(b[0], b[1])] + list(arena.waypoints))
            self._wp_ref = arena.waypoints
            self.outcome, self.bad_since, self.prog_xy = '', None, None
        tr, t, b = self.tracker, arena.t_world, arena.belief()
        if self.prog_xy is None or math.hypot(
                b[0] - self.prog_xy[0], b[1] - self.prog_xy[1]) > PROGRESS_RADIUS:
            self.prog_xy, self.prog_t = (b[0], b[1]), t
        gd = math.hypot(b[0] - tr.goal[0], b[1] - tr.goal[1])
        if gd < GOAL_XY:
            err = 0.0 if tr.goal_yaw is None else wrap(tr.goal_yaw - b[2])
            if abs(err) < GOAL_YAW:
                return self._finish(arena, 'succeeded')
            return (0.0, max(-1.0, min(1.0, 2.0 * err)), False)
        win = LocalWindow(b, arena.ranges, arena.angles, arena.lidar.mount,
                          tr.path[tr.i:tr.i + 200], self.window_params)
        local = tr.local(b, win)
        e = self.engine
        if e.kind == 'dwa':
            cy = e.compute(b, arena.v, arena.w, win, local, arena.dt)
        elif e.kind == 'rpp':
            cy = e.compute(b, arena.v, arena.w, win, local, arena.dt,
                           goal_dist=gd)
        else:
            cy = e.compute(b, arena.v, arena.w, win, local, arena.dt,
                           goal=tr.goal, goal_yaw=tr.goal_yaw, goal_dist=gd)
        self.last = cy
        self._emit(arena, cy, win, tr)
        self.cycle += 1
        if cy.status == 'invalid_path':
            return self._finish(arena, 'invalid_path')
        if cy.status != 'ok':
            if self.bad_since is None:
                self.bad_since = t
            if t - self.bad_since > FAILURE_TOLERANCE + 1e-9:
                return self._finish(arena, 'no_valid_control')
            return (0.0, 0.0, False)
        self.bad_since = None
        if t - self.prog_t > PROGRESS_TIME:
            return self._finish(arena, 'failed_to_make_progress')
        return (cy.v, cy.w, False)

    def _finish(self, arena, outcome):
        self.outcome = outcome
        arena.mode, arena.goal = 'idle', None
        arena.waypoints, arena.wp_index = [], 0
        self._wp_ref = arena.waypoints
        mb = Batch('coco.metrics.v1.MetricBatch')
        mb.add(arena.tick, arena.t_world, name=f'outcome.{outcome}',
               value=float(CODES.get(outcome, 0)), unit='code')
        arena.emit('coco.metrics.values.v1', mb)
        return (0.0, 0.0, outcome == 'succeeded')

    def _emit(self, arena, cy, win, tr):
        if arena.on_family is None:
            return
        tick, t = arena.tick, arena.t_world
        cid = self.controller
        cb = Batch('coco.control.v1.CandidateBatch', cycle=self.cycle,
                   controller_id=cid)
        off = 0
        stride = len(self.engine.critics)
        for k, c in enumerate(cy.candidates):
            pts = c.traj[TRAJ_STRIDE - 1::TRAJ_STRIDE] or c.traj
            cb.add(tick, t, candidate=k, v=c.v, w=c.w, valid=c.valid,
                   rejection=c.rejection, cost=c.cost, traj_offset=off,
                   traj_len=len(pts))
            sc = list(c.scores) + [math.nan] * (stride - len(c.scores))
            cb.extend_flat('critic_scores', sc[:stride])
            cb.extend_flat('traj_x', [p[0] for p in pts])
            cb.extend_flat('traj_y', [p[1] for p in pts])
            off += len(pts)
        arena.emit('coco.control.local.candidates.v1', cb)
        lx, ly = cy.lookahead if cy.lookahead else (math.nan, math.nan)
        mb = Batch('coco.control.v1.CommandBatch', controller_id=cid)
        mb.add(tick, t, cycle=self.cycle, chosen=cy.chosen, v=cy.v, w=cy.w,
               status=cy.status, n_candidates=cy.n_candidates,
               n_valid=cy.n_valid, lookahead_x=lx, lookahead_y=ly)
        arena.emit('coco.control.local.command.v1', mb)
        x, y, _ = arena.pose
        me = Batch('coco.metrics.v1.MetricBatch')
        me.add(tick, t, name='n_valid', value=float(cy.n_valid), unit='')
        me.add(tick, t, name='cmd_v', value=cy.v, unit='m/s')
        me.add(tick, t, name='tracking_error', value=tr.distance_to(x, y),
               unit='m')
        arena.emit('coco.metrics.values.v1', me)

    # -- the hash --------------------------------------------------------------

    def state_bytes(self) -> bytes:
        """Return the move state, quantized (docs/v2/ARENA_MODEL.md)."""
        off = self.offset or (0.0, 0.0, 0.0)
        out = [struct.pack('<BBB3qIQ', CONTROLLERS.index(self.controller),
                           SCENARIOS.index(self.scenario),
                           OUTCOMES.index(self.outcome),
                           *(_q(v) for v in off), self.cycle,
                           0 if self.tracker is None else self.tracker.i),
               struct.pack('<4Q', *self.rng.state)]
        for ac in self.actors:
            out.append(struct.pack('<3qBI', _q(ac.x), _q(ac.y), _q(ac.s),
                                   ac.triggered, ac.held))
        if self.engine is not None:
            vals = self.engine.state_values()
            out.append(struct.pack(f'<{len(vals)}q', *(_q(v) for v in vals)))
        bs = -1.0 if self.bad_since is None else self.bad_since
        out.append(struct.pack('<2q', _q(bs), _q(self.prog_t)))
        return b''.join(out)


SUBSYSTEMS['move'] = ArenaMover
