// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M2.7: Lab 2's localisation bundles convert to v2 runs and back with
 * nothing lost (the v1 decoder re-checks the content hash), into the
 * whole loop's families: estimates, particles, MCL bookkeeping, the EKF.
 */

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { CH, fromLab2, toLab2 } from '../src/convert/lab2';
import { loadLocBytes } from '../src/loc/decode';
import { EvidenceClass } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { readRun, writeRun } from '../src/schemas/mcap';
import { LAB_WEB, unregistered } from './helpers';

const DIR = join(LAB_WEB, 'public', 'generated', 'loc');
const IDS = readdirSync(DIR).filter((d) => !d.endsWith('.json')).sort();

describe('Lab 2 loc bundles -> v2 runs -> loc bundles', () => {
  it('finds the five localisation bundles', () => {
    expect(IDS.length).toBe(5);
  });

  it.each(IDS)('%s: lossless, hash-checked, MODEL', async (id) => {
    const manifest = new Uint8Array(readFileSync(join(DIR, id, 'manifest.json')));
    const bundle = await loadLocBytes(manifest, new Uint8Array(readFileSync(join(DIR, id, 'arrays.bin.gz'))));
    const conv = await fromLab2(bundle, manifest);
    const run = await readRun(await writeRun(conv.manifest, conv.records));
    expect(run.manifest.evidenceClass).toBe(EvidenceClass.MODEL);
    const back = await toLab2(run.manifest, run.messages);
    expect(back.contentHash).toBe(bundle.contentHash);
    expect(unregistered(run.messages)).toEqual([]);
    const channels = new Set(run.messages.map((m) => m.channel));
    if (bundle.runs.some((r) => r.kind === 'mcl')) expect(channels.has(CH.set)).toBe(true);
    if (bundle.runs.some((r) => r.kind === 'ekf')) expect(channels.has(CH.ekf)).toBe(true);
  });
});
