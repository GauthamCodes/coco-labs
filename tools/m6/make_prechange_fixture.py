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
M6F.1: freeze what the v1 and v2 worlds produce BEFORE World Spec v3 exists.

Run once, on the commit before any v3 code (0d1f37f), with the untouched
loader. It writes ``coco_lab/test/fixtures/m6f/prechange_v1v2.json``:

- the sha256 of each spec's canonical bytes (what ``run_id`` hashes);
- the sha256 of each Arena map (``arena_map``; for v2 also the LiDAR's
  ``terrain_map(scan_only=True)``);
- every tick's state hash of seeded sessions on each spec (hash versions 1
  and 2), with mixed inputs: goals, teleop, planner switches, stops, and on
  v2 the gated grasp.

``coco_lab/test/test_worldspec_v3.py`` replays the same sessions through the
v3 loader and asserts every byte is unchanged. The fixture is evidence: it is
never regenerated after v3 code exists (the script refuses if it is).

Usage: make_prechange_fixture.py <repo> <out.json>
"""

import hashlib
import json
import os
import random
import subprocess
import sys


def main(repo, out):
    sys.path.insert(0, os.path.join(repo, 'coco_lab'))
    if os.path.exists(os.path.join(repo, 'coco_lab', 'coco_lab', 'worldspec_v3.py')):
        sys.exit('refusing: worldspec_v3.py exists; this fixture is the pre-change state')
    import yaml
    from coco_lab.arena import Arena, InputEvent, is_free
    from coco_lab.worldspec import arena_map, canonical_bytes, terrain_map

    sha = subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True,
                         text=True, check=True).stdout.strip()
    result = {'schema': 'coco_lab.m6f.prechange', 'version': 1, 'made_at_commit': sha,
              'specs': {}}
    for name in ('coco_arena_v1', 'coco_arena_v2'):
        with open(os.path.join(repo, 'worlds', name + '.yaml'), encoding='utf-8') as f:
            spec = yaml.safe_load(f)
        entry = {'canonical_sha256': hashlib.sha256(canonical_bytes(spec)).hexdigest()}
        m = arena_map(spec)
        entry['arena_map_sha256'] = hashlib.sha256(m.occupancy).hexdigest()
        entry['arena_map_content_hash'] = m.content_hash()
        entry['arena_map_shape'] = [m.width, m.height, m.resolution, list(m.origin)]
        if name.endswith('v2'):
            entry['scan_map_sha256'] = hashlib.sha256(
                terrain_map(spec, scan_only=True).occupancy).hexdigest()
        sessions = []
        for k in range(6):
            rng = random.Random(20261017 + k)
            seed = rng.randrange(1 << 31)
            hash_version = 1 + k % 2
            probe = Arena(spec, seed)
            inputs = []
            for tick in sorted(rng.sample(range(1, 140), 9)):
                r = rng.random()
                if r < 0.35:
                    for _ in range(50):
                        x, y = rng.uniform(-6, 18), rng.uniform(-8, 8)
                        if is_free(probe, x, y):
                            inputs.append({'tick': tick, 'kind': 'goal', 'x': x, 'y': y})
                            break
                elif r < 0.7:
                    inputs.append({'tick': tick, 'kind': 'teleop',
                                   'linear': rng.uniform(-0.3, 0.5),
                                   'angular': rng.uniform(-1.0, 1.0)})
                elif r < 0.8:
                    inputs.append({'tick': tick, 'kind': 'planner',
                                   'choice': rng.choice(['astar', 'dijkstra', 'greedy'])})
                elif r < 0.9:
                    inputs.append({'tick': tick, 'kind': 'stop'})
                else:
                    inputs.append({'tick': tick, 'kind': 'grasp'})
            arena = Arena(spec, seed, hash_version=hash_version)
            by = {}
            for e in inputs:
                by.setdefault(e['tick'], []).append(InputEvent(**e))
            hashes = [arena.step(by.get(arena.tick, ())).state_hash for _ in range(150)]
            sessions.append({'seed': seed, 'hash_version': hash_version, 'ticks': 150,
                             'inputs': inputs, 'hashes': hashes})
        entry['sessions'] = sessions
        result['specs'][name] = entry
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.write('\n')
    print(out, sha)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
