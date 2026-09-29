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

r"""
The lab-only Nav2 parameter overlay, merged onto the mission's file.

The mission's ``gazebo_models/config/nav2_params.yaml`` is never edited.
The lab's ``config/nav2_lab_overlay.yaml`` is deep-merged onto a COPY:

- mappings merge key by key, recursively;
- anything else (lists included) in the overlay REPLACES the base value;
  lists are never concatenated, so ``planner_plugins`` is exactly the
  overlay's list;
- the base object is never mutated;
- the output is ``yaml.safe_dump(sort_keys=True)``, byte-stable for one
  input pair.

Usage::

    lab_params merge --base nav2_params.yaml \\
        --overlay nav2_lab_overlay.yaml --out merged.yaml

prints the SHA-256 of all three files and every dotted key that differs.
"""

import argparse
import copy
import hashlib
import sys
from typing import Dict, List


def deep_merge(base, overlay):
    """Return ``base`` with ``overlay`` merged in (see module doc)."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = {k: copy.deepcopy(v) for k, v in base.items()}
        for k, v in overlay.items():
            out[k] = deep_merge(base[k], v) if k in base else \
                copy.deepcopy(v)
        return out
    return copy.deepcopy(overlay)


def flatten(obj, prefix: str = '') -> Dict[str, object]:
    """Return ``{dotted.key: leaf}``; lists are leaves."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out.update(flatten(v, f'{prefix}{k}.' if isinstance(v, dict)
                               else f'{prefix}{k}'))
        return out
    return {prefix.rstrip('.'): obj}


def differing_keys(a, b) -> List[str]:
    """Return every dotted key whose value differs between ``a`` and ``b``."""
    fa, fb = flatten(a), flatten(b)
    return sorted(k for k in set(fa) | set(fb) if fa.get(k, object())
                  != fb.get(k, object()) or (k in fa) != (k in fb))


def dump(obj) -> str:
    """Return deterministic YAML text."""
    import yaml
    return yaml.safe_dump(obj, sort_keys=True, default_flow_style=False)


def load(path: str):
    """Load a YAML file."""
    import yaml
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def sha256_file(path: str) -> str:
    """Return the hex SHA-256 of a file's bytes."""
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def merge_files(base_path: str, overlay_path: str, out_path: str
                ) -> Dict[str, object]:
    """Merge two YAML files into ``out_path``; return hashes and the diff."""
    base, overlay = load(base_path), load(overlay_path)
    merged = deep_merge(base, overlay)
    text = dump(merged)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return {
        'base': base_path, 'base_sha256': sha256_file(base_path),
        'overlay': overlay_path, 'overlay_sha256': sha256_file(overlay_path),
        'merged': out_path, 'merged_sha256': sha256_file(out_path),
        'differing_keys': differing_keys(base, merged),
    }


def main(argv=None) -> int:
    """Command-line entry point (``lab_params merge``)."""
    ap = argparse.ArgumentParser(prog='lab_params', description=__doc__,
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('merge')
    m.add_argument('--base', required=True)
    m.add_argument('--overlay', required=True)
    m.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    info = merge_files(args.base, args.overlay, args.out)
    for k in ('base', 'overlay', 'merged'):
        print(f'{k} {info[k + "_sha256"]} {info[k]}')
    for k in info['differing_keys']:
        print(f'differs {k}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
