// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The invalid-bundle corpus (tools/invalid_corpus.py). tools/test_tools.py
// asserts coco_lab refuses every case; here the TS decoder must refuse every
// STRUCTURAL case with the named code, decode the SEMANTIC ones (only
// coco_lab can judge those) and then be stopped by the catalog gate, and
// refuse the one case Python accepts (duplicate keys: TS is stricter).

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { BundleError } from '../src/bundle/errors';
import { loadBundleBytes, requireValidated, type CatalogEntry } from '../src/bundle/load';
import { LAB_WEB, loadDir, readBundleDir, REPO } from './helpers';

const INVALID = join(LAB_WEB, 'test/invalid');
const index = JSON.parse(readFileSync(join(INVALID, 'index.json'), 'utf-8'));
const cases = Object.entries<any>(index.cases);

async function codeOf(p: Promise<unknown>): Promise<string | null> {
  try {
    await p;
    return null;
  } catch (exc) {
    if (exc instanceof BundleError) return exc.code;
    throw exc;
  }
}

describe('invalid corpus', () => {
  it('has the structural and semantic cases the plan lists', () => {
    const names = cases.map(([n]) => n);
    for (const n of ['truncated', 'padded', 'flipped_bit', 'major_2', 'bad_version', 'arrays_reversed',
      'wrong_dtype', 'nan_in_g', 'too_deep', 'gzip_bomb', 'gzip_claimed_raw', 'recording_under_1_0',
      'recording_on_glass_box', 'group_present_and_missing', 'group_count', 't_backwards', 'map_hash',
      'run_header', 'duplicate_key', 'path_not_neighbours']) {
      expect(names).toContain(n);
    }
    expect(Object.keys(index.generated)).toEqual(['oversize_manifest']);
  });

  it.each(cases.filter(([, c]) => c.tier === 'structural'))(
    'refuses %s with the code the corpus names', async (name, c) => {
      expect(await codeOf(loadDir(join(INVALID, name)))).toBe(c.code);
    });

  it.each(cases.filter(([, c]) => c.tier === 'semantic'))(
    'decodes semantic case %s structurally, and the catalog gate refuses it', async (name) => {
      const b = await loadDir(join(INVALID, name));
      const golden = await loadDir(join(REPO, 'coco_lab/test/fixtures/bundles/astar_open'));
      const entry = { id: 'astar_open', content_hash: golden.contentHash,
        validated: { by: 'coco_lab', replay: 'reproduced' } } as CatalogEntry;
      expect(() => requireValidated(b, entry)).toThrow(/catalog_mismatch/);
      expect(requireValidated(golden, entry)?.by).toBe('catalog');
    });

  it('refuses the generated oversize manifest before parsing it', async () => {
    const g = index.generated.oversize_manifest;
    const { arrays } = readBundleDir(join(REPO, 'coco_lab/test/fixtures/bundles/astar_open'));
    const manifest = new Uint8Array(g.bytes).fill(0x20);
    expect(await codeOf(loadBundleBytes(manifest, arrays))).toBe(g.code);
  });

  it('stops a gzip bomb at the declared size + 1 byte', async () => {
    const { manifest, arrays } = readBundleDir(join(INVALID, 'gzip_bomb'));
    expect(arrays.length).toBeLessThan(100_000); // 64 MiB of zeros, compressed
    const t0 = performance.now();
    expect(await codeOf(loadBundleBytes(manifest, arrays))).toBe('length');
    expect(performance.now() - t0).toBeLessThan(5_000);
  });

  it('is never more permissive than Python: TS-only refusals are listed', () => {
    const tsOnly = cases.filter(([, c]) => c.python === 'accepts').map(([n]) => n);
    expect(tsOnly).toEqual(['duplicate_key']);
  });
});
