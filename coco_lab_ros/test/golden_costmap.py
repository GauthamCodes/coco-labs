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
The golden costmap: a small ``costmap_raw``-shaped fixture, and its maker.

It is a 40 x 30 map at 0.05 m with a wall, a lethal post, an unknown
patch and an inflation-like cost gradient computed by Nav2's own inflation
formula (``(253 - 1) * exp(-csf * (d - r_inscribed))``, truncated to an
integer, for ``d`` beyond the inscribed radius; 253 within it; csf 5.0
and r 0.20 as in the mission's global costmap), so the planner meets
the same kind of cost field it meets live. Run as a script to (re)write
the committed JSON; the test checks the committed bytes equal what this
code makes.
"""

import json
import math
import os

W, H, RES = 40, 30, 0.05
ORIGIN = (-1.0, -0.5)
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures',
                    'golden_costmap.json')


def make():
    """Return the golden snapshot's fields as a dict (Nav2 order)."""
    lethal = set()
    for my in range(4, 24):                 # a wall with a gap at the top
        lethal.add((18, my))
    for mx in range(28, 31):                # a post
        for my in range(10, 13):
            lethal.add((mx, my))
    unknown = {(mx, my) for mx in range(5, 9) for my in range(20, 25)}
    data = []
    for my in range(H):
        for mx in range(W):
            if (mx, my) in lethal:
                data.append(254)
                continue
            if (mx, my) in unknown:
                data.append(255)
                continue
            d = min((math.hypot(mx - a, my - b) * RES
                     for a, b in lethal), default=99.0)
            if d <= 0.20:
                data.append(253)
            else:
                data.append(int(252 * math.exp(-5.0 * (d - 0.20))))
    return {'width': W, 'height': H, 'resolution': RES,
            'origin': list(ORIGIN), 'frame_id': 'map', 'data': data}


def text():
    """Return the fixture's canonical JSON text."""
    return json.dumps(make(), sort_keys=True, separators=(',', ':')) + '\n'


if __name__ == '__main__':
    with open(PATH, 'w', encoding='utf-8') as f:
        f.write(text())
    print(PATH)
