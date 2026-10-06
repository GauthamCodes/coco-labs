// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The search-bundle decoder against Python, bundle by bundle: every array's
// little-endian bytes must hash to what coco_lab wrote
// (golden/search_expected.json, from tools/make_search_expectations.py), and
// the content hash is RECOMPUTED here and must equal the manifest's.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { BundleError } from '../src/bundle/errors';
import { sha256Hex } from '../src/bundle/sha256';
import { loadSearchBytes, parseSearchManifest, type DecodedSearchBundle } from '../src/search/decode';
import { LAB_WEB, readBundleDir, REPO } from './helpers';

const expected = JSON.parse(readFileSync(join(LAB_WEB, 'test/golden/search_expected.json'), 'utf-8'));

type Col = Int32Array | Float64Array;
const bytesOf = (c: Col) => new Uint8Array(c.buffer, c.byteOffset, c.byteLength);

function columnOf(b: DecodedSearchBundle, name: string): Col {
  const [, id, col] = name.split('.');
  const r = b.runs.find((x) => x.id === id)!;
  const key = ({ kind: 'kinds', region: 'region', outcome: 'outcome', cost: 'cost', belief: 'belief',
    candidates: 'candidates', t: 't' } as Record<string, keyof typeof r>)[col];
  return r[key] as Col;
}

const v = (x: unknown) => (x === 'nan' ? NaN : x === 'inf' ? Infinity : x === '-inf' ? -Infinity : x);

async function load(dir: string) {
  const { manifest, arrays } = readBundleDir(join(REPO, dir));
  return loadSearchBytes(manifest, arrays);
}

const cases: Array<[string, any]> = expected.bundles.map((e: any) => [e.id, e]);

describe.each(cases)('search bundle %s', (_id, exp) => {
  it('decodes, every array byte-identical to coco_lab', async () => {
    const b = await load(exp.dir);
    expect(b.version).toBe(exp.version);
    expect(b.contentHash).toBe(exp.content_hash);
    expect(b.problem.regions.map((r) => r.id)).toEqual(exp.regions);
    for (const [name, a] of Object.entries(exp.arrays) as Array<[string, any]>) {
      const col = columnOf(b, name);
      expect(col.length, name).toBe(a.count);
      expect(await sha256Hex(bytesOf(col)), name).toBe(a.sha256);
      if (a.count) {
        expect(col[0], `${name}[0]`).toBe(v(a.first));
        expect(col[col.length - 1], `${name}[-1]`).toBe(v(a.last));
      }
    }
  });

  it('carries the runs and their summaries as coco_lab wrote them', async () => {
    const b = await load(exp.dir);
    expect(b.runs.map((r) => r.id)).toEqual(exp.runs.map((r: any) => r.id));
    for (const [r, e] of b.runs.map((r, i) => [r, exp.runs[i]] as const)) {
      expect(r.kind).toBe(e.kind);
      expect(r.n).toBe(e.n_events);
      expect(r.summary).toEqual(e.summary);
    }
  });
});

describe('search bundle refusals', () => {
  const dir = expected.bundles.find((e: any) => e.compression === 'none').dir;

  it('refuses a flipped byte (content hash)', async () => {
    const { manifest, arrays } = readBundleDir(join(REPO, dir));
    const bad = new Uint8Array(arrays);
    bad[3] ^= 1;
    await expect(loadSearchBytes(manifest, bad)).rejects.toBeInstanceOf(BundleError);
  });

  it('refuses an unknown major version', () => {
    const { manifest } = readBundleDir(join(REPO, dir));
    const m = JSON.parse(new TextDecoder().decode(manifest));
    m.version = '2.0';
    expect(() => parseSearchManifest(new TextEncoder().encode(JSON.stringify(m)))).toThrow(/major version 2/);
  });

  it('refuses another schema', () => {
    const { manifest } = readBundleDir(join(REPO, dir));
    const m = JSON.parse(new TextDecoder().decode(manifest));
    m.schema = 'coco_lab.slam_bundle';
    expect(() => parseSearchManifest(new TextEncoder().encode(JSON.stringify(m)))).toThrow(/schema/);
  });

  it('keeps the recorded run\'s timeline and its evaluator block apart from the trace', async () => {
    const rec = expected.bundles.find((e: any) => e.runs.some((r: any) => r.kind === 'recorded'));
    const b = await load(rec.dir);
    const r = b.runs.find((x) => x.kind === 'recorded')!;
    expect(r.timeline.length).toBeGreaterThan(0);
    expect(r.t!.length).toBe(r.n);
    expect(r.evaluator).toHaveProperty('truth_region');
    expect(r.summary.truth).toBeNull();
  });
});
