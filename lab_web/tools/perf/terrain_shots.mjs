// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.3 screenshots of the terrain in 3D, for review (not a pass/fail): the
 * built site with ?world=v2&camera=follow, a goal on the blue bay's
 * platform, a shot while the model has the robot pitched on the ramp, a shot
 * on the platform, then E (the gated grasp) and a shot once it carries.
 * Every wait is on the model's own tick (window.__cocoArena.last), never on
 * time alone.
 *
 *   node tools/perf/terrain_shots.mjs --out DIR [--site URL]
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4244/coco-labs/';
const OUT = args.out ?? 'terrain-shots';
mkdirSync(OUT, { recursive: true });
/** the blue bay's platform centre, map frame (World Spec v2: world (3.6, 2) + world_to_map (2, 0)) */
const GOAL = [5.6, 2.0];

const browser = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, goal: GOAL, shots: [], errors };
const last = () => page.evaluate(() => window.__cocoArena?.last ?? null);
const until = (fn, what, timeout = 180_000) => page.waitForFunction(fn, null, { timeout, polling: 50 })
  .catch((e) => { throw new Error(`waiting for ${what}: ${e.message}`); });
try {
  await page.goto(`${SITE}?view=arena&camera=follow&world=v2`);
  await until(() => !!window.__cocoPerf?.marks?.world3d_ready && !!window.__cocoPerf?.marks?.arena_ready, 'the 3D world');
  await page.waitForTimeout(800);
  const canvas = page.locator('canvas').first();
  await canvas.scrollIntoViewIfNeeded();
  const [sx, sy] = await page.evaluate(([x, y]) => window.__cocoArena.renderer.screenOf(x, y), GOAL);
  await page.mouse.click(sx, sy);
  const shot = async (file, note) => {
    await page.waitForTimeout(400);   // the sprung camera settles; the model keeps stepping
    const t = await last();
    await canvas.screenshot({ path: join(OUT, file) });
    out.shots.push({ file, note, tick: t?.tick, pose: t?.pose, tilt: t?.tilt, source: t?.source, grasp: t?.grasp?.phase ?? null });
  };
  await until(() => (window.__cocoArena?.last?.tilt?.[1] ?? 0) < -0.25, 'the robot pitched on the ramp');
  await shot('climbing_ramp.png', 'the model has the robot nose-up on the blue bay\'s ramp');
  await until(() => window.__cocoArena?.last?.arrived === true && (window.__cocoArena?.last?.tilt?.[0] ?? 0) > 0.6, 'arrival on the platform');
  await shot('on_platform.png', 'arrived on the platform, facing the target row');
  await page.keyboard.press('KeyE');
  await until(() => window.__cocoArena?.last?.grasp?.phase === 'carry', 'the grasp to carry');
  await shot('carrying.png', 'after E: approached, picked through the gate, carrying');
  await page.evaluate(() => window.__cocoArena.renderer.setCameraMode('orbit'));
  await shot('orbit_wide.png', 'the wide orbit camera, the robot on the platform');
  out.renderer = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const ext = gl?.getExtension('WEBGL_debug_renderer_info');
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';
  });
} finally {
  await browser.close();
}
writeFileSync(join(OUT, 'terrain_shots.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ shots: out.shots.map((s) => [s.file, s.tick, s.tilt, s.grasp]), errors }));
