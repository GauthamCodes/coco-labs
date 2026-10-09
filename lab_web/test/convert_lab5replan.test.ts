// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M2.7: Lab 5's D* Lite replanning bundles convert to v2 runs and back with
 * nothing lost (the v1 decoder re-checks the content hash); every D* Lite
 * event survives with its kind, rhs and round.
 */

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { fromLab5Replan, toLab5Replan } from '../src/convert/lab5replan';
import { loadReplanBytes } from '../src/move/decode';
import { EvidenceClass } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { readRun, writeRun } from '../src/schemas/mcap';
import { LAB_WEB, unregistered } from './helpers';

const DIR = join(LAB_WEB, 'public', 'generated', 'move', 'replan');
const IDS = readdirSync(DIR).sort();

describe('Lab 5 replan bundles -> v2 runs -> replan bundles', () => {
  it('finds the four replanning worlds', () => {
    expect(IDS).toEqual(['arena_c', 'sketch_0', 'sketch_1', 'sketch_2']);
  });

  it.each(IDS)('%s: lossless, hash-checked, MODEL', async (id) => {
    const manifest = new Uint8Array(readFileSync(join(DIR, id, 'manifest.json')));
    const bundle = await loadReplanBytes(manifest, new Uint8Array(readFileSync(join(DIR, id, 'arrays.bin.gz'))));
    const conv = await fromLab5Replan(bundle, manifest);
    const run = await readRun(await writeRun(conv.manifest, conv.records));
    expect(run.manifest.evidenceClass).toBe(EvidenceClass.MODEL);
    const back = await toLab5Replan(run.manifest, run.messages);
    expect(back.contentHash).toBe(bundle.contentHash);
    expect(unregistered(run.messages)).toEqual([]);
    expect(Array.from(back.trace.rhs)).toEqual(Array.from(bundle.trace.rhs));
    expect(Array.from(back.walk)).toEqual(Array.from(bundle.walk));
  });
});
