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
R5.5: the world editor's live check of a level.

The World Spec validator's own verdict, then what a level needs to be driven: COCO fits at its
start, and every goal is reachable from there.

``check(spec, goals)`` returns ``{'ok', 'errors': [...], 'start': {...}, 'goals': [...]}``. Errors
are the validator's (``coco_lab.worldspec.normalize``: every refusal names its reason) or this
module's: the start or a goal off the map, COCO not fitting at the start (its inflated footprint is
blocked there), a goal not reachable (A* on the Arena's own planning grid, the robot's radius
inflated, as Play's planner sees the level). A goal inside an obstacle is snapped to the nearest
free cell, as Play does, and the snap is reported. Deterministic and pure (runs in the browser's
worker).
"""
from typing import Dict, List, Sequence

from coco_lab import numerics
from coco_lab.worldspec import normalize, to_map_frame


def check(spec, goals: Sequence[Sequence[float]] = ()) -> Dict[str, object]:
    """Validate ``spec`` (a World Spec dict) and its ``goals`` (``[[x, y], ...]``, world frame)."""
    try:
        s = normalize(spec)
    except (ValueError, KeyError, TypeError) as e:
        return {'ok': False, 'errors': [str(e)], 'start': None, 'goals': []}
    from coco_lab.arena import Arena, ArenaError, PLANNERS
    from coco_lab.search import search
    from coco_lab.sketch import _nearest_free

    errors: List[str] = []
    try:
        a = Arena(s, 1)
    except ArenaError as e:  # the Arena refuses a start inside an obstacle itself
        why = str(e)
        if 'start' in why:
            why = (
                f"COCO does not fit at the start ({s['start']['x']}, {s['start']['y']}): its "
                f"{s['robot']['radius']} m radius reaches an obstacle or a wall ({why})"
            )
        return {
            'ok': False,
            'errors': [why],
            'start': {'cell': None, 'fits': False},
            'goals': [
                {
                    'goal': [float(x), float(y)],
                    'reachable': False,
                    'path_m': None,
                    'snapped_m': None,
                }
                for x, y in goals
            ],
        }
    g, pm = a.grid, a.plan_map
    res = pm.resolution
    sx, sy = to_map_frame(s, s['start']['x'], s['start']['y'])
    sc = pm.cell_at(sx, sy)
    start = {'cell': sc, 'fits': bool(sc is not None and g.is_valid(sc))}
    if sc is None:
        errors.append(f"the start ({s['start']['x']}, {s['start']['y']}) is outside the map")
    elif not start['fits']:
        errors.append(
            f"COCO does not fit at the start ({s['start']['x']}, {s['start']['y']}): its "
            f"{s['robot']['radius']} m radius reaches an obstacle or a wall"
        )
    out = []
    for k, (gx, gy) in enumerate(goals):
        mx, my = to_map_frame(s, float(gx), float(gy))
        gc = pm.cell_at(mx, my)
        r = {'goal': [float(gx), float(gy)], 'reachable': False, 'path_m': None, 'snapped_m': None}
        if gc is None:
            errors.append(f'goal {k + 1} ({gx}, {gy}) is outside the map')
        elif start['fits']:
            t = _nearest_free(g, gc)
            if t is None:
                errors.append(f'goal {k + 1} ({gx}, {gy}) has no free cell near it')
            else:
                r['snapped_m'] = round(res * numerics.hypot(t[0] - gc[0], t[1] - gc[1]), 3)
                found = search(g, sc, t, **PLANNERS['astar'])
                if found.found:
                    r['reachable'] = True
                    p = found.path
                    r['path_m'] = round(
                        sum(
                            res
                            * ((p[i + 1][0] - p[i][0]) ** 2 + (p[i + 1][1] - p[i][1]) ** 2) ** 0.5
                            for i in range(len(p) - 1)
                        ),
                        2,
                    )
                else:
                    errors.append(
                        f'goal {k + 1} ({gx}, {gy}) is not reachable from the start: no path wide '
                        f"enough for COCO's {s['robot']['radius']} m radius"
                    )
        out.append(r)
    # the spec as the site ships its levels: the kit plus the boxes and elevation it lowers to
    # (Play's world
    # look reads them; the reader accepts them only if they equal what the kit lowers to)
    shipped = dict(spec, boxes=s['boxes'], elevation=s.get('elevation', []))
    return {'ok': not errors, 'errors': errors, 'start': start, 'goals': out, 'spec': shipped}
