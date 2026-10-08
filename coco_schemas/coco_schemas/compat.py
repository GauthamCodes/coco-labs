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
Within a major version, a schema change must be compatible.

Compared against a committed baseline descriptor set
(``coco_schemas/compat/v1.binpb``), for every package whose name ends in
``.v<N>`` that the baseline has:

- every message and enum still exists, under the same full name;
- every field still exists with the same number, name, type, message or
  enum type, label and ``optional``-ness -- or its number AND name are
  reserved (a removal done properly);
- no field number is reused, and every enum value keeps its number and name.

Adding packages, messages, enums, fields and enum values is allowed: an old
reader skips what it does not know. Anything else needs a new major
(``coco.<family>.v<N+1>``) and a converter (README section 3, invariant 5).

    python3 -m coco_schemas.compat CURRENT.binpb [--baseline B.binpb]
"""

import argparse
import os
import re
import sys
from typing import Dict, List

from google.protobuf import descriptor_pb2

HERE = os.path.dirname(os.path.realpath(__file__))
BASELINE = os.path.join(os.path.dirname(HERE), 'compat', 'v1.binpb')
VERSIONED = re.compile(r'\.v\d+$')


def load(path: str) -> descriptor_pb2.FileDescriptorSet:
    """Read a binary FileDescriptorSet."""
    s = descriptor_pb2.FileDescriptorSet()
    with open(path, 'rb') as f:
        s.ParseFromString(f.read())
    return s


def _index(fds: descriptor_pb2.FileDescriptorSet):
    """Return ``{full_name: (kind, proto)}`` for messages and enums."""
    out: Dict[str, tuple] = {}

    def walk_msg(prefix, m):
        name = f'{prefix}.{m.name}'
        out[name] = ('message', m)
        for e in m.enum_type:
            out[f'{name}.{e.name}'] = ('enum', e)
        for nested in m.nested_type:
            walk_msg(name, nested)

    for f in fds.file:
        if not VERSIONED.search(f.package):
            continue
        for m in f.message_type:
            walk_msg(f.package, m)
        for e in f.enum_type:
            out[f'{f.package}.{e.name}'] = ('enum', e)
    return out


def _field_sig(f) -> tuple:
    return (f.name, f.type, f.type_name, f.label, f.proto3_optional)


def _reserved(m, number: int, name: str) -> bool:
    nums = any(r.start <= number < r.end for r in m.reserved_range)
    return nums and name in m.reserved_name


def problems(baseline: descriptor_pb2.FileDescriptorSet,
             current: descriptor_pb2.FileDescriptorSet) -> List[str]:
    """Return every incompatibility; empty means compatible."""
    old, new = _index(baseline), _index(current)
    out = []
    for name, (kind, o) in sorted(old.items()):
        if name not in new:
            out.append(f'{kind} {name} was removed')
            continue
        nkind, n = new[name]
        if nkind != kind:
            out.append(f'{name} changed from {kind} to {nkind}')
            continue
        if kind == 'enum':
            nv = {v.number: v.name for v in n.value}
            for v in o.value:
                if nv.get(v.number) != v.name:
                    out.append(f'enum {name}: value {v.number} {v.name} '
                               f'is now {nv.get(v.number)!r}')
            continue
        nf = {f.number: f for f in n.field}
        for f in o.field:
            if f.number not in nf:
                if not _reserved(n, f.number, f.name):
                    out.append(f'{name}.{f.name} (field {f.number}) removed '
                               'without reserving its number and name')
                continue
            if _field_sig(nf[f.number]) != _field_sig(f):
                out.append(f'{name} field {f.number}: {_field_sig(f)} -> '
                           f'{_field_sig(nf[f.number])}')
        old_numbers = {f.number for f in o.field}
        for f in n.field:
            if f.number not in old_numbers and any(
                    r.start <= f.number < r.end for r in o.reserved_range):
                out.append(f'{name}.{f.name} reuses reserved number {f.number}')
    return out


def main(argv=None) -> int:
    """Check CURRENT against the baseline; print each problem."""
    ap = argparse.ArgumentParser(description='within-major compatibility')
    ap.add_argument('current')
    ap.add_argument('--baseline', default=BASELINE)
    a = ap.parse_args(argv)
    found = problems(load(a.baseline), load(a.current))
    for p in found:
        print(f'INCOMPATIBLE: {p}', file=sys.stderr)
    if not found:
        print('compatible with the baseline')
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
