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
Lab 2's teaching rooms and scenarios. Every claim made about them is tested.

Two 12 x 8 m rooms at 0.10 m, painted in metres (``maps.Raster``, rule
``overlap``):

``landmarks``
    Walls, an L-shaped partition and four boxes of different sizes, placed
    with no symmetry: every place looks different to a LiDAR, so a global
    start can converge. ``test_localise.py`` checks MCL does, from a
    uniform cloud.
``twins``
    The same outer walls with two identical boxes and two identical
    partitions placed with **180-degree rotational symmetry**: a pose and
    its rotation about the centre see identical scans (tested exactly on
    the noise-free ray caster). From a global start a particle filter has
    two equally good answers -- perceptual aliasing, the lesson the real
    arena teaches with its four identical bays.

The arena scenarios use COCO's saved Nav2 map, downsampled to 0.10 m;
they are built at site-build time from ``gazebo_models/maps``, because
coco_lab ships no data files.
"""

import math
from typing import Dict, List, Tuple

from .maps import LabMap, OCCUPIED, Raster
from .sketch import Kidnap, Noise, Scenario

RES = 0.10
WIDTH_M = 12.0
HEIGHT_M = 8.0
WALL = 0.2


def _room(map_id: str) -> Raster:
    w = int(round(WIDTH_M / RES))
    h = int(round(HEIGHT_M / RES))
    r = Raster(w, h, RES, (0.0, 0.0))
    for (x0, x1, y0, y1) in ((0, WIDTH_M, 0, WALL),
                             (0, WIDTH_M, HEIGHT_M - WALL, HEIGHT_M),
                             (0, WALL, 0, HEIGHT_M),
                             (WIDTH_M - WALL, WIDTH_M, 0, HEIGHT_M)):
        r.paint(x0, x1, y0, y1, OCCUPIED, rule='overlap')
    return r


#: (xmin, xmax, ymin, ymax) of each obstacle, metres
LANDMARK_BOXES = (
    (2.0, 2.6, 5.4, 6.0),      # small square, north-west
    (8.6, 10.0, 5.6, 6.2),     # long bar, north-east
    (9.6, 10.2, 1.4, 3.0),     # tall bar, south-east
    (4.6, 5.2, 1.8, 2.2),      # small slab, south
    (6.0, 6.2, 3.0, 6.0),      # partition, vertical
    (6.0, 7.6, 3.0, 3.2),      # partition foot (the L)
)

#: Half of the twins room's obstacles; the other half is their rotation
#: by 180 degrees about the room's centre (6, 4).
TWIN_HALF = (
    (2.4, 3.4, 5.2, 6.2),      # a box
    (4.4, 4.6, 0.2, 2.8),      # a partition from the south wall
)


def rotate180(rect):
    """Return ``rect`` rotated 180 degrees about the room's centre."""
    x0, x1, y0, y1 = rect
    return (WIDTH_M - x1, WIDTH_M - x0, HEIGHT_M - y1, HEIGHT_M - y0)


def landmarks_map() -> LabMap:
    """Return the asymmetric room."""
    r = _room('loc_landmarks')
    for b in LANDMARK_BOXES:
        r.paint(*b, OCCUPIED, rule='overlap')
    return r.build('loc_landmarks', frame='map',
                   meta={'source': 'coco_lab.loc_teaching',
                         'claim': 'no symmetry; global MCL converges'})


def twins_map() -> LabMap:
    """Return the 180-degree-symmetric room."""
    r = _room('loc_twins')
    for b in TWIN_HALF:
        r.paint(*b, OCCUPIED, rule='overlap')
    # rotate the raster itself, cell for cell: painting the rotated
    # rectangles instead is NOT exactly symmetric, because an edge that
    # lands on a cell centre rounds differently on each side (measured)
    cells = r.cells
    n = len(cells)
    for i in range(n):
        if cells[n - 1 - i] == OCCUPIED:
            cells[i] = OCCUPIED
    return r.build('loc_twins', frame='map',
                   meta={'source': 'coco_lab.loc_teaching',
                         'claim': '180-degree rotational symmetry'})


LANDMARKS_ROUTE = [(3.0, 2.5), (8.0, 1.2), (11.0, 4.0), (8.0, 7.0),
                   (4.0, 7.0), (1.2, 4.0), (3.0, 2.5)]
TWINS_ROUTE = [(2.0, 2.0), (2.0, 4.0), (3.5, 4.0)]


def scenarios() -> Dict[str, Tuple[str, Scenario, Dict[str, object]]]:
    """
    Return ``{id: (map_id, scenario, defaults)}`` for the teaching rooms.

    ``defaults`` are the filter settings the catalog bundle is computed
    with: ``init`` (``tracking`` or ``global``) and nothing else -- every
    other knob starts at its documented default.
    """
    tour = list(LANDMARKS_ROUTE)
    return {
        'tracking': ('loc_landmarks',
                     Scenario(start=(1.5, 1.5, 0.0), route=tour, seed=1),
                     {'init': 'tracking'}),
        'kidnap': ('loc_landmarks',
                   Scenario(start=(1.5, 1.5, 0.0), route=tour, seed=2,
                            kidnap=Kidnap(t=40.0, to=(9.0, 4.5, math.pi))),
                   {'init': 'tracking'}),
        'global': ('loc_landmarks',
                   Scenario(start=(3.0, 4.0, 0.5), route=tour[2:], seed=3),
                   {'init': 'global'}),
        'twins': ('loc_twins',
                  Scenario(start=(1.5, 2.0, 1.5708), route=TWINS_ROUTE,
                           seed=4),
                  {'init': 'global'}),
    }


def teaching_maps() -> Dict[str, LabMap]:
    """Return the two rooms by id."""
    return {'loc_landmarks': landmarks_map(), 'loc_twins': twins_map()}


def arena_scenario(seed: int = 5) -> Scenario:
    """
    Return a kidnap in COCO's arena (map frame; the spawn is map (0, 0)).

    The robot loops near the spawn and at t = 20 s is carried past the
    bays to map (16, 0), facing +y -- target K1 of the real-stack kidnap
    A/B (``docs/data/lab2``) -- where it drives two small loops.
    ``build_catalog`` pairs it with the saved Nav2 map at 0.10 m.
    """
    loop = [(16.0, 1.2), (15.2, 1.2), (15.2, -1.2), (16.0, -1.2), (16.0, 0.0)]
    return Scenario(start=(0.0, 0.0, 0.0),
                    route=[(-2.0, 0.0), (-2.0, 1.5), (0.0, 1.5), (0.0, 0.0)]
                    + loop + loop,
                    seed=seed, noise=Noise(),
                    kidnap=Kidnap(t=20.0, to=(16.0, 0.0, math.pi / 2)))


def route_points(sc: Scenario) -> List[Tuple[float, float]]:
    """Return the scenario's start followed by its waypoints."""
    return [sc.start[:2]] + list(sc.route)
