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
The canonical-JSON corpus: Python's answer for inputs a browser must match.

A bundle's content hash is a sha256 over ``coco_lab.bundle.canonical_json``
-- Python's ``json.dumps(sort_keys=True, separators=(',', ':'),
allow_nan=False)`` with ``ensure_ascii`` -- of the parsed manifest. A
JavaScript ``JSON.parse`` + ``JSON.stringify`` does not reproduce those
bytes (``252.0`` vs ``252``, ``1e-05`` vs ``0.00001``, UTF-16 key order,
``\\u`` escaping). The TypeScript decoder therefore parses losslessly and
re-serialises the Python way; this corpus is what it is tested against.

``cases``
    Seeded random JSON *texts*, deliberately non-canonical (random
    whitespace, shuffled keys, every float lexeme form, escaped and raw
    non-ASCII, ``\\/``, ``-0``, big ints). For each: the text, Python's
    ``canonical_json(json.loads(text))`` and its sha256.
``floats``
    Doubles of every magnitude as IEEE-754 bit patterns (hex) with
    Python's ``repr`` -- the formatting ``json.dumps`` uses for a float.
"""

import hashlib
import json
import math
import random
import struct

from coco_lab.bundle import canonical_json

SEED = 20260930
N_CASES = 1200
N_FLOATS = 4000

_WS = ['', '', '', ' ', '\n', '\t', '  ', '\r\n']

_ALPHABET = (
    [chr(c) for c in range(0x20, 0x7f)]
    + ['\u0000', '\u0001', '\u001f', '\b', '\f', '\n', '\r', '\t', '\u007f',
       '"', '\\', '/', 'é', 'ÿ', 'Ā', ' ', ' ',
       '﻿', '�', '！', '', '中', '\U0001f600',
       '\U00010000', '\U0010ffff', '\U0001d11e'])


def _float(rng: random.Random) -> float:
    r = rng.random()
    if r < 0.30:
        # a uniformly random bit pattern, finite
        while True:
            x = struct.unpack('<d', rng.getrandbits(64).to_bytes(8, 'little'))[0]
            if math.isfinite(x):
                return x
    if r < 0.45:
        return float(rng.randint(-10 ** 6, 10 ** 6))
    if r < 0.60:
        return rng.choice([0.0, -0.0, 0.1, 0.5, 1.0, 1e16, 1e15, 1e-4, 1e-5,
                           9999999999999998.0, 1.7976931348623157e308,
                           5e-324, 2.2250738585072014e-308, 123456789.125,
                           0.30000000000000004, 1e22, 1e21, 1e-7, 100.0,
                           -1.5, float(2 ** 53), float(2 ** 53) + 2.0, 160.04162, 0.05])
    e = rng.randint(-330, 310)
    try:
        x = rng.uniform(-9.99, 9.99) * 10.0 ** e
    except OverflowError:
        return 1.0
    return x if math.isfinite(x) else 1.0


def _float_lexeme(rng: random.Random, x: float) -> str:
    r = repr(x)
    choice = rng.randrange(6)
    if choice == 0:
        return r
    if choice == 1:
        return '%.17g' % x
    if choice == 2:
        return '%.17e' % x
    if choice == 3:
        return r.upper()          # 1E-05, 1E+16
    if choice == 4 and 'e' not in r and '.' in r:
        return r + '000'          # trailing zeros
    return repr(x)


def _int(rng: random.Random) -> int:
    r = rng.random()
    if r < 0.5:
        return rng.randint(-1000, 1000)
    if r < 0.8:
        return rng.randint(-2 ** 63, 2 ** 63)
    return rng.randint(-10 ** 30, 10 ** 30)


def _string(rng: random.Random, n_max: int = 8) -> str:
    return ''.join(rng.choice(_ALPHABET) for _ in range(rng.randint(0, n_max)))


def _value(rng: random.Random, depth: int):
    r = rng.random()
    if depth < 5 and r < 0.18:
        return [_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    if depth < 5 and r < 0.36:
        return {_string(rng, 4): _value(rng, depth + 1)
                for _ in range(rng.randint(0, 5))}
    r = rng.random()
    if r < 0.40:
        return _float(rng)
    if r < 0.65:
        return _int(rng)
    if r < 0.85:
        return _string(rng)
    return rng.choice([None, True, False])


def _dump_string(rng: random.Random, s: str) -> str:
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif o < 0x20:
            short = {'\b': '\\b', '\f': '\\f', '\n': '\\n', '\r': '\\r',
                     '\t': '\\t'}.get(ch)
            out.append(short if short and rng.random() < 0.5
                       else '\\u%04x' % o)
        elif ch == '/' and rng.random() < 0.5:
            out.append('\\/')
        elif o > 0x7e and rng.random() < 0.5:
            if o > 0xffff:
                v = o - 0x10000
                hi, lo = 0xd800 + (v >> 10), 0xdc00 + (v & 0x3ff)
                fmt = '\\u%04X\\u%04X' if rng.random() < 0.5 else \
                    '\\u%04x\\u%04x'
                out.append(fmt % (hi, lo))
            else:
                out.append(('\\u%04X' if rng.random() < 0.5 else '\\u%04x')
                           % o)
        elif o < 0x7f and rng.random() < 0.05:
            out.append('\\u%04x' % o)
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def _dump(rng: random.Random, v) -> str:
    ws = lambda: rng.choice(_WS)  # noqa: E731
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, int):
        return '-0' if v == 0 and rng.random() < 0.2 else str(v)
    if isinstance(v, float):
        return _float_lexeme(rng, v)
    if isinstance(v, str):
        return _dump_string(rng, v)
    if isinstance(v, list):
        return '[' + ws() + (',' + ws()).join(
            ws() + _dump(rng, x) + ws() for x in v) + ']'
    items = list(v.items())
    rng.shuffle(items)
    return '{' + ws() + ','.join(
        ws() + _dump_string(rng, k) + ws() + ':' + ws() + _dump(rng, x) + ws()
        for k, x in items) + '}'


def corpus() -> dict:
    """Return the corpus document (deterministic for :data:`SEED`)."""
    rng = random.Random(SEED)
    cases = []
    # a few fixed ones first: the hazards named in the plan
    fixed = ['252.0', '1e-05', '0.00001', '1e16', '1E+16', '-0', '-0.0',
             '1e400', '{"b":1,"a":2}', '{"\\uff01":1,"\\ud83d\\ude00":2}',
             '"\\u007f"', '"\\ud800"', '[1.0,2.50,3e0,0.1e1,10E-1]',
             '12345678901234567890123', '5e-324', '1.7976931348623157e308',
             '{"a":{"b":[{},[],""]}}', '"caf\\u00e9 \\u2028"']
    texts = fixed + [_dump(rng, _value(rng, 0)) for _ in range(N_CASES)]
    for text in texts:
        value = json.loads(text)
        try:
            canonical = canonical_json(value)
        except ValueError as exc:
            # 1e400 parses to inf in Python; canonical_json refuses it
            cases.append({'input': text, 'canonical': None,
                          'error': str(exc)})
            continue
        cases.append({
            'input': text, 'canonical': canonical,
            'sha256': hashlib.sha256(canonical.encode('utf-8')).hexdigest()})
    floats = []
    for _ in range(N_FLOATS):
        x = _float(rng)
        floats.append([struct.pack('>d', x).hex(), repr(x)])
    return {'generator': 'lab_web/tools/json_corpus.py', 'seed': SEED,
            'cases': cases, 'floats': floats}
