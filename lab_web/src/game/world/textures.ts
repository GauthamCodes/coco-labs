// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.5: procedural textures, generated on the device from a seed (nothing is
 * downloaded; integrity rule 8: own work). Presentation only.
 */

import * as THREE from 'three';
import { variety, type Paint, type WorldLook } from './describe';

const canvas = (w: number, h: number) => {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return [c, c.getContext('2d')!] as const;
};

/** Value noise, tiling, in [0, 1]: `octaves` layers on a `size` square. */
function tilingNoise(size: number, seed: number, octaves = 4): Float32Array {
  const rnd = variety(seed);
  const out = new Float32Array(size * size);
  let amp = 1, total = 0;
  for (let o = 0; o < octaves; o++) {
    const cells = 4 << o;
    const grid = new Float32Array(cells * cells).map(() => rnd());
    const g = (i: number, j: number) => grid[((j % cells) + cells) % cells * cells + (((i % cells) + cells) % cells)];
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const fx = (x / size) * cells, fy = (y / size) * cells;
      const i = Math.floor(fx), j = Math.floor(fy), u = fx - i, v = fy - j;
      const su = u * u * (3 - 2 * u), sv = v * v * (3 - 2 * v);
      const n = (g(i, j) * (1 - su) + g(i + 1, j) * su) * (1 - sv) + (g(i, j + 1) * (1 - su) + g(i + 1, j + 1) * su) * sv;
      out[y * size + x] += n * amp;
    }
    total += amp; amp *= 0.5;
  }
  for (let k = 0; k < out.length; k++) out[k] /= total;
  return out;
}

const texture = (c: HTMLCanvasElement, srgb = true, repeat = true) => {
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  return t;
};

/** Polished concrete roughness detail (tiles every 4 m). */
export function concreteRoughness(seed = 7): THREE.Texture {
  const size = 256;
  const n = tilingNoise(size, seed, 5);
  const [c, g] = canvas(size, size);
  const img = g.createImageData(size, size);
  for (let k = 0; k < n.length; k++) {
    const v = Math.round(255 * (0.35 + 0.45 * n[k]));
    img.data.set([v, v, v, 255], k * 4);
  }
  g.putImageData(img, 0, 0);
  return texture(c, false);
}

/** A material's surface pattern, tiled in world metres by build3d's world-space mapping. */
export function surface(kind: 'panel' | 'fence' | 'office' | 'rollup' | 'mesh' | 'ramp' | 'deck' | 'labpanel' | 'wrap' | 'carton' | 'crate' | 'wood' | 'exit', seed = 1): THREE.Texture {
  const size = 256;
  const [c, g] = canvas(size, size);
  const n = tilingNoise(size, seed, 3);
  const base = (r: number, gg: number, b: number, k = 18) => {
    const img = g.createImageData(size, size);
    for (let i = 0; i < n.length; i++) {
      const d = (n[i] - 0.5) * k;
      img.data.set([r + d, gg + d, b + d, 255], i * 4);
    }
    g.putImageData(img, 0, 0);
  };
  switch (kind) {
    case 'panel': // 2 m modular panels, ribbed
      base(52, 60, 74, 10);
      g.fillStyle = 'rgba(0,0,0,0.35)';
      for (let x = 0; x < size; x += size / 8) g.fillRect(x, 0, 2, size);
      g.fillStyle = 'rgba(0,0,0,0.6)'; g.fillRect(0, 0, 3, size); g.fillRect(0, 0, size, 3);
      break;
    case 'office':
      base(70, 76, 88, 8);
      g.fillStyle = 'rgba(0,0,0,0.25)'; g.fillRect(0, 0, 2, size);
      break;
    case 'labpanel':
      base(196, 201, 208, 8);
      g.fillStyle = 'rgba(40,50,64,0.35)'; g.fillRect(0, 0, 2, size); g.fillRect(0, 0, size, 2);
      break;
    case 'fence': // chain-link over a dark backing (solid in the model, so it is backed)
      base(34, 40, 50, 6);
      g.strokeStyle = 'rgba(150,162,180,0.75)'; g.lineWidth = 1.5;
      for (let k = -size; k < size * 2; k += 16) {
        g.beginPath(); g.moveTo(k, 0); g.lineTo(k + size, size); g.stroke();
        g.beginPath(); g.moveTo(k, size); g.lineTo(k + size, 0); g.stroke();
      }
      g.fillStyle = 'rgba(160,170,186,0.9)'; g.fillRect(0, 0, size, 5); g.fillRect(0, 0, 5, size);
      break;
    case 'mesh':
      base(40, 46, 58, 6);
      g.strokeStyle = 'rgba(170,180,195,0.6)'; g.lineWidth = 1;
      for (let k = 0; k < size; k += 12) { g.beginPath(); g.moveTo(k, 0); g.lineTo(k, size); g.stroke(); g.beginPath(); g.moveTo(0, k); g.lineTo(size, k); g.stroke(); }
      break;
    case 'rollup':
      base(88, 96, 108, 6);
      g.fillStyle = 'rgba(0,0,0,0.35)';
      for (let y = 0; y < size; y += 12) g.fillRect(0, y, size, 3);
      break;
    case 'ramp': { // chevrons along the climb
      base(58, 62, 70, 10);
      g.fillStyle = '#FACC15';
      for (let y = 0; y < size; y += size / 2) {
        g.beginPath(); g.moveTo(size * 0.2, y + size * 0.35); g.lineTo(size * 0.5, y + size * 0.1); g.lineTo(size * 0.8, y + size * 0.35);
        g.lineTo(size * 0.8, y + size * 0.45); g.lineTo(size * 0.5, y + size * 0.2); g.lineTo(size * 0.2, y + size * 0.45); g.fill();
      }
      break;
    }
    case 'deck':
      base(64, 70, 80, 14);
      g.fillStyle = 'rgba(0,0,0,0.3)';
      for (let k = 0; k < size; k += 16) { g.fillRect(k, 0, 1, size); g.fillRect(0, k, size, 1); }
      break;
    case 'wrap':
      base(190, 198, 206, 26);
      g.fillStyle = 'rgba(255,255,255,0.18)';
      for (let y = 0; y < size; y += 22) g.fillRect(0, y, size, 6);
      break;
    case 'carton':
      base(200, 200, 200, 22);
      g.fillStyle = 'rgba(120,90,40,0.5)'; g.fillRect(size * 0.46, 0, size * 0.08, size);
      break;
    case 'crate':
      base(120, 84, 52, 30);
      g.fillStyle = 'rgba(0,0,0,0.35)';
      for (let y = 0; y < size; y += size / 4) g.fillRect(0, y, size, 3);
      g.lineWidth = 8; g.strokeStyle = 'rgba(70,46,24,0.8)'; g.strokeRect(4, 4, size - 8, size - 8);
      break;
    case 'wood':
      base(132, 98, 62, 34);
      g.fillStyle = 'rgba(0,0,0,0.4)';
      for (let x = 0; x < size; x += size / 5) g.fillRect(x, 0, 6, size);
      break;
    case 'exit':
      g.fillStyle = '#0b2a1c'; g.fillRect(0, 0, size, size);
      g.fillStyle = '#7dffbf'; g.font = `bold ${size * 0.42}px "Chakra Petch", sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText('EXIT', size / 2, size / 2);
      break;
  }
  return texture(c, true);
}

/**
 * The floor: concrete (depot) or a light lab floor, with every paint decal drawn
 * into it. `pxPerM` is the tier's resolution. Row 0 is the floor's +y edge.
 */
export function floorTexture(look: WorldLook, pxPerM: number): THREE.Texture {
  const f = look.floor;
  const W = Math.min(4096, Math.round((f.maxX - f.minX) * pxPerM)), H = Math.min(4096, Math.round((f.maxY - f.minY) * pxPerM));
  const sx = W / (f.maxX - f.minX), sy = H / (f.maxY - f.minY);
  const [c, g] = canvas(W, H);
  const lab = look.theme === 'lab';
  // base: tiled noise slabs (4 m), with saw-cut joints
  const tile = 128, n = tilingNoise(tile, 11, 4);
  const [tc, tg] = canvas(tile, tile);
  const img = tg.createImageData(tile, tile);
  for (let k = 0; k < n.length; k++) {
    const v = lab ? 168 + (n[k] - 0.5) * 22 : 46 + (n[k] - 0.5) * 30;
    img.data.set(lab ? [v - 4, v, v + 6, 255] : [v, v + 3, v + 9, 255], k * 4);
  }
  tg.putImageData(img, 0, 0);
  const pat = g.createPattern(tc, 'repeat')!;
  pat.setTransform(new DOMMatrix().scale((4 * sx) / tile, (4 * sy) / tile));
  g.fillStyle = pat; g.fillRect(0, 0, W, H);
  g.strokeStyle = lab ? 'rgba(80,90,104,0.25)' : 'rgba(0,0,0,0.35)'; g.lineWidth = Math.max(1, 0.012 * sx);
  for (let x = Math.ceil(f.minX / 4) * 4; x < f.maxX; x += 4) { g.beginPath(); g.moveTo((x - f.minX) * sx, 0); g.lineTo((x - f.minX) * sx, H); g.stroke(); }
  for (let y = Math.ceil(f.minY / 4) * 4; y < f.maxY; y += 4) { g.beginPath(); g.moveTo(0, (f.maxY - y) * sy); g.lineTo(W, (f.maxY - y) * sy); g.stroke(); }
  const X = (x: number) => (x - f.minX) * sx, Y = (y: number) => (f.maxY - y) * sy;
  const draw = (p: Paint) => {
    switch (p.kind) {
      case 'grid':
        g.strokeStyle = p.color; g.lineWidth = Math.max(1, p.width * sx);
        for (let x = Math.ceil(f.minX / p.step) * p.step; x < f.maxX; x += p.step) { g.beginPath(); g.moveTo(X(x), 0); g.lineTo(X(x), H); g.stroke(); }
        for (let y = Math.ceil(f.minY / p.step) * p.step; y < f.maxY; y += p.step) { g.beginPath(); g.moveTo(0, Y(y)); g.lineTo(W, Y(y)); g.stroke(); }
        break;
      case 'line':
        g.strokeStyle = p.color; g.lineWidth = p.width * sx; g.setLineDash(p.dash ? [p.dash * sx, p.dash * sx * 0.6] : []);
        g.beginPath(); g.moveTo(X(p.from[0]), Y(p.from[1])); g.lineTo(X(p.to[0]), Y(p.to[1])); g.stroke(); g.setLineDash([]);
        break;
      case 'rect':
        g.strokeStyle = p.color; g.lineWidth = p.width * sx; g.setLineDash(p.dash ? [p.dash * sx, p.dash * sx * 0.5] : []);
        g.strokeRect(X(p.min[0]), Y(p.max[1]), (p.max[0] - p.min[0]) * sx, (p.max[1] - p.min[1]) * sy); g.setLineDash([]);
        break;
      case 'hazard': {
        g.save();
        g.beginPath(); g.rect(X(p.min[0]), Y(p.max[1]), (p.max[0] - p.min[0]) * sx, (p.max[1] - p.min[1]) * sy); g.clip();
        g.fillStyle = 'rgba(17,17,17,0.85)'; g.fillRect(X(p.min[0]), Y(p.max[1]), (p.max[0] - p.min[0]) * sx, (p.max[1] - p.min[1]) * sy);
        g.fillStyle = 'rgba(250,204,21,0.82)';
        const s = 0.3 * sx, span = (p.max[0] - p.min[0]) * sx + (p.max[1] - p.min[1]) * sy;
        for (let k = -span; k < span; k += 2 * s) {
          g.beginPath(); g.moveTo(X(p.min[0]) + k, Y(p.min[1])); g.lineTo(X(p.min[0]) + k + s, Y(p.min[1]));
          g.lineTo(X(p.min[0]) + k + s + span, Y(p.min[1]) - span); g.lineTo(X(p.min[0]) + k + span, Y(p.min[1]) - span); g.fill();
        }
        g.restore();
        break;
      }
      case 'label':
        g.save(); g.translate(X(p.at[0]), Y(p.at[1])); if (p.rot) g.rotate(p.rot);
        g.fillStyle = p.color; g.font = `700 ${p.size * sy}px "Chakra Petch", sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(p.text, 0, 0); g.restore();
        break;
      case 'cal': {
        g.strokeStyle = p.color; g.lineWidth = Math.max(1, 0.02 * sx);
        const r = p.size * sx;
        g.beginPath(); g.arc(X(p.at[0]), Y(p.at[1]), r * 0.6, 0, Math.PI * 2); g.stroke();
        g.beginPath(); g.moveTo(X(p.at[0]) - r, Y(p.at[1])); g.lineTo(X(p.at[0]) + r, Y(p.at[1]));
        g.moveTo(X(p.at[0]), Y(p.at[1]) - r); g.lineTo(X(p.at[0]), Y(p.at[1]) + r); g.stroke();
        break;
      }
    }
  };
  for (const p of look.paint) draw(p);
  const t = texture(c, true, false);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  return t;
}
