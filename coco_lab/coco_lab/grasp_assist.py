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
Grasp Assist, the model side (M6F.3 envelope, M6F.5 pipeline; README §5.8).

Badge: **MODEL · MoveIt-style**. Deterministic, kinematic, no forces: it decides
from geometry and COCO's own constants whether an object can be picked, why not
when it cannot, and how the robot gets there.

Every envelope number is an existing constant, imported, never re-typed:

- the **approach window** ``grasp.WINDOW`` (0.151-0.1565 m ahead) and lateral
  limit ``grasp.MAX_LATERAL`` (10 mm): ``coco_config.robot.approach_window`` and
  ``GRASP_MAX_LATERAL``, the Stack's proximity gate;
- the **fingers**: the widest object they have closed on in the Stack, the
  32 mm yellow target (``grasp.TARGET_DIAMETER``, from ``coco_config.robot.TARGETS``);
  the four targets (20-32 mm) are the verified band;
- the **magnet does the holding** (two fingers and a magnet): an object that is
  not magnetic cannot be held, whatever its size;
- the **reach envelope**: the arm (``arm.ik``, the URDF chain of
  ``arm_ik.py``) must reach both ends of the approach window at the object's grasp
  band height and at the hover height above it (``arm.HOVER_CLEARANCE``), so every
  pick ends inside the Stack's own window. The magnet binds
  ``grasp.TARGET_HEIGHT - arm.TARGET_XZ[1]`` = 30 mm below an object's top, as on
  the Stack's targets -- an ASSUMPTION for other objects, labelled as one.

Refusal reasons, in the order they are checked and reported (README §5.8):
``too_wide``, ``out_of_reach``, ``not_magnetic``, ``blocked``.
"""

import struct
from typing import Dict, List, Optional, Tuple

from . import arm
from .arena import ArenaError, SUBSYSTEMS
from .columns import Batch, CLOCKS
from .grasp import (ALIGNED, APPROACH_RANGE, CREEP, Grasp, MAX_CREEPS, MAX_LATERAL, SETTLED,
                    TARGET_DIAMETER, TARGET_HEIGHT, TURN, WINDOW)
from .numerics import math, sq
from .search import search
from .sketch import _nearest_free, WAYPOINT_TOL
from .terrain import ray_rect

REASONS = ('too_wide', 'out_of_reach', 'not_magnetic', 'blocked')
REASON_TEXT = {
    'too_wide': 'too wide for the fingers',
    'out_of_reach': "out of the arm's reach envelope",
    'not_magnetic': 'not magnetic: the magnet does the holding',
    'blocked': 'blocked: no free pose puts it in the approach window',
}
#: the widest object the fingers have closed on in the Stack (the yellow target)
FINGER_MAX = max(TARGET_DIAMETER.values())
#: the band of widths the Stack has picked (the four targets)
FINGER_VERIFIED = (min(TARGET_DIAMETER.values()), FINGER_MAX)
#: where the magnet binds below an object's top (the Stack's targets: 0.158 - 0.128)
BAND_BELOW_TOP = TARGET_HEIGHT - arm.TARGET_XZ[1]


def width(item: Dict[str, object]) -> float:
    """Return what the fingers must span: a cylinder's diameter, a box's narrower side."""
    if item['shape'] == 'cylinder':
        return item['diameter']
    return min(item['size'][0], item['size'][1])


def top(item: Dict[str, object]) -> float:
    """Return the item's height above what it stands on."""
    return item['height'] if item['shape'] == 'cylinder' else item['size'][2]


def band_height(obj: Dict[str, object], floor_z: float) -> float:
    """
    Return the grasp band's height above the surface the robot stands on (m).

    Relative first, so an object on a deck gives bit for bit the band it gives on
    the floor: the Stack's grasp height is the envelope's top edge (the hover
    reach bounds it, ``coco_config.robot.GRASP_REACH_X_MAX``).
    """
    return (obj['z'] - floor_z) + (top(obj) - BAND_BELOW_TOP)


def reachable(band_z: float) -> bool:
    """Return whether the arm reaches both window ends at the band and at hover above it."""
    return all(arm.ik(x, z) for x in WINDOW for z in (band_z, band_z + arm.HOVER_CLEARANCE))


def reach_band(step: float = 0.0005, z_max: float = 0.5) -> Tuple[float, float]:
    """
    Return the grasp-band heights the arm can pick at, ``(lo, hi)`` (m).

    Derived by scanning :func:`reachable` at ``step``; the envelope drawn on the
    floor is the approach window itself (a 5.5 mm band ahead of the robot).
    """
    zs = [k * step for k in range(int(z_max / step) + 1)]
    ok = [z for z in zs if reachable(z)]
    if not ok:
        return (math.nan, math.nan)
    return (ok[0], ok[-1])


def robot_floor(obj: Dict[str, object]) -> float:
    """
    Return the height of the surface the robot would stand on to pick ``obj``.

    The floor under a bench, rack, pallet or box (0: they stand on the floor);
    the object's own surface when it stands on the floor or on a platform the
    robot can drive onto.
    """
    return obj['z'] if obj['support'] == 'floor' or obj.get('support_kind') == 'platform' \
        else 0.0


def static_check(obj: Dict[str, object]) -> List[str]:
    """
    Return every reason ``obj`` cannot be picked, from the object alone.

    ``blocked`` needs the world (:func:`approach_poses`); this is the rest,
    in :data:`REASONS` order. An empty list means the object is pickable if a
    free approach pose exists.
    """
    out = []
    if width(obj) > FINGER_MAX:
        out.append('too_wide')
    if not reachable(band_height(obj, robot_floor(obj))):
        out.append('out_of_reach')
    if not obj['magnetic']:
        out.append('not_magnetic')
    return out


def affordances(spec) -> Dict[str, Dict[str, object]]:
    """
    Return, for each object spawn of a canonical v3 spec, its static affordance.

    ``{id: {'item', 'width', 'band_z', 'reasons'}}``; ``blocked`` is added by
    the pipeline, which knows the map.
    """
    from . import worldspec_v3 as v3
    kinds = {e['id']: e['kind'] for e in spec['kit']}
    out = {}
    for o in v3.objects(spec):
        o = dict(o, support_kind=kinds.get(o['support'], 'floor'))
        out[o['id']] = {'item': o['item'], 'width': width(o),
                        'band_z': band_height(o, robot_floor(o)),
                        'reasons': static_check(o)}
    return out


def window_pose(xy: Tuple[float, float], heading: float) -> Tuple[float, float, float]:
    """Return the robot pose facing ``heading`` with ``xy`` at the window's centre."""
    mid = (WINDOW[0] + WINDOW[1]) / 2
    return (xy[0] - mid * math.cos(heading), xy[1] - mid * math.sin(heading), heading)


def headings(n: int = 16) -> List[float]:
    """Return ``n`` evenly spaced approach headings, 0 first."""
    return [2 * math.pi * k / n for k in range(n)]


def first_reason(reasons: List[str]) -> Optional[str]:
    """Return the reason shown first (README order), or None for a pickable object."""
    for r in REASONS:
        if r in reasons:
            return r
    return None


# -- the pipeline (M6F.5): an Arena subsystem, "assist" ------------------------------

#: coco_config.robot.CAMERA_HFOV and CAMERA_XYZ[0] (rad, m ahead of base_footprint);
#: coco_lab never imports coco_config, so they are copied here and pinned by
#: coco_lab_ros/test/test_m6f_constants.py
CAMERA_HFOV = 1.25
CAMERA_X = 0.125
#: MEASURED (STACK): the 20 mm target was first detected about 1.40 m away, as a
#: 3 x 4 px blob (docs/data/p03c_episode_gazebo/README.md); the camera range used here
DETECT_RANGE = 1.40
#: detected in any direction within the gated grasp's approach zone (grasp.APPROACH_RANGE)
SHORT_RADIUS = APPROACH_RANGE
#: the pre-grasp pose stands this far behind the object: the waypoint follower stops
#: within sketch.WAYPOINT_TOL of its goal, which leaves the object inside the approach
#: zone (grasp.APPROACH_RANGE)
STANDOFF = APPROACH_RANGE - WAYPOINT_TOL
HEADINGS = 16
BADGE = 'MODEL · MoveIt-style'
CH_ENVELOPE = 'coco.manip.grasp.envelope.v1'
CH_CANDIDATES = 'coco.manip.grasp.candidates.v1'
CH_STAGES = 'coco.manip.grasp.stages.v1'
CH_ARM = 'coco.arm.state.v1'
PHASES = ('idle', 'approach', 'align', 'reach', 'carry', 'release')
#: the manip.grasp stream messages, as columns (coco_lab.columns' form; every
#: column per row); coco_lab_ros/test/test_m6f_manip_schema.py holds them to the proto
TABLES = {
    'coco.manip.v1.CandidateBatch': (
        ('attempt', 'I'), ('object_id', 's'), ('item', 's'), ('x', 'd'), ('y', 'd'),
        ('z', 'd'), ('width', 'd'), ('band_z', 'd'), ('magnetic', 'B'), ('seen_by', 's'),
        ('reason', 's'), ('reasons_mask', 'I'), ('approach_x', 'd'), ('approach_y', 'd'),
        ('approach_theta', 'd'), ('approach_cost', 'd'), ('rank', 'I')),
    'coco.manip.v1.StageBatch': (
        ('attempt', 'I'), ('stage', 's'), ('object_id', 's'), ('robot_x', 'd'),
        ('robot_y', 'd'), ('robot_theta', 'd'), ('ahead', 'd'), ('left', 'd'),
        ('ik_joint1', 'd'), ('ik_joint2', 'd'), ('outcome', 's')),
}
_NAN = float('nan')


class GraspBatch(Batch):
    """A coco_lab.columns.Batch for the manip.grasp messages (their own tables)."""

    def __init__(self, message: str):
        """Start empty; ``message`` is one of :data:`TABLES`."""
        self.message = message
        self.fields = CLOCKS + TABLES[message]
        self.scalars = {}
        self.seq = 0
        self._new()


def envelope() -> Dict[str, object]:
    """Return the GraspEnvelope header: every number a refusal is measured against."""
    lo, hi = reach_band()
    return {'window_near': WINDOW[0], 'window_far': WINDOW[1], 'max_lateral': MAX_LATERAL,
            'finger_max': FINGER_MAX, 'finger_verified_min': FINGER_VERIFIED[0],
            'band_below_top': BAND_BELOW_TOP, 'reach_band_lo': lo, 'reach_band_hi': hi,
            'hover_clearance': arm.HOVER_CLEARANCE, 'detect_range': DETECT_RANGE,
            'detect_hfov': CAMERA_HFOV, 'short_radius': SHORT_RADIUS, 'standoff': STANDOFF,
            'headings': HEADINGS, 'badge': BADGE}


def mask(reasons: List[str]) -> int:
    """Return the reasons as bits, :data:`REASONS` order."""
    return sum(1 << REASONS.index(r) for r in reasons)


def ik_nearest(x: float, z: float, near) -> Optional[Tuple[float, float]]:
    """Return the IK solution for (x, z) nearest the joint pose ``near``, or None."""
    sols = arm.ik(x, z)
    if not sols:
        return None
    return min(sols, key=lambda q: sq(q[0] - near[0]) + sq(q[1] - near[1]))


def pick_script(ahead: float, band: float):
    """
    Return the pick as joint-space waypoints, for an object ``ahead`` m at ``band``.

    ``arm.GRASP_SCRIPT``'s phases, durations, fingers and magnet, with its
    hover and grasp poses solved by IK for this object (the solution nearest
    pick_place.py's verified pose); None if IK has no solution.
    """
    grasp_q = ik_nearest(ahead, band, arm.POSES['grasp'])
    hover_q = ik_nearest(ahead, band + arm.HOVER_CLEARANCE, arm.hover_pose())
    if grasp_q is None or hover_q is None:
        return None
    named = dict(arm.POSES, hover=hover_q, grasp=grasp_q)
    return [(ph, named[to], dur, fingers, magnet)
            for ph, to, dur, fingers, magnet in arm.GRASP_SCRIPT]


def script_at(script, t: float) -> Optional[Dict[str, object]]:
    """Return the arm ``t`` s into a pick script (``arm.script_state``'s rules), or None."""
    q = arm.POSES['home']
    start = 0.0
    for phase, goal, dur, fingers, magnet in script:
        if t < start + dur - 1e-9:
            f = (t - start) / dur
            j1 = q[0] + (goal[0] - q[0]) * f
            j2 = q[1] + (goal[1] - q[1]) * f
            x, z = arm.fk(j1, j2)
            return {'joint1': j1, 'joint2': j2, 'ee_x': x, 'ee_z': z,
                    'finger_left': fingers[0], 'finger_right': fingers[1],
                    'magnet_on': magnet, 'holding': magnet, 'phase': phase}
        q, start = goal, start + dur
    return None


def script_seconds(script) -> float:
    """Return a pick script's duration."""
    return sum(d for _, _, d, _, _ in script)


class GraspAssist:
    """
    The Arena's ``assist`` subsystem: Grasp Assist on a World Spec v3 level.

    Inputs (``config``): ``assist.grasp=go`` (the G button: pick the best
    candidate, or release what is carried), ``assist.target=<object id>|any``
    (restrict the choice), ``assist.abort=1``. A person's teleop, a goal click
    or STOP ends an attempt (STOP > the person > assists, README invariant 3).
    """

    def __init__(self, arena):
        """Attach to a v3 Arena: the objects where the spec puts them, nothing carried."""
        from . import worldspec_v3 as v3
        if not v3.is_v3(arena.spec):
            raise ArenaError('Grasp Assist needs a World Spec v3 level')
        dx, dy = arena.spec['world_to_map']
        kinds = {e['id']: e['kind'] for e in arena.spec['kit']}
        #: id -> the resolved object (catalog fields), MAP frame
        self.objects: Dict[str, Dict[str, object]] = {}
        for o in v3.objects(arena.spec):
            self.objects[o['id']] = dict(o, x=o['x'] + dx, y=o['y'] + dy,
                                         support_kind=kinds.get(o['support'], 'floor'),
                                         status='placed')
        #: occluders, MAP frame: (id, rect)
        self.occluders = [(rid, (r[0] + dx, r[1] + dx, r[2] + dy, r[3] + dy))
                          for rid, r in v3.static_rects(arena.spec)]
        self.want = 'any'
        self.attempt = 0
        self.pending = False
        self.pending_abort = False
        self._idle()
        arena.emit_header(CH_ENVELOPE, envelope())

    def _idle(self):
        self.phase = 'idle'
        self.target: Optional[str] = None
        self.pre: Optional[Tuple[float, float, float]] = None
        self.since = 0.0
        self.creeps = 0
        self.wait = 0
        self.script = None
        self.verified = False
        self.reason = ''

    # -- inputs ---------------------------------------------------------------------

    def config(self, key: str, value: str) -> None:
        """Apply ``assist.<key>=<value>``."""
        if key == 'grasp':
            self.pending = True
        elif key == 'target':
            if value != 'any' and value not in self.objects:
                raise ArenaError(f'assist.target: no object {value!r}')
            self.want = value
        elif key == 'abort':
            self.pending_abort = True
        else:
            raise ArenaError(f'unknown assist setting {key!r}')

    def on_reset(self, arena) -> None:
        """End the attempt on a reset; a carried object is put down where it is."""
        for o in self.objects.values():
            if o['status'] == 'carried':
                o['status'] = 'placed'
        self._idle()

    # -- the tick -------------------------------------------------------------------

    def on_tick(self, a) -> None:
        """Advance the attempt one tick (after the robot moved and scanned)."""
        if self.pending_abort:
            self.pending_abort = False
            if self.phase not in ('idle', 'carry'):
                self._end(a, 'aborted', 'aborted by the person')
        if self.pending:
            self.pending = False
            self._press(a)
        ph = self.phase
        if ph == 'approach':
            self._approach(a)
        elif ph == 'align':
            self._align(a)
        elif ph in ('reach', 'release'):
            self._script(a)
        if self.phase == 'carry':
            self._ride(a)

    def _press(self, a) -> None:
        if self.phase == 'carry':
            self.phase, self.since = 'release', a.t_world
            self._drive(a, 0.0, 0.0)
            self._stage(a, 'release', self.target, 'ok')
            return
        if self.phase != 'idle':
            self._stage(a, 'busy', self.target or '', f'an attempt is already {self.phase}')
            return
        self.attempt += 1
        rows = self.candidates(a)
        self._emit_candidates(a, rows)
        self._stage(a, 'detect', '', f'{len(rows)} object(s) in range')
        ok = [r for r in rows if not r['reason']]
        self._stage(a, 'check', '', f'{len(ok)} of {len(rows)} can be picked')
        chosen = next((r for r in rows if r['rank'] == 0 and not r['reason']
                       and self.want in ('any', r['object_id'])), None)
        if chosen is None:
            if not rows:
                why = 'nothing in range'
            else:
                r = next((r for r in rows if self.want in ('any', r['object_id'])), rows[0])
                why = f'{r["object_id"]}: ' + (REASON_TEXT[r['reason']] if r['reason']
                                               else 'not the requested object')
            self._end(a, 'refused', why)
            return
        self.target = chosen['object_id']
        self.pre = (chosen['approach_x'], chosen['approach_y'], chosen['approach_theta'])
        self._stage(a, 'choose', self.target, f'cost {chosen["approach_cost"]:.2f} m')
        a.request_goal(self.pre[0], self.pre[1])
        self.phase, self.wait = 'approach', 1
        self._stage(a, 'approach', self.target, 'planning to the pre-grasp pose')

    # -- detect, check, choose -------------------------------------------------------

    def seen_by(self, a, o) -> str:
        """Return 'camera', 'radius' or '' for object ``o`` from the robot's true pose."""
        x, y, th = a.pose
        cx, cy = x + CAMERA_X * math.cos(th), y + CAMERA_X * math.sin(th)
        dx, dy = o['x'] - cx, o['y'] - cy
        d = math.hypot(dx, dy)
        bearing = math.atan2(dy, dx) - th
        bearing = math.atan2(math.sin(bearing), math.cos(bearing))
        if d <= DETECT_RANGE and abs(bearing) <= CAMERA_HFOV / 2 and \
                not self._occluded(cx, cy, o, d):
            return 'camera'
        if math.hypot(o['x'] - x, o['y'] - y) <= SHORT_RADIUS:
            return 'radius'
        return ''

    def _occluded(self, cx, cy, o, d) -> bool:
        if d < 1e-9:
            return False
        ux, uy = (o['x'] - cx) / d, (o['y'] - cy) / d
        for rid, r in self.occluders:
            if rid == o['support']:
                continue        # what it stands on does not hide it
            t = ray_rect(cx, cy, ux, uy, r)
            if t is not None and t < d - 1e-9:
                return True
        return False

    def _free(self, a, x, y) -> bool:
        cell = a.plan_map.cell_at(x, y)
        return cell is not None and a.plan_map.at(cell) == 0

    def _floor_at(self, a, x, y) -> float:
        return a.terrain.height(x, y) if a.terrain is not None else 0.0

    def approach_poses(self, a, o) -> List[Tuple[float, float, float]]:
        """
        Return the free pre-grasp poses for ``o``, one per free heading.

        A heading is free when the pre-grasp pose (``STANDOFF`` behind), the
        window pose and the straight line between them are all free on the
        plan map (inflated by the robot's radius), and both poses stand on the
        surface the object is picked from.
        """
        floor = robot_floor(o)
        res = a.plan_map.resolution
        out = []
        for h in headings(HEADINGS):
            wx, wy, _ = window_pose((o['x'], o['y']), h)
            px, py = o['x'] - STANDOFF * math.cos(h), o['y'] - STANDOFF * math.sin(h)
            n = max(1, math.ceil(math.hypot(px - wx, py - wy) / (res / 2)))
            line = [(px + (wx - px) * k / n, py + (wy - py) * k / n) for k in range(n + 1)]
            if all(self._free(a, x, y) and abs(self._floor_at(a, x, y) - floor) < 1e-9
                   for x, y in line):
                out.append((px, py, h))
        return out

    def plan_cost(self, a, xy) -> Optional[float]:
        """Return the planned path length (m) from the robot's belief to ``xy``, or None."""
        from .arena import PLANNERS
        g = a.grid
        b = a.belief()
        sc, gc = a.plan_map.cell_at(b[0], b[1]), a.plan_map.cell_at(*xy)
        if sc is None or gc is None:
            return None
        s, t = _nearest_free(g, sc), _nearest_free(g, gc)
        if s is None or t is None:
            return None
        r = search(g, s, t, **PLANNERS['astar'])
        return r.cost * a.plan_map.resolution if r.found else None

    def candidates(self, a, only_seen: bool = True) -> List[Dict[str, object]]:
        """
        Detect, check and rank the placed objects (one row each, CandidateBatch's).

        The cost is the planned path length to the free pre-grasp pose nearest
        the robot that a path reaches. Rank 0 is the cheapest pickable one
        (restricted to ``assist.target`` when set); refused objects rank after
        every pickable one, by distance.
        """
        b = a.belief()
        rows = []
        for oid in sorted(self.objects):
            o = self.objects[oid]
            if o['status'] != 'placed':
                continue
            seen = self.seen_by(a, o)
            if only_seen and not seen:
                continue
            reasons = static_check(o)
            best = None
            if not reasons:
                poses = sorted(self.approach_poses(a, o),
                               key=lambda p: (math.hypot(p[0] - b[0], p[1] - b[1]), p[2]))
                for p in poses:
                    cost = self.plan_cost(a, (p[0], p[1]))
                    if cost is not None:
                        best = (p, cost)
                        break
                if best is None:
                    reasons = ['blocked']
            rows.append({'object_id': oid, 'item': o['item'], 'x': o['x'], 'y': o['y'],
                         'z': o['z'], 'width': width(o),
                         'band_z': band_height(o, robot_floor(o)), 'magnetic': o['magnetic'],
                         'seen_by': seen, 'reason': first_reason(reasons) or '',
                         'reasons_mask': mask(reasons),
                         'approach_x': best[0][0] if best else _NAN,
                         'approach_y': best[0][1] if best else _NAN,
                         'approach_theta': best[0][2] if best else _NAN,
                         'approach_cost': best[1] if best else _NAN,
                         'dist': math.hypot(o['x'] - b[0], o['y'] - b[1])})
        ok = sorted((r for r in rows if not r['reason']
                     and self.want in ('any', r['object_id'])),
                    key=lambda r: (r['approach_cost'], r['object_id']))
        chosen = {r['object_id'] for r in ok}
        rest = sorted((r for r in rows if r['object_id'] not in chosen),
                      key=lambda r: (r['dist'], r['object_id']))
        for k, r in enumerate(ok + rest):
            r['rank'] = k
        return sorted(rows, key=lambda r: r['rank'])

    # -- approach, align, creep --------------------------------------------------------

    def _approach(self, a) -> None:
        if self.wait:
            self.wait -= 1
            return
        if a.user_teleop or (a.mode == 'goal' and a.goal_source != 'mission'):
            self._end(a, 'aborted', 'the person took the wheels')
            return
        if a.mode == 'goal':
            return
        x, y, _ = a.belief()
        miss = math.hypot(x - self.pre[0], y - self.pre[1])
        if miss > WAYPOINT_TOL + 1e-9:
            self._end(a, 'aborted', f'the approach stopped {miss:.2f} m short of the '
                                    'pre-grasp pose (no path, or STOP)')
            return
        self.phase, self.creeps = 'align', 0
        self._drive(a, 0.0, 0.0)
        self._stage(a, 'align', self.target, f'at the pre-grasp pose ({miss:.3f} m off)')

    def _drive(self, a, v: float, w: float) -> None:
        # autonomy driving, as the mission backs up: teleop mode, not the person's
        a.mode, a.teleop, a.user_teleop = 'teleop', (v, w), False

    def _interrupted(self, a) -> bool:
        return a.user_teleop or a.mode != 'teleop'

    def _align(self, a) -> None:
        if self._interrupted(a):
            self._end(a, 'aborted', 'the person took the wheels, or STOP')
            return
        o = self.objects[self.target]
        ax, ay = Grasp.in_base(a.pose, (o['x'], o['y']))
        bearing = math.atan2(ay, ax)
        if abs(bearing) > ALIGNED:
            self._drive(a, 0.0, max(-TURN, min(TURN, bearing / a.dt)))
            return
        mid = (WINDOW[0] + WINDOW[1]) / 2
        if ax - mid > SETTLED and self.creeps < MAX_CREEPS:
            if self.creeps == 0:
                self._stage(a, 'creep', self.target, 'aligned; creeping into the window',
                            ax, ay)
            self.creeps += 1
            self._drive(a, min(CREEP, (ax - mid) / a.dt), 0.0)
            return
        self._drive(a, 0.0, 0.0)
        if not (WINDOW[0] <= ax <= WINDOW[1] and abs(ay) <= MAX_LATERAL):
            self._end(a, 'refused', f'not in the window (ahead {ax * 1000:.1f} mm, left '
                                    f'{ay * 1000:.1f} mm)', ax, ay)
            return
        floor = self._floor_at(a, a.pose[0], a.pose[1])
        self.script = pick_script(ax, band_height(o, floor))
        if self.script is None:
            self._end(a, 'refused', REASON_TEXT['out_of_reach'], ax, ay)
            return
        self.phase, self.since, self.verified = 'reach', a.t_world, False
        g = self.script[2][1]
        self._stage(a, 'reach', self.target, 'in the window: IK solved', ax, ay, g[0], g[1])

    # -- reach, grip, verify, carry, release ---------------------------------------------

    def _script(self, a) -> None:
        if self._interrupted(a):
            self._end(a, 'aborted', 'the person took the wheels, or STOP')
            return
        self._drive(a, 0.0, 0.0)
        t = a.t_world - self.since
        if self.phase == 'release':   # the arm's own time, as the gated grasp's release
            if t >= arm.script_seconds() - 1e-9:
                o = self.objects[self.target]
                x, y, th = a.pose
                mid = (WINDOW[0] + WINDOW[1]) / 2
                ox, oy = x + mid * math.cos(th), y + mid * math.sin(th)
                o.update(x=ox, y=oy, z=self._floor_at(a, ox, oy), status='placed',
                         support='floor', support_kind='floor')
                self._end(a, 'done', f'released {self.target}')
            return
        s = script_at(self.script, t)
        if s is None:
            s = script_at(self.script, script_seconds(self.script) - 1e-6)
            self._emit_arm(a, s, 'stowed')
            self.phase = 'carry'
            self._stage(a, 'carry', self.target, f'the magnet holds {self.target}')
            a.mode, a.teleop = 'idle', (0.0, 0.0)
            return
        self._emit_arm(a, s, s['phase'])
        if s['magnet_on'] and not self.verified:
            o = self.objects[self.target]
            ax, ay = Grasp.in_base(a.pose, (o['x'], o['y']))
            ok = (o['magnetic'] and width(o) <= FINGER_MAX and WINDOW[0] <= ax <= WINDOW[1]
                  and abs(ay) <= MAX_LATERAL)
            self._stage(a, 'grip', self.target, 'fingers closed, magnet on', ax, ay)
            if not ok:
                self._end(a, 'refused', 'verify failed: the magnet did not hold', ax, ay)
                return
            self.verified = True
            o['status'] = 'carried'
            self._stage(a, 'verify', self.target, 'ok: the magnet holds', ax, ay)

    def _ride(self, a) -> None:
        o = self.objects[self.target]
        x, y, th = a.pose
        mid = (WINDOW[0] + WINDOW[1]) / 2
        o.update(x=x + mid * math.cos(th), y=y + mid * math.sin(th),
                 z=self._floor_at(a, x, y))

    def carried(self) -> Optional[str]:
        """Return the id of the object the magnet holds, if any."""
        return self.target if self.phase in ('carry', 'release') else None

    def _end(self, a, stage, outcome, ahead=_NAN, left=_NAN) -> None:
        self._stage(a, stage, self.target or '', outcome, ahead, left)
        if self.target is not None and self.phase != 'release' \
                and self.objects[self.target]['status'] == 'carried':
            self.objects[self.target]['status'] = 'placed'
        if a.mode == 'teleop' and not a.user_teleop:
            a.mode, a.teleop = 'idle', (0.0, 0.0)
        att = self.attempt
        self._idle()
        self.attempt, self.reason = att, outcome

    # -- emitting -------------------------------------------------------------------------

    def _stage(self, a, stage, object_id, outcome, ahead=_NAN, left=_NAN, j1=_NAN,
               j2=_NAN) -> None:
        b = GraspBatch('coco.manip.v1.StageBatch')
        x, y, th = a.pose
        b.add(a.tick, a.t_world, attempt=self.attempt, stage=stage, object_id=object_id,
              robot_x=x, robot_y=y, robot_theta=th, ahead=ahead, left=left, ik_joint1=j1,
              ik_joint2=j2, outcome=outcome)
        a.emit(CH_STAGES, b)

    def _emit_candidates(self, a, rows) -> None:
        b = GraspBatch('coco.manip.v1.CandidateBatch')
        for r in rows:
            b.add(a.tick, a.t_world, attempt=self.attempt,
                  **{k: v for k, v in r.items() if k != 'dist'})
        a.emit(CH_CANDIDATES, b)

    def _emit_arm(self, a, s, phase) -> None:
        ex, ez = arm.elbow_point(s['joint1'])
        row = dict(s, phase=phase, ee_x=s['ee_x'] - arm.S_X, ee_z=s['ee_z'] - arm.S_Z,
                   elbow_x=ex - arm.S_X, elbow_z=ez - arm.S_Z)
        ab = Batch('coco.arm.v1.ArmStateBatch')
        ab.add(a.tick, a.t_world, **row)
        a.emit(CH_ARM, ab)

    # -- the hash -------------------------------------------------------------------------

    def state_bytes(self) -> bytes:
        """Return the attempt and every object's place, quantized (micrometres)."""
        def q(v):
            return round(v * 1e6)
        ids = sorted(self.objects)
        parts = [b'coco.arena.assist.v1\x00',
                 struct.pack('<BIii', PHASES.index(self.phase), self.attempt,
                             -1 if self.target is None else ids.index(self.target),
                             -1 if self.want == 'any' else ids.index(self.want)),
                 struct.pack('<qII', q(self.since), self.creeps, self.wait)]
        for oid in ids:
            o = self.objects[oid]
            parts.append(struct.pack('<3qB', q(o['x']), q(o['y']), q(o['z']),
                                     o['status'] == 'carried'))
        return b''.join(parts)


def run_scenario(spec, scenario: Dict[str, object]) -> Dict[str, object]:
    """
    Run one Grasp Assist scenario headless; return its stage log and hashes.

    ``scenario``: ``{seed, pose: [x, y, theta] (map frame), ticks, inputs: [{tick,
    kind, ...}], hash_version}``; inputs are ``coco_lab.arena.InputEvent`` fields.
    The result holds every stage row, the per-tick state hashes' sha256 chain and
    the last hash: what the golden traces pin.
    """
    import hashlib
    from .arena import Arena, InputEvent
    stages = []

    def hook(ch, tick, cols, scalars):
        if cols is not None and ch == CH_STAGES:
            for i in range(len(cols['seq'])):
                row = [cols[n][i] for n, _ in TABLES['coco.manip.v1.StageBatch']]
                stages.append([tick] + [None if isinstance(v, float) and v != v else v
                                        for v in row])
    a = Arena(spec, scenario['seed'], on_family=hook,
              hash_version=scenario.get('hash_version', 1))
    a.pose = tuple(scenario['pose'])
    by: Dict[int, list] = {}
    for e in scenario['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    chain = hashlib.sha256()
    last = ''
    for _ in range(scenario['ticks']):
        last = a.step(by.get(a.tick, ())).state_hash
        chain.update(last.encode())
    sub = a.subsystems.get('assist')
    return {'stages': stages, 'hash_chain': chain.hexdigest(), 'last_hash': last,
            'pose': list(a.pose), 'carried': sub.carried() if sub else None,
            'objects': {k: [o['x'], o['y'], o['z'], o['status']]
                        for k, o in sorted(sub.objects.items())} if sub else {}}


SUBSYSTEMS['assist'] = GraspAssist
