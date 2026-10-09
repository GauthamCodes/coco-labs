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

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
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
  // M2.7: Lab 5's drives, one v2 run per controller run, drawn on the map the stack localised against
  const { fromLab5Drive, toLab5Drive } = await server.ssrLoadModule('/src/convert/lab5.ts');
  const { loadDriveBytes } = await server.ssrLoadModule('/src/move/decode.ts');
  const { create } = await import('@bufbuild/protobuf');
  const { WorldGridSchema } = await server.ssrLoadModule('/src/schemas/gen/coco/world/v1/world_pb.ts');
  const navDir = join(GEN, 'bundles', 'arena_native');
  const navManifest = new Uint8Array(readFileSync(join(navDir, 'manifest.json')));
  const nav = await loadBundleBytes(navManifest, new Uint8Array(readFileSync(join(navDir, arraysFileName(parseManifest(navManifest).compression)))));
  const navGrid = create(WorldGridSchema, { mapId: nav.map.id, width: nav.map.width, height: nav.map.height,
    resolution: nav.map.geo.resolution, originX: nav.map.geo.origin[0], originY: nav.map.geo.origin[1],
    blocked: nav.map.occupancy.map((v) => (v === 0 ? 0 : 1)), occupancy: nav.map.occupancy, cost: [], specSha256: '', row0IsBottom: false });
  const driveDir = join(GEN, 'move', 'drive');
  for (const sc of readdirSync(driveDir).sort()) {
    const manifest = new Uint8Array(readFileSync(join(driveDir, sc, 'manifest.json')));
    const bundle = await loadDriveBytes(manifest, new Uint8Array(readFileSync(join(driveDir, sc, 'arrays.bin.gz'))));
    const conv = await fromLab5Drive(bundle, manifest, navGrid);
    const written = [];
    for (const c of conv) written.push([c, await writeRun(c.manifest, c.records, (d) => new Uint8Array(zstdCompressSync(d)))]);
    const back = await toLab5Drive(await Promise.all(written.map(([, bytes]) => readRun(bytes))));
    if (back.contentHash !== bundle.contentHash) throw new Error(`lab5 ${sc}: the conversion is not lossless`);
    for (const [c, bytes] of written) {
      const id = `lab5_${sc}_${c.id.toLowerCase()}`; // the viewer accepts [a-z0-9_] ids
      const r = bundle.runs.find((x) => x.id === c.id);
      writeFileSync(join(OUT, `${id}.mcap`), bytes);
      index.push({ id, title: `Lab 5 · ${sc} · ${r.controller} ${c.id} (${r.outcome})`, group: 'Lab 5', evidence: 'STACK',
        algorithm: r.controller, events: 0, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex'),
        run_id: c.manifest.runId, from_bundle: bundle.contentHash, citation: 'docs/labs/LAB5_MOVE.md' });
    }
    console.log(`lab5 ${sc}: ${conv.length} runs, round trip exact`);
  }
  writeFileSync(join(OUT, 'index.json'), JSON.stringify({ schema: 'lab_web.v2_runs', version: '1.0', runs: index }, null, 1) + '\n');
  // a Learn mission (M2.8) may link only to a run this index holds (build_catalog.py wrote missions.json)
  const ids = new Set(index.map((x) => x.id));
  const missions = JSON.parse(readFileSync(join(GEN, 'missions.json'), 'utf-8')).missions;
  for (const m of missions) for (const b of m.beats) {
    if (b.arena?.replay && !ids.has(b.arena.replay)) throw new Error(`mission ${m.id} beat ${b.beat}: no recorded run "${b.arena.replay}"`);
  }
  console.log(`missions: ${missions.length}, every replay link names a run here`);
} finally {
  await server.close();
}
