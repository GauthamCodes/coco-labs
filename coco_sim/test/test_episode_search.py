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
Phase 5 (Lab 4): what a SEARCHING mission is given, against the manifest.

The episode spec already draws the line -- :meth:`EpisodeSpec.task_view`
is what the robot may know, the manifest is what the world and the
evaluator know. The searching mission is handed
:func:`search_mission_inputs`, and these tests prove it carries the
colour and nothing that depends on where the targets stand.
"""

import dataclasses
import json

from coco_config.robot import REGION_IDS, TARGET_COLOURS
from coco_sim.episode import (compat_mission_inputs, generate_episode,
                              InvalidEpisode, rebind, search_mission_inputs,
                              validate_episode)
import pytest


def _corrupted(spec, colour, dx=0.0, dy=0.0):
    """The manifest with one target's pose overwritten, UNVALIDATED.

    ``dataclasses.replace`` skips :func:`rebind`'s validation on purpose:
    the point is that even a manifest the evaluator would refuse cannot
    change what the searching robot is given.
    """
    targets = tuple(dataclasses.replace(t, x=t.x + dx, y=t.y + dy)
                    if t.colour == colour else t for t in spec.targets)
    return dataclasses.replace(spec, targets=targets)


def _moved_to(spec, colour, region_id):
    """The target moved to ``region_id``, swapping with whoever was there."""
    mine = spec.target(colour)
    other = next(t for t in spec.targets if t.region_id == region_id)
    targets = []
    for t in spec.targets:
        if t.colour == colour:
            t = dataclasses.replace(t, y=other.y, region_id=region_id)
        elif t.colour == other.colour:
            t = dataclasses.replace(t, y=mine.y, region_id=mine.region_id)
        targets.append(t)
    return rebind(spec, targets=tuple(targets))


def test_the_searching_mission_is_given_the_colour_and_nothing_else():
    spec = generate_episode(seed=4, level='colours', requested_colour='red')
    inputs = search_mission_inputs(spec)
    assert inputs == {'target_colour': 'red'}
    assert inputs['target_colour'] == spec.task_view()['requested_colour']


@pytest.mark.parametrize('level', ['fixed', 'colours', 'positions'])
@pytest.mark.parametrize('seed', range(12))
def test_the_inputs_do_not_depend_on_where_anything_stands(level, seed):
    spec = generate_episode(seed=seed, level=level, requested_colour='blue')
    text = json.dumps(search_mission_inputs(spec))
    for t in spec.targets:
        for v in (t.x, t.y, t.z):
            assert repr(v) not in text and f'{v:.2f}' not in text
    for rid in REGION_IDS:
        assert rid not in text
    assert 'lane' not in text


def test_corrupting_the_manifest_pose_changes_nothing_the_robot_gets():
    spec = generate_episode(seed=7, level='positions',
                            requested_colour='green')
    wild = _corrupted(spec, 'green', dx=123.4, dy=-56.7)
    assert wild.target('green').x != spec.target('green').x
    assert search_mission_inputs(wild) == search_mission_inputs(spec)
    # (The evaluator side refuses such a manifest outright.)
    with pytest.raises(InvalidEpisode):
        validate_episode(wild)


@pytest.mark.parametrize('colour', TARGET_COLOURS)
def test_moving_the_target_to_another_bay_needs_no_change(colour):
    spec = generate_episode(seed=0, level='fixed', requested_colour=colour)
    here = spec.target(colour).region_id
    for rid in REGION_IDS:
        if rid == here:
            continue
        moved = _moved_to(spec, colour, rid)
        assert moved.target(colour).region_id == rid
        assert search_mission_inputs(moved) == search_mission_inputs(spec)
        # ...whereas the told channel would have to change.
        assert compat_mission_inputs(moved)['region_map'] != \
            compat_mission_inputs(spec)['region_map']


def test_every_permutation_of_colours_gives_the_same_inputs():
    seen = set()
    for seed in range(40):
        spec = generate_episode(seed=seed, level='colours',
                                requested_colour='yellow')
        seen.add(json.dumps(search_mission_inputs(spec), sort_keys=True))
    assert seen == {'{"target_colour": "yellow"}'}
