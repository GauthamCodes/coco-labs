// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena's runtime assets, written into public/generated/ before every
 * build (M1.5; `npm run build` runs this first):
 *
 *   arena/coco_lab.zip      coco_lab's sources (stdlib only), unpacked into
 *                           Pyodide's file system: no wheel, no micropip
 *   arena/coco_arena_v1.json  the World Spec's canonical bytes (worlds/)
 *   arena/manifest.json     sha256 of each, the Pyodide version, sizes
 *   pyodide/                Pyodide itself, SELF-HOSTED from the pinned npm
 *                           package (same origin: no CDN connection), with
 *                           python_stdlib.zip trimmed to what the Arena uses
 *                           (tools/arena_stdlib.txt; see docs/v2/COLDSTART.md)
 *
 * Deterministic: files in sorted order, fixed zip timestamps, so two builds
 * give identical bytes (CI builds twice and compares).
 *
 *   node tools/build_arena_assets.mjs [--full-stdlib]
 */

import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateRawSync, inflateRawSync } from 'node:zlib';

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..');
const repo = join(web, '..');
const out = join(web, 'public', 'generated');
const FULL_STDLIB = process.argv.includes('--full-stdlib');
const PYODIDE = join(web, 'node_modules', 'pyodide');
const PYODIDE_FILES = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'pyodide-lock.json'];

const sha256 = (b) => createHash('sha256').update(b).digest('hex');

// -- a minimal, deterministic zip writer (deflate, fixed 1980-01-01 times) --
const CRC_TABLE = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
export function zip(entries) {
  const parts = [];
  const central = [];
  let offset = 0;
  const DOS_TIME = 0;
  const DOS_DATE = (0 << 9) | (1 << 5) | 1; // 1980-01-01
  for (const [name, data] of entries) {
    const nameBuf = Buffer.from(name, 'utf-8');
    const comp = deflateRawSync(data, { level: 9 });
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(0x0800, 6);
    local.writeUInt16LE(8, 8); local.writeUInt16LE(DOS_TIME, 10); local.writeUInt16LE(DOS_DATE, 12);
    local.writeUInt32LE(crc, 14); local.writeUInt32LE(comp.length, 18); local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26); local.writeUInt16LE(0, 28);
    parts.push(local, nameBuf, comp);
    const c = Buffer.alloc(46);
    c.writeUInt32LE(0x02014b50, 0); c.writeUInt16LE(20, 4); c.writeUInt16LE(20, 6); c.writeUInt16LE(0x0800, 8);
    c.writeUInt16LE(8, 10); c.writeUInt16LE(DOS_TIME, 12); c.writeUInt16LE(DOS_DATE, 14);
    c.writeUInt32LE(crc, 16); c.writeUInt32LE(comp.length, 20); c.writeUInt32LE(data.length, 24);
    c.writeUInt16LE(nameBuf.length, 28); c.writeUInt32LE(offset, 42);
    central.push(c, nameBuf);
    offset += 30 + nameBuf.length + comp.length;
  }
  const cd = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(cd.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...parts, cd, end]);
}

function walk(dir) {
  return readdirSync(dir).sort().flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? (n === '__pycache__' ? [] : walk(p)) : [p];
  });
}

/** The stdlib, trimmed to the modules tools/arena_stdlib.txt lists. */
export function trimmedStdlib(fullZip, keepList) {
  // read the full zip's central directory, keep the listed entries' bytes
  const buf = fullZip;
  const eocd = buf.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const n = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  const keep = keepList.map((k) => k.trim()).filter((k) => k && !k.startsWith('#'));
  const wanted = (name) => keep.some((k) => (k.endsWith('/') ? name.startsWith(k) : name === k));
  const entries = [];
  for (let i = 0; i < n; i += 1) {
    const method = buf.readUInt16LE(p + 10);
    const csize = buf.readUInt32LE(p + 20);
    const nlen = buf.readUInt16LE(p + 28);
    const xlen = buf.readUInt16LE(p + 30);
    const clen = buf.readUInt16LE(p + 32);
    const lho = buf.readUInt32LE(p + 42);
    const name = buf.subarray(p + 46, p + 46 + nlen).toString('utf-8');
    p += 46 + nlen + xlen + clen;
    if (name.endsWith('/') || !wanted(name)) continue;
    const lnlen = buf.readUInt16LE(lho + 26);
    const lxlen = buf.readUInt16LE(lho + 28);
    const data = buf.subarray(lho + 30 + lnlen + lxlen, lho + 30 + lnlen + lxlen + csize);
    entries.push([name, method === 8 ? inflateRawSync(data) : Buffer.from(data)]);
  }
  entries.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return { zip: zip(entries), files: entries.length };
}

/**
 * COCO's top-down silhouette, from the Gazebo chassis mesh (M1.6).
 *
 * gazebo_models/meshes/base.stl is in millimetres (xacro mesh_scale 0.001)
 * with Y up: its X spans the chassis length (240 mm) and Z its width
 * (274 mm). The chassis collision box (coco_robo2.xacro, chassis_collision)
 * is centred at mesh (-120, *, -80) mm, and coco_config's CHASSIS_FRONT_X
 * = 0.120 puts that centre on base_link. So the outline in base_link metres
 * is the convex hull of the mesh's (x, z) points, shifted by (+120, +80) mm.
 * The hull is symmetric front/back and left/right, so no sign is assumed.
 */
export function robotOutline(stl) {
  const n = stl.readUInt32LE(80);
  const pts = new Map();
  for (let i = 0; i < n; i += 1) {
    for (let k = 0; k < 3; k += 1) {
      const o = 84 + 50 * i + 12 + 12 * k;
      const x = Math.round(stl.readFloatLE(o) * 10) / 10;
      const z = Math.round(stl.readFloatLE(o + 8) * 10) / 10;
      pts.set(`${x},${z}`, [x, z]);
    }
  }
  const p = [...pts.values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const half = (list) => {
    const h = [];
    for (const q of list) {
      while (h.length >= 2 && cross(h[h.length - 2], h[h.length - 1], q) <= 0) h.pop();
      h.push(q);
    }
    return h.slice(0, -1);
  };
  const hull = [...half(p), ...half([...p].reverse())];
  return hull.map(([x, z]) => [Math.round((x + 120) * 10) / 10000, Math.round((z + 80) * 10) / 10000]);
}

function main() {
  // arena
  const arenaDir = join(out, 'arena');
  rmSync(arenaDir, { recursive: true, force: true });
  mkdirSync(arenaDir, { recursive: true });
  const src = join(repo, 'coco_lab', 'coco_lab');
  const entries = walk(src).filter((f) => f.endsWith('.py'))
    .map((f) => [`coco_lab/${relative(src, f)}`, readFileSync(f)]);
  const cocoZip = zip(entries);
  writeFileSync(join(arenaDir, 'coco_lab.zip'), cocoZip);
  const spec = readFileSync(join(repo, 'worlds', 'coco_arena_v1.json'));
  writeFileSync(join(arenaDir, 'coco_arena_v1.json'), spec);
  const outline = robotOutline(readFileSync(join(repo, 'gazebo_models', 'meshes', 'base.stl')));
  writeFileSync(join(arenaDir, 'robot_outline.json'), JSON.stringify({
    source: 'gazebo_models/meshes/base.stl (convex hull of x-z, mm -> base_link m; build_arena_assets.mjs)',
    frame: 'base_link, x forward, metres', polygon: outline,
  }) + '\n');

  // pyodide, self-hosted
  const pyDir = join(out, 'pyodide');
  rmSync(pyDir, { recursive: true, force: true });
  mkdirSync(pyDir, { recursive: true });
  const pyodideVersion = JSON.parse(readFileSync(join(PYODIDE, 'package.json'), 'utf-8')).version;
  const files = {};
  for (const f of PYODIDE_FILES) {
    copyFileSync(join(PYODIDE, f), join(pyDir, f));
    files[f] = { bytes: statSync(join(pyDir, f)).size, sha256: sha256(readFileSync(join(pyDir, f))) };
  }
  const fullStd = readFileSync(join(PYODIDE, 'python_stdlib.zip'));
  let std;
  let stdFiles;
  if (FULL_STDLIB) {
    std = fullStd;
    stdFiles = 'all';
  } else {
    const t = trimmedStdlib(fullStd, readFileSync(join(here, 'arena_stdlib.txt'), 'utf-8').split('\n'));
    std = t.zip;
    stdFiles = t.files;
  }
  writeFileSync(join(pyDir, 'python_stdlib.zip'), std);
  files['python_stdlib.zip'] = { bytes: std.length, sha256: sha256(std), entries: stdFiles,
    full_bytes: fullStd.length };

  const manifest = {
    pyodide: pyodideVersion,
    coco_lab_zip: { bytes: cocoZip.length, sha256: sha256(cocoZip), files: entries.length },
    spec: { file: 'coco_arena_v1.json', bytes: spec.length, sha256: sha256(spec) },
    pyodide_files: files,
    stdlib: FULL_STDLIB ? 'full' : 'trimmed (tools/arena_stdlib.txt)',
  };
  writeFileSync(join(arenaDir, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n');
  console.log(`arena assets: coco_lab.zip ${cocoZip.length} B (${entries.length} files), stdlib ${std.length} B ` +
    `(${stdFiles} entries, full ${fullStd.length} B), pyodide ${pyodideVersion}`);
}

main();
