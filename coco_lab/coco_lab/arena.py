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
from .sketch import (_inflated_grid_map, _nearest_free, drive_command,
                     LidarSpec, SketchMap, step_pose, wrap)
from .worldspec import arena_map, normalize, to_map_frame

#: The state-hash layout's name; a change to the layout changes this.
STATE_LAYOUT = b'coco.arena.state.v1\x00'
INPUT_KINDS = ('goal', 'teleop', 'stop', 'planner', 'reset')
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


def _q(v: float, scale: float) -> int:
    """Quantize to an int64 (round half to even, Python's round)."""
    return round(v * scale)


class Arena:
    """A deterministic Arena run: one world, one seed, one input log."""

    def __init__(self, spec: Dict[str, object], seed: int,
                 planner: str = 'astar', range_sigma: float = 0.0,
                 lidar_every: int = 1, on_plan_batch=None,
                 plan_batch_size: int = 2048):
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
            self._reset_robot()

    def _plan_begin(self):
        """Start the search from the current pose to the goal (not run yet)."""
        g = self.grid
        s_cell = self.plan_map.cell_at(self.pose[0], self.pose[1])
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
            while self.wp_index < len(self.waypoints):
                c = drive_command(self.pose, self.waypoints[self.wp_index],
                                  lim['auto_linear'], lim['auto_angular'],
                                  self.dt)
                if c is not None:
                    return c[0], c[1], False
                self.wp_index += 1
            self.mode, self.goal = 'idle', None
            return 0.0, 0.0, True
        return 0.0, 0.0, False

    def _scan(self) -> List[float]:
        true = self.smap.scan(self.pose, self.lidar, self.angles)
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

    def _prepare(self):
        """Apply the pending inputs to the snapshot; start the one search."""
        self._want_plan = False
        for e in self._pending:
            self._apply(e)
        if self._want_plan and self.goal is not None:
            self._plan_begin()

    def begin_step(self, events: Sequence[InputEvent] = ()):
        """Apply this tick's inputs and start its search, if it needs one."""
        if self._in_step:
            raise ArenaError('a step is already in progress')
        self._check_ticks(events)
        self._snap = self._snapshot()
        self._pending = list(events)
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
        applied = self._pending
        self._pending = []
        self._in_step = False
        tv, tw, arrived = self._command()
        lim, dt = self.limits, self.dt
        dv = lim['linear_accel'] * dt
        dw = lim['angular_accel'] * dt
        self.v += max(-dv, min(dv, tv - self.v))
        self.w += max(-dw, min(dw, tw - self.w))
        new = step_pose(self.pose, self.v, self.w, dt)
        blocked = self.smap.clearance(new[0], new[1]) < self.radius * 0.5
        if blocked:
            new = self.pose
            self.v = self.w = 0.0
        self.pose = new
        self.tick += 1
        self.ranges = self._scan()
        b = self.state_bytes()
        self._chain = hashlib.sha256(self._chain + b).digest()
        h = hashlib.sha256(b).hexdigest()
        return Tick(self.tick, self.t_world, self.pose, self.v, self.w,
                    self.mode, list(self.ranges), plans, applied, blocked,
                    arrived, h)

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
        return b''.join(parts)

    def state_hash(self) -> str:
        """Return sha256 of the current state bytes (hex)."""
        return hashlib.sha256(self.state_bytes()).hexdigest()

    @property
    def chain(self) -> str:
        """Return the hash chain over every tick so far (one per run)."""
        return self._chain.hex()


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
