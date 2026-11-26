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

from coco_lab import level_files as lf  # noqa: E402, I100

TEMPLATE = os.path.join(REPO, 'gazebo_models', 'worlds', 'coco_navigation.world')
NAV2_PARAMS = os.path.join(REPO, 'gazebo_models', 'config', 'nav2_params.yaml')
CONTROLLERS = os.path.join(REPO, 'gazebo_models', 'urdf', 'coco_controllers.yaml')

# R5.4: the generation itself lives in coco_lab.level_files (the browser runs it too, for a level's
# ROS 2 package); this tool reads COCO's templates, passes yaml.safe_dump, and writes the files. Its
# outputs are unchanged: the coco-ros2 image's build checks them against the committed checksums.
ODOM_TURN_SCALE = lf.ODOM_TURN_SCALE
SCENARIO_RULE_ID = lf.SCENARIO_RULE_ID
SCENARIO_STEP_S = lf.SCENARIO_STEP_S
AMCL_UPDATE = lf.AMCL_UPDATE
SHIM = lf.SHIM
RPP = lf.RPP


def _yaml(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def scenario_rule(s):
    """G2.9: the rule ``tools/g2/actor_scenario.py`` applies to the actors (coco_lab.level_files)."""
    return lf.scenario_rule(s)


def diff_drive_calibration():
    """G2.9: the Stack's diff_drive_controller parameters with the turn scale calibrated (YAML text)."""
    return lf.diff_drive_calibration(_yaml(CONTROLLERS), yaml.safe_dump)


def derive_nav2_params(spec, map_yaml_name, resolution, derivation=1):
    """Return (params text, derivation list) from the Stack's nav2_params.yaml (coco_lab.level_files)."""
    return lf.derive_nav2_params(spec, _yaml(NAV2_PARAMS), yaml.safe_dump, map_yaml_name, resolution, derivation)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data if isinstance(data, bytes) else data.encode('utf-8'))


def map_with_objects(s, resolution):
    """G2.6: the Nav2 map plus the objects crossing the LiDAR's scan plane (coco_lab.level_files)."""
    return lf.map_with_objects(s, resolution)


def generate(spec_path, out, arena_res, nav_res, gz_check, derivation=1):
    with open(spec_path, encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    with open(TEMPLATE, encoding='utf-8') as f:
        template = f.read()
    s, files = lf.level_files(spec, template, _yaml(NAV2_PARAMS), _yaml(CONTROLLERS), yaml.safe_dump,
                              arena_res=arena_res, nav_res=nav_res, derivation=derivation)
    root = os.path.join(out, s['id'])
    for rel, data in files.items():
        write(os.path.join(root, rel), data)
    written = lf.sha256s(files)
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
