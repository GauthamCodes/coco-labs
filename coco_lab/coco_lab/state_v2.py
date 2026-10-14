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

"""Canonical behavioural snapshot for state hash v2 (ADR 0008)."""
from array import array
import hashlib
import json
import math

# These are presentation/transport, hash-chain bookkeeping, immutable world
# derivatives, or search-generator machinery. They do not survive as an input
# to a completed tick's next behaviour. Queued subsystem goals DO survive.
EXCLUDED = frozenset({
    'on_plan_batch', 'on_family', 'plan_batch_size', '_chain',
    '_collector', '_stream', '_snapshot', '_plan_snap', '_snap',
    '_pending', '_loop_applied', '_in_step', '_requested', '_want_plan', '_plan_ctx',
    'lab_map', 'smap', 'scan_smap', 'plan_map', 'grid', 'terrain',
    'angles', 'lidar', '_v2_world', 'hash_version',
})


def snapshot(arena):
    """
    Encode all remaining mutable fields, nested engines and aliasing.

    Unknown object types raise; new behaviour cannot silently disappear from
    v2. Aliases are named by traversal path, never process address. Floating
    state retains IEEE-754 values as hex, rather than losing tiny differences.
    """
    memo = {id(arena): '$'}
    immutable = {id(v): k for k, v in vars(arena).items()
                 if k in {'lab_map', 'smap', 'scan_smap', 'plan_map', 'grid',
                          'terrain', 'lidar', 'angles'}}

    def encode(v, path):
        if v is None or isinstance(v, (bool, int, str)):
            return v
        if isinstance(v, float):
            return {'float': v.hex() if math.isfinite(v) else str(v)}
        if isinstance(v, (bytes, bytearray)):
            return {'bytes': bytes(v).hex()}
        if id(v) in immutable:
            return {'world': immutable[id(v)]}
        if callable(v):
            return {'callable': v.__module__ + '.' + v.__qualname__}
        if id(v) in memo:
            return {'ref': memo[id(v)]}
        memo[id(v)] = path
        if isinstance(v, (list, tuple, array)):
            return [encode(x, f'{path}/{i}') for i, x in enumerate(v)]
        if isinstance(v, (set, frozenset)):
            return sorted([encode(x, f'{path}/set') for x in v],
                          key=lambda x: json.dumps(x, sort_keys=True))
        if isinstance(v, dict):
            keys = sorted(v, key=lambda x: repr(x))
            return [[encode(k, f'{path}/key/{i}'), encode(v[k], f'{path}/{i}')]
                    for i, k in enumerate(keys)]
        if hasattr(v, '__dict__'):
            return {'type': type(v).__module__ + '.' + type(v).__qualname__,
                    'fields': {k: encode(x, path + '/' + k)
                               for k, x in sorted(vars(v).items())}}
        raise TypeError(f'unhashed v2 state {path}: {type(v).__name__}')

    fields = {k: encode(v, '$/' + k) for k, v in sorted(vars(arena).items())
              if k not in EXCLUDED}
    return json.dumps({'world': arena._v2_world, 'state': fields},
                      sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def world_hash(spec, lidar):
    """Anchor immutable world and the actual scan sampling in the snapshot."""
    return hashlib.sha256(json.dumps({'spec': spec, 'lidar': vars(lidar)},
                                     sort_keys=True, separators=(',', ':')).encode()).hexdigest()
