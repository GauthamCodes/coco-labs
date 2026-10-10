// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Write docs/v2/data/m2/m27/p05_matrix.mcap (M2.7): Lab 4's 16 searches
 * recorded on the full stack, converted to a v2 run by src/convert/lab4.ts
 * -- uncompressed, so coco_schemas' Python test can read it without zstd.
 * The conversion is checked lossless (v1 decoder, content hash) before
 * anything is written; test/convert_lab4.test.ts requires this exact file.
 *
 *   node tools/make_v2_search.mjs
 */

import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const web = join(dirname(fileURLToPath(import.meta.url)), '..');
const repo = join(web, '..');
const SRC = join(repo, 'docs', 'data', 'lab4', 'replay', 'p05_matrix');
const OUT = join(repo, 'docs', 'v2', 'data', 'm2', 'm27');

const server = await createServer({ root: web, logLevel: 'error', server: { middlewareMode: true }, appType: 'custom' });
try {
  const { fromLab4, toLab4 } = await server.ssrLoadModule('/src/convert/lab4.ts');
  const { loadSearchBytes } = await server.ssrLoadModule('/src/search/decode.ts');
  const { readRun, writeRun } = await server.ssrLoadModule('/src/schemas/mcap.ts');
  const manifest = new Uint8Array(readFileSync(join(SRC, 'manifest.json')));
  const bundle = await loadSearchBytes(manifest, new Uint8Array(readFileSync(join(SRC, 'arrays.bin.gz'))));
  const conv = await fromLab4(bundle, manifest);
  const bytes = await writeRun(conv.manifest, conv.records);
  const run = await readRun(bytes);
  const back = await toLab4(run.manifest, run.messages);
  if (back.contentHash !== bundle.contentHash) throw new Error('the conversion is not lossless');
  mkdirSync(OUT, { recursive: true });
  writeFileSync(join(OUT, 'p05_matrix.mcap'), bytes);
  console.log(`p05_matrix.mcap: ${bytes.length} B, ${run.messages.length} messages, ${bundle.runs.length} searches, round trip exact, sha256 ${createHash('sha256').update(bytes).digest('hex')}`);
} finally {
  await server.close();
}
