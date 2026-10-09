// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 1's bundles as v2 runs (M1.9): public/generated/v2/<id>.mcap and
 * v2/index.json, for the Arena viewer (`?view=arena&replay=<id>`).
 *
 * Reads the bundles build_catalog.py wrote (run it first), converts each
 * with src/convert/lab1.ts, and -- before writing anything -- converts it
 * BACK from the written bytes and requires the v1 decoder to accept it with
 * the original content hash. A conversion that loses anything fails the
 * build. The old Lab 1 view keeps reading the v1 bundles.
 *
 *   node tools/build_v2_runs.mjs
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { zstdCompressSync } from 'node:zlib';
import { createServer } from 'vite';

const web = join(dirname(fileURLToPath(import.meta.url)), '..');
const GEN = join(web, 'public', 'generated');
const OUT = join(GEN, 'v2');

const server = await createServer({ root: web, logLevel: 'error', server: { middlewareMode: true }, appType: 'custom' });
try {
  const { fromLab1, toLab1 } = await server.ssrLoadModule('/src/convert/lab1.ts');
  const { loadBundleBytes, arraysFileName } = await server.ssrLoadModule('/src/bundle/load.ts');
  const { parseManifest } = await server.ssrLoadModule('/src/bundle/decode.ts');
  const { readRun, writeRun } = await server.ssrLoadModule('/src/schemas/mcap.ts');
  const catalog = JSON.parse(readFileSync(join(GEN, 'catalog.json'), 'utf-8'));
  mkdirSync(OUT, { recursive: true });
  const index = [];
  for (const e of catalog.bundles) {
    const dir = join(GEN, e.path);
    const manifest = new Uint8Array(readFileSync(join(dir, 'manifest.json')));
    const arrays = new Uint8Array(readFileSync(join(dir, arraysFileName(parseManifest(manifest).compression))));
    const bundle = await loadBundleBytes(manifest, arrays);
    if (bundle.contentHash !== e.content_hash) throw new Error(`${e.id}: the bundle is not the one the catalog lists`);
    const conv = await fromLab1(bundle, manifest);
    const bytes = await writeRun(conv.manifest, conv.records, (d) => new Uint8Array(zstdCompressSync(d)));
    const run = await readRun(bytes);
    const back = await toLab1(run.manifest, run.messages);
    if (back.contentHash !== bundle.contentHash) throw new Error(`${e.id}: the conversion is not lossless`);
    writeFileSync(join(OUT, `${e.id}.mcap`), bytes);
    index.push({ id: e.id, title: e.title, group: e.group, evidence: e.source_kind === 'recorded-run' ? 'STACK' : 'MODEL',
      algorithm: e.algorithm, events: e.events, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex'),
      run_id: run.manifest.runId, from_bundle: bundle.contentHash, citation: e.citation });
    console.log(`${e.id}: ${bytes.length} B, ${run.messages.length} messages, round trip exact`);
  }
  writeFileSync(join(OUT, 'index.json'), JSON.stringify({ schema: 'lab_web.v2_runs', version: '1.0', runs: index }, null, 1) + '\n');
} finally {
  await server.close();
}
