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
The world a mapping run reads: a Sketch simulation or a recorded drive.

A :class:`MapWorld` holds, per ROW (every ``dt`` in Sketch, every scan in
a recording), the truth and the odometry; the UPDATE rows where odometry
had moved ``UPDATE_MIN_D`` / ``UPDATE_MIN_A`` since the last update (the
rule Lab 2 uses, ``coco_lab.sketch``); at each update the measured scan
and the IDEALISED landmark observations. :meth:`MapWorld.inputs` is what
every SLAM receives -- no truth in it.

- :func:`from_sketch`: :func:`coco_lab.sketch.simulate` on a scenario,
  then the idealised landmark sensor on the true poses (its own random
  stream, from the scenario's seed).
- :func:`from_recorded`: a drive recorded on the real stack in Gazebo
  (``docs/data/lab3/make_drive.py``): COCO's wheel odometry and LiDAR as
  recorded, every ``beam_step``-th beam kept; the truth from the
  simulator. Its landmark observations are SYNTHESISED from the recorded
  truth and the ground-truth map -- the robot has no landmark sensor --
  and are labelled so.
"""

from dataclasses import dataclass, field
import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

from . import landmarks as lmk
from . import slam
from .maps import LabMap
from .sketch import (LidarSpec, Scenario, simulate, SketchMap, UPDATE_MIN_A,
                     UPDATE_MIN_D, wrap)

SOURCES = ('sketch', 'recorded')
#: XOR'd into the scenario seed for the landmark sensor's own stream
LANDMARK_STREAM = 0x4C414E44  # 'LAND'


@dataclass
class LandmarkSpec:
    """How landmarks are made and seen (both idealised)."""

    sensor: lmk.LandmarkSensor = field(default_factory=lmk.LandmarkSensor)
    min_separation: float = 1.0
    max_count: int = 32

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-ready dict."""
        return {'sensor': self.sensor.to_dict(),
                'min_separation': self.min_separation,
                'max_count': self.max_count}

    @classmethod
    def from_dict(cls, d) -> 'LandmarkSpec':
        """Inverse of :meth:`to_dict`."""
        s = cls(lmk.LandmarkSensor.from_dict(d['sensor']),
                float(d['min_separation']), int(d['max_count']))
        if not (0 < s.min_separation <= 20 and 0 <= s.max_count <= 64):
            raise ValueError('landmark spec out of range')
        return s


@dataclass
class MapWorld:
    """Truth, odometry, scans and landmark observations; see the module."""

    source: str
    t: List[float]
    gt: List[Tuple[float, float, float]]
    odom: List[Tuple[float, float, float]]
    updates: List[int]
    ranges: List[List[float]]
    lidar: LidarSpec
    start: Tuple[float, float, float]
    landmark_spec: LandmarkSpec
    landmarks: List[lmk.Landmark]
    observations: List[List[lmk.Observation]]
    status: str
    scenario: Optional[Scenario] = None
    recorded: Optional[Dict[str, object]] = None

    def inputs(self) -> slam.SlamInputs:
        """Return what a SLAM may read: no truth."""
        u = self.updates
        return slam.SlamInputs(
            rows=list(u), t=[self.t[r] for r in u],
            odom=[self.odom[r] for r in u], ranges=self.ranges,
            lidar=self.lidar, start=tuple(self.start),
            landmarks=self.observations,
            landmark_sensor=self.landmark_spec.sensor)

    def true_poses(self) -> List[Tuple[float, float, float]]:
        """Return the truth at every update (scoring and ``known`` only)."""
        return [self.gt[r] for r in self.updates]


def update_rows(odom: Sequence[Tuple[float, float, float]],
                min_d: float = UPDATE_MIN_D,
                min_a: float = UPDATE_MIN_A) -> List[int]:
    """Return the rows where odometry moved ``min_d`` m or ``min_a`` rad."""
    out = [0]
    last = odom[0]
    for i in range(1, len(odom)):
        o = odom[i]
        if math.hypot(o[0] - last[0], o[1] - last[1]) >= min_d or \
                abs(wrap(o[2] - last[2])) >= min_a:
            out.append(i)
            last = o
    return out


def _observe_all(smap, poses, marks, spec, seed):
    rng = random.Random(seed ^ LANDMARK_STREAM)
    return [lmk.observe(smap, p, marks, spec.sensor, rng) for p in poses]


def from_sketch(lab_map: LabMap, sc: Scenario,
                spec: Optional[LandmarkSpec] = None,
                smap: Optional[SketchMap] = None) -> MapWorld:
    """Simulate ``sc`` on ``lab_map``; add the idealised landmark sensor."""
    spec = spec or LandmarkSpec()
    smap = smap or SketchMap(lab_map)
    w = simulate(smap, sc)
    marks = lmk.corners(lab_map, spec.min_separation, spec.max_count)
    obs = _observe_all(smap, [w.gt[r] for r in w.updates], marks, spec,
                       sc.seed)
    return MapWorld('sketch', w.t, w.gt, w.odom, w.updates, w.ranges,
                    sc.lidar, sc.start, spec, marks, obs, w.status,
                    scenario=sc)


def recorded_lidar(d: Dict[str, object], beam_step: int) -> LidarSpec:
    """Return the recorded LiDAR, every ``beam_step``-th beam kept."""
    li = d['lidar']
    full = LidarSpec(int(li['samples']), float(li['angle_min']),
                     float(li['angle_max']), float(li['range_min']),
                     float(li['range_max']), tuple(li['mount']))
    return full.decimated(beam_step)


def from_recorded(rec: Dict[str, object], truth_map: LabMap,
                  spec: Optional[LandmarkSpec] = None,
                  seed: int = 0) -> MapWorld:
    """
    Build a world from a recorded drive (see :func:`recorded_payload`).

    ``rec``: ``{'lidar': {..., 'mount'}, 'beam_step', 't', 'gt', 'odom',
    'ranges_full'}`` -- per row; ``ranges_full`` are the scans' every beam
    (``inf`` for no return). The scan at each update is decimated by
    ``beam_step``.
    """
    spec = spec or LandmarkSpec()
    step = int(rec['beam_step'])
    lidar = recorded_lidar(rec, step)
    odom = [tuple(p) for p in rec['odom']]
    gt = [tuple(p) for p in rec['gt']]
    ups = update_rows(odom)
    ranges = [list(rec['ranges_full'][r][::step]) for r in ups]
    smap = SketchMap(truth_map)
    marks = lmk.corners(truth_map, spec.min_separation, spec.max_count)
    obs = _observe_all(smap, [gt[r] for r in ups], marks, spec, seed)
    return MapWorld('recorded', list(rec['t']), gt, odom, ups, ranges, lidar,
                    gt[0], spec, marks, obs, 'route_done',
                    recorded={k: rec[k] for k in ('provenance', 'beam_step')
                              if k in rec})
