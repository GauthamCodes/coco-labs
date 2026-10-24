// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.5: bake each world's floor light map at build time (zero runtime cost).
 *
 *   node tools/g1/bake_worlds.mjs [--check]
 *
 * For every world the game draws (the Depot, World Spec v3; the Proving
 * Ground, World Spec v1 and v2), the look is described from the World Spec
 * alone (src/game/world/describe.ts, run here by Node as TypeScript) and the
 * floor's light is baked into a small PNG at 0.1 m per texel:
 *
 * - ambient occlusion: darker toward every collision footprint, and under it;
 * - light pools: soft warm pools under the overhead fixtures, a cool spill at
 *   each dock lamp.
 *
 * The bake refuses a dishonest look (describe.honestyViolations). It is
 * deterministic: same spec bytes, same PNG bytes (no timestamps, fixed zlib
 * level). Output: public/generated/g1/<world>.light.png and
 * public/generated/g1/manifest.json (sha256 and sizes); presentation only,
 * never read by the model.
 */
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateSync } from 'node:zlib';
import { describe, honestyViolations } from '../../src/game/world/describe.ts';

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..', '..');
const repo = join(web, '..');
const out = join(web, 'public', 'generated', 'g1');
export const WORLDS = { depot: 'coco_depot_v1.json', proving_v1: 'coco_arena_v1.json', proving_v2: 'coco_arena_v2.json',
  // owner request 2026-10-24: Fetch by colour's level (the Depot plus four rods)
  depot_colours: 'coco_depot_colours_v1.json' };
export const TEXEL = 0.1;

const sha256 = (b) => createHash('sha256').update(b).digest('hex');
const CRC = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc32 = (buf) => { let c = 0xffffffff; for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
/** A plain RGB8 PNG. */
export function png(width, height, rgb) {
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (width * 3 + 1)] = 0;
    rgb.copy ? rgb.copy(raw, y * (width * 3 + 1) + 1, y * width * 3, (y + 1) * width * 3)
      : raw.set(rgb.subarray(y * width * 3, (y + 1) * width * 3), y * (width * 3 + 1) + 1);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw, { level: 9 })), chunk('IEND', Buffer.alloc(0))]);
}

const POOL = { strip: { sigma: 1.45, gain: 0.8, rgb: [1.0, 0.8, 0.55] }, dock: { sigma: 2.2, gain: 0.65, rgb: [0.62, 0.78, 1.0] }, lamp: { sigma: 1.7, gain: 0.5, rgb: [1.0, 0.95, 0.88] } };
const AMBIENT = { depot: [0.2, 0.24, 0.32], lab: [0.62, 0.64, 0.68] };

/** Bake one look: [width, height, rgb bytes]; texel (i, j) covers floor.minX + i*TEXEL, floor.maxY - j*TEXEL (row 0 at the far +y edge). */
export function bake(look) {
  const f = look.floor;
  const w = Math.round((f.maxX - f.minX) / TEXEL), h = Math.round((f.maxY - f.minY) / TEXEL);
  const rects = look.footprints.filter((p) => p.kind === 'box' && p.top > 0.05);
  const amb = AMBIENT[look.theme];
  const rgb = Buffer.alloc(w * h * 3);
  for (let j = 0; j < h; j++) {
    const y = f.maxY - (j + 0.5) * TEXEL;
    for (let i = 0; i < w; i++) {
      const x = f.minX + (i + 0.5) * TEXEL;
      let d = Infinity;
      for (const r of rects) {
        const ddx = Math.max(r.min[0] - x, 0, x - r.max[0]), ddy = Math.max(r.min[1] - y, 0, y - r.max[1]);
        const dd = Math.hypot(ddx, ddy);
        if (dd < d) d = dd;
      }
      const ao = d === 0 ? 0.3 : 1 - 0.55 * Math.exp(-d / 0.35);
      const c = [amb[0] * ao, amb[1] * ao, amb[2] * ao];
      for (const fx of look.fixtures) {
        const p = POOL[fx.kind];
        const r2 = (x - fx.x) ** 2 + (y - fx.y) ** 2;
        if (r2 > 9 * p.sigma * p.sigma) continue;
        const k = p.gain * Math.exp(-r2 / (2 * p.sigma * p.sigma)) * (0.55 + 0.45 * ao);
        c[0] += k * p.rgb[0]; c[1] += k * p.rgb[1]; c[2] += k * p.rgb[2];
      }
      // stored at half scale: the material reads it with lightMapIntensity 2
      for (let k = 0; k < 3; k++) rgb[(j * w + i) * 3 + k] = Math.max(0, Math.min(255, Math.round((c[k] / 2) * 255)));
    }
  }
  return [w, h, rgb];
}

export function bakeAll() {
  const files = {};
  const worlds = {};
  for (const [name, file] of Object.entries(WORLDS)) {
    const specBytes = readFileSync(join(repo, 'worlds', file));
    const look = describe(JSON.parse(specBytes.toString('utf-8')));
    const bad = honestyViolations(look);
    if (bad.length) throw new Error(`${name}: decorative honesty: ${bad.slice(0, 5).join('; ')}`);
    const [w, h, rgb] = bake(look);
    const bytes = png(w, h, rgb);
    files[`${name}.light.png`] = bytes;
    worlds[name] = { spec: file, spec_sha256: sha256(specBytes), light: `${name}.light.png`, light_sha256: sha256(bytes), light_bytes: bytes.length,
      texel: TEXEL, size: [w, h], floor: look.floor, parts: look.parts.length };
  }
  // G1.6: Fetch Rush's reference cards (docs/v2/m6/data/games_reference.json), for coco_lab.games.stars in the worker
  const ref = JSON.parse(readFileSync(join(repo, 'docs', 'v2', 'm6', 'data', 'games_reference.json'), 'utf-8'));
  const cards = Object.fromEntries(ref.runs.filter((r) => r.record.game === 'fetch_rush').map((r) => [String(r.record.arg), r.result.scorecard]));
  files['references.json'] = Buffer.from(JSON.stringify({ source: 'docs/v2/m6/data/games_reference.json', fetch_rush: cards }) + '\n');
  const manifest = Buffer.from(JSON.stringify({ about: 'G1.5 baked floor light maps (presentation only; tools/g1/bake_worlds.mjs)', worlds,
    references: { file: 'references.json', sha256: sha256(files['references.json']) } }, null, 1) + '\n');
  return { files, manifest };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { files, manifest } = bakeAll();
  if (process.argv.includes('--check')) {
    const now = JSON.parse(readFileSync(join(out, 'manifest.json'), 'utf-8'));
    const want = JSON.parse(manifest.toString());
    if (JSON.stringify(now) !== JSON.stringify(want)) { console.error('g1 bake is stale'); process.exit(1); }
    console.log('g1 bake current');
  } else {
    mkdirSync(out, { recursive: true });
    for (const [name, bytes] of Object.entries(files)) writeFileSync(join(out, name), bytes);
    writeFileSync(join(out, 'manifest.json'), manifest);
    for (const [name, bytes] of Object.entries(files)) console.log(name, bytes.length);
  }
}
