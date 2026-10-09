// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Lens layers keep a texture's own transparency (M2.4: the built map drew unknown as black). */

import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { LensLayers } from '../src/arena/render/lensLayers';
import { PALETTES } from '../src/arena/render/palette';

const mat = (s: THREE.Scene) => {
  const out: THREE.Material[] = [];
  s.traverse((o) => { const m = (o as THREE.Mesh).material; if (m) out.push(m as THREE.Material); });
  return out;
};
const pixels = (s: THREE.Scene) => {
  let data: Uint8Array | null = null;
  s.traverse((o) => { const m = (o as THREE.Mesh).material as THREE.MeshBasicMaterial | undefined; if (m?.map) data = (m.map.image as { data: Uint8Array }).data; });
  return data!;
};

describe('LensLayers.mapTexture', () => {
  it('stays transparent at full opacity, so unknown cells are see-through', () => {
    const s = new THREE.Scene();
    const L = new LensLayers(s, PALETTES.light);
    L.mapTexture('m', 2, 1, 0.1, [0, 0], [0, 2], true);
    expect(mat(s).every((m) => m.transparent)).toBe(true);
    L.setDim('m', 1);
    L.setVisible('m', true);
    expect(mat(s).every((m) => m.transparent)).toBe(true);
    const px = pixels(s);
    expect(px[3]).toBe(0); // unknown: alpha 0
    expect(px[7]).toBeGreaterThan(0); // observed
  });

  it('veils unknown cells with the palette colour when asked', () => {
    const s = new THREE.Scene();
    const L = new LensLayers(s, PALETTES.light);
    L.mapTexture('m', 2, 1, 0.1, [0, 0], [0, -2], true, 0.7);
    const px = pixels(s);
    const unk = new THREE.Color(PALETTES.light.unknown);
    expect([px[0], px[1], px[2], px[3]]).toEqual([Math.round(unk.r * 255), Math.round(unk.g * 255), Math.round(unk.b * 255), Math.round(0.7 * 255)]);
  });

  it('an opaque line layer is not made transparent', () => {
    const s = new THREE.Scene();
    const L = new LensLayers(s, PALETTES.light);
    L.segments('l', [0, 0, 1, 1], 'path', 1);
    expect(mat(s).every((m) => !m.transparent)).toBe(true);
    L.setDim('l', 0.25);
    expect(mat(s).every((m) => m.transparent)).toBe(true);
  });
});
