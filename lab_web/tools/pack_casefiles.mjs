// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Pack the converted Case Files for the site (M3.3; ADR 0005):
 *
 *   node tools/pack_casefiles.mjs RAW_DIR      (from lab_web; RAW_DIR = build_casefiles.py's output)
 *
 * Repacks each uncompressed run file with zstd chunks and an index
 * (src/schemas/mcap.ts repackRun: the same messages, byte for byte), writes
 * it to lab_web/casefiles/<id>.mcap, checks it reads back with every message
 * equal, and writes lab_web/casefiles/index.json: id, group, title, bytes,
 * sha256, run id and the source citation of each. Refuses a Case File over
 * the per-file budget or a set over the total budget (ADR 0005).
 */

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync, readdirSync, unlinkSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { zstdCompressSync } from 'node:zlib';
import { createServer } from 'vite';

export const PER_FILE_BUDGET = 20_000_000;
export const TOTAL_BUDGET = 150_000_000;

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(WEB, 'casefiles');
const RAW = process.argv[2];
if (!RAW) throw new Error('usage: node tools/pack_casefiles.mjs RAW_DIR');

const server = await createServer({ root: WEB, server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' });
const { repackRun, readRun, readRawStream } = await server.ssrLoadModule('/src/schemas/mcap.ts');
const build = JSON.parse(readFileSync(join(RAW, 'build.json'), 'utf-8'));
mkdirSync(OUT, { recursive: true });
const keep = new Set(build.cases.map((c) => `${c.id}.mcap`));
for (const f of readdirSync(OUT)) if (f.endsWith('.mcap') && !keep.has(f)) unlinkSync(join(OUT, f));

const entries = [];
let total = 0;
for (const c of build.cases) {
  const raw = new Uint8Array(readFileSync(join(RAW, `${c.id}.mcap`)));
  const packed = await repackRun(raw, (d) => new Uint8Array(zstdCompressSync(d)), 'lab_web/tools/pack_casefiles.mjs');
  // the same messages, byte for byte
  const before = readRawStream(raw).messages;
  const after = (await readRun(packed)).messages;
  if (before.length !== after.length) throw new Error(`${c.id}: ${before.length} messages became ${after.length}`);
  const sorted = [...before].sort((a, b) => (a.logTime < b.logTime ? -1 : a.logTime > b.logTime ? 1 : 0));
  after.forEach((m, i) => {
    if (m.logTime !== sorted[i].logTime || Buffer.compare(Buffer.from(m.data), Buffer.from(sorted[i].data)) !== 0) {
      throw new Error(`${c.id}: message ${i} changed in the repack`);
    }
  });
  if (packed.byteLength > PER_FILE_BUDGET) throw new Error(`${c.id}: ${packed.byteLength} B is over the ${PER_FILE_BUDGET} B budget (ADR 0005)`);
  total += packed.byteLength;
  writeFileSync(join(OUT, `${c.id}.mcap`), packed);
  entries.push({
    id: c.id, group: c.group, title: c.title, case: c.case, bytes: packed.byteLength,
    sha256: createHash('sha256').update(packed).digest('hex'), run_id: c.run_id, messages: after.length,
    bags: c.bags, checksum: c.checksum, window: c.window, log_window_ns: c.log_window_ns,
  });
  console.log(`${c.id}: ${raw.byteLength} -> ${packed.byteLength} B`);
}
if (total > TOTAL_BUDGET) throw new Error(`the Case Files total ${total} B, over the ${TOTAL_BUDGET} B budget (ADR 0005)`);
writeFileSync(join(OUT, 'index.json'), JSON.stringify({
  schema: 'lab_web.casefiles', version: '1.0', adapter: build.adapter, detail: build.detail,
  built_at_commit: build.git_sha, total_bytes: total, budget: { per_file: PER_FILE_BUDGET, total: TOTAL_BUDGET },
  casefiles: entries,
}, null, 1) + '\n');
console.log(JSON.stringify({ casefiles: entries.length, total_bytes: total }));
await server.close();
