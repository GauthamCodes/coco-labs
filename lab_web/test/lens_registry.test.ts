// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The lens framework's rules (M2.2), held for every lens:
 * - one lens per family of computation: Plan, Localise, Map, Move, Decide,
 *   each reading only channel families coco_schemas defines;
 * - Watch shows at most TWO computation layers by default;
 * - every layer's colour is a palette key in both themes; layer ids unique;
 * - uncertainty layers are translucent (their palette alpha < 1, and the
 *   ellipse primitive refuses an opaque one); no layer is drawn in the
 *   truth colour (truth is the M1 renderer's dashed outline only);
 * - every lens's Python pack exists in tools/arena_packs.json.
 * Also: the ellipse axes the Localise/Map lenses draw, and the family store.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import * as THREE from 'three';
import { describe, expect, it } from 'vitest';

import { defaultLayers, LENSES, LEVELS } from '../src/arena/lens/registry';
import { familyOf, FamilyStore } from '../src/arena/lens/store';
import { ellipseAxes, LensLayers } from '../src/arena/render/lensLayers';
import { PALETTES, type Palette } from '../src/arena/render/palette';
import { REPO } from './helpers';

const channelsPy = readFileSync(join(REPO, 'coco_schemas', 'coco_schemas', 'channels.py'), 'utf-8');
const FAMILIES = new Set([...channelsPy.matchAll(/Channel\('[^']+',\s*'([a-z_.]+)'/g)].map((m) => m[1]));
const PACKS = JSON.parse(readFileSync(join(REPO, 'lab_web', 'tools', 'arena_packs.json'), 'utf-8')).packs;

describe('the lens registry', () => {
  it('has the five lenses, each on families coco_schemas defines', () => {
    expect(LENSES.map((l) => l.id)).toEqual(['plan', 'localise', 'map', 'move', 'decide']);
    expect(FAMILIES.size).toBeGreaterThan(15);
    for (const l of LENSES) for (const f of l.families) expect(FAMILIES.has(f), `${l.id}: ${f}`).toBe(true);
  });

  it('shows at most two computation layers at Watch', () => {
    for (const l of LENSES) {
      const watch = l.layers.filter((x) => x.from === 'watch' && (x.role === 'computation' || x.role === 'uncertainty'));
      expect(watch.length, l.id).toBeLessThanOrEqual(2);
      expect(watch.length, l.id).toBeGreaterThan(0);
      // more detail never hides a layer
      for (let i = 1; i < LEVELS.length; i += 1) {
        for (const id of defaultLayers(l, LEVELS[i - 1])) expect(defaultLayers(l, LEVELS[i])).toContain(id);
      }
    }
  });

  it('colours every layer from the palette, never in the truth colour', () => {
    const ids = new Set<string>();
    for (const l of LENSES) {
      for (const x of l.layers) {
        expect(ids.has(x.id), x.id).toBe(false);
        ids.add(x.id);
        expect(x.colour).not.toBe('truth');
        expect(x.role).not.toBe('truth');
        for (const t of ['light', 'dark'] as const) expect(typeof PALETTES[t][x.colour], `${x.id} ${t}`).toBe('string');
      }
    }
  });

  it('draws uncertainty translucent', () => {
    for (const l of LENSES) {
      for (const x of l.layers.filter((y) => y.role === 'uncertainty')) {
        for (const t of ['light', 'dark'] as const) {
          const a = PALETTES[t][`${x.colour}Alpha` as keyof Palette] as unknown as number;
          expect(a, `${x.id} needs ${x.colour}Alpha`).toBeLessThan(1);
          expect(a).toBeGreaterThan(0);
        }
      }
    }
    const ll = new LensLayers(new THREE.Scene(), PALETTES.light);
    expect(() => ll.ellipses('e', [{ x: 0, y: 0, cxx: 1, cxy: 0, cyy: 1 }], 'covariance', 1)).toThrow(/translucent/);
    ll.ellipses('e', [{ x: 0, y: 0, cxx: 1, cxy: 0, cyy: 1 }], 'covariance', 0.3);
    expect(ll.has('e')).toBe(true);
  });

  it('loads each lens from a pack the build knows', () => {
    for (const l of LENSES) expect(l.pack === 'core' || l.pack in PACKS, l.id).toBe(true);
  });
});

describe('ellipse axes (95 %, chi2(2) = 5.991)', () => {
  it('a diagonal covariance gives axis-aligned half-axes', () => {
    const [a, b, ang] = ellipseAxes(4, 0, 1);
    expect(a).toBeCloseTo(Math.sqrt(5.991 * 4), 9);
    expect(b).toBeCloseTo(Math.sqrt(5.991), 9);
    expect(ang).toBeCloseTo(0, 9);
  });
  it('a covariance rotated by 30 degrees comes back at 30 degrees', () => {
    const th = Math.PI / 6; const c = Math.cos(th); const s = Math.sin(th);
    const l1 = 9; const l2 = 1;
    const [a, b, ang] = ellipseAxes(c * c * l1 + s * s * l2, c * s * (l1 - l2), s * s * l1 + c * c * l2);
    expect(a).toBeCloseTo(Math.sqrt(5.991 * 9), 9);
    expect(b).toBeCloseTo(Math.sqrt(5.991), 9);
    expect(Math.tan(ang)).toBeCloseTo(Math.tan(th), 9);
  });
});

describe('the family store', () => {
  it('answers the latest batch at a tick, a tick exactly, and metric series', () => {
    const s = new FamilyStore();
    for (const t of [3, 5, 9]) {
      s.add({ channel: 'coco.estimate.pose.v1', tick: t, columns: { x: Float64Array.of(t) }, scalars: { estimator: 'mcl' } });
    }
    s.add({ channel: 'coco.metrics.values.v1', tick: 5, columns: { tick: BigUint64Array.of(5n, 5n), name: ['err_xy', 'n_eff'], value: Float64Array.of(0.4, 120) }, scalars: {} });
    s.add({ channel: 'coco.metrics.values.v1', tick: 9, columns: { tick: BigUint64Array.of(9n), name: ['err_xy'], value: Float64Array.of(0.2) }, scalars: {} });
    expect(s.latest('coco.estimate.pose.v1', 2)).toBeNull();
    expect(s.latest('coco.estimate.pose.v1', 6)!.tick).toBe(5);
    expect(s.latest('coco.estimate.pose.v1', 99)!.tick).toBe(9);
    expect(s.at('coco.estimate.pose.v1', 9)).toHaveLength(1);
    expect(s.series('err_xy', 8)).toEqual([{ tick: 5, value: 0.4 }]);
    expect(s.series('err_xy', 9).map((p) => p.value)).toEqual([0.4, 0.2]);
    expect(s.metricNames().sort()).toEqual(['err_xy', 'n_eff']);
    expect(s.recent(['coco.estimate.pose.v1'], 9, 2).map((b) => b.tick)).toEqual([5, 9]);
  });
  it('names a channel family, two-part families included', () => {
    expect(familyOf('coco.localise.particles.set.v1')).toBe('localise.particles');
    expect(familyOf('coco.arm.state.v1')).toBe('arm');
    expect(familyOf('coco.control.local.candidates.v1')).toBe('control.local');
    expect(familyOf('coco.metrics.values.v1')).toBe('metrics');
  });
});
