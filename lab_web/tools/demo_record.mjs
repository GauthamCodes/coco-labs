// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Record a 60-90 s demo of COCO Lab in 3D (M4.9; M3.8's script reshot. A DRAFT for
 * Gautham, never published by the agent):
 *
 *   node tools/demo_record.mjs --site URL --out DIR [--gpu 1]
 *
 * One continuous browser video (Playwright's recordVideo, WebM, 1280 x 720):
 *   1. the 3D Arena (World Spec v2), follow camera: a goal on the blue bay's platform,
 *      the search spreading from the robot (the orbit camera for the overview), then
 *      the robot driving up the ramp (MODEL · kinematic);
 *   2. the same search at Explain, the camera to top-down (C, the 0.4 s transition):
 *      the heatmap of the order the cells were expanded;
 *   3. Race the planner's ghost: the warm-up level, the ghost (translucent) leaving
 *      as the person starts to drive;
 *   4. a Case File in 3D: a Lab 4 fetch climbing a ramp, as Gazebo recorded it (STACK),
 *      its body at the recorded height and tilt.
 * Writes DIR/coco_lab_demo_3d.webm and DIR/demo.json (the scenes and timings).
 */

import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4244/coco-labs/';
const OUT = args.out ?? 'demo-out';
mkdirSync(OUT, { recursive: true });
const size = { width: 1280, height: 720 };
const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const context = await browser.newContext({ viewport: size, recordVideo: { dir: OUT, size } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
const t0 = Date.now();
const scenes = [];
const scene = (name) => scenes.push({ name, at_s: (Date.now() - t0) / 1000 });
const ready3d = () => page.waitForFunction(() => !!window.__cocoPerf?.marks?.world3d_ready && !!window.__cocoPerf?.marks?.arena_ready,
  null, { timeout: 180_000 });
const canvasCentre = async () => {
  const c = page.locator('canvas').first();
  await c.scrollIntoViewIfNeeded();
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
};

// 1. a goal on a platform: the search spreading, then the climb
scene('3D Arena (World Spec v2): a goal on the blue platform, the search, the climb');
await page.goto(`${SITE}?view=arena&world=v2&camera=follow`);
await ready3d();
await canvasCentre();
await page.waitForTimeout(1200);
await page.keyboard.press('KeyC');                       // orbit: the whole arena, the search spreading
await page.waitForTimeout(900);
const [gx, gy] = await page.evaluate(() => window.__cocoArena.renderer.screenOf(5.6, 2.0));
await page.mouse.click(gx, gy);
await page.waitForTimeout(4000);
await page.keyboard.press('KeyV');                       // back to follow: the robot drives up the ramp
await page.waitForFunction(() => (window.__cocoArena?.last?.tilt?.[1] ?? 0) < -0.25, null, { timeout: 60_000 });
await page.waitForTimeout(6000);

// 2. Explain: the heatmap, top-down
scene('Explain: the heatmap of the expansion order, top-down');
await page.getByRole('button', { name: 'Explain', exact: true }).first().click().catch(() => {});
await canvasCentre();
await page.keyboard.press('KeyC');                       // follow -> orbit
await page.waitForTimeout(500);
await page.keyboard.press('KeyC');                       // -> robot-eye
await page.waitForTimeout(1500);
await page.keyboard.press('KeyC');                       // -> top-down
await page.waitForTimeout(5000);

// 3. the ghost race
scene("Race the planner's ghost: the warm-up");
await page.goto(`${SITE}?view=arena&play=race-the-ghost&pl=warm-up&camera=follow&seed=1`);
await ready3d();
await canvasCentre();
await page.waitForTimeout(1500);
await page.keyboard.down('KeyA');
await page.waitForTimeout(700);
await page.keyboard.up('KeyA');
await page.keyboard.down('KeyW');
await page.waitForTimeout(5500);
await page.keyboard.up('KeyW');
await page.keyboard.press('KeyC');                       // orbit: the ghost reaching the flag
await page.waitForTimeout(4000);

// 4. a Case File in 3D: a Lab 4 fetch on the ramp
scene('Case File (STACK): a Lab 4 fetch climbing a ramp, as Gazebo recorded it');
await page.goto(`${SITE}?view=arena&casefile=lab4_b1_colours_s5_red`);
await page.waitForFunction(() => !!window.__cocoPerf?.marks?.recording_ready && !!window.__cocoPerf?.marks?.world3d_ready, null, { timeout: 180_000 });
await canvasCentre();
// the first tick the recorded body is on the ramp (truth pitch below -0.25 rad)
const climb = await page.evaluate(() => {
  const s = window.__cocoArena.session();
  const h = s.history.find((x) => (x.truth_tilt?.[1] ?? 0) < -0.25);
  return h ? h.tick : null;
});
if (climb !== null) {
  await page.evaluate((t) => { const s = window.__cocoArena.session(); s.playing = false; s.seekTick(Math.max(1, t - 40)); s.playing = true; }, climb);
}
await page.waitForTimeout(12000);
scene('end');

await context.close();
await browser.close();
const video = await page.video()?.path();
const file = join(OUT, 'coco_lab_demo_3d.webm');
if (video) renameSync(video, file);
writeFileSync(join(OUT, 'demo.json'), JSON.stringify({ site: SITE, file, duration_s: (Date.now() - t0) / 1000, scenes, errors, climb_tick: climb }, null, 1) + '\n');
console.log(JSON.stringify({ file, duration_s: (Date.now() - t0) / 1000, scenes: scenes.length, errors: errors.length, climb_tick: climb }));
