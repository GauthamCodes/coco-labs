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

"""R2.1: the allowed-modules guard (coco_lab.user_code; ADR 0012)."""

from pathlib import Path

from coco_lab import api, numerics
from coco_lab.rng import Rng
from coco_lab.user_code import (ALLOWED_MODULES, check, Console, describe_error, exact_pow,
                                GuardError, load, MAX_OUTPUT_CHARS)
import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / 'coco_lab' / 'templates'
OK = 'def plan(costmap, start, goal, ctx):\n    return None\n'


def refused(src):
    with pytest.raises(GuardError) as e:
        load(src)
    return str(e.value)


@pytest.mark.parametrize('line', [
    'import js', 'import pyodide', 'import pyodide.ffi', 'from pyodide.ffi import to_js',
    'import os', 'import sys', 'import time', 'import subprocess', 'import importlib',
    'import builtins', 'import ctypes', 'import socket', 'import gc', 'import inspect',
    'import coco_lab', 'import coco_lab.experiments', 'from coco_lab import exp_user',
    'from . import x', 'from math import *', 'import operator', 'import numpy'])
def test_refuses_imports(line):
    assert 'line 1' in refused(line + '\n' + OK)


@pytest.mark.parametrize('expr', [
    '().__class__', 'f.__globals__', '(1).__class__.__base__.__subclasses__()',
    'x._private', 'g.gi_frame', 'g.gi_frame.f_globals', 'e.with_traceback', 'tb.tb_frame',
    '__builtins__', '__import__("os")', 'type.mro(int)', '"{0}".format_map({})'])
def test_refuses_escape_syntax(expr):
    refused(f'def plan(costmap, start, goal, ctx):\n    return {expr}\n')


def test_refuses_async_and_dunder_global():
    refused('async def plan(costmap, start, goal, ctx):\n    return None\n')
    refused('def plan(costmap, start, goal, ctx):\n    global __x__\n    return None\n')


@pytest.mark.parametrize('name', ['open', 'exec', 'eval', 'compile', 'input', 'globals',
                                  'locals', 'vars', 'id', 'memoryview', 'breakpoint', 'help',
                                  'exit', 'quit', 'dir'])
def test_builtins_are_missing(name):
    m = load(f'def plan(costmap, start, goal, ctx):\n    return {name}\n')
    with pytest.raises(NameError):
        m.fn(None, None, None, None)


def test_getattr_refuses_underscores():
    m = load('def plan(costmap, start, goal, ctx):\n    return getattr(ctx, "_sink")\n')
    with pytest.raises(AttributeError):
        m.fn(None, None, None, ctx())
    m = load('def plan(costmap, start, goal, ctx):\n    return getattr(start, "gi_frame", 1)\n')
    with pytest.raises(AttributeError):
        m.fn(None, None, None, ctx())


def test_shims_hold_public_names_only():
    for name, make in ALLOWED_MODULES.items():
        mod = make()
        assert not [k for k in vars(mod) if k.startswith('_') and not k.startswith('__')], name
        assert 'sys' not in vars(mod) and 'os' not in vars(mod)


def test_math_shim_is_deterministic_numerics():
    m = load('import math\ndef plan(costmap, start, goal, ctx):\n'
             '    return [math.sin(0.5), math.atan2(1.0, 2.0), math.hypot(3.0, 4.0)]\n')
    out = m.fn(None, None, None, ctx())
    assert out == [numerics.sin(0.5), numerics.atan2(1.0, 2.0), numerics.hypot(3.0, 4.0)]
    refused_tanh = load('import math\ndef plan(c, s, g, ctx):\n    return math.sinh\n')
    with pytest.raises(AttributeError):
        refused_tanh.fn(None, None, None, ctx())


def test_pow_is_rewritten_and_exact():
    m = load('def plan(c, s, g, ctx):\n    x = 1.1\n    x **= 2\n'
             '    return [2 ** 10, 1.1 ** 2, x, 2.0 ** 0.5, pow(3, 2), 2 ** -1]\n')
    assert m.fn(None, None, None, ctx()) == [1024, 1.1 * 1.1, 1.1 * 1.1, 2.0 ** 0.5, 9, 0.5]
    assert exact_pow(2.0, 0.25) == numerics.exp(0.25 * numerics.log(2.0))
    with pytest.raises(ZeroDivisionError):
        exact_pow(0.0, -1.0)


def test_random_follows_ctx_rng():
    src = ('import random\ndef plan(c, s, g, ctx):\n'
           '    return [random.random(), ctx.rng.random()]\n')
    a = load(src).call(ctx(7), None, None, None)
    want = Rng(7)
    assert a == [want.random(), want.random()]
    with pytest.raises(RuntimeError):
        load(src).fn(None, None, None, ctx())   # outside a call: no generator


def test_print_is_bounded():
    m = load('def plan(c, s, g, ctx):\n    for i in range(100000):\n'
             '        print("x" * 100)\n    return None\n')
    m.fn(None, None, None, ctx())
    text = m.console.text()
    assert len(text) < MAX_OUTPUT_CHARS + 100 and 'more characters not kept' in text
    c = Console(10)
    c.write('abcdefghijkl')
    assert c.text().startswith('abcdefghij') and '2 more' in c.text()


def test_exactly_one_entry_point():
    assert 'exactly one' in refused('x = 1\n')
    assert 'exactly one' in refused(OK + 'def control(s, sc, p, ctx):\n    return None\n')
    assert load(OK).kind == 'planner'


def test_size_and_syntax():
    assert 'over' in refused('#' * (300 * 1024))
    msg = refused('def plan(:\n')
    assert 'SyntaxError' in msg


def test_errors_map_to_lines():
    m = load('def helper(x):\n    return 1 / x\n\n'
             'def plan(c, s, g, ctx):\n    return helper(0)\n')
    try:
        m.fn(None, None, None, ctx())
    except ZeroDivisionError as e:
        d = describe_error(e)
    assert d['type'] == 'ZeroDivisionError' and d['line'] == 2
    assert [f['line'] for f in d['frames']] == [5, 2]


def test_api_imports_work():
    m = load('from coco_lab.api import Pose2D\nimport coco_lab.api as api\n'
             'from coco_lab import api as api2\n'
             'def plan(c, s, g, ctx):\n    return [Pose2D(1, 2), api.Twist.of(1, 0), '
             'api2.API_VERSION]\n')
    p, t, v = m.fn(None, None, None, ctx())
    assert p == api.Pose2D(1, 2) and t.linear.x == 1.0 and v == 1


def test_modules_are_fresh_per_load():
    src = 'N = [0]\ndef plan(c, s, g, ctx):\n    N[0] += 1\n    return N[0]\n'
    a, b = load(src), load(src)
    assert a.fn(None, None, None, ctx()) == 1 and a.fn(None, None, None, ctx()) == 2
    assert b.fn(None, None, None, ctx()) == 1


@pytest.mark.parametrize('path', sorted(TEMPLATES.glob('*.py')), ids=lambda p: p.stem)
def test_templates_pass_the_guard(path):
    m = load(path.read_text())
    assert m.kind in ('planner', 'controller', 'localiser')
    check(path.read_text())


def ctx(seed=1):
    return api.Context(Rng(seed), api.Robot())
