// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M2.7: Lab 5's drive bundles (every controller run recorded on the full
 * stack) convert to one v2 run per drive and back with nothing lost: the
 * bundle's arrays rebuilt from ALL its runs' channels and accepted by the
 * v1 decoder (content hash). Nav2's own candidates come out as STACK
 * control.local batches, exactly as recorded.
 */

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fromBinary } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import { CH, fromLab5Drive, toLab5Drive } from '../src/convert/lab5';
import { loadDriveBytes } from '../src/move/decode';
import { CandidateBatchSchema, ControllerHeaderSchema } from '../src/schemas/gen/coco/control/v1/control_pb';
import { EvidenceClass } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { readRun, writeRun } from '../src/schemas/mcap';
import { LAB_WEB, unregistered } from './helpers';

const DIR = join(LAB_WEB, 'public', 'generated', 'move', 'drive');
const IDS = readdirSync(DIR).sort();

async function convert(id: string) {
  const manifest = new Uint8Array(readFileSync(join(DIR, id, 'manifest.json')));
  const bundle = await loadDriveBytes(manifest, new Uint8Array(readFileSync(join(DIR, id, 'arrays.bin.gz'))));
  const conv = await fromLab5Drive(bundle, manifest, null);
  const files = [];
  for (const c of conv) files.push(await readRun(await writeRun(c.manifest, c.records)));
  return { bundle, conv, files };
}

describe('Lab 5 drive bundles -> v2 runs (one per drive) -> drive bundles', () => {
  it('finds the four scenarios', () => {
    expect(IDS).toEqual(['crossing', 'mislocalised', 'oncoming', 'static_room']);
  });

  it.each(IDS)('%s: lossless, hash-checked, every run STACK', async (id) => {
    const { bundle, conv, files } = await convert(id);
    expect(conv.length).toBe(bundle.runs.length);
    expect(files.every((f) => f.manifest.evidenceClass === EvidenceClass.STACK)).toBe(true);
    const back = await toLab5Drive(files);
    expect(back.contentHash).toBe(bundle.contentHash);
    for (const f of files) expect(unregistered(f.messages)).toEqual([]);
    // a run's header names it and its controller
    const head = fromBinary(ControllerHeaderSchema, files[0].messages.find((m) => m.channel === CH.header)!.data);
    expect(head.controllerId).toBe(bundle.runs[0].id);
    expect(head.kind).toBe(bundle.runs[0].controller);
    expect(head.evidence).toBe('STACK');
  });

  it('Nav2\'s recorded candidates play as STACK control.local batches, valid and best as recorded', async () => {
    const { bundle, files } = await convert('static_room');
    const i = bundle.runs.findIndex((r) => r.rollouts);
    expect(i).toBeGreaterThanOrEqual(0);
    const r = bundle.runs[i];
    const frames = files[i].messages.filter((m) => m.channel === CH.candidates)
      .map((m) => fromBinary(CandidateBatchSchema, m.data)).filter((b) => b.controllerId === r.id);
    expect(frames.length).toBe(r.rollouts!.t.length);
    const valid = frames.reduce((s, f) => s + f.valid.filter(Boolean).length, 0);
    const recorded = Array.from(r.rollouts!.flags).filter((f) => (f & 3) === 1).length;
    expect(valid).toBe(recorded);
  });
});
