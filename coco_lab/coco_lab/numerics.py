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
Deterministic transcendental functions for state hash v3 (G1.8).

**Why this exists.** The Arena model runs in two Pythons: CPython on a
desktop (glibc's libm, with FMA variants chosen at load time) and Pyodide in
the browser (musl's libm compiled to WebAssembly). IEEE 754 fixes the result
of ``+ - * /`` and ``sqrt`` exactly, but not of ``sin``, ``cos``, ``atan2``,
``exp``, ``log`` or ``pow``: two libms may differ in the last bit. G1.6
measured it: at tick 0 of the Depot, 2 of 480 LiDAR ranges differ in the
last bit between the two runtimes (state hash v2 encodes exact floats, so
the hashes differ from tick 0), and under v1's quantization a Fetch Rush run
diverged at tick 144 (``docs/v2/g1/data/g16/README.md``).

**The fix.** Under hash version 3 every transcendental the model calls is
computed here, in pure Python, from basic IEEE operations, ``math.sqrt``,
``math.ldexp``, ``math.fmod`` and ``math.fsum`` -- all exact or correctly
rounded on every conforming platform -- so the bits are the same in every
runtime. The algorithms are Sun's fdlibm (``k_sin.c``, ``k_cos.c``,
``e_rem_pio2.c``, ``s_atan.c``, ``e_atan2.c``, ``e_acos.c``, ``e_exp.c``,
``e_log.c``), accurate to under one ulp. ``hypot`` and ``dist`` are the
plain square root of a sequential sum of squares (CPython's own ``hypot``
is not IEEE-specified and its algorithm has changed across releases); ``tan`` is
``sin / cos``. ``x ** 2``, ``x ** 3`` and ``x ** 0.5`` call C ``pow``, so
the model's few uses go through :func:`sq`, :func:`cube` and :func:`root`.

**How it is switched.** Every ``coco_lab`` module imports its ``math`` from
here (``from .numerics import math``): one shared namespace, holding the real
:mod:`math` functions under hash versions 1 and 2 (unchanged, byte for byte,
so every old golden still holds) and the functions above under version 3.
:func:`version` -- entered by the Arena's entry points, the game rules and the
glue's queries with their run's ``hash_version`` -- swaps the ten entries in
place for the call and puts back what was in force after it, so a module
imported mid-run (a lens's pack) is covered and nothing outside a version 3
call ever sees version 3's functions. Call sites keep writing ``math.sin``.
"""

import contextlib
import functools
import math as _libm
import struct
import types

_PACK = struct.Struct('<d')
_UNPACK_Q = struct.Struct('<Q')


def _hi(x: float) -> int:
    """Return the high 32 bits of ``x``'s IEEE representation, as a signed int."""
    h = _UNPACK_Q.unpack(_PACK.pack(x))[0] >> 32
    return h - (1 << 32) if h & 0x80000000 else h


def _with_hi(x: float, hi: int) -> float:
    """``x`` with its high word replaced by ``hi`` (low word kept)."""
    lo = _UNPACK_Q.unpack(_PACK.pack(x))[0] & 0xFFFFFFFF
    return _PACK.unpack(_UNPACK_Q.pack(((hi & 0xFFFFFFFF) << 32) | lo))[0]


def _lo_zero(x: float) -> float:
    """``x`` with its low 32 bits cleared."""
    q = _UNPACK_Q.unpack(_PACK.pack(x))[0] & 0xFFFFFFFF00000000
    return _PACK.unpack(_UNPACK_Q.pack(q))[0]


# -- sin, cos: e_rem_pio2.c, k_sin.c, k_cos.c ---------------------------------

_INVPIO2 = 6.36619772367581382433e-01
_PIO2_1 = 1.57079632673412561417e+00
_PIO2_1T = 6.07710050650619224932e-11
_PIO2_2 = 6.07710050630396597660e-11
_PIO2_2T = 2.02226624879595063154e-21
_PIO2_3 = 2.02226624871116645580e-21
_PIO2_3T = 8.47842766036889956997e-32
_TWO_PI = 6.283185307179586


def _bits(q: int) -> float:
    return _PACK.unpack(_UNPACK_Q.pack(q))[0]


def _bexp(v: float) -> int:
    """Return the biased exponent field of ``v`` (``high word >> 20 & 0x7ff``), unpacked."""
    return 0 if v == 0.0 else max(_libm.frexp(v)[1] + 1022, 0)


# fdlibm's high-word tests as magnitudes: positive doubles order as their bits do, so
# ``ix <= 0x3FE921FB`` is ``|x| < bits(0x3FE921FC 00000000)``, and so on (bit-exact)
_PIO4_HW = _bits(0x3FE921FC00000000)
_BIG_HW = _bits(0x413921FC00000000)


def _rem_pio2(x: float):
    """Return ``(n, y0, y1)`` with ``x = n pi/2 + (y0 + y1)``, ``|y0 + y1| <= ~pi/4``."""
    t = abs(x)
    if t < _PIO4_HW:
        return 0, x, 0.0
    if t >= _BIG_HW:
        # |x| > 2^19 pi/2: fold by the double nearest 2 pi first (fmod is exact).
        # Not fdlibm's Payne-Hanek reduction -- less accurate for such angles,
        # but just as deterministic, and the model never meets one.
        return _rem_pio2(_libm.fmod(x, _TWO_PI))
    n = int(t * _INVPIO2 + 0.5)
    fn = float(n)
    r = t - fn * _PIO2_1
    w = fn * _PIO2_1T
    j = _bexp(t)
    y0 = r - w
    i = j - _bexp(y0)
    if i > 16:
        t = r
        w = fn * _PIO2_2
        r = t - w
        w = fn * _PIO2_2T - ((t - r) - w)
        y0 = r - w
        i = j - _bexp(y0)
        if i > 49:
            t = r
            w = fn * _PIO2_3
            r = t - w
            w = fn * _PIO2_3T - ((t - r) - w)
            y0 = r - w
    y1 = (r - y0) - w
    if x < 0:
        return -n, -y0, -y1
    return n, y0, y1


_S1 = -1.66666666666666324348e-01
_S2 = 8.33333333332248946124e-03
_S3 = -1.98412698298579493134e-04
_S4 = 2.75573137070700676789e-06
_S5 = -2.50507602534068634195e-08
_S6 = 1.58969099521155010221e-10


def _k_sin(x: float, y: float, iy: int) -> float:
    z = x * x
    v = z * x
    r = _S2 + z * (_S3 + z * (_S4 + z * (_S5 + z * _S6)))
    if iy == 0:
        return x + v * (_S1 + z * r)
    return x - ((z * (0.5 * y - v * r) - y) - v * _S1)


_C1 = 4.16666666666666019037e-02
_C2 = -1.38888888888741095749e-03
_C3 = 2.48015872894767294178e-05
_C4 = -2.75573143513906633035e-07
_C5 = 2.08757232129817482790e-09
_C6 = -1.13596475577881948265e-11


_TINY_HW = _bits(0x3E40000000000000)    # ix < 0x3E400000 (2^-27)
_P3_HW = _bits(0x3FD3333300000000)       # ix < 0x3FD33333
_P78_HW = _bits(0x3FE9000100000000)      # ix > 0x3FE90000


def _k_cos(x: float, y: float) -> float:
    ax = abs(x)
    if ax < _TINY_HW:
        return 1.0
    z = x * x
    r = z * (_C1 + z * (_C2 + z * (_C3 + z * (_C4 + z * (_C5 + z * _C6)))))
    if ax < _P3_HW:
        return 1.0 - (0.5 * z - (z * r - x * y))
    # fdlibm: x/4 with the low word cleared (exponent - 2: exact)
    qx = 0.28125 if ax >= _P78_HW else _lo_zero(ax) * 0.25
    hz = 0.5 * z - qx
    a = 1.0 - qx
    return a - (hz - (z * r - x * y))


def _domain(x: float) -> None:
    if _libm.isinf(x):
        raise ValueError('math domain error')


def _sin(x: float) -> float:
    if not _libm.isfinite(x):
        _domain(x)
        return x
    if abs(x) < _TINY_HW:
        return x                  # fdlibm: sin x = x below 2^-27 (keeps the sign of zero)
    n, y0, y1 = _rem_pio2(x)
    if n == 0:
        return _k_sin(x, 0.0, 0)
    q = n & 3
    if q == 0:
        return _k_sin(y0, y1, 1)
    if q == 1:
        return _k_cos(y0, y1)
    if q == 2:
        return -_k_sin(y0, y1, 1)
    return -_k_cos(y0, y1)


def _cos(x: float) -> float:
    if not _libm.isfinite(x):
        _domain(x)
        return x
    n, y0, y1 = _rem_pio2(x)
    q = n & 3
    if q == 0:
        return _k_cos(y0, y1)
    if q == 1:
        return -_k_sin(y0, y1, 1)
    if q == 2:
        return -_k_cos(y0, y1)
    return _k_sin(y0, y1, 1)


# The model asks for the same angles over and over (each LiDAR beam's direction is
# needed by the walls, the discs and the boxes), so the last few thousand answers are
# kept. The functions are pure: a remembered answer is the same bits. Zero is never
# kept (0.0 and -0.0 are one dictionary key, and their sines differ in sign).
_SIN: dict = {}
_COS: dict = {}
_KEEP = 4096


def sin(x: float) -> float:
    """Return fdlibm's ``sin``."""
    x = float(x)
    r = _SIN.get(x)
    if r is None:
        r = _sin(x)
        if x != 0.0 and x == x:
            if len(_SIN) >= _KEEP:
                _SIN.clear()
            _SIN[x] = r
    return r


def cos(x: float) -> float:
    """Return fdlibm's ``cos``."""
    x = float(x)
    r = _COS.get(x)
    if r is None:
        r = _cos(x)
        if x != 0.0 and x == x:
            if len(_COS) >= _KEEP:
                _COS.clear()
            _COS[x] = r
    return r


def tan(x: float) -> float:
    """``sin(x) / cos(x)``, both from here."""
    return sin(x) / cos(x)


# -- atan, atan2: s_atan.c, e_atan2.c ----------------------------------------

_ATANHI = (4.63647609000806093515e-01, 7.85398163397448278999e-01,
           9.82793723247329054082e-01, 1.57079632679489655800e+00)
_ATANLO = (2.26987774529616870924e-17, 3.06161699786838301793e-17,
           1.39033110312309984516e-17, 6.12323399573676603587e-17)
_AT = (3.33333333333329318027e-01, -1.99999999998764832476e-01,
       1.42857142725034663711e-01, -1.11111104054623557880e-01,
       9.09088713343650656196e-02, -7.69187620504482999495e-02,
       6.66107313738753120669e-02, -5.83357013379057348645e-02,
       4.97687799461593236017e-02, -3.65315727442169155270e-02,
       1.62858201153657823623e-02)


def atan(x: float) -> float:
    """Return fdlibm's ``atan``."""
    x = float(x)
    hx = _hi(x)
    ix = hx & 0x7FFFFFFF
    if ix >= 0x44100000:
        if _libm.isnan(x):
            return x + x
        return _ATANHI[3] + _ATANLO[3] if hx >= 0 else -_ATANHI[3] - _ATANLO[3]
    if ix < 0x3FDC0000:
        if ix < 0x3E200000:
            return x
        k = -1
    else:
        x = abs(x)
        if ix < 0x3FF30000:
            if ix < 0x3FE60000:
                k = 0
                x = (2.0 * x - 1.0) / (2.0 + x)
            else:
                k = 1
                x = (x - 1.0) / (x + 1.0)
        elif ix < 0x40038000:
            k = 2
            x = (x - 1.5) / (1.0 + 1.5 * x)
        else:
            k = 3
            x = -1.0 / x
    z = x * x
    w = z * z
    a = _AT
    s1 = z * (a[0] + w * (a[2] + w * (a[4] + w * (a[6] + w * (a[8] + w * a[10])))))
    s2 = w * (a[1] + w * (a[3] + w * (a[5] + w * (a[7] + w * a[9]))))
    if k < 0:
        return x - x * (s1 + s2)
    z = _ATANHI[k] - ((x * (s1 + s2) - _ATANLO[k]) - x)
    return -z if hx < 0 else z


_PI_O_4 = 7.8539816339744827900e-01
_PI_O_2 = 1.5707963267948965580e+00
_PI = 3.1415926535897931160e+00
_PI_LO = 1.2246467991473531772e-16


def atan2(y: float, x: float) -> float:
    """Return fdlibm's ``atan2``."""
    y = float(y)
    x = float(x)
    if _libm.isnan(x) or _libm.isnan(y):
        return x + y
    if x == 1.0:
        return atan(y)
    m = (1 if _libm.copysign(1.0, y) < 0 else 0) | (2 if _libm.copysign(1.0, x) < 0 else 0)
    if y == 0.0:
        return (y, y, _PI, -_PI)[m]
    if x == 0.0:
        return -_PI_O_2 if y < 0 else _PI_O_2
    if _libm.isinf(x):
        if _libm.isinf(y):
            return (_PI_O_4, -_PI_O_4, 3.0 * _PI_O_4, -3.0 * _PI_O_4)[m]
        return (0.0, -0.0, _PI, -_PI)[m]
    if _libm.isinf(y):
        return -_PI_O_2 if y < 0 else _PI_O_2
    k = ((_hi(y) & 0x7FFFFFFF) - (_hi(x) & 0x7FFFFFFF)) >> 20
    if k > 60:
        z = _PI_O_2 + 0.5 * _PI_LO
    elif x < 0 and k < -60:
        z = 0.0
    else:
        z = atan(abs(y / x))
    if m == 0:
        return z
    if m == 1:
        return -z
    if m == 2:
        return _PI - (z - _PI_LO)
    return (z - _PI_LO) - _PI


# -- acos: e_acos.c -------------------------------------------------------------

_PIO2_HI = 1.57079632679489655800e+00
_PIO2_LO = 6.12323399573676603587e-17
_PS = (1.66666666666666657415e-01, -3.25565818622400915405e-01,
       2.01212532134862925881e-01, -4.00555345006794114027e-02,
       7.91534994289814532176e-04, 3.47933107596021167570e-05)
_QS = (-2.40339491173441421878e+00, 2.02094576023350569471e+00,
       -6.88283971605453293030e-01, 7.70381505559019352791e-02)


def _acos_r(z: float) -> float:
    p = z * (_PS[0] + z * (_PS[1] + z * (_PS[2] + z * (_PS[3] + z * (_PS[4] + z * _PS[5])))))
    q = 1.0 + z * (_QS[0] + z * (_QS[1] + z * (_QS[2] + z * _QS[3])))
    return p / q


def acos(x: float) -> float:
    """Return fdlibm's ``acos``."""
    x = float(x)
    if _libm.isnan(x):
        return x
    hx = _hi(x)
    ix = hx & 0x7FFFFFFF
    if ix >= 0x3FF00000:
        if x == 1.0:
            return 0.0
        if x == -1.0:
            return _PI + 2.0 * _PIO2_LO
        raise ValueError('math domain error')
    if ix < 0x3FE00000:
        if ix <= 0x3C600000:
            return _PIO2_HI + _PIO2_LO
        r = _acos_r(x * x)
        return _PIO2_HI - (x - (_PIO2_LO - x * r))
    if hx < 0:
        z = (1.0 + x) * 0.5
        s = _libm.sqrt(z)
        w = _acos_r(z) * s - _PIO2_LO
        return _PI - 2.0 * (s + w)
    z = (1.0 - x) * 0.5
    s = _libm.sqrt(z)
    df = _lo_zero(s)
    c = (z - df * df) / (s + df)
    w = _acos_r(z) * s + c
    return 2.0 * (df + w)


# -- exp: e_exp.c ------------------------------------------------------------

_O_THRESHOLD = 7.09782712893383973096e+02
_U_THRESHOLD = -7.45133219101941108420e+02
_LN2HI = (6.93147180369123816490e-01, -6.93147180369123816490e-01)
_LN2LO = (1.90821492927058770002e-10, -1.90821492927058770002e-10)
_INVLN2 = 1.44269504088896338700e+00
_P = (1.66666666666666019037e-01, -2.77777777770155933842e-03,
      6.61375632143793436117e-05, -1.65339022054652515390e-06,
      4.13813679705723846039e-08)


def exp(x: float) -> float:
    """Return fdlibm's ``exp``; ``ldexp`` applies the power of two."""
    x = float(x)
    hx = _hi(x)
    xsb = 1 if hx < 0 else 0
    hx &= 0x7FFFFFFF
    if hx >= 0x40862E42:
        if _libm.isnan(x):
            return x + x
        if _libm.isinf(x):
            return x if xsb == 0 else 0.0
        if x > _O_THRESHOLD:
            raise OverflowError('math range error')
        if x < _U_THRESHOLD:
            return 0.0
    hi = lo = 0.0
    if hx > 0x3FD62E42:
        if hx < 0x3FF0A2B2:
            hi = x - _LN2HI[xsb]
            lo = _LN2LO[xsb]
            k = 1 - xsb - xsb
        else:
            k = int(_INVLN2 * x + (0.5, -0.5)[xsb])
            t = float(k)
            hi = x - t * _LN2HI[0]
            lo = t * _LN2LO[0]
        x = hi - lo
    elif hx < 0x3E300000:
        return 1.0 + x
    else:
        k = 0
    t = x * x
    c = x - t * (_P[0] + t * (_P[1] + t * (_P[2] + t * (_P[3] + t * _P[4]))))
    if k == 0:
        return 1.0 - ((x * c) / (c - 2.0) - x)
    y = 1.0 - ((lo - (x * c) / (2.0 - c)) - hi)
    return _libm.ldexp(y, k)


# -- log: e_log.c ------------------------------------------------------------

_LN2_HI = 6.93147180369123816490e-01
_LN2_LO = 1.90821492927058770002e-10
_TWO54 = 1.80143985094819840000e+16
_LG = (6.666666666666735130e-01, 3.999999999940941908e-01,
       2.857142874366239149e-01, 2.222219843214978396e-01,
       1.818357216161805012e-01, 1.531383769920937332e-01,
       1.479819860511658591e-01)


def _log(x: float) -> float:
    hx = _hi(x)
    k = 0
    if hx < 0x00100000:
        if x == 0.0 or hx < 0 or _libm.isnan(x):
            if _libm.isnan(x):
                return x
            raise ValueError('math domain error')
        k -= 54
        x *= _TWO54
        hx = _hi(x)
    if hx >= 0x7FF00000:
        return x + x
    k += (hx >> 20) - 1023
    hx &= 0x000FFFFF
    i = (hx + 0x95F64) & 0x100000
    x = _with_hi(x, hx | (i ^ 0x3FF00000))
    k += i >> 20
    f = x - 1.0
    dk = float(k)
    if (0x000FFFFF & (2 + hx)) < 3:
        if f == 0.0:
            return 0.0 if k == 0 else dk * _LN2_HI + dk * _LN2_LO
        r = f * f * (0.5 - 0.33333333333333333 * f)
        return f - r if k == 0 else dk * _LN2_HI - ((r - dk * _LN2_LO) - f)
    s = f / (2.0 + f)
    z = s * s
    i = hx - 0x6147A
    w = z * z
    j = 0x6B851 - hx
    t1 = w * (_LG[1] + w * (_LG[3] + w * _LG[5]))
    t2 = z * (_LG[0] + w * (_LG[2] + w * (_LG[4] + w * _LG[6])))
    i |= j
    r = t2 + t1
    if i > 0:
        hfsq = 0.5 * f * f
        if k == 0:
            return f - (hfsq - s * (hfsq + r))
        return dk * _LN2_HI - ((hfsq - (s * (hfsq + r) + dk * _LN2_LO)) - f)
    if k == 0:
        return f - s * (f - r)
    return dk * _LN2_HI - ((s * (f - r) - dk * _LN2_LO) - f)


def log(x: float, base: float = None) -> float:
    """Return fdlibm's natural logarithm; with ``base``, over that of the base (as CPython)."""
    x = float(x)
    if x <= 0.0:
        raise ValueError('math domain error')
    if base is None:
        return _log(x)
    return _log(x) / _log(float(base))


# -- hypot, dist; powers -------------------------------------------------------

def hypot(*coords: float) -> float:
    """``sqrt`` of the sequential sum of squares."""
    s = 0.0
    for c in coords:
        c = float(c)
        if _libm.isinf(c):
            return _libm.inf
        s += c * c
    return _libm.sqrt(s)


def dist(p, q) -> float:
    """``hypot`` of the coordinate differences."""
    if len(p) != len(q):
        raise ValueError('both points must have the same number of dimensions')
    return hypot(*(float(a) - float(b) for a, b in zip(p, q)))


#: the version-3 functions, by the name ``math`` gives them
DET = {'sin': sin, 'cos': cos, 'tan': tan, 'atan': atan, 'atan2': atan2, 'acos': acos,
       'exp': exp, 'log': log, 'hypot': hypot, 'dist': dist}
_LIBM = {k: getattr(_libm, k) for k in DET}

#: what every coco_lab module calls ``math``: the real module's contents, with
#: :data:`DET`'s ten swapped in while hash version 3 is in force
math = types.ModuleType('coco_lab.numerics.math')
math.__dict__.update({k: v for k, v in vars(_libm).items() if not k.startswith('__')})

_det = False


def sq(x):
    """``x ** 2`` (C ``pow``) under versions 1 and 2; ``x * x`` under 3."""
    return x * x if _det else x ** 2


def cube(x):
    """``x ** 3`` under versions 1 and 2; ``x * x * x`` under 3."""
    return x * x * x if _det else x ** 3


def root(x):
    """``x ** 0.5`` under versions 1 and 2; ``math.sqrt(x)`` under 3."""
    return _libm.sqrt(x) if _det else x ** 0.5


def deterministic() -> bool:
    """Whether hash version 3's numerics are in force."""
    return _det


def _set(want: bool) -> None:
    global _det
    if want != _det:
        _det = want
        math.__dict__.update(DET if want else _LIBM)


def use(hash_version: int) -> None:
    """Put the numerics of ``hash_version`` in force until changed (prefer :func:`version`)."""
    _set(hash_version >= 3)


@contextlib.contextmanager
def version(hash_version: int):
    """Use the numerics of ``hash_version`` for the ``with`` block, then what was in force."""
    was = _det
    _set(hash_version >= 3)
    try:
        yield
    finally:
        _set(was)


def in_run(method):
    """Run ``method`` inside :func:`version` of ``self.hash_version`` (default 1)."""
    @functools.wraps(method)
    def run(self, *args, **kw):
        was = _det
        _set(getattr(self, 'hash_version', 1) >= 3)
        try:
            return method(self, *args, **kw)
        finally:
            _set(was)
    return run
