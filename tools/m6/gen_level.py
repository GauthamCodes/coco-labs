#!/usr/bin/env python3
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
Compile a World Spec into its three outputs (M6F.2; coco_lab.worldgen).

    gen_level.py worlds/coco_depot_v1.yaml --out tools/m6/out [--gz-check]
        [--arena-res 0.1 --arena-res 0.05] [--nav-res 0.05]
        [--checksums docs/v2/m6/data/coco_depot_v1_outputs.json] [--verify]

Writes ``<out>/<id>/``:

- ``arena/arena_world_<res>.json`` -- the Arena model world at each resolution;
- ``gazebo/<id>.sdf`` plus ``gazebo/meshes/*.stl``, ``gazebo/actors.json`` and
  ``gazebo/objects/<object>.sdf`` (each object, spawnable on its own);
- ``nav2/<id>.pgm``, ``nav2/<id>.yaml`` and ``nav2/nav2_params.yaml`` -- derived
  from ``gazebo_models/config/nav2_params.yaml`` (never edited): the AMCL initial
  pose is the level's start in the map frame, ``map_server.yaml_filename`` names
  the level's map, the global costmap's resolution is the map's. Every change is
  listed in ``nav2/params_derivation.json``.

``--derivation 2`` (G2.6, docs/v2/g2/data/g26/DIAGNOSIS.md) changes, in the GENERATED files only,
what the Depot diagnosis measured: AMCL updates every 0.05 m / 0.05 rad (not 0.25 m / 0.2 rad),
and the map also holds the objects whose body crosses the LiDAR's scan plane (the LiDAR sees them;
on the Depot, ``bad_crate``). Derivation 1 (the default) is M6F.2's, unchanged.

``--derivation 3`` (G2.8, docs/v2/g2/data/g28/round_gate/): derivation 2, and the controller
server's FollowPath wraps the same DWB in Nav2's RotationShimController. Measured on the per-round
gate: beside ``obj_maze_2``'s pre-grasp pose DWB commanded ~0 (v 0, w ~±0.03 rad/s) for ~40 s at a
time, its known preference for standing still when every forward arc scores badly; the shim turns
the robot toward the path first (more than ``SHIM['angular_dist_threshold']`` off), then hands over
to DWB, whose parameters are unchanged. Measured: not enough (seed 6, 1 of 2: DWB still stood
still at the maze's corner, already facing the path).

``--derivation 4`` (G2.8): derivation 2, and FollowPath is Nav2's Regulated Pure Pursuit in place of
DWB, at DWB's limits (``RPP``). At a sharp corner every DWB forward arc leaves the path line while
standing still costs nothing more, so DWB stood still (C2-NAV.21's degeneracy); RPP steers to a
lookahead point on the global path (which keeps >= 0.6 m from the walls there) and rotates in place
first when the path turns sharply.

``--derivation 5`` (G2.9, Gautham's decisions of 2026-10-27; docs/v2/g2/data/g29/): derivation 4 (Regulated
Pure Pursuit kept for driving recordings), and two GENERATED side files:

- ``gazebo/actors.json`` carries a ``scenario_rule``: the actors stop for COCO as Fetch Rush rules 5's
  do in the model (``coco_lab.games.DepotActors``: hold a step whose box would come within the robot's
  radius + ``ACTOR_STOP_MARGIN`` of COCO's centre and closer than now). It is a scenario rule, not
  physics; ``tools/g2/actor_scenario.py`` drives the actors by it (``tools/m6/m6f8_run.sh`` starts it
  when the file has the rule). The world SDF says so in a comment.
- ``gazebo/diff_drive_calibration.yaml``: the Stack's ``diff_drive_controller`` block (from
  ``gazebo_models/urdf/coco_controllers.yaml``, never edited) with ``wheel_separation_multiplier``
  scaled by the turn over-count measured on derivation 4's gate (``ODOM_TURN_SCALE``), loaded over the
  controller by the runner (``spawner -p``). One value corrects both: odometry divides the wheels'
  speed difference by separation × multiplier, the wheels are commanded with it.

``--gz-check`` runs ``gz sdf -k`` on every SDF written (light; allowed while
other work runs). ``--checksums`` writes the sha256 of every output to a JSON
file; ``--verify`` instead compares against it and fails on any difference.
The outputs are disposable and stay out of git; their checksums are committed.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys

import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab import worldgen  # noqa: E402, I100
from coco_lab import worldspec_v3 as v3  # noqa: E402
from coco_lab.worldspec import normalize, to_map_frame  # noqa: E402

TEMPLATE = os.path.join(REPO, 'gazebo_models', 'worlds', 'coco_navigation.world')
NAV2_PARAMS = os.path.join(REPO, 'gazebo_models', 'config', 'nav2_params.yaml')


#: G2.9 (derivation 5): wheel odometry's turn over the truth's, pooled over derivation 4's per-round
#: gate (40 runs, docs/v2/g2/data/g29/odom/turn_scale_d4_gate.json; tools/g2/odom_turn_scale.py)
ODOM_TURN_SCALE = 1.2029
CONTROLLERS = os.path.join(REPO, 'gazebo_models', 'urdf', 'coco_controllers.yaml')
#: G2.9 (derivation 5): Gazebo's actors stop for COCO -- a scenario rule, as Fetch Rush rules 5's
SCENARIO_RULE_ID = 'actors_yield_to_coco'
SCENARIO_STEP_S = 0.05


def scenario_rule(s):
    """G2.9: the rule ``tools/g2/actor_scenario.py`` applies to the actors (rules 5's, coco_lab.games)."""
    from coco_lab.games import ACTOR_STOP_MARGIN
    return {'id': SCENARIO_RULE_ID, 'kind': 'SCENARIO RULE (not physics)',
            'label': 'Scenario rule (G2.9): the actors stop for COCO, as Fetch Rush rules 5 in the model',
            'rule': ('each actor keeps its own clock; it holds a step when its box at the next pose would be '
                     'within robot_radius_m + stop_margin_m of COCO\'s centre (Gazebo truth) and closer than now'),
            'model_rule': 'coco_lab.games.DepotActors.world_step (actors.yield=1)',
            'robot_radius_m': s['robot']['radius'], 'stop_margin_m': ACTOR_STOP_MARGIN, 'step_s': SCENARIO_STEP_S,
            'driver': 'tools/g2/actor_scenario.py'}


def diff_drive_calibration():
    """G2.9: the Stack's diff_drive_controller parameters with the turn scale calibrated (YAML text)."""
    with open(CONTROLLERS, encoding='utf-8') as f:
        block = yaml.safe_load(f)['diff_drive_controller']
    p = block['ros__parameters']
    old = p['wheel_separation_multiplier']
    p['wheel_separation_multiplier'] = round(old * ODOM_TURN_SCALE, 3)
    header = ('# GENERATED by tools/m6/gen_level.py --derivation 5 (G2.9) from gazebo_models/urdf/coco_controllers.yaml\n'
              '# (never edited). Odometry calibration in the generated files only (Gautham, 2026-10-27):\n'
              f'# wheel_separation_multiplier {old} x {ODOM_TURN_SCALE} (wheel odometry turned {ODOM_TURN_SCALE} x the\n'
              '# truth over derivation 4\'s gate) -> ' f'{p["wheel_separation_multiplier"]}. Loaded over the running controller\n'
              '# by tools/m6/m6f8_run.sh (spawner -p). Everything else is the original block.\n')
    return header + yaml.safe_dump({'diff_drive_controller': block}, sort_keys=False), old, p['wheel_separation_multiplier']


#: G2.6: AMCL's update thresholds (measured: the largest single reduction of its drift)
AMCL_UPDATE = 0.05

#: G2.8 (derivation 3): Nav2's RotationShimController around the Stack's DWB (FollowPath). The
#: rotation rate and acceleration stay within DWB's own limits (max_vel_theta 1.0, acc_lim_theta
#: 3.2); goal headings stay DWB's (rotate_to_goal_heading False).
SHIM = {'plugin': 'nav2_rotation_shim_controller::RotationShimController',
        'primary_controller': 'dwb_core::DWBLocalPlanner',
        'angular_dist_threshold': 0.785, 'forward_sampling_distance': 0.5,
        'rotate_to_heading_angular_vel': 0.8, 'max_angular_accel': 3.2,
        'simulate_ahead_time': 1.0, 'rotate_to_goal_heading': False}

#: G2.8 (derivation 4): Regulated Pure Pursuit replaces DWB, within DWB's limits (max_vel_x 0.3,
#: max_vel_theta 1.0, acc_lim_theta 3.2); no reversing; collision checking on; cost-regulated slowing
#: off (the collision monitor already slows the robot beside obstacles).
RPP = {'plugin': 'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController',
       'desired_linear_vel': 0.3, 'lookahead_dist': 0.6, 'min_lookahead_dist': 0.3, 'max_lookahead_dist': 0.9,
       'lookahead_time': 1.5, 'use_velocity_scaled_lookahead_dist': False, 'transform_tolerance': 0.1,
       'min_approach_linear_velocity': 0.05, 'approach_velocity_scaling_dist': 0.6,
       'use_collision_detection': True, 'max_allowed_time_to_collision_up_to_carrot': 1.0,
       'use_regulated_linear_velocity_scaling': True, 'use_cost_regulated_linear_velocity_scaling': False,
       'regulated_linear_scaling_min_radius': 0.9, 'regulated_linear_scaling_min_speed': 0.25,
       'use_rotate_to_heading': True, 'rotate_to_heading_angular_vel': 0.8, 'rotate_to_heading_min_angle': 0.785,
       'max_angular_accel': 3.2, 'allow_reversing': False, 'use_fixed_curvature_lookahead': False}


def derive_nav2_params(spec, map_yaml_name, resolution, derivation=1):
    """Return (params text, derivation list) from the Stack's nav2_params.yaml."""
    with open(NAV2_PARAMS, encoding='utf-8') as f:
        params = yaml.safe_load(f)
    s = normalize(spec)
    sx, sy = to_map_frame(s, s['start']['x'], s['start']['y'])
    changes = []

    def put(path, value, why=None):
        node = params
        for k in path[:-1]:
            node = node[k]
        old = node.get(path[-1])
        node[path[-1]] = value
        changes.append(dict({'key': '.'.join(path), 'from': old, 'to': value}, **({'why': why} if why else {})))

    put(['amcl', 'ros__parameters', 'initial_pose'],
        {'x': sx, 'y': sy, 'z': 0.0, 'yaw': s['start']['theta']})
    put(['map_server', 'ros__parameters', 'yaml_filename'], map_yaml_name)
    put(['global_costmap', 'global_costmap', 'ros__parameters', 'resolution'], resolution)
    if derivation >= 2:
        g26 = 'G2.6 (docs/v2/g2/data/g26/DIAGNOSIS.md): '
        a = ['amcl', 'ros__parameters']
        put(a + ['update_min_d'], AMCL_UPDATE, g26 + 'updates every 0.25 m let a wrong likelihood peak capture the filter while turning; 0.05 measured best of the variants replayed')
        put(a + ['update_min_a'], AMCL_UPDATE, g26 + 'as update_min_d')
    if derivation in (4, 5):
        g28 = 'G2.8 (docs/v2/g2/data/g28/round_gate/): '
        cs = params['controller_server']['ros__parameters']
        old = cs['FollowPath']
        assert old['plugin'] == SHIM['primary_controller'], old['plugin']
        cs['FollowPath'] = dict(RPP)
        changes.append({'key': 'controller_server.ros__parameters.FollowPath', 'from': old, 'to': dict(RPP),
                        'why': g28 + 'DWB stood still at the maze corner (every forward arc leaves the path line; standing costs no more); RPP follows the path, which keeps >= 0.6 m from the walls there'})
    if derivation == 3:
        g28 = 'G2.8 (docs/v2/g2/data/g28/round_gate/): '
        fp = ['controller_server', 'ros__parameters', 'FollowPath']
        dwb = params['controller_server']['ros__parameters']['FollowPath']['plugin']
        assert dwb == SHIM['primary_controller'], dwb
        put(fp + ['plugin'], SHIM['plugin'], g28 + 'DWB stalled (v 0, w ~0) beside obj_maze_2 for ~40 s at a time; the shim turns to the path first, then DWB drives')
        for k, v in SHIM.items():
            if k != 'plugin':
                put(fp + [k], v, g28 + 'RotationShimController parameter')
    header = (f'# GENERATED by tools/m6/gen_level.py for World Spec {s["id"]!r} from\n'
              '# gazebo_models/config/nav2_params.yaml (unchanged); the changes are listed\n'
              '# in params_derivation.json. Comments of the original are not carried.\n')
    if derivation >= 2:
        header += f'# Derivation {derivation} (G2.6{", G2.8" if derivation >= 3 else ""}{", G2.9" if derivation >= 5 else ""}): see params_derivation.json for each change and why.\n'
    return header + yaml.safe_dump(params, sort_keys=False), changes


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data if isinstance(data, bytes) else data.encode('utf-8'))


def map_with_objects(s, resolution):
    """
    G2.6: the Nav2 map (worldgen.nav2_map's) plus every object whose body crosses the LiDAR's scan
    plane (the LiDAR sees it; the base map holds the level's static solids only). Returns
    ``(pgm_bytes, yaml_text, added)``.
    """
    import math
    from coco_lab.maps import OCCUPIED
    from coco_lab.worldspec import scan_height
    m = worldgen.nav_map(s, resolution)
    occ = bytearray(m.occupancy)
    sh = scan_height(s)
    dx, dy = s['world_to_map']
    added = []
    for o in v3.objects(s):
        top = o['height'] if o['shape'] == 'cylinder' else o['size'][2]
        if not (o['z'] < sh < o['z'] + top):
            continue
        L, W = (o['diameter'],) * 2 if o['shape'] == 'cylinder' else tuple(o['size'][:2])
        cx, cy, yaw = o['x'] + dx, o['y'] + dy, o.get('yaw', 0.0)
        c, sn = math.cos(yaw), math.sin(yaw)
        n = 0
        for row in range(m.height):
            y = m.origin[1] + (m.height - 1 - row + 0.5) * m.resolution
            for col in range(m.width):
                x = m.origin[0] + (col + 0.5) * m.resolution
                lx, ly = c * (x - cx) + sn * (y - cy), -sn * (x - cx) + c * (y - cy)
                if abs(lx) <= L / 2 and abs(ly) <= W / 2 and occ[row * m.width + col] != OCCUPIED:
                    occ[row * m.width + col] = OCCUPIED
                    n += 1
        added.append({'object': o['id'], 'cells': n})
    pgm = (f'P5\n{m.width} {m.height}\n255\n'.encode()
           + bytes(occ).translate(bytes(worldgen.PGM_VALUE.get(i, 0) for i in range(256))))
    _, myaml = worldgen.nav2_map(s, f'{s["id"]}.pgm', resolution)
    return pgm, myaml, added


def generate(spec_path, out, arena_res, nav_res, gz_check, derivation=1):
    with open(spec_path, encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    s = normalize(spec)
    root = os.path.join(out, s['id'])
    written = {}

    def emit(rel, data):
        write(os.path.join(root, rel), data)
        written[rel] = hashlib.sha256(data if isinstance(data, bytes)
                                      else data.encode('utf-8')).hexdigest()

    for res in arena_res or [s['arena']['resolution']]:
        emit(f'arena/arena_world_{res:g}.json', worldgen.arena_world_json(s, res) + '\n')
    with open(TEMPLATE, encoding='utf-8') as f:
        template = f.read()
    sdf, files = worldgen.sdf_world(s, template, world_name=s['id'])
    calibration = None
    if derivation >= 5 and 'actors.json' in files:
        rule = scenario_rule(s)
        doc = json.loads(files['actors.json'])
        doc['scenario_rule'] = rule
        files['actors.json'] = (json.dumps(doc, sort_keys=True, indent=1) + '\n').encode()
        sdf = sdf.replace(f'<world name="{s["id"]}">', f'<world name="{s["id"]}">\n    <!-- {rule["label"]}: {rule["rule"]}. '
                          f'Driven by {rule["driver"]} from actors.json; not physics. -->', 1)
    if derivation >= 5:
        text, old, new = diff_drive_calibration()
        emit('gazebo/diff_drive_calibration.yaml', text)
        calibration = {'file': 'gazebo/diff_drive_calibration.yaml', 'wheel_separation_multiplier': {'from': old, 'to': new},
                       'turn_scale': ODOM_TURN_SCALE, 'source': 'docs/v2/g2/data/g29/odom/turn_scale_d4_gate.json'}
    emit(f'gazebo/{s["id"]}.sdf', sdf)
    for rel, data in sorted(files.items()):
        emit(f'gazebo/{rel}', data)
    if v3.is_v3(s):
        for o in v3.objects(s):
            emit(f'gazebo/objects/{o["id"]}.sdf', worldgen.object_sdf(s, o['id']))
    nres = nav_res if nav_res is not None else s['arena']['resolution']
    added = None
    if derivation >= 2:
        pgm, myaml, added = map_with_objects(s, nres)
    else:
        pgm, myaml = worldgen.nav2_map(s, f'{s["id"]}.pgm', nres)
    emit(f'nav2/{s["id"]}.pgm', pgm)
    emit(f'nav2/{s["id"]}.yaml', myaml)
    params, changes = derive_nav2_params(s, f'{s["id"]}.yaml', nres, derivation)
    emit('nav2/nav2_params.yaml', params)
    record = {'source': 'gazebo_models/config/nav2_params.yaml', 'changes': changes}
    if derivation >= 2:
        record.update(derivation=derivation, map_objects_added=added)
    if calibration:
        record.update(odometry_calibration=calibration,
                      scenario_rule=SCENARIO_RULE_ID if 'actors.json' in files else None)
    emit('nav2/params_derivation.json', json.dumps(record, indent=1, sort_keys=True) + '\n')
    checks = {}
    if gz_check:
        for rel in sorted(written):
            if rel.endswith('.sdf'):
                r = subprocess.run(['gz', 'sdf', '-k', os.path.join(root, rel)],
                                   capture_output=True, text=True)
                checks[rel] = {'returncode': r.returncode,
                               'output': (r.stdout + r.stderr).strip()[-400:]}
    return s, root, written, checks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec')
    ap.add_argument('--out', default=os.path.join(REPO, 'tools', 'm6', 'out'))
    ap.add_argument('--arena-res', type=float, action='append')
    ap.add_argument('--nav-res', type=float)
    ap.add_argument('--gz-check', action='store_true')
    ap.add_argument('--checksums')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--derivation', type=int, default=1, choices=(1, 2, 3, 4, 5))
    a = ap.parse_args(argv)
    s, root, written, checks = generate(a.spec, a.out, a.arena_res, a.nav_res, a.gz_check, a.derivation)
    bad = [rel for rel, c in checks.items() if c['returncode'] != 0]
    for rel, c in sorted(checks.items()):
        print(f'gz sdf -k {rel}: rc {c["returncode"]} {c["output"]}')
    record = {'schema': 'coco_lab.m6f.level_outputs', 'version': 1, 'world_spec': s['id'],
              **({'derivation': a.derivation} if a.derivation != 1 else {}),
              'spec_file': os.path.relpath(os.path.abspath(a.spec), REPO),
              'spec_sha256': hashlib.sha256(open(a.spec, 'rb').read()).hexdigest(),
              'canonical_sha256': hashlib.sha256(
                  json.dumps(s, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
              'outputs': dict(sorted(written.items()))}
    if a.checksums and a.verify:
        with open(a.checksums, encoding='utf-8') as f:
            want = json.load(f)
        diff = sorted(k for k in set(want['outputs']) | set(written)
                      if want['outputs'].get(k) != written.get(k))
        print('verify:', 'identical' if not diff else f'{len(diff)} differ: {diff}')
        return 1 if diff or bad else 0
    if a.checksums:
        if checks:
            record['gz_sdf_check'] = {k: v['returncode'] for k, v in sorted(checks.items())}
        write(a.checksums, json.dumps(record, indent=1, sort_keys=True) + '\n')
    print(f'{len(written)} outputs in {root}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
