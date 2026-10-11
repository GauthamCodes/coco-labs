// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lay the Case Files out so the first frame loads before the scans (M3 review,
 * decision D6; ADR 0005, amendment D6):
 *
 *   node tools/layout_casefiles.mjs [--in DIR] [--out DIR] [--lossless FILE] [--only ID,ID]
 *
 * Rewrites each Case File the index in --in names as one file with its scans after
 * everything else (mcap.ts orderCase), and --out/index.json with its new bytes and
 * sha256 and `layout: "ordered"`. Nothing is re-encoded: every message keeps its bytes,
 * times and sequence. Before writing, the new file's content digest (mcap.ts
 * contentDigest: per channel, every message and the schema) must equal the original's,
 * or the tool stops. --lossless writes those original digests, with each original
 * file's sha256: the record test/casefile_layout.test.ts checks in CI.
 *
 * pack_casefiles.mjs, which packs the adapter's output, lays out its files the same way.
 */

import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { zstdCompressSync } from 'node:zlib';
import { createServer } from 'vite';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const IN = args.in ?? join(WEB, 'casefiles');
const OUT = args.out ?? IN;
const only = args.only ? new Set(args.only.split(',')) : null;
mkdirSync(OUT, { recursive: true });

const server = await createServer({ root: WEB, server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' });
try {
  const m = await server.ssrLoadModule('/src/schemas/mcap.ts');
  const sha = (b) => createHash('sha256').update(b).digest('hex');
  const zstd = (d) => new Uint8Array(zstdCompressSync(d));
  const index = JSON.parse(readFileSync(join(IN, 'index.json'), 'utf-8'));
  const lossless = { schema: 'lab_web.casefiles.lossless', version: '1.0',
    what: "Each Case File's content as M3 committed it (one file each, all messages in log-time order): the "
      + "file's sha256 and bytes, and its contentDigest (lab_web/src/schemas/mcap.ts). The ordered layout "
      + '(ADR 0005, amendment D6) must have exactly these digests.',
    casefiles: {} };
  const out = [];
  let total = 0;
  for (const e of index.casefiles) {
    if (only && !only.has(e.id)) continue;
    const old = new Uint8Array(readFileSync(join(IN, `${e.id}.mcap`)));
    if (sha(old) !== e.sha256) throw new Error(`${e.id}: not the file its index names`);
    const raw = m.readRawStream(old);
    const want = m.contentDigest(raw, sha);
    lossless.casefiles[e.id] = { sha256: e.sha256, bytes: old.byteLength, digest: want };
    const data = await m.orderCase(raw, zstd, Number(args.chunk ?? 1 << 18), 'lab_web/tools/layout_casefiles.mjs');
    if (JSON.stringify(m.contentDigest(m.readRawStream(data), sha)) !== JSON.stringify(want)) {
      throw new Error(`${e.id}: the laid-out file does not hold exactly the original's content`);
    }
    writeFileSync(join(OUT, `${e.id}.mcap`), data);
    total += data.byteLength;
    out.push({ ...e, bytes: data.byteLength, sha256: sha(data) });
    console.log(`${e.id}: ${old.byteLength} -> ${data.byteLength} B`);
  }
  writeFileSync(join(OUT, 'index.json'), JSON.stringify({ ...index, version: '1.1', layout: 'ordered', total_bytes: total, casefiles: out }, null, 1) + '\n');
  if (args.lossless) writeFileSync(args.lossless, JSON.stringify(lossless, null, 1) + '\n');
  console.log(JSON.stringify({ layout: 'ordered', casefiles: out.length, total_bytes: total }));
} finally {
  await server.close();
}
