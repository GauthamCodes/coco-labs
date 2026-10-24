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
The M6 mini-games, model side (M6F.6; README §5.9): Fetch Rush and Rush Hour.

Three parts, none of them UI:

- **The actors** (:class:`DepotActors`, the Arena subsystem ``actors``): a World
  Spec v3 level's forklifts and walkers as **collision bodies in the model** --
  discs covering each actor's box, at its kinematic pose
  (``worldspec_v3.actor_pose``), so the LiDAR sees them and the robot cannot
  drive into one. SIMPLIFIED: the discs over-cover the box by a few centimetres
  at its long sides; the game's clearance is measured to the exact box.
  Actors never yield (they are a schedule, as in Gazebo's ``set_pose``).
- **The rules** (:class:`FetchRush`, :class:`RushHour`): observers of the Arena's
  ticks. A game is a pure function of the World Spec, the seed and the input
  log (:func:`play`); its scorecard is never part of the model's state, as a
  renderer is not. Scores use real metrics only (integrity rule 4); stars come
  from the reference bot's result on the same seed and level (:func:`stars`),
  never from hand-picked numbers.
- **The reference bots** (:func:`bot_fetch_rush`, :func:`bot_rush_hour`): the
  planner plus Grasp Assist, closed-loop, recording the input log they send.
  :func:`verify` replays a record within M5's link limits.

"Fragile cargo" (Rush Hour) is a **game rule about how the robot is driven**, not
physics (README invariant 13): it scores the jerk of the commanded motion while
the canister is carried. The model simulates no breakage and no forces.
"""

import functools
import hashlib
import json
from pathlib import Path
import struct
from typing import Dict, List, Optional, Tuple

from . import numerics
from . import worldspec_v3 as v3
from .arena import Arena, ArenaError, InputEvent, PLANNERS, SUBSYSTEMS
from .grasp_assist import GraspAssist
from .link_bounds import validate_log
from .numerics import math
from .rng import Rng
from .search import search
from .sketch import _nearest_free, WAYPOINT_TOL

GAMES = ('fetch_rush', 'rush_hour')
#: README §5.9: Fetch Rush runs for three minutes
FETCH_RUSH_SECONDS = 180.0
#: Rush Hour's objectives on the Depot: pick ``object``, deliver it to ``drop``,
#: starting at ``start`` (world frame); the forklift lanes lie between them
RUSH_HOUR = {
    'aisle_to_dispatch': {'object': 'obj_aisle_1', 'drop': 'dispatch_drop',
                          'start': (20.0, 16.5, math.pi / 2), 'staging': (26.2, 14.0),
                          'across': (26.2, 8.5)},
}
GAME_LAYOUT = b'coco.game.v1\x00'

#: G1.11 -- Fetch Rush rules 2 (Gautham's 2026-10-18 decision, recorded 2026-10-21):
#: a round starts inside one zone; each order's planned round trip (from where the
#: last order ended to the object's best pre-grasp pose, then to the drop zone's
#: centre) fits ROUND_BUDGET_M; ROUND_ORDERS orders; the timer is the reference
#: bot's time for those deliveries x ROUND_TIMER_FACTOR. A record without ``rules``
#: is rules 1 (M6F.6's: 10 orders, 180 s), which stays as it was.
ROUND_BUDGET_M = 32.0
ROUND_ORDERS = 3
ROUND_TIMER_FACTOR = 1.5
#: a round's start zones: the Depot's regions, minus the forklift lanes (a start
#: there would be inside an actor's path at tick 0)
ROUND_NO_START = ('zone_forklift_lanes',)
LEVELS = Path(__file__).resolve().parent / 'levels'

#: G1.12 -- Fetch Rush rules 3 (Gautham's 2026-10-22 decisions): rules 2's rounds in two
#: modes. 'phone' (the default): 2 orders (the decision: each planned round trip <= 16 m;
#: PROVISIONAL 22 m -- with the lanes kept out, no 2-order round exists on the Depot below
#: 21.4 m, docs/v2/g1/data/g112/phone_budget.json; Gautham's call, G1_STATUS); 'full'
#: (the "Full shift"): rules 2's 3 orders within 32 m. No order's planned
#: route crosses the forklift lanes (ROUND_LANES), and a round the reference bot cannot
#: finish is rejected when the rounds are generated (the next draw is taken), so every
#: round on file is offered. Rules 2's rounds and records stay as they were.
ROUND_MODES = {'phone': {'orders': 2, 'budget_m': 22.0},
               'full': {'orders': ROUND_ORDERS, 'budget_m': ROUND_BUDGET_M}}
ROUND_MODE_DEFAULT = 'phone'
ROUND_LANES = ('zone_forklift_lanes',)

#: G2.1 -- Fetch Rush rules 4 (Gautham, 2026-10-23; planning answer 2026-10-24): rules 3's
#: rounds, but a route may cross the forklift lane (ROUND_LANES, the east-west lane) only at a
#: marked crossing (:func:`crossings`: hazard-striped where a walker's lane crosses it), with
#: COCO's whole footprint on the stripes (:func:`crossing_bands`), and never run along it; the
#: phone budget is the smallest giving at least 3 distinct rounds with timers <= 5:00 (else
#: <= 6:00): ``tools/g2/sweep_phone_budget_r4.py``. Rules 3's rounds and records stay as they were.
FETCH_RUSH_RULES = 4
ROUND_MODES_R4 = {'phone': {'orders': 2, 'budget_m': 22.0},
                  'full': {'orders': ROUND_ORDERS, 'budget_m': ROUND_BUDGET_M}}
#: a lane is drawn this wide each side of an actor's path beyond half its footprint
#: (lab_web/src/game/world/describe.ts paints the same lanes and stripes)
LANE_MARGIN = 0.25


# -- the actors as collision bodies ------------------------------------------------

def actor_discs(actor, t: float, dx: float = 0.0, dy: float = 0.0):
    """Return discs ``(x, y, r)`` whose union covers the actor's box at ``t``."""
    x, y, yaw = v3.actor_pose(actor, t)
    length, width = actor['footprint']
    n = max(1, math.ceil(length / width - 1e-9))
    seg = length / n
    r = math.hypot(seg / 2, width / 2)
    c, s = math.cos(yaw), math.sin(yaw)
    out = []
    for k in range(n):
        u = -length / 2 + seg * (k + 0.5)
        out.append((x + dx + c * u, y + dy + s * u, r))
    return out


def box_distance(px: float, py: float, actor, t: float, dx: float = 0.0,
                 dy: float = 0.0) -> float:
    """Return the distance from a point to the actor's box at ``t`` (0 inside)."""
    x, y, yaw = v3.actor_pose(actor, t)
    c, s = math.cos(yaw), math.sin(yaw)
    rx, ry = px - (x + dx), py - (y + dy)
    lx, ly = c * rx + s * ry, -s * rx + c * ry
    ex = max(abs(lx) - actor['footprint'][0] / 2, 0.0)
    ey = max(abs(ly) - actor['footprint'][1] / 2, 0.0)
    return math.hypot(ex, ey)


class DepotActors:
    """The Arena's ``actors`` subsystem: a v3 level's actor lanes, solid (``actors.on=1``)."""

    def __init__(self, arena):
        """Attach to a World Spec v3 Arena."""
        if not v3.is_v3(arena.spec):
            raise ArenaError('actors need a World Spec v3 level')
        self.arena = arena
        self.actors = v3.elements(arena.spec, 'actor')
        self.offset = tuple(arena.spec['world_to_map'])

    def config(self, key: str, value: str) -> None:
        """Apply ``actors.on=1`` (they move from t = 0 whether or not anyone watches)."""
        if key != 'on' or value != '1':
            raise ArenaError('actors: the only setting is actors.on=1')

    def discs(self):
        """Return every actor's covering discs at the current time, MAP frame."""
        t = self.arena.t_world
        return [d for a in self.actors for d in actor_discs(a, t, *self.offset)]

    def clearance(self, x: float, y: float, radius: float) -> float:
        """Return the robot circle's clearance to the nearest actor box (m; < 0 overlaps)."""
        t = self.arena.t_world
        return min((box_distance(x, y, a, t, *self.offset) for a in self.actors),
                   default=math.inf) - radius

    def on_tick(self, arena) -> None:
        """Do nothing: an actor's pose is a function of time."""

    def on_reset(self, arena) -> None:
        """Do nothing: the schedule does not restart."""

    def state_bytes(self) -> bytes:
        """Return the layout tag and the actor count (their poses follow from the tick)."""
        return b'coco.arena.actors.v1\x00' + struct.pack('<I', len(self.actors))


SUBSYSTEMS['actors'] = DepotActors


# -- helpers -------------------------------------------------------------------------

def _in_arena(fn):
    """G1.11: run ``fn`` in the numerics of the Arena it is given (numerics.version)."""
    @functools.wraps(fn)
    def run(*args, **kw):
        a = next(x for x in args if isinstance(x, Arena))
        with numerics.version(a.hash_version):
            return fn(*args, **kw)
    return run


@_in_arena
def plan_length(a: Arena, frm, to) -> Optional[float]:
    """Return A*'s path length (m) on the Arena's plan grid between two points, or None."""
    g = a.grid
    sc, gc = a.plan_map.cell_at(*frm), a.plan_map.cell_at(*to)
    if sc is None or gc is None:
        return None
    s, t = _nearest_free(g, sc), _nearest_free(g, gc)
    if s is None or t is None:
        return None
    r = search(g, s, t, **PLANNERS['astar'])
    return r.cost * a.plan_map.resolution if r.found else None


def zone_rect(spec, zone_id: str) -> Tuple[float, float, float, float]:
    """Return a zone's rectangle, MAP frame."""
    z = next(e for e in spec['kit'] if e['id'] == zone_id)
    dx, dy = spec['world_to_map']
    (cx, cy), (sx, sy) = z['center'], z['size']
    return (cx + dx - sx / 2, cx + dx + sx / 2, cy + dy - sy / 2, cy + dy + sy / 2)


def _inside(xy, r) -> bool:
    return r[0] <= xy[0] <= r[1] and r[2] <= xy[1] <= r[3]


# -- G2.1: the marked crossings of the forklift lane (rules 4) --------------------------------

def in_rect(xy, r) -> bool:
    """Whether ``xy`` lies in the rectangle ``(x0, x1, y0, y1)`` (edges included)."""
    return _inside(xy, r)


def _actor_lanes(spec):
    """Each actor's lane box ``(actor kind, x0, x1, y0, y1)``, MAP frame (describe.ts's lanes)."""
    dx, dy = spec['world_to_map']
    out = []
    for k in spec['kit']:
        if k.get('kind') != 'actor':
            continue
        w = k['footprint'][1] / 2 + LANE_MARGIN
        xs = [p[0] + dx for p in k['path']]
        ys = [p[1] + dy for p in k['path']]
        out.append((k['actor'], min(xs) - w, max(xs) + w, min(ys) - w, max(ys) + w))
    return out


def crossings(spec, lanes=ROUND_LANES) -> List[Tuple[float, float, float, float]]:
    """
    The marked crossings of the round lanes, MAP frame, sorted: where a forklift's lane meets
    another actor's (the hazard stripes describe.ts paints), across the whole depth of the
    lane zone it lies in (a lane zone wider than deep is crossed in y, else in x).
    """
    zones = [zone_rect(spec, z) for z in lanes]
    al = _actor_lanes(spec)
    out = set()
    for i in range(len(al)):
        for j in range(i + 1, len(al)):
            a, b = al[i], al[j]
            if 'forklift' not in (a[0], b[0]):
                continue
            x0, x1 = max(a[1], b[1]), min(a[2], b[2])
            y0, y1 = max(a[3], b[3]), min(a[4], b[4])
            if not (x0 < x1 and y0 < y1):
                continue
            for z in zones:
                if not (x0 < z[1] and z[0] < x1 and y0 < z[3] and z[2] < y1):
                    continue
                if z[1] - z[0] >= z[3] - z[2]:
                    out.add((max(x0, z[0]), min(x1, z[1]), z[2], z[3]))
                else:
                    out.add((z[0], z[1], max(y0, z[2]), min(y1, z[3])))
    return sorted(out)


def crossing_bands(spec, lanes=ROUND_LANES) -> List[Tuple[float, float, float, float]]:
    """Where COCO's centre may be inside a lane: each crossing narrowed by the robot radius
    across its width, so the whole footprint stays on the stripes."""
    r = spec['robot']['radius']
    zones = [zone_rect(spec, z) for z in lanes]
    out = []
    for c in crossings(spec, lanes):
        z = next(z for z in zones if z[0] <= c[0] and c[1] <= z[1] and z[2] <= c[2] and c[3] <= z[3])
        if z[1] - z[0] >= z[3] - z[2]:
            out.append((c[0] + r, c[1] - r, c[2], c[3]))
        else:
            out.append((c[0], c[1], c[2] + r, c[3] - r))
    return out


#: G2.1: a crossing is open to Fetch Rush's routes only if, within this many ticks of start
#: times (60 s: the walkers' 10 s and the east-west forklift's 40 s cycles), one straight
#: crossing at the auto speed touches no actor
CROSSING_WINDOW_TICKS = 600


@_in_arena
def crossing_windows(a: Arena, lanes=ROUND_LANES) -> List[Dict[str, object]]:
    """
    For each crossing band: a straight crossing of the lane zone on the band's centre line, at
    the auto speed, started at each of CROSSING_WINDOW_TICKS start times; the actors move by
    their known schedules (the model's own). Returns per band its start times with no contact
    (COCO's disc clear of every actor's box), the best clearance (m; negative: overlapping) and
    the crossing's duration (s). Measured on the model; nothing here moves it.
    """
    actors = v3.elements(a.spec, 'actor')        # the world's actors and their schedules
    off = tuple(a.spec['world_to_map'])
    rects = [zone_rect(a.spec, z) for z in lanes]
    out = []
    for band in crossing_bands(a.spec, lanes):
        rect = next(r for r in rects if band[0] >= r[0] - 1e-9 and band[1] <= r[1] + 1e-9)
        if rect[1] - rect[0] >= rect[3] - rect[2]:
            x = (band[0] + band[1]) / 2
            frm, to = (x, rect[2] - a.radius), (x, rect[3] + a.radius)
        else:
            y = (band[2] + band[3]) / 2
            frm, to = (rect[0] - a.radius, y), (rect[1] + a.radius, y)
        T = math.hypot(to[0] - frm[0], to[1] - frm[1]) / a.limits['auto_linear']
        n = int(math.ceil(T / a.dt))
        clear, best = 0, None
        for k in range(CROSSING_WINDOW_TICKS):
            worst = None
            for i in range(n + 1):
                f = min(1.0, i * a.dt / T)
                px, py = frm[0] + (to[0] - frm[0]) * f, frm[1] + (to[1] - frm[1]) * f
                t = k * a.dt + i * a.dt
                for ac in actors:
                    d = box_distance(px, py, ac, t, *off) - a.radius
                    worst = d if worst is None or d < worst else worst
            if worst is None or worst > 0:
                clear += 1
            best = worst if best is None or (worst is not None and worst > best) else best
        out.append({'band': list(band), 'from': list(frm), 'to': list(to), 'seconds': T,
                    'clear_starts': clear, 'of': CROSSING_WINDOW_TICKS,
                    'best_clearance_m': best, 'open': clear > 0})
    return out


def lane_side(xy, rect) -> int:
    """Which side of a lane zone ``xy`` is on, across the lane: -1 or +1."""
    if rect[1] - rect[0] >= rect[3] - rect[2]:
        return -1 if xy[1] < (rect[2] + rect[3]) / 2 else 1
    return -1 if xy[0] < (rect[0] + rect[1]) / 2 else 1


def on_band_centre(xy, band, rect) -> List[float]:
    """``xy`` moved along the lane onto the band's centre line (rounded to 1 mm)."""
    if rect[1] - rect[0] >= rect[3] - rect[2]:
        return [round((band[0] + band[1]) / 2, 3), round(xy[1], 3)]
    return [round(xy[0], 3), round((band[2] + band[3]) / 2, 3)]


def lane_grid(a: Arena, lanes=ROUND_LANES, bands=None):
    """
    The Arena's plan grid with every cell whose centre is in a round lane, but not on one of
    ``bands`` (default: every crossing band), blocked (a new grid; the Arena's own is untouched).
    """
    from .grid import Grid
    g, pm = a.grid, a.plan_map
    rects = [zone_rect(a.spec, z) for z in lanes]
    bands = crossing_bands(a.spec, lanes) if bands is None else bands
    blocked = list(g._blocked)
    for i in range(g.width * g.height):
        if blocked[i]:
            continue
        xy = pm.cell_centre(i // g.width, i % g.width)
        if any(_inside(xy, r) for r in rects) and not any(_inside(xy, b) for b in bands):
            blocked[i] = True
    return Grid(g.width, g.height, blocked, g._cost, connectivity=g.move_model.connectivity,
                diagonal_cost=g.move_model.diagonal_cost, corner_cutting=g.corner_cutting,
                cost_weight=g.cost_weight, cost_scale=g.cost_scale)


@_in_arena
def best_approach(a: Arena, assist: GraspAssist, oid: str, frm):
    """Return ``(pre_pose, length)``: the free pre-grasp pose nearest ``frm`` by plan."""
    best = None
    for p in assist.approach_poses(a, assist.objects[oid]):
        d = plan_length(a, frm, (p[0], p[1]))
        if d is not None and (best is None or d < best[1] - 1e-12):
            best = (p, d)
    return best


@_in_arena
def pickable(a: Arena, assist: GraspAssist) -> List[str]:
    """Return the objects Grasp Assist can pick somewhere on the level, sorted."""
    from .grasp_assist import static_check
    return [oid for oid in sorted(assist.objects)
            if not static_check(assist.objects[oid]) and assist.approach_poses(
                a, assist.objects[oid])]


# -- Fetch Rush ------------------------------------------------------------------------

class FetchRush:
    """
    Fetch Rush's rules: seeded orders, deliveries, the timer, the ghost, contacts.

    Orders come one at a time: an object Grasp Assist can pick and a drop zone,
    both drawn from the game's own seeded generator (``coco_lab.rng``), so every
    player of a link gets the same orders. An order is **delivered** when its
    object is put down inside its drop zone. Each order's planner ghost is the
    A* path from where the robot stood when the order appeared to the object's
    best pre-grasp pose, plus the A* path from there to the drop zone's centre;
    path efficiency is ghost length / distance driven. A contact is a tick the
    model refused the robot's motion (a wall or an actor), or the robot's circle
    overlapping an actor's box, counted once per episode.
    """

    def __init__(self, seed: int):
        """Make the game for ``seed``; orders are drawn when it starts."""
        self.seed = int(seed)
        self.orders: List[Tuple[str, str]] = []
        self.started = False
        self.seconds = FETCH_RUSH_SECONDS

    @_in_arena
    def start(self, a: Arena) -> None:
        """Draw the orders and start the clock (call after the setup inputs' tick)."""
        assist = a.subsystems['assist']
        pool = pickable(a, assist)
        drops = sorted(z['id'] for z in v3.zones(a.spec, 'drop'))
        rng = Rng(self.seed)
        order = list(pool)
        for i in range(len(order) - 1, 0, -1):          # Fisher-Yates, seeded
            j = rng.randrange(i + 1)
            order[i], order[j] = order[j], order[i]
        self.orders = [(oid, drops[rng.randrange(len(drops))]) for oid in order]
        self.t0 = a.t_world
        self.k = 0
        self.delivered: List[Dict[str, object]] = []
        self.contacts = 0
        self.contact_log: List[Dict[str, object]] = []
        self._was = False
        self._new_order(a)
        self.started = True
        self.over = False

    @_in_arena
    def _new_order(self, a: Arena) -> None:
        self.order_t0 = a.t_world
        self.driven = 0.0
        self.last = a.pose
        self.ghost = None
        if self.k < len(self.orders):
            oid, drop = self.orders[self.k]
            assist = a.subsystems['assist']
            ba = best_approach(a, assist, oid, a.pose[:2])
            r = zone_rect(a.spec, drop)
            centre = ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2)
            back = plan_length(a, ba[0][:2], centre) if ba else None
            self.ghost = ba[1] + back if ba and back is not None else None

    def current(self) -> Optional[Tuple[str, str]]:
        """Return the order being filled, or None when the game is over."""
        if not self.started or self.over or self.k >= len(self.orders):
            return None
        return self.orders[self.k]

    @_in_arena
    def observe(self, a: Arena, tick) -> None:
        """Score one tick (after the Arena stepped)."""
        if not self.started or self.over:
            return
        self.driven += math.hypot(a.pose[0] - self.last[0], a.pose[1] - self.last[1])
        self.last = a.pose
        actor = _actor_touch(a)
        touching = bool(tick.contact) or actor
        if touching and not self._was:
            self.contacts += 1
            self.contact_log.append({'t': a.t_world - self.t0, 'x': a.pose[0], 'y': a.pose[1],
                                     'actor': actor or _actor_near(a)})
        self._was = touching
        cur = self.current()
        if cur is not None:
            oid, drop = cur
            o = a.subsystems['assist'].objects[oid]
            if o['status'] == 'placed' and _inside((o['x'], o['y']), zone_rect(a.spec, drop)):
                self.delivered.append({'object': oid, 'drop': drop,
                                       't': a.t_world - self.t0,
                                       'seconds': a.t_world - self.order_t0,
                                       'driven': self.driven, 'ghost': self.ghost})
                self.k += 1
                self._new_order(a)
        if a.t_world - self.t0 >= self.seconds - 1e-9 or self.k >= len(self.orders):
            self.over = True

    def scorecard(self) -> Dict[str, object]:
        """Return the real metrics, and the ranking key (net deliveries first)."""
        eff = [d['ghost'] / d['driven'] for d in self.delivered
               if d['ghost'] is not None and d['driven'] > 0]
        used = self.delivered[-1]['t'] if self.delivered else self.seconds
        n = len(self.delivered)
        return {'game': 'fetch_rush', 'seed': self.seed, 'deliveries': n,
                'contacts': self.contacts, 'net_deliveries': n - self.contacts,
                'time_used': used, 'path_efficiency': sum(eff) / len(eff) if eff else 0.0,
                'orders': [list(o) for o in self.orders[:max(n + 1, 1)]],
                'delivered': self.delivered, 'contact_log': self.contact_log}


def fetch_rush_key(card) -> Tuple:
    """Return the ranking key: net deliveries (contacts subtract), then time, then efficiency."""
    return (card['net_deliveries'], -card['time_used'], card['path_efficiency'])


# -- Fetch Rush rules 2: budgeted rounds (G1.11) ----------------------------------------

def rounds_file(level: str = 'coco_depot_v1', rules: int = 2) -> Path:
    """Rules 2's ``<level>.fetch_rush.json``; rules 3's (and 4's) ``<level>.fetch_rush.r<N>.json``."""
    return LEVELS / (f'{level}.fetch_rush.json' if rules == 2 else f'{level}.fetch_rush.r{rules}.json')


def round_modes(rules: int) -> Dict[str, Dict[str, float]]:
    """The modes (orders, budget) of rules 3 or 4."""
    return ROUND_MODES_R4 if rules >= 4 else ROUND_MODES


def load_rounds(level: str = 'coco_depot_v1', rules: int = 2) -> Dict[str, object]:
    """Return a level's Fetch Rush rounds for ``rules`` (2, 3 or 4)."""
    with open(rounds_file(level, rules), encoding='utf-8') as f:
        return json.load(f)


def _completes(trips, pos: str, used, left: int, budget: float) -> bool:
    """Whether ``left`` more orders can follow from ``pos`` within the budget."""
    if left == 0:
        return True
    return any(length <= budget and _completes(trips, drop, used | {oid}, left - 1, budget)
               for oid, ds in sorted(trips[pos].items()) if oid not in used
               for drop, length in sorted(ds.items()))


def draw_round(seed: int, trips, budget: float = ROUND_BUDGET_M,
               n: int = ROUND_ORDERS, attempt: int = 0) -> Dict[str, object]:
    """
    Draw a round from the planned-trip table, seeded (``coco_lab.rng``).

    ``trips[frm][oid][drop]`` is the planned round trip (m) from ``frm`` (a start
    zone, or the drop zone the previous order ended at) to ``oid``'s best pre-grasp
    pose and on to ``drop``'s centre. The start zone is drawn among those from
    which ``n`` orders can be chained within ``budget``; each order is drawn among
    the unused objects and drops whose trip fits and from which the rest of the
    round still can. Pure: the same seed and table give the same round. ``attempt``
    (rules 3) draws again for a seed whose earlier draw was rejected.
    """
    rng = Rng(int(seed) if attempt == 0 else int(seed) * 1000003 + int(attempt))
    starts = sorted(f for f in trips if f.startswith('zone_') and f not in ROUND_NO_START
                    and _completes(trips, f, frozenset(), n, budget))
    if not starts:
        raise ArenaError('no start zone allows a round within the budget')
    region = starts[rng.randrange(len(starts))]
    pos, used, orders = region, frozenset(), []
    for k in range(n):
        cands = [(oid, drop) for oid, ds in sorted(trips[pos].items()) if oid not in used
                 for drop, length in sorted(ds.items())
                 if length <= budget
                 and _completes(trips, drop, used | {oid}, n - k - 1, budget)]
        oid, drop = cands[rng.randrange(len(cands))]
        orders.append([oid, drop])
        used, pos = used | {oid}, drop
    return {'region': region, 'orders': orders}


class FetchRushRound(FetchRush):
    """
    Fetch Rush rules 2: one precomputed round (``levels/<level>.fetch_rush.json``).

    The orders, each order's planner ghost (the planned round trip the round was
    drawn with) and the timer come from the round; nothing is planned while the
    game runs, so a tick never waits for a search. Deliveries, contacts, the
    ranking and path efficiency (ghost / distance driven) are rules 1's.
    """

    def __init__(self, seed: int, rnd: Dict[str, object], seconds: Optional[float] = None,
                 rules: int = 2, mode: Optional[str] = None):
        """``seconds`` overrides the round's timer (the reference bot's first run only)."""
        super().__init__(seed)
        self.round = rnd
        self.rules = rules
        self.mode = mode if rules >= 3 else None
        self.seconds = float(seconds if seconds is not None else rnd['timer_s'])

    @_in_arena
    def start(self, a: Arena) -> None:
        """Take the round's orders and start the clock."""
        self.orders = [tuple(o) for o in self.round['orders']]
        self.t0 = a.t_world
        self.k = 0
        self.delivered = []
        self.contacts = 0
        self.contact_log = []
        self._was = False
        self._new_order(a)
        self.started = True
        self.over = False

    @_in_arena
    def _new_order(self, a: Arena) -> None:
        self.order_t0 = a.t_world
        self.driven = 0.0
        self.last = a.pose
        ghosts = self.round['ghost_m']
        self.ghost = ghosts[self.k] if self.k < len(ghosts) else None

    def scorecard(self) -> Dict[str, object]:
        """Rules 1's scorecard, plus the rules version, the round and its timer."""
        card = dict(super().scorecard(), rules=self.rules,
                    round=self.round['region'], timer=self.seconds)
        if self.mode is not None:
            card['mode'] = self.mode
        return card


# -- Rush Hour -------------------------------------------------------------------------

class RushHour:
    """
    Rush Hour's rules: carry a canister across the forklift lanes.

    The objective (:data:`RUSH_HOUR`) names the canister, the drop zone and the
    start. Metrics: delivered, the time from the start to delivery, the minimum
    clearance between the robot's circle and any actor's box over the run,
    contacts (as Fetch Rush counts them), and the **fragile cargo rule**: the
    RMS and peak jerk of the robot's commanded linear motion while the canister
    is carried, ``j = (a_k - a_{k-1}) / dt`` with ``a_k = (v_k - v_{k-1}) / dt``.
    A game rule about driving smoothly, not physics: nothing breaks in the model.
    The driving assist in use is on the scorecard.
    """

    def __init__(self, objective: str):
        """Make the game for one objective."""
        if objective not in RUSH_HOUR:
            raise ArenaError(f'rush hour: no objective {objective!r}')
        self.objective = objective
        self.started = False

    @_in_arena
    def start(self, a: Arena) -> None:
        """Start the clock."""
        self.t0 = a.t_world
        self.done = False
        self.time = None
        self.min_clearance = math.inf
        self.contacts = 0
        self.contact_log: List[Dict[str, object]] = []
        self._was = False
        self.vs: List[float] = []
        self.jerks: List[float] = []
        self.started = True
        self.over = False

    @_in_arena
    def observe(self, a: Arena, tick) -> None:
        """Score one tick."""
        if not self.started or self.over:
            return
        ob = RUSH_HOUR[self.objective]
        actors = a.subsystems['actors']
        c = actors.clearance(a.pose[0], a.pose[1], a.radius)
        self.min_clearance = min(self.min_clearance, c)
        touching = bool(tick.contact) or c <= 0.0
        if touching and not self._was:
            self.contacts += 1
            self.contact_log.append({'t': a.t_world - self.t0, 'x': a.pose[0], 'y': a.pose[1],
                                     'actor': c <= 0.0 or _actor_near(a)})
        self._was = touching
        assist = a.subsystems['assist']
        if assist.carried() == ob['object']:
            self.vs.append(a.v)
            if len(self.vs) >= 3:
                v0, v1, v2 = self.vs[-3:]
                self.jerks.append(((v2 - v1) - (v1 - v0)) / (a.dt * a.dt))
        else:
            self.vs = []
        o = assist.objects[ob['object']]
        if o['status'] == 'placed' and _inside((o['x'], o['y']), zone_rect(a.spec, ob['drop'])):
            self.done, self.time, self.over = True, a.t_world - self.t0, True

    def scorecard(self, assist_name: str = 'builtin') -> Dict[str, object]:
        """Return the real metrics."""
        j = self.jerks
        return {'game': 'rush_hour', 'objective': self.objective, 'delivered': self.done,
                'time': self.time, 'min_clearance': self.min_clearance,
                'contacts': self.contacts,
                'jerk_rms': math.sqrt(sum(x * x for x in j) / len(j)) if j else 0.0,
                'jerk_peak': max((abs(x) for x in j), default=0.0),
                'assist': assist_name, 'fragile_cargo': 'game rule, not physics',
                'contact_log': self.contact_log}


@_in_arena
def _actor_near(a: Arena) -> bool:
    # a refused motion next to an actor's covering discs (the model's actor body)
    act = a.subsystems.get('actors')
    return act is not None and any(
        math.hypot(a.pose[0] - x, a.pose[1] - y) < a.radius + r + 0.05
        for x, y, r in act.discs())


@_in_arena
def _actor_touch(a: Arena) -> bool:
    act = a.subsystems.get('actors')
    return act is not None and act.clearance(a.pose[0], a.pose[1], a.radius) <= 0.0


# -- stars: from the reference, never hand-picked ----------------------------------------

def stars(card: Dict[str, object], reference: Dict[str, object]) -> int:
    """
    Return 0-3 stars for ``card`` against the reference bot's card (same level, seed).

    Fetch Rush: 1 for a delivery; 2 for as many net deliveries as the reference;
    3 for ranking at or above it (:func:`fetch_rush_key`). Rush Hour: 1 for the
    delivery; 2 for delivering with no contact no slower than the reference; 3
    for also keeping at least its clearance and at most its RMS jerk.
    """
    if card['game'] == 'fetch_rush':
        if card['deliveries'] < 1:
            return 0
        if card['net_deliveries'] < reference['net_deliveries']:
            return 1
        return 3 if fetch_rush_key(card) >= fetch_rush_key(reference) else 2
    if not card['delivered']:
        return 0
    if card['contacts'] or reference['time'] is None or card['time'] > reference['time']:
        return 1
    if card['min_clearance'] >= reference['min_clearance'] and \
            card['jerk_rms'] <= reference['jerk_rms']:
        return 3
    return 2


# -- playing a record ------------------------------------------------------------------------

def setup_inputs(game: str, arg, rules: int = 1, rnd=None,
                 mode: Optional[str] = None) -> List[Dict[str, object]]:
    """Return the tick-0 inputs every session of ``game`` starts with (in its log)."""
    out = [{'tick': 0, 'kind': 'config', 'choice': 'actors.on=1'},
           {'tick': 0, 'kind': 'config', 'choice': 'assist.target=any'}]
    start = None
    if game == 'rush_hour':
        start = RUSH_HOUR[arg]['start']
    elif game == 'fetch_rush' and rules >= 2:
        start = (rnd or round_for(arg, rules=rules, mode=mode))['start']   # the round's start
    if start is not None:
        x, y, th = start
        out.insert(0, {'tick': 0, 'kind': 'kidnap', 'x': x, 'y': y, 'theta': th,
                       'has_theta': True})
    return out


def round_for(seed, level: str = 'coco_depot_v1', rules: int = 2,
              mode: Optional[str] = None) -> Dict[str, object]:
    """Return the precomputed round for ``seed`` (rules 2, or rules 3 / 4 in ``mode``), or raise."""
    if rules >= 3:
        mode = mode or ROUND_MODE_DEFAULT
        modes = round_modes(rules)
        if mode not in modes:
            raise ArenaError(f'Fetch Rush modes are {sorted(modes)}, not {mode!r}')
        rounds = load_rounds(level, rules)['rounds'][mode]
        rnd = rounds.get(str(int(seed)))
        if rnd is None:
            raise ArenaError(f'Fetch Rush ({mode}) has rounds for seeds '
                             f'{sorted(int(k) for k in rounds)}, not {seed!r}')
        return rnd
    rounds = load_rounds(level)['rounds']
    playable = sorted(int(k) for k, r in rounds.items() if r.get('timer_s') is not None)
    rnd = rounds.get(str(int(seed)))
    if rnd is None:
        raise ArenaError(f'Fetch Rush has rounds for seeds {playable}, not {seed!r}')
    if rnd.get('timer_s') is None:
        # no reference time, so no timer (the decision): kept on file, never played
        raise ArenaError(f'seed {seed}: the reference bot did not complete this round, so it '
                         f'has no timer; playable seeds: {playable}')
    return rnd


def _rules(game: str, arg, rules: int = 1, mode: Optional[str] = None):
    if game == 'fetch_rush':
        if rules >= 2:
            mode = (mode or ROUND_MODE_DEFAULT) if rules >= 3 else None
            return FetchRushRound(int(arg), round_for(arg, rules=rules, mode=mode),
                                  rules=rules, mode=mode)
        return FetchRush(int(arg))
    if game == 'rush_hour':
        return RushHour(str(arg))
    raise ArenaError(f'unknown game {game!r}')


def play(spec, record: Dict[str, object]) -> Dict[str, object]:
    """
    Replay a game record; return the scorecard and the state-hash chain.

    A record is ``{game, arg (seed or objective), seed (the Arena's), ticks, inputs}``.
    """
    a = Arena(spec, record['seed'], hash_version=record.get('hash_version', 1))
    by: Dict[int, list] = {}
    for e in record['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    rules = _rules(record['game'], record['arg'], record.get('rules', 1), record.get('mode'))
    chain = hashlib.sha256()
    last = ''
    for _ in range(record['ticks']):
        t = a.step(by.get(a.tick, ()))
        if not rules.started:
            rules.start(a)
        rules.observe(a, t)
        last = t.state_hash
        chain.update(last.encode())
    return {'scorecard': _card(rules, a), 'hash_chain': chain.hexdigest(), 'last_hash': last}


def _card(rules, a):
    if isinstance(rules, RushHour):
        mv = a.subsystems.get('move')
        return rules.scorecard(mv.controller if mv is not None else 'builtin')
    return rules.scorecard()


def verify(spec, record: Dict[str, object], claimed: Dict[str, object]) -> bool:
    """
    Return whether a record reproduces its claimed result, within M5's link limits.

    The inputs are validated as a link's are (``coco_lab.link_bounds``) before any
    Arena is built; then the game is replayed and every number compared.
    """
    validate_log(record['inputs'])
    if record['ticks'] > 11930 or record['game'] not in GAMES:
        raise ValueError('a game record must name a game and stay within the link tick limit')
    got = play(spec, record)
    return got == claimed


# -- the reference bots ------------------------------------------------------------------------

class _Driver:
    """Step an Arena, recording every input sent (the bot's own log)."""

    def __init__(self, spec, seed, game, arg, rules=None, version: int = 1,
                 hash_version: int = 1):
        self.a = Arena(spec, seed, hash_version=hash_version)
        self.inputs: List[Dict[str, object]] = []
        self.rules = rules if rules is not None else _rules(game, arg)
        self.version = version
        self.hash_version = hash_version
        self.ticks = 0
        self.chain = hashlib.sha256()
        self.step(setup_inputs(game, arg, version, getattr(self.rules, 'round', None)))

    @numerics.in_run
    def step(self, inputs=()) -> object:
        evs = []
        for e in inputs:
            e = dict(e, tick=self.a.tick)
            self.inputs.append(e)
            evs.append(InputEvent(**e))
        t = self.a.step(evs)
        if not self.rules.started:
            self.rules.start(self.a)
        self.rules.observe(self.a, t)
        self.ticks += 1
        self.chain.update(t.state_hash.encode())
        self.last = t.state_hash
        return t

    @numerics.in_run
    def goal(self, xy, limit: int, yield_to_actors: bool = False) -> bool:
        """Drive to ``xy``; yielding, STOP when the path ahead meets an actor, then re-plan."""
        a = self.a
        t = self.step([{'kind': 'goal', 'x': xy[0], 'y': xy[1]}])
        waiting = 0
        for _ in range(limit):
            if self.done():
                break
            if waiting:
                waiting += 1
                if waiting > YIELD_TICKS or not _conflict(a, _path_points(a, xy)):
                    waiting = 0
                    t = self.step([{'kind': 'goal', 'x': xy[0], 'y': xy[1]}])
                else:
                    t = self.step()
                continue
            if a.mode != 'goal':
                break                           # arrived, or no path
            if yield_to_actors and _conflict(
                    a, [a.pose[:2]] + [tuple(w) for w in a.waypoints[a.wp_index:]]):
                waiting = 1
                t = self.step([{'kind': 'stop'}])
                continue
            t = self.step()
        return math.hypot(a.pose[0] - xy[0], a.pose[1] - xy[1]) <= WAYPOINT_TOL + 1e-9 \
            or t.arrived

    @numerics.in_run
    def until(self, cond, limit: int) -> bool:
        for _ in range(limit):
            if cond():
                return True
            if self.done():
                return False
            self.step()
        return cond()

    def done(self) -> bool:
        return getattr(self.rules, 'over', False)

    def record(self, game, arg, seed):
        rec = {'game': game, 'arg': arg, 'seed': seed, 'ticks': self.ticks,
               'inputs': self.inputs}
        if self.version != 1:
            rec['rules'] = self.version
        if self.hash_version != 1:
            rec['hash_version'] = self.hash_version
        if getattr(self.rules, 'mode', None) is not None:
            rec['mode'] = self.rules.mode
        return rec


def bot_fetch_rush(spec, seed: int, arena_seed: int = 1, rules=None,
                   hash_version: int = 1) -> Tuple[Dict, Dict]:
    """
    Play Fetch Rush as the reference player: the planner plus Grasp Assist.

    For each order: drive (A* + the waypoint follower) to the object's best
    pre-grasp pose, press G for that object, drive to the drop zone's centre,
    press G to put it down. Returns ``(record, result)``; :func:`play` on the
    record gives the result again.
    """
    version = rules.rules if isinstance(rules, FetchRushRound) else 1
    d = _Driver(spec, arena_seed, 'fetch_rush', seed, rules, version, hash_version)
    a, rules = d.a, d.rules
    assist = a.subsystems['assist']
    # G2.1, rules 4: the round names each order's pre-grasp pose and its legs' crossing mouths
    # (the routes it was drawn with keep the crossing rule); the bot drives through those
    planned = version >= 4 and 'pick' in rules.round
    while not d.done():
        cur = rules.current()
        if cur is None:
            break
        oid, drop = cur
        k = rules.k
        if planned:
            for xy in rules.round['via'][k][0]:
                d.goal(xy, 3000, yield_to_actors=True)
            ba = (rules.round['pick'][k], None)
        else:
            ba = best_approach(a, assist, oid, a.pose[:2])
        if ba is None or not d.goal(ba[0][:2], 3000, yield_to_actors=True):
            d.until(lambda: False, 10)
            if d.done():
                break
            continue
        if d.done():
            break
        d.step([{'kind': 'config', 'choice': f'assist.target={oid}'},
                {'kind': 'config', 'choice': 'assist.grasp=go'}])
        if not d.until(lambda: assist.carried() == oid or assist.phase == 'idle', 2000) \
                or assist.carried() != oid:
            continue
        if planned:
            for xy in rules.round['via'][k][1]:
                d.goal(xy, 3000, yield_to_actors=True)
        r = zone_rect(a.spec, drop)
        d.goal(((r[0] + r[1]) / 2, (r[2] + r[3]) / 2), 4000, yield_to_actors=True)
        if d.done():
            break
        d.step([{'kind': 'config', 'choice': 'assist.grasp=go'}])
        d.until(lambda: assist.phase == 'idle', 200)
    rec = d.record('fetch_rush', seed, arena_seed)
    return rec, {'scorecard': _card(rules, a), 'hash_chain': d.chain.hexdigest(),
                 'last_hash': d.last}


def bot_rush_hour(spec, objective: str, arena_seed: int = 1) -> Tuple[Dict, Dict]:
    """
    Play Rush Hour as the reference player: pick, then cross when the lanes are clear.

    It picks the canister with Grasp Assist, drives to the staging point beside
    the lanes, and waits for the earliest start at which its straight crossing,
    predicted at the auto speed from the actors' known schedule, keeps at least a
    robot diameter (2 x radius) from every actor's box; then it crosses and
    delivers. Returns ``(record, result)``.
    """
    d = _Driver(spec, arena_seed, 'rush_hour', objective)
    a, ob = d.a, RUSH_HOUR[objective]
    assist = a.subsystems['assist']
    dx, dy = a.spec['world_to_map']
    d.step([{'kind': 'config', 'choice': f'assist.target={ob["object"]}'},
            {'kind': 'config', 'choice': 'assist.grasp=go'}])
    d.until(lambda: assist.carried() == ob['object'] or assist.phase == 'idle', 2000)
    stage = (ob['staging'][0] + dx, ob['staging'][1] + dy)
    across = (ob['across'][0] + dx, ob['across'][1] + dy)
    d.goal(stage, 4000)
    wait = _crossing_delay(a, stage, across)
    for _ in range(wait):
        d.step()
    d.goal(across, 3000)
    r = zone_rect(a.spec, ob['drop'])
    d.goal(((r[0] + r[1]) / 2, (r[2] + r[3]) / 2), 4000)
    d.step([{'kind': 'config', 'choice': 'assist.grasp=go'}])
    d.until(lambda: d.done(), 200)
    rec = d.record('rush_hour', objective, arena_seed)
    return rec, {'scorecard': _card(d.rules, a), 'hash_chain': d.chain.hexdigest(),
                 'last_hash': d.last}


#: the reference bots' look-ahead (s) and the longest they wait for a clear path (ticks)
YIELD_HORIZON = 4.0
YIELD_TICKS = 600


@_in_arena
def _path_points(a: Arena, xy) -> List[Tuple[float, float]]:
    """Return the path the Arena's planner would drive to ``xy`` from the robot, as points."""
    g = a.grid
    sc, gc = a.plan_map.cell_at(a.pose[0], a.pose[1]), a.plan_map.cell_at(*xy)
    if sc is None or gc is None:
        return [a.pose[:2]]
    s, t = _nearest_free(g, sc), _nearest_free(g, gc)
    if s is None or t is None:
        return [a.pose[:2]]
    r = search(g, s, t, **PLANNERS[a.planner])
    return [a.pose[:2]] + [a.plan_map.cell_centre(*c) for c in r.path[1:]] if r.found \
        else [a.pose[:2]]


@_in_arena
def _conflict(a: Arena, pts, horizon: float = YIELD_HORIZON) -> bool:
    """Return whether driving ``pts`` at the auto speed meets an actor within 2 x radius."""
    act = a.subsystems.get('actors')
    if act is None:
        return False
    speed, margin = a.limits['auto_linear'], 2 * a.radius
    pos, i, k = pts[0], 1, 0
    while k * a.dt <= horizon + 1e-9:
        t = a.t_world + k * a.dt
        if any(box_distance(pos[0], pos[1], ac, t, *act.offset) - a.radius < margin
               for ac in act.actors):
            return True
        step = speed * a.dt
        while i < len(pts) and step > 0:
            d = math.hypot(pts[i][0] - pos[0], pts[i][1] - pos[1])
            if d <= step:
                pos, step, i = pts[i], step - d, i + 1
            else:
                f = step / d
                pos, step = (pos[0] + (pts[i][0] - pos[0]) * f,
                             pos[1] + (pts[i][1] - pos[1]) * f), 0.0
        k += 1
    return False


@_in_arena
def _crossing_delay(a: Arena, frm, to, horizon_ticks: int = 1200) -> int:
    """Return the ticks to wait so a straight crossing keeps 2 x radius from every actor."""
    actors = a.subsystems['actors']
    dist = math.hypot(to[0] - frm[0], to[1] - frm[1])
    speed = a.limits['auto_linear']
    # turn to face the crossing first (at the auto turn rate), then drive it
    turn = abs(math.atan2(math.sin(math.atan2(to[1] - frm[1], to[0] - frm[0]) - a.pose[2]),
                          math.cos(math.atan2(to[1] - frm[1], to[0] - frm[0]) - a.pose[2])))
    t_turn = turn / a.limits['auto_angular']
    t_cross = dist / speed
    margin = 2 * a.radius
    off = actors.offset
    for k in range(horizon_ticks):
        t0 = a.t_world + k * a.dt + t_turn
        ok = True
        n = int(math.ceil(t_cross / a.dt)) + 1
        for i in range(n + 1):
            f = min(1.0, i * a.dt / t_cross)
            x, y = frm[0] + (to[0] - frm[0]) * f, frm[1] + (to[1] - frm[1]) * f
            t = t0 + i * a.dt
            if any(box_distance(x, y, ac, t, *off) - a.radius < margin for ac in actors.actors):
                ok = False
                break
        if ok:
            return k
    return horizon_ticks
