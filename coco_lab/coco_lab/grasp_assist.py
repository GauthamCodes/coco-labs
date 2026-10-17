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
Grasp Assist, the model side (M6F.3 envelope, M6F.5 pipeline; README §5.8).

Badge: **MODEL · MoveIt-style**. Deterministic, kinematic, no forces: it decides
from geometry and COCO's own constants whether an object can be picked, why not
when it cannot, and how the robot gets there.

Every envelope number is an existing constant, imported, never re-typed:

- the **approach window** ``grasp.WINDOW`` (0.151-0.1565 m ahead) and lateral
  limit ``grasp.MAX_LATERAL`` (10 mm): ``coco_config.robot.approach_window`` and
  ``GRASP_MAX_LATERAL``, the Stack's proximity gate;
- the **fingers**: the widest object they have closed on in the Stack, the
  32 mm yellow target (``grasp.TARGET_DIAMETER``, from ``coco_config.robot.TARGETS``);
  the four targets (20-32 mm) are the verified band;
- the **magnet does the holding** (two fingers and a magnet): an object that is
  not magnetic cannot be held, whatever its size;
- the **reach envelope**: the arm (``arm.ik``, the URDF chain of
  ``arm_ik.py``) must reach both ends of the approach window at the object's grasp
  band height and at the hover height above it (``arm.HOVER_CLEARANCE``), so every
  pick ends inside the Stack's own window. The magnet binds
  ``grasp.TARGET_HEIGHT - arm.TARGET_XZ[1]`` = 30 mm below an object's top, as on
  the Stack's targets -- an ASSUMPTION for other objects, labelled as one.

Refusal reasons, in the order they are checked and reported (README §5.8):
``too_wide``, ``out_of_reach``, ``not_magnetic``, ``blocked``.
"""

import math
from typing import Dict, List, Optional, Tuple

from . import arm
from .grasp import TARGET_DIAMETER, TARGET_HEIGHT, WINDOW

REASONS = ('too_wide', 'out_of_reach', 'not_magnetic', 'blocked')
REASON_TEXT = {
    'too_wide': 'too wide for the fingers',
    'out_of_reach': "out of the arm's reach envelope",
    'not_magnetic': 'not magnetic: the magnet does the holding',
    'blocked': 'blocked: no free pose puts it in the approach window',
}
#: the widest object the fingers have closed on in the Stack (the yellow target)
FINGER_MAX = max(TARGET_DIAMETER.values())
#: the band of widths the Stack has picked (the four targets)
FINGER_VERIFIED = (min(TARGET_DIAMETER.values()), FINGER_MAX)
#: where the magnet binds below an object's top (the Stack's targets: 0.158 - 0.128)
BAND_BELOW_TOP = TARGET_HEIGHT - arm.TARGET_XZ[1]


def width(item: Dict[str, object]) -> float:
    """Return what the fingers must span: a cylinder's diameter, a box's narrower side."""
    if item['shape'] == 'cylinder':
        return item['diameter']
    return min(item['size'][0], item['size'][1])


def top(item: Dict[str, object]) -> float:
    """Return the item's height above what it stands on."""
    return item['height'] if item['shape'] == 'cylinder' else item['size'][2]


def band_height(obj: Dict[str, object], floor_z: float) -> float:
    """
    Return the grasp band's height above the surface the robot stands on (m).

    Relative first, so an object on a deck gives bit for bit the band it gives on
    the floor: the Stack's grasp height is the envelope's top edge (the hover
    reach bounds it, ``coco_config.robot.GRASP_REACH_X_MAX``).
    """
    return (obj['z'] - floor_z) + (top(obj) - BAND_BELOW_TOP)


def reachable(band_z: float) -> bool:
    """Return whether the arm reaches both window ends at the band and at hover above it."""
    return all(arm.ik(x, z) for x in WINDOW for z in (band_z, band_z + arm.HOVER_CLEARANCE))


def reach_band(step: float = 0.0005, z_max: float = 0.5) -> Tuple[float, float]:
    """
    Return the grasp-band heights the arm can pick at, ``(lo, hi)`` (m).

    Derived by scanning :func:`reachable` at ``step``; the envelope drawn on the
    floor is the approach window itself (a 5.5 mm band ahead of the robot).
    """
    zs = [k * step for k in range(int(z_max / step) + 1)]
    ok = [z for z in zs if reachable(z)]
    if not ok:
        return (math.nan, math.nan)
    return (ok[0], ok[-1])


def robot_floor(obj: Dict[str, object]) -> float:
    """
    Return the height of the surface the robot would stand on to pick ``obj``.

    The floor under a bench, rack, pallet or box (0: they stand on the floor);
    the object's own surface when it stands on the floor or on a platform the
    robot can drive onto.
    """
    return obj['z'] if obj['support'] == 'floor' or obj.get('support_kind') == 'platform' \
        else 0.0


def static_check(obj: Dict[str, object]) -> List[str]:
    """
    Return every reason ``obj`` cannot be picked, from the object alone.

    ``blocked`` needs the world (:func:`approach_poses`); this is the rest,
    in :data:`REASONS` order. An empty list means the object is pickable if a
    free approach pose exists.
    """
    out = []
    if width(obj) > FINGER_MAX:
        out.append('too_wide')
    if not reachable(band_height(obj, robot_floor(obj))):
        out.append('out_of_reach')
    if not obj['magnetic']:
        out.append('not_magnetic')
    return out


def affordances(spec) -> Dict[str, Dict[str, object]]:
    """
    Return, for each object spawn of a canonical v3 spec, its static affordance.

    ``{id: {'item', 'width', 'band_z', 'reasons'}}``; ``blocked`` is added by
    the pipeline, which knows the map.
    """
    from . import worldspec_v3 as v3
    kinds = {e['id']: e['kind'] for e in spec['kit']}
    out = {}
    for o in v3.objects(spec):
        o = dict(o, support_kind=kinds.get(o['support'], 'floor'))
        out[o['id']] = {'item': o['item'], 'width': width(o),
                        'band_z': band_height(o, robot_floor(o)),
                        'reasons': static_check(o)}
    return out


def window_pose(xy: Tuple[float, float], heading: float) -> Tuple[float, float, float]:
    """Return the robot pose facing ``heading`` with ``xy`` at the window's centre."""
    mid = (WINDOW[0] + WINDOW[1]) / 2
    return (xy[0] - mid * math.cos(heading), xy[1] - mid * math.sin(heading), heading)


def headings(n: int = 16) -> List[float]:
    """Return ``n`` evenly spaced approach headings, 0 first."""
    return [2 * math.pi * k / n for k in range(n)]


def first_reason(reasons: List[str]) -> Optional[str]:
    """Return the reason shown first (README order), or None for a pickable object."""
    for r in REASONS:
        if r in reasons:
            return r
    return None
