// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M2.7: Lab 3's mapping/SLAM bundles convert to v2 runs and back with
 * nothing lost (the v1 decoder re-checks the content hash): maps,
 * FastSLAM particles, EKF-SLAM landmarks, the pose graph, the IDEALISED
 * landmark sightings, and the external backends of the recorded tour.
 */

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fromBinary } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import { CH, fromLab3, toLab3 } from '../src/convert/lab3';
import { loadSlamBytes } from '../src/map/decode';
import { EvidenceClass } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { SlamHeaderSchema } from '../src/schemas/gen/coco/map/v1/map_pb';
import { readRun, writeRun } from '../src/schemas/mcap';
import { LAB_WEB, unregistered } from './helpers';

const DIR = join(LAB_WEB, 'public', 'generated', 'map');
const IDS = readdirSync(DIR).filter((d) => !d.endsWith('.json')).sort();

describe('Lab 3 slam bundles -> v2 runs -> slam bundles', () => {
  it('finds the five mapping bundles', () => {
    expect(IDS).toEqual(['map_arena', 'map_corridor', 'map_landmarks', 'map_loop', 's1_tour']);
  });

  it.each(IDS)('%s: lossless, hash-checked, labelled', async (id) => {
    const manifest = new Uint8Array(readFileSync(join(DIR, id, 'manifest.json')));
    const bundle = await loadSlamBytes(manifest, new Uint8Array(readFileSync(join(DIR, id, 'arrays.bin.gz'))));
    const conv = await fromLab3(bundle, manifest);
    const run = await readRun(await writeRun(conv.manifest, conv.records));
    const back = await toLab3(run.manifest, run.messages);
    expect(back.contentHash).toBe(bundle.contentHash);
    expect(unregistered(run.messages)).toEqual([]);
    expect(run.manifest.evidenceClass).toBe(bundle.world.source === 'recorded' ? EvidenceClass.STACK : EvidenceClass.MODEL);
    const evid = run.messages.filter((m) => m.channel === CH.slamHeader).map((m) => fromBinary(SlamHeaderSchema, m.data))
      .map((h) => [h.slamId, h.params?.items.find((p) => p.key === 'evidence')?.value?.value.value]);
    for (const [sid, ev] of evid) expect(ev).toBe(String(sid).startsWith('ext:') ? 'STACK' : 'MODEL');
  });
});
