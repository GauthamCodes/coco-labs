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
D* Lite: replanning when the world changes, without starting over.

The algorithm is Koenig and Likhachev's D* Lite (AAAI 2002), the basic
version of their Figure 3, on the same :class:`coco_lab.graph.SearchGraph`
interface Lab 1's five algorithms search -- nothing here knows about
grids except :func:`grid_changes`, which turns two grids into the set of
states whose out-edges changed.

**How it differs from A*.** It searches BACKWARDS, from the goal towards
the robot, and keeps two values per state: ``g``, its current estimate of
the cost to the goal, and ``rhs``, a one-step lookahead
(``min over successors s' of c(s, s') + g(s')``). A state is *consistent*
when they agree. When edge costs change only the states whose ``rhs``
changed are queued again, and only the inconsistency they cause is
repaired; most of the previous search is reused. The key of a queued
state is ``(min(g, rhs) + h(start, s) + km, min(g, rhs))``; ``km`` grows
by ``h(last, start)`` each time the robot has moved before a replan, so
old keys stay valid lower bounds without re-sorting the queue.

**Rules this implementation fixes** (the property tests prove the claims):

- *Optimality.* After every :meth:`DStarLite.compute`, ``g(start)`` equals
  the optimal cost on the CURRENT graph -- Dijkstra's, exactly, on 1,000
  seeded random maps and change sequences
  (``coco_lab/test/test_dstarlite.py``).
- *Determinism.* Ties in the queue break by insertion order; successors
  and predecessors come in the graph's own neighbour order; no set or hash
  order is ever consulted. The same inputs give the same trace.
- *Predecessors.* The algorithm needs ``pred(s)``. A graph may provide
  ``predecessors(s)``; otherwise ``neighbours(s)`` is used, which is right
  only for symmetric adjacency (``b in neighbours(a)`` iff ``a in
  neighbours(b)``) -- true of :class:`coco_lab.grid.Grid` (corner rule
  included), and tested. Edge COSTS may be asymmetric (a Grid's are).
- *Consistent heuristic only.* ``h`` must be consistent; on a Grid
  :func:`coco_lab.heuristics.analyse` decides, and an inconsistent one is
  refused rather than allowed to return a wrong path silently.

**The trace** (:class:`ReplanTrace`) records what the search did, round
by round (round 0 is the first plan, round k the k-th replan), in columns:
``kind`` (:data:`EVENT_KINDS`), ``row``, ``col``, ``sub``, ``g``, ``rhs``,
``round``. ``g`` and ``rhs`` use ``-1`` for infinity (costs are never
negative, so the sentinel is unambiguous).
"""

from dataclasses import dataclass, field
import heapq
import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .graph import SearchGraph, State

INF = math.inf
#: Tolerance for comparing keys. Two keys that are equal in exact
#: arithmetic can differ in the last bit when their sums were formed in a
#: different order (measured: 7.242640687119286 against ...285 ended a
#: search one state early and returned a cost 0.59 below the optimum), so
#: key comparisons treat components within ``KEY_EPS`` as equal.
KEY_EPS = 1e-9
#: How infinity is written in a trace column.
INF_SENTINEL = -1.0

#: Event kinds, in code order.
#: ``expand``  a state popped and made consistent (g lowered to rhs);
#: ``raise``   a state popped underconsistent: g reset to infinity;
#: ``update``  UpdateVertex queued a state (its rhs is the value shown);
#: ``change``  a state whose out-edges the world changed;
#: ``path``    one state of the plan produced by the round;
#: ``move``    the robot stepped onto a state.
EVENT_KINDS = ('expand', 'raise', 'update', 'change', 'path', 'move')
EXPAND, RAISE, UPDATE, CHANGE, PATH, MOVE = range(len(EVENT_KINDS))
COLUMNS = ('kind', 'row', 'col', 'sub', 'g', 'rhs', 'round')


class ReplanError(ValueError):
    """A D* Lite input the algorithm cannot honour."""


def key_less(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    """Return ``a < b`` lexicographically, components within KEY_EPS equal."""
    if a[0] < b[0] - KEY_EPS:
        return True
    if a[0] > b[0] + KEY_EPS:
        return False
    return a[1] < b[1] - KEY_EPS


def _enc(v: float) -> float:
    return INF_SENTINEL if v == INF else float(v)


@dataclass
class ReplanTrace:
    """Columnar events, one row per event, in the order they happened."""

    columns: Dict[str, List] = field(
        default_factory=lambda: {c: [] for c in COLUMNS})

    def add(self, kind, loc, g, rhs, rnd):
        """Append one event."""
        c = self.columns
        c['kind'].append(kind)
        c['row'].append(int(loc[0]))
        c['col'].append(int(loc[1]))
        c['sub'].append(int(loc[2]))
        c['g'].append(_enc(g))
        c['rhs'].append(_enc(rhs))
        c['round'].append(int(rnd))

    def __len__(self):
        """Return the number of events."""
        return len(self.columns['kind'])

    def count(self, kind: int, rnd: Optional[int] = None) -> int:
        """Return how many events of ``kind`` (in round ``rnd``) exist."""
        c = self.columns
        return sum(1 for i, k in enumerate(c['kind'])
                   if k == kind and (rnd is None or c['round'][i] == rnd))


class DStarLite:
    """
    One D* Lite search, kept alive across moves and world changes.

    ``heuristic`` names a :data:`coco_lab.graph.HEURISTICS` entry; it is
    evaluated as ``graph.heuristic(name, s, start)`` -- a norm of the
    offset, so symmetric.
    """

    def __init__(self, graph: SearchGraph, start: State, goal: State,
                 heuristic: str = 'octile', trace: bool = True):
        """Initialise (Figure 3, ``Initialize()``); no search yet."""
        _check_heuristic(graph, heuristic)
        for name, s in (('start', start), ('goal', goal)):
            if not graph.is_valid(s):
                raise ReplanError(f'{name} {s!r} is not a valid state')
        self.graph = graph
        self.heuristic = heuristic
        self.start = start
        self.last = start
        self.goal = goal
        self.km = 0.0
        self.g: Dict[State, float] = {}
        self.rhs: Dict[State, float] = {goal: 0.0}
        self._heap: List[tuple] = []
        self._entry: Dict[State, int] = {}   # state -> live heap seq
        self._seq = 0
        self.round = 0
        self.trace = ReplanTrace() if trace else None
        self.expansions = 0      # expand + raise pops, all rounds
        self.round_expansions: List[int] = []
        self._insert(goal)

    # -- values -------------------------------------------------------------

    def g_of(self, s: State) -> float:
        """Return ``g(s)`` (infinity if never set)."""
        return self.g.get(s, INF)

    def rhs_of(self, s: State) -> float:
        """Return ``rhs(s)`` (infinity if never set)."""
        return self.rhs.get(s, INF)

    def h(self, s: State) -> float:
        """Return the heuristic estimate from the start to ``s``."""
        return self.graph.heuristic(self.heuristic, s, self.start)

    def key(self, s: State) -> Tuple[float, float]:
        """Return ``CalculateKey(s)``."""
        m = min(self.g_of(s), self.rhs_of(s))
        return (m + self.h(s) + self.km, m)

    # -- the queue (lazy deletion: a state's live entry is its last seq) ----

    def _insert(self, s: State) -> None:
        k = self.key(s)
        self._seq += 1
        self._entry[s] = self._seq
        heapq.heappush(self._heap, (k[0], k[1], self._seq, s))

    def _remove(self, s: State) -> None:
        self._entry.pop(s, None)

    def _clean(self) -> None:
        h = self._heap
        while h and self._entry.get(h[0][3]) != h[0][2]:
            heapq.heappop(h)

    def _peek(self):
        """
        Return the smallest live entry under :func:`key_less`, or None.

        The heap orders raw floats, so two first components within
        KEY_EPS can be in either order there while the tolerant order
        decides by the second component. Every live entry within KEY_EPS
        of the heap's minimum is therefore considered (measured: without
        this, an entry ``(25.142135623730955, 5.41)`` sat behind
        ``(25.14213562373095, 11.66)`` and a replan stopped with the start
        resting on a stale neighbour).
        """
        self._clean()
        h = self._heap
        if not h:
            return None
        k1 = h[0][0]
        near = []
        while h and h[0][0] <= k1 + KEY_EPS:
            e = heapq.heappop(h)
            if self._entry.get(e[3]) == e[2]:
                near.append(e)
        for e in near:
            heapq.heappush(h, e)
        return min(near, key=lambda e: (e[1], e[2])) if near else None

    def top_key(self) -> Tuple[float, float]:
        """Return the smallest live key, or ``(inf, inf)``."""
        e = self._peek()
        return (e[0], e[1]) if e is not None else (INF, INF)

    def queued(self) -> int:
        """Return how many states are queued."""
        return len(self._entry)

    # -- the graph's two directions -----------------------------------------

    def succ(self, s: State) -> Iterable[State]:
        """Return the successors of ``s`` (none if ``s`` is not valid)."""
        if not self.graph.is_valid(s):
            return ()
        return self.graph.neighbours(s)

    def pred(self, s: State) -> Iterable[State]:
        """Return the predecessors of ``s`` (module doc: symmetric fallback)."""
        fn = getattr(self.graph, 'predecessors', None)
        if fn is not None:
            return fn(s)
        # An invalid state is never queued (g = rhs = inf), so it is never
        # popped; its former predecessors are re-checked through the
        # caller's affected set (grid_changes) instead.
        return self.graph.neighbours(s) if self.graph.is_valid(s) else ()

    # -- Figure 3 -------------------------------------------------------------

    def update_vertex(self, u: State) -> None:
        """``UpdateVertex(u)``."""
        if u != self.goal:
            best = INF
            for s in self.succ(u):
                c = self.graph.edge_cost(u, s) + self.g_of(s)
                if c < best:
                    best = c
            if best == INF:
                self.rhs.pop(u, None)
            else:
                self.rhs[u] = best
        self._remove(u)
        if self.g_of(u) != self.rhs_of(u):
            self._insert(u)
            self._event(UPDATE, u)

    def compute(self) -> bool:
        """``ComputeShortestPath()``; return whether a path exists."""
        n = 0
        while (key_less(self.top_key(), self.key(self.start))
               or self.rhs_of(self.start) != self.g_of(self.start)):
            e = self._peek()
            if e is None:
                break
            k_old, u = (e[0], e[1]), e[3]
            del self._entry[u]          # its heap tuple is now stale
            k_new = self.key(u)
            if key_less(k_old, k_new):
                self._insert(u)
            elif self.g_of(u) > self.rhs_of(u):
                self.g[u] = self.rhs_of(u)
                n += 1
                self._event(EXPAND, u)
                for s in self.pred(u):
                    self.update_vertex(s)
            else:
                self.g.pop(u, None)
                n += 1
                self._event(RAISE, u)
                for s in list(self.pred(u)) + [u]:
                    self.update_vertex(s)
        self.expansions += n
        self.round_expansions.append(n)
        found = self.g_of(self.start) < INF
        if found:
            for s in self.path():
                self._event(PATH, s)
        return found

    def path(self) -> List[State]:
        """
        Return the plan from ``start`` to ``goal``, or ``[]`` if none.

        Each step moves to the successor minimising ``c(s, s') + g(s')``;
        ties go to the first in the graph's neighbour order.
        """
        if self.g_of(self.start) == INF:
            return []
        out, s, limit = [self.start], self.start, len(self.g) + 1
        while s != self.goal:
            best, nxt = INF, None
            for t in self.succ(s):
                c = self.graph.edge_cost(s, t) + self.g_of(t)
                if c < best:
                    best, nxt = c, t
            if nxt is None or len(out) > limit:
                return []
            out.append(nxt)
            s = nxt
        return out

    def path_cost(self, path: Sequence[State]) -> float:
        """Return the sum of edge costs along ``path`` on the current graph."""
        return sum(self.graph.edge_cost(a, b) for a, b in zip(path, path[1:]))

    # -- the robot and the world ----------------------------------------------

    def move_to(self, s: State) -> None:
        """Record that the robot stepped onto ``s`` (``s_start = s``)."""
        self.start = s
        self._event(MOVE, s)

    def apply_changes(self, graph: SearchGraph, affected: Sequence[State]
                      ) -> None:
        """
        Switch to the changed ``graph`` and repair (no search yet).

        ``affected`` must hold every state whose OUT-edges (their set or
        their costs) differ between the old graph and ``graph``, in a
        deterministic order (:func:`grid_changes` computes it for grids).
        Figure 3: ``km += h(last, start); last = start``, then
        ``UpdateVertex`` on each. A state that is no longer valid loses its
        ``g`` as well, so nothing can route through it.
        """
        self.graph = graph
        self.round += 1
        self.km += self.graph.heuristic(self.heuristic, self.last,
                                        self.start)
        self.last = self.start
        if not graph.is_valid(self.goal):
            raise ReplanError('the goal became invalid')
        for u in affected:
            self._event(CHANGE, u)
            if not graph.is_valid(u):
                self.g.pop(u, None)
            self.update_vertex(u)

    # -- tracing ------------------------------------------------------------------

    def _event(self, kind: int, s: State) -> None:
        if self.trace is not None:
            self.trace.add(kind, self.graph.locate(s), self.g_of(s),
                           self.rhs_of(s), self.round)


def _check_heuristic(graph, name: str) -> None:
    mm = getattr(graph, 'move_model', None)
    if mm is None:
        return
    from .heuristics import analyse
    rep = analyse(name, mm)
    if not rep.consistent:
        raise ReplanError(f'D* Lite needs a consistent heuristic: '
                          f'{rep.reason}')


def grid_changes(old, new) -> Tuple[List[Tuple[int, int]],
                                    List[Tuple[int, int]]]:
    """
    Return ``(changed, affected)`` cells between two same-sized grids.

    ``changed``: cells whose occupancy or cost differs, row-major.
    ``affected``: every cell whose out-edges may differ -- each changed
    cell and its 8 neighbours (an edge INTO a changed cell is priced by
    its cost; a diagonal PAST it is allowed or not by the corner rule) --
    row-major, without repeats. Blocked cells are included: the algorithm
    must forget their ``g``.
    """
    if (old.width, old.height) != (new.width, new.height):
        raise ReplanError('the grids differ in size')
    changed = []
    for r in range(old.height):
        for c in range(old.width):
            if (old.is_blocked((r, c)) != new.is_blocked((r, c))
                    or old.cost_at((r, c)) != new.cost_at((r, c))):
                changed.append((r, c))
    marks = set()
    for r, c in changed:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if 0 <= r + dr < old.height and 0 <= c + dc < old.width:
                    marks.add((r + dr, c + dc))
    affected = [(r, c) for r in range(old.height) for c in range(old.width)
                if (r, c) in marks]
    return changed, affected
