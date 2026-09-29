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
The static smoke test's saved map, and its maker.

An 80 x 60 cell (4 m x 3 m) Nav2 saved map at 0.05 m, origin (0, 0):
border walls, an internal wall with a 0.8 m gap, and a box. Written with
``coco_lab.maps.to_nav2`` (trinary, map_saver's values). Run as a script
to rewrite the committed files; the test checks they equal this output.
"""

import os

from coco_lab.maps import LabMap, OCCUPIED, to_nav2

W, H, RES = 80, 60, 0.05
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
YAML, PGM = 'smoke_map.yaml', 'smoke_map.pgm'
#: Map-frame start and goal on either side of the internal wall.
START = (0.6, 0.6)
GOAL = (3.4, 2.4)


def make():
    """Return ``(yaml_text, pgm_bytes)``."""
    occ = bytearray(W * H)

    def block(c0, c1, r0, r1):          # columns and rows, TOP-down rows
        for r in range(r0, r1):
            for c in range(c0, c1):
                occ[r * W + c] = OCCUPIED
    block(0, W, 0, 2)
    block(0, W, H - 2, H)
    block(0, 2, 0, H)
    block(W - 2, W, 0, H)
    block(38, 41, 16, H)                 # the wall; gap at its top
    block(58, 66, 30, 38)                # the box
    m = LabMap(W, H, bytes(occ), resolution=RES, origin=(0.0, 0.0),
               frame='map', map_id='smoke')
    return to_nav2(m, PGM)


if __name__ == '__main__':
    y, p = make()
    with open(os.path.join(DIR, YAML), 'w', encoding='utf-8') as f:
        f.write(y)
    with open(os.path.join(DIR, PGM), 'wb') as f:
        f.write(p)
    print(DIR)
