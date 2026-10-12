// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.6: every lens at every level in 3D (README §5.3, §7 M4.6).
 *
 *   node tools/perf/lens3d_check.mjs --out DIR [--site URL] [--camera follow] [--world v1|v2]
 *
 * For Plan, Localise, Map, Move and Decide at Watch, Explain and Inspect (an
 * explicit 3D ?camera=, since Inspect alone opens top-down), the page opens
 * with the subsystem's config, a goal is given, and after the model has run
 * a few seconds it records: the camera, the lens layers drawn (and visible),
 * the computation layers shown at Watch, the lens marks' heights (on a v2
 * terrain a mark on a ramp or platform stands above the floor), page errors,
 * and a screenshot. Conditions (power, GPU driver) are recorded.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4244/coco-labs/';
const OUT = args.out ?? 'lens3d-check';
const CAMERA = args.camera ?? 'follow';
const WORLD = args.world ?? 'v1';
mkdirSync(join(OUT, 'shots'), { recursive: true });
const CONDITIONS_AT_START = conditions();
/** What switches each lens's subsystem on (as render3d_fps.mjs's M2 scene does). */
const CFG = {
  plan: [], localise: ['arena.range_sigma=0.02', 'localise.filter=mcl'],
  map: ['arena.range_sigma=0.02', 'localise.filter=mcl', 'map.algorithm=occupancy', 'map.poses=belief'],
  move: ['move.controller=dwa'], decide: ['mission.start=red'],
};
const GOAL = { v1: [6.0, 4.0], v2: [5.6, 2.0] };

const b = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const rows = [];
for (const lens of Object.keys(CFG)) {
  for (const level of ['watch', 'explain', 'inspect']) {
    const page = await b.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    const q = [`view=arena`, `camera=${CAMERA}`, `lens=${lens}`, `level=${level}`, ...(WORLD === 'v2' ? ['world=v2'] : []),
      ...CFG[lens].map((c) => `cfg=${encodeURIComponent(c)}`)].join('&');
    const row = { lens, level, url: `?${q}` };
    try {
      await page.goto(`${SITE}?${q}`);
      await page.waitForFunction(() => !!window.__cocoPerf?.marks?.world3d_ready && !!window.__cocoPerf?.marks?.arena_ready, null, { timeout: 180_000 });
      await page.waitForTimeout(1500);
      const [gx, gy] = await page.evaluate((g) => window.__cocoArena.renderer.screenOf(g[0], g[1]), GOAL[WORLD]);
      await page.mouse.click(gx, gy);
      await page.waitForFunction(() => (window.__cocoArena?.last?.tick ?? 0) > 60, null, { timeout: 120_000 });
      await page.waitForTimeout(800);
      Object.assign(row, await page.evaluate(() => {
        const r = window.__cocoArena.renderer;
        const objs = [];
        r.scene.traverse((o) => { if (o.layers.mask === 1 && (o.isMesh || o.isLine || o.isPoints)) objs.push(o); });
        let zmax = 0;
        for (const o of objs) {
          o.updateMatrixWorld();
          const p = o.geometry?.getAttribute?.('position');
          if (!p || p.count > 20000) continue;
          for (let i = 0; i < p.count; i += Math.max(1, Math.floor(p.count / 200))) {
            const v = { x: p.getX(i), y: p.getY(i), z: p.getZ(i) };
            const w = o.localToWorld(new o.position.constructor(v.x, v.y, v.z));
            zmax = Math.max(zmax, w.z);
          }
        }
        const toggles = [...document.querySelectorAll('[data-testid^=lens-layer-]')];
        return {
          camera: r.cameraMode, is3d: r.is3D, tick: window.__cocoArena.last?.tick,
          layers_on: toggles.filter((t) => t.checked).map((t) => t.dataset.testid.slice(11)),
          computation_on: toggles.filter((t) => t.checked && t.dataset.role === 'computation').length,
          overlay_objects: objs.length, overlay_zmax: zmax,
        };
      }));
      await page.locator('canvas').first().screenshot({ path: join(OUT, 'shots', `${lens}_${level}.png`) });
    } catch (e) {
      row.failure = String(e).split('\n')[0];
    }
    row.errors = errors;
    rows.push(row);
    console.log(JSON.stringify([lens, level, row.camera, row.layers_on, row.overlay_zmax?.toFixed?.(3), errors.length, row.failure ?? '']));
    await page.close();
  }
}
await b.close();
const verdict = {
  every_lens_every_level_ran_in_3d: rows.every((r) => !r.failure && r.is3d === true),
  watch_at_most_two_computation_layers: rows.filter((r) => r.level === 'watch' && r.lens !== 'plan').every((r) => r.computation_on <= 2),
  no_page_errors: rows.every((r) => r.errors.length === 0),
};
const result = { criterion: 'M4.6: Plan, Localise, Map, Move, Decide at Watch, Explain, Inspect in 3D', camera: CAMERA, world: WORLD, verdict, rows };
writeFileSync(join(OUT, `lens3d_${WORLD}_${CAMERA}.json`), JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify(verdict));
