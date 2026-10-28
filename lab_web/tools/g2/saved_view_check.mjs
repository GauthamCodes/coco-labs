// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.8: Play opened with SIM view saved (the `view` pref) draws SIM, not GAME's world under a SIM
 * label. Found on the real phone: a saved SIM view reached the renderer before the world existed,
 * and the second call (world ready) was skipped as "no change". Checked per profile: the renderer's
 * view, SIM's group shown and the world hidden, the RViz camera; then V → GAME (world, chase camera)
 * and V → SIM again.
 *
 *   node tools/g2/saved_view_check.mjs SITE OUT.json
 */
import { chromium, devices } from 'playwright';
import { writeFileSync } from 'node:fs';

const [site, out] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const state = () => { const r = window.__cocoGame.renderer; return { view: r.view, sim: !!r.sim?.group.visible, world: !!r.world?.group.visible, cam: r.cam.mode }; };
const rows = [];
for (const [name, ctxOpts] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['phone-landscape', { ...devices['Pixel 5 landscape'], viewport: { width: 915, height: 412 } }]]) {
  const ctx = await b.newContext({ ...ctxOpts, serviceWorkers: 'block' });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e)));
  await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); localStorage.setItem('coco.prefs.v1.view', '"sim"'); } catch { /* none */ } });
  await p.goto(`${site}?view=play&game=fetch_rush&seed=1`);
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
  const beforePlay = await p.evaluate(state);
  await p.click('[data-testid="g1-play"]');
  await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
  await p.waitForTimeout(1000);
  const playing = await p.evaluate(state);
  await p.keyboard.press('KeyV'); await p.waitForTimeout(500);
  const game = await p.evaluate(state);
  await p.keyboard.press('KeyV'); await p.waitForTimeout(500);
  const simAgain = await p.evaluate(state);
  const isSim = (s) => s.view === 'sim' && s.sim && !s.world && s.cam === 'rviz';
  const ok = isSim(beforePlay) && isSim(playing) && game.view === 'game' && !game.sim && game.world && game.cam === 'chase' && isSim(simAgain) && errors.length === 0;
  rows.push({ profile: name, ok, beforePlay, playing, game, simAgain, errors });
  console.log(name, ok ? 'ok' : 'FAILED', JSON.stringify({ beforePlay, playing, game, simAgain }));
  await ctx.close();
}
await b.close();
const passed = rows.every((r) => r.ok);
writeFileSync(out, JSON.stringify({ site, passed, rows }, null, 1) + '\n');
process.exitCode = passed ? 0 : 1;
