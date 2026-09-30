// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `coco_lab.bundle.canonical_json` in TypeScript: Python's
 * `json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)`.
 *
 * - keys sorted by Unicode CODE POINT (Python's `str` order), not by UTF-16
 *   code unit (JavaScript's default sort): U+FF01 sorts before U+1F600;
 * - `ensure_ascii`: every code unit outside `' '..'~'` is written `\uXXXX`
 *   in lowercase hex (so an astral character becomes its surrogate pair,
 *   and DEL is escaped), except the short forms `\" \\ \n \r \t \b \f`;
 * - ints as their exact decimal ({@link JInt}), floats as Python `repr`.
 */

import { JFloat, JInt, JObject, type JNode } from './json';
import { pyFloatRepr } from './pyrepr';

const SHORT: Record<number, string> = {
  0x22: '\\"', 0x5c: '\\\\', 0x0a: '\\n', 0x0d: '\\r', 0x09: '\\t', 0x08: '\\b', 0x0c: '\\f',
};

export function pyString(s: string): string {
  let out = '"';
  for (let k = 0; k < s.length; k++) {
    const c = s.charCodeAt(k);
    const short = SHORT[c];
    if (short !== undefined) out += short;
    else if (c >= 0x20 && c <= 0x7e) out += s[k];
    else out += '\\u' + c.toString(16).padStart(4, '0');
  }
  return out + '"';
}

/** Compare two strings by Unicode code point, as Python does. */
export function compareCodePoints(a: string, b: string): number {
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    const ca = a.codePointAt(i)!;
    const cb = b.codePointAt(j)!;
    if (ca !== cb) return ca < cb ? -1 : 1;
    i += ca > 0xffff ? 2 : 1;
    j += cb > 0xffff ? 2 : 1;
  }
  const ra = a.length - i;
  const rb = b.length - j;
  return ra === rb ? 0 : ra < rb ? -1 : 1;
}

export function canonicalJson(v: JNode): string {
  if (v === null) return 'null';
  if (v === true) return 'true';
  if (v === false) return 'false';
  if (typeof v === 'string') return pyString(v);
  if (v instanceof JInt) return v.lex;
  if (v instanceof JFloat) return pyFloatRepr(v.value);
  if (Array.isArray(v)) return '[' + v.map(canonicalJson).join(',') + ']';
  if (v instanceof JObject) {
    const entries = [...v.entries].sort(([a], [b]) => compareCodePoints(a, b));
    return '{' + entries.map(([k, x]) => pyString(k) + ':' + canonicalJson(x)).join(',') + '}';
  }
  throw new TypeError('not a JSON value');
}
