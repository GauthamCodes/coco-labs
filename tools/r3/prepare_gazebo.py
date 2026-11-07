#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.4: the generated Gazebo + Nav2 files for COCO-Bench v1's STACK baselines (outside the repository,
under ~/coco_lab_runs/r3/; never COCO's robot repository).

    tools/r3/prepare_gazebo.py

1. The cluttered Depot through the same toolchain and flags as G2's derivation 5 (checked: run on
   coco_depot_v1 it reproduces ~/coco_lab_runs/g2/gen_d5/coco_depot_v1 byte for byte):
   ``tools/m6/gen_level.py worlds/coco_depot_clutter_v1.yaml --derivation 5 --arena-res 0.1
   --arena-res 0.05 --nav-res 0.05`` into ``~/coco_lab_runs/r3/gen_d5/``, and its world laid out
   as G2's (``~/coco_lab_runs/r3/d5/<level>/gazebo_models/worlds/<level>.sdf`` + ``meshes/``).
2. Variants ``<gen>/<level>__<controller>/`` for controller in rpp, dwb, mppi: the level's files
   (gazebo/ and arena/ linked, nav2/ copied) with ``nav2_params.yaml`` changed as listed in its
   ``params_derivation.json`` (``r3`` entry); for the Depot also ``<level>__<controller>__noyield``
   (the actors keep their schedule: ``actors.json`` stop_margin_m -1000, relabelled; ctrl-dynamic-30):
   - every variant: Smac Hybrid-A* added to the planner server as ``SmacHybrid`` (beside
     ``GridBased`` = Smac 2D and ``NavFn``);
   - rpp: FollowPath unchanged (G2's RPP);
   - dwb / mppi: FollowPath replaced by Nav2 Jazzy's bringup defaults for DWB / MPPI, with COCO's
     limits (0.3 m/s, 1.0 rad/s, no reversing) and the same goal checker.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml

REPO = Path(__file__).resolve().parents[2]
RUNS = Path.home() / 'coco_lab_runs'
G2_GEN = RUNS / 'g2' / 'gen_d5'
R3_GEN = RUNS / 'r3' / 'gen_d5'
R3_D5 = RUNS / 'r3' / 'd5'
CLUTTER = 'coco_depot_clutter_v1'

SMAC_HYBRID = {'plugin': 'nav2_smac_planner::SmacPlannerHybrid', 'tolerance': 0.25,
               'allow_unknown': False, 'max_iterations': 1000000, 'max_planning_time': 5.0,
               'motion_model_for_search': 'DUBIN', 'angle_quantization_bins': 72,
               'analytic_expansion_ratio': 3.5, 'analytic_expansion_max_length': 3.0,
               'minimum_turning_radius': 0.3, 'reverse_penalty': 2.0, 'change_penalty': 0.0,
               'non_straight_penalty': 1.2, 'cost_penalty': 2.0, 'retrospective_penalty': 0.015,
               'lookup_table_size': 20.0, 'cache_obstacle_heuristic': False,
               'downsample_costmap': False, 'downsampling_factor': 1, 'smooth_path': True}

DWB = {'plugin': 'dwb_core::DWBLocalPlanner', 'debug_trajectory_details': False,
       'min_vel_x': 0.0, 'min_vel_y': 0.0, 'max_vel_x': 0.3, 'max_vel_y': 0.0,
       'max_vel_theta': 1.0, 'min_speed_xy': 0.0, 'max_speed_xy': 0.3, 'min_speed_theta': 0.0,
       'acc_lim_x': 2.5, 'acc_lim_y': 0.0, 'acc_lim_theta': 3.2, 'decel_lim_x': -2.5,
       'decel_lim_y': 0.0, 'decel_lim_theta': -3.2, 'vx_samples': 20, 'vy_samples': 5,
       'vtheta_samples': 20, 'sim_time': 1.7, 'linear_granularity': 0.05,
       'angular_granularity': 0.025, 'transform_tolerance': 0.2, 'xy_goal_tolerance': 0.25,
       'trans_stopped_velocity': 0.25, 'short_circuit_trajectory_evaluation': True,
       'stateful': True,
       'critics': ['RotateToGoal', 'Oscillation', 'BaseObstacle', 'GoalAlign', 'PathAlign',
                   'PathDist', 'GoalDist'],
       'BaseObstacle.scale': 0.02, 'PathAlign.scale': 32.0,
       'PathAlign.forward_point_distance': 0.1, 'GoalAlign.scale': 24.0,
       'GoalAlign.forward_point_distance': 0.1, 'PathDist.scale': 32.0, 'GoalDist.scale': 24.0,
       'RotateToGoal.scale': 32.0, 'RotateToGoal.slowing_factor': 5.0,
       'RotateToGoal.lookahead_time': -1.0}

MPPI = {'plugin': 'nav2_mppi_controller::MPPIController', 'time_steps': 56, 'model_dt': 0.05,
        'batch_size': 2000, 'ax_max': 3.0, 'ax_min': -3.0, 'ay_max': 3.0, 'az_max': 3.5,
        'vx_std': 0.2, 'vy_std': 0.2, 'wz_std': 0.4, 'vx_max': 0.3, 'vx_min': 0.0,
        'vy_max': 0.0, 'wz_max': 1.0, 'iteration_count': 1, 'prune_distance': 1.7,
        'transform_tolerance': 0.1, 'temperature': 0.3, 'gamma': 0.015,
        'motion_model': 'DiffDrive', 'visualize': False, 'regenerate_noises': True,
        'critics': ['ConstraintCritic', 'CostCritic', 'GoalCritic', 'GoalAngleCritic',
                    'PathAlignCritic', 'PathFollowCritic', 'PathAngleCritic',
                    'PreferForwardCritic'],
        'ConstraintCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 4.0},
        'GoalCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 5.0,
                       'threshold_to_consider': 1.4},
        'GoalAngleCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 3.0,
                            'threshold_to_consider': 0.5},
        'PreferForwardCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 5.0,
                                'threshold_to_consider': 0.5},
        'CostCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 3.81,
                       'near_collision_cost': 253, 'critical_cost': 300.0,
                       'consider_footprint': False, 'collision_cost': 1000000.0,
                       'near_goal_distance': 1.0, 'trajectory_point_step': 2},
        'PathAlignCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 14.0,
                            'max_path_occupancy_ratio': 0.05, 'trajectory_point_step': 4,
                            'threshold_to_consider': 0.5, 'offset_from_furthest': 20,
                            'use_path_orientations': False},
        'PathFollowCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 5.0,
                             'offset_from_furthest': 5, 'threshold_to_consider': 1.4},
        'PathAngleCritic': {'enabled': True, 'cost_power': 1, 'cost_weight': 2.0,
                            'offset_from_furthest': 4, 'threshold_to_consider': 0.5,
                            'max_angle_to_furthest': 1.0, 'mode': 0}}

CONTROLLERS = {'rpp': None, 'dwb': DWB, 'mppi': MPPI}


def generate_clutter():
    out = R3_GEN / CLUTTER
    if not out.exists():
        subprocess.run([sys.executable, '-P', str(REPO / 'tools/m6/gen_level.py'),
                        str(REPO / 'worlds' / f'{CLUTTER}.yaml'), '--out', str(R3_GEN),
                        '--derivation', '5', '--arena-res', '0.1', '--arena-res', '0.05',
                        '--nav-res', '0.05'], check=True)
    wdir = R3_D5 / CLUTTER / 'gazebo_models' / 'worlds'
    if not (wdir / f'{CLUTTER}.sdf').exists():
        wdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(out / 'gazebo' / f'{CLUTTER}.sdf', wdir / f'{CLUTTER}.sdf')
        shutil.copytree(out / 'gazebo' / 'meshes', wdir / 'meshes')
    return out


def variant(level_dir: Path, level: str, ctrl: str) -> Path:
    v = R3_GEN / f'{level}__{ctrl}'
    if v.exists():
        shutil.rmtree(v)
    (v / 'nav2').mkdir(parents=True)
    for sub in ('gazebo', 'arena'):
        os.symlink(level_dir / sub, v / sub)
    for f in (level_dir / 'nav2').iterdir():
        if f.name not in ('nav2_params.yaml', 'params_derivation.json'):
            shutil.copy(f, v / 'nav2' / f.name)
    p = yaml.safe_load((level_dir / 'nav2' / 'nav2_params.yaml').read_text())
    ps = p['planner_server']['ros__parameters']
    ps['planner_plugins'] = list(ps['planner_plugins']) + ['SmacHybrid']
    ps['SmacHybrid'] = SMAC_HYBRID
    changes = [{'key': 'planner_server: + SmacHybrid', 'to': 'nav2_smac_planner::SmacPlannerHybrid',
                'why': 'R3.4: the third Nav2 planner of the baseline (beside Smac 2D and NavFn)'}]
    if CONTROLLERS[ctrl] is not None:
        cs = p['controller_server']['ros__parameters']
        old = cs['FollowPath']['plugin']
        cs['FollowPath'] = CONTROLLERS[ctrl]
        changes.append({'key': 'controller_server.FollowPath', 'from': old,
                        'to': CONTROLLERS[ctrl]['plugin'],
                        'why': "R3.4: Nav2 Jazzy's bringup defaults for this controller, with "
                               "COCO's limits (0.3 m/s, 1.0 rad/s, no reversing)"})
    (v / 'nav2' / 'nav2_params.yaml').write_text(yaml.safe_dump(p, sort_keys=False, width=100))
    d = json.loads((level_dir / 'nav2' / 'params_derivation.json').read_text())
    d['r3'] = {'tool': 'tools/r3/prepare_gazebo.py', 'controller': ctrl, 'changes': changes}
    (v / 'nav2' / 'params_derivation.json').write_text(json.dumps(d, indent=1) + '\n')
    return v


def no_yield(v: Path) -> Path:
    """ctrl-dynamic-30's other half: the actors keep their schedule (a scenario rule, not physics)."""
    n = v.parent / (v.name + '__noyield')
    if n.exists():
        shutil.rmtree(n)
    shutil.copytree(v, n, symlinks=True)
    os.unlink(n / 'gazebo')
    shutil.copytree((v / 'gazebo').resolve(), n / 'gazebo')
    doc = json.loads((n / 'gazebo' / 'actors.json').read_text())
    r = doc['scenario_rule']
    r.update(id='actors_keep_schedule', stop_margin_m=-1000.0,
             label='Scenario rule (R3.4): the actors keep their schedule and never stop for COCO, '
                   'as Fetch Rush rules 4 in the model (actors.yield off)',
             model_rule='coco_lab.games.DepotActors.world_step (actors.yield off)',
             rule='as actors_yield_to_coco with stop_margin_m -1000: no hold is ever triggered')
    (n / 'gazebo' / 'actors.json').write_text(json.dumps(doc, indent=1) + '\n')
    d = json.loads((n / 'nav2' / 'params_derivation.json').read_text())
    d['r3']['actors'] = 'keep schedule (gazebo/actors.json scenario_rule.stop_margin_m = -1000)'
    (n / 'nav2' / 'params_derivation.json').write_text(json.dumps(d, indent=1) + '\n')
    return n


def main():
    clutter = generate_clutter()
    made = []
    for level, ldir in (('coco_depot_v1', G2_GEN / 'coco_depot_v1'), (CLUTTER, clutter)):
        for ctrl in CONTROLLERS:
            v = variant(ldir, level, ctrl)
            made.append(str(v))
            if level == 'coco_depot_v1':
                made.append(str(no_yield(v)))
    print('\n'.join(made))
    return 0


if __name__ == '__main__':
    sys.exit(main())
