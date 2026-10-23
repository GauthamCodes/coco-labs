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
Race the planner's ghost (M4.8; README §7 M4.8). MODEL.

A level is a start (the World Spec's), a goal and a finish radius on a
World Spec. **The ghost** is the Arena model following the planner's path
with a reference tracker under the same limits as a person: it plans once
(on a throwaway Arena, so planning leaves no state behind) and then drives
a fresh Arena with ``teleop`` inputs only, inside the teleop limits, one
per change of command. Its input log is a submission like any other, so it
is deterministic, its result is reproducible, and it is scored by the same
function as a person's drive (:func:`drive`).

**Scores** (each shown): the time to the finish (ticks x dt; ticks are an
integer, so no engine's last bit can move it), the ground-truth path
length, and the contacts (ticks the robot stopped against something).
**Stars** come from the ghost's own result (``level['reference']``):

- one: finish within the level's ``max_ticks``;
- two: finish within ``SLOW`` x the ghost's time, with no more contacts
  than the ghost;
- three: beat the ghost's time (strictly), with no more contacts than the
  ghost and a path at most ``LONG`` x the ghost's.

The ghost itself earns two stars: three is for beating it.

**The tracker** is pure pursuit, the textbook form (README's Move lens
names it): the target is the first path point at least ``LOOKAHEAD``
ahead of the closest one; the robot turns on the spot while the target is
more than ``SPIN`` off its nose, else drives at the teleop maximum scaled
by the cosine of the heading error (and, within ``LOOKAHEAD`` of the goal,
by the distance left), with ``w = 2 v sin(a) / L``; both
clamped to the teleop limits; commands rounded to ``Q`` so the log keeps
one input per change.
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

LOOKAHEAD = 0.45
#: the dense path's spacing (m) and how far ahead progress may jump in one tick (points)
STEP = 0.05
WINDOW = 40
SPIN = math.radians(50)
Q = 0.01
SLOW = 1.2
LONG = 1.1
RACE_KINDS = ('teleop', 'stop')


class RaceError(ValueError):
    """A race that is not one (bad level or input log)."""


def _arena(spec, level):
    from .arena import Arena
    return Arena(spec, int(level['seed']), planner=level.get('planner', 'astar'))


def ghost_path(spec, level) -> List[Tuple[float, float]]:
    """Return the planner's path to the goal: waypoints, map frame (a throwaway Arena plans it)."""
    a = _arena(spec, level)
    a.goal = (float(level['goal'][0]), float(level['goal'][1]))
    a._plan_begin()
    plan = a._plan_finish()
    if not plan.waypoints:
        raise RaceError(f"{level['id']}: the planner found no path to {level['goal']}")
    x, y, _ = a.pose
    return [(x, y)] + [tuple(w) for w in plan.waypoints]


def _wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def densify(path: Sequence[Tuple[float, float]],
            step: float = STEP) -> List[Tuple[float, float]]:
    """Return the path as points at most ``step`` apart (the waypoints are corners only)."""
    out = [tuple(path[0])]
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        n = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / step))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
    return out


def pursue(pose, path: Sequence[Tuple[float, float]], limits,
           done: int = 0) -> Tuple[float, float, int]:
    """
    Return pure pursuit's command at ``pose`` along a dense ``path`` (the module doc).

    ``done`` is the progress so far (an index into ``path``): progress only moves
    forward, to the closest point within the next ``WINDOW`` points; the target is
    the first point after it at least ``LOOKAHEAD`` away, or the goal. Returns
    ``(v, w, progress)``.
    """
    x, y, th = pose
    hi = min(len(path), done + WINDOW)
    k = min(range(done, hi), key=lambda i: (path[i][0] - x) ** 2 + (path[i][1] - y) ** 2)
    target = path[-1]
    for i in range(k + 1, len(path)):
        if math.hypot(path[i][0] - x, path[i][1] - y) >= LOOKAHEAD:
            target = path[i]
            break
    a = _wrap(math.atan2(target[1] - y, target[0] - x) - th)
    vmax, wmax = limits['teleop_linear'], limits['teleop_angular']
    if abs(a) > SPIN:
        return 0.0, math.copysign(wmax, a), k
    # slower as the goal nears: at full speed the tightest turn (vmax / wmax) is wider
    # than a finish radius, and pursuit would circle the goal instead of reaching it
    d_goal = math.hypot(path[-1][0] - x, path[-1][1] - y)
    v = vmax * math.cos(a) * min(1.0, d_goal / LOOKAHEAD)
    w = max(-wmax, min(wmax, 2.0 * v * math.sin(a) / LOOKAHEAD))
    return v, w, k


def _q(v: float) -> float:
    return round(v / Q) * Q


def ghost_inputs(spec, level) -> List[Dict[str, object]]:
    """Return the ghost's input log: pure pursuit on the planner's path, teleop only."""
    from .arena import InputEvent
    path = densify(ghost_path(spec, level))
    a = _arena(spec, level)
    gx, gy = level['goal']
    log, last, done = [], None, 0
    for k in range(int(level['max_ticks'])):
        x, y, _ = a.pose
        if math.hypot(gx - x, gy - y) <= level['finish_m']:
            break
        v, w, done = pursue(a.pose, path, a.limits, done)
        cmd = (_q(v), _q(w))
        rows = []
        if cmd != last:
            rows = [{'tick': k, 'kind': 'teleop', 'linear': cmd[0], 'angular': cmd[1]}]
            last = cmd
            log.extend(rows)
        a.step([InputEvent(**r) for r in rows])
    return log


def drive(spec, level, inputs) -> Dict[str, object]:
    """
    Re-simulate a race from its input log: race ticks (or None), path length, contacts.

    The Arena is stepped exactly as the page steps it (inputs stamped ``tick == k`` go
    into step ``k``). The clock starts at the first input (a person reads the level
    first; the ghost's first input is at tick 0) and stops when the robot is within
    ``finish_m`` of the goal; ``max_ticks`` race ticks at most.
    """
    from .arena import InputEvent
    from .link_bounds import validate_log
    validate_log(inputs, RaceError)
    if not isinstance(inputs, list) or len(inputs) > 20000:
        raise RaceError('an input log is a list')
    by_tick: Dict[int, list] = {}
    prev = -1
    for r in inputs:
        if not isinstance(r, dict) or r.get('kind') not in RACE_KINDS:
            raise RaceError(f'{r!r}: a race may only drive (teleop, stop)')
        t = r.get('tick')
        if not isinstance(t, int) or isinstance(t, bool) or t < prev or t < 0:
            raise RaceError('input ticks are whole numbers, in order')
        prev = t
        by_tick.setdefault(t, []).append(InputEvent(**r))
    a = _arena(spec, level)
    gx, gy = level['goal']
    path_m, contacts, finish = 0.0, 0, None
    px, py = a.pose[0], a.pose[1]
    start = inputs[0]['tick'] if inputs else 0
    for k in range(start + int(level['max_ticks'])):
        if math.hypot(gx - a.pose[0], gy - a.pose[1]) <= level['finish_m']:
            finish = k - start
            break
        t = a.step(by_tick.get(k, ()))
        path_m += math.hypot(a.pose[0] - px, a.pose[1] - py)
        px, py = a.pose[0], a.pose[1]
        contacts += 1 if t.blocked else 0
    else:
        if math.hypot(gx - a.pose[0], gy - a.pose[1]) <= level['finish_m']:
            finish = int(level['max_ticks'])
    if finish is not None and finish < 0:
        finish = 0
    return {'finish_tick': finish, 'start_tick': start,
            'time_s': None if finish is None else finish * a.dt,
            'path_m': path_m, 'contacts': contacts, 'dt': a.dt}


def references(spec, level) -> Dict[str, object]:
    """Return the ghost's own result, which sets the stars."""
    log = ghost_inputs(spec, level)
    r = drive(spec, level, log)
    if r['finish_tick'] is None:
        raise RaceError(f"{level['id']}: the ghost did not finish within "
                        f"{level['max_ticks']} ticks")
    return {'ghost': {'finish_tick': r['finish_tick'], 'time_s': r['time_s'],
                      'path_m': r['path_m'], 'contacts': r['contacts'], 'inputs': len(log)}}


def stars(level, r) -> Tuple[int, List[bool], List[str]]:
    """Return the stars for a drive against the level's ghost, and the thresholds' text."""
    g = level['reference']['ghost']
    done = r['finish_tick'] is not None
    two = done and r['finish_tick'] <= SLOW * g['finish_tick'] and r['contacts'] <= g['contacts']
    three = done and r['finish_tick'] < g['finish_tick'] and r['contacts'] <= g['contacts'] \
        and r['path_m'] <= LONG * g['path_m'] + 1e-9
    passed = [done, two, three]
    text = [f"finish within {level['max_ticks']} ticks ({level['max_ticks'] * r['dt']:g} s)",
            f"finish within {SLOW:g} x the ghost's time ({SLOW * g['time_s']:.1f} s) with at most "
            f"{g['contacts']} contacts",
            f"beat the ghost's time ({g['time_s']:.1f} s) with at most {g['contacts']} contacts "
            f"and a path at most {LONG:g} x the ghost's ({LONG * g['path_m']:.2f} m)"]
    n = 0
    for p in passed:
        if not p:
            break
        n += 1
    return n, passed, text


def ghost_track(spec, level, every: int = 1) -> List[Optional[List[float]]]:
    """Return the ghost's poses tick by tick, [x, y, theta] (to draw it beside the person)."""
    from .arena import InputEvent
    log = ghost_inputs(spec, level)
    by_tick: Dict[int, list] = {}
    for r in log:
        by_tick.setdefault(r['tick'], []).append(InputEvent(**r))
    a = _arena(spec, level)
    out = [list(a.pose)]
    end = drive(spec, level, log)['finish_tick']
    for k in range(end):
        a.step(by_tick.get(k, ()))
        if (k + 1) % every == 0 or k + 1 == end:
            out.append([round(v, 4) for v in a.pose])
    return out
