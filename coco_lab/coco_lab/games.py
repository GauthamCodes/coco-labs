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

import hashlib
import struct
from typing import Dict, List, Optional, Tuple

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


def best_approach(a: Arena, assist: GraspAssist, oid: str, frm):
    """Return ``(pre_pose, length)``: the free pre-grasp pose nearest ``frm`` by plan."""
    best = None
    for p in assist.approach_poses(a, assist.objects[oid]):
        d = plan_length(a, frm, (p[0], p[1]))
        if d is not None and (best is None or d < best[1] - 1e-12):
            best = (p, d)
    return best


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
        if a.t_world - self.t0 >= FETCH_RUSH_SECONDS - 1e-9 or self.k >= len(self.orders):
            self.over = True

    def scorecard(self) -> Dict[str, object]:
        """Return the real metrics, and the ranking key (net deliveries first)."""
        eff = [d['ghost'] / d['driven'] for d in self.delivered
               if d['ghost'] is not None and d['driven'] > 0]
        used = self.delivered[-1]['t'] if self.delivered else FETCH_RUSH_SECONDS
        n = len(self.delivered)
        return {'game': 'fetch_rush', 'seed': self.seed, 'deliveries': n,
                'contacts': self.contacts, 'net_deliveries': n - self.contacts,
                'time_used': used, 'path_efficiency': sum(eff) / len(eff) if eff else 0.0,
                'orders': [list(o) for o in self.orders[:max(n + 1, 1)]],
                'delivered': self.delivered, 'contact_log': self.contact_log}


def fetch_rush_key(card) -> Tuple:
    """Return the ranking key: net deliveries (contacts subtract), then time, then efficiency."""
    return (card['net_deliveries'], -card['time_used'], card['path_efficiency'])


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


def _actor_near(a: Arena) -> bool:
    # a refused motion next to an actor's covering discs (the model's actor body)
    act = a.subsystems.get('actors')
    return act is not None and any(
        math.hypot(a.pose[0] - x, a.pose[1] - y) < a.radius + r + 0.05
        for x, y, r in act.discs())


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

def setup_inputs(game: str, arg) -> List[Dict[str, object]]:
    """Return the tick-0 inputs every session of ``game`` starts with (in its log)."""
    out = [{'tick': 0, 'kind': 'config', 'choice': 'actors.on=1'},
           {'tick': 0, 'kind': 'config', 'choice': 'assist.target=any'}]
    if game == 'rush_hour':
        x, y, th = RUSH_HOUR[arg]['start']
        out.insert(0, {'tick': 0, 'kind': 'kidnap', 'x': x, 'y': y, 'theta': th,
                       'has_theta': True})
    return out


def _rules(game: str, arg):
    if game == 'fetch_rush':
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
    rules = _rules(record['game'], record['arg'])
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

    def __init__(self, spec, seed, game, arg):
        self.a = Arena(spec, seed)
        self.inputs: List[Dict[str, object]] = []
        self.rules = _rules(game, arg)
        self.ticks = 0
        self.chain = hashlib.sha256()
        self.step(setup_inputs(game, arg))

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
        return {'game': game, 'arg': arg, 'seed': seed, 'ticks': self.ticks,
                'inputs': self.inputs}


def bot_fetch_rush(spec, seed: int, arena_seed: int = 1) -> Tuple[Dict, Dict]:
    """
    Play Fetch Rush as the reference player: the planner plus Grasp Assist.

    For each order: drive (A* + the waypoint follower) to the object's best
    pre-grasp pose, press G for that object, drive to the drop zone's centre,
    press G to put it down. Returns ``(record, result)``; :func:`play` on the
    record gives the result again.
    """
    d = _Driver(spec, arena_seed, 'fetch_rush', seed)
    a, rules = d.a, d.rules
    assist = a.subsystems['assist']
    while not d.done():
        cur = rules.current()
        if cur is None:
            break
        oid, drop = cur
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
