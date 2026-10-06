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
Lab 4's search: where the robot should look next, given what it knows.

The robot is told one thing -- a colour. It knows its own map, the
regions where a target may stand, what it costs to drive to each and to
look, and how often its camera finds a target that is there. It does
NOT know which region holds the target. This module is everything it
does with that:

- a **belief** over the regions (the target is in exactly one);
- a **detection model**: ``d`` = P(found | the target is in the region
  surveyed). A survey never reports a target that is not there (a
  positive is confirmed by perception, approach and grasp), so a miss is
  evidence, not proof, whenever ``d < 1``;
- **Bayes' rule** on a miss: ``p_i <- p_i (1 - d) / (1 - p_i d)``, every
  other region rescaled by ``1 / (1 - p_i d)``;
- the **expected search cost** of a one-pass order, and the order that
  minimises it, found by exact enumeration (at most :data:`MAX_REGIONS`
  regions, so at most 40,320 orders);
- three teaching policies beside it -- nearest first, most likely first,
  and an order given by the learner -- so a learner can see where each
  is beaten;
- :func:`run_search`, a seeded Sketch of the whole loop, which keeps the
  truth in a different variable from everything a policy can read.

Costs are in **metres driven** (derived): the travel between places is
whatever the caller measured on its map (``travel_costs`` does it with
coco_lab's own A* on an occupancy map), and a survey adds the region's
fixed ``survey_cost`` (for COCO: up the ramp and back down it).

**The anti-cheat rule, structurally.** A policy is a function of a
:class:`SearchView` -- belief, searched regions, where the robot is, the
order it was given -- and of the :class:`SearchProblem`. Neither has a
field that could hold the truth. :func:`run_search` holds the truth and
uses it for exactly one thing: drawing a survey's outcome.
"""

from dataclasses import dataclass, field
import itertools
import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

SCHEMA = 'coco_lab.search_trace'
VERSION = '1.0'
MAJOR = 1

#: Enumerating every order is exact and, at this size, cheap.
MAX_REGIONS = 8
#: How many surveys one Sketch run may make before it stops.
MAX_SURVEYS = 64

POLICIES = ('expected_cost', 'nearest', 'most_likely', 'given')

#: Event kinds, in the order a step emits them.
KINDS = ('select', 'survey', 'mark', 'discover', 'exhausted', 'stopped')
KIND_CODE = {k: i for i, k in enumerate(KINDS)}

#: Probabilities closer than this are treated as equal when ranking.
EPS = 1e-12


class SearchError(ValueError):
    """A search problem, belief or trace that is not well formed."""


# -- the problem ------------------------------------------------------------------

@dataclass(frozen=True)
class Region:
    """
    One place a target may stand, and the places the robot uses there.

    ``approach`` is where the robot starts its survey (for COCO, the bay's
    pre-ramp pose); ``platform`` the area surveyed, as
    ``(x_min, x_max, y_min, y_max)``; ``survey_pose`` where the camera is
    when it looks, as ``(x, y, yaw)``; ``exit`` where the robot is once it
    has left (for COCO, back at the pre-ramp pose). World coordinates of
    the caller's choosing -- this module only draws and costs them.
    """

    id: str  # noqa: A003 -- the region's stable name
    label: str
    approach: Tuple[float, float]
    platform: Tuple[float, float, float, float]
    survey_pose: Tuple[float, float, float]
    exit: Tuple[float, float]  # noqa: A003
    survey_cost: float

    def to_dict(self) -> Dict[str, object]:
        """Plain JSON form."""
        return {'id': self.id, 'label': self.label,
                'approach': list(self.approach),
                'platform': list(self.platform),
                'survey_pose': list(self.survey_pose),
                'exit': list(self.exit), 'survey_cost': self.survey_cost}

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> 'Region':
        """Inverse of :meth:`to_dict`."""
        return cls(str(d['id']), str(d['label']), _pair(d['approach']),
                   tuple(float(v) for v in d['platform']),
                   tuple(float(v) for v in d['survey_pose']),
                   _pair(d['exit']), float(d['survey_cost']))


def _pair(v) -> Tuple[float, float]:
    return (float(v[0]), float(v[1]))


@dataclass(frozen=True)
class SearchProblem:
    """
    Everything the robot knows before it looks, and nothing else.

    ``travel[a][b]`` is the cost of driving from location ``a`` to region
    ``b``'s approach, where a location is ``start`` or a region id (the
    robot is at that region's exit). ``detection[i]`` is region ``i``'s
    ``d``. ``prior`` is the belief before any survey.
    """

    regions: Tuple[Region, ...]
    start: str
    start_xy: Tuple[float, float]
    travel: Dict[str, Dict[str, float]]
    detection: Tuple[float, ...]
    prior: Tuple[float, ...]
    meta: Dict[str, object] = field(default_factory=dict)

    @property
    def ids(self) -> Tuple[str, ...]:
        """Region ids, in index order."""
        return tuple(r.id for r in self.regions)

    @property
    def n(self) -> int:
        """Return the number of regions."""
        return len(self.regions)

    def index(self, region_id: str) -> int:
        """Index of ``region_id``; raises :class:`SearchError`."""
        try:
            return self.ids.index(region_id)
        except ValueError:
            raise SearchError(f'unknown region {region_id!r}') from None

    def leg(self, location: str, i: int) -> float:
        """Cost of driving from ``location`` to region ``i`` and looking."""
        return self.travel[location][self.regions[i].id] + \
            self.regions[i].survey_cost

    def validate(self) -> None:
        """Raise :class:`SearchError` unless the problem is well formed."""
        n = self.n
        if not 1 <= n <= MAX_REGIONS:
            raise SearchError(f'1..{MAX_REGIONS} regions, not {n}')
        ids = self.ids
        if len(set(ids)) != n or not all(_ok_id(i) for i in ids):
            raise SearchError(f'region ids must be unique short words: '
                              f'{ids}')
        if not _ok_id(self.start) or self.start in ids:
            raise SearchError(f'start {self.start!r} must be a short word '
                              f'that is not a region id')
        locations = (self.start,) + ids
        if set(self.travel) != set(locations):
            raise SearchError('travel must have a row per location')
        for a in locations:
            row = self.travel[a]
            if set(row) != set(ids):
                raise SearchError(f'travel[{a!r}] must cover every region')
            for b, c in row.items():
                if not (_finite(c) and c >= 0):
                    raise SearchError(f'travel[{a!r}][{b!r}] = {c!r}')
        for r in self.regions:
            if not (_finite(r.survey_cost) and r.survey_cost >= 0):
                raise SearchError(f'{r.id}: survey_cost {r.survey_cost!r}')
            if r.platform[0] > r.platform[1] or r.platform[2] > r.platform[3]:
                raise SearchError(f'{r.id}: platform bounds out of order')
        if len(self.detection) != n or not all(
                _finite(d) and 0.0 < d <= 1.0 for d in self.detection):
            raise SearchError('detection: one probability in (0, 1] per '
                              'region')
        check_belief(self.prior, n)

    def to_dict(self) -> Dict[str, object]:
        """Plain JSON form (the bundle's ``problem`` block)."""
        return {'regions': [r.to_dict() for r in self.regions],
                'start': self.start, 'start_xy': list(self.start_xy),
                'travel': {a: dict(sorted(row.items()))
                           for a, row in sorted(self.travel.items())},
                'detection': list(self.detection),
                'prior': list(self.prior), 'meta': dict(self.meta)}

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> 'SearchProblem':
        """Inverse of :meth:`to_dict`; validates."""
        try:
            p = cls(tuple(Region.from_dict(r) for r in d['regions']),
                    str(d['start']), _pair(d['start_xy']),
                    {str(a): {str(b): float(c) for b, c in row.items()}
                     for a, row in d['travel'].items()},
                    tuple(float(v) for v in d['detection']),
                    tuple(float(v) for v in d['prior']),
                    dict(d.get('meta') or {}))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise SearchError(f'bad problem: {exc}') from None
        p.validate()
        return p


def _ok_id(i) -> bool:
    return isinstance(i, str) and 0 < len(i) <= 32 and \
        all(c.isalnum() or c in '_-' for c in i)


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and \
        math.isfinite(v)


# -- belief -----------------------------------------------------------------------

def uniform(n: int) -> Tuple[float, ...]:
    """Return the belief that knows nothing: ``1/n`` everywhere."""
    if n < 1:
        raise SearchError('n must be >= 1')
    return tuple(1.0 / n for _ in range(n))


def normalise(weights: Sequence[float]) -> Tuple[float, ...]:
    """Scale non-negative weights to sum to one."""
    if not weights or not all(_finite(w) and w >= 0 for w in weights):
        raise SearchError(f'weights must be finite and >= 0: {weights}')
    s = math.fsum(weights)
    if s <= 0:
        raise SearchError('weights must not all be zero')
    return tuple(w / s for w in weights)


def check_belief(belief: Sequence[float], n: int) -> None:
    """Raise unless ``belief`` is ``n`` probabilities summing to one."""
    if len(belief) != n:
        raise SearchError(f'belief has {len(belief)} entries, not {n}')
    if not all(_finite(p) and 0.0 <= p <= 1.0 for p in belief):
        raise SearchError(f'belief entries must be in [0, 1]: {belief}')
    if abs(math.fsum(belief) - 1.0) > 1e-9:
        raise SearchError(f'belief must sum to 1, not {math.fsum(belief)}')


def update(belief: Sequence[float], i: int, found: bool,
           d: float) -> Tuple[float, ...]:
    """
    Bayes' rule after surveying region ``i``.

    ``found``: the target is in ``i`` (no false alarms), so the belief is
    one-hot. A miss: ``P(miss) = 1 - p_i d``; region ``i`` keeps
    ``p_i (1 - d)`` of its mass and every other region is rescaled.
    """
    n = len(belief)
    if not 0 <= i < n:
        raise SearchError(f'region index {i} out of range')
    if not (_finite(d) and 0.0 < d <= 1.0):
        raise SearchError(f'detection probability {d!r}')
    if found:
        return tuple(1.0 if j == i else 0.0 for j in range(n))
    miss = 1.0 - belief[i] * d
    if miss <= 0.0:
        raise SearchError(f'a miss in region {i} was impossible under this '
                          f'belief (p = {belief[i]}, d = {d})')
    out = [p / miss for p in belief]
    out[i] = belief[i] * (1.0 - d) / miss
    return normalise(out)


# -- expected cost ----------------------------------------------------------------

def plan_cost(problem: SearchProblem, belief: Sequence[float],
              location: str, order: Sequence[int]) -> Dict[str, object]:
    """
    Return the expected cost of surveying ``order`` once each.

    The search stops at the first discovery. With ``P_k`` the probability
    the discovery happens at step ``k`` (``p_{o_k} d_{o_k}``: the target is
    there and the camera finds it) and ``C_k`` the cost driven by the end
    of step ``k``::

        E = sum_k P_k C_k + (1 - sum_k P_k) C_last

    -- a search that finds nothing has driven the whole order. Returns
    ``expected``, ``p_find``, and per step ``leg``, ``cumulative`` and
    ``p_at``.
    """
    check_belief(belief, problem.n)
    if len(set(order)) != len(order) or not all(
            0 <= i < problem.n for i in order):
        raise SearchError(f'order {list(order)} must be distinct indices')
    legs, cum, p_at = [], [], []
    at, total = location, 0.0
    for i in order:
        leg = problem.leg(at, i)
        total += leg
        legs.append(leg)
        cum.append(total)
        p_at.append(belief[i] * problem.detection[i])
        at = problem.regions[i].id
    p_find = math.fsum(p_at)
    expected = math.fsum(p * c for p, c in zip(p_at, cum)) + \
        max(0.0, 1.0 - p_find) * total
    return {'expected': expected, 'p_find': p_find, 'leg': legs,
            'cumulative': cum, 'p_at': p_at}


def optimal_order(problem: SearchProblem, belief: Sequence[float],
                  location: str, remaining: Sequence[int]) -> Tuple[int, ...]:
    """
    Return the one-pass order over ``remaining`` of least expected cost.

    Exact: every permutation is costed. Ties go to the order that is
    first lexicographically by region index, so the answer is
    deterministic.
    """
    rem = sorted(set(remaining))
    if not rem:
        return ()
    best, best_e = None, math.inf
    for perm in itertools.permutations(rem):
        e = plan_cost(problem, belief, location, perm)['expected']
        if best is None or e < best_e - 1e-9 * max(1.0, abs(best_e)):
            best, best_e = perm, e
    return tuple(best)


def ratio_order(problem: SearchProblem, belief: Sequence[float],
                remaining: Sequence[int]) -> Tuple[int, ...]:
    """
    Sort by ``p_i d_i / c_i``, largest first (ties: region index).

    Optimal when each region's cost does not depend on where the robot
    comes from (the classic index rule; ``test_regionsearch`` proves it
    against :func:`optimal_order`). COCO's travel DOES depend on it, which
    is why the robot enumerates instead.
    """
    def key(i):
        c = problem.leg(problem.start, i)
        r = math.inf if c == 0 else belief[i] * problem.detection[i] / c
        return (-r, i)
    return tuple(sorted(set(remaining), key=key))


# -- what a policy may see --------------------------------------------------------

@dataclass(frozen=True)
class SearchView:
    """The robot's state of knowledge. There is no field for the truth."""

    belief: Tuple[float, ...]
    searched: Tuple[int, ...]
    location: str
    given_order: Tuple[int, ...] = ()

    def remaining(self, n: int) -> Tuple[int, ...]:
        """Regions not yet surveyed, in index order."""
        return tuple(i for i in range(n) if i not in self.searched)


def choose(policy: str, problem: SearchProblem,
           view: SearchView) -> Optional[int]:
    """
    Return the next region ``policy`` would survey (None: none remain).

    ``expected_cost``: the first step of :func:`optimal_order`, recomputed
    from the current belief (the robot's policy). ``nearest``: cheapest
    next leg. ``most_likely``: largest ``p d``. ``given``: the next
    unsearched region of ``view.given_order`` (the learner's), then None.
    Ties always go to the lower region index.
    """
    rem = view.remaining(problem.n)
    if policy == 'given':
        for i in view.given_order:
            if i not in view.searched:
                return i
        return None
    if not rem:
        return None
    if policy == 'expected_cost':
        return optimal_order(problem, view.belief, view.location, rem)[0]
    if policy == 'nearest':
        return min(rem, key=lambda i: (problem.leg(view.location, i), i))
    if policy == 'most_likely':
        return min(rem, key=lambda i: (
            -round(view.belief[i] * problem.detection[i], 12), i))
    raise SearchError(f'unknown policy {policy!r}; expected one of '
                      f'{POLICIES}')


def candidate_costs(problem: SearchProblem,
                    view: SearchView) -> List[Optional[float]]:
    """
    Return, per region, the expected cost of surveying it next.

    The rest are then surveyed in their best order; None for a searched
    region. These are what the robot compares.
    """
    # Exact: every tail is costed as part of the whole plan. (Ranking the
    # tail on its own is NOT equivalent: the failure term weights the
    # tail's total length, which depends on its order.)
    rem = view.remaining(problem.n)
    out: List[Optional[float]] = [None] * problem.n
    for i in rem:
        rest = [j for j in rem if j != i]
        out[i] = min(plan_cost(problem, view.belief, view.location,
                               (i,) + perm)['expected']
                     for perm in itertools.permutations(rest))
    return out


# -- the trace --------------------------------------------------------------------

@dataclass
class SearchTrace:
    """
    One search, step by step: columnar events plus a belief per event.

    Columns: ``kind`` (index into :data:`KINDS`), ``region`` (-1 if none),
    ``outcome`` (1 found, 0 miss, -1 not a survey), ``cost`` (metres driven
    by then, derived). ``belief`` is ``n_events x n_regions`` (after the
    event); ``candidates`` the same shape, :func:`candidate_costs` at each
    ``select`` (NaN elsewhere and for searched regions).
    """

    header: Dict[str, object]
    kind: List[int]
    region: List[int]
    outcome: List[int]
    cost: List[float]
    belief: List[float]
    candidates: List[float]
    summary: Dict[str, object]

    @property
    def n_events(self) -> int:
        """Return the number of events."""
        return len(self.kind)

    def validate(self, n_regions: int) -> None:
        """Raise :class:`SearchError` unless the columns agree."""
        k = self.n_events
        for name in ('region', 'outcome', 'cost'):
            if len(getattr(self, name)) != k:
                raise SearchError(f'trace.{name} has the wrong length')
        if len(self.belief) != k * n_regions or \
                len(self.candidates) != k * n_regions:
            raise SearchError('trace belief/candidates must be '
                              'n_events x n_regions')
        if not all(0 <= c < len(KINDS) for c in self.kind):
            raise SearchError('trace.kind out of range')
        if not all(-1 <= r < n_regions for r in self.region):
            raise SearchError('trace.region out of range')
        if not all(o in (-1, 0, 1) for o in self.outcome):
            raise SearchError('trace.outcome must be -1, 0 or 1')
        if any(b < a - 1e-12 for a, b in zip(self.cost, self.cost[1:])):
            raise SearchError('trace.cost must not decrease')
        for e in range(k):
            check_belief(self.belief[e * n_regions:(e + 1) * n_regions],
                         n_regions)


def _check_policy(problem: SearchProblem, policy: str,
                  given_order: Sequence[int]) -> None:
    if policy not in POLICIES:
        raise SearchError(f'unknown policy {policy!r}')
    n = problem.n
    if policy == 'given':
        if not given_order or len(set(given_order)) != len(given_order) \
                or not all(0 <= i < n for i in given_order):
            raise SearchError('given_order must be distinct region indices')


def _search_loop(problem: SearchProblem, policy: str, observe,
                 given: Tuple[int, ...], passes: int, limit: int,
                 header: Dict[str, object]) -> Tuple[SearchTrace,
                                                     Dict[str, object]]:
    """
    Run the select / survey / mark loop; ``observe(i)`` says what a look saw.

    ``observe`` returns True (found), False (a miss) or None (no more
    looks: the run stopped, e.g. a recording that ends there). Everything
    else -- the choice, Bayes, the costs -- is the policy's and this
    module's, and is identical whoever supplies the outcomes.
    """
    n = problem.n
    tr = SearchTrace(header, [], [], [], [], [], [], {})
    nan = [math.nan] * n

    def emit(kind, region, outcome, cost, belief, cands=None):
        tr.kind.append(KIND_CODE[kind])
        tr.region.append(region)
        tr.outcome.append(outcome)
        tr.cost.append(cost)
        tr.belief.extend(belief)
        tr.candidates.extend(nan if cands is None else
                             [math.nan if c is None else c for c in cands])

    belief = tuple(problem.prior)
    searched: Tuple[int, ...] = ()
    location = problem.start
    cost, surveys, done_passes = 0.0, 0, 1
    order: List[int] = []
    discovered: Optional[int] = None
    status = 'exhausted'
    contradicted = False
    while True:
        view = SearchView(belief, searched, location, given)
        nxt = choose(policy, problem, view)
        if nxt is None and policy != 'given' and done_passes < passes and \
                any(belief[i] > EPS for i in range(n)):
            searched, done_passes = (), done_passes + 1
            view = SearchView(belief, searched, location, given)
            nxt = choose(policy, problem, view)
        if nxt is None:
            status = 'exhausted'
            emit('exhausted', -1, -1, cost, belief)
            break
        if surveys >= limit:
            status = 'stopped'
            emit('stopped', -1, -1, cost, belief)
            break
        found = observe(nxt)
        if found is None:
            status = 'stopped'
            emit('stopped', -1, -1, cost, belief)
            break
        emit('select', nxt, -1, cost, belief,
             candidate_costs(problem, view))
        cost += problem.leg(location, nxt)
        surveys += 1
        order.append(nxt)
        emit('survey', nxt, 1 if found else 0, cost, belief)
        location = problem.regions[nxt].id
        if found:
            belief = update(belief, nxt, True, problem.detection[nxt])
            discovered = nxt
            status = 'discovered'
            emit('discover', nxt, 1, cost, belief)
            break
        if belief[nxt] * problem.detection[nxt] >= 1.0:
            # The model said the target had to be here and the camera
            # never misses: a miss contradicts "there is a target". Only
            # reachable with no target placed and d = 1.
            contradicted = True
            status = 'exhausted'
            emit('exhausted', nxt, -1, cost, belief)
            break
        belief = update(belief, nxt, False, problem.detection[nxt])
        searched = searched + (nxt,)
        emit('mark', nxt, 0, cost, belief)

    summary = {
        'status': status,
        'order': [problem.ids[i] for i in order],
        'surveys': surveys,
        'discovered': None if discovered is None else problem.ids[discovered],
        'discovered_at': None if discovered is None else surveys,
        'cost': round(cost, 9),
        'model_contradicted': contradicted,
    }
    return tr, summary


def run_search(problem: SearchProblem, policy: str, truth: Optional[int],
               *, seed: int = 0, true_detection: Optional[Sequence[float]]
               = None, max_surveys: Optional[int] = None,
               given_order: Sequence[int] = (), passes: int = 1
               ) -> SearchTrace:
    """
    Simulate one search in Sketch, seeded and deterministic.

    ``truth`` is the region holding the target (None: no target anywhere)
    and is read in exactly one place: drawing whether a survey of that
    region finds it, with probability ``true_detection[i]`` (default: the
    robot's own model). The policy sees only a :class:`SearchView`.

    ``max_surveys`` stops the search early -- "give up after A" -- and the
    run ends ``stopped``. ``passes`` > 1 lets the robot start over on the
    regions it has already searched once every region has been searched
    (it is a model with ``d < 1``: a miss is not proof).
    """
    problem.validate()
    n = problem.n
    if truth is not None and not 0 <= truth < n:
        raise SearchError(f'truth {truth} out of range')
    _check_policy(problem, policy, given_order)
    if not 1 <= passes <= 4:
        raise SearchError('passes must be 1..4')
    td = tuple(true_detection) if true_detection is not None \
        else problem.detection
    if len(td) != n or not all(_finite(d) and 0 <= d <= 1 for d in td):
        raise SearchError('true_detection: one probability per region')
    limit = MAX_SURVEYS if max_surveys is None else int(max_surveys)
    if not 0 <= limit <= MAX_SURVEYS:
        raise SearchError(f'max_surveys must be 0..{MAX_SURVEYS}')
    rng = random.Random(seed)

    def observe(nxt):
        # The truth is read here, and only here.
        found = truth == nxt and rng.random() < td[nxt]
        return found

    tr, summary = _search_loop(
        problem, policy, observe, tuple(given_order), passes, limit,
        {'schema': SCHEMA, 'version': VERSION, 'source': 'sketch',
         'policy': policy, 'seed': seed,
         'given_order': [problem.ids[i] for i in given_order],
         'max_surveys': max_surveys, 'passes': passes,
         'true_detection': list(td)})
    summary['truth'] = None if truth is None else problem.ids[truth]
    tr.summary = summary
    tr.validate(n)
    return tr


def replay_search(problem: SearchProblem, policy: str,
                  outcomes: Sequence[Tuple[str, bool]],
                  given_order: Sequence[int] = ()) -> SearchTrace:
    """
    Rebuild a RECORDED search from its observations alone.

    ``outcomes`` is what the real mission saw, ``(region_id, found)`` in
    order. The policy chooses each region again from the same belief; a
    recording whose region differs from that choice did not follow the
    policy, and is refused. The result is the trace the robot computed --
    belief, candidate costs, bookkeeping -- with no truth anywhere in it.
    A recording that ends before a find or exhaustion ends ``stopped``.
    """
    problem.validate()
    _check_policy(problem, policy, given_order)
    queue = list(outcomes)

    def observe(nxt):
        if not queue:
            return None
        rid, found = queue.pop(0)
        if rid != problem.ids[nxt]:
            raise SearchError(f'recording surveyed {rid} where policy '
                              f'{policy} chooses {problem.ids[nxt]}')
        return bool(found)

    tr, summary = _search_loop(
        problem, policy, observe, tuple(given_order), 1, MAX_SURVEYS,
        {'schema': SCHEMA, 'version': VERSION, 'source': 'recorded',
         'policy': policy,
         'given_order': [problem.ids[i] for i in given_order]})
    if queue:
        raise SearchError(f'{len(queue)} recorded looks after the search '
                          f'ended')
    summary['truth'] = None
    tr.summary = summary
    tr.validate(problem.n)
    return tr


def challenge_passed(trace: SearchTrace) -> bool:
    """
    Return whether the search passed Lab 4's challenge: target found.

    Stopping early -- giving up after region A when the target is in C --
    is a failure, whatever it saved.
    """
    return trace.summary.get('status') == 'discovered'


def replay_decisions(problem: SearchProblem, policy: str,
                     outcomes: Sequence[Tuple[str, bool]],
                     given_order: Sequence[int] = ()) -> List[str]:
    """
    Re-derive a recorded search's choices from its observations alone.

    ``outcomes`` is the recorded ``(region_id, found)`` sequence. Returns
    the region ``policy`` would have chosen before each survey; a recorded
    run whose order differs did not follow ``policy``. Used to check that
    the real mission chose what coco_lab says it should have.
    """
    problem.validate()
    belief = tuple(problem.prior)
    searched: Tuple[int, ...] = ()
    location = problem.start
    out = []
    for rid, found in outcomes:
        view = SearchView(belief, searched, location, tuple(given_order))
        nxt = choose(policy, problem, view)
        out.append(None if nxt is None else problem.ids[nxt])
        i = problem.index(rid)
        belief = update(belief, i, bool(found), problem.detection[i])
        if found:
            break
        searched = searched + (i,)
        location = rid
    return out


# -- travel costs from a map ------------------------------------------------------

def travel_costs(lab_map, places: Dict[str, Tuple[float, float]],
                 targets: Sequence[str], radius: float,
                 offset: Tuple[float, float] = (0.0, 0.0)
                 ) -> Dict[str, Dict[str, float]]:
    """
    Shortest-path lengths in metres between named places, on ``lab_map``.

    coco_lab's own A* (8-connected, octile, no corner cutting) on the map
    inflated by ``radius``; unknown cells blocked, as Nav2's global
    planner is configured. ``travel[a][b]`` for every place ``a`` and
    every ``b`` in ``targets``. ``offset`` is added to every place to put
    it in the map's frame (COCO: map = world + (2, 0)). Raises
    :class:`SearchError` when two places are not connected.
    """
    from .search import search
    from .sketch import _inflated_grid_map, _nearest_free, SketchMap
    inflated = _inflated_grid_map(SketchMap(lab_map), radius)
    g = inflated.to_grid(connectivity=8)
    cells = {}
    for name, xy in places.items():
        c = inflated.cell_at(xy[0] + offset[0], xy[1] + offset[1])
        c = None if c is None else _nearest_free(g, c)
        if c is None:
            raise SearchError(f'place {name} {xy} has no free cell near it')
        cells[name] = c
    out: Dict[str, Dict[str, float]] = {}
    for a in places:
        row = {}
        for b in targets:
            if cells[a] == cells[b]:
                row[b] = 0.0
                continue
            res = search(g, cells[a], cells[b], 'astar', 'octile')
            if res.path is None:
                raise SearchError(f'no path from {a} to {b}')
            row[b] = round(res.cost * lab_map.resolution, 6)
        out[a] = row
    return out


# -- COCO's bays as a search problem ----------------------------------------------

def bay_regions(target_regions, climb_end_x: float) -> Tuple[Region, ...]:
    """
    Return COCO's regions, built from ``coco_config``'s TARGET_REGIONS.

    Duck-typed (coco_lab never imports coco_config): each item needs
    ``region_id``, ``bay_y``, ``pre_ramp_pose`` and ``platform_bounds``.
    The semantic places: approach = the pre-ramp pose; the survey pose is
    the end of the climb, facing the platform; the exit is the pre-ramp
    pose again, because the robot leaves by backing down the ramp it
    climbed. The survey costs the ramp up and back: ``2 (climb_end_x -
    pre_ramp_x)`` metres (derived).
    """
    out = []
    for k, r in enumerate(target_regions, start=1):
        pre = (float(r.pre_ramp_pose[0]), float(r.pre_ramp_pose[1]))
        out.append(Region(
            str(r.region_id), f'Bay {k}', pre,
            tuple(float(v) for v in r.platform_bounds),
            (float(climb_end_x), float(r.bay_y), 0.0), pre,
            round(2.0 * (float(climb_end_x) - pre[0]), 9)))
    return tuple(out)


def bay_problem(regions: Sequence[Region], start_xy: Tuple[float, float],
                travel: Dict[str, Dict[str, float]], detection: float,
                prior: Optional[Sequence[float]] = None,
                meta: Optional[Dict[str, object]] = None) -> SearchProblem:
    """
    Return a :class:`SearchProblem` over ``regions`` starting at home.

    ``prior`` None is uniform: the robot is told a colour, not where it
    is, and the frozen colour->bay table is the TOLD channel.
    """
    n = len(regions)
    p = SearchProblem(tuple(regions), 'home', _pair(start_xy),
                      {a: dict(row) for a, row in travel.items()},
                      tuple(float(detection) for _ in range(n)),
                      uniform(n) if prior is None else normalise(prior),
                      dict(meta or {}))
    p.validate()
    return p


def places_of(regions: Sequence[Region], start_xy: Tuple[float, float]
              ) -> Dict[str, Tuple[float, float]]:
    """
    ``{'home': start, region id: its exit}`` -- where a leg can begin.

    A region's exit is also its approach for COCO; travel is measured TO
    approaches (``travel_costs``' targets are the region ids, placed at
    their approaches), so the two coincide by construction here.
    """
    out = {'home': _pair(start_xy)}
    for r in regions:
        if r.exit != r.approach:
            raise SearchError(f'{r.id}: travel_costs needs exit == approach')
        out[r.id] = r.approach
    return out
