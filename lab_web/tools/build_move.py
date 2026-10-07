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
Lab 5 (Move): what the site serves, every number from coco_lab or evidence.

Called by ``build_catalog.build``; writes under ``generated/move/``:

``replan/sketch_<seed>/``
    D* Lite episodes COMPUTED here by coco_lab (``replan.sketch_world``):
    a grid world whose map lacks some of its obstacles, and a closed door
    on the direct route. Seeds fixed before any outcome was known.
``replan/<id>/``
    COPIED from ``docs/data/lab5/replan/`` -- Experiment C: D* Lite on two
    of Nav2's own global costmaps, before and after a person stopped on
    the apron (a glass-box world from recorded snapshots).
``drive/<scenario>/``
    COPIED from ``docs/data/lab5/drive/`` -- the controller runs recorded
    in Gazebo (``lab5_evidence.py``).

Every replan bundle is written (or copied), loaded and REPLAYED
(``movebundle.replay_replan``: byte for byte); every drive bundle's
metrics are recomputed (``replay_drive``). One that does not reproduce
fails the build. Every quotation of run 15 is checked to appear verbatim
in ``docs/RESULTS.md``. Returns the catalog's ``move`` block.
"""

import json
import os
import shutil

import coco_lab
from coco_lab import bundle, movebundle as mb, replan
import common

LAB5 = os.path.join(common.REPO, 'docs', 'data', 'lab5')
RESULTS_MD = os.path.join(common.REPO, 'docs', 'RESULTS.md')
TOOL = 'lab_web/tools/build_move.py'
D = 'coco_lab/test/test_dstarlite.py'
R = 'coco_lab/test/test_replan.py'
B = 'coco_lab/test/test_movebundle.py'
L5 = 'coco_lab_ros/test/test_lab5.py'
MM = 'coco_lab/test/test_movemetrics.py'

#: The Sketch seeds the site ships, fixed before any outcome was known.
SEEDS = (0, 1, 2)

#: The Sketch's limits (the worker refuses outside them).
LIMITS = {'seed': [0, 9999], 'sense_radius': [1.5, 6.0],
          'max_painted': 200, 'width': 32, 'height': 20}

SCENARIO_LESSONS = {
    'static_room': 'One global path, frozen in a file: around the end of a '
                   'wall and into a room. Three controllers drive it on '
                   'the same robot with the same limits. Watch where each '
                   'one leaves the line.',
    'crossing': 'The same apron path, and a person crosses it in front of '
                'the robot. The global path does not move; only the local '
                'controller (and the collision monitor under it) can react.',
    'oncoming': 'A person walks straight down the robot\'s path towards '
                'it, and does not stop. Leaving the path is the only way '
                'past.',
    'mislocalised': 'The robot is told it is 3.4 m from where it is (run '
                    '15\'s measured gap). The global path is fine; the '
                    'robot\'s idea of where it stands is not.',
}

CONTROLLERS = [
    {'id': 'DWB', 'name': 'DWB (Dynamic Window)', 'colour': '#1f77b4',
     'how': 'Samples (v, w) pairs it can reach within one control step '
            '(819 per cycle with the mission\'s settings), rolls each '
            'forward 1.5 s, scores each with critics -- obstacle cost, '
            'distance to the path and the goal, alignment, oscillation -- '
            'and drives the best. A critic can reject a candidate outright.',
     'shows': 'every candidate it scored (Nav2\'s own /evaluation), '
              'rejected ones in red',
     'cites': ['gazebo_models/config/nav2_params.yaml (controller_server.'
               'FollowPath, the mission\'s, unchanged)',
               f'{L5}::test_the_overlay_adds_two_controllers_and_changes_'
               f'nothing_else']},
    {'id': 'MPPI', 'name': 'MPPI (Model Predictive Path Integral)',
     'colour': '#2ca02c',
     'how': 'Samples 2,000 noisy control sequences 2.8 s long, scores each '
            'whole trajectory with critics, and AVERAGES them, weighted by '
            'exp(-cost / temperature). The command is a blend of good '
            'trajectories, not the single best one.',
     'shows': 'a fifth of its samples, as Nav2 publishes them '
              '(/trajectories) -- MPPI publishes no per-sample score',
     'cites': ['coco_lab_ros/config/nav2_move_overlay.yaml (MPPI)']},
    {'id': 'RPP', 'name': 'Regulated Pure Pursuit', 'colour': '#d62728',
     'how': 'Chases a point 0.6 m ahead on the path along the arc through '
            'it, slows on tight curves, and checks that arc for collision '
            '-- and stops rather than swerve. It has no candidates: it '
            'follows the path or stops.',
     'shows': 'its lookahead point and the arc it checked '
              '(/lookahead_point, /lookahead_collision_arc)',
     'cites': ['coco_lab_ros/config/nav2_move_overlay.yaml (RPP)']},
]

CLAIMS = [
    {'id': 'same_inputs',
     'text': 'Every controller drives the SAME global path -- one file, its '
             'hash checked in every run -- on the same robot with the same '
             'speed, turn-rate and acceleration limits.',
     'cites': [f'{L5}::test_each_scenario_names_a_frozen_path_that_matches_'
               f'it', f'{L5}::test_no_controller_gets_a_faster_or_more_'
               f'agile_robot']},
    {'id': 'metrics',
     'text': 'Every number in the comparison is recomputed from the '
             'recording at site build by coco_lab; a bundle whose numbers '
             'do not reproduce is refused.',
     'cites': [f'{B}::test_a_metric_that_does_not_reproduce_is_refused',
               f'{MM}::test_box_clearance_axis_aligned_and_rotated']},
    {'id': 'actor',
     'text': 'The moving person is seen by the LiDAR but has no collision '
             'geometry: it cannot push the robot. A contact is measured, '
             'from ground truth, as a clearance of zero.',
     'cites': [f'{L5}::test_the_actor_has_no_collision_geometry',
               f'{MM}::test_an_actor_walking_through_the_robot_is_a_contact',
               'docs/RESULTS.md "COCO Lab Phase 6"']},
    {'id': 'dstar_optimal',
     'text': 'After every change and every move, D* Lite\'s plan costs '
             'exactly what Dijkstra finds from scratch on the new map.',
     'cites': [f'{D}::test_dstar_lite_is_optimal_after_every_change_and_'
               f'move', f'{R}::test_every_round_agrees_with_astar_from_'
               f'scratch']},
    {'id': 'dstar_arrives',
     'text': 'A robot whose map only lacks obstacles (never invents them) '
             'reaches the goal whenever the world has a route, and never '
             'steps into a cell it could have known was blocked.',
     'cites': [f'{R}::test_an_optimistic_robot_arrives_iff_the_world_has_'
               f'a_route']},
]


def _load_json(name):
    p = os.path.join(LAB5, name)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def _experiment_c():
    c = _load_json('replan_c.json')
    if c is None:
        return None
    keep = ('grid', 'resolution_m', 'window_map_frame', 'cells_changed',
            'newly_blocked', 'summary', 'before', 'after', 'content_hash')
    out = {k: c[k] for k in keep}
    out['rounds'] = [{k: v for k, v in r.items() if k != 'changed'}
                     for r in c['rounds']]
    return out


def work_claim():
    """The D* Lite work claim, composed from the evidence files (no typed numbers)."""
    st = _load_json('replan_sketch_stats.json')
    c = _load_json('replan_c.json')
    if st is None or c is None:
        return {'id': 'dstar_work', 'text': 'How D* Lite\'s work compares '
                'with A* from scratch: not yet measured.', 'cites': []}
    ratio = st['episode_ratio_dstar_over_astar']
    rep = c['rounds'][-1]
    return {
        'id': 'dstar_work',
        'text': (f"Same answer, not always less work. Over {st['seeds']} "
                 f"seeded Sketch worlds D* Lite's total work was below A* "
                 f"from scratch in {st['episodes_dstar_less_total']} "
                 f"(median {ratio['median']:.2f} of A*'s), yet in "
                 f"{st['replans_dstar_more']} of {st['replans']} single "
                 f"replans it did more; and on the real costmap change of "
                 f"Experiment C it touched {rep['dstar_expansions']:,} cells "
                 f"where A* from scratch touched {rep['astar_expansions']:,}."),
        'cites': ['docs/data/lab5/replan_sketch_stats.json',
                  'docs/data/lab5/replan_c.json',
                  'docs/RESULTS.md "COCO Lab Phase 6"',
                  f'{R}::test_every_round_agrees_with_astar_from_scratch']}

#: Run 15, as RESULTS.md records it. Each string is checked verbatim.
RUN15_QUOTES = [
    'DWBLocalPlanner: No valid trajectories out of 819!',
    'PathDistCritic: None of the 5 first of 5 (5) points of the global plan',
    'GoalDistCritic: None of the points of the global plan were in the '
    'local costmap.',
    '| | run 15 (failed) | run 11 (same colour, succeeded) |',
    '| ground truth, map | (8.747, 0.149) | (\u22120.085, 0.016) |',
    '| AMCL believed | (7.252, \u22122.962) | (\u22120.013, \u22120.055) |',
    '| **gap** | **3.4 m** | **0.10 m** |',
]


def _in_doc(path, needles):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    for n in needles:
        if n not in text:
            raise SystemExit(f'{path} does not contain {n!r}; the page '
                             f'quotes it')


def _size(d):
    return sum(os.path.getsize(os.path.join(d, n)) for n in os.listdir(d))


def _replan_entry(rid, title, kind, dst, lesson, cites):
    m = mb.replay_replan(dst)
    return {'id': rid, 'title': title, 'kind': kind,
            'path': f'move/replan/{rid}/',
            'arrays_file': 'arrays.bin.gz' if m['encoding']['compression']
            == 'gzip' else 'arrays.bin',
            'bytes': _size(dst), 'content_hash': m['content_hash'],
            'summary': m['summary'], 'world': m['world'],
            'validated': {'by': f'coco_lab {coco_lab.__version__}',
                          'replay': 'reproduced byte for byte '
                                    '(movebundle.replay_replan)'},
            'lesson': lesson, 'cites': cites}


def replan_entries(out):
    """Compute the Sketch episodes and copy Experiment C; replay all."""
    entries = []
    for seed in SEEDS:
        rid = f'sketch_{seed}'
        dst = os.path.join(out, 'move', 'replan', rid)
        prov = bundle.make_provenance('sketch', seed=seed,
                                      git=bundle.git_provenance(common.REPO),
                                      tool=TOOL)
        mb.write_replan_bundle(replan.run_replan(replan.sketch_world(seed)),
                               prov, dst, 'gzip')
        entries.append(_replan_entry(
            rid, f'A map with gaps in it (Sketch, seed {seed})', 'sketch',
            dst, 'The robot plans on the map it has. Some obstacles are '
            'missing from it, and a door on its direct route is closed. It '
            'sees 2.5 cells around itself; each time what it sees disagrees '
            'with its map, D* Lite repairs the plan.',
            [f'{R}::test_the_closed_door_forces_at_least_one_replan',
             f'{R}::test_every_round_agrees_with_astar_from_scratch']))
    src = os.path.join(LAB5, 'replan')
    if os.path.isdir(src):
        for rid in sorted(os.listdir(src)):
            dst = os.path.join(out, 'move', 'replan', rid)
            shutil.copytree(os.path.join(src, rid), dst)
            m = json.load(open(os.path.join(dst, 'manifest.json')))
            entries.append(_replan_entry(
                rid, m['provenance'].get('title') or rid, 'glass-box', dst,
                'Two of Nav2\'s own global costmaps from Gazebo: before and '
                'after a person stopped on the apron. D* Lite plans on the '
                'first, is handed the second, and repairs; A* searches the '
                'second from scratch. Same answer, different work.',
                ['docs/RESULTS.md "COCO Lab Phase 6"',
                 'docs/data/lab5/README.md']))
    return entries


def drive_entries(out):
    """Copy the recorded drive bundles; recompute every metric."""
    src = os.path.join(LAB5, 'drive')
    entries = []
    if not os.path.isdir(src):
        return entries
    for sid in sorted(os.listdir(src)):
        dst = os.path.join(out, 'move', 'drive', sid)
        shutil.copytree(os.path.join(src, sid), dst)
        m = mb.replay_drive(dst)
        entries.append({
            'id': sid, 'title': m['scenario']['title'], 'kind': 'replay',
            'path': f'move/drive/{sid}/', 'arrays_file': 'arrays.bin.gz',
            'bytes': _size(dst), 'content_hash': m['content_hash'],
            'runs': [{'id': r['id'], 'controller': r['controller'],
                      'outcome': r['outcome'], 'metrics': r['metrics'],
                      'has_rollouts': r['has_rollouts']}
                     for r in m['runs']],
            'validated': {'by': f'coco_lab {coco_lab.__version__}',
                          'replay': 'every metric recomputed from the '
                                    'recording (movebundle.replay_drive)'},
            'lesson': SCENARIO_LESSONS.get(sid, ''),
            'cites': ['docs/RESULTS.md "COCO Lab Phase 6"',
                      'docs/data/lab5/README.md']})
    return entries


def _results():
    p = os.path.join(LAB5, 'results.json')
    if not os.path.exists(p):
        return {'status': 'not yet measured'}
    with open(p) as f:
        r = json.load(f)
    for sc in r['scenarios'].values():
        sc.pop('rows', None)          # the bundles carry the per-run data
    return dict(r, status='measured')


def move_block(out):
    """Build Lab 5's files under ``out``; return the catalog block."""
    _in_doc(RESULTS_MD, RUN15_QUOTES)
    return {
        'version': '1.0',
        'replan': {'bundles': replan_entries(out), 'limits': LIMITS,
                   'experiment_c': _experiment_c(),
                   'sketch_stats': {k: v for k, v in (
                       _load_json('replan_sketch_stats.json') or {}).items()
                       if k != 'rows'} or None},
        'drive': {'bundles': drive_entries(out), 'results': _results()},
        'controllers': CONTROLLERS,
        'claims': CLAIMS + [work_claim()],
        'run15': {
            'quotes': RUN15_QUOTES,
            'source': 'docs/RESULTS.md "The one failure: run 15, and it is '
                      'a localisation failure" (the M6 fetch matrix in the '
                      'v1 wedge world; that text entered RESULTS.md on '
                      '2026-08-06, per git)',
            'reproduced': 'mislocalised',
        },
    }
