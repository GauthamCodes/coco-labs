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
Two builds of the v1 archive, compared (M2.10, ADR 0003).

    python3 docs/v2/data/m2/m210/compare_v1_builds.py DIST_A DIST_B --out F.json

Lists every file that differs; for each JSON file, checks that the two
differ ONLY in ``provenance.created_utc`` (the wall-clock stamp the tag's
tools write and exclude from every content hash).
"""

import argparse
import hashlib
import json
import os


def tree(d):
    out = {}
    for root, _, names in os.walk(d):
        for n in names:
            p = os.path.join(root, n)
            with open(p, 'rb') as f:
                out[os.path.relpath(p, d)] = hashlib.sha256(f.read()).hexdigest()
    return out


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k != 'created_utc'}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    ta, tb = tree(a.a), tree(a.b)
    differ = sorted(k for k in ta if k in tb and ta[k] != tb[k])
    rows = []
    for k in differ:
        row = {'file': k}
        if k.endswith('.json'):
            ja, jb = (json.load(open(os.path.join(d, k))) for d in (a.a, a.b))
            row['equal_without_created_utc'] = strip(ja) == strip(jb)
            row['content_hash_equal'] = ja.get('content_hash') == jb.get('content_hash')
        rows.append(row)
    result = {
        'tool': 'docs/v2/data/m2/m210/compare_v1_builds.py', 'evidence': 'MODEL (build tooling)',
        'tag': 'coco-lab-v1-final', 'commit': '35711693d11da99218fa85050db60c6e10462bd2',
        'files': {'a': len(ta), 'b': len(tb)}, 'only_in_a': sorted(set(ta) - set(tb)), 'only_in_b': sorted(set(tb) - set(ta)),
        'bytes_a': sum(os.path.getsize(os.path.join(a.a, k)) for k in ta),
        'differ': rows,
        'all_differences_are_created_utc_only': all(r.get('equal_without_created_utc') for r in rows),
        'build_seconds_local': 108,
    }
    with open(a.out, 'w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('files', 'all_differences_are_created_utc_only')}), len(rows), 'differ')


if __name__ == '__main__':
    main()
