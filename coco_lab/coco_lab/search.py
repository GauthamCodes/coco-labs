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
Lab 1's five algorithms, and only five, each emitting a v1 trace.

========================= =============================================
``bfs``                   first-in-first-out; ignores edge costs
``dijkstra``              ``f = g``
``astar``                 ``f = g + h``
``greedy``                ``f = h``
``weighted_astar``        ``f = g + w * h``, ``w >= 0``
========================= =============================================

The algorithms see only the :class:`coco_lab.graph.SearchGraph` interface.

**Rules shared by all five** (each is part of what the property tests
prove, so none is incidental):

- *Goal test on expansion.* The search stops when the goal is popped, not
  when it is first pushed. This is what makes Dijkstra and A* optimal; BFS
  uses it too, so "expansions" means the same thing for all five.
- *Closed states are final.* A popped state is never reopened. With a
  consistent heuristic A* never needs to; weighted A* with a consistent
  heuristic still meets its ``w x optimal`` bound without reopening
  (Likhachev, Gordon and Thrun, ARA*, NIPS 2003); greedy best-first
  never reopens by definition.
- *Relaxation on the open list.* If a cheaper path reaches a state that
  is still open, its ``g`` and parent are updated and it is re-queued at
  its new priority -- a ``relax`` event. BFS never relaxes: the first
  discovery of a state is final.
- *Determinism.* Neighbour order comes from the graph. Among equal
  priorities, the tie-break below decides, and after that insertion order
  does. No set or hash order is ever consulted, so the same inputs give
  the same trace in any process.

**Tie-breaking.** The queue is ordered by the key ``(f, t, seq)``:

``'low_h'`` (default)
    ``t`` is the heuristic *term* of ``f`` -- ``h`` for A* and greedy,
    ``w * h`` for weighted A*, ``0`` for Dijkstra. Among equal ``f`` it
    prefers the state estimated closest to the goal, equivalently the
    deepest (largest ``g``); then first in, first out.
``'fifo'`` (the alternative)
    ``t = 0``: among equal ``f``, pure insertion order.

Dijkstra's tie term is 0 under both policies, so ``weighted_astar`` with
``w = 0`` produces Dijkstra's trace exactly, not merely its cost. BFS is
first-in-first-out under both.

**The ``h`` and ``f`` columns.** ``h`` is always the chosen heuristic's
value at the state -- also for Dijkstra and BFS, which do not use it -- so
a learner can see it. ``f`` is the priority the queue actually used; for
BFS that is the state's depth in moves.
"""

from collections import deque
from dataclasses import dataclass
import heapq
import math
from typing import Callable, Dict, Generator, List, Optional, Tuple

from .graph import HEURISTICS, SearchGraph, State
from .trace import (EXPAND, MAJOR, NO_PARENT, PATH, PUSH, RELAX, SCHEMA,
                    Trace, TraceBuilder, VERSION)

ALGORITHMS = ('bfs', 'dijkstra', 'astar', 'greedy', 'weighted_astar')
TIE_BREAKS = ('low_h', 'fifo')

assert int(VERSION.split('.')[0]) == MAJOR


@dataclass
class SearchResult:
    """What a search returns: the path, its cost, and the full trace."""

    status: str
    path: List[State]
    cost: Optional[float]
    trace: Trace

    @property
    def found(self) -> bool:
        """Return whether a path was found."""
        return self.status == 'found'

    @property
    def expanded(self) -> List[tuple]:
        """Return the expanded states' locations, in expansion order."""
        return self.trace.cells('expand')


def _priority(algorithm: str, weight: float) -> Callable[[float, float],
                                                         tuple]:
    """Return ``(g, h) -> (f, heuristic term)`` for a heap-ordered search."""
    if algorithm == 'dijkstra':
        return lambda g, h: (g, 0.0)
    if algorithm == 'astar':
        return lambda g, h: (g + h, h)
    if algorithm == 'greedy':
        return lambda g, h: (h, h)
    if algorithm == 'weighted_astar':
        return lambda g, h: (g + weight * h, weight * h)
    raise AssertionError(algorithm)  # pragma: no cover


#: One event, in the v1 trace's column order (``coco_lab.trace.COLUMNS``):
#: ``(kind, row, col, sub, g, h, f, parent_row, parent_col, parent_sub)``.
EventRow = Tuple[int, int, int, int, float, float, float, int, int, int]


@dataclass
class SearchOutcome:
    """What :func:`search_events` returns once it is exhausted."""

    status: str
    path: List[State]
    cost: Optional[float]
    header: Dict[str, object]
    summary: Dict[str, object]


def search(graph: SearchGraph, start: State, goal: State,
           algorithm: str, heuristic: str = 'zero',
           weight: Optional[float] = None,
           tie_break: str = 'low_h') -> SearchResult:
    """
    Search ``graph`` from ``start`` to ``goal`` and trace every step.

    ``weight`` is required for ``weighted_astar`` (finite, ``>= 0``) and
    refused for every other algorithm, so a trace never records a weight
    that did nothing. Raises :class:`ValueError` for an unknown algorithm,
    heuristic or tie-break, and for an invalid start or goal -- a blocked
    start is a mistake to report, not a "no path" result.

    Since M1.4 this collects :func:`search_events` into a v1 trace; the
    traces are byte-identical to Lab 1's on the 1,000-map corpus
    (``test/test_golden_traces.py``).
    """
    return collect(search_events(graph, start, goal, algorithm, heuristic,
                                 weight, tie_break))


def collect(events, sink: Optional[Callable[[EventRow], None]] = None
            ) -> SearchResult:
    """
    Run a :func:`search_events` generator to the end into a v1 trace.

    ``sink``, if given, sees every row as it is made (the Arena hands rows
    to the renderer in batches while the search runs).
    """
    tb = TraceBuilder()
    add = tb.add
    try:
        while True:
            e = next(events)
            add(e[0], e[1:4], e[4], e[5], e[6], e[7:10])
            if sink is not None:
                sink(e)
    except StopIteration as stop:
        out: SearchOutcome = stop.value
    trace = Trace(out.header, tb.columns, out.summary)
    trace.validate()
    return SearchResult(out.status, out.path, out.cost, trace)


def search_events(graph: SearchGraph, start: State, goal: State,
                  algorithm: str, heuristic: str = 'zero',
                  weight: Optional[float] = None,
                  tie_break: str = 'low_h'
                  ) -> Generator[EventRow, None, SearchOutcome]:
    """
    Search, yielding each event AS THE SEARCH MAKES IT (M1.4).

    The same search as :func:`search`, one :data:`EventRow` per push,
    expand, relax and path event, in order; the caller decides how many to
    take before rendering (the Arena streams them in batches, so the
    planner visibly computes). The generator's return value
    (``StopIteration.value``, or ``outcome = yield from ...``) is a
    :class:`SearchOutcome` with the v1 header and summary. Arguments are
    validated now, at the call, not at the first ``next()``.
    """
    weight = _checked(graph, start, goal, algorithm, heuristic, weight,
                      tie_break)
    return _events(graph, start, goal, algorithm, heuristic, weight,
                   tie_break)


def _row(kind, loc, g, h, f, parent=NO_PARENT) -> EventRow:
    return (kind, loc[0], loc[1], loc[2], g, h, f,
            parent[0], parent[1], parent[2])


def _checked(graph, start, goal, algorithm, heuristic, weight, tie_break):
    """Validate a search request; return the weight to use."""
    if algorithm not in ALGORITHMS:
        raise ValueError(
            f'unknown algorithm {algorithm!r}; expected one of {ALGORITHMS}')
    if heuristic not in HEURISTICS:
        raise ValueError(
            f'unknown heuristic {heuristic!r}; expected one of {HEURISTICS}')
    if tie_break not in TIE_BREAKS:
        raise ValueError(
            f'unknown tie_break {tie_break!r}; expected one of {TIE_BREAKS}')
    if algorithm == 'weighted_astar':
        if weight is None or not (isinstance(weight, (int, float))
                                  and math.isfinite(weight) and weight >= 0):
            raise ValueError(
                f'weighted_astar needs a finite weight >= 0, got {weight!r}')
        weight = float(weight)
    elif weight is not None:
        raise ValueError(f'weight applies only to weighted_astar, '
                         f'not {algorithm!r}')
    if not graph.is_valid(start):
        raise ValueError(f'start {start!r} is blocked or outside the map')
    if not graph.is_valid(goal):
        raise ValueError(f'goal {goal!r} is blocked or outside the map')
    return weight


def _events(graph, start, goal, algorithm, heuristic, weight, tie_break):
    """Run the search itself, as a generator (validated by the caller)."""
    def h_of(s):
        return graph.heuristic(heuristic, s, goal)

    g: Dict[State, float] = {start: 0.0}
    parent: Dict[State, Optional[State]] = {start: None}
    counts = {'push': 0, 'relax': 0, 'expand': 0}

    def loc(s):
        return graph.locate(s) if s is not None else NO_PARENT

    if algorithm == 'bfs':
        reached = yield from _bfs(graph, start, goal, g, parent, counts,
                                  h_of, loc)
    else:
        reached = yield from _best_first(graph, start, goal, g, parent,
                                         counts, h_of, loc,
                                         _priority(algorithm, weight),
                                         tie_break)

    header = {
        'schema': SCHEMA,
        'version': VERSION,
        'algorithm': algorithm,
        'heuristic': heuristic,
        'weight': weight,
        'tie_break': tie_break,
        'start': list(graph.locate(start)),
        'goal': list(graph.locate(goal)),
        'graph': _describe(graph),
    }

    if not reached:
        summary = {'status': 'no_path', 'expansions': counts['expand'],
                   'pushes': counts['push'], 'relaxes': counts['relax'],
                   'path_cost': None, 'path_length': None,
                   'path_steps': None}
        return SearchOutcome('no_path', [], None, header, summary)

    path = [goal]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])
    path.reverse()
    length = 0.0
    for i, s in enumerate(path):
        p = path[i - 1] if i else None
        yield _row(PATH, loc(s), g[s], h_of(s), g[s], loc(p))
        if p is not None:
            (r0, c0, _), (r1, c1, _) = loc(p), loc(s)
            length += math.hypot(r1 - r0, c1 - c0)
    summary = {'status': 'found', 'expansions': counts['expand'],
               'pushes': counts['push'], 'relaxes': counts['relax'],
               'path_cost': g[goal], 'path_length': length,
               'path_steps': len(path) - 1}
    return SearchOutcome('found', path, g[goal], header, summary)


def suboptimality_bound(algorithm: str, report,
                        weight: Optional[float] = None) -> Optional[float]:
    """
    Return ``B`` such that the path found costs at most ``B x optimal``.

    ``report`` is :func:`coco_lab.heuristics.analyse` for the heuristic on
    the graph's move model. ``None`` means no guarantee holds on every map.
    This is the number the UI shows next to the weighted-A* slider; the
    property tests check that it holds.

    - ``dijkstra``: 1.
    - ``astar``: 1 when the heuristic is consistent; otherwise ``None``,
      because a closed state is never reopened.
    - ``weighted_astar``: ``max(1, w)`` when the heuristic is consistent.
      For ``w <= 1``, ``w * h`` is itself consistent, so the search is
      optimal; for ``w > 1``, the ``w x optimal`` bound holds without
      reopening (Likhachev, Gordon and Thrun, ARA*, NIPS 2003).
    - ``greedy``: ``None``; it ignores ``g``.
    - ``bfs``: ``None``; it is optimal in steps, not in cost.
    """
    if algorithm not in ALGORITHMS:
        raise ValueError(
            f'unknown algorithm {algorithm!r}; expected one of {ALGORITHMS}')
    if algorithm == 'weighted_astar':
        if weight is None or not (isinstance(weight, (int, float))
                                  and math.isfinite(weight) and weight >= 0):
            raise ValueError(
                f'weighted_astar needs a finite weight >= 0, got {weight!r}')
    elif weight is not None:
        raise ValueError(f'weight applies only to weighted_astar, '
                         f'not {algorithm!r}')
    if algorithm == 'dijkstra':
        return 1.0
    if algorithm in ('greedy', 'bfs') or not report.consistent:
        return None
    if algorithm == 'astar':
        return 1.0
    return max(1.0, float(weight))


def _describe(graph) -> Dict[str, object]:
    describe = getattr(graph, 'describe', None)
    return describe() if callable(describe) else {'kind': type(graph).__name__}


def _edge(graph, a, b) -> float:
    c = graph.edge_cost(a, b)
    if not (math.isfinite(c) and c >= 0):
        raise ValueError(f'edge {a!r} -> {b!r} has cost {c!r}; '
                         f'costs must be finite and >= 0')
    return c


def _bfs(graph, start, goal, g, parent, counts, h_of, loc):
    """Yield BFS's events; return whether the goal was expanded."""
    depth = {start: 0}
    queue = deque([start])
    yield _row(PUSH, loc(start), 0.0, h_of(start), 0.0)
    counts['push'] += 1
    while queue:
        s = queue.popleft()
        yield _row(EXPAND, loc(s), g[s], h_of(s), depth[s], loc(parent[s]))
        counts['expand'] += 1
        if s == goal:
            return True
        for n in graph.neighbours(s):
            if n in depth:
                continue
            depth[n] = depth[s] + 1
            g[n] = g[s] + _edge(graph, s, n)
            parent[n] = s
            queue.append(n)
            yield _row(PUSH, loc(n), g[n], h_of(n), depth[n], loc(s))
            counts['push'] += 1
    return False


def _best_first(graph, start, goal, g, parent, counts, h_of, loc,
                priority, tie_break):
    """Yield a best-first search's events; return whether it reached goal."""
    use_tie = tie_break == 'low_h'
    heap = []
    latest: Dict[State, int] = {}  # seq of each open state's live entry
    closed = set()
    seq = 0

    def push(s, h):
        nonlocal seq
        f, term = priority(g[s], h)
        heapq.heappush(heap, (f, term if use_tie else 0.0, seq, s))
        latest[s] = seq
        seq += 1
        return f

    h0 = h_of(start)
    yield _row(PUSH, loc(start), 0.0, h0, push(start, h0))
    counts['push'] += 1
    while heap:
        f, _, entry, s = heapq.heappop(heap)
        if latest.get(s) != entry:
            continue  # superseded by a relax; the live entry is still queued
        del latest[s]
        closed.add(s)
        yield _row(EXPAND, loc(s), g[s], h_of(s), f, loc(parent[s]))
        counts['expand'] += 1
        if s == goal:
            return True
        for n in graph.neighbours(s):
            if n in closed:
                continue
            ng = g[s] + _edge(graph, s, n)
            if n not in g:
                kind = PUSH
            elif ng < g[n]:
                kind = RELAX
            else:
                continue
            g[n] = ng
            parent[n] = s
            hn = h_of(n)
            yield _row(kind, loc(n), ng, hn, push(n, hn), loc(s))
            counts['push' if kind == PUSH else 'relax'] += 1
    return False
