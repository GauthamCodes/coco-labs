// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The canonical-JSON corpus: Python's canonical_json + sha256 for >= 1,000
// seeded, deliberately non-canonical JSON texts, and Python's repr for
// 4,000 doubles (tools/json_corpus.py). TS must agree byte for byte.

import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

import { canonicalJson, compareCodePoints } from '../src/bundle/canonical';
import { BundleError } from '../src/bundle/errors';
import { JFloat, JInt, parseJson } from '../src/bundle/json';
import { pyFloatRepr } from '../src/bundle/pyrepr';
import { sha256Hex } from '../src/bundle/sha256';

interface Corpus {
  cases: Array<{ input: string; canonical: string | null; sha256?: string }>;
  floats: Array<[string, string]>;
}
const corpus: Corpus = JSON.parse(
  readFileSync(new URL('./golden/json_corpus.json', import.meta.url), 'utf-8'),
);

describe('canonical-JSON corpus', () => {
  it('has at least 1,000 cases', () => {
    expect(corpus.cases.length).toBeGreaterThanOrEqual(1000);
  });

  it('matches Python byte for byte and hash for hash on every case', async () => {
    let checked = 0;
    for (const c of corpus.cases) {
      if (c.canonical === null) {
        // Python refuses to serialise it (a float that overflowed to inf);
        // TS refuses to parse it.
        expect(() => parseJson(c.input)).toThrow(BundleError);
        continue;
      }
      const ours = canonicalJson(parseJson(c.input));
      expect(ours, c.input).toBe(c.canonical);
      expect(await sha256Hex(new TextEncoder().encode(ours))).toBe(c.sha256);
      checked++;
    }
    expect(checked).toBeGreaterThanOrEqual(1000);
  });

  it('reproduces Python repr for 4,000 doubles of every magnitude', () => {
    const dv = new DataView(new ArrayBuffer(8));
    for (const [hex, text] of corpus.floats) {
      for (let k = 0; k < 8; k++) dv.setUint8(k, parseInt(hex.slice(2 * k, 2 * k + 2), 16));
      expect(pyFloatRepr(dv.getFloat64(0, false)), hex).toBe(text);
    }
    expect(corpus.floats.length).toBe(4000);
  });
});

describe('the hazards a JSON.parse round trip gets wrong', () => {
  it('keeps int and float apart and formats like Python', () => {
    expect(canonicalJson(parseJson('252.0'))).toBe('252.0');
    expect(canonicalJson(parseJson('252'))).toBe('252');
    expect(canonicalJson(parseJson('0.00001'))).toBe('1e-05');
    expect(canonicalJson(parseJson('1e16'))).toBe('1e+16');
    expect(canonicalJson(parseJson('1e15'))).toBe('1000000000000000.0');
    expect(canonicalJson(parseJson('-0'))).toBe('0');
    expect(canonicalJson(parseJson('-0.0'))).toBe('-0.0');
    expect(canonicalJson(parseJson('12345678901234567890123'))).toBe('12345678901234567890123');
  });

  it('sorts keys by code point and escapes like ensure_ascii', () => {
    expect(canonicalJson(parseJson('{"\\ud83d\\ude00":2,"\\uff01":1}'))).toBe(
      '{"\\uff01":1,"\\ud83d\\ude00":2}',
    );
    expect(compareCodePoints('！', '\u{1f600}')).toBe(-1);
    expect(canonicalJson(parseJson('"\\u007f\\/é"'))).toBe('"\\u007f/\\u00e9"');
  });

  it('parses losslessly', () => {
    expect(parseJson('1.0')).toBeInstanceOf(JFloat);
    expect(parseJson('1')).toBeInstanceOf(JInt);
  });

  it('refuses what Python refuses, and is stricter where documented', () => {
    for (const bad of ['NaN', '-Infinity', '{"a":1,"a":1}', '﻿{}', '[1,]', '01', '1.', '"\t"', '{} x']) {
      expect(() => parseJson(bad), bad).toThrow(BundleError);
    }
    const deep = '{"a":' + '['.repeat(40) + '1' + ']'.repeat(40) + '}';
    expect(() => parseJson(deep)).toThrow(/bounds/);
    // 32 levels exactly is allowed (Python: _depth <= 32)
    const ok = '['.repeat(31) + '1' + ']'.repeat(31);
    expect(() => parseJson(ok)).not.toThrow();
    expect(() => parseJson('[' + ok + ']')).toThrow(/bounds/);
  });
});
