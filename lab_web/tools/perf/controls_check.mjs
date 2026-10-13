// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.5: the Arena's controls, driven in a real browser (README §5.5).
 *
 *   node tools/perf/controls_check.mjs --out DIR [--site URL]
 *
 * On the plain Arena (no parameters but ?perf): the default camera is
 * follow (D1); W drives and the HUD says the person is driving; Space
 * latches STOP and W does nothing until R releases it; holding R resets the
 * robot home; C walks follow -> orbit -> robot-eye -> top-down -> follow,
 * and the longest frame during each 0.4 s transition is recorded (README
 * acceptance: no frame over 50 ms during transitions); H opens the help; a
 * remap (STOP to X) works, and survives a reload (the preferences module);
 * Tab hands back to autonomy after a goal. Every wait is on the model's own
 * tick or the page's state. Records conditions (power, GPU driver).
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
const OUT = args.out ?? 'controls-check';
mkdirSync(OUT, { recursive: true });
const CONDITIONS_AT_START = conditions();

const b = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const ctx = await b.newContext({ viewport: { width: 1400, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
const checks = {};
const last = () => page.evaluate(() => window.__cocoArena?.last ?? null);
const until = (fn, arg, what, timeout = 30_000) => page.waitForFunction(fn, arg, { timeout, polling: 30 })
  .catch((e) => { throw new Error(`waiting for ${what}: ${e.message.split('\n')[0]}`); });
const hud = () => page.evaluate(() => ({ source: document.querySelector('[data-testid=hud-source]')?.textContent ?? null,
  latched: !!document.querySelector('[data-testid=hud-latched]') }));
const open = async () => {
  await page.goto(`${SITE}?view=arena&perf`);
  await until(() => !!window.__cocoPerf?.marks?.world3d_ready && !!window.__cocoPerf?.marks?.arena_ready, null, 'the 3D world', 180_000);
  await page.waitForTimeout(500);
  await page.locator('canvas').first().click({ position: { x: 5, y: 5 }, trial: true });
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
};
const poseOf = (t) => t?.pose ?? [0, 0, 0];
const dist = (a, c) => Math.hypot(a[0] - c[0], a[1] - c[1]);

try {
  await open();
  checks.default_camera = await page.evaluate(() => window.__cocoArena.renderer.cameraMode);
  const home = poseOf(await last());

  // W drives; the HUD names the driver
  await page.keyboard.down('KeyW');
  await until((h) => { const p = window.__cocoArena?.last?.pose; return p && Math.hypot(p[0] - h[0], p[1] - h[1]) > 0.05; }, home, 'W to move the robot');
  checks.w_drives = true;
  checks.hud_while_driving = (await hud()).source;
  await page.keyboard.up('KeyW');

  // Space latches STOP: W then does nothing
  await page.keyboard.press('Space');
  await until(() => Math.abs(window.__cocoArena?.last?.v ?? 1) < 1e-9, null, 'STOP');
  checks.hud_after_stop = await hud();
  const held = poseOf(await last());
  await page.keyboard.down('KeyW');
  await page.waitForTimeout(800);
  await page.keyboard.up('KeyW');
  checks.latched_moved_m = dist(poseOf(await last()), held);
  // R releases; W drives again
  await page.keyboard.press('KeyR');
  checks.hud_after_release = await hud();
  const rel = poseOf(await last());
  await page.keyboard.down('KeyW');
  await until((h) => { const p = window.__cocoArena?.last?.pose; return p && Math.hypot(p[0] - h[0], p[1] - h[1]) > 0.05; }, rel, 'W after release');
  await page.keyboard.up('KeyW');
  checks.release_drives = true;
  // hold R: back home
  await page.keyboard.down('KeyR');
  await page.waitForTimeout(1300);
  await page.keyboard.up('KeyR');
  await until((h) => { const p = window.__cocoArena?.last?.pose; return p && Math.hypot(p[0] - h[0], p[1] - h[1]) < 1e-6; }, home, 'reset home');
  checks.hold_r_resets_home = true;

  // C walks the cameras; the longest frame in each transition
  checks.cameras = [];
  for (const want of ['orbit', 'robot_eye', 'topdown', 'follow']) {
    await page.evaluate(() => {
      window.__tr = [];
      let lastT = performance.now();
      const f = (now) => { window.__tr.push(now - lastT); lastT = now; if (window.__tr.length < 60) requestAnimationFrame(f); };
      requestAnimationFrame(f);
    });
    await page.keyboard.press('KeyC');
    await page.waitForTimeout(1100);
    const r = await page.evaluate(() => ({ mode: window.__cocoArena.renderer.cameraMode, three: window.__cocoArena.renderer.three?.mode,
      max_frame_ms: Math.max(...window.__tr.slice(1)) }));
    checks.cameras.push({ want, ...r });
  }

  // H opens the help; remap STOP to X; X then stops; it survives a reload
  await page.keyboard.press('KeyH');
  checks.help_opens = await page.locator('[data-testid=help]').isVisible();
  await page.locator('[data-testid=rebind-stop]').click();
  await page.keyboard.press('KeyX');
  await page.locator('[data-testid=help-close]').click();
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  await page.keyboard.down('KeyW');
  await page.waitForTimeout(400);
  await page.keyboard.up('KeyW');
  await page.keyboard.press('KeyX');
  await until(() => !!document.querySelector('[data-testid=hud-latched]'), null, 'X to stop after the remap');
  checks.remap_works = true;
  await page.keyboard.press('KeyR');
  await open();
  await page.keyboard.press('KeyX');
  await until(() => !!document.querySelector('[data-testid=hud-latched]'), null, 'X to stop after a reload');
  checks.remap_survives_reload = true;
  await page.keyboard.press('KeyR');

  // a goal, then the person drives, then Tab hands back: the planner drives again
  const [gx, gy] = await page.evaluate(() => window.__cocoArena.renderer.screenOf(6.0, 4.0));
  await page.mouse.click(gx, gy);
  await until(() => window.__cocoArena?.last?.source === 'planner', null, 'the planner to drive');
  await page.keyboard.down('KeyA');
  await until(() => window.__cocoArena?.last?.source === 'teleop', null, 'the person to take over');
  await page.keyboard.up('KeyA');
  await page.keyboard.press('Tab');
  await until(() => window.__cocoArena?.last?.source === 'planner', null, 'Tab to hand back');
  checks.tab_hands_back = true;
} finally {
  await b.close();
}
const verdict = {
  default_follow: checks.default_camera === 'follow',
  drive_and_hud: checks.w_drives === true && /driving/.test(checks.hud_while_driving ?? ''),
  stop_latches: checks.hud_after_stop?.latched === true && checks.latched_moved_m < 1e-6 && checks.hud_after_release?.latched === false,
  hold_r_resets: checks.hold_r_resets_home === true,
  cameras_cycle: JSON.stringify(checks.cameras?.map((c) => c.mode)) === JSON.stringify(['orbit', 'robot_eye', 'topdown', 'follow']),
  transitions_under_50ms: (checks.cameras ?? []).every((c) => c.max_frame_ms <= 50),
  help_and_remap: checks.help_opens === true && checks.remap_works === true && checks.remap_survives_reload === true,
  tab_hands_back: checks.tab_hands_back === true,
  no_page_errors: errors.length === 0,
};
const result = { criterion: 'M4.5: README 5.5 controls in a real browser', verdict, checks, errors };
writeFileSync(join(OUT, 'controls_check.json'), JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify({ verdict, cameras: checks.cameras, errors: errors.slice(0, 3) }));
