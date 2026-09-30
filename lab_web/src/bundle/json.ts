// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * A strict, LOSSLESS JSON parser.
 *
 * `JSON.parse` forgets whether `252.0` was a float or an int and cannot
 * hold a 30-digit integer exactly; a bundle's content hash depends on both
 * (Python re-serialises the parsed manifest). This parser keeps what
 * Python's `json.loads` would know:
 *
 * - an integer lexeme (no `.`/exponent) stays an exact decimal string
 *   ({@link JInt}); anything else is a double ({@link JFloat}) -- the same
 *   correctly-rounded double Python's `float()` gives;
 * - object members keep their input order ({@link JObject}).
 *
 * It is stricter than Python in documented ways, never looser: it refuses
 * `NaN`/`Infinity` literals (Python parses them, then refuses to hash
 * them), a float that overflows to infinity, and DUPLICATE KEYS (Python
 * keeps the last). Nesting deeper than {@link MAX_DEPTH} is refused with
 * Python's depth rule (`coco_lab.bundle._depth`: the top-level value is
 * level 1, and every value -- scalar or container -- counts).
 */

import { fail } from './errors';

export const MAX_DEPTH = 32;

export class JInt {
  /** The exact decimal lexeme, `-0` normalised to `0` (Python's `str(int)`). */
  readonly lex: string;
  constructor(lex: string) {
    this.lex = lex === '-0' ? '0' : lex;
  }
  get value(): number {
    return Number(this.lex);
  }
  get big(): bigint {
    return BigInt(this.lex);
  }
}

export class JFloat {
  readonly value: number;
  constructor(value: number) {
    this.value = value;
  }
}

export class JObject {
  readonly entries: ReadonlyArray<readonly [string, JNode]>;
  private readonly index: Map<string, JNode>;
  constructor(entries: Array<readonly [string, JNode]>) {
    this.entries = entries;
    this.index = new Map(entries);
  }
  get(key: string): JNode | undefined {
    return this.index.get(key);
  }
  has(key: string): boolean {
    return this.index.has(key);
  }
  keys(): string[] {
    return this.entries.map(([k]) => k);
  }
  /** A copy without `drop`'s keys (order kept). */
  without(...drop: string[]): JObject {
    return new JObject(this.entries.filter(([k]) => !drop.includes(k)));
  }
  /** A copy with `key` set to `value` (replaced in place, or appended). */
  with(key: string, value: JNode): JObject {
    const out = this.entries.map(([k, v]) => [k, k === key ? value : v] as const);
    if (!this.has(key)) out.push([key, value]);
    return new JObject(out);
  }
}

export type JNode = null | boolean | string | JInt | JFloat | JNode[] | JObject;

const NUMBER = /-?(?:0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?/y;
const WS = new Set([0x20, 0x09, 0x0a, 0x0d]);

/** Decode UTF-8 exactly as Python's `bytes.decode('utf-8')` would. */
export function decodeUtf8(bytes: Uint8Array): string {
  try {
    // ignoreBOM: keep a leading U+FEFF so the parser refuses it, as
    // Python's json.loads does ("Unexpected UTF-8 BOM").
    return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
  } catch {
    return fail('json', 'manifest is not JSON: not valid UTF-8');
  }
}

export function parseJson(text: string): JNode {
  let i = 0;
  const n = text.length;

  const err = (what: string): never =>
    fail('json', `manifest is not JSON: ${what} at char ${i}`);

  const ws = () => {
    while (i < n && WS.has(text.charCodeAt(i))) i++;
  };

  const str = (): string => {
    // text[i] === '"'
    i++;
    let out = '';
    let run = i;
    for (;;) {
      if (i >= n) err('unterminated string');
      const c = text.charCodeAt(i);
      if (c === 0x22) {
        out += text.slice(run, i);
        i++;
        return out;
      }
      if (c < 0x20) err('control character in string');
      if (c !== 0x5c) {
        i++;
        continue;
      }
      out += text.slice(run, i);
      const e = text[i + 1];
      i += 2;
      switch (e) {
        case '"': out += '"'; break;
        case '\\': out += '\\'; break;
        case '/': out += '/'; break;
        case 'b': out += '\b'; break;
        case 'f': out += '\f'; break;
        case 'n': out += '\n'; break;
        case 'r': out += '\r'; break;
        case 't': out += '\t'; break;
        case 'u': {
          const hex = text.slice(i, i + 4);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) err('bad \\u escape');
          out += String.fromCharCode(parseInt(hex, 16));
          i += 4;
          break;
        }
        default:
          err('bad escape');
      }
      run = i;
    }
  };

  const value = (level: number): JNode => {
    if (level > MAX_DEPTH) {
      fail('bounds', `manifest nests deeper than ${MAX_DEPTH}`);
    }
    ws();
    if (i >= n) err('unexpected end');
    const c = text[i];
    if (c === '{') {
      i++;
      const entries: Array<readonly [string, JNode]> = [];
      const seen = new Set<string>();
      ws();
      if (text[i] === '}') {
        i++;
        return new JObject(entries);
      }
      for (;;) {
        ws();
        if (text[i] !== '"') err('expected a key');
        const key = str();
        if (seen.has(key)) err(`duplicate key ${JSON.stringify(key)}`);
        seen.add(key);
        ws();
        if (text[i] !== ':') err("expected ':'");
        i++;
        entries.push([key, value(level + 1)]);
        ws();
        if (text[i] === ',') {
          i++;
          continue;
        }
        if (text[i] === '}') {
          i++;
          return new JObject(entries);
        }
        err("expected ',' or '}'");
      }
    }
    if (c === '[') {
      i++;
      const items: JNode[] = [];
      ws();
      if (text[i] === ']') {
        i++;
        return items;
      }
      for (;;) {
        items.push(value(level + 1));
        ws();
        if (text[i] === ',') {
          i++;
          continue;
        }
        if (text[i] === ']') {
          i++;
          return items;
        }
        err("expected ',' or ']'");
      }
    }
    if (c === '"') return str();
    if (text.startsWith('true', i)) {
      i += 4;
      return true;
    }
    if (text.startsWith('false', i)) {
      i += 5;
      return false;
    }
    if (text.startsWith('null', i)) {
      i += 4;
      return null;
    }
    NUMBER.lastIndex = i;
    const m = NUMBER.exec(text);
    if (!m || m[0] === '-') err('unexpected token');
    const lex = m![0];
    i += lex.length;
    if (m![1] === undefined && m![2] === undefined) return new JInt(lex);
    const v = Number(lex);
    if (!Number.isFinite(v)) err(`float ${lex} overflows`);
    return new JFloat(v);
  };

  const root = value(1);
  ws();
  if (i !== n) err('extra data');
  return root;
}

// -- helpers for reading a parsed manifest ------------------------------------

export const isObj = (v: JNode | undefined): v is JObject => v instanceof JObject;
export const isList = (v: JNode | undefined): v is JNode[] => Array.isArray(v);
export const isStr = (v: JNode | undefined): v is string => typeof v === 'string';
/** Python `isinstance(v, int) and not isinstance(v, bool)`. */
export const isInt = (v: JNode | undefined): v is JInt => v instanceof JInt;
/** Python `_num`: an int or float (not a bool) that is finite. */
export const isNum = (v: JNode | undefined): v is JInt | JFloat =>
  (v instanceof JInt || v instanceof JFloat) && Number.isFinite(v.value);

/** The numeric value of an int, float or bool (Python: True == 1). */
export function numeric(v: JNode | undefined): number | undefined {
  if (v instanceof JInt || v instanceof JFloat) return v.value;
  if (typeof v === 'boolean') return v ? 1 : 0;
  return undefined;
}

/** Python `==` between two parsed JSON values. */
export function pyEquals(a: JNode | undefined, b: JNode | undefined): boolean {
  if (a === undefined || b === undefined) return a === b;
  const na = numeric(a);
  const nb = numeric(b);
  if (na !== undefined || nb !== undefined) {
    if (a instanceof JInt && b instanceof JInt) return a.lex === b.lex;
    return na !== undefined && nb !== undefined && na === nb;
  }
  if (a === null || b === null) return a === b;
  if (typeof a === 'string' || typeof b === 'string') return a === b;
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
      a.every((x, k) => pyEquals(x, b[k]));
  }
  if (a instanceof JObject && b instanceof JObject) {
    const ka = a.keys();
    return ka.length === b.keys().length && ka.every((k) => b.has(k) && pyEquals(a.get(k), b.get(k)));
  }
  return false;
}

/** Python truthiness of a parsed JSON value. */
export function truthy(v: JNode | undefined): boolean {
  if (v === undefined || v === null || v === false) return false;
  if (v === true) return true;
  if (typeof v === 'string') return v.length > 0;
  if (v instanceof JInt || v instanceof JFloat) return v.value !== 0;
  if (Array.isArray(v)) return v.length > 0;
  return v.entries.length > 0;
}

/** Convert to plain JS values (numbers as JS numbers) for display. */
export function toPlain(v: JNode): unknown {
  if (v instanceof JInt || v instanceof JFloat) return v.value;
  if (Array.isArray(v)) return v.map(toPlain);
  if (v instanceof JObject) {
    const o: Record<string, unknown> = {};
    for (const [k, x] of v.entries) o[k] = toPlain(x);
    return o;
  }
  return v;
}
