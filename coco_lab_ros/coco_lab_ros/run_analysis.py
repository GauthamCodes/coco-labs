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
One real run's metrics, from its recorded streams (plan §E.2). Pure.

Definitions, fixed before the runs:

- **window**: from the FollowPath goal's acceptance to its result, both
  as the lab node stamped them on ``/lab/status`` in sim time (``t_sim``).
- **duration**: result minus acceptance, in sim time and in wall time.
- **tracking error**: for every ground-truth sample in the window, its
  distance (map frame) to the nearest point of the planned polyline;
  mean, p95 (nearest rank), max.
- **endpoint error**: distance from the last ground-truth sample at or
  before the result to the goal.
- **belief gap**: for every AMCL sample in the window, the distance from
  the AMCL position to the ground-truth position linearly interpolated at
  the AMCL stamp; mean, max. Samples outside the ground truth's time span
  are skipped, never extrapolated.
- **recoveries**: distinct goal ids seen on the behavior server's action
  status topics during the window.
- **arbiter timeline**: ``(t, mode, active)`` at every change of
  ``/cmd_vel_arbiter/status``'s mode or active source.
"""

import bisect
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .metrics import distance_to_polyline, tracking_stats

Sample = Tuple[float, float, float, float]      # t, x, y, yaw


def window(samples: Sequence[Sample], t0: float, t1: float) -> List[Sample]:
    """Return the samples with ``t0 <= t <= t1``."""
    return [s for s in samples if t0 <= s[0] <= t1]


def interpolate_xy(samples: Sequence[Sample], t: float
                   ) -> Optional[Tuple[float, float]]:
    """Return x, y linearly interpolated at ``t``; None outside the span."""
    if not samples or t < samples[0][0] or t > samples[-1][0]:
        return None
    ts = [s[0] for s in samples]
    i = bisect.bisect_left(ts, t)
    if ts[i] == t:
        return samples[i][1], samples[i][2]
    a, b = samples[i - 1], samples[i]
    f = (t - a[0]) / (b[0] - a[0])
    return a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])


def tracking_error(gt: Sequence[Sample],
                   plan_xy: Sequence[Tuple[float, float]]
                   ) -> Dict[str, object]:
    """Return tracking statistics of ``gt`` against the planned polyline."""
    return tracking_stats([distance_to_polyline((s[1], s[2]), plan_xy)
                           for s in gt])


def belief_gap(amcl: Sequence[Sample], gt: Sequence[Sample]
               ) -> Dict[str, object]:
    """Return ``{n, mean, max, skipped}`` of |AMCL - GT(t_amcl)|."""
    gaps, skipped = [], 0
    for t, x, y, _ in amcl:
        p = interpolate_xy(gt, t)
        if p is None:
            skipped += 1
            continue
        gaps.append(math.hypot(x - p[0], y - p[1]))
    if not gaps:
        return {'n': 0, 'mean': None, 'max': None, 'skipped': skipped}
    return {'n': len(gaps), 'mean': sum(gaps) / len(gaps),
            'max': max(gaps), 'skipped': skipped}


def endpoint_error(gt: Sequence[Sample], t_end: float,
                   goal: Tuple[float, float]) -> Optional[float]:
    """Return the last GT sample's (at or before ``t_end``) goal distance."""
    before = [s for s in gt if s[0] <= t_end]
    if not before:
        return None
    s = before[-1]
    return math.hypot(s[1] - goal[0], s[2] - goal[1])


def parse_kv(text: str) -> Dict[str, str]:
    """Split a space-separated ``key=value`` line (arbiter status)."""
    out = {}
    for part in text.split():
        if '=' in part:
            k, v = part.split('=', 1)
            out[k] = v
    return out


def timeline(events: Sequence[Tuple[float, Tuple]]) -> List[list]:
    """Return ``[t, *value]`` at the first sample and at every change."""
    out, last = [], object()
    for t, value in events:
        if value != last:
            out.append([t, *value])
            last = value
    return out


def arbiter_timeline(statuses: Sequence[Tuple[float, str]]) -> List[list]:
    """Return ``[t, mode, active]`` at every change of the arbiter status."""
    return timeline([(t, (parse_kv(s).get('mode'), parse_kv(s).get('active')))
                     for t, s in statuses])


def to_map(samples: Sequence[Sample], dx: float, dy: float) -> List[Sample]:
    """Shift world-frame samples into the map frame (identity rotation)."""
    return [(t, x + dx, y + dy, yaw) for t, x, y, yaw in samples]
