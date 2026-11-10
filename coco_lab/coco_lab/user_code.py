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
Loading someone's algorithm file (R2; ADR 0012): the allowed-modules guard.

The same guard runs everywhere the file runs -- the browser's sandboxed worker,
``coco experiment run --algorithm``, the leaderboard verifier and the generated
ROS 2 package -- so a file that loads in one loads in all of them.

**What the guard is.** Before anything runs, the source is parsed and refused if it

- imports a module outside :data:`ALLOWED_MODULES` (``import js``, ``pyodide``, ``os``,
  ``sys``, ``time``, ...),
- reads or writes an attribute whose name starts with ``_`` (``x.__class__``,
  ``f.__globals__``, ``obj._private``) or one of :data:`DENIED_ATTRIBUTES` (frames,
  code objects, tracebacks: ``gi_frame``, ``f_globals``, ``tb_frame``, ...),
- names anything starting with ``__`` (``__builtins__``, ``__import__``), or
- uses ``async``/``await``, ``global`` of a dunder, or a star import.

It then runs with a reduced set of builtins (no ``open``, ``exec``, ``eval``,
``compile``, ``input``, ``globals``, ``vars``, ``id``, ``memoryview``, ``breakpoint``;
``getattr``/``setattr``/``hasattr``/``delattr`` refuse ``_`` names; ``print`` writes to
a bounded console) and every import goes through a hook that hands out *shims*:
modules holding only the public names listed here (``collections`` without its
``_sys``, ``functools`` without its internals). ``random`` is a shim over the run's
seeded generator; ``math`` holds only functions that give the same bits in every
runtime (:mod:`coco_lab.numerics`'s fdlibm ports and IEEE-exact ones); ``x ** y`` is
rewritten to an exact power for that reason.

**What the guard is not.** A Python-level guard is not a security boundary on its own:
CPython was never designed to contain hostile code. In the browser the boundary is the
worker (no network, DOM or storage, inherited CSP; ADR 0012); in CI it is the container
(``--network none``, no secrets, limits). The guard keeps honest code honest and makes
every escape need a second, independent failure.
"""

import ast
import hashlib
import types
from typing import Dict, List, Optional

from . import api, numerics
from .numerics import math

#: the most a file may be (the browser's share-link limit is about 64 KB compressed)
MAX_SOURCE_BYTES = 256 * 1024
#: console output kept per run; the rest is counted
MAX_OUTPUT_CHARS = 64 * 1024

KINDS = {'plan': 'planner', 'control': 'controller', 'localise': 'localiser'}

#: attributes no algorithm needs and every escape uses (frames, code, tracebacks)
DENIED_ATTRIBUTES = frozenset({
    'gi_frame', 'gi_code', 'gi_yieldfrom', 'gi_running', 'gi_suspended',
    'cr_frame', 'cr_code', 'cr_await', 'cr_origin', 'ag_frame', 'ag_code', 'ag_await',
    'f_back', 'f_builtins', 'f_code', 'f_globals', 'f_locals', 'f_trace', 'f_lasti',
    'f_lineno', 'tb_frame', 'tb_next', 'tb_lasti', 'tb_lineno', 'co_code', 'co_consts',
    'co_names', 'co_varnames', 'func_globals', 'func_code', 'mro', 'format_map',
    'with_traceback'})

#: builtins user code keeps (everything else is absent)
SAFE_BUILTINS = (
    'abs', 'all', 'any', 'bool', 'callable', 'chr', 'dict', 'divmod', 'enumerate', 'filter',
    'float', 'frozenset', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map',
    'max', 'min', 'next', 'ord', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
    'sorted', 'str', 'sum', 'tuple', 'zip', 'bin', 'hex', 'oct', 'hash', 'format', 'object',
    'bytes', 'bytearray',
    'property', 'staticmethod', 'classmethod', 'super', 'type', 'Exception', 'ArithmeticError',
    'AssertionError', 'AttributeError', 'IndexError', 'KeyError', 'LookupError',
    'NotImplementedError', 'OverflowError', 'RuntimeError', 'StopIteration', 'TypeError',
    'ValueError', 'ZeroDivisionError', 'NotImplemented', 'Ellipsis', 'True', 'False', 'None')

_EXACT_MATH = ('sqrt', 'floor', 'ceil', 'trunc', 'fabs', 'fmod', 'copysign', 'isfinite',
               'isnan', 'isinf', 'isclose', 'fsum', 'ldexp', 'frexp', 'modf', 'remainder',
               'nextafter', 'ulp', 'gcd', 'lcm', 'isqrt', 'comb', 'perm', 'factorial', 'prod',
               'pi', 'e', 'tau', 'inf', 'nan')


class GuardError(ValueError):
    """The file breaks a rule of the guard; ``problems`` lists each with its line."""

    def __init__(self, problems: List[Dict]):
        """``problems``: ``[{line, col, message}]``."""
        self.problems = problems
        super().__init__('; '.join(f'line {p["line"]}: {p["message"]}' for p in problems))


# -- the deterministic numbers --------------------------------------------------------------------

def exact_pow(x, y):
    """``x ** y`` with the same bits in every runtime (``**`` is rewritten to this)."""
    if isinstance(x, int) and isinstance(y, int) and not isinstance(x, bool) \
            and not isinstance(y, bool):
        if y >= 0 and (abs(x) <= 1 or y <= 4096):
            return pow(x, y)   # integers: exact (the float case below avoids C pow)
    x, y = float(x), float(y)
    if y == 0.0:
        return 1.0
    if y == 0.5 and x >= 0.0:
        return math.sqrt(x)
    if y.is_integer() and abs(y) <= 64:
        n, r, b = int(abs(y)), 1.0, x
        while n:
            if n & 1:
                r *= b
            b *= b
            n >>= 1
        return 1.0 / r if y < 0 else r
    if x > 0.0:
        return numerics.exp(y * numerics.log(x))
    if x == 0.0:
        if y > 0.0:
            return 0.0
        raise ZeroDivisionError('0.0 cannot be raised to a negative power')
    raise ValueError('a negative number to a fractional power is complex')


def _math_shim():
    m = types.ModuleType('math')
    for k in _EXACT_MATH:
        setattr(m, k, getattr(math, k))
    for k, f in numerics.DET.items():
        setattr(m, k, f)
    m.pow = exact_pow
    m.asin = lambda x: numerics.atan2(x, math.sqrt((1.0 - x) * (1.0 + x)))
    m.log2 = lambda x: numerics.log(x) / numerics.log(2.0)
    m.log10 = lambda x: numerics.log(x) / numerics.log(10.0)
    m.degrees = lambda x: x * (180.0 / math.pi)
    m.radians = lambda x: x * (math.pi / 180.0)
    m.tanh = lambda x: 1.0 - 2.0 / (numerics.exp(2.0 * x) + 1.0)
    return m


class _RandomShim(types.ModuleType):
    """``import random``: the run's ``ctx.rng`` (set per call), nothing else."""

    def __init__(self):
        super().__init__('random')
        self.current = None

    def _need(self):
        if self.current is None:
            raise RuntimeError('random: use ctx.rng (no call is running)')
        return self.current


def _random_shim():
    m = _RandomShim()
    for name in ('random', 'uniform', 'gauss', 'randint', 'randrange', 'choice', 'shuffle',
                 'sample'):
        def f(*a, _n=name, **k):
            return getattr(m._need(), _n)(*a, **k)
        f.__name__ = name
        setattr(m, name, f)
    return m


def _public(name: str, names):
    import importlib
    real = importlib.import_module(name)
    m = types.ModuleType(name)
    for k in names:
        setattr(m, k, getattr(real, k))
    return m


def _api_shim():
    m = types.ModuleType('coco_lab.api')
    for k in api.__all__:
        setattr(m, k, getattr(api, k))
    return m


#: module -> its shim's builder; nothing else can be imported
ALLOWED_MODULES = {
    'math': _math_shim,
    'random': _random_shim,
    'heapq': lambda: _public('heapq', ('heappush', 'heappop', 'heapify', 'heapreplace',
                                       'heappushpop', 'nlargest', 'nsmallest', 'merge')),
    'collections': lambda: _public('collections', ('deque', 'defaultdict', 'Counter',
                                                   'OrderedDict', 'namedtuple', 'ChainMap')),
    'itertools': lambda: _public('itertools', (
        'accumulate', 'chain', 'combinations', 'combinations_with_replacement', 'compress',
        'count', 'cycle', 'dropwhile', 'filterfalse', 'groupby', 'islice', 'pairwise',
        'permutations', 'product', 'repeat', 'starmap', 'takewhile', 'tee', 'zip_longest')),
    'functools': lambda: _public('functools', ('lru_cache', 'cache', 'partial', 'reduce',
                                               'cmp_to_key', 'total_ordering')),
    'bisect': lambda: _public('bisect', ('bisect', 'bisect_left', 'bisect_right', 'insort',
                                         'insort_left', 'insort_right')),
    'typing': lambda: _public('typing', ('Any', 'Callable', 'Dict', 'Iterable', 'List',
                                         'Optional', 'Sequence', 'Set', 'Tuple', 'Union')),
    'dataclasses': lambda: _public('dataclasses', ('dataclass', 'field', 'fields', 'asdict',
                                                   'astuple', 'replace')),
    'coco_lab.api': _api_shim,
}


# -- the static check -----------------------------------------------------------------------------

class _Check(ast.NodeVisitor):

    def __init__(self):
        self.problems: List[Dict] = []

    def bad(self, node, message):
        self.problems.append({'line': getattr(node, 'lineno', 0),
                              'col': getattr(node, 'col_offset', 0), 'message': message})

    def visit_Import(self, node):
        for a in node.names:
            if a.name not in ALLOWED_MODULES:
                self.bad(node, f'import {a.name}: only {", ".join(sorted(ALLOWED_MODULES))} '
                               'may be imported')
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        mod = node.module or ''
        if node.level or mod not in ALLOWED_MODULES:
            if not (mod == 'coco_lab' and all(a.name == 'api' for a in node.names)):
                self.bad(node, f'from {mod} import ...: only {", ".join(sorted(ALLOWED_MODULES))}'
                               ' may be imported')
        for a in node.names:
            if a.name == '*':
                self.bad(node, 'import * is not allowed; name what you use')
            elif a.name.startswith('_'):
                self.bad(node, f'cannot import the private name {a.name}')
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith('_'):
            self.bad(node, f'.{node.attr}: attribute names starting with _ are not allowed '
                           '(sandbox rule; name it without the underscore)')
        elif node.attr in DENIED_ATTRIBUTES:
            self.bad(node, f'.{node.attr} is not allowed (sandbox rule)')
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id.startswith('__') and node.id != '__name__':
            self.bad(node, f'{node.id}: names starting with __ are not allowed')
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.bad(node, 'async functions are not allowed')

    def visit_Await(self, node):
        self.bad(node, 'await is not allowed')

    def visit_AsyncFor(self, node):
        self.bad(node, 'async for is not allowed')

    def visit_AsyncWith(self, node):
        self.bad(node, 'async with is not allowed')

    def visit_Global(self, node):
        for n in node.names:
            if n.startswith('__'):
                self.bad(node, f'global {n} is not allowed')
        self.generic_visit(node)


class _Pow(ast.NodeTransformer):
    """``a ** b`` -> ``__coco_pow__(a, b)``; ``a **= b`` -> ``a = __coco_pow__(a, b)``."""

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Pow):
            return ast.copy_location(ast.Call(ast.Name('__coco_pow__', ast.Load()),
                                              [node.left, node.right], []), node)
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Pow) and isinstance(node.target, ast.Name):
            call = ast.Call(ast.Name('__coco_pow__', ast.Load()),
                            [ast.Name(node.target.id, ast.Load()), node.value], [])
            return ast.copy_location(ast.Assign([node.target], call), node)
        return node


def check(source: str, filename: str = 'algorithm.py') -> ast.Module:
    """Parse ``source`` and apply the static rules; return the (rewritten) tree."""
    if len(source.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise GuardError([{'line': 0, 'col': 0,
                           'message': f'the file is over {MAX_SOURCE_BYTES // 1024} KB'}])
    try:
        tree = ast.parse(source, filename)
    except SyntaxError as e:
        raise GuardError([{'line': e.lineno or 0, 'col': (e.offset or 1) - 1,
                           'message': f'SyntaxError: {e.msg}'}]) from None
    c = _Check()
    c.visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Pow) and \
                not isinstance(node.target, ast.Name):
            c.bad(node, 'x.y **= n: write x.y = x.y ** n')
    if c.problems:
        raise GuardError(sorted(c.problems, key=lambda p: (p['line'], p['col'])))
    tree = _Pow().visit(tree)
    ast.fix_missing_locations(tree)
    return tree


# -- running --------------------------------------------------------------------------------------

class Console:
    """``print`` for user code: a bounded buffer (what is cut is counted)."""

    def __init__(self, limit: int = MAX_OUTPUT_CHARS):
        """Keep at most ``limit`` characters."""
        self.limit, self.parts, self.size, self.cut = limit, [], 0, 0

    def write(self, text: str) -> None:
        """Append ``text`` (cut at the limit)."""
        room = self.limit - self.size
        if room <= 0:
            self.cut += len(text)
            return
        self.parts.append(text[:room])
        self.size += min(room, len(text))
        self.cut += max(0, len(text) - room)

    def text(self) -> str:
        """Return what was kept, with a note of what was cut."""
        out = ''.join(self.parts)
        if self.cut:
            out += f'\n[... {self.cut} more characters not kept]\n'
        return out


def _guarded(name, fn):
    def g(obj, attr, *rest):
        if not isinstance(attr, str) or attr.startswith('_') or attr in DENIED_ATTRIBUTES:
            raise AttributeError(f'{name}: {attr!r} is not allowed (sandbox rule)')
        return fn(obj, attr, *rest)
    g.__name__ = name
    return g


class UserModule:
    """A loaded algorithm file: its kind, functions, hash and console."""

    def __init__(self, source: str, filename: str = 'algorithm.py',
                 entry: Optional[str] = None):
        """
        Check and execute ``source`` in a fresh namespace of its own.

        ``entry`` (R4, the course's function exercises): require that function instead of
        exactly one of plan/control/localise; the file is still guarded the same way.
        """
        self.source = source
        self.filename = filename
        self.sha256 = code_sha256(source)
        tree = check(source, filename)
        self.console = Console()
        self.random = None
        shims: Dict[str, types.ModuleType] = {}

        def guarded_import(name, globals_=None, locals_=None, fromlist=(), level=0):
            if level:
                raise ImportError('relative imports are not allowed')
            if name == 'coco_lab' and fromlist and set(fromlist) <= {'api'}:
                name = 'coco_lab.api'
            if name not in ALLOWED_MODULES:
                raise ImportError(f'import {name}: not allowed (sandbox rule)')
            if name not in shims:
                shims[name] = ALLOWED_MODULES[name]()
                if name == 'random':
                    self.random = shims[name]
            m = shims[name]
            if name == 'coco_lab.api' and not fromlist:
                pkg = types.ModuleType('coco_lab')
                pkg.api = m
                return pkg
            if name == 'coco_lab.api' and fromlist == ('api',):
                pkg = types.ModuleType('coco_lab')
                pkg.api = m
                return pkg
            return m

        import builtins as real
        b = {k: getattr(real, k) for k in SAFE_BUILTINS}
        b['__import__'] = guarded_import
        b['__build_class__'] = real.__build_class__
        b['__name__'] = 'builtins'
        b['getattr'] = _guarded('getattr', getattr)
        b['setattr'] = _guarded('setattr', setattr)
        b['delattr'] = _guarded('delattr', delattr)
        b['hasattr'] = _guarded('hasattr', hasattr)
        b['pow'] = exact_pow
        console = self.console

        def user_print(*args, sep=' ', end='\n', file=None, flush=False):
            console.write(str(sep).join(str(a) for a in args) + str(end))
        b['print'] = user_print
        self.namespace = {'__builtins__': b, '__name__': 'user_algorithm',
                          '__coco_pow__': exact_pow}
        code = compile(tree, filename, 'exec')
        exec(code, self.namespace)
        if entry is not None:
            if not callable(self.namespace.get(entry)):
                raise GuardError([{'line': 0, 'col': 0,
                                   'message': f'define a function {entry}()'}])
            self.function_name, self.kind = entry, 'function'
            self.fn = self.namespace[entry]
            return
        found = [k for k in KINDS if callable(self.namespace.get(k))]
        if len(found) != 1:
            raise GuardError([{'line': 0, 'col': 0, 'message':
                               'define exactly one of plan(), control() or localise() '
                               f'(found {found or "none"})'}])
        self.function_name = found[0]
        self.kind = KINDS[found[0]]
        self.fn = self.namespace[found[0]]

    def call(self, ctx: api.Context, *args):
        """Call the algorithm with ``args`` and ``ctx`` (``random`` follows ``ctx.rng``)."""
        if self.random is not None:
            self.random.current = ctx.rng
        try:
            return self.fn(*args, ctx)
        finally:
            if self.random is not None:
                self.random.current = None


def code_sha256(source: str) -> str:
    """Return the sha256 of the file's UTF-8 bytes (what a spec and a link name)."""
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def user_frames(tb, filename: str = 'algorithm.py') -> List[Dict]:
    """Return the traceback's frames in the user's file: ``[{line, function}]``, innermost last."""
    out = []
    while tb is not None:
        co = tb.tb_frame.f_code
        if co.co_filename == filename:
            out.append({'line': tb.tb_lineno, 'function': co.co_name})
        tb = tb.tb_next
    return out


def describe_error(e: BaseException, filename: str = 'algorithm.py') -> Dict:
    """Return ``{type, message, line, frames}`` for an exception from user code."""
    frames = user_frames(e.__traceback__, filename)
    if isinstance(e, GuardError):
        line = e.problems[0]['line'] if e.problems else None
        return {'type': 'GuardError', 'message': str(e), 'line': line, 'frames': [],
                'problems': e.problems}
    return {'type': type(e).__name__, 'message': str(e),
            'line': frames[-1]['line'] if frames else None, 'frames': frames}


def load(source: str, filename: str = 'algorithm.py') -> Optional[UserModule]:
    """Return the loaded module (raises :class:`GuardError` or the file's own exception)."""
    return UserModule(source, filename)
