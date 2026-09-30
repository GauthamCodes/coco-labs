// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Python's `repr(float)`, exactly.
 *
 * Python and JavaScript both print the SHORTEST decimal digit string that
 * round-trips to the double, choosing the closest when several are
 * shortest; they differ only in layout. `String(x)` gives the digits; this
 * lays them out the Python way (`float_repr_style == 'short'`, format
 * `'r'`):
 *
 * - with `decpt` the position of the decimal point relative to the first
 *   significant digit, scientific notation iff `decpt <= -4` or
 *   `decpt > 16`, i.e. exponent `< -4` or `>= 16`;
 * - the exponent has a sign and at least two digits (`1e-05`, `1e+16`);
 * - a fixed-notation integral value keeps a `.0` (`252.0`); a scientific
 *   one with a single digit has no `.0` (`1e+16`).
 *
 * `test/pyrepr.test.ts` checks this against 4,000 Python `repr`s of every
 * magnitude, plus the canonical-JSON corpus.
 */
export function pyFloatRepr(x: number): string {
  if (!Number.isFinite(x)) throw new RangeError(`not finite: ${x}`);
  if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0';
  const sign = x < 0 ? '-' : '';
  const s = String(Math.abs(x));
  const [mant, expPart] = s.split('e');
  const e = expPart === undefined ? 0 : Number(expPart);
  const dot = mant.indexOf('.');
  const intPart = dot < 0 ? mant : mant.slice(0, dot);
  const fracPart = dot < 0 ? '' : mant.slice(dot + 1);
  let digits = intPart + fracPart;
  let point = intPart.length + e; // decimal point after `point` digits
  const lead = digits.length - digits.replace(/^0+/, '').length;
  digits = digits.slice(lead);
  point -= lead;
  digits = digits.replace(/0+$/, '');
  const exp10 = point - 1; // value = d.ddd x 10^exp10
  if (exp10 < -4 || exp10 >= 16) {
    const m = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : digits;
    const es = Math.abs(exp10).toString().padStart(2, '0');
    return `${sign}${m}e${exp10 < 0 ? '-' : '+'}${es}`;
  }
  if (point <= 0) return `${sign}0.${'0'.repeat(-point)}${digits}`;
  if (digits.length <= point) return `${sign}${digits}${'0'.repeat(point - digits.length)}.0`;
  return `${sign}${digits.slice(0, point)}.${digits.slice(point)}`;
}
