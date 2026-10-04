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
Sketch outcome counts over filter seeds, for the Localise lab's reveals.

A single run is not a rate. The lab shows one seeded run at a time, so
beside every predict-then-reveal it quotes how often the same outcome
happens over ``--seeds`` filter seeds ON THE SAME WORLD (the world seed is
the scenario's, fixed: only the filter's randomness varies). Everything
here is Sketch -- coco_lab's model, not the robot -- and is labelled so.

Usage (no ROS)::

    python3 docs/data/lab2/sketch_rates.py --seeds 20 \
        --out docs/data/lab2/sketch_rates.json
"""

import argparse
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

import coco_lab  # noqa: E402
from coco_lab import loc_teaching, localise as L, maps, sketch  # noqa: E402

NAV_YAML = os.path.join(REPO, 'gazebo_models', 'maps', 'coco_navigation.yaml')


def arena_map():
    """COCO's saved Nav2 map at 0.10 m, the arena scenario's map."""
    return maps.load_nav2(NAV_YAML).downsample(2, 'coco_navigation@0.10')


def experiments():
    """Return ``[(id, map, scenario, [(label, kind, params_fn)])]``."""
    rooms = loc_teaching.teaching_maps()
    sc = loc_teaching.scenarios()
    out = []

    def mcl(**kw):
        return lambda s: L.MCLParams(seed=s, **kw)

    mid, s, _ = sc['kidnap']
    out.append(('kidnap', rooms[mid], s, [
        ('mcl_off', 'mcl', mcl()),
        ('mcl_augmented', 'mcl', mcl(injection='augmented')),
        ('mcl_fixed_5pc', 'mcl', mcl(injection='fixed',
                                     inject_fraction=0.05)),
        ('ekf', 'ekf', None)]))
    mid, s, _ = sc['global']
    out.append(('global', rooms[mid], s, [
        ('mcl_300', 'mcl', mcl(init='global', particles=300)),
        ('mcl_1000', 'mcl', mcl(init='global', particles=1000)),
        ('ekf', 'ekf', None)]))
    mid, s, _ = sc['twins']
    out.append(('twins', rooms[mid], s, [
        ('mcl_1000', 'mcl', mcl(init='global', particles=1000)),
        ('ekf', 'ekf', None)]))
    mid, s, _ = sc['tracking']
    out.append(('tracking', rooms[mid], s, [
        ('mcl_300', 'mcl', mcl()), ('ekf', 'ekf', None)]))
    out.append(('arena_kidnap', arena_map(), loc_teaching.arena_scenario(),
                [('mcl_off_500', 'mcl', mcl(particles=500)),
                 ('mcl_augmented_500', 'mcl',
                  mcl(particles=500, injection='augmented')),
                 ('ekf', 'ekf', None)]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--seeds', type=int, default=20)
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    t_all = time.time()
    result = {'tool': 'docs/data/lab2/sketch_rates.py',
              'command': f'python3 docs/data/lab2/sketch_rates.py --seeds '
                         f'{args.seeds} --out {os.path.relpath(args.out, REPO)}',
              'label': 'Sketch (coco_lab model), not the robot',
              'coco_lab_version': coco_lab.__version__,
              'python': platform.python_version(),
              'seeds': list(range(args.seeds)),
              'definition': {'ok_xy_m': L.OK_XY, 'ok_yaw_rad': L.OK_YAW,
                             'hold_updates': L.OK_HOLD},
              'experiments': {}}
    for eid, lab_map, sc, runs in experiments():
        smap = sketch.SketchMap(lab_map)
        world = sketch.simulate(smap, sc)
        rec = {'map': lab_map.id, 'world_seed': sc.seed,
               'world_status': world.status, 'n_updates': len(world.updates),
               'kidnap_s': None if world.kidnap_row is None
               else world.t[world.kidnap_row], 'runs': {}}
        for label, kind, fn in runs:
            seeds = [0] if kind == 'ekf' else range(args.seeds)
            outs = []
            for s in seeds:
                if kind == 'ekf':
                    p = L.EKFParams(init='global' if eid in ('global', 'twins')
                                    else 'tracking')
                    tr = L.run_ekf(smap, world, p)
                else:
                    tr = L.run_mcl(smap, world, fn(s))
                sm = tr.summary
                outs.append({'seed': s, 'converged_s': sm['converged_s'],
                             'recovered': sm['recovered'],
                             'recovery_s': sm['recovery_s'],
                             'final_err_xy': sm['final_err_xy'],
                             'mean_err_xy': sm['mean_err_xy']})
            n = len(outs)
            conv = sum(1 for o in outs if o['converged_s'] is not None)
            recd = sum(1 for o in outs if o['recovered'])
            far = sum(1 for o in outs if o['final_err_xy'] > 2.0)
            times = sorted(o['recovery_s'] for o in outs if o['recovered'])
            rec['runs'][label] = {
                'kind': kind, 'n': n,
                'deterministic': kind == 'ekf',
                'converged': conv, 'recovered': recd,
                'final_err_over_2m': far,
                'recovery_s_sorted': times,
                'per_seed': outs}
            print(f'{eid:13s} {label:18s} n={n:2d} converged={conv:2d} '
                  f'recovered={recd:2d} final>2m={far:2d}', flush=True)
        result['experiments'][eid] = rec
    result['wall_s'] = round(time.time() - t_all, 1)
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
