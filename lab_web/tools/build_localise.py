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
Lab 2 (Localise): what the site serves, every number from evidence.

Called by ``build_catalog.build``; writes under ``generated/``:

``loc/<id>/``
    Localisation bundles ``coco_lab`` computes here (Sketch: the landmarks
    and twins rooms, and COCO's arena at 0.10 m). Each is written, loaded
    back with ``locbundle.load_loc_bundle`` and REPLAYED
    (``locbundle.replay_check``): a bundle that does not reproduce byte
    for byte fails the build. Filter seed 0 for every bundle -- no seed is
    picked for its outcome; the rate over 20 seeds sits beside it.
``loc_exhibits.json``
    COCO's four documented localisation failures, from committed
    evidence only, each figure checked to be printed where it is cited.

and returns the catalog's ``localise`` block: the bundles, the Sketch
fidelity result, the Sketch outcome counts, the real-stack results, and
which of them are ``not yet measured``.
"""

import csv
import json
import math
import os

import coco_lab
from coco_lab import bundle, loc_teaching, locbundle, maps
from coco_lab.localise import EKFParams, MCLParams
import common

LAB2 = os.path.join(common.REPO, 'docs', 'data', 'lab2')
RESULTS = os.path.join(common.REPO, 'docs', 'RESULTS.md')
NAV_YAML = os.path.join(common.REPO, 'gazebo_models', 'maps',
                        'coco_navigation.yaml')
TOOL = 'lab_web/tools/build_localise.py'
LOC_TEST = 'coco_lab/test/test_localise.py'
SKETCH_TEST = 'coco_lab/test/test_sketch.py'

#: id -> (title, map id or 'arena', scenario id or 'arena', the learner's
#: starting settings (a LocSpec), what it teaches, the tests it relies on)
SCENES = {
    'loc_tracking': (
        'Tracking a known start (landmarks room)', 'loc_landmarks',
        'tracking',
        {'particles': 300, 'injection': 'none', 'init': 'tracking'},
        'Both filters are told where the robot starts. Watch the particle '
        'cloud and the EKF ellipse stay small while the truth moves.',
        [f'{LOC_TEST}::test_both_filters_track_a_known_start']),
    'loc_kidnap': (
        'The kidnapped robot (landmarks room)', 'loc_landmarks', 'kidnap',
        {'particles': 300, 'injection': 'augmented', 'init': 'tracking'},
        'At t = 40 s the robot is picked up and carried 9.2 m to the far '
        'corner of the room; odometry is not '
        'told. Compare MCL with injection on, the same MCL with injection '
        'off (as COCO ships AMCL), and the EKF -- on one world.',
        [f'{LOC_TEST}::test_injection_is_what_recovers_a_kidnap',
         f'{LOC_TEST}::test_the_ekf_cannot_recover_a_kidnap_or_start_'
         f'globally',
         f'{SKETCH_TEST}::test_a_kidnap_moves_the_truth_and_not_the_'
         f'odometry']),
    'loc_global': (
        'Global localisation from nowhere (landmarks room)',
        'loc_landmarks', 'global',
        {'particles': 1000, 'injection': 'none', 'init': 'global'},
        'Nobody tells either filter where the robot starts. Particles '
        'cover the room; the EKF must start somewhere.',
        [f'{LOC_TEST}::test_mcl_converges_from_a_uniform_cloud_on_unique_'
         f'features']),
    'loc_twins': (
        'Perceptual aliasing (the twins room)', 'loc_twins', 'twins',
        {'particles': 1000, 'injection': 'none', 'init': 'global'},
        'Rotate this room 180 degrees and it is the same room: two poses '
        'see identical scans. A global start has two right answers.',
        [f'{SKETCH_TEST}::test_the_twins_room_is_symmetric_to_the_ray_'
         f'caster', f'{LOC_TEST}::test_the_twins_room_aliases']),
    'loc_arena_kidnap': (
        "A kidnap in COCO's arena (saved Nav2 map, 0.10 m)", 'arena',
        'arena',
        {'particles': 500, 'injection': 'augmented', 'init': 'tracking'},
        'The same kidnap as the real-stack A/B target K1: carried from the '
        'spawn past the bays. The arena has four near-identical bays.',
        [f'{LOC_TEST}::test_injection_is_what_recovers_a_kidnap']),
}

#: The learner's default settings, shared by every scene (overridden per
#: scene above). motion_noise 1.0 is Sketch's Noise() default.
BASE_SPEC = {'particles': 300, 'motion_noise': 1.0, 'sensor_sigma': 0.02,
             'injection': 'none', 'alpha_slow': 0.001, 'alpha_fast': 0.1,
             'inject_fraction': 0.05, 'init': 'tracking', 'kidnap': None,
             'seed': 0, 'filter_seed': 0}


def _in_doc(path, *needles):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    for n in needles:
        if n not in text:
            raise SystemExit(f'{path} does not contain {n!r}; Lab 2 cites '
                             f'it')


def arena_map():
    """COCO's saved Nav2 map, downsampled to 0.10 m (any occupied wins)."""
    return maps.load_nav2(NAV_YAML).downsample(2, 'coco_navigation@0.10')


def _scene(sid):
    title, mid, scen, over, lesson, cites = SCENES[sid]
    if mid == 'arena':
        lab_map, sc = arena_map(), loc_teaching.arena_scenario()
    else:
        lab_map = loc_teaching.teaching_maps()[mid]
        sc = loc_teaching.scenarios()[scen][1]
    spec = dict(BASE_SPEC, **over, seed=sc.seed)
    if sc.kidnap is not None:
        spec['kidnap'] = sc.kidnap.to_dict()
    return lab_map, sc, spec


def runs_for(spec):
    """The runs recompute.py's ``localise`` makes for ``spec`` (seed 0)."""
    alphas = (0.02 * spec['motion_noise'],) * 4
    hit = max(0.2, spec['sensor_sigma'])
    mcl = MCLParams(particles=spec['particles'], alphas=alphas,
                    sigma_hit=hit, init=spec['init'],
                    injection=spec['injection'],
                    alpha_slow=spec['alpha_slow'],
                    alpha_fast=spec['alpha_fast'],
                    inject_fraction=spec['inject_fraction'],
                    seed=spec['filter_seed'])
    runs = [('mcl', 'mcl', mcl)]
    if spec['injection'] != 'none':
        runs.append(('mcl_coco', 'mcl', MCLParams(
            particles=spec['particles'], alphas=alphas, sigma_hit=hit,
            init=spec['init'], injection='none', seed=spec['filter_seed'])))
    runs.append(('ekf', 'ekf', EKFParams(alphas=alphas, sigma_hit=hit,
                                          init=spec['init'])))
    return runs


def build_bundles(out):
    """Write, load and replay every scene's bundle; return catalog entries."""
    entries = []
    for sid in SCENES:
        title, _, _, _, lesson, cites = SCENES[sid]
        lab_map, sc, spec = _scene(sid)
        prov = bundle.make_provenance(
            'sketch', seed=sc.seed, git=bundle.git_provenance(common.REPO),
            tool=TOOL)
        lb = locbundle.LocBundle.compute(lab_map, sc, runs_for(spec), prov)
        dst = os.path.join(out, 'loc', sid)
        digest = locbundle.write_loc_bundle(lb, dst, 'gzip')
        back = locbundle.load_loc_bundle(dst)
        locbundle.replay_check(back)
        size = sum(os.path.getsize(os.path.join(dst, n))
                   for n in os.listdir(dst))
        entries.append({
            'id': sid, 'title': title, 'path': f'loc/{sid}/',
            'arrays_file': 'arrays.bin.gz', 'bytes': size,
            'content_hash': digest, 'map_id': lab_map.id,
            'source_kind': 'sketch', 'spec': spec, 'lesson': lesson,
            'runs': [{'id': rid, 'kind': tr.kind, 'summary': tr.summary}
                     for rid, tr in back.runs],
            'validated': {
                'by': f'coco_lab {coco_lab.__version__} '
                      f'locbundle.load_loc_bundle',
                'replay': 'reproduced byte for byte (locbundle.replay_check)'},
            'cites': cites,
        })
    return entries


# -- evidence ----------------------------------------------------------------

def _load(name):
    p = os.path.join(LAB2, name)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def fidelity():
    """The Sketch-vs-Gazebo result, or ``not yet measured``."""
    d = _load(os.path.join('fidelity', 'fidelity.json'))
    if d is None:
        return {'status': 'not yet measured'}
    s = d['scans']
    return {
        'status': 'measured',
        'cite': 'docs/RESULTS.md "COCO Lab Phase 3"; '
                'docs/data/lab2/fidelity/fidelity.json',
        'command': d['command'],
        'sessions': [m['session'] for m in d['sessions']],
        'scans_used': s['scans_used'], 'scans_recorded': s['scans_recorded'],
        'beams_both': s['classes']['both'], 'classes': s['classes'],
        'error_m': s['error_m']['all'], 'abs_error_m': s['abs_error_m'],
        'frac_abs_below': s['frac_abs_below'],
        'histogram': s['histogram'],
        'drives': [{k: dr[k] for k in (
            'session', 'drive', 'distance_m', 'rotation_rad', 'gazebo',
            'gazebo_truth_vs_commanded_unicycle_m',
            'sketch_zero_noise_final_pos_err_m', 'sketch_default_noise')}
            for dr in d['drives']],
    }


def sketch_rates():
    """The Sketch outcome counts over 20 filter seeds, or not measured."""
    d = _load('sketch_rates.json')
    if d is None:
        return {'status': 'not yet measured'}
    out = {'status': 'measured', 'label': d['label'],
           'cite': 'docs/data/lab2/sketch_rates.json (' + d['command'] + ')',
           'definition': d['definition'], 'experiments': {}}
    for eid, e in d['experiments'].items():
        out['experiments'][eid] = {
            'world_seed': e['world_seed'], 'kidnap_s': e['kidnap_s'],
            'runs': {k: {f: v[f] for f in ('kind', 'n', 'deterministic',
                                           'converged', 'recovered',
                                           'final_err_over_2m',
                                           'recovery_s_sorted')}
                     for k, v in e['runs'].items()}}
    return out


def kidnap_ab():
    """The real-stack recovery_alpha A/B, or ``not yet measured``."""
    d = _load('kidnap_ab.json')
    if d is None:
        return {'status': 'not yet measured'}
    return dict(d, status='measured')


def ekf_drift():
    """The robot_localization comparison, or ``not yet measured``."""
    d = _load('ekf_drift.json')
    if d is None:
        return {'status': 'not yet measured'}
    return dict(d, status='measured')


def amcl_odom():
    """AMCL on wheel odometry vs on the EKF, offline, or not measured."""
    d = _load('amcl_odom.json')
    if d is None:
        return {'status': 'not yet measured'}
    return dict(d, status='measured')


def covariance_series():
    """
    C2-M5.0 ``diverged1``: AMCL's covariance against its true error.

    Read from the committed CSV with C2-M5.0's own definitions
    (``docs/data/c2m5_analysis.py``: sigma_xy = sqrt(cxx + cyy); the truth
    moved into the map frame by WORLD_TO_MAP (2, 0)), and refused unless it
    reproduces RESULTS.md's table row at t_sim 104.5.
    """
    path = os.path.join(common.REPO, 'docs', 'data', 'c2m5_diverged1.csv')
    t, err, sig, d = [], [], [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r['state'] != 'RETURN_HOME':
                continue
            ts = float(r['t_sim'])
            if not 95.0 <= ts <= 140.0:
                continue
            e = math.hypot(float(r['amcl_x']) - (float(r['gt_x']) + 2.0),
                           float(r['amcl_y']) - float(r['gt_y']))
            t.append(ts)
            err.append(round(e, 4))
            sig.append(round(math.sqrt(float(r['amcl_cxx'])
                                       + float(r['amcl_cyy'])), 4))
            v = r['lik_mean_d']
            d.append(None if v in ('', 'nan') else float(v))
    k = min(range(len(t)), key=lambda i: abs(t[i] - 104.5))
    if (round(err[k], 3), round(sig[k], 3)) != (3.002, 0.070):
        raise SystemExit(f'c2m5_diverged1.csv at t={t[k]} gives err '
                         f'{err[k]} sigma {sig[k]}, not RESULTS.md\'s '
                         f'3.002 / 0.070')
    _in_doc(RESULTS, '| **104.5** | **3.002** | **0.070** |',
            'took **24.5 s** to climb past the')
    return {'t': t, 'err_xy': err, 'sigma_xy': sig, 'scan_map_d': d,
            'injection_t': t[k]}


def exhibits():
    """COCO's four documented failures, every figure checked at its source."""
    _in_doc(RESULTS, 'a full\n2π spin ran for 9.1 s',
            'the scan disagreed again 6.0 s after the mission\nresumed',
            'world **(2.60, −0.64)** — *inside the wedge footprint*',
            '| **gap** | **3.4 m** | **0.10 m** |',
            '| AMCL gap at descent end | 0.119 – **1.183 m**, mean 0.378, '
            'sd 0.216 |',
            'somewhere in **(0.470, 1.183) m**')
    planner = os.path.join(common.REPO, 'docs', 'data',
                           'c2m51_planner_after_recovery.txt')
    lines = [
        'AMCL converged to map (4.60, -0.64) = world (2.60, -0.64), which is',
        'INSIDE the wedge footprint (world x 1.0..6.5, |y| <= 1.25).',
    ]
    _in_doc(planner, *lines,
            'GridBased plugin failed to plan from (4.60, -0.64) to (0.00, '
            '0.00): "no valid path found"',
            '"Start occupied"')
    return {
        'tool': TOOL,
        'recovery_alpha': {
            'title': "Injection off: AMCL cannot leave a pose it is sure of",
            'historical': {
                'claim': "COCO's AMCL ships recovery_alpha_fast/slow = 0.0. "
                         'In C2-M5.1 a full 2π spin ran for 9.1 s after an '
                         'induced divergence; health came back, and the '
                         'scan disagreed again 6.0 s after the mission '
                         'resumed.',
                'label': 'historical (measured 2026-08-31, C2-M5.1)',
                'cite': 'docs/RESULTS.md "What the recovery cannot fix, '
                        'and why"'},
            'ab': kidnap_ab(),
            'sketch': 'loc_kidnap',
        },
        'aliasing': {
            'title': 'Global relocalisation converged inside the ramp',
            'historical': {
                'claim': 'C2-M5.1 asked AMCL to relocalise globally '
                         '(/reinitialize_global_localization). It converged '
                         'to world (2.60, -0.64) -- inside the wedge '
                         'footprint. The health monitor was satisfied; the '
                         'planner was not.',
                'log': lines,
                'label': 'historical (measured 2026-08-31, C2-M5.1, on '
                         'the v1 wedge world, not the current arena)',
                'cite': 'docs/RESULTS.md "Global relocalization converges '
                        'to an unplannable pose on this map"; '
                        'docs/data/c2m51_planner_after_recovery.txt'},
            'sketch': 'loc_twins',
        },
        'covariance': {
            'title': "Covariance is not health: AMCL's uncertainty moved "
                     'the wrong way',
            'historical': {
                'claim': 'At the injected 3 m divergence AMCL\'s sigma_xy '
                         'fell to 0.070 m -- smaller than anything in the '
                         'healthy run -- and took 24.5 s to climb past the '
                         'healthy maximum. The scan-vs-map distance left '
                         'its healthy envelope in 0.4 s.',
                'caveat': 'The injection itself hands AMCL a 0.05 m '
                          'covariance, so the dip to 0.070 is by '
                          'construction. What is measured is the 24.5 s '
                          'AMCL then took to notice, with real laser data '
                          'disagreeing the whole time.',
                'label': 'historical (measured 2026-08-31, C2-M5.0, run '
                         'diverged1, induced)',
                'cite': 'docs/RESULTS.md "C2-M5.0 localization health"; '
                        'docs/data/c2m5_diverged1.csv; '
                        'docs/data/c2m5_analysis.py'},
            'series': covariance_series(),
        },
        'run15': {
            'title': 'Run 15: 3.4 m of drift in the unmapped corridor',
            'historical': {
                'claim': 'M6 run 15 picked its target, then could not be '
                         'driven home: AMCL believed (7.252, -2.962) while '
                         'the robot was at (8.747, 0.149), a 3.4 m gap, '
                         'after dead-reckoning on skid-steer odometry '
                         'through a corridor the map left blank. Across '
                         'the 20 runs the gap at the end of the descent '
                         'was 0.119-1.183 m; the threshold lies somewhere '
                         'in (0.470, 1.183) m, nothing sampled between.',
                'label': 'historical (measured, M6 fetch matrix)',
                'cite': 'docs/RESULTS.md "The one failure: run 15, and it '
                        'is a localisation failure"'},
            'ekf': ekf_drift(),
            'amcl': amcl_odom(),
            'note': 'The robot_localization result is measured on Phase 3 '
                    'drives in the current arena, not on run 15, and does '
                    'not claim to fix it.',
        },
    }


def localise_block(out):
    """Build Lab 2's files under ``out``; return the catalog block."""
    entries = build_bundles(out)
    with open(os.path.join(out, 'loc_exhibits.json'), 'w') as f:
        f.write(json.dumps(exhibits(), indent=1, sort_keys=True) + '\n')
    return {
        'version': '1.0',
        'bundles': entries,
        'exhibits': 'loc_exhibits.json',
        'fidelity': fidelity(),
        'sketch_rates': sketch_rates(),
        'kidnap_ab': kidnap_ab(),
        'ekf_drift': ekf_drift(),
        'amcl_odom': amcl_odom(),
        'limits': {'particles': [10, 2000], 'motion_noise': [0, 5],
                   'sensor_sigma': [0, 0.5], 'inject_fraction': [0, 0.5]},
    }
