# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""Write a COCO Lab level and its goals as a ROS 2 package (R5.4), from the command line.

    python3 tools/r5/level_package.py worlds/coco_depot_v1.yaml --goals 26,6.5 30,11 --out DIR

The package itself is made by ``coco_lab.level_package.package`` (the same function the browser's
worker runs). This CLI lives outside the runtime package because it reads YAML with PyYAML, and
``coco_lab`` imports only the standard library (coco_lab/test/test_stdlib_only.py).
"""
import argparse
from pathlib import Path
import sys

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))

from coco_lab.level_package import package  # noqa: E402
from coco_lab.worldspec import normalize  # noqa: E402


def main(argv=None) -> int:
    """Write the package; print where."""
    ap = argparse.ArgumentParser(prog='tools/r5/level_package.py')
    ap.add_argument('spec')
    ap.add_argument('--goals', nargs='+', required=True, help='x,y in the World Spec frame')
    ap.add_argument('--scenario', default='goals')
    ap.add_argument('--repo', default=str(REPO), help="COCO Lab's checkout (the world and Nav2 templates)")
    ap.add_argument('--out', required=True)
    ap.add_argument('--no-actors', action='store_true', help='leave the actors\' driver out (they stand still)')
    a = ap.parse_args(argv)
    repo = Path(a.repo)
    spec = yaml.safe_load(Path(a.spec).read_text(encoding='utf-8'))
    goals = [[float(v) for v in g.split(',')] for g in a.goals]
    files = package(normalize(spec), goals,
                    (repo / 'gazebo_models/worlds/coco_navigation.world').read_text(encoding='utf-8'),
                    yaml.safe_load((repo / 'gazebo_models/config/nav2_params.yaml').read_text(encoding='utf-8')),
                    yaml.safe_load((repo / 'gazebo_models/urdf/coco_controllers.yaml').read_text(encoding='utf-8')),
                    scenario=a.scenario, dump=yaml.safe_dump,
                    actor_driver=None if a.no_actors else (repo / 'tools/g2/actor_scenario.py').read_text(encoding='utf-8'))
    for rel, data in files.items():
        p = Path(a.out) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    print(f'wrote {len(files)} files: {Path(a.out) / next(iter(files)).split("/")[0]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
