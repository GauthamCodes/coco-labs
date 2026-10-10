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
The Arena's fetch mission (M2.6; MODEL): the ``mission`` subsystem.

The whole loop, in order: **localise -> choose a bay -> plan -> local
control -> detect -> grasp -> return**. Each step is another pack's work,
used as it is: the belief is whatever ``localise`` (or nothing) makes it;
the plan is the Arena's planner, asked through
:meth:`coco_lab.arena.Arena.request_goal`; the driving is ``move``'s local
controller or M1's driver. So when localisation degrades, the learner sees
it reach the planner (it plans from the believed pose), the controller (it
steers by it), the survey (the camera looks where the robot TRULY is) and
the search's belief (a miss in the wrong place is still counted as a miss
at the bay the robot believes it searched).

``config`` keys: ``mission.start=<colour>`` (red, green, blue, yellow),
``mission.truth=<bay id>`` (where the target stands; default the frozen
layout, :data:`coco_lab.fetch_problem.LAYOUT`), ``mission.detect=<p>``
(how often the camera REALLY finds a target that is in view; default
0.9), ``mission.abort=1``.

**The search is Lab 4's** (:mod:`coco_lab.regionsearch`, the problem in
:mod:`coco_lab.fetch_problem`): a uniform prior over COCO's four bays (the
robot is told a colour, not where it is), the robot's ASSUMED detection
probability d = 0.9 -- an ASSUMPTION, labelled so in the data
(``coco.decide.search.header.v1``) and on screen -- Bayes' rule on a miss,
and the next bay chosen by the least expected metres driven, every order
costed exactly. The world's detection rate is a separate knob
(``mission.detect``), equal to the assumption unless the learner changes
it.

SIMPLIFIED, and said wherever shown: the Arena is 2D, so the ramp climb is
not modelled -- the robot surveys a bay from its pre-ramp pose, the
detection is abstract (``sensor.detect``: found with probability
``mission.detect`` when the bay TRULY in view holds the target, never a
false positive), and the grasp is the arm's kinematic pick
(:mod:`coco_lab.arm`) at that pose. A bay is in view when the robot's TRUE
position is within :data:`VIEW_RADIUS` of its pre-ramp pose.
"""

import itertools
import math
import struct
from typing import List, Optional, Tuple

from . import arm, fetch_problem, regionsearch as rs
from .arena import ArenaError, Q_STATE, SUBSYSTEMS
from .columns import Batch
from .sketch import wrap

STATES = ('idle', 'localise', 'choose_bay', 'go_to_bay', 'detect', 'grasp',
          'return', 'done', 'failed', 'recover')
NOMINAL = STATES[1:8]
COLOURS = tuple(fetch_problem.LAYOUT)
DETECTION_LABEL = 'ASSUMPTION'
#: the robot's own uncertainty it waits to be under before choosing (m)
LOCALISED_SIGMA = 0.3
#: how long it waits for that before going anyway (s)
LOCALISE_TIMEOUT = 5.0
#: a bay is in the camera's view within this of its pre-ramp pose (TRUE)
VIEW_RADIUS = 0.6
#: arrived when the BELIEVED position is this close to the goal (m)
ARRIVED = 0.35
SURVEY_SECONDS = 2.0
LEG_TIMEOUT = 300.0
#: a leg fails when the BELIEVED position moves less than this ...
PROGRESS_RADIUS = 0.1
#: ... in this long (Nav2's progress checker's values)
PROGRESS_TIME = 10.0
#: the fetch plans with this clearance from walls (m): the mission's global
#: costmap keeps its paths away from them (inflation 0.5 m); M1's planner
#: alone keeps only the robot's radius, 0.22 m, which leaves no margin for
#: any localisation error (measured: a 0.19 m error put the robot against
#: a box it believed it was clear of)
CLEARANCE = 0.40
#: a leg whose controller gave up backs up and re-plans, at most this many
#: times -- after Nav2's BackUp recovery (0.30 m at 0.15 m/s); SIMPLIFIED:
#: Nav2's behaviour tree also clears its costmaps, spins and waits
RECOVERIES = 3
BACKUP_SPEED = 0.15
BACKUP_SECONDS = 2.0
MISSION_ID = 'arena_fetch'


def _q(v: float) -> int:
    return round(v * Q_STATE)


def _to_map(xy, arena) -> Tuple[float, float]:
    dx, dy = arena.spec['world_to_map']
    return (xy[0] + dx, xy[1] + dy)


class ArenaMission:
    """The Arena's ``mission`` subsystem: the fetch, as a state machine."""

    def __init__(self, arena):
        """Attach idle; the problem is Lab 4's."""
        self.arena = arena
        self.rng = arena.rng.split()
        self.problem = rs.SearchProblem.from_dict(fetch_problem.PROBLEM)
        self.p_true = 0.9
        self.truth_override: Optional[str] = None
        self._clear()

    def _clear(self):
        p = self.problem
        self.state = 'idle'
        self.colour: Optional[str] = None
        self.truth: Optional[str] = None
        self.bay_belief = tuple(p.prior)
        self.searched: Tuple[int, ...] = ()
        self.location = p.start
        self.target: Optional[int] = None
        self.since = 0.0
        self.update = 0
        self.awaiting = False
        self.result = ''
        self.prog_xy: Optional[Tuple[float, float]] = None
        self.prog_t = 0.0
        self.leg = ''
        self.recoveries = 0

    # -- config ----------------------------------------------------------------

    def config(self, key: str, value: str) -> None:
        """Apply ``mission.<key>=<value>``."""
        a = self.arena
        if key == 'start':
            if value not in COLOURS:
                raise ArenaError(f'mission.start must be one of {COLOURS}')
            # Every fetch starts from home (M3.0). A fetch that already ran
            # in this session -- done, failed or still going -- left the
            # robot wherever it ended, and a stalled pose stalls the next
            # fetch too; so put it back home first, as a `reset` input does.
            # A session's first fetch (mission idle) starts where it stands.
            came_from = None
            if self.state != 'idle':
                came_from = a.pose[:2]
                a.reset_home()
            self._clear()
            self.colour = value
            self.truth = self.truth_override or fetch_problem.LAYOUT[value]
            if a.plan_clearance < CLEARANCE:
                a.set_plan_clearance(CLEARANCE)
            self._headers(a)
            self._emit_belief(a)
            why = (f'told to fetch the {value} target; it is not told which '
                   'bay holds it')
            if came_from is not None:
                why += (f' (another fetch ran first: the robot was put back '
                        f'home from ({came_from[0]:.2f}, {came_from[1]:.2f}))')
            self._go(a, 'localise', 'start', why)
        elif key == 'truth':
            if value not in self.problem.ids:
                raise ArenaError(f'mission.truth must be one of '
                                 f'{self.problem.ids}')
            self.truth_override = value
            if self.colour is not None:
                self.truth = value
        elif key == 'detect':
            v = float(value)
            if not 0.0 < v <= 1.0:
                raise ArenaError('mission.detect must be in (0, 1]')
            self.p_true = v
        elif key == 'abort':
            if self.state not in ('idle', 'done', 'failed'):
                self._fail(a, 'aborted', 'ABORTED by the learner')
        else:
            raise ArenaError(f'unknown mission setting {key!r}')

    def on_reset(self, arena) -> None:
        """End the mission on a reset."""
        self._clear()

    # -- emitting --------------------------------------------------------------

    def _headers(self, a):
        p = self.problem
        a.emit_header('coco.mission.fsm.header.v1', {
            'mission_id': MISSION_ID, 'states': list(NOMINAL),
            'params': {'colour': self.colour, 'detect_true': self.p_true,
                       'simplified': 'the ramp climb is not modelled: '
                       'survey and grasp at the pre-ramp pose',
                       # the arm inset's anchors, base_footprint (m)
                       'arm.shoulder_x': arm.S_X, 'arm.shoulder_z': arm.S_Z,
                       'arm.target_x': arm.TARGET_XZ[0],
                       'arm.target_z': arm.TARGET_XZ[1]},
            'evidence': 'MODEL'})
        a.emit_header('coco.decide.search.header.v1', {
            'problem_id': MISSION_ID, 'region_ids': list(p.ids),
            'detection': p.detection[0], 'detection_label': DETECTION_LABEL,
            'params': dict({'policy': 'expected_cost', 'prior': 'uniform',
                            'costs': 'metres driven (A* on the Nav2 map, '
                            'Lab 4)',
                            'survey_cost': p.regions[0].survey_cost},
                           **self._geometry(a))})

    def _geometry(self, a):
        """Each bay's platform and approach in the MAP frame, as text."""
        out = {}
        dx, dy = a.spec['world_to_map']
        for r in self.problem.regions:
            x0, x1, y0, y1 = r.platform
            out[f'{r.id}.platform'] = \
                f'{x0 + dx},{x1 + dx},{y0 + dy},{y1 + dy}'
            ax, ay = _to_map(r.approach, a)
            out[f'{r.id}.approach'] = f'{ax},{ay}'
            out[f'{r.id}.label'] = r.label
        return out

    def _emit_belief(self, a):
        b = Batch('coco.decide.v1.BeliefBatch', update=self.update,
                  problem_id=MISSION_ID)
        for i, pr in enumerate(self.bay_belief):
            b.add(a.tick, a.t_world, region=i, probability=pr)
        a.emit('coco.decide.search.belief.v1', b)

    def _go(self, a, to, event, reason, result=''):
        tb = Batch('coco.mission.v1.TransitionBatch', mission_id=MISSION_ID)
        tb.add(a.tick, a.t_world, from_state=self.state, to_state=to,
               event=event, reason=reason, result=result)
        a.emit('coco.mission.fsm.transition.v1', tb)
        self.state, self.since = to, a.t_world

    def _fail(self, a, event, reason):
        self.result = f'failed: {reason}'
        a.mode, a.goal, a.waypoints, a.wp_index = 'idle', None, [], 0
        self._go(a, 'failed', event, reason, self.result)

    # -- the machine -----------------------------------------------------------

    def on_tick(self, a) -> None:
        """Advance the mission one tick (after the robot moved and scanned)."""
        st = self.state
        if st in ('idle', 'done', 'failed'):
            return
        if a.tick % 10 == 0:
            self._emit_loc(a)
        t = a.t_world - self.since
        if st == 'localise':
            self._localise(a, t)
        elif st == 'choose_bay':
            self._choose(a)
        elif st in ('go_to_bay', 'return'):
            self._drive(a, t)
        elif st == 'recover':
            if t >= BACKUP_SECONDS - 1e-9:
                a.mode, a.teleop = 'idle', (0.0, 0.0)
                self._request_leg(a)
                self._go(a, self.leg, 'recovered',
                         f'backed up; re-planning (recovery '
                         f'{self.recoveries} of {RECOVERIES})')
        elif st == 'detect':
            if t >= SURVEY_SECONDS - 1e-9:
                self._detect(a)
        elif st == 'grasp':
            s = arm.script_state(t)
            if s is None:
                s = arm.script_state(arm.script_seconds() - 1e-6)
                self._emit_arm(a, s, 'stowed')
                self._go(a, 'return', 'grasped', 'the magnet holds the '
                         'target; going home')
                self.recoveries = 0
                self.leg = 'return'
                self._request_leg(a)
            else:
                self._emit_arm(a, s, s['phase'])

    def _localise(self, a, t):
        loc = a.subsystems.get('localise')
        q = loc.quality() if loc is not None and \
            hasattr(loc, 'quality') else None
        if loc is None or getattr(loc, 'filter', 'off') == 'off':
            b = a.belief()
            told = math.hypot(b[0] - a.pose[0], b[1] - a.pose[1]) > 1e-9
            self._go(a, 'choose_bay', 'no_localiser',
                     'no localiser runs: the robot takes the pose it was '
                     'given as true' if told else
                     'no localiser runs: the belief is the truth '
                     '(SIMPLIFIED)')
        elif q is None or q['sigma_xy'] < LOCALISED_SIGMA:
            sig = 'told its start' if q is None else \
                f"sigma {q['sigma_xy']:.2f} m ({q['filter']})"
            self._go(a, 'choose_bay', 'localised', f'localised: {sig}')
        elif t >= LOCALISE_TIMEOUT:
            self._go(a, 'choose_bay', 'localise_timeout',
                     f'not localised after {LOCALISE_TIMEOUT:.0f} s '
                     f"(sigma {q['sigma_xy']:.2f} m): going anyway")

    def _choose(self, a):
        p = self.problem
        view = rs.SearchView(self.bay_belief, self.searched, self.location)
        rem = view.remaining(p.n)
        if not rem:
            self._fail(a, 'target_not_found', 'every bay searched once and '
                       'the target not found')
            return
        ob = Batch('coco.decide.v1.OrderCostBatch', update=self.update,
                   problem_id=MISSION_ID)
        off = 0
        for perm in itertools.permutations(rem):
            e = rs.plan_cost(p, self.bay_belief, self.location, perm)['expected']
            ob.add(a.tick, a.t_world, order_offset=off, order_len=len(perm),
                   expected_cost=e)
            ob.extend_flat('order', list(perm))
            off += len(perm)
        a.emit('coco.decide.search.orders.v1', ob)
        costs = rs.candidate_costs(p, view)
        i = rs.choose('expected_cost', p, view)
        ab = Batch('coco.decide.v1.ActionBatch', update=self.update,
                   problem_id=MISSION_ID)
        ab.add(a.tick, a.t_world, region=i, expected_cost=costs[i],
               reason='least expected metres driven over every order of '
               'the bays left')
        a.emit('coco.decide.search.action.v1', ab)
        mb = Batch('coco.metrics.v1.MetricBatch')
        mb.add(a.tick, a.t_world, name='expected_cost', value=costs[i],
               unit='m')
        mb.add(a.tick, a.t_world, name='p_max', value=max(self.bay_belief),
               unit='')
        a.emit('coco.metrics.values.v1', mb)
        self.target = i
        r = p.regions[i]
        self.recoveries = 0
        self.leg = 'go_to_bay'
        self._request_leg(a)
        self._go(a, 'go_to_bay', 'bay_chosen',
                 f'{r.label} ({r.id}): expected {costs[i]:.1f} m')

    def _request_leg(self, a):
        goal = self.problem.regions[self.target].approach \
            if self.leg == 'go_to_bay' else self.problem.start_xy
        a.request_goal(*_to_map(goal, a))
        self.awaiting = True

    def _drive(self, a, t):
        goal = self.problem.regions[self.target].approach \
            if self.state == 'go_to_bay' else self.problem.start_xy
        gx, gy = _to_map(goal, a)
        if self.awaiting:
            if a.mode == 'goal':
                self.awaiting = False
                self.prog_xy, self.prog_t = None, a.t_world
            elif t > 2 * a.dt + 1e-9:
                self._fail(a, 'no_path', f'no path to ({gx:.2f}, {gy:.2f})')
            return
        if t > LEG_TIMEOUT:
            self._fail(a, 'timeout', f'not there after {LEG_TIMEOUT:.0f} s')
            return
        b = a.belief()
        if a.mode == 'goal':
            if self.prog_xy is None or math.hypot(
                    b[0] - self.prog_xy[0],
                    b[1] - self.prog_xy[1]) > PROGRESS_RADIUS:
                self.prog_xy, self.prog_t = (b[0], b[1]), a.t_world
            elif a.t_world - self.prog_t > PROGRESS_TIME:
                self._fail(a, 'no_progress', 'NAVIGATION_FAILED: moved less '
                           f'than {PROGRESS_RADIUS} m in {PROGRESS_TIME:.0f} '
                           's (blocked?)')
            return
        mv = a.subsystems.get('move')
        outcome = getattr(mv, 'outcome', '') if mv is not None else ''
        if math.hypot(b[0] - gx, b[1] - gy) > ARRIVED or \
                outcome not in ('', 'succeeded'):
            why = outcome or 'stopped short'
            if outcome in ('no_valid_control', 'failed_to_make_progress') \
                    and self.recoveries < RECOVERIES:
                self.recoveries += 1
                self.leg = self.state
                a.mode, a.teleop = 'teleop', (-BACKUP_SPEED, 0.0)
                self._go(a, 'recover', 'controller_failed',
                         f'{why}: backing up {BACKUP_SPEED * BACKUP_SECONDS:.2f}'
                         " m (after Nav2's BackUp recovery)")
                return
            self._fail(a, 'navigation_failed', f'NAVIGATION_FAILED: {why}')
            return
        if self.state == 'return':
            self.result = 'fetch'
            self._go(a, 'done', 'home', 'home with the target', 'fetch')
        else:
            self._go(a, 'detect', 'arrived', 'at the bay, looking')

    def _detect(self, a):
        p = self.problem
        i = self.target
        x, y, _ = a.pose
        seen = None
        for k, r in enumerate(p.regions):
            mx, my = _to_map(r.approach, a)
            if math.hypot(mx - x, my - y) <= VIEW_RADIUS:
                seen = k
        draw = self.rng.random()
        found = seen is not None and p.ids[seen] == self.truth and \
            draw < self.p_true
        nx, ny, _ = fetch_problem.TARGET_NOMINAL[p.ids[i]]
        tx, ty = _to_map((nx, ny), a)
        db = Batch('coco.sensor.v1.DetectionBatch',
                   detection_probability=self.p_true,
                   detection_label="the world's rate (the robot assumes "
                   f'{p.detection[i]}: {DETECTION_LABEL})')
        db.add(a.tick, a.t_world, region_id=p.ids[i], colour=self.colour,
               detected=found, range=math.hypot(tx - x, ty - y),
               bearing=wrap(math.atan2(ty - y, tx - x) - a.pose[2]))
        a.emit('coco.sensor.detect.colour.v1', db)
        obs = Batch('coco.decide.v1.ObservationBatch', problem_id=MISSION_ID)
        obs.add(a.tick, a.t_world, region=i, found=found)
        a.emit('coco.decide.search.observation.v1', obs)
        self.bay_belief = rs.update(self.bay_belief, i, found, p.detection[i])
        self.searched = self.searched + (i,)
        self.location = p.ids[i]
        self.update += 1
        self._emit_belief(a)
        where = 'nothing in view' if seen is None else \
            f'the camera saw {p.regions[seen].label}'
        if seen is not None and seen != i:
            where += f' (the robot believes it is at {p.regions[i].label})'
        if found:
            self._go(a, 'grasp', 'target_detected',
                     f'the {self.colour} target, seen: {where}')
        else:
            self._go(a, 'choose_bay', 'miss',
                     f'no {self.colour} target ({where}); P(bay) '
                     f'{self.bay_belief[i]:.2f} after the miss')

    def _emit_loc(self, a):
        """Emit the error the robot cannot see, beside the one it believes."""
        b, x = a.belief(), a.pose
        mb = Batch('coco.metrics.v1.MetricBatch')
        mb.add(a.tick, a.t_world, name='loc_error',
               value=math.hypot(b[0] - x[0], b[1] - x[1]), unit='m')
        loc = a.subsystems.get('localise')
        q = loc.quality() if loc is not None and hasattr(loc, 'quality') \
            else None
        if q is not None:
            mb.add(a.tick, a.t_world, name='loc_sigma', value=q['sigma_xy'],
                   unit='m')
        a.emit('coco.metrics.values.v1', mb)

    def _emit_arm(self, a, s, phase):
        # side view, from the shoulder (coco.arm.v1): the pinch and the elbow
        ex, ez = arm.elbow_point(s['joint1'])
        row = dict(s, phase=phase, ee_x=s['ee_x'] - arm.S_X,
                   ee_z=s['ee_z'] - arm.S_Z, elbow_x=ex - arm.S_X,
                   elbow_z=ez - arm.S_Z)
        ab = Batch('coco.arm.v1.ArmStateBatch')
        ab.add(a.tick, a.t_world, **row)
        a.emit('coco.arm.state.v1', ab)

    # -- the hash --------------------------------------------------------------

    def state_bytes(self) -> bytes:
        """Return the mission state, quantized (docs/v2/ARENA_MODEL.md)."""
        p = self.problem
        mask = sum(1 << i for i in self.searched)
        out = [struct.pack('<BBbbbBII', STATES.index(self.state),
                           0 if self.colour is None
                           else COLOURS.index(self.colour) + 1,
                           -1 if self.truth is None else p.index(self.truth),
                           -1 if self.target is None else self.target,
                           -1 if self.location == p.start
                           else p.index(self.location),
                           self.awaiting, mask, self.update),
               struct.pack(f'<{len(self.bay_belief)}q',
                           *(round(v * 1e12) for v in self.bay_belief)),
               struct.pack('<3qBB', _q(self.since), _q(self.p_true),
                           _q(self.prog_t), self.recoveries,
                           STATES.index(self.leg) if self.leg else 255),
               struct.pack('<4Q', *self.rng.state)]
        return b''.join(out)


def order_rows(cols) -> List[Tuple[Tuple[int, ...], float]]:
    """Return ``[(order, expected cost)]`` from an OrderCostBatch's columns."""
    o = cols['order']
    return [(tuple(o[a:a + n]), e) for a, n, e in
            zip(cols['order_offset'], cols['order_len'],
                cols['expected_cost'])]


SUBSYSTEMS['mission'] = ArenaMission
