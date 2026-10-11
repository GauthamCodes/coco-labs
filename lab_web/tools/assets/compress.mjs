// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The 3D assets the site serves, from the converters' sources (M4.2; ADR 0006):
 *
 *   node tools/assets/compress.mjs SRC_DIR OUT_DIR      (from lab_web)
 *
 * SRC_DIR holds robot_src.glb and arena_src.glb (convert_robot.py, convert_world.py).
 * Writes OUT_DIR/robot_high.glb, robot_low.glb and arena.glb:
 *
 * - LEVELS OF DETAIL (README §5.4: about 20k triangles near the camera, well under 5k
 *   for phones and distant views). A level's triangle budget is shared by water-filling:
 *   a mesh under the fair share keeps every triangle; the rest share what is left
 *   equally. Each mesh is simplified to its share by meshoptimizer's simplifier.
 * - NORMALS: smooth across edges flatter than 40°, split at sharper ones (the CAD
 *   meshes' edges stay crisp). The arena's boxes and wedges keep their flat normals.
 * - COMPRESSION: every buffer view is meshopt-encoded (EXT_meshopt_compression, codec
 *   version 0, the extension's), vertices reordered for it; the extension is required,
 *   with a data-less fallback buffer as the extension specifies. three.js decodes it
 *   with its bundled MeshoptDecoder.
 *
 * meshoptimizer is the one dependency (pinned, WebAssembly). The output is a pure
 * function of the sources: the same bytes on every machine (CI regenerates and compares).
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { MeshoptEncoder, MeshoptSimplifier } from 'meshoptimizer';

export const LEVELS = { high: 20000, low: 4500 };
const CREASE_COS = Math.cos((40 * Math.PI) / 180);

export function parseGlb(buf) {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  if (dv.getUint32(0, true) !== 0x46546c67) throw new Error('not a GLB');
  const jlen = dv.getUint32(12, true);
  const json = JSON.parse(new TextDecoder().decode(buf.subarray(20, 20 + jlen)));
  const blen = dv.getUint32(20 + jlen, true);
  return { json, bin: buf.subarray(28 + jlen, 28 + jlen + blen) };
}

function accessorData(glb, i) {
  const a = glb.json.accessors[i];
  const v = glb.json.bufferViews[a.bufferView];
  const n = a.count * { SCALAR: 1, VEC3: 3 }[a.type];
  const bytes = glb.bin.slice(v.byteOffset + (a.byteOffset ?? 0), v.byteOffset + (a.byteOffset ?? 0) + n * 4);
  return a.componentType === 5126 ? new Float32Array(bytes.buffer) : new Uint32Array(bytes.buffer);
}

/** Water-filling: each mesh's share of `budget` triangles. */
export function shares(counts, budget) {
  const sorted = [...counts].sort((a, b) => a - b);
  let left = budget; let n = sorted.length; let cap = Infinity;
  for (const c of sorted) {
    if (c * n <= left) { left -= c; n -= 1; } else { cap = Math.floor(left / n); break; }
  }
  return counts.map((c) => Math.min(c, cap));
}

function compact(indices, positions) {
  const remap = new Int32Array(positions.length / 3).fill(-1);
  const out = [];
  let k = 0;
  const idx = new Uint32Array(indices.length);
  indices.forEach((v, i) => {
    if (remap[v] < 0) { remap[v] = k++; out.push(positions[3 * v], positions[3 * v + 1], positions[3 * v + 2]); }
    idx[i] = remap[v];
  });
  return { indices: idx, positions: new Float32Array(out) };
}

/** Smooth normals, split where faces meet at more than the crease angle. */
function creaseNormals(indices, positions) {
  const nt = indices.length / 3;
  const fn = new Float32Array(nt * 3);
  const acc = new Float64Array(positions.length);
  for (let t = 0; t < nt; t += 1) {
    const [a, b, c] = [indices[3 * t], indices[3 * t + 1], indices[3 * t + 2]];
    const ux = positions[3 * b] - positions[3 * a]; const uy = positions[3 * b + 1] - positions[3 * a + 1]; const uz = positions[3 * b + 2] - positions[3 * a + 2];
    const vx = positions[3 * c] - positions[3 * a]; const vy = positions[3 * c + 1] - positions[3 * a + 1]; const vz = positions[3 * c + 2] - positions[3 * a + 2];
    const nx = uy * vz - uz * vy; const ny = uz * vx - ux * vz; const nz = ux * vy - uy * vx;
    const l = Math.hypot(nx, ny, nz) || 1;
    fn.set([nx / l, ny / l, nz / l], 3 * t);
    for (const v of [a, b, c]) { acc[3 * v] += nx; acc[3 * v + 1] += ny; acc[3 * v + 2] += nz; }
  }
  const pos = []; const nor = []; const idx = new Uint32Array(indices.length);
  const seen = new Map();
  for (let i = 0; i < indices.length; i += 1) {
    const v = indices[i]; const t = Math.floor(i / 3);
    let x = acc[3 * v]; let y = acc[3 * v + 1]; let z = acc[3 * v + 2];
    const l = Math.hypot(x, y, z) || 1; x /= l; y /= l; z /= l;
    if (x * fn[3 * t] + y * fn[3 * t + 1] + z * fn[3 * t + 2] < CREASE_COS) { x = fn[3 * t]; y = fn[3 * t + 1]; z = fn[3 * t + 2]; }
    const key = `${v},${Math.round(x * 1000)},${Math.round(y * 1000)},${Math.round(z * 1000)}`;
    let k = seen.get(key);
    if (k === undefined) {
      k = pos.length / 3; seen.set(key, k);
      pos.push(positions[3 * v], positions[3 * v + 1], positions[3 * v + 2]); nor.push(x, y, z);
    }
    idx[i] = k;
  }
  return { indices: idx, positions: new Float32Array(pos), normals: new Float32Array(nor) };
}

/** Write a GLB whose every buffer view is meshopt-compressed. prims: [{positions, normals, indices}] by mesh. */
function writeCompressed(json, prims) {
  const out = structuredClone(json);
  out.accessors = []; out.bufferViews = [];
  const chunks = []; let clen = 0; let flen = 0;
  const view = (raw, count, stride, mode, target) => {
    const enc = MeshoptEncoder.encodeGltfBuffer(raw, count, stride, mode, 0);
    while (clen % 4) { chunks.push(new Uint8Array(1)); clen += 1; }
    const v = { buffer: 1, byteOffset: flen, byteLength: raw.byteLength, target,
      extensions: { EXT_meshopt_compression: { buffer: 0, byteOffset: clen, byteLength: enc.byteLength, byteStride: stride, count, mode } } };
    if (mode === 'ATTRIBUTES') v.byteStride = stride;
    chunks.push(enc); clen += enc.byteLength;
    flen += raw.byteLength; while (flen % 4) flen += 1;
    out.bufferViews.push(v);
    return out.bufferViews.length - 1;
  };
  out.meshes.forEach((m, mi) => {
    const p = prims[mi];
    // vertex order for the encoder (and the GPU cache)
    const [remap, unique] = MeshoptEncoder.reorderMesh(p.indices, true, false);
    const pos = new Float32Array(unique * 3); const nor = new Float32Array(unique * 3);
    for (let v = 0; v < remap.length; v += 1) {
      const r = remap[v]; if (r === 0xffffffff) continue;
      pos.set(p.positions.subarray(3 * v, 3 * v + 3), 3 * r); nor.set(p.normals.subarray(3 * v, 3 * v + 3), 3 * r);
    }
    const lo = [0, 1, 2].map((k) => Math.min(...pos.filter((_, i) => i % 3 === k)));
    const hi = [0, 1, 2].map((k) => Math.max(...pos.filter((_, i) => i % 3 === k)));
    out.accessors.push({ bufferView: view(new Uint8Array(pos.buffer), unique, 12, 'ATTRIBUTES', 34962), componentType: 5126, count: unique, type: 'VEC3', min: lo, max: hi });
    const pi = out.accessors.length - 1;
    out.accessors.push({ bufferView: view(new Uint8Array(nor.buffer), unique, 12, 'ATTRIBUTES', 34962), componentType: 5126, count: unique, type: 'VEC3' });
    const ni = out.accessors.length - 1;
    const small = unique < 65536;
    const idx = small ? Uint16Array.from(p.indices) : p.indices;
    out.accessors.push({ bufferView: view(new Uint8Array(idx.buffer), idx.length, small ? 2 : 4, 'TRIANGLES', 34963), componentType: small ? 5123 : 5125, count: idx.length, type: 'SCALAR' });
    m.primitives[0].attributes = { POSITION: pi, NORMAL: ni };
    m.primitives[0].indices = out.accessors.length - 1;
  });
  out.buffers = [{ byteLength: clen }, { byteLength: flen, extensions: { EXT_meshopt_compression: { fallback: true } } }];
  out.extensionsUsed = ['EXT_meshopt_compression'];
  out.extensionsRequired = ['EXT_meshopt_compression'];
  const bin = new Uint8Array(clen + ((4 - (clen % 4)) % 4));
  let o = 0; for (const c of chunks) { bin.set(c, o); o += c.byteLength; }
  let js = new TextEncoder().encode(JSON.stringify(out));
  const pad = (4 - (js.byteLength % 4)) % 4;
  if (pad) { const j2 = new Uint8Array(js.byteLength + pad).fill(0x20); j2.set(js); js = j2; }
  const glb = new Uint8Array(12 + 8 + js.byteLength + 8 + bin.byteLength);
  const dv = new DataView(glb.buffer);
  dv.setUint32(0, 0x46546c67, true); dv.setUint32(4, 2, true); dv.setUint32(8, glb.byteLength, true);
  dv.setUint32(12, js.byteLength, true); dv.setUint32(16, 0x4e4f534a, true); glb.set(js, 20);
  dv.setUint32(20 + js.byteLength, bin.byteLength, true); dv.setUint32(24 + js.byteLength, 0x004e4942, true);
  glb.set(bin, 28 + js.byteLength);
  return glb;
}

function triangles(prims) {
  return prims.reduce((n, p) => n + p.indices.length / 3, 0);
}

/** The robot at one level of detail; returns the GLB and a per-mesh report. */
export function robotLevel(src, budget) {
  const meshes = src.json.meshes.map((m) => ({ positions: accessorData(src, m.primitives[0].attributes.POSITION),
    indices: accessorData(src, m.primitives[0].indices) }));
  const share = shares(meshes.map((m) => m.indices.length / 3), budget);
  const report = [];
  const prims = meshes.map((m, i) => {
    let idx = m.indices;
    if (share[i] < idx.length / 3) {
      [idx] = MeshoptSimplifier.simplify(m.indices, m.positions, 3, share[i] * 3, 1.0, []);
      if (idx.length / 3 > share[i]) idx = MeshoptSimplifier.simplifySloppy(m.indices, m.positions, 3, null, share[i] * 3, 1.0)[0];
    }
    const c = compact(idx, m.positions);
    const p = creaseNormals(c.indices, c.positions);
    report.push({ mesh: src.json.meshes[i].name, source_tris: m.indices.length / 3, share: share[i], tris: p.indices.length / 3 });
    return p;
  });
  return { glb: writeCompressed(src.json, prims), triangles: triangles(prims), report };
}

/** The arena: no simplification (964 triangles of boxes and wedges), normals as converted. */
export function arenaAsset(src) {
  const prims = src.json.meshes.map((m) => ({ positions: accessorData(src, m.primitives[0].attributes.POSITION),
    normals: accessorData(src, m.primitives[0].attributes.NORMAL), indices: accessorData(src, m.primitives[0].indices) }));
  return { glb: writeCompressed(src.json, prims), triangles: triangles(prims) };
}

export async function compressAll(srcDir, outDir) {
  await MeshoptEncoder.ready; await MeshoptSimplifier.ready;
  mkdirSync(outDir, { recursive: true });
  const robot = parseGlb(new Uint8Array(readFileSync(join(srcDir, 'robot_src.glb'))));
  const arena = parseGlb(new Uint8Array(readFileSync(join(srcDir, 'arena_src.glb'))));
  const summary = { levels: {} };
  for (const [level, budget] of Object.entries(LEVELS)) {
    const r = robotLevel(robot, budget);
    writeFileSync(join(outDir, `robot_${level}.glb`), r.glb);
    summary.levels[level] = { file: `robot_${level}.glb`, bytes: r.glb.byteLength, triangles: r.triangles, budget, meshes: r.report };
  }
  const a = arenaAsset(arena);
  writeFileSync(join(outDir, 'arena.glb'), a.glb);
  summary.arena = { file: 'arena.glb', bytes: a.glb.byteLength, triangles: a.triangles };
  return summary;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const s = await compressAll(process.argv[2], process.argv[3]);
  writeFileSync(join(process.argv[3], 'robot.json'), JSON.stringify(s.levels, null, 1) + '\n');
  for (const [k, v] of Object.entries(s.levels)) console.log(`robot_${k}.glb: ${v.bytes} B, ${v.triangles} triangles (budget ${v.budget})`);
  console.log(`arena.glb: ${s.arena.bytes} B, ${s.arena.triangles} triangles`);
}
