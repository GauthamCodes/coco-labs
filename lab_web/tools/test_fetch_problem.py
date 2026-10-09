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

"""coco_lab's generated fetch problem is Lab 4's, exactly (M2.6)."""

from coco_lab import fetch_problem
import build_search


def test_the_arena_fetch_searches_lab_4s_problem():
    assert fetch_problem.PROBLEM == build_search.arena_problem().to_dict()


def test_the_layout_and_the_targets_are_coco_configs():
    robot = build_search._robot()
    for t in robot.TARGETS:
        bay = fetch_problem.LAYOUT[t.colour]
        reg = [r for r in robot.TARGET_REGIONS if r.region_id == bay]
        assert reg[0].bay_y == t.lane_y
        assert fetch_problem.TARGET_NOMINAL[bay] == list(reg[0].target_nominal)
    assert fetch_problem.SPAWN_XY == list(robot.SPAWN_XY)
