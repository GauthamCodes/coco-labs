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
Phase 5 (Lab 4): the mission discovers its target.

The machine is driven by the same scripted world as test_mission_states
(:class:`Harness`), with the arena's travel table held fixed so the
search order is known: at the assumed detection 0.9 coco_lab chooses
bay_3, bay_4, bay_2, bay_1 (coco_lab test_regionsearch pins why).

What is proven here, beyond the transitions themselves:

- a negative search: bay_3, then bay_4, then found in bay_2 -- each miss
  marked before the find, the belief updated each time;
- giving up after the first bay is an abort with nothing discovered;
- the choice of bay never reads the robot's pose, the colour, the
  perception line's told-lane field, or anything from an episode;
- silence is not a miss.
"""

import ast
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, HERE)
import mission_search as msearch  # noqa: E402
import mission_states as ms  # noqa: E402
from test_mission_states import Harness  # noqa: E402

from coco_lab import regionsearch as rs  # noqa: E402

#: The same table coco_lab's test pins against the Nav2 map.
ARENA_TRAVEL = {
    'home': {'bay_1': 7.797056, 'bay_2': 3.826346, 'bay_3': 3.767767,
             'bay_4': 7.767767},
    'bay_1': {'bay_1': 0.0, 'bay_2': 6.943503, 'bay_3': 10.943503,
              'bay_4': 14.943503},
    'bay_2': {'bay_1': 6.943503, 'bay_2': 0.0, 'bay_3': 6.972792,
              'bay_4': 10.972792},
    'bay_3': {'bay_1': 10.943503, 'bay_2': 6.972792, 'bay_3': 0.0,
              'bay_4': 6.972792},
    'bay_4': {'bay_1': 14.943503, 'bay_2': 10.972792, 'bay_3': 6.972792,
              'bay_4': 0.0},
}
BAY_Y = {'bay_1': -6.0, 'bay_2': -2.0, 'bay_3': 2.0, 'bay_4': 6.0}
POLICY_ORDER = ['bay_3', 'bay_4', 'bay_2', 'bay_1']


def session(policy='expected_cost', order=(), detection=0.9):
    problem = msearch.build_problem(None, detection, travel=ARENA_TRAVEL)
    given = msearch.parse_order(','.join(order), problem)
    return msearch.SearchSession(problem, policy, given)


def searching(colour='red', **kwargs):
    harness = Harness(ms.MissionPlan(colour, search=session(**kwargs)))
    harness.colour = colour
    for key in ('approach', 'grasp'):
        harness.lines[key] = harness.lines[key].replace('blue', colour)
    harness.publish('perception', f'sel={colour} found=0 seen=-- age=0.05')
    return harness


def tick_until_left(harness, state, limit=600):
    for _ in range(limit):
        if harness.state != state:
            return
        harness.tick()
    raise AssertionError(f'still in {state} after {limit} ticks')


def visit(harness, bay):
    """SELECT -> NAVIGATE -> ALIGN -> CLIMB -> VERIFY, into SURVEY."""
    y = BAY_Y[bay]
    # Driving between bays the camera sees no target.
    harness.publish('perception',
                    f'sel={harness.colour} found=0 seen=-- age=0.05')
    tick_until_left(harness, ms.SELECT_SEARCH_REGION, 5)
    assert harness.machine.plan.region == bay
    harness.tick()                            # the Nav2 goal goes out
    harness.nav_arrives(ms.PRE_RAMP_X, y)
    harness.tick(2)
    harness.worker('ramp', 'segment', 'climb', 'goal',
                   extra='lateral=+0.02 disp=+0.01',
                   pose=(ms.CLIMB_END_X, y, 0.0))
    harness.tick(2)
    assert harness.state == ms.SURVEY_REGION, harness.states()[-4:]


def miss(harness, seen='--', extra=''):
    colour = harness.colour
    harness.publish('perception',
                    f'sel={colour} found=0 seen={seen} age=0.05 {extra}')
    tick_until_left(harness, ms.SURVEY_REGION)
    assert harness.state == ms.MARK_REGION_SEARCHED
    harness.tick(2)
    assert harness.state == ms.LEAVE_REGION
    bay = harness.machine.plan.region
    harness.worker('ramp', 'segment', 'retreat', 'goal',
                   extra='lateral=+0.01 disp=+0.00',
                   pose=(0.65, BAY_Y[bay], 3.1))


def find(harness):
    harness.publish('perception',
                    f'sel={harness.colour} found=1 u=160 v=130 area=40 '
                    f'range=1.240 x=1.364 y=-0.012 z=0.071 seen='
                    f'{harness.colour} lane=-6.00 age=0.03')
    harness.tick(2)


def fetch_rest(harness):
    harness.worker('grasp', 'phase', 'stow', 'done', extra='lifted=0')
    harness.worker('approach', 'phase', 'servo', 'arrived')
    harness.worker('grasp', 'phase', 'pick:hover', 'held', extra='lifted=1')
    harness.tick(2)
    harness.worker('ramp', 'segment', 'descend', 'goal',
                   extra='lateral=+0.02 disp=+0.01')
    harness.nav_arrives(*ms.HOME)
    harness.worker('grasp', 'phase', 'place:lift', 'placed',
                   extra='lifted=0')
    harness.tick(2)


def start(harness):
    harness.tick(3)
    assert harness.state == ms.SELECT_SEARCH_REGION or \
        ms.SELECT_SEARCH_REGION in harness.states()


# -- the negative search, A then B then C ------------------------------------------

def test_a_then_b_then_found_in_c():
    h = searching('green')                     # green stands in bay_2
    start(h)
    visit(h, 'bay_3')
    miss(h, seen='blue')
    visit(h, 'bay_4')
    miss(h, seen='yellow')
    visit(h, 'bay_2')
    find(h)
    assert h.state == ms.STOW_ARM
    fetch_rest(h)
    assert h.state == ms.COMPLETE and h.machine.result == 'fetch'

    search = h.machine.plan.search
    assert [search.problem.ids[i] for i in search.order] == \
        ['bay_3', 'bay_4', 'bay_2']
    assert search.problem.ids[search.discovered] == 'bay_2'
    obs = search.observations
    assert [(o['region'], o['found']) for o in obs] == [
        ('bay_3', False), ('bay_4', False), ('bay_2', True)]
    assert obs[0]['seen'] == ['blue'] and obs[1]['seen'] == ['yellow']
    assert all(o['lines'] >= ms.SURVEY_MIN_LINES for o in obs[:2])
    # The discovery is perception's point, in base_footprint.
    assert obs[2]['point'] == (1.364, -0.012, 0.071)
    # Both misses were MARKED before the find.
    states = h.states()
    marks = [i for i, s in enumerate(states)
             if s == ms.MARK_REGION_SEARCHED]
    stow = states.index(ms.STOW_ARM)
    assert len(marks) == 2 and all(m < stow for m in marks)


def test_the_search_drives_to_each_chosen_bay_and_backs_out():
    h = searching('green')
    start(h)
    visit(h, 'bay_3')
    miss(h)
    visit(h, 'bay_4')
    miss(h)
    visit(h, 'bay_2')
    find(h)
    fetch_rest(h)
    navs = [p for k, p in h.requests if k == ms.NAV_GOAL]
    assert navs == [(ms.PRE_RAMP_X, 2.0), (ms.PRE_RAMP_X, 6.0),
                    (ms.PRE_RAMP_X, -2.0), ms.HOME]
    calls = [p for k, p in h.requests if k == ms.CALL_SERVICE]
    assert calls == ['/ramp/climb', '/ramp/retreat', '/ramp/climb',
                     '/ramp/retreat', '/ramp/climb', '/grasp/stow',
                     '/approach/run', '/grasp/pick', '/ramp/descend',
                     '/grasp/place']


def test_the_belief_after_each_miss_is_bayes_rule():
    h = searching('red')
    start(h)
    visit(h, 'bay_3')
    miss(h)
    b1 = h.machine.plan.search.belief
    expect = rs.update((0.25,) * 4, 2, False, 0.9)
    assert b1 == pytest.approx(expect)
    # Searched, not impossible: the camera can miss.
    assert 0 < b1[2] < b1[0]


def test_every_bay_empty_comes_home_and_says_so():
    h = searching('red')
    start(h)
    for bay in POLICY_ORDER:
        visit(h, bay)
        miss(h)
    assert h.state == ms.RETURN_HOME
    assert h.machine.degraded_reason == ms.SEARCH_EXHAUSTED
    h.nav_arrives(*ms.HOME)
    assert h.state == ms.ABORT
    assert h.machine.reason == ms.SEARCH_EXHAUSTED
    assert h.machine.result == 'aborted'
    calls = [p for k, p in h.requests if k == ms.CALL_SERVICE]
    # Never grasped, never drove forward over a deck.
    assert '/grasp/pick' not in calls and '/ramp/descend' not in calls
    assert calls.count('/ramp/retreat') == 4


def test_aborting_after_the_first_bay_fails_with_nothing_found():
    h = searching('green')                     # green is in bay_2, 3rd
    start(h)
    visit(h, 'bay_3')
    miss(h)
    h.abort_requested = True
    h.tick(2)
    h.recover()
    assert h.state == ms.ABORT
    assert h.machine.reason == ms.OPERATOR_ABORT
    assert h.machine.plan.search.discovered is None
    assert h.machine.result == 'aborted'


# -- silence is not a miss ---------------------------------------------------------

def test_a_survey_with_no_perception_lines_is_not_a_miss():
    h = searching('red')
    start(h)
    visit(h, 'bay_3')
    h.silent.add('perception')
    tick_until_left(h, ms.SURVEY_REGION)
    assert h.state == ms.RECOVERY
    assert h.machine.reason == ms.PERCEPTION_SILENT
    assert h.machine.plan.search.searched == ()
    assert h.machine.plan.search.observations == []


def test_silence_twice_leaves_by_the_ramp_and_aborts_at_home():
    h = searching('red')
    start(h)
    visit(h, 'bay_3')
    h.silent.add('perception')
    tick_until_left(h, ms.SURVEY_REGION)
    h.recover()
    assert h.state == ms.SURVEY_REGION        # one retry
    tick_until_left(h, ms.SURVEY_REGION)
    h.recover()
    assert h.state == ms.LEAVE_REGION         # never DESCEND over the deck
    h.worker('ramp', 'segment', 'retreat', 'goal',
             pose=(0.65, 2.0, 3.1))
    assert h.state == ms.RETURN_HOME
    h.nav_arrives(*ms.HOME)
    assert h.state == ms.ABORT and h.machine.reason == ms.PERCEPTION_SILENT


def test_lines_for_another_colour_do_not_count_toward_a_miss():
    h = searching('red')
    start(h)
    visit(h, 'bay_3')
    h.publish('perception', 'sel=blue found=0 seen=-- age=0.05')
    h.tick(3)
    assert ms.TARGET_COLOUR_MISMATCH in h.reasons()
    assert h.machine.plan.search.observations == []


def test_a_grasp_given_up_after_discovery_leaves_by_the_ramp():
    h = searching('blue')                      # blue is in bay_3, first
    start(h)
    visit(h, 'bay_3')
    find(h)
    for _ in range(2):                        # stow fails twice
        h.worker('grasp', 'phase', 'stow', 'failed', extra='lifted=0')
        h.recover()
    assert h.state == ms.LEAVE_REGION
    assert h.machine.degraded_reason == ms.STOW_FAILED


# -- what the choice reads, and what it does not -----------------------------------

@pytest.mark.parametrize('colour', ['red', 'green', 'blue', 'yellow'])
def test_the_first_bay_does_not_depend_on_the_colour(colour):
    h = searching(colour)
    start(h)
    tick_until_left(h, ms.SELECT_SEARCH_REGION, 5)
    assert h.machine.plan.region == 'bay_3'


def test_the_plan_holds_no_lane_until_the_search_chooses():
    plan = ms.MissionPlan('red', search=session())
    # The told mission would already hold bay_1 (red's frozen lane).
    assert plan.region is None and plan.lane == 0.0


def test_a_searching_plan_refuses_a_region_map():
    with pytest.raises(ValueError):
        ms.MissionPlan('red', search=session(),
                       region_map={'red': 'bay_2', 'green': 'bay_1',
                                   'blue': 'bay_3', 'yellow': 'bay_4'})


def test_the_ground_truth_pose_does_not_change_the_choice():
    picks = set()
    for pose in ((-2.0, 0.0, 0.0), (6.8, -6.0, 1.0), (0.5, 6.0, 3.0)):
        h = searching('red')
        h.pose = pose
        start(h)
        tick_until_left(h, ms.SELECT_SEARCH_REGION, 5)
        picks.add(h.machine.plan.region)
    assert picks == {'bay_3'}


def test_the_told_lane_on_the_perception_line_is_never_read():
    """target_finder's `lane=` is lane_for_colour: the told answer."""
    runs = []
    for extra in ('', 'lane=-6.00', 'lane=+6.00'):
        h = searching('red')
        start(h)
        visit(h, 'bay_3')
        miss(h, extra=extra)
        visit(h, 'bay_4')
        runs.append((tuple(h.machine.plan.search.order),
                     h.machine.plan.search.belief, h.states()))
    assert runs[0] == runs[1] == runs[2]


def test_a_given_order_is_followed_and_a_short_one_ends_exhausted():
    h = searching('green', policy='given', order=('bay_1',))
    start(h)
    visit(h, 'bay_1')
    miss(h)
    assert h.state == ms.RETURN_HOME
    assert h.machine.degraded_reason == ms.SEARCH_EXHAUSTED


def test_the_selection_check_reads_only_the_search_state():
    src = open(os.path.join(HERE, '..', 'scripts', 'mission_states.py'))
    tree = ast.parse(src.read())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == '_check_select_search_region')
    reads = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)
             and isinstance(n.value, ast.Name) and n.value.id == 'obs'}
    assert reads == set(), reads


def test_mission_search_never_touches_episode_or_told_inputs():
    text = open(os.path.join(HERE, '..', 'scripts',
                             'mission_search.py')).read()
    tree = ast.parse(text)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported |= {a.name for a in node.names}
            imported.add(node.module)
    assert 'coco_sim' not in ' '.join(m for m in imported if m)
    for name in ('resolve_lane', 'lane_for_colour', 'region_map',
                 'FIXED_REGION_MAP', 'TARGETS', 'target_by_colour'):
        assert name not in imported, name


# -- the session and its line ------------------------------------------------------

def test_the_status_line_parses_and_says_discover():
    s = session()
    s.select()
    s.observe(False, seen=['blue'], lines=12)
    fields = ms.parse_kv(s.status_line())
    assert fields['mode'] == 'discover'
    assert fields['order'] == 'bay_3' and fields['searched'] == 'bay_3'
    assert fields['seen'] == 'blue' and fields['discovered'] == '--'
    assert len(fields['belief'].split(',')) == 4
    assert ms.parse_kv(msearch.TOLD_LINE) == {'mode': 'told'}


def test_a_bad_order_is_refused():
    problem = msearch.build_problem(None, travel=ARENA_TRAVEL)
    with pytest.raises(ValueError):
        msearch.parse_order('bay_9', problem)
    with pytest.raises(ValueError):
        msearch.parse_order('bay_1,bay_1', problem)
    with pytest.raises(ValueError):
        msearch.SearchSession(problem, 'nearest')


def test_the_prior_is_uniform_and_the_detection_is_labelled_assumed():
    problem = msearch.build_problem(None, travel=ARENA_TRAVEL)
    assert problem.prior == (0.25,) * 4
    assert problem.meta['detection_is'] == 'assumed'
    assert problem.detection == (msearch.DEFAULT_DETECTION,) * 4


def test_the_installed_map_gives_the_pinned_table():
    path = os.path.join(HERE, '..', '..', 'gazebo_models', 'maps',
                        'coco_navigation.yaml')
    assert msearch.build_problem(path).travel == ARENA_TRAVEL


# -- the launch file ---------------------------------------------------------------

def _resolve(**configs):
    import importlib.util
    from launch import LaunchContext
    from launch.actions import SetLaunchConfiguration
    launch = os.path.join(HERE, '..', 'launch', 'mission.launch.py')
    spec = importlib.util.spec_from_file_location('coco_mission_launch_s',
                                                  launch)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = LaunchContext()
    base = {'episode_level': 'fixed', 'episode_seed': '0',
            'episode_manifest': '', 'target_colour': 'blue',
            'search': 'true'}
    base.update({k: str(v) for k, v in configs.items()})
    context.launch_configurations.update(base)
    for action in module.resolve_mission_episode(context):
        if isinstance(action, SetLaunchConfiguration):
            action.execute(context)
    return context


def test_searching_an_episode_sets_the_colour_and_no_region_map():
    context = _resolve(episode_level='colours', episode_seed='1827',
                       target_colour='red')
    assert 'coco_episode_region_map' not in context.launch_configurations
    assert context.launch_configurations['target_colour'] == 'red'


def test_moving_the_target_launches_the_same_search(tmp_path):
    """Two valid manifests, the yellow target in different bays."""
    import dataclasses
    from coco_sim.episode import generate_episode, rebind
    spec = generate_episode(seed=3, level='positions',
                            requested_colour='yellow')
    mine = spec.target('yellow')
    other = next(t for t in spec.targets if t.colour != 'yellow')
    moved = rebind(spec, targets=tuple(
        dataclasses.replace(t, y=other.y, region_id=other.region_id)
        if t.colour == 'yellow' else
        dataclasses.replace(t, y=mine.y, region_id=mine.region_id)
        if t.colour == other.colour else t
        for t in spec.targets))
    assert moved.target('yellow').region_id != mine.region_id
    configs = []
    for n, s in enumerate((spec, moved)):
        path = tmp_path / f'm{n}.json'
        path.write_text(s.to_json())
        context = _resolve(episode_manifest=path, target_colour='blue')
        configs.append({k: v for k, v in
                        context.launch_configurations.items()
                        if k != 'episode_manifest'})
    assert configs[0] == configs[1]
    assert configs[0]['target_colour'] == 'yellow'


def test_the_launch_file_searches_by_default_and_tells_both_nodes():
    body = open(os.path.join(HERE, '..', 'launch',
                             'mission.launch.py')).read()
    assert "'search', default_value='true'" in body
    # ramp_driver's datum and the executive's mode come from ONE argument.
    assert "'search_mode': ParameterValue(\n                    " \
        "LaunchConfiguration('search')" in body
    assert "'search': ParameterValue(\n                    " \
        "LaunchConfiguration('search')" in body
