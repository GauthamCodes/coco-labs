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
Lab 4 (Search): what the site serves, every number from coco_lab or evidence.

Called by ``build_catalog.build``; writes under ``generated/``:

``search/search_arena/``
    A search bundle COMPUTED here by coco_lab: COCO's four bays (the regions
    of ``coco_config``'s TARGET_REGIONS, loaded by path), travel measured by
    coco_lab's A* on the robot's own Nav2 map, the mission's assumed
    detection and a uniform prior -- the same problem the real mission
    builds (``coco_mission/scripts/mission_search.py``). Its runs: the
    robot's policy with the target in each bay, the two teaching policies
    and a search that gives up after one bay, all at world seed 0 (fixed
    before any outcome was known).

``search/<recorded id>/``
    COPIED from ``docs/data/lab4/replay/`` -- searches the real mission ran
    in Gazebo, rebuilt from their looks alone (``replay_search``).

Every bundle is written, loaded back and REPLAYED
(``searchbundle.replay_check``); one that does not reproduce byte for byte
fails the build. Returns the catalog's ``search`` block.
"""

import importlib.util
import json
import os
import shutil

import coco_lab
from coco_lab import bundle, regionsearch as rs, searchbundle as sbm
from coco_lab.maps import load_nav2
import common

LAB4 = os.path.join(common.REPO, 'docs', 'data', 'lab4')
TOOL = 'lab_web/tools/build_search.py'
NAV_YAML = os.path.join(common.REPO, 'gazebo_models', 'maps',
                        'coco_navigation.yaml')
ROBOT_PY = os.path.join(common.REPO, 'coco_config', 'coco_config',
                        'robot.py')
MISSION_SEARCH = os.path.join(common.REPO, 'coco_mission', 'scripts',
                              'mission_search.py')
T = 'coco_lab/test/test_regionsearch.py'
M = 'coco_mission/test/test_mission_search.py'
E = 'coco_sim/test/test_episode_search.py'

#: The seed every default Sketch run uses, fixed before any outcome.
SEED = 0


def _robot():
    spec = importlib.util.spec_from_file_location('coco_robot_search',
                                                  ROBOT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mission_detection():
    """The mission's assumed d, read from mission_search.py's source."""
    import ast
    tree = ast.parse(open(MISSION_SEARCH).read())
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], 'id', '') ==
                'DEFAULT_DETECTION'):
            return float(ast.literal_eval(node.value))
    raise SystemExit('mission_search.DEFAULT_DETECTION not found')


def arena_problem():
    """The searching mission's problem, built the way it builds it."""
    robot = _robot()
    regs = rs.bay_regions(robot.TARGET_REGIONS, robot.CLIMB_END_X)
    travel = rs.travel_costs(
        load_nav2(NAV_YAML, 'coco_navigation'),
        rs.places_of(regs, robot.SPAWN_XY), [r.id for r in regs], 0.20,
        offset=(-robot.SPAWN_XY[0], -robot.SPAWN_XY[1]))
    return rs.bay_problem(regs, robot.SPAWN_XY, travel, mission_detection(),
                          meta={'map': 'coco_navigation.yaml',
                                'detection_is': 'assumed',
                                'frame': 'world'})


def _runs(p):
    out = []
    for i, rid in enumerate(p.ids):
        out.append(sbm.SearchRun(f'robot_{rid}', 'sketch', rs.run_search(
            p, 'expected_cost', i, seed=SEED)))
    last = p.index('bay_1')
    out.append(sbm.SearchRun('nearest_bay_1', 'sketch', rs.run_search(
        p, 'nearest', last, seed=SEED)))
    out.append(sbm.SearchRun('likely_bay_1', 'sketch', rs.run_search(
        p, 'most_likely', last, seed=SEED)))
    out.append(sbm.SearchRun('gave_up_bay_1', 'sketch', rs.run_search(
        p, 'expected_cost', last, seed=SEED, max_surveys=1)))
    return out


def _write(sb, out, sid):
    dst = os.path.join(out, 'search', sid)
    digest = sbm.write_search_bundle(sb, dst, 'gzip')
    back = sbm.load_search_bundle(dst)
    sbm.replay_check(back)
    size = sum(os.path.getsize(os.path.join(dst, n)) for n in os.listdir(dst))
    return back, digest, size


def _entry(sid, title, kind, back, digest, size, lesson, cites, extra=None):
    e = {'id': sid, 'title': title, 'kind': kind,
         'path': f'search/{sid}/', 'arrays_file': 'arrays.bin.gz',
         'bytes': size, 'content_hash': digest,
         'runs': [{'id': r.id, 'kind': r.kind, 'policy':
                   r.trace.header['policy'], 'summary': r.trace.summary}
                  for r in back.runs],
         'validated': {'by': f'coco_lab {coco_lab.__version__}',
                       'replay': 'byte-identical'},
         'lesson': lesson, 'cites': cites}
    e.update(extra or {})
    return e


def arena_entry(out):
    """The default Sketch bundle, computed and replayed."""
    p = arena_problem()
    prov = bundle.make_provenance('sketch', seed=SEED,
                                  git=bundle.git_provenance(common.REPO),
                                  tool=TOOL)
    back, digest, size = _write(sbm.SearchBundle(prov, p, _runs(p)), out,
                                'search_arena')
    return _entry(
        'search_arena', "COCO's four bays (Sketch: the robot's own problem)",
        'sketch', back, digest, size,
        'The robot is told "red" and nothing else. It knows its map, the '
        'four bays, what it costs to drive to each and climb its ramp, and '
        'that its camera misses a target that is there one time in ten '
        '(an ASSUMPTION, labelled). Where should it look first?',
        [f'{T}::test_the_arena_order_when_the_camera_can_miss_is_not_'
         f'nearest_first',
         f'{T}::test_the_arena_travel_table_is_coco_labs_astar_on_the_'
         f'nav2_map',
         f'{M}::test_the_first_bay_does_not_depend_on_the_colour'])


def replay_entries(out):
    """Copy, load and replay the committed Gazebo search bundles."""
    src_dir = os.path.join(LAB4, 'replay')
    entries = []
    if not os.path.isdir(src_dir):
        return entries
    for sid in sorted(os.listdir(src_dir)):
        dst = os.path.join(out, 'search', sid)
        shutil.copytree(os.path.join(src_dir, sid), dst)
        back = sbm.load_search_bundle(dst)
        sbm.replay_check(back)
        size = sum(os.path.getsize(os.path.join(dst, n))
                   for n in os.listdir(dst))
        entries.append(_entry(
            sid, back.provenance.get('title') or
            'The real mission, searching in Gazebo', 'replay', back,
            back.manifest()['content_hash'], size,
            'Searches the real mission ran in Gazebo, told only the colour. '
            "Each is rebuilt from the robot's own looks: coco_lab chooses "
            'every bay again from the same belief, and a recording that '
            'disagreed would not load. Where the target really stood comes '
            'from the episode manifest -- the evaluator side -- and is '
            'shown only as truth.',
            ['docs/RESULTS.md "COCO Lab Phase 5"',
             'docs/data/lab4/README.md',
             'coco_lab/test/test_searchbundle.py::test_a_recording_that_'
             'disagrees_with_the_policy_is_refused']))
    return entries


def _load(name):
    p = os.path.join(LAB4, name)
    if not os.path.exists(p):
        return {'status': 'not yet measured'}
    with open(p) as f:
        return dict(json.load(f), status='measured')


#: What the page says, each claim with the evidence it rests on.
CLAIMS = [
    {'id': 'bayes',
     'text': 'A miss is evidence, not proof: with d = 0.9 a searched bay '
             'keeps a little belief, and the others rise.',
     'cites': [f'{T}::test_update_is_bayes_rule_against_the_enumerated_'
               f'joint', f'{T}::test_a_find_is_certain_and_a_perfect_miss_'
               f'is_proof']},
    {'id': 'index_rule',
     'text': 'If every bay cost the same to reach from anywhere, "most '
             'likely per metre first" would be optimal. COCO\'s bays do '
             'not, so the robot costs every order.',
     'cites': [f'{T}::test_index_rule_is_optimal_when_costs_do_not_depend_'
               f'on_order', f'{T}::test_the_robot_order_is_no_worse_than_'
               f'any_other_order']},
    {'id': 'counterexample',
     'text': 'With a camera that can miss, nearest-first is beaten: a '
             'search that finds nothing drives the whole tour, so the '
             "tour's length counts.",
     'cites': [f'{T}::test_the_arena_order_when_the_camera_can_miss_is_'
               f'not_nearest_first',
               f'{T}::test_the_arena_order_with_a_perfect_camera_is_'
               f'nearest_first']},
    {'id': 'negative',
     'text': 'Negative search: bay A, then B, then found in C -- each miss '
             'marked before the find. Giving up after A fails the '
             'challenge, whatever it saved.',
     'cites': [f'{T}::test_negative_search_finds_it_in_the_last_region_'
               f'checked', f'{T}::test_giving_up_after_the_first_region_'
               f'fails_the_challenge', f'{M}::test_a_then_b_then_found_'
               f'in_c', f'{M}::test_aborting_after_the_first_bay_fails_'
               f'with_nothing_found']},
    {'id': 'anticheat',
     'text': 'The real mission is told the colour and nothing else: no '
             'bay, no pose. Moving the target, or corrupting the manifest, '
             'changes nothing the robot is given; the policy has no field '
             'that could hold the truth.',
     'cites': [f'{E}::test_moving_the_target_to_another_bay_needs_no_'
               f'change', f'{E}::test_corrupting_the_manifest_pose_changes_'
               f'nothing_the_robot_gets',
               f'{T}::test_no_field_a_policy_reads_can_hold_the_truth',
               f'{M}::test_the_told_lane_on_the_perception_line_is_never_'
               f'read']},
    {'id': 'silence',
     'text': 'Silence is not a miss: a look with no camera reports is a '
             'failure, never evidence that the target is absent.',
     'cites': [f'{M}::test_a_survey_with_no_perception_lines_is_not_a_'
               f'miss']},
]


def search_block(out):
    """Build Lab 4's files under ``out``; return the catalog block."""
    entries = [arena_entry(out)] + replay_entries(out)
    return {
        'version': '1.0',
        'bundles': entries,
        'claims': CLAIMS,
        'matrix': _load('results.json'),
        'policies': list(rs.POLICIES),
        'limits': {'detection': [0.5, 1.0], 'max_surveys': [1, 4],
                   'seed': [0, 2 ** 31 - 1]},
        'challenge': {
            'title': 'Find it',
            'task': 'Choose the order the robot looks in, predict whether '
                    'yours beats the robot\'s policy on expected cost, then '
                    'place the target and watch both search.',
            'score': 'Pass = the target found. Stopping early fails, '
                     'whatever it saved.',
            'cites': [f'{T}::test_giving_up_after_the_first_region_fails_'
                      f'the_challenge']},
    }
