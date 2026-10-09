// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M2.7: Lab 4's search bundles convert to v2 runs and back with nothing
 * lost -- the v1 arrays rebuilt from the v2 CHANNELS alone and accepted by
 * the v1 decoder, which checks the content hash -- and the 16 searches
 * recorded on the full stack convert to EXACTLY the committed run file
 * (docs/v2/data/m2/m27/p05_matrix.mcap), the one
 * coco_schemas/test/test_search_replay_v2.py replays.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { fromLab4, toLab4, CH } from '../src/convert/lab4';
import { loadSearchBytes, parseSearchManifest } from '../src/search/decode';
import { EvidenceClass, Tier } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { readRun, writeRun } from '../src/schemas/mcap';
import { LAB_WEB, unregistered } from './helpers';

const REPO = join(LAB_WEB, '..');
const RECORDED = join(REPO, 'docs', 'data', 'lab4', 'replay', 'p05_matrix');
const SKETCH = join(LAB_WEB, 'public', 'generated', 'search', 'search_arena');
const COMMITTED = join(REPO, 'docs', 'v2', 'data', 'm2', 'm27', 'p05_matrix.mcap');

async function load(dir: string) {
  const manifest = new Uint8Array(readFileSync(join(dir, 'manifest.json')));
  const comp = parseSearchManifest(manifest).compression;
  const arrays = new Uint8Array(readFileSync(join(dir, comp === 'gzip' ? 'arrays.bin.gz' : 'arrays.bin')));
  return { manifest, bundle: await loadSearchBytes(manifest, arrays) };
}

async function roundTrip(dir: string) {
  const { manifest, bundle } = await load(dir);
  const conv = await fromLab4(bundle, manifest);
  const bytes = await writeRun(conv.manifest, conv.records);
  const run = await readRun(bytes);
  const back = await toLab4(run.manifest, run.messages);
  return { bundle, conv, bytes, run, back };
}

describe('Lab 4 search bundles -> v2 runs -> Lab 4 bundles', () => {
  it('the 16 recorded searches: lossless, STACK, and exactly the committed file', async () => {
    const { bundle, bytes, run, back } = await roundTrip(RECORDED);
    expect(bundle.runs.length).toBe(16);
    expect(bundle.runs.every((r) => r.kind === 'recorded')).toBe(true);
    expect(back.contentHash).toBe(bundle.contentHash);
    expect(unregistered(run.messages)).toEqual([]);
    expect(run.manifest.tier).toBe(Tier.STACK);
    expect(run.manifest.evidenceClass).toBe(EvidenceClass.STACK);
    for (const [a, b] of bundle.runs.map((r, i) => [r, back.runs[i]] as const)) {
      expect(Array.from(b.belief)).toEqual(Array.from(a.belief));
      expect(Array.from(b.candidates)).toEqual(Array.from(a.candidates));
      expect(Array.from(b.kinds)).toEqual(Array.from(a.kinds));
    }
    expect(Buffer.from(bytes).equals(readFileSync(COMMITTED))).toBe(true);
  });

  it('every look is an observation, every choice an action with every candidate', async () => {
    const { bundle, run } = await roundTrip(RECORDED);
    const count = (ch: string) => run.messages.filter((m) => m.channel === ch).length;
    const looks = bundle.runs.reduce((s, r) => s + Array.from(r.kinds).filter((k) => k === 1).length, 0);
    const selects = bundle.runs.reduce((s, r) => s + Array.from(r.kinds).filter((k) => k === 0).length, 0);
    expect(count(CH.observation)).toBe(looks);
    expect(count(CH.action)).toBe(selects);
    expect(count(CH.header)).toBe(16);
    expect(looks).toBe(39); // RESULTS.md, COCO Lab Phase 5: 39 looks
  });

  it('the Sketch searches the site computes: lossless, MODEL', async () => {
    const { bundle, run, back } = await roundTrip(SKETCH);
    expect(back.contentHash).toBe(bundle.contentHash);
    expect(run.manifest.evidenceClass).toBe(EvidenceClass.MODEL);
  });
});
