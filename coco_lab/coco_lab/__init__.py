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
COCO Lab core: traced graph search with its theorems tested.

Pure Python, standard library only, and never ``rclpy``: the same code runs
in CI, in the browser under Pyodide, and inside a ROS node.

Modules:

- :mod:`coco_lab.graph` -- the interface every algorithm searches
- :mod:`coco_lab.grid` -- the occupancy/cost grid, one implementation of it
- :mod:`coco_lab.heuristics` -- the four heuristics and the admissibility
  and consistency analysis the UI badge comes from
- :mod:`coco_lab.search` -- the five algorithms
- :mod:`coco_lab.trace` -- trace schema v1
- :mod:`coco_lab.maps` -- map schema v1, Nav2 saved-map import, rasterising
- :mod:`coco_lab.teaching` -- Lab 1's 20 x 20 teaching maps, claims tested
- :mod:`coco_lab.bundle` -- bundle format v1: save, check, load, replay
- :mod:`coco_lab.heading` -- the (cell, incoming heading) state space
- :mod:`coco_lab.isro` -- the ISRO simulator's search, verbatim, and its
  harness (historical behaviour, kept apart from the reference code)
"""

__version__ = '0.2.0'
