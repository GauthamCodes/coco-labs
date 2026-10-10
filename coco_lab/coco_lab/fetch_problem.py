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
Lab 4's bay search problem and the frozen target layout (M2.6). GENERATED.

Written by docs/v2/data/m2/m26/make_fetch_problem.py from
lab_web/tools/build_search.py ``arena_problem()`` (coco_config's
TARGET_REGIONS, A* travel on the Nav2 map, the mission's ASSUMED detection
0.9, a uniform prior) and coco_config's TARGETS. WORLD frame (the Arena's
map frame is world + (2, 0)). Do not edit: regenerate;
lab_web/tools/test_fetch_problem.py checks it.
"""

PROBLEM = {
    'regions': [
        {
            'id': 'bay_1',
            'label': 'Bay 1',
            'approach': [0.5, -6.0],
            'platform': [3.0, 4.2, -7.25, -4.75],
            'survey_pose': [2.95, -6.0, 0.0],
            'exit': [0.5, -6.0],
            'survey_cost': 4.9,
        },
        {
            'id': 'bay_2',
            'label': 'Bay 2',
            'approach': [0.5, -2.0],
            'platform': [3.0, 4.2, -3.25, -0.75],
            'survey_pose': [2.95, -2.0, 0.0],
            'exit': [0.5, -2.0],
            'survey_cost': 4.9,
        },
        {
            'id': 'bay_3',
            'label': 'Bay 3',
            'approach': [0.5, 2.0],
            'platform': [3.0, 4.2, 0.75, 3.25],
            'survey_pose': [2.95, 2.0, 0.0],
            'exit': [0.5, 2.0],
            'survey_cost': 4.9,
        },
        {
            'id': 'bay_4',
            'label': 'Bay 4',
            'approach': [0.5, 6.0],
            'platform': [3.0, 4.2, 4.75, 7.25],
            'survey_pose': [2.95, 6.0, 0.0],
            'exit': [0.5, 6.0],
            'survey_cost': 4.9,
        },
    ],
    'start': 'home',
    'start_xy': [-2.0, 0.0],
    'travel': {
        'bay_1': {
            'bay_1': 0.0,
            'bay_2': 6.943503,
            'bay_3': 10.943503,
            'bay_4': 14.943503,
        },
        'bay_2': {
            'bay_1': 6.943503,
            'bay_2': 0.0,
            'bay_3': 6.972792,
            'bay_4': 10.972792,
        },
        'bay_3': {
            'bay_1': 10.943503,
            'bay_2': 6.972792,
            'bay_3': 0.0,
            'bay_4': 6.972792,
        },
        'bay_4': {
            'bay_1': 14.943503,
            'bay_2': 10.972792,
            'bay_3': 6.972792,
            'bay_4': 0.0,
        },
        'home': {
            'bay_1': 7.797056,
            'bay_2': 3.826346,
            'bay_3': 3.767767,
            'bay_4': 7.767767,
        },
    },
    'detection': [0.9, 0.9, 0.9, 0.9],
    'prior': [0.25, 0.25, 0.25, 0.25],
    'meta': {
        'map': 'coco_navigation.yaml',
        'detection_is': 'assumed',
        'frame': 'world',
    },
}

#: the world: which bay each colour stands in (never the prior)
LAYOUT = {
    'red': 'bay_1',
    'green': 'bay_2',
    'blue': 'bay_3',
    'yellow': 'bay_4',
}

#: each bay's target, (x, y, z) world (z: the grasp height)
TARGET_NOMINAL = {
    'bay_1': [4.05, -6.0, 0.128],
    'bay_2': [4.05, -2.0, 0.128],
    'bay_3': [4.05, 2.0, 0.128],
    'bay_4': [4.05, 6.0, 0.128],
}

SPAWN_XY = [-2.0, 0.0]
