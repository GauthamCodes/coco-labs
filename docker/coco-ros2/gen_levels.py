#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R5.1: the coco-ros2 image's levels, generated when the image is built (never committed; their
checksums are) and checked against the committed checksums of the files COCO's recorded STACK
runs used.

    gen_levels.py REPO OUT [--only ALIAS ...] [--allow-unverified]

For every level of ``docker/coco-ros2/levels.json``:

- ``world_spec``: ``tools/m6/gen_level.py``'s ``generate()`` with the level's derivation and
  resolutions, into ``OUT/gen/<id>/`` (arena/, gazebo/, nav2/); the world is laid out as the
  laptop's runs laid it out (``tools/r3/prepare_gazebo.py``): ``OUT/world/<id>/gazebo_models/
  worlds/<id>.sdf`` with ``meshes/`` beside it, because the SDF names its meshes relative to
  itself. Every output named by the level's committed record must be byte-identical, or the
  build fails (``--allow-unverified`` only for development; the index then says so).
- ``stock``: COCO's own world, map and parameters, used as gazebo_models installs them.

Writes ``OUT/index.json``: per alias the id, the start pose (Gazebo's world frame), the runtime
paths, every generated file's sha256 and the verification. Needs only the standard library,
PyYAML and the repository (coco_lab is standard-library only).
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

import yaml


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def compare(written, want):
    """Return (result, details): 'identical' when every wanted file has the wanted sha256."""
    differ = sorted(k for k in want if written.get(k) != want[k])
    missing = sorted(k for k in want if k not in written)
    if not differ:
        return 'identical', {'compared': len(want)}
    return 'DIFFERENT', {'compared': len(want), 'differ': differ, 'missing': missing}


def expected(repo, level):
    """The committed sha256s this level's outputs must have, and where they come from."""
    v = level['verify']
    if 'record' in v:
        with open(os.path.join(repo, v['record']), encoding='utf-8') as f:
            rec = json.load(f)
        spec_sha = sha256(os.path.join(repo, level['spec']))
        return v['record'], dict(rec['outputs']), {
            'spec_sha256_recorded': rec.get('spec_sha256'), 'spec_sha256_now': spec_sha,
            'spec_unchanged': rec.get('spec_sha256') == spec_sha}
    if 'session_meta' in v:
        with open(os.path.join(repo, v['session_meta']), encoding='utf-8') as f:
            meta = json.load(f)
        i = level['id']
        assert meta['level'] == i, (meta['level'], i)
        return v['session_meta'], {f'gazebo/{i}.sdf': meta['world_sha256'],
                                   f'nav2/{i}.yaml': meta['map_yaml_sha256'],
                                   f'nav2/{i}.pgm': meta['map_pgm_sha256']}, {}
    raise ValueError(f'{level["alias"]}: no verification source')


def world_spec_level(repo, out, level, gen_level):
    gen_root = os.path.join(out, 'gen')
    s, root, written, _ = gen_level.generate(os.path.join(repo, level['spec']), gen_root,
                                             level['arena_res'], level['nav_res'], False,
                                             level['derivation'])
    i = s['id']
    assert i == level['id'], (i, level['id'])
    wdir = os.path.join(out, 'world', i, 'gazebo_models', 'worlds')
    os.makedirs(wdir, exist_ok=True)
    shutil.copy(os.path.join(root, 'gazebo', f'{i}.sdf'), os.path.join(wdir, f'{i}.sdf'))
    meshes = os.path.join(root, 'gazebo', 'meshes')
    if os.path.isdir(meshes):
        shutil.copytree(meshes, os.path.join(wdir, 'meshes'), dirs_exist_ok=True)
    source, want, extra = expected(repo, level)
    result, details = compare(written, want)
    cal = os.path.join(root, 'gazebo', 'diff_drive_calibration.yaml')
    multiplier = None
    if os.path.exists(cal):
        with open(cal, encoding='utf-8') as f:
            multiplier = yaml.safe_load(f)['diff_drive_controller']['ros__parameters'][
                'wheel_separation_multiplier']
    start = s['start']
    return {
        'id': i, 'kind': 'world_spec', 'derivation': level['derivation'],
        'title': s.get('title'), 'provenance': level['provenance'],
        'frame': 'world', 'world_to_map': list(s['world_to_map']),
        'start': {'x': start['x'], 'y': start['y'], 'theta': start['theta']},
        'teleport': True,
        'world': os.path.join(wdir, f'{i}.sdf'),
        'map': os.path.join(root, 'nav2', f'{i}.yaml'),
        'params': os.path.join(root, 'nav2', 'nav2_params.yaml'),
        'calibration': cal if multiplier is not None else None,
        'wheel_separation_multiplier': multiplier,
        'actors': os.path.join(root, 'gazebo', 'actors.json')
        if os.path.exists(os.path.join(root, 'gazebo', 'actors.json')) else None,
        'sha256': dict(sorted(written.items())),
        'verification': dict({'against': source, 'result': result}, **details, **extra),
    }


def stock_level(repo, level):
    """COCO's own world as installed; the World Spec describing it gives the start and frames."""
    with open(os.path.join(repo, level['spec']), encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    start = spec['start']
    return {'id': level['id'], 'kind': 'stock', 'provenance': level['provenance'],
            'described_by': level['spec'], 'frame': 'world',
            'world_to_map': list(spec['world_to_map']),
            'start': {'x': start['x'], 'y': start['y'], 'theta': start['theta']},
            'teleport': False, 'world': None, 'map': None, 'params': None,
            'calibration': None, 'wheel_separation_multiplier': None, 'actors': None,
            'verification': {'result': 'stock (as installed by gazebo_models)'}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('repo')
    ap.add_argument('out')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--allow-unverified', action='store_true')
    a = ap.parse_args(argv)
    repo, out = os.path.abspath(a.repo), os.path.abspath(a.out)
    sys.path.insert(0, os.path.join(repo, 'tools', 'm6'))
    import gen_level  # noqa: E402  (inserts coco_lab itself)
    with open(os.path.join(repo, 'docker', 'coco-ros2', 'levels.json'), encoding='utf-8') as f:
        registry = json.load(f)
    index = {'schema': 'coco_ros2.levels', 'version': 1, 'levels': {}}
    bad = []
    for level in registry['levels']:
        if a.only and level['alias'] not in a.only:
            continue
        if level['kind'] == 'stock':
            entry = stock_level(repo, level)
        else:
            entry = world_spec_level(repo, out, level, gen_level)
            if entry['verification']['result'] != 'identical':
                bad.append(level['alias'])
        index['levels'][level['alias']] = entry
        print(f'{level["alias"]:>14}: {entry["id"]} -- {entry["verification"]["result"]}'
              + (f' against {entry["verification"]["against"]}'
                 if 'against' in entry['verification'] else ''))
    index['all_verified'] = not bad
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=1, sort_keys=True)
        f.write('\n')
    if bad:
        for alias in bad:
            print(f'NOT IDENTICAL: {alias}: {json.dumps(index["levels"][alias]["verification"])}',
                  file=sys.stderr)
        return 0 if a.allow_unverified else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
