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
The REAL ``world_geometry`` against the REAL ``coco_config``.

Every other test that reaches ``welcome`` uses a fake node whose
``world_geometry`` is a stub, so nothing ever ran the method that reads
``coco_config.robot.TARGET_REGIONS``. When 917bc59 made
``TargetRegion.platform_bounds`` a plain tuple ``(x_min, x_max, y_min,
y_max)``, the method kept reading ``.x_min`` and every browser
connection raised ``AttributeError`` in ``ControlSocket.open()`` --
1,193 times in one live run, measured -- with 575 coco_web tests green.
The page sat on "Disconnected" and teleop moved nothing.
"""

import json
from types import SimpleNamespace

from coco_config import robot
from coco_web import platform_server as ps


def _geometry():
    """Call the unbound method; it touches ``self`` only to log."""
    quiet = SimpleNamespace(get_logger=lambda: SimpleNamespace(
        warn=lambda *_: None))
    return ps.CocoWebNode.world_geometry(quiet)


def test_world_geometry_builds_from_the_real_config():
    world = _geometry()
    assert world is not None, 'coco_config did not import'
    # It rides in `welcome`, so it must survive json.dumps unchanged.
    assert json.loads(json.dumps(world)) == world


def test_every_region_becomes_a_bay_in_map_coordinates():
    world = _geometry()
    shift = -robot.SPAWN_XY[0]
    assert world['offset_x'] == shift
    assert len(world['bays']) == len(robot.TARGET_REGIONS)
    for bay, region in zip(world['bays'], robot.TARGET_REGIONS):
        x_min, x_max, _, _ = region.platform_bounds
        assert bay['bay_id'] == region.region_id
        assert bay['y'] == region.bay_y
        assert bay['platform'] == {'x0': x_min + shift, 'x1': x_max + shift}
        assert bay['descent'] == {'x0': x_max + shift,
                                  'x1': region.descent_x + shift}
        assert bay['ramp']['x1'] == bay['platform']['x0']
