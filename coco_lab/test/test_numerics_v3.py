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
G1.8: state hash v3 and the deterministic numerics behind it.

The goldens are new files (fixtures/v3/, written by tools/g1/make_v3_goldens.py);
v1 and v2 goldens are untouched and still pass (test_golden_traces,
test_state_hash_v2, the bundle tests). That CPython and Pyodide give the same
v3 bits is lab_web/tools/g1/native_gate.mjs, run in CI.
"""
import ast
import copy
import json
import math as libm
from pathlib import Path
import random
import struct

from coco_lab import games, loc_arena, numerics  # noqa: F401 -- loc_arena: the subsystem
from coco_lab.arena import Arena, ArenaError, InputEvent
import pytest

HERE = Path(__file__).parent
REPO = HERE.parents[1]
PKG = REPO / 'coco_lab' / 'coco_lab'
V3 = HERE / 'fixtures' / 'v3'


def world(name):
    return json.loads((REPO / 'worlds' / name).read_text())


def ulps(a, b):
    ia, ib = (struct.unpack('<q', struct.pack('<d', v))[0] for v in (a, b))
    return abs(ia - ib)


@pytest.fixture(autouse=True)
def libm_after():
    yield
    numerics.use(1)


def test_vectors_reproduce_bit_for_bit():
    data = json.loads((V3 / 'numerics_vectors.json').read_text())['vectors']
    assert set(data) == {'sin', 'cos', 'tan', 'atan', 'atan2', 'acos', 'exp', 'log', 'hypot'}
    for name, rows in data.items():
        f = getattr(numerics, name)
        for args, want in rows:
            try:
                got = f(*(float.fromhex(a) for a in args)).hex()
            except (ValueError, OverflowError) as e:
                got = type(e).__name__
            assert got == want, (name, args)


@pytest.mark.parametrize('name,n,lo,hi,worst', [
    ('sin', 1, -60, 60, 1), ('cos', 1, -60, 60, 1), ('tan', 1, -1.5, 1.5, 2),
    ('atan', 1, -20, 20, 1), ('atan2', 2, -20, 20, 1), ('acos', 1, -1, 1, 1),
    ('exp', 1, -40, 40, 1), ('hypot', 2, -50, 50, 1)])
def test_within_an_ulp_or_two_of_libm(name, n, lo, hi, worst):
    r = random.Random(name)
    f, g = getattr(numerics, name), getattr(libm, name)
    for _ in range(4000):
        args = [r.uniform(lo, hi) for _ in range(n)]
        assert ulps(f(*args), g(*args)) <= worst, (name, args)


def test_log_and_special_values():
    r = random.Random(3)
    for _ in range(4000):
        x = libm.exp(r.uniform(-40, 40))
        assert ulps(numerics.log(x), libm.log(x)) <= 1
    assert numerics.log(8.0, 2.0) == 3.0
    for f in (numerics.log, numerics.acos):
        with pytest.raises(ValueError):
            f(-2.0)
    with pytest.raises(ValueError):
        numerics.sin(libm.inf)
    with pytest.raises(OverflowError):
        numerics.exp(1000.0)
    assert numerics.exp(-1000.0) == 0.0
    assert libm.isnan(numerics.atan2(libm.nan, 1.0))
    for y, x in [(0.0, -1.0), (-0.0, -1.0), (0.0, 0.0), (-0.0, -0.0), (1.0, libm.inf),
                 (-1.0, -libm.inf), (libm.inf, libm.inf), (libm.inf, 1.0)]:
        a, b = numerics.atan2(y, x), libm.atan2(y, x)
        assert a == b and libm.copysign(1, a) == libm.copysign(1, b), (y, x)


def test_every_model_module_takes_math_from_numerics():
    """A module that imported the real math would compute v3 with libm, silently."""
    for p in sorted(PKG.glob('*.py')):
        if p.name == 'numerics.py':
            continue
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Import):
                assert 'math' not in [a.name for a in node.names], p.name
            if isinstance(node, ast.ImportFrom) and node.module == 'math':
                raise AssertionError(f'{p.name}: from math import ...')


def test_no_pow_operator_on_floats_in_the_model():
    """``x ** y`` is C pow; the model uses numerics.sq / cube / root (int literals aside)."""
    for p in sorted(PKG.glob('*.py')):
        if p.name == 'numerics.py':
            continue
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                ints = all(isinstance(v, ast.Constant) and type(v.value) is int
                           for v in (node.left, node.right))
                assert ints, f'{p.name}:{node.lineno}'


def test_the_switch_is_in_place_by_version_and_scoped():
    from coco_lab import arena, control
    assert arena.math is numerics.math is control.math
    seen = {}

    class Probe:
        hash_version = 3

        @numerics.in_run
        def look(self):
            seen['sin'] = numerics.math.sin
            seen['det'] = numerics.deterministic()

    Probe().look()
    assert seen == {'sin': numerics.sin, 'det': True}
    # G1.11: version 3 holds for the call only; the caller's numerics come back after it
    Arena(world('coco_arena_v1.json'), 1, hash_version=3)
    assert numerics.math.sin is libm.sin and not numerics.deterministic()
    with numerics.version(3):
        assert numerics.math.sin is numerics.sin and numerics.sq(3.0) == 9.0
        Arena(world('coco_arena_v1.json'), 1, hash_version=2)
        assert numerics.math.sin is numerics.sin        # an inner v2 call restored v3
        with numerics.version(1):
            assert numerics.math.sin is libm.sin and numerics.root(4.0) == 2.0
        assert numerics.deterministic()
    assert numerics.math.sin is libm.sin and not numerics.deterministic()
    with pytest.raises(ArenaError):
        Arena(world('coco_arena_v1.json'), 1, hash_version=4)


def _hashes(a, ticks, inputs):
    by = {}
    for e in inputs:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    return [a.step(by.get(a.tick, ())).state_hash for _ in range(ticks)]


def test_interleaved_versions_do_not_leak():
    """A v1 and a v3 run stepped alternately give what each gives alone."""
    spec = world('coco_arena_v1.json')
    inputs = [{'tick': 0, 'kind': 'goal', 'x': 2.5, 'y': 2.0}]
    alone = {hv: _hashes(Arena(spec, 1, hash_version=hv), 40, inputs) for hv in (1, 3)}
    runs = {hv: Arena(spec, 1, hash_version=hv) for hv in (1, 3)}
    got = {1: [], 3: []}
    ev = [InputEvent(**inputs[0])]
    for k in range(40):
        for hv in (1, 3):
            got[hv].append(runs[hv].step(ev if k == 0 else ()).state_hash)
    assert got == alone
    assert alone[1] != alone[3]


def test_v3_hashes_differ_from_v2_by_tag_and_both_stay_available():
    spec = world('coco_arena_v1.json')
    v2, v3 = Arena(spec, 1, hash_version=2), Arena(spec, 1, hash_version=3)
    assert v2.state_bytes().startswith(b'coco.arena.state.v2\0')
    assert v3.state_bytes().startswith(b'coco.arena.state.v3\0')
    assert v2.chain != v3.chain


GOLDEN = json.loads((V3 / 'state_hash_v3.json').read_text())


@pytest.mark.parametrize('name', sorted(GOLDEN['runs']))
def test_v3_goldens(name):
    import hashlib
    g = GOLDEN['runs'][name]
    a = Arena(world(g['world']), g['seed'], hash_version=3)
    by = {}
    for e in g['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    rules = games._rules(*g['game']) if 'game' in g else None
    chain = hashlib.sha256()
    first = None
    for _ in range(g['ticks']):
        t = a.step(by.get(a.tick, ()))
        if rules is not None:
            if not rules.started:
                rules.start(a)
            rules.observe(a, t)
        first = first or t.state_hash
        chain.update(t.state_hash.encode())
    assert first == g['first_hash']
    assert t.state_hash == g['last_hash']
    assert chain.hexdigest() == g['chain']
    assert [v.hex() for v in a.pose] == g['final_pose']
    if rules is not None:
        assert games._card(rules, a) == g['scorecard']


def test_games_play_takes_version_3():
    g = GOLDEN['runs']['depot_fetch_rush']
    rec = {'game': g['game'][0], 'arg': g['game'][1], 'seed': g['seed'], 'ticks': 50,
           'inputs': [e for e in g['inputs'] if e['tick'] < 50], 'hash_version': 3}
    out = games.play(world(g['world']), copy.deepcopy(rec))
    assert out == games.play(world(g['world']), rec)
    v2 = games.play(world(g['world']), dict(rec, hash_version=2))
    assert out['last_hash'] != v2['last_hash']
