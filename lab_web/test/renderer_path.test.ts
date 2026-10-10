// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** The planned path's line takes every point of every new path (M2.4 fix). */

import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { setLinePoints } from '../src/arena/render/Renderer';

const pts = (n: number, y = 0) => Array.from({ length: n }, (_, i) => new THREE.Vector3(i, y, 0));
const drawn = (l: THREE.Line) => {
  const a = l.geometry.getAttribute('position');
  return Array.from({ length: a.count }, (_, i) => [a.getX(i), a.getY(i)]);
};

describe('setLinePoints', () => {
  it('draws a longer path whole, not cut to the first one', () => {
    const l = new THREE.Line(new THREE.BufferGeometry());
    setLinePoints(l, pts(3));
    setLinePoints(l, pts(7, 1));
    expect(drawn(l)).toEqual(pts(7, 1).map((p) => [p.x, p.y]));
  });

  it('draws a shorter path without the old tail', () => {
    const l = new THREE.Line(new THREE.BufferGeometry());
    setLinePoints(l, pts(7));
    setLinePoints(l, pts(2, 5));
    expect(drawn(l)).toEqual([[0, 5], [1, 5]]);
  });

  it('draws a path after a cleared one', () => {
    const l = new THREE.Line(new THREE.BufferGeometry());
    setLinePoints(l, []);
    setLinePoints(l, pts(4));
    expect(drawn(l)).toHaveLength(4);
  });

  it('the old way did cut a longer path (the defect this replaces)', () => {
    const g = new THREE.BufferGeometry().setFromPoints(pts(3));
    const warn = console.warn;
    console.warn = () => {};
    try { g.setFromPoints(pts(7, 1)); } finally { console.warn = warn; }
    expect(g.getAttribute('position').count).toBe(3);
  });
});
