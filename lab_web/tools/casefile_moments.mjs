// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Write the moments a mission's beat scrubs to (M3.4), found in each Case
 * File by src/arena/moments.ts -- the rule is there, with its threshold:
 *
 *   node tools/casefile_moments.mjs OUT.json ID...      (from lab_web)
 *
 * The output is committed (docs/v2/data/m3/m34/moments.json);
 * lab_web/tools/missions.py requires every Case File link in a mission to
 * name one of these moments and its tick, and test/casefile_moments.test.ts
 * re-derives every entry from the committed Case Files.
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..');
const [OUT, ...IDS] = process.argv.slice(2);
if (!OUT || !IDS.length) throw new Error('usage: node tools/casefile_moments.mjs OUT.json ID...');

const server = await createServer({ root: WEB, server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' });
try {
  const { parseConverted } = await server.ssrLoadModule('/src/arena/replay.ts');
  const { findMoments, DIVERGENCE_M } = await server.ssrLoadModule('/src/arena/moments.ts');
  const { create } = await import('@bufbuild/protobuf');
  const { WorldGridSchema } = await server.ssrLoadModule('/src/schemas/gen/coco/world/v1/world_pb.ts');
  // the viewer is handed a map; finding moments does not read it
  const grid = create(WorldGridSchema, { mapId: 'moments', width: 1, height: 1, resolution: 1,
    occupancy: new Uint8Array(1), blocked: new Uint8Array(1) });
  const out = { what: 'Moments in Case Files: where the stack\'s belief first leaves the truth, and where it gives up',
    rule: 'lab_web/src/arena/moments.ts', divergence_m: DIVERGENCE_M, tool: 'lab_web/tools/casefile_moments.mjs', casefiles: {} };
  for (const id of IDS) {
    const rec = await parseConverted(new Uint8Array(readFileSync(join(WEB, 'casefiles', `${id}.mcap`))), grid);
    out.casefiles[id] = findMoments(rec);
    console.log(id, JSON.stringify(out.casefiles[id]));
  }
  writeFileSync(OUT, JSON.stringify(out, null, 1) + '\n');
} finally {
  await server.close();
}
