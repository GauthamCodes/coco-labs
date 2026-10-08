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
The run identity: ``run_id`` = hash of canonical spec + seed + engines.

    spec_sha256 = sha256(spec_bytes)                       # hex
    identity    = {"engines": [[name, version], ...] sorted,
                   "seed": seed, "spec_sha256": spec_sha256}
    run_id      = sha256(b"coco.run_id.v1\\n" + canonical_json(identity))

``canonical_json`` is Python's ``json.dumps(sort_keys=True,
separators=(',', ':'), ensure_ascii=True)``: sorted keys (by code point), no
whitespace, every non-ASCII character escaped as ``\uXXXX`` -- the same
canonical form as ``coco_lab.bundle.canonical_json`` and lab_web's
``canonical.ts``. The seed is an integer (0 <= seed < 2**64). Two runs with
the same spec bytes, seed and engine versions have the same ``run_id`` in
Python and in TypeScript (``lab_web/src/schemas/runid.ts``); the test
vectors in ``test/vectors/run_id.json`` pin both.

Canonical SPEC bytes are the spec's own business (the World Spec's
canonical form is defined in M1.2); this module hashes whatever bytes it
is given.
"""

import hashlib
import json
from typing import Iterable, Tuple

DOMAIN = b'coco.run_id.v1\n'


def canonical_json(obj) -> bytes:
    """Serialize ``obj`` canonically: sorted keys, no spaces, ASCII."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def spec_sha256(spec: bytes) -> str:
    """Return the hex sha256 of the canonical spec bytes."""
    return hashlib.sha256(spec).hexdigest()


def run_id(spec: bytes, seed: int, engines: Iterable[Tuple[str, str]]) -> str:
    """Return the run identity for these inputs (hex sha256)."""
    if isinstance(seed, bool) or not (isinstance(seed, int)
                                      and 0 <= seed < 2 ** 64):
        raise ValueError(f'seed must be an int in [0, 2**64), got {seed!r}')
    pairs = sorted([str(n), str(v)] for n, v in engines)
    if len({n for n, _ in pairs}) != len(pairs):
        raise ValueError(f'engine named twice: {pairs}')
    identity = {'engines': pairs, 'seed': seed,
                'spec_sha256': spec_sha256(spec)}
    return hashlib.sha256(DOMAIN + canonical_json(identity)).hexdigest()
