// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.1: the three reference screenshots that fix the visual target (README §7, M4.1),
 * for Gautham's approval -- never judged by the agent (README §9 rule 7):
 *
 *   node tools/perf/reference_shots.mjs --site URL --out DIR
 *
 *   follow_toward_ramp.png  the follow camera, COCO driving toward the blue lane's ramp,
 *                           the planner's frontier and closed set on the floor
 *   orbit_wide.png          a wide orbit of the whole arena
 *   robot_eye.png           the robot-eye view (rendered presentation, URDF camera link)
 *
 * 1600 x 900, GPU (ANGLE on the laptop's NVIDIA GPU), the live Arena model, goal (2.6, 2.0), the foot of the blue lane's ramp,
 * in the map frame. Writes DIR/reference_shots.json with the conditions and console errors.
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
const OUT = args.out ?? 'reference-shots';
mkdirSync(OUT, { recursive: true });
const GOAL = [2.6, 2.0];

const browser = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, goal: GOAL, shots: [], errors };
try {
  await page.goto(`${SITE}?view=arena&camera=follow`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks?.world3d_ready && !!window.__cocoPerf?.marks?.arena_ready, null, { timeout: 120_000 });
  await page.waitForTimeout(1200);
  const canvas = page.locator('canvas').first();
  await canvas.scrollIntoViewIfNeeded();
  const [sx, sy] = await page.evaluate(([x, y]) => window.__cocoArena.renderer.screenOf(x, y), GOAL);
  await page.mouse.click(sx, sy);
  await page.waitForTimeout(5000);
  await canvas.screenshot({ path: join(OUT, 'follow_toward_ramp.png') });
  out.shots.push({ file: 'follow_toward_ramp.png', camera: 'follow', after_goal_ms: 5000 });
  for (const [mode, file] of [['orbit', 'orbit_wide.png'], ['robot_eye', 'robot_eye.png']]) {
    await page.evaluate((m) => window.__cocoArena.renderer.setCameraMode(m), mode);
    await page.waitForTimeout(600);
    await canvas.screenshot({ path: join(OUT, file) });
    out.shots.push({ file, camera: mode });
  }
  out.renderer = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const ext = gl?.getExtension('WEBGL_debug_renderer_info');
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';
  });
  out.triangles = await page.evaluate(() => window.__cocoArena.renderer.three?.triangles);
} finally {
  await browser.close();
}
writeFileSync(join(OUT, 'reference_shots.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ shots: out.shots.length, errors: errors.length, renderer: out.renderer }));
