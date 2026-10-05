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
Lab 3 (Map): what the site serves, every number from coco_lab or evidence.

Called by ``build_catalog.build``; writes under ``generated/``:

``map/<id>/``
    Map bundles. The Sketch scenes and the arena challenge are COMPUTED here
    by coco_lab (``map_teaching.scene_scenario``, the documented defaults,
    the world seed each scene was given before any outcome was known; no
    seed is picked for its outcome -- the 20-world counts sit beside it).
    The Replay is COPIED from ``docs/data/lab3/replay/`` (a recorded drive
    and the ROS backends' measured runs on it). Every bundle is written,
    loaded back with ``slambundle.load_slam_bundle`` and REPLAYED
    (``slambundle.replay_check``): a bundle that does not reproduce byte
    for byte, or whose scores do not recompute, fails the build.

and returns the catalog's ``map`` block: the bundles, the challenge's
documented score, Sketch's measured fidelity (Lab 2's: the same model),
the 20-world Sketch counts, and the real-backend results -- each marked
measured or ``not yet measured``.
"""

import json
import os
import shutil

import coco_lab
from coco_lab import bundle, map_teaching, mapworld, slambundle
from coco_lab.sketch import SketchMap
import build_localise
import common

LAB3 = os.path.join(common.REPO, 'docs', 'data', 'lab3')
TOOL = 'lab_web/tools/build_map.py'
NAV_YAML = os.path.join(common.REPO, 'gazebo_models', 'maps',
                        'coco_navigation.yaml')
SLAM_TEST = 'coco_lab/test'

#: id -> (title, scene id or 'arena', lesson, the tests it relies on)
SCENES = {
    'map_loop': (
        'Closing the loop (a ring room)', 'map_loop',
        'Drive round the block and come back. Odometry alone bends the '
        'map; pose-graph SLAM recognises where it started and pulls the '
        'whole loop straight. Compare it with the same pose graph with loop '
        'closure switched off -- and press "new world": it does not always '
        'recognise the start.',
        [f'{SLAM_TEST}/test_posegraph.py::test_loop_closure_usually_closes_'
         f'the_loop_room',
         f'{SLAM_TEST}/test_map_teaching.py::test_the_loop_rooms_drive_is_'
         f'a_loop']),
    'map_corridor': (
        'The featureless corridor', 'map_corridor',
        'Two rooms joined by 18 m of perfectly smooth corridor. A scan in '
        'the corridor pins the robot sideways and its heading, but says '
        'nothing about how far along it is: every SLAM here drifts there, '
        'and only the rooms at the ends bring it back.',
        [f'{SLAM_TEST}/test_map_teaching.py::test_a_scan_mid_corridor_'
         f'cannot_see_how_far_along_it_is',
         f'{SLAM_TEST}/test_map_teaching.py::test_the_corridor_is_two_'
         f'straight_featureless_walls',
         f'{SLAM_TEST}/test_posegraph.py::test_a_corridor_constrains_'
         f'nothing_along_its_axis']),
    'map_landmarks': (
        "Landmarks vs scans (Lab 2's room)", 'map_landmarks',
        "EKF-SLAM sees the room's box corners with an IDEALISED sensor "
        '(identity known, no false detections); FastSLAM and the pose '
        'graph see only the LiDAR. Same drive, same odometry, same scans.',
        [f'{SLAM_TEST}/test_ekfslam.py::test_ekf_slam_beats_odometry_on_'
         f'the_landmarks_room',
         f'{SLAM_TEST}/test_ekfslam.py::test_the_linear_case_equals_the_'
         f'exact_gaussian_posterior',
         f'{SLAM_TEST}/test_fastslam.py::test_fastslam_beats_odometry_on_'
         f'the_landmarks_room']),
}

#: the learner's starting settings for every Sketch scene (a MapSpec)
BASE_SPEC = {'noise_scale': map_teaching.NOISE_SCALE, 'particles': 20,
             'fastslam_seed': 0, 'runs': list(map_teaching.RUN_IDS)}
#: the challenge computes these runs: known poses (the best map YOUR drive
#: allows), odometry (the worst), and the two SLAMs the learner may enter
CHALLENGE_RUNS = ['known', 'odometry', 'fastslam', 'pose_graph']


def arena_map():
    """COCO's saved Nav2 map at 0.10 m: Lab 2's arena (any occupied wins)."""
    return build_localise.arena_map()


def _write(sb, out, sid):
    dst = os.path.join(out, 'map', sid)
    digest = slambundle.write_slam_bundle(sb, dst, 'gzip')
    back = slambundle.load_slam_bundle(dst)
    slambundle.replay_check(back)
    size = sum(os.path.getsize(os.path.join(dst, n)) for n in os.listdir(dst))
    return back, digest, size


def _runs(back):
    return [{'id': rid, 'algorithm': tr.algorithm, 'summary': tr.summary}
            for rid, tr in back.runs]


def _validated():
    return {'by': f'coco_lab {coco_lab.__version__} '
                  f'slambundle.load_slam_bundle',
            'replay': 'reproduced and re-scored byte for byte '
                      '(slambundle.replay_check)'}


def scene_entries(out):
    """Compute, write, load and replay every Sketch scene."""
    git = bundle.git_provenance(common.REPO)
    maps_ = map_teaching.teaching_maps()
    entries = []
    for sid, (title, scene, lesson, cites) in SCENES.items():
        m, sc = map_teaching.scene_scenario(scene, maps_)
        _, base = map_teaching.scenarios()[scene]
        world = mapworld.from_sketch(m, sc)
        prov = bundle.make_provenance('sketch', seed=sc.seed, git=git,
                                      tool=TOOL)
        sb = slambundle.SlamBundle.compute(m, world, map_teaching.run_specs(),
                                           prov)
        back, digest, size = _write(sb, out, sid)
        spec = dict(BASE_SPEC, seed=sc.seed,
                    clicks=[list(p) for p in base.route])
        entries.append({
            'id': sid, 'title': title, 'kind': 'sketch', 'path': f'map/{sid}/',
            'arrays_file': 'arrays.bin.gz', 'bytes': size,
            'content_hash': digest, 'map_id': m.id, 'spec': spec,
            'lesson': lesson, 'runs': _runs(back), 'validated': _validated(),
            'cites': cites})
    return entries


#: the challenge's documented score -- what the page prints, and how
CHALLENGE = {
    'title': 'Map the arena',
    'task': "Drive COCO's arena in Sketch and build the best map you can. "
            'The start, the world seed, the noise (Sketch\'s default) and the '
            'LiDAR are fixed; you choose the drive and which SLAM maps it.',
    'score': 'round(100 x F1), F1 of the map at 0.10 m against the arena '
             'it was driven in (coco_lab.mapeval.score_map)',
    'definition': {
        'precision': "share of the map's occupied cells within 0.10 m of a "
                     'truly occupied cell',
        'recall': "share of the arena's VISIBLE walls (wall cells next to "
                  'free space reachable from the start) with a mapped '
                  'occupied cell within 0.10 m',
        'f1': 'the harmonic mean of precision and recall',
        'coverage': 'share of the reachable free space the map has '
                    'observed (shown, not scored)',
    },
    'algorithms': ['pose_graph', 'fastslam'],
    'noise_scale': map_teaching.ARENA_NOISE_SCALE,
    'cites': [f'{SLAM_TEST}/test_mapeval.py::test_a_map_scored_against_'
              f'itself_is_perfect',
              f'{SLAM_TEST}/test_mapeval.py::test_the_tolerance_forgives_one_'
              f'cell_and_exact_does_not',
              f'{SLAM_TEST}/test_mapeval.py::test_unseen_walls_are_not_'
              f'counted_and_unknown_is_not_coverage'],
}


def challenge_entry(out):
    """The arena challenge's default drive, computed and replayed."""
    m = arena_map()
    base = map_teaching.arena_scenario()
    scale = map_teaching.ARENA_NOISE_SCALE
    sc = map_teaching.scenario_for(base, SketchMap(m), base.route, scale,
                                   base.seed)
    world = mapworld.from_sketch(m, sc, mapworld.LandmarkSpec(
        min_separation=2.0, max_count=64))
    prov = bundle.make_provenance('sketch', seed=sc.seed,
                                  git=bundle.git_provenance(common.REPO),
                                  tool=TOOL)
    sb = slambundle.SlamBundle.compute(
        m, world, map_teaching.run_specs(scale=scale,
                                         ids=tuple(CHALLENGE_RUNS)), prov)
    back, digest, size = _write(sb, out, 'map_arena')
    return {
        'id': 'map_arena', 'title': "Map the arena (COCO's saved map, "
        '0.10 m)', 'kind': 'challenge', 'path': 'map/map_arena/',
        'arrays_file': 'arrays.bin.gz', 'bytes': size, 'content_hash': digest,
        'map_id': m.id,
        'spec': dict(BASE_SPEC, seed=sc.seed, runs=CHALLENGE_RUNS,
                     noise_scale=scale,
                     clicks=[list(p) for p in base.route]),
        'lesson': CHALLENGE['task'], 'runs': _runs(back),
        'validated': _validated(), 'cites': CHALLENGE['cites']}


def replay_entries(out):
    """Copy, load and replay the committed recorded-drive bundles."""
    src_dir = os.path.join(LAB3, 'replay')
    entries = []
    if not os.path.isdir(src_dir):
        return entries
    for sid in sorted(os.listdir(src_dir)):
        dst = os.path.join(out, 'map', sid)
        shutil.copytree(os.path.join(src_dir, sid), dst)
        back = slambundle.load_slam_bundle(dst)
        slambundle.replay_check(back)
        size = sum(os.path.getsize(os.path.join(dst, n))
                   for n in os.listdir(dst))
        entries.append({
            'id': sid, 'title': "COCO's real 121 m tour (recorded in Gazebo)",
            'kind': 'replay', 'path': f'map/{sid}/',
            'arrays_file': 'arrays.bin.gz', 'bytes': size,
            'content_hash': back.manifest()['content_hash'],
            'map_id': back.lab_map.id, 'spec': None,
            'lesson': 'A drive recorded on the real stack in Gazebo, replayed '
                      'into slam_toolbox and Cartographer, and into '
                      "coco_lab's SLAMs -- identical scans, identical "
                      'odometry. The truth is the arena rasterised from the '
                      'world generator.',
            'runs': _runs(back),
            'external': [{'id': e.id, 'backend': e.backend, 'arm': e.arm,
                          'summary': e.summary, 'source': e.source}
                         for e in back.external],
            'validated': _validated(),
            'cites': ['docs/RESULTS.md "COCO Lab Phase 4"',
                      'docs/data/lab3/README.md']})
    return entries


def _load(name):
    p = os.path.join(LAB3, name)
    if not os.path.exists(p):
        return {'status': 'not yet measured'}
    with open(p) as f:
        return dict(json.load(f), status='measured')


def map_block(out):
    """Build Lab 3's files under ``out``; return the catalog block."""
    entries = scene_entries(out) + [challenge_entry(out)] + \
        replay_entries(out)
    return {
        'version': '1.0',
        'bundles': entries,
        'challenge': CHALLENGE,
        'fidelity': build_localise.fidelity(),
        'sketch_counts': _load('sketch_counts.json'),
        'real': _load('results.json'),
        'limits': {'noise_scale': [0, 5], 'particles': [2, 100],
                   'clicks': map_teaching.MAX_CLICKS},
        'run_ids': list(map_teaching.RUN_IDS),
    }
