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
Experiment scenarios (R1): seeded start/goal pairs in free space, MAP frame.

A world context (:class:`World`) holds what every run on one world shares: the
normalized World Spec, its LabMap and SketchMap, the Arena's own planning grid
(the map inflated by the robot's radius, 8-connected, no corner cutting) and
that grid's connected components. Two cells are mutually reachable on the
planning grid exactly when they share a component (a diagonal step without
corner cutting can always be replaced by two orthogonal ones, so 4-connected
labels are the 8-connected reachability).

:func:`sample_pairs` draws ``n`` pairs with :class:`coco_lab.rng.Rng`:

- candidate cells are free with clearance above ``min_clearance_m`` and valid
  on the planning grid; the robot is placed at the cell centre;
- ``zones``: both ends inside the union of the named region zones (World Spec
  v3), else anywhere; ``stratify='zone'`` splits ``n`` evenly over the zones
  by the START's zone (the goal may be in any of them);
- ``min_separation_m``: straight-line distance between start and goal;
- ``require_reachable``: a draw whose ends are in different components is
  rejected AND COUNTED (``rejected_unreachable``); nothing is dropped silently;
- each pair gets its own 53-bit seed (the Arena's, for MCL and MPPI draws; 53
  bits so a JavaScript number carries it exactly), shared by every algorithm
  that runs it, so comparisons hold it fixed.

Everything is deterministic: the same arguments give the same pairs in
CPython and in Pyodide (integer arithmetic, cell centres, fdlibm-free).
"""

from collections import deque
from typing import Dict, List, Optional, Sequence

from . import worldspec, worldspec_v3
from .numerics import math
from .rng import Rng
from .sketch import _inflated_grid_map, SketchMap


class ScenarioError(ValueError):
    """Scenarios that cannot be drawn as asked."""


class World:
    """What every run on one world shares (built once per worker and world)."""

    def __init__(self, spec: Dict[str, object]):
        """Rasterize the world and label the planning grid's components."""
        self.spec = worldspec.normalize(spec)
        self.id = self.spec['id']
        self.lab_map = worldspec.arena_map(self.spec)
        self.smap = SketchMap(self.lab_map)
        self.radius = self.spec['robot']['radius']
        self.plan_map = _inflated_grid_map(self.smap, self.radius)
        self.grid = self.plan_map.to_grid(connectivity=8)
        self.resolution = self.lab_map.resolution
        self._labels = None
        self.regions = {}
        if self.spec['spec_version'] == worldspec.SPEC_VERSION_V3:
            dx, dy = self.spec['world_to_map']
            for z in worldspec_v3.zones(self.spec, 'region'):
                (cx, cy), (sx, sy) = z['center'], z['size']
                self.regions[z['id']] = (cx + dx - sx / 2, cx + dx + sx / 2,
                                         cy + dy - sy / 2, cy + dy + sy / 2)

    def labels(self) -> List[int]:
        """Return each planning-grid cell's component (-1 where invalid)."""
        if self._labels is None:
            g, w, h = self.grid, self.lab_map.width, self.lab_map.height
            lab = [-1] * (w * h)
            k = 0
            for r in range(h):
                for c in range(w):
                    if lab[r * w + c] != -1 or not g.is_valid((r, c)):
                        continue
                    lab[r * w + c] = k
                    q = deque([(r, c)])
                    while q:
                        a, b = q.popleft()
                        for na, nb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                            if 0 <= na < h and 0 <= nb < w and lab[na * w + nb] == -1 \
                                    and g.is_valid((na, nb)):
                                lab[na * w + nb] = k
                                q.append((na, nb))
                    k += 1
            self._labels = lab
        return self._labels

    def component(self, x: float, y: float) -> int:
        """Return the planning-grid component of the point (-1 off the grid or blocked)."""
        cell = self.lab_map.cell_at(x, y)
        if cell is None:
            return -1
        return self.labels()[cell[0] * self.lab_map.width + cell[1]]

    def zone_of(self, x: float, y: float) -> Optional[str]:
        """Return the first region zone containing the point (spec order), or None."""
        for zid, r in self.regions.items():
            if r[0] <= x <= r[1] and r[2] <= y <= r[3]:
                return zid
        return None

    def candidates(self, min_clearance: float, rect=None) -> List[tuple]:
        """Return the cell centres free with clearance > ``min_clearance``, inside ``rect``."""
        sm, out = self.smap, []
        labels = self.labels()
        for ix, iy in sm.free_cells(min_clearance):
            x, y = sm.cell_centre(ix, iy)
            if rect is not None and not (rect[0] <= x <= rect[1] and rect[2] <= y <= rect[3]):
                continue
            cell = self.lab_map.cell_at(x, y)
            if cell is None or labels[cell[0] * self.lab_map.width + cell[1]] < 0:
                continue
            out.append((x, y))
        return out


def sample_pairs(world: World, n: int, seed: int, min_separation_m: float = 2.0,
                 min_clearance_m: float = 0.35, zones: Optional[Sequence[str]] = None,
                 stratify: str = 'none', require_reachable: bool = True,
                 max_attempts: int = 2000) -> Dict[str, object]:
    """Return ``{scenarios, rejected_unreachable, rejected_separation}`` (see the module)."""
    if zones:
        unknown = [z for z in zones if z not in world.regions]
        if unknown:
            raise ScenarioError(f'{world.id} has no region zone {unknown[0]!r}; '
                                f'its zones: {sorted(world.regions)}')
    if stratify not in ('none', 'zone'):
        raise ScenarioError("stratify is 'none' or 'zone'")
    if stratify == 'zone' and not world.regions:
        raise ScenarioError(f'{world.id} has no zones to stratify by')
    names = list(zones) if zones else (list(world.regions) if stratify == 'zone' else None)
    if names is None:
        pools = {None: world.candidates(min_clearance_m)}
    else:
        pools = {z: world.candidates(min_clearance_m, world.regions[z]) for z in names}
    union = [p for z in pools for p in pools[z]]
    if not union:
        raise ScenarioError('no free cell satisfies the clearance and zones')
    rng = Rng(seed)
    if stratify == 'zone':
        k = len(names)
        quota = [n // k + (1 if i < n % k else 0) for i in range(k)]
        plan = [z for z, q in zip(names, quota) for _ in range(q)]
    else:
        plan = [None] * n
    out, rej_unreach, rej_sep = [], 0, 0
    for i, z in enumerate(plan):
        starts = pools[z] if stratify == 'zone' else union
        if not starts:
            raise ScenarioError(f'zone {z!r} has no free cell with that clearance')
        for _ in range(max_attempts):
            s = starts[rng.randrange(len(starts))]
            g = union[rng.randrange(len(union))]
            if math.hypot(g[0] - s[0], g[1] - s[1]) < min_separation_m:
                rej_sep += 1
                continue
            if require_reachable and world.component(*s) != world.component(*g):
                rej_unreach += 1
                continue
            break
        else:
            raise ScenarioError(f'scenario {i}: no pair found in {max_attempts} draws '
                                f'(separation {min_separation_m} m too large for the zones?)')
        theta = rng.uniform(-math.pi, math.pi)
        out.append({'id': f's{i + 1:03d}', 'start': [s[0], s[1], theta], 'goal': [g[0], g[1]],
                    'seed': rng.next_u64() >> 11, 'start_zone': world.zone_of(*s),
                    'goal_zone': world.zone_of(*g)})
    return {'scenarios': out, 'rejected_unreachable': rej_unreach,
            'rejected_separation': rej_sep}


def hand_pairs(world: World, pairs: Sequence[Dict[str, object]], seed: int) -> List[Dict]:
    """Return hand-placed pairs as scenarios (each checked to be on the map), seeded."""
    rng = Rng(seed)
    out = []
    for i, p in enumerate(pairs):
        st, gl = list(p['start']), list(p['goal'])
        if len(st) == 2:
            st.append(0.0)
        if len(st) != 3 or len(gl) != 2 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in st + gl):
            raise ScenarioError(f'pair {i}: start [x, y, theta?] and goal [x, y] in metres')
        for name, (x, y) in (('start', st[:2]), ('goal', gl)):
            if world.lab_map.cell_at(x, y) is None:
                raise ScenarioError(f'pair {i}: {name} ({x}, {y}) is off the map')
        out.append({'id': p.get('id') or f'h{i + 1:03d}', 'start': [float(v) for v in st],
                    'goal': [float(v) for v in gl], 'seed': rng.next_u64() >> 11,
                    'start_zone': world.zone_of(st[0], st[1]),
                    'goal_zone': world.zone_of(gl[0], gl[1])})
    return out
