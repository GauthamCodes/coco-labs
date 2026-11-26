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
R5.4: a World Spec's Gazebo + Nav2 files, computed in memory (moved from tools/m6/gen_level.py).

``level_files`` returns ``{relative path: bytes}`` -- the very files ``gen_level.py`` writes -- from
the World Spec and COCO's own templates, which the caller supplies already parsed:

- ``world_template``: ``gazebo_models/worlds/coco_navigation.world`` (text);
- ``nav2_params``: ``gazebo_models/config/nav2_params.yaml`` (a dict);
- ``controllers``: ``gazebo_models/urdf/coco_controllers.yaml`` (a dict);
- ``dump``: how a dict becomes text. ``gen_level.py`` passes ``yaml.safe_dump`` (so its bytes are
  unchanged: the coco-ros2 image's build checks them against the committed checksums); the browser,
  which has no PyYAML, passes JSON (valid YAML, read by Nav2's parameter parser).

Nothing here reads a file or imports a third-party package (coco_lab runs in Pyodide).
"""
import hashlib
import json
import math

from coco_lab import worldgen
from coco_lab import worldspec_v3 as v3
from coco_lab.worldspec import normalize, to_map_frame

#: G2.9 (derivation 5): wheel odometry's turn over the truth's, pooled over derivation 4's per-round
#: gate (40 runs, docs/v2/g2/data/g29/odom/turn_scale_d4_gate.json; tools/g2/odom_turn_scale.py)
ODOM_TURN_SCALE = 1.2029
#: G2.9 (derivation 5): Gazebo's actors stop for COCO -- a scenario rule, as Fetch Rush rules 5's
SCENARIO_RULE_ID = 'actors_yield_to_coco'
SCENARIO_STEP_S = 0.05
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


def json_dump(data, sort_keys=False):
    """A ``dump`` for callers without PyYAML: JSON, which YAML parsers (and Nav2's) read."""
    return json.dumps(data, indent=1, sort_keys=sort_keys) + '\n'


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


def diff_drive_calibration(controllers, dump):
    """G2.9: the Stack's diff_drive_controller parameters with the turn scale calibrated (YAML text)."""
    block = json.loads(json.dumps(controllers['diff_drive_controller']))   # a copy
    p = block['ros__parameters']
    old = p['wheel_separation_multiplier']
    p['wheel_separation_multiplier'] = round(old * ODOM_TURN_SCALE, 3)
    header = ('# GENERATED by tools/m6/gen_level.py --derivation 5 (G2.9) from gazebo_models/urdf/coco_controllers.yaml\n'
              '# (never edited). Odometry calibration in the generated files only (Gautham, 2026-10-27):\n'
              f'# wheel_separation_multiplier {old} x {ODOM_TURN_SCALE} (wheel odometry turned {ODOM_TURN_SCALE} x the\n'
              '# truth over derivation 4\'s gate) -> ' f'{p["wheel_separation_multiplier"]}. Loaded over the running controller\n'
              '# by tools/m6/m6f8_run.sh (spawner -p). Everything else is the original block.\n')
    return header + dump({'diff_drive_controller': block}, sort_keys=False), old, p['wheel_separation_multiplier']


def derive_nav2_params(spec, nav2_params, dump, map_yaml_name, resolution, derivation=1):
    """Return (params text, derivation list) from the Stack's nav2_params.yaml (a dict, not changed)."""
    params = json.loads(json.dumps(nav2_params))                            # a copy
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
    return header + dump(params, sort_keys=False), changes


def map_with_objects(s, resolution):
    """
    G2.6: the Nav2 map (worldgen.nav2_map's) plus every object whose body crosses the LiDAR's scan
    plane (the LiDAR sees it; the base map holds the level's static solids only). Returns
    ``(pgm_bytes, yaml_text, added)``.
    """
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


def level_files(spec, world_template, nav2_params, controllers, dump=json_dump,
                arena_res=None, nav_res=None, derivation=1):
    """
    Return ``(normalized spec, {relative path: bytes})``: what ``tools/m6/gen_level.py`` writes under
    ``<out>/<id>/`` (arena/, gazebo/, nav2/), for ``spec`` (a World Spec dict).
    """
    s = normalize(spec)
    files_out = {}

    def emit(rel, data):
        files_out[rel] = data if isinstance(data, bytes) else data.encode('utf-8')

    for res in arena_res or [s['arena']['resolution']]:
        emit(f'arena/arena_world_{res:g}.json', worldgen.arena_world_json(s, res) + '\n')
    sdf, files = worldgen.sdf_world(s, world_template, world_name=s['id'])
    calibration = None
    if derivation >= 5 and 'actors.json' in files:
        rule = scenario_rule(s)
        doc = json.loads(files['actors.json'])
        doc['scenario_rule'] = rule
        files['actors.json'] = (json.dumps(doc, sort_keys=True, indent=1) + '\n').encode()
        sdf = sdf.replace(f'<world name="{s["id"]}">', f'<world name="{s["id"]}">\n    <!-- {rule["label"]}: {rule["rule"]}. '
                          f'Driven by {rule["driver"]} from actors.json; not physics. -->', 1)
    if derivation >= 5:
        text, old, new = diff_drive_calibration(controllers, dump)
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
    params, changes = derive_nav2_params(s, nav2_params, dump, f'{s["id"]}.yaml', nres, derivation)
    emit('nav2/nav2_params.yaml', params)
    record = {'source': 'gazebo_models/config/nav2_params.yaml', 'changes': changes}
    if derivation >= 2:
        record.update(derivation=derivation, map_objects_added=added)
    if calibration:
        record.update(odometry_calibration=calibration,
                      scenario_rule=SCENARIO_RULE_ID if 'actors.json' in files else None)
    emit('nav2/params_derivation.json', json.dumps(record, indent=1, sort_keys=True) + '\n')
    return s, files_out


def sha256s(files):
    """``{relative path: sha256 hex}`` of ``level_files``' output (gen_level's ``written``)."""
    return {rel: hashlib.sha256(data).hexdigest() for rel, data in files.items()}
