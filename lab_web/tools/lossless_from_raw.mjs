// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Record what each Case File must hold, from the adapter's own output (M4.7):
 *
 *   node tools/lossless_from_raw.mjs RAW_DIR      (from lab_web; RAW_DIR = build_casefiles.py's output)
 *
 * casefiles/lossless.json is the reference test/casefile_layout.test.ts holds
 * every committed Case File to: per file, the content digest (mcap.ts
 * contentDigest: per channel, every message and the schema) of the file the
 * ADAPTER wrote, with that file's sha256 and bytes. M3 recorded its own files'
 * (version 1.0); M4.7 re-converted every Case File with the recorded 3D truth
 * (z, roll, pitch), so the reference moves to that conversion (version 1.1):
 * the packed, ordered file must still hold exactly what the adapter wrote.
 */

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..');
const RAW = process.argv[2];
if (!RAW) throw new Error('usage: node tools/lossless_from_raw.mjs RAW_DIR');
const sha = (b) => createHash('sha256').update(b).digest('hex');

const server = await createServer({ root: WEB, server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' });
try {
  const m = await server.ssrLoadModule('/src/schemas/mcap.ts');
  const index = JSON.parse(readFileSync(join(WEB, 'casefiles', 'index.json'), 'utf-8'));
  const out = { schema: 'lab_web.casefiles.lossless', version: '1.1',
    what: "Each Case File's content as the adapter wrote it (M4.7: re-converted with the recorded 3D truth; "
      + 'version 1.0 held M3\'s): that file\'s sha256 and bytes, and its contentDigest (lab_web/src/schemas/mcap.ts). '
      + 'The committed, ordered file (ADR 0005, amendment D6) must have exactly these digests.',
    casefiles: {} };
  for (const e of index.casefiles) {
    const raw = new Uint8Array(readFileSync(join(RAW, `${e.id}.mcap`)));
    const want = m.contentDigest(m.readRawStream(raw), sha);
    const packed = m.contentDigest(m.readRawStream(new Uint8Array(readFileSync(join(WEB, 'casefiles', `${e.id}.mcap`)))), sha);
    if (JSON.stringify(packed) !== JSON.stringify(want)) throw new Error(`${e.id}: the packed file does not hold the adapter's content`);
    out.casefiles[e.id] = { sha256: sha(raw), bytes: raw.byteLength, digest: want };
  }
  writeFileSync(join(WEB, 'casefiles', 'lossless.json'), JSON.stringify(out, null, 1) + '\n');
  console.log(`lossless.json: ${Object.keys(out.casefiles).length} Case Files, each packed file holds its adapter content`);
} finally {
  await server.close();
}
