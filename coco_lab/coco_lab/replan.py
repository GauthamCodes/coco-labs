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
Lab 5's replanning episode: a robot that learns the map as it drives.

A :class:`ReplanWorld` holds two maps of the same grid:

``known``
    what the robot's map says before it moves;
``truth``
    what the world really is -- and, through ``schedule``, what it
    becomes at given steps (a door closing, a person stopping in a
    corridor).

:func:`run_replan` drives one episode, deterministically:

1. the robot senses every cell within ``sense_radius`` (Euclidean, in
   cells; ``None`` = it is told every change at once, as a global costmap
   update would) and copies the truth of those cells into its map;
2. D* Lite (:mod:`coco_lab.dstarlite`) plans on the known map (round 0);
3. the robot steps to the next cell of the plan, the world applies any
   change scheduled for that step, the robot senses again, and if its map
   changed D* Lite repairs and replans (round k);
4. until it reaches the goal, no path exists on what it knows, or
   ``max_steps``.

Every round is checked against Lab 1's A* run FROM SCRATCH on the same
known map from the same cell: the costs must agree (they always have; the
property tests prove it), and the A* expansions are recorded beside D*
Lite's, which is the comparison the lab shows -- the same answer, for less
(or sometimes more) work. ``sense_radius`` must be at least 1.5 so the
next cell (diagonals included) is always seen before it is entered: the
robot never steps into an obstacle it could not have known about.

Everything here is a Sketch: a grid model, not the robot. Seeded
generators (:func:`sketch_world`) make the teaching scenarios; a world
built from two real Nav2 costmaps (``docs/data/lab5``) makes Experiment C.
"""

from dataclasses import dataclass, field
import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

from .dstarlite import DStarLite, grid_changes, ReplanError
from .grid import Grid
from .search import search

Cell = Tuple[int, int]

STATUSES = ('reached', 'no_path', 'step_limit')


@dataclass
class ReplanWorld:
    """Everything an episode needs; validated by :meth:`validate`."""

    width: int
    height: int
    known: List[bool]
    truth: List[bool]
    start: Cell
    goal: Cell
    sense_radius: Optional[float] = 2.5
    connectivity: int = 8
    heuristic: str = 'octile'
    #: optional cost layer of the robot's map (Grid's units)
    cost: Optional[List[float]] = None
    #: the world's cost layer, if it differs from the map's (a costmap
    #: update changes inflation costs, not only occupancy); needs ``cost``
    truth_cost: Optional[List[float]] = None
    #: the first step at which the robot senses: 0 (from the start) or 1
    #: (the world's difference arrives after the first plan -- a global
    #: costmap update between two snapshots, Experiment C)
    first_sense_step: int = 0
    #: ``[(step, [(row, col, blocked), ...]), ...]``: world changes
    schedule: List[Tuple[int, List[Tuple[int, int, bool]]]] = field(
        default_factory=list)
    max_steps: int = 2000

    def validate(self) -> None:
        """Raise :class:`ReplanError` unless the world is usable."""
        n = self.width * self.height
        if not (isinstance(self.width, int) and isinstance(self.height, int)
                and 1 <= self.width <= 512 and 1 <= self.height <= 512
                and n >= 2):
            raise ReplanError('width and height must be ints in 1..512, '
                              'at least two cells')
        if len(self.known) != n or len(self.truth) != n:
            raise ReplanError('known and truth must cover the grid')
        if self.cost is not None and len(self.cost) != n:
            raise ReplanError('cost must cover the grid')
        if self.truth_cost is not None and (self.cost is None
                                            or len(self.truth_cost) != n):
            raise ReplanError('truth_cost needs cost, and must cover the '
                              'grid')
        if self.first_sense_step not in (0, 1):
            raise ReplanError('first_sense_step must be 0 or 1')
        if self.first_sense_step == 1:
            # the first step is taken unsensed: its cells must not differ
            r0, c0 = self.start
            for r in range(max(0, r0 - 1), min(self.height, r0 + 2)):
                for c in range(max(0, c0 - 1), min(self.width, c0 + 2)):
                    i = r * self.width + c
                    if self.known[i] != self.truth[i] or (
                            self.truth_cost is not None
                            and self.cost[i] != self.truth_cost[i]):
                        raise ReplanError('with first_sense_step 1 the '
                                          'cells around the start must be '
                                          'known')
        if self.sense_radius is not None and not (
                isinstance(self.sense_radius, (int, float))
                and 1.5 <= self.sense_radius <= 64):
            raise ReplanError('sense_radius must be None or in 1.5..64 '
                              'cells (the next cell must be seen first)')
        for name, c in (('start', self.start), ('goal', self.goal)):
            r, k = c
            if not (0 <= r < self.height and 0 <= k < self.width):
                raise ReplanError(f'{name} {c} is off the grid')
            i = r * self.width + k
            if self.known[i] or self.truth[i]:
                raise ReplanError(f'{name} {c} is blocked')
        last = -1
        for step, cells in self.schedule:
            if not (isinstance(step, int) and step > last):
                raise ReplanError('schedule steps must increase')
            last = step
            for r, k, b in cells:
                if not (0 <= r < self.height and 0 <= k < self.width):
                    raise ReplanError(f'scheduled cell {(r, k)} off grid')
                if b and (r, k) in (self.start, self.goal):
                    raise ReplanError('the schedule may not block the '
                                      'start or the goal')
        if not 1 <= self.max_steps <= 100000:
            raise ReplanError('max_steps must be in 1..100000')

    def grid(self, blocked: Sequence[bool],
             cost: Optional[Sequence[float]] = None) -> Grid:
        """Return a :class:`Grid` with this world's model."""
        return Grid(self.width, self.height, list(blocked),
                    self.cost if cost is None else list(cost),
                    connectivity=self.connectivity)

    def to_dict(self) -> Dict[str, object]:
        """Return the world's parameters (not its occupancy arrays)."""
        return {'width': self.width, 'height': self.height,
                'start': list(self.start), 'goal': list(self.goal),
                'sense_radius': self.sense_radius,
                'connectivity': self.connectivity,
                'heuristic': self.heuristic,
                'has_cost': self.cost is not None,
                'has_truth_cost': self.truth_cost is not None,
                'first_sense_step': self.first_sense_step,
                'schedule': [[s, [list(c) for c in cells]]
                             for s, cells in self.schedule],
                'max_steps': self.max_steps}


@dataclass
class Round:
    """One plan: round 0 is the first, round k the k-th replan."""

    step: int                      # robot steps taken when it was made
    robot: Cell
    changed: List[Cell]            # cells the robot's map changed in
    found: bool
    cost: Optional[float]          # D* Lite's g(robot)
    path: List[Cell]
    dstar_expansions: int
    dstar_reexpansions: int        # popped this round, also in an earlier
    astar_expansions: int          # Lab 1's A*, from scratch, same map
    astar_cost: Optional[float]


@dataclass
class ReplanResult:
    """An episode: the robot's walk, every round, and D* Lite's trace."""

    world: ReplanWorld
    status: str
    walk: List[Cell]
    rounds: List[Round]
    trace: object                  # dstarlite.ReplanTrace
    known_final: List[bool]

    def summary(self) -> Dict[str, object]:
        """Return a JSON-ready digest of the episode."""
        d = sum(r.dstar_expansions for r in self.rounds)
        a = sum(r.astar_expansions for r in self.rounds)
        g = self.world.grid(self.world.truth, self.world.truth_cost)
        moved = 0.0
        for p, q in zip(self.walk, self.walk[1:]):
            moved += g.move_cost(p, q)
        return {'status': self.status, 'steps': len(self.walk) - 1,
                'replans': len(self.rounds) - 1,
                'dstar_expansions': d, 'astar_expansions': a,
                'reexpansions': sum(r.dstar_reexpansions
                                    for r in self.rounds),
                'first_cost': self.rounds[0].cost if self.rounds else None,
                'walked_length': moved,
                'costs_agree': all(
                    (r.cost is None and r.astar_cost is None)
                    or (r.cost is not None and r.astar_cost is not None
                        and abs(r.cost - r.astar_cost) <= 1e-9)
                    for r in self.rounds)}


def _sense(world: ReplanWorld, truth, known, at: Cell, tcost=None,
           kcost=None) -> List[Cell]:
    """Copy the truth of the sensed cells into ``known``; return changes."""
    out = []
    r0, c0 = at
    R = world.sense_radius
    for r in range(world.height):
        if R is not None and abs(r - r0) > R:
            continue
        for c in range(world.width):
            if R is not None and math.hypot(r - r0, c - c0) > R:
                continue
            i = r * world.width + c
            if known[i] != truth[i] or (tcost is not None
                                        and kcost[i] != tcost[i]):
                known[i] = truth[i]
                if tcost is not None:
                    kcost[i] = tcost[i]
                out.append((r, c))
    return out


def run_replan(world: ReplanWorld) -> ReplanResult:
    """Drive one episode (module doc); deterministic in its inputs."""
    world.validate()
    truth = list(world.truth)
    known = list(world.known)
    tcost = list(world.truth_cost) if world.truth_cost is not None else None
    kcost = list(world.cost) if tcost is not None else None
    changed0 = (_sense(world, truth, known, world.start, tcost, kcost)
                if world.first_sense_step == 0 else [])
    grid = world.grid(known, kcost)
    dsl = DStarLite(grid, world.start, world.goal, world.heuristic)
    expanded_before = set()
    rounds: List[Round] = []
    schedule = dict(world.schedule)
    walk = [world.start]

    def plan(changed):
        n0 = len(dsl.trace) if dsl.trace is not None else 0
        found = dsl.compute()
        cols = dsl.trace.columns
        popped = [(cols['row'][i], cols['col'][i])
                  for i in range(n0, len(dsl.trace))
                  if cols['kind'][i] in (0, 1)]
        re = sum(1 for p in popped if p in expanded_before)
        expanded_before.update(popped)
        ref = search(dsl.graph, dsl.start, world.goal, 'astar',
                     world.heuristic)
        path = dsl.path() if found else []
        rounds.append(Round(
            step=len(walk) - 1, robot=dsl.start, changed=list(changed),
            found=found, cost=dsl.g_of(dsl.start) if found else None,
            path=path, dstar_expansions=dsl.round_expansions[-1],
            dstar_reexpansions=re, astar_expansions=ref.trace.summary[
                'expansions'], astar_cost=ref.cost if ref.found else None))
        return found, path

    found, path = plan(changed0)
    status = 'reached' if dsl.start == world.goal else None
    while status is None:
        if not found:
            status = 'no_path'
            break
        if len(walk) - 1 >= world.max_steps:
            status = 'step_limit'
            break
        nxt = path[1]
        dsl.move_to(nxt)
        walk.append(nxt)
        step = len(walk) - 1
        for r, c, b in schedule.get(step, []):
            truth[r * world.width + c] = bool(b)
        changed = _sense(world, truth, known, nxt, tcost, kcost)
        if nxt == world.goal:
            status = 'reached'
            break
        if changed:
            new = world.grid(known, kcost)
            _, affected = grid_changes(grid, new)
            dsl.apply_changes(new, affected)
            grid = new
            found, path = plan(changed)
        else:
            path = path[1:]
    return ReplanResult(world, status, walk, rounds, dsl.trace, known)


# -- seeded teaching worlds -----------------------------------------------------

def sketch_world(seed: int, width: int = 32, height: int = 20,
                 density: float = 0.18, hidden: float = 0.35,
                 sense_radius: float = 2.5) -> ReplanWorld:
    """
    Return a seeded world: random walls, some of them unknown to the robot.

    The truth is ``density`` random obstacle cells plus two walls, the
    first with one gap and the second with two; ``hidden`` of the random
    obstacle cells, and the closing of the second wall's first gap, are
    missing from the robot's map (an optimistic map: nothing on it is
    blocked that is not blocked in the world).
    Start is the left-middle, goal the right-middle; both are kept free.
    Deterministic in its arguments (``random.Random(seed)``).
    """
    rng = random.Random(seed)
    n = width * height
    truth = [rng.random() < density for _ in range(n)]
    known = list(truth)
    start, goal = (height // 2, 1), (height // 2, width - 2)
    w1, w2 = width // 3, (2 * width) // 3
    gap1 = rng.randrange(2, height - 2)
    # the second wall's first gap is on the direct route (middle rows), its
    # second near the top or bottom edge: closing the first forces a detour
    gap2 = height // 2 + rng.randrange(-1, 2)
    for r in range(height):
        for c, gap in ((w1, gap1), (w2, gap2)):
            i = r * width + c
            truth[i] = known[i] = abs(r - gap) > 1
    # the second wall's gap is closed in the world but open on the map
    for r in range(gap2 - 1, gap2 + 2):
        truth[r * width + w2] = True
    # a second gap, open on the map AND in the world, so a route remains.
    # The robot's map is OPTIMISTIC, as D* Lite assumes: it may lack an
    # obstacle, it never invents one.
    alt = 2 if rng.random() < 0.5 else height - 3
    for r in range(alt - 1, alt + 2):
        truth[r * width + w2] = known[r * width + w2] = False
    for i in range(n):
        if truth[i] and known[i] and rng.random() < hidden and \
                (i % width) not in (w1, w2):
            known[i] = False
    for r0, c0 in (start, goal):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                r, c = r0 + dr, c0 + dc
                if 0 <= r < height and 0 <= c < width:
                    truth[r * width + c] = known[r * width + c] = False
    return ReplanWorld(width, height, known, truth, start, goal,
                       sense_radius=sense_radius)
