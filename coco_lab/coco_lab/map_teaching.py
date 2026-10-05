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
Lab 3's teaching worlds and their default drives. Every claim is tested.

All at 0.10 m, painted in metres (``maps.Raster``, rule ``overlap``).

``map_loop``    A 16 x 10 m room around an 8 x 3 m central block: a ring.
                Driving once round it and back to the start is a LOOP --
                where loop closure has something to close.
``map_corridor`` Two 6 x 6 m rooms with boxes in them, joined by an 18 m
                corridor 2 m wide with perfectly smooth walls. In the
                corridor a scan pins the robot's lateral position and
                heading but says nothing about how far along it is.
``loc_landmarks`` Lab 2's asymmetric room (``loc_teaching``), reused: its
                box corners are good landmarks for EKF-SLAM.
``arena``       COCO's saved Nav2 map at 0.10 m -- built at site build from
                ``gazebo_models/maps``, because coco_lab ships no data --
                the "map the arena" challenge.

The SLAMs are told the world's true noise model (as Lab 2's filters are):
what differs between them is the algorithm, not a mis-tuned model.
"""

from typing import Dict, List, Tuple

from . import loc_teaching
from .maps import LabMap, OCCUPIED, Raster
from .sketch import Noise, Scenario

RES = 0.10
WALL = 0.2
#: the Sketch default odometry alphas are 0.02; the lab's scenes use x3
NOISE_SCALE = 3.0


def _box(w_m: float, h_m: float, map_id: str) -> Raster:
    r = Raster(int(round(w_m / RES)), int(round(h_m / RES)), RES, (0.0, 0.0))
    for (x0, x1, y0, y1) in ((0, w_m, 0, WALL), (0, w_m, h_m - WALL, h_m),
                             (0, WALL, 0, h_m), (w_m - WALL, w_m, 0, h_m)):
        r.paint(x0, x1, y0, y1, OCCUPIED, rule='overlap')
    return r


#: the loop room's central block and the bumps that give scans features
LOOP_BLOCK = (4.0, 12.0, 3.5, 6.5)
LOOP_FEATURES = (
    (6.0, 6.6, 0.2, 0.9),      # south wall bump
    (13.4, 14.4, 9.0, 9.8),    # north wall bump
    (0.2, 0.9, 6.0, 7.2),      # west wall bump
    (15.1, 15.8, 2.0, 2.6),    # east wall bump
    (8.0, 8.4, 8.1, 8.5),      # a pillar in the north corridor
    (2.4, 2.8, 4.6, 5.0),      # a pillar in the west corridor
)


def loop_map() -> LabMap:
    """Return the ring room."""
    r = _box(16.0, 10.0, 'map_loop')
    r.paint(*LOOP_BLOCK, OCCUPIED, rule='overlap')
    for b in LOOP_FEATURES:
        r.paint(*b, OCCUPIED, rule='overlap')
    return r.build('map_loop', frame='map',
                   meta={'source': 'coco_lab.map_teaching',
                         'claim': 'a ring: a drive round it closes a loop'})


#: the corridor: rooms A (x 0..6) and B (x 24..30), corridor y 2..4
CORRIDOR_Y = (2.0, 4.0)
CORRIDOR_X = (6.0, 24.0)
CORRIDOR_BOXES = (
    (1.0, 1.8, 4.4, 5.0),      # room A
    (3.6, 4.0, 0.8, 1.8),
    (2.2, 2.6, 2.6, 3.0),
    (26.0, 27.0, 1.0, 1.4),    # room B
    (28.0, 28.6, 4.0, 5.2),
    (25.4, 25.8, 4.6, 5.0),
)


def corridor_map() -> LabMap:
    """Return two rooms joined by a smooth 18 m corridor."""
    r = _box(30.0, 6.0, 'map_corridor')
    y0, y1 = CORRIDOR_Y
    x0, x1 = CORRIDOR_X
    # the rooms' inner walls, leaving the corridor's mouth open
    for x in (x0 - WALL, x1):
        r.paint(x, x + WALL, 0.0, y0, OCCUPIED, rule='overlap')
        r.paint(x, x + WALL, y1, 6.0, OCCUPIED, rule='overlap')
    # solid fill above and below the corridor: smooth walls, nothing else
    r.paint(x0, x1, 0.0, y0, OCCUPIED, rule='overlap')
    r.paint(x0, x1, y1, 6.0, OCCUPIED, rule='overlap')
    for b in CORRIDOR_BOXES:
        r.paint(*b, OCCUPIED, rule='overlap')
    return r.build('map_corridor', frame='map',
                   meta={'source': 'coco_lab.map_teaching',
                         'claim': 'the corridor walls are straight and '
                                  'featureless for 18 m'})


LOOP_ROUTE = [(14.0, 2.0), (14.0, 8.0), (2.0, 8.0), (2.0, 2.0), (6.0, 2.0)]
CORRIDOR_ROUTE = [(5.0, 3.0), (25.0, 3.0), (27.5, 2.5), (27.5, 3.5),
                  (25.0, 3.0), (5.0, 3.0), (3.0, 2.0)]


def noise(scale: float = NOISE_SCALE) -> Noise:
    """Return Sketch's default noise with the odometry alphas scaled."""
    return Noise(odom_alphas=(0.02 * scale,) * 4, range_sigma=0.02)


def scenarios() -> Dict[str, Tuple[str, Scenario]]:
    """Return ``{scene id: (map id, scenario)}`` for the teaching worlds."""
    lm = list(loc_teaching.LANDMARKS_ROUTE)
    return {
        'map_loop': ('map_loop', Scenario(
            start=(2.0, 2.0, 0.0), route=list(LOOP_ROUTE), seed=11,
            noise=noise(), max_time=900.0)),
        'map_corridor': ('map_corridor', Scenario(
            start=(2.0, 3.0, 0.0), route=list(CORRIDOR_ROUTE), seed=12,
            noise=noise(), max_time=900.0)),
        'map_landmarks': ('loc_landmarks', Scenario(
            start=(1.5, 1.5, 0.0), route=lm + lm[1:], seed=13,
            noise=noise(), max_time=900.0)),
    }


#: the arena challenge: start at the spawn, map (0, 0), facing +x
ARENA_START = (0.0, 0.0, 0.0)
#: a short default drive near the spawn; the learner draws their own
ARENA_ROUTE = [(4.0, 0.0), (4.0, 2.0), (-2.0, 2.0), (-2.0, -2.0),
               (4.0, -2.0), (4.0, 0.0), (0.5, 0.0)]
ARENA_SEED = 21


def arena_scenario(route: List[Tuple[float, float]] = None,
                   seed: int = ARENA_SEED) -> Scenario:
    """Return the challenge's scenario: fixed start, seed and noise."""
    return Scenario(start=ARENA_START, route=list(route or ARENA_ROUTE),
                    seed=seed, noise=noise(), max_time=1200.0)


def teaching_maps() -> Dict[str, LabMap]:
    """Return the Lab 3 maps (and Lab 2's landmarks room) by id."""
    return {'map_loop': loop_map(), 'map_corridor': corridor_map(),
            'loc_landmarks': loc_teaching.landmarks_map()}


#: every run a scene computes, in display order
RUN_IDS = ('known', 'odometry', 'ekf_slam', 'fastslam', 'pose_graph',
           'pose_graph_noloop')


def run_specs(scale: float = NOISE_SCALE, particles: int = 20,
              fastslam_seed: int = 0, sigma_range: float = 0.05,
              sigma_bearing: float = 0.02, snapshots: int = 16,
              ids=RUN_IDS) -> List[Tuple[str, str, object]]:
    """
    Return ``[(id, algorithm, params)]`` for a scene.

    The SLAMs assume the world's TRUE odometry alphas (``0.02 * scale``)
    and the idealised sensor's true sigmas: the comparison is between
    algorithms, not between mis-tuned models.
    """
    from .ekfslam import EKFSlamParams
    from .fastslam import FastSlamParams
    from .mapping import GivenPoseParams
    from .posegraph import PoseGraphParams
    alphas = (0.02 * scale,) * 4
    specs = {
        'known': ('known', GivenPoseParams(snapshots=snapshots)),
        'odometry': ('odometry', GivenPoseParams(snapshots=snapshots)),
        'ekf_slam': ('ekf_slam', EKFSlamParams(
            alphas=alphas, sigma_range=sigma_range,
            sigma_bearing=sigma_bearing, snapshots=snapshots)),
        'fastslam': ('fastslam', FastSlamParams(
            particles=particles, alphas=alphas, seed=fastslam_seed,
            snapshots=snapshots)),
        'pose_graph': ('pose_graph', PoseGraphParams(snapshots=snapshots)),
        'pose_graph_noloop': ('pose_graph', PoseGraphParams(
            snapshots=snapshots, loop_closure=False)),
    }
    return [(i, specs[i][0], specs[i][1]) for i in ids]
