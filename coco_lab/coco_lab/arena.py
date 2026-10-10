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
The Arena model (README section 5.1, tier 1): a deterministic 2D world.

**The Arena is a MODEL, not the robot.** It is Sketch's world, run as a
fixed-step simulator beside the planners, inside a Web Worker. What it
leaves out is Sketch's list (``coco_lab.sketch``): the world is the 2D
occupancy map generated from the World Spec (``coco_lab.worldspec``);
wheels never slip; the robot's belief IS its true pose (no localisation in
M1, so ``robot.state`` and ``truth.pose`` carry the same numbers, honestly
labelled); a step whose end would bring the robot's centre within
``radius / 2`` of an obstacle is refused, as in Sketch.

**Deterministic by construction** (README section 5.1):

- fixed time step ``spec.arena.dt`` (0.1 s for COCO: Nav2's 10 Hz);
- one single-threaded loop, :meth:`Arena.step`;
- every random number from :class:`coco_lab.rng.Rng`, seeded once;
- goals, teleop, STOP, planner choice and reset arrive only as
  :class:`InputEvent` rows, each applied at the START of its ``tick``;
- a per-tick state hash over a canonical, quantized byte layout
  (:meth:`Arena.state_bytes`, ``docs/v2/ARENA_MODEL.md``).

The same spec, seed and input log give the same hashes, tick for tick.

**The whole loop (M2).** Two more input kinds turn it on: ``kidnap`` (the
robot is carried; odometry is not told) and ``config`` (``key=value``:
``arena.slip=on``, ``localise.filter=mcl``, ...). From the first of them
the Arena keeps wheel odometry (the motion model's noise, Sketch's
``sample_delta``), an optional labelled wheel-slip model (the truth turns
less than the wheels report, Lab 2's measured turn divergence), and the
subsystems a ``config`` names -- each registered in :data:`SUBSYSTEMS` by
its own pack (``coco_lab.loc_arena`` for ``localise``). Planning and
driving then use the robot's BELIEF (a localiser's estimate when there is
one), never the truth. Loop inputs apply first in their tick and are
committed at once; an amendment cannot carry one. Until the first loop
input the state, and so every hash, is exactly M1's.

**Planning happens once per tick, after all of the tick's inputs** (M2.0):
a goal, a planner change or both in one tick give one search, on the state
the inputs leave. A step can run in slices -- :meth:`Arena.begin_step`,
:meth:`Arena.advance`, :meth:`Arena.finish_step` -- and an input that
arrives while a slice-run step is still planning joins that tick through
:meth:`Arena.amend`, which cancels the search in flight and starts the one
the amended inputs call for. The result depends only on the tick's final
input list, so :meth:`Arena.step` (all in one go) gives the same state and
hashes; M1's hash layout is unchanged (a search's id is not state).
"""

from dataclasses import dataclass, field
import hashlib
import math
import struct
from typing import Dict, List, Optional, Sequence, Tuple

from .events import SearchEventColumns
from .maps import OCCUPIED
from .rng import Rng
from .search import Collector, search_events, SearchResult
from .sketch import (_inflated_grid_map, _nearest_free, apply_delta,
                     drive_command, LidarSpec, odom_delta, sample_delta,
                     SketchMap, step_pose, wrap)
from .worldspec import arena_map, normalize, to_map_frame

#: The state-hash layout's name; a change to the layout changes this.
STATE_LAYOUT = b'coco.arena.state.v1\x00'
INPUT_KINDS = ('goal', 'teleop', 'stop', 'planner', 'reset', 'kidnap',
               'config')
#: Inputs that switch on or drive the whole loop (M2); applied first
LOOP_KINDS = ('kidnap', 'config')
#: The whole loop's subsystems, registered by their packs on import
#: (name -> class taking the Arena): never imported by this module
SUBSYSTEMS: Dict[str, type] = {}
LOOP_LAYOUT = b'coco.arena.loop.v1\x00'
#: The wheel-slip option (M2.3, off by default; labelled wherever shown):
#: in turns the truth rotates this fraction of what the wheels report.
#: COCO's skid-steer wheel odometry integrated 72.5 rad of yaw on the
#: recorded tour where the gyro and the truth gave 56.3 / 56.2 rad
#: (docs/labs/LAB2_LOCALISE.md section 4.1; STACK), so 56.2 / 72.5.
SLIP_TURN = 56.2 / 72.5
#: Sketch's default odometry noise (coco_lab.sketch.Noise)
ODOM_ALPHAS = (0.02, 0.02, 0.02, 0.02)
MODES = ('idle', 'teleop', 'goal')
#: The planners a learner can choose, and how each is run on the grid.
PLANNERS: Dict[str, Dict[str, object]] = {
    'bfs': {'algorithm': 'bfs'},
    'dijkstra': {'algorithm': 'dijkstra'},
    'astar': {'algorithm': 'astar', 'heuristic': 'octile'},
    'greedy': {'algorithm': 'greedy', 'heuristic': 'octile'},
    'weighted_astar': {'algorithm': 'weighted_astar', 'heuristic': 'octile',
                       'weight': 2.0},
}
PLANNER_IDS = tuple(PLANNERS)
#: Quantization of the hash layout: 1 micrometre / microradian for the
#: pose and velocities, 0.1 mm for ranges.
Q_STATE = 1e6
Q_RANGE = 1e4
NO_RETURN = 0xFFFFFFFF


class ArenaError(ValueError):
    """An input the Arena cannot honour."""


@dataclass(frozen=True)
class InputEvent:
    """One input, applied at the start of ``tick`` (coco.input.events.v1)."""

    tick: int
    kind: str
    x: float = 0.0          # goal, map frame
    y: float = 0.0
    theta: float = 0.0
    has_theta: bool = False
    linear: float = 0.0     # teleop, m/s
    angular: float = 0.0    # teleop, rad/s
    choice: str = ''        # planner name

    def __post_init__(self):
        """Refuse what cannot be an input."""
        if self.kind not in INPUT_KINDS:
            raise ArenaError(f'unknown input kind {self.kind!r}')
        if isinstance(self.tick, bool) or not isinstance(self.tick, int) \
                or self.tick < 0:
            raise ArenaError(f'tick must be an int >= 0, got {self.tick!r}')
        for name in ('x', 'y', 'theta', 'linear', 'angular'):
            if not math.isfinite(getattr(self, name)):
                raise ArenaError(f'{name} must be finite')
        if self.kind == 'config' and '=' not in self.choice:
            raise ArenaError(f'config must be key=value, got {self.choice!r}')


@dataclass
class Plan:
    """One planning call: the search (with its trace) and the route."""

    planner: str
    goal: Tuple[float, float]
    result: SearchResult
    waypoints: List[Tuple[float, float]]
    tick: int


@dataclass
class Tick:
    """What one step produced (the state AFTER it)."""

    tick: int
    t_world: float
    pose: Tuple[float, float, float]
    v: float
    w: float
    mode: str
    ranges: List[float]
    plans: List[Plan] = field(default_factory=list)
    inputs: List[InputEvent] = field(default_factory=list)
    blocked: bool = False
    arrived: bool = False
    state_hash: str = ''
    #: the whole loop's belief (None until the loop is on: then truth is it)
    belief: Optional[Tuple[float, float, float]] = None
    #: moving bodies in the world, (x, y, radius) (M2.5: the Move pack's actors)
    actors: List[Tuple[float, float, float]] = field(default_factory=list)


def _q(v: float, scale: float) -> int:
    """Quantize to an int64 (round half to even, Python's round)."""
    return round(v * scale)


class Arena:
    """A deterministic Arena run: one world, one seed, one input log."""

    def __init__(self, spec: Dict[str, object], seed: int,
                 planner: str = 'astar', range_sigma: float = 0.0,
                 lidar_every: int = 1, on_plan_batch=None,
                 plan_batch_size: int = 2048, on_family=None):
        """Build the world from ``spec`` and place the robot at its start."""
        self.spec = normalize(spec)
        if planner not in PLANNERS:
            raise ArenaError(f'unknown planner {planner!r}')
        if not (math.isfinite(range_sigma) and range_sigma >= 0):
            raise ArenaError(f'range_sigma must be >= 0, got {range_sigma!r}')
        self.lab_map = arena_map(self.spec)
        self.smap = SketchMap(self.lab_map)
        rb = self.spec['robot']
        li = rb['lidar']
        lidar = LidarSpec(li['samples'], li['angle_min'], li['angle_max'],
                          li['range_min'], li['range_max'],
                          (li['mount'][0], li['mount'][1], 0.0))
        self.lidar = lidar.decimated(lidar_every) if lidar_every > 1 else lidar
        self.angles = self.lidar.angles()
        self.radius = rb['radius']
        self.limits = rb['limits']
        self.dt = self.spec['arena']['dt']
        self.range_sigma = float(range_sigma)
        # planning: the map inflated by the robot's radius, 8-connected
        self.plan_clearance = self.radius
        self.plan_map = _inflated_grid_map(self.smap, self.radius)
        self.grid = self.plan_map.to_grid(connectivity=8)
        self.seed = seed
        self.rng = Rng(seed)
        self.noise_rng = self.rng.split()
        st = self.spec['start']
        sx, sy = to_map_frame(self.spec, st['x'], st['y'])
        self.start = (sx, sy, wrap(st['theta']))
        if self.smap.clearance(sx, sy) < self.radius * 0.5:
            raise ArenaError(f'start {self.start} is against a wall')
        self.planner = planner
        #: called with (columns, meta) for each batch of plan events, while
        #: the search runs (coco_lab.events.SearchEventColumns); never part
        #: of the state, so it cannot change a hash
        self.on_plan_batch = on_plan_batch
        self.plan_batch_size = plan_batch_size
        self.plans_made = 0
        self.tick = 0
        self._in_step = False
        self._pending: List[InputEvent] = []
        self._collector: Optional[Collector] = None
        self._stream = None
        self._want_plan = False
        #: a goal a subsystem asked for (M2.6: the mission), taken at the
        #: start of the next tick; ``_requested`` keeps it planned if the
        #: tick is amended
        self._goal_request: Optional[Tuple[float, float]] = None
        self._requested = False
        #: called with (channel, tick, columns, scalars) for each whole-loop
        #: family batch (coco_lab.columns); never part of the state
        self.on_family = on_family
        # -- the whole loop (M2): off until the first loop input
        self.loop = False
        self.subsystems: Dict[str, object] = {}
        self.slip = False
        self.odom = (0.0, 0.0, 0.0)
        self.odom_alphas = ODOM_ALPHAS
        self.odom_rng: Optional[Rng] = None
        self._chain = hashlib.sha256(STATE_LAYOUT).digest()
        self._reset_robot()
        self.ranges = self._scan()

    # -- state -----------------------------------------------------------------

    def _reset_robot(self):
        self.pose = self.start
        self.v = 0.0
        self.w = 0.0
        self.mode = 'idle'
        self.goal: Optional[Tuple[float, float]] = None
        self.waypoints: List[Tuple[float, float]] = []
        self.wp_index = 0
        self.teleop = (0.0, 0.0)

    @property
    def t_world(self) -> float:
        """Return the simulation seconds at the current tick."""
        return self.tick * self.dt

    # -- inputs ----------------------------------------------------------------

    def _apply(self, e: InputEvent):
        lim = self.limits
        if e.kind == 'goal':
            self.goal = (e.x, e.y)
            self.teleop = (0.0, 0.0)
            self._want_plan = True
        elif e.kind == 'teleop':
            self.goal, self.waypoints, self.wp_index = None, [], 0
            self.mode = 'teleop'
            self.teleop = (
                max(-lim['teleop_linear'], min(lim['teleop_linear'], e.linear)),
                max(-lim['teleop_angular'],
                    min(lim['teleop_angular'], e.angular)))
        elif e.kind == 'stop':
            self.goal, self.waypoints, self.wp_index = None, [], 0
            self.mode = 'idle'
            self.teleop = (0.0, 0.0)
            self.v = self.w = 0.0          # STOP is immediate in the model
        elif e.kind == 'planner':
            if e.choice not in PLANNERS:
                raise ArenaError(f'unknown planner {e.choice!r}')
            self.planner = e.choice
            if self.goal is not None:      # a running goal is re-planned
                self._want_plan = True
        elif e.kind == 'reset':
            self.reset_home()

    def reset_home(self) -> None:
        """
        Put the robot back at the start pose and restart the loop.

        What a ``reset`` input does: the robot at the start pose, stopped,
        with no goal; odometry zeroed; every subsystem told (each restarts
        its filter, map or scenario, the mission ends). The fetch mission
        also calls it when a new fetch starts after another (M3.0).
        """
        self._reset_robot()
        if self.loop:
            self.odom = (0.0, 0.0, 0.0)
            for name in sorted(self.subsystems):
                self.subsystems[name].on_reset(self)

    def _plan_begin(self):
        """Start the search from the current pose to the goal (not run yet)."""
        g = self.grid
        here = self.belief()
        s_cell = self.plan_map.cell_at(here[0], here[1])
        t_cell = self.plan_map.cell_at(*self.goal)
        if s_cell is None or t_cell is None:
            raise ArenaError(f'goal {self.goal} or the robot is off the map')
        s = _nearest_free(g, s_cell)
        t = _nearest_free(g, t_cell)
        if s is None or t is None:
            raise ArenaError(f'no free cell near the robot or {self.goal}')
        events = search_events(g, s, t, **PLANNERS[self.planner])
        self._plan_ctx = (self.planner, self.goal, self.tick)
        self._stream = None
        sink = None
        if self.on_plan_batch is not None:
            # stream the search to the renderer while it runs (M1.5);
            # the search, and so the state, is the same either way
            cols = SearchEventColumns(search_id=self.plans_made,
                                      tick=self.tick, t_world=self.t_world)
            meta = {'search_id': self.plans_made, 'planner': self.planner,
                    'tick': self.tick}
            size, hook = self.plan_batch_size, self.on_plan_batch
            self._stream = (cols, meta)

            def _sink(row):
                cols.add(row)
                if len(cols) >= size:
                    hook(cols.drain(), dict(meta, final=False))
            sink = _sink
        self._collector = Collector(events, sink)

    def _plan_cancel(self):
        """Drop the search in flight; it keeps its id, so ids never repeat."""
        if self._collector is None:
            return
        if self._stream is not None:
            cols, meta = self._stream
            self.on_plan_batch(cols.drain(),
                               dict(meta, final=True, cancelled=True))
        self._collector = self._stream = None
        self.plans_made += 1

    def _plan_finish(self) -> Plan:
        """Run the search to its end; turn its path into waypoints."""
        c = self._collector
        c.advance()
        res = c.result
        if self._stream is not None:
            cols, meta = self._stream
            self.on_plan_batch(cols.drain(), dict(meta, final=True))
        self._collector = self._stream = None
        planner, goal, tick = self._plan_ctx
        self.plans_made += 1
        waypoints = []
        if res.path:
            cells = [(c[0], c[1]) for c in res.path]
            for i, c in enumerate(cells):
                if 0 < i < len(cells) - 1:
                    p, n = cells[i - 1], cells[i + 1]
                    if (c[0] - p[0], c[1] - p[1]) == (n[0] - c[0],
                                                      n[1] - c[1]):
                        continue
                waypoints.append(self.plan_map.cell_centre(*c))
            waypoints[-1] = goal
            waypoints = waypoints[1:] or waypoints
        self.waypoints, self.wp_index = waypoints, 0
        self.mode = 'goal' if waypoints else 'idle'
        if not waypoints:
            self.goal = None
        return Plan(planner, goal, res, list(waypoints), tick)

    # -- the step --------------------------------------------------------------

    def _command(self) -> Tuple[float, float, bool]:
        """Return the target ``(v, w)`` and whether the goal was reached."""
        lim = self.limits
        if self.mode == 'teleop':
            return self.teleop[0], self.teleop[1], False
        if self.mode == 'goal':
            # a local controller from a subsystem drives instead (M2.5)
            for name in sorted(self.subsystems):
                f = getattr(self.subsystems[name], 'command', None)
                c = f(self) if f is not None else None
                if c is not None:
                    return c
            while self.wp_index < len(self.waypoints):
                c = drive_command(self.belief(), self.waypoints[self.wp_index],
                                  lim['auto_linear'], lim['auto_angular'],
                                  self.dt)
                if c is not None:
                    return c[0], c[1], False
                self.wp_index += 1
            self.mode, self.goal = 'idle', None
            return 0.0, 0.0, True
        return 0.0, 0.0, False

    def discs(self) -> List[Tuple[float, float, float]]:
        """Every moving body's (x, y, radius), from the subsystems (M2.5)."""
        out: List[Tuple[float, float, float]] = []
        for name in sorted(self.subsystems):
            f = getattr(self.subsystems[name], 'discs', None)
            if f is not None:
                out.extend(f())
        return out

    def _scan(self) -> List[float]:
        true = self.smap.scan(self.pose, self.lidar, self.angles)
        discs = self.discs() if self.subsystems else []
        if discs:
            true = _with_discs(true, self.pose, self.lidar, self.angles, discs)
        lo, hi = self.lidar.range_min, self.lidar.range_max
        out = []
        for z in true:
            if self.range_sigma > 0:
                z = z + self.noise_rng.gauss(0.0, self.range_sigma)
            out.append(z if lo <= z <= hi else math.inf)
        return out

    # -- a step, whole or in slices -------------------------------------------

    def _snapshot(self):
        return (self.pose, self.v, self.w, self.mode, self.goal,
                list(self.waypoints), self.wp_index, self.teleop,
                self.planner)

    def _restore(self, snap):
        (self.pose, self.v, self.w, self.mode, self.goal, waypoints,
         self.wp_index, self.teleop, self.planner) = snap
        self.waypoints = list(waypoints)

    def _check_ticks(self, events: Sequence[InputEvent]):
        for e in events:
            if e.tick != self.tick:
                raise ArenaError(f'input for tick {e.tick} given at tick '
                                 f'{self.tick}')

    # -- the whole loop ---------------------------------------------------------

    def belief(self) -> Tuple[float, float, float]:
        """Where the robot believes it is: a localiser's estimate, or truth."""
        for name in sorted(self.subsystems):
            b = getattr(self.subsystems[name], 'belief', None)
            pose = b() if b is not None else None
            if pose is not None:
                return pose
        return self.pose

    def _activate(self):
        if not self.loop:
            self.loop = True
            self.odom = (0.0, 0.0, 0.0)
            self.odom_rng = self.rng.split()

    def _apply_loop(self, e: InputEvent):
        self._activate()
        if e.kind == 'kidnap':
            th = wrap(e.theta) if e.has_theta else self.pose[2]
            if self.smap.clearance(e.x, e.y) < self.radius * 0.5:
                raise ArenaError(f'kidnap target ({e.x}, {e.y}) is against '
                                 'a wall')
            self.pose = (e.x, e.y, th)          # odometry is not told
            self.v = self.w = 0.0
            return
        key, _, value = e.choice.partition('=')
        head, _, rest = key.partition('.')
        if head == 'arena':
            self._config_arena(rest, value)
            return
        sub = self.subsystems.get(head)
        if sub is None:
            cls = SUBSYSTEMS.get(head)
            if cls is None:
                raise ArenaError(f'no subsystem {head!r} (its pack is not '
                                 'loaded)')
            sub = self.subsystems[head] = cls(self)
        sub.config(rest, value)

    def _config_arena(self, key: str, value: str):
        if key == 'slip':
            if value not in ('on', 'off'):
                raise ArenaError(f'arena.slip must be on or off, not {value!r}')
            self.slip = value == 'on'
        elif key == 'range_sigma':
            v = float(value)
            if not (math.isfinite(v) and v >= 0):
                raise ArenaError('arena.range_sigma must be >= 0')
            self.range_sigma = v
        elif key == 'plan_clearance':
            v = float(value)
            if not (math.isfinite(v) and self.radius <= v <= 1.0):
                raise ArenaError(f'arena.plan_clearance must be in '
                                 f'[{self.radius}, 1.0] m')
            self.set_plan_clearance(v)
        elif key == 'odom_alphas':
            a = tuple(float(x) for x in value.split(','))
            if len(a) != 4 or any(not (math.isfinite(x) and x >= 0)
                                  for x in a):
                raise ArenaError('arena.odom_alphas must be four values >= 0')
            self.odom_alphas = a
        else:
            raise ArenaError(f'unknown arena setting {key!r}')

    def emit(self, channel: str, batch) -> None:
        """Hand a filled coco_lab.columns.Batch to the family hook."""
        if self.on_family is not None and len(batch):
            cols, scalars = batch.drain()
            self.on_family(channel, self.tick, cols, scalars)

    def emit_header(self, channel: str, header: Dict[str, object]) -> None:
        """Hand a channel's static header to the family hook."""
        if self.on_family is not None:
            self.on_family(channel, self.tick, None, header)

    def set_plan_clearance(self, r: float) -> None:
        """Plan on the map inflated by ``r`` (M1: the robot's radius)."""
        if r != self.plan_clearance:
            self.plan_clearance = r
            self.plan_map = _inflated_grid_map(self.smap, r)
            self.grid = self.plan_map.to_grid(connectivity=8)

    def request_goal(self, x: float, y: float) -> None:
        """Ask for a goal from a subsystem: planned at the next tick's start."""
        self._goal_request = (float(x), float(y))

    def _prepare(self):
        """Apply the pending inputs to the snapshot; start the one search."""
        self._want_plan = self._requested
        for e in self._pending:
            self._apply(e)
        if self._want_plan and self.goal is not None:
            self._plan_begin()

    def begin_step(self, events: Sequence[InputEvent] = ()):
        """Apply this tick's inputs and start its search, if it needs one."""
        if self._in_step:
            raise ArenaError('a step is already in progress')
        self._check_ticks(events)
        # loop inputs first, committed now (never restored by an amendment)
        loop = [e for e in events if e.kind in LOOP_KINDS]
        for e in loop:
            self._apply_loop(e)
        self._loop_applied = loop
        if self._goal_request is not None:
            # committed like a loop input: an amendment re-plans it
            self.goal, self.teleop = self._goal_request, (0.0, 0.0)
            self._goal_request = None
            self._requested = True
        self._snap = self._snapshot()
        self._pending = [e for e in events if e.kind not in LOOP_KINDS]
        self._in_step = True
        try:
            self._prepare()
        except Exception:
            self._restore(self._snap)
            self._pending = []
            self._in_step = False
            raise

    def advance(self, n: Optional[int] = None) -> bool:
        """Take up to ``n`` events of the tick's search; return whether done."""
        if not self._in_step:
            raise ArenaError('advance outside a step')
        return self._collector is None or self._collector.advance(n)

    def amend(self, events: Sequence[InputEvent]):
        """
        Add inputs to the tick in progress (they arrived while it planned).

        The search in flight is cancelled and the tick is prepared again
        from its snapshot with every input so far, in order -- exactly what
        :meth:`step` would do with the whole list. An amendment the Arena
        cannot honour is refused and the tick goes on with what it had.
        """
        if not self._in_step:
            raise ArenaError('amend outside a step')
        self._check_ticks(events)
        if any(e.kind in LOOP_KINDS for e in events):
            raise ArenaError('a loop input opens a tick; it cannot amend one')
        self._plan_cancel()
        self._restore(self._snap)
        before = len(self._pending)
        self._pending.extend(events)
        try:
            self._prepare()
        except Exception:
            self._plan_cancel()
            self._restore(self._snap)
            del self._pending[before:]
            self._prepare()
            raise

    def finish_step(self) -> Tick:
        """Finish the tick's search, advance one ``dt``, scan, hash."""
        if not self._in_step:
            raise ArenaError('finish_step outside a step')
        plans: List[Plan] = []
        if self._collector is not None:
            plans.append(self._plan_finish())
        applied = self._loop_applied + self._pending
        self._requested = False
        self._pending = []
        self._loop_applied = []
        self._in_step = False
        tv, tw, arrived = self._command()
        lim, dt = self.limits, self.dt
        dv = lim['linear_accel'] * dt
        dw = lim['angular_accel'] * dt
        self.v += max(-dv, min(dv, tv - self.v))
        self.w += max(-dw, min(dw, tw - self.w))
        before = self.pose
        new = step_pose(before, self.v, self.w, dt)
        wheels = new
        if self.loop and self.slip:
            # the wheels did the commanded motion; the body turned less
            new = step_pose(before, self.v, self.w * SLIP_TURN, dt)
        blocked = self.smap.clearance(new[0], new[1]) < self.radius * 0.5
        if not blocked and self.subsystems:
            # a moving body is solid: the robot cannot drive into one (M2.5)
            blocked = any(math.hypot(new[0] - dx, new[1] - dy) < self.radius + r
                          for dx, dy, r in self.discs())
        if blocked:
            new = wheels = before
            self.v = self.w = 0.0
        self.pose = new
        if self.loop:
            r1, tr, r2 = odom_delta(before, wheels)
            n1, nt, n2 = sample_delta(r1, tr, r2, self.odom_alphas,
                                      self.odom_rng)
            self.odom = apply_delta(self.odom, n1, nt, n2)
        self.tick += 1
        for name in sorted(self.subsystems):
            f = getattr(self.subsystems[name], 'world_step', None)
            if f is not None:
                f(self)
        self.ranges = self._scan()
        for name in sorted(self.subsystems):
            self.subsystems[name].on_tick(self)
        b = self.state_bytes()
        self._chain = hashlib.sha256(self._chain + b).digest()
        h = hashlib.sha256(b).hexdigest()
        return Tick(self.tick, self.t_world, self.pose, self.v, self.w,
                    self.mode, list(self.ranges), plans, applied, blocked,
                    arrived, h, belief=self.belief() if self.loop else None,
                    actors=self.discs() if self.subsystems else [])

    def step(self, events: Sequence[InputEvent] = ()) -> Tick:
        """Apply this tick's inputs, plan once, advance ``dt``, scan, hash."""
        self.begin_step(events)
        return self.finish_step()

    # -- the per-tick state hash -------------------------------------------------

    def state_bytes(self) -> bytes:
        """
        Return the canonical, quantized state (docs/v2/ARENA_MODEL.md).

        Little-endian: tick u64; x, y, theta, v, w as int64 micro-units;
        mode, planner, has_goal u8; goal x, y int64 micro-units (0 if none);
        waypoint index and count u32; both RNG states as 4 x u64; beam count
        u32 and every range as u32 tenths of a millimetre (0xFFFFFFFF = no
        return).
        """
        x, y, th = self.pose
        gx, gy = self.goal if self.goal is not None else (0.0, 0.0)
        parts = [struct.pack('<Q5q3B2q2I', self.tick,
                             _q(x, Q_STATE), _q(y, Q_STATE), _q(th, Q_STATE),
                             _q(self.v, Q_STATE), _q(self.w, Q_STATE),
                             MODES.index(self.mode),
                             PLANNER_IDS.index(self.planner),
                             self.goal is not None,
                             _q(gx, Q_STATE), _q(gy, Q_STATE),
                             self.wp_index, len(self.waypoints)),
                 struct.pack('<4Q', *self.rng.state),
                 struct.pack('<4Q', *self.noise_rng.state),
                 struct.pack('<I', len(self.ranges))]
        parts.append(struct.pack(f'<{len(self.ranges)}I', *(
            NO_RETURN if r == math.inf else _q(r, Q_RANGE)
            for r in self.ranges)))
        if self.loop:
            # the whole loop's state (layout coco.arena.loop.v1, ARENA_MODEL.md)
            ox, oy, oth = self.odom
            parts += [LOOP_LAYOUT,
                      struct.pack('<3qBq', _q(ox, Q_STATE), _q(oy, Q_STATE),
                                  _q(oth, Q_STATE), self.slip,
                                  _q(self.range_sigma, Q_STATE)),
                      struct.pack('<4q', *(_q(a, Q_STATE)
                                           for a in self.odom_alphas)),
                      struct.pack('<4Q', *self.odom_rng.state)]
            if self.plan_clearance != self.radius:
                # only when set (M2.6), so earlier loop hashes are unchanged
                parts.append(b'clearance' + struct.pack(
                    '<q', _q(self.plan_clearance, Q_STATE)))
            for name in sorted(self.subsystems):
                nb = name.encode('utf-8')
                sb = self.subsystems[name].state_bytes()
                parts += [struct.pack('<I', len(nb)), nb,
                          struct.pack('<I', len(sb)), sb]
        return b''.join(parts)

    def state_hash(self) -> str:
        """Return sha256 of the current state bytes (hex)."""
        return hashlib.sha256(self.state_bytes()).hexdigest()

    @property
    def chain(self) -> str:
        """Return the hash chain over every tick so far (one per run)."""
        return self._chain.hex()


def _with_discs(ranges, pose, lidar, angles, discs) -> List[float]:
    """Return ``ranges`` shortened where a beam meets a disc first."""
    x, y, th = pose
    mx, my, myaw = lidar.mount
    c, s = math.cos(th), math.sin(th)
    sx = x + c * mx - s * my
    sy = y + s * mx + c * my
    out = list(ranges)
    for k, a in enumerate(angles):
        ux, uy = math.cos(th + myaw + a), math.sin(th + myaw + a)
        for dx, dy, r in discs:
            fx, fy = dx - sx, dy - sy
            b = fx * ux + fy * uy
            q = b * b - (fx * fx + fy * fy - r * r)
            if q < 0:
                continue
            t = b - math.sqrt(q)
            if t < 0:
                t = b + math.sqrt(q)
                if t < 0:
                    continue
                t = 0.0  # the sensor is inside the disc
            if t < out[k]:
                out[k] = t
    return out


def replay(spec: Dict[str, object], seed: int, inputs: Sequence[InputEvent],
           ticks: int, **kw) -> List[str]:
    """Run ``ticks`` steps from the start; return every tick's state hash."""
    arena = Arena(spec, seed, **kw)
    by_tick: Dict[int, List[InputEvent]] = {}
    for e in inputs:
        by_tick.setdefault(e.tick, []).append(e)
    return [arena.step(by_tick.get(arena.tick, ())).state_hash
            for _ in range(ticks)]


def is_free(arena: Arena, x: float, y: float) -> bool:
    """Return whether a goal at ``(x, y)`` lies in a plannable cell."""
    cell = arena.plan_map.cell_at(x, y)
    return cell is not None and arena.plan_map.at(cell) != OCCUPIED
