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
Write the M2 families' cross-language vectors (M2.1), from the reference.

    python3 coco_schemas/scripts/make_vectors_m2.py [--check]

``test/vectors/m2_batches.json``: for every whole-loop ``*Batch`` message
declared in ``coco_lab.columns``, a batch filled with fixed pseudo-random
rows (finite values; float columns exact in float32), and Python
protobuf's encoding of it, base64. TypeScript's ``encodeBatch`` must
reproduce every encoding byte for byte (``lab_web/test/schemas_m2.test.ts``).
``--check`` fails if the committed file differs from a fresh run.
"""

import base64
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from coco_lab.columns import Batch, CLOCKS, FLAT, TABLES  # noqa: E402
from coco_schemas.channels import message_class  # noqa: E402

OUT = os.path.join(PKG, 'test', 'vectors', 'm2_batches.json')


def _value(t, rng):
    if t == 'd':
        return round(rng.uniform(-100, 100), 6)
    if t == 'f':
        return float(rng.randint(-400, 400)) / 8.0
    if t in 'QI':
        return rng.randint(0, 70000)
    if t == 'i':
        return rng.randint(-70000, 70000)
    if t == 'B':
        return rng.random() < 0.5
    return rng.choice(['', 'ok', 'collision', 'no_valid_candidate',
                       'ASSUMPTION', 'bay α'])


def vectors():
    out = []
    for message in sorted(TABLES):
        rng = random.Random('m2:' + message)
        cols, scalars = TABLES[message]
        b = Batch(message, **{n: _value(t, rng) for n, t in scalars})
        for k in range(9):
            b.add(100 + k // 2, round(10.0 + k * 0.1, 6),
                  **{n: _value(t, rng) for n, t in cols if n not in FLAT})
        for n, t in cols:
            if n in FLAT:
                b.extend_flat(n, [_value(t, rng) for _ in range(13)])
        columns, sc = b.drain()
        plain = {n: [bool(x) for x in columns[n]] if t == 'B'
                 else list(columns[n]) for n, t in CLOCKS + cols}
        data = message_class(message)(**plain, **sc).SerializeToString()
        out.append({
            'message': message,
            'types': dict(CLOCKS + cols),
            'scalar_types': dict(scalars),
            'columns': {n: [str(v) if t == 'Q' else v for v in plain[n]]
                        for n, t in CLOCKS + cols},
            'scalars': {n: (str(sc[n]) if t == 'Q' else sc[n])
                        for n, t in scalars},
            'protobuf_b64': base64.b64encode(data).decode('ascii'),
        })
    return {'method': 'coco_lab.columns.Batch -> Python protobuf '
                      'SerializeToString (docs/v2/SCHEMAS.md)',
            'note': 'uint64 values are decimal strings (they may exceed '
                    '2**53)',
            'vectors': out}


def main():
    text = json.dumps(vectors(), indent=1, ensure_ascii=False) + '\n'
    if '--check' in sys.argv:
        with open(OUT, encoding='utf-8') as f:
            if f.read() != text:
                sys.exit(f'{OUT} is stale: re-run make_vectors_m2.py')
        print('m2 vectors are current')
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
