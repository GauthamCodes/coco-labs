// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.12: the chase camera never puts COCO under the HUD (Gautham, 2026-10-22).
 *
 * The real game page (Free Drive on the Depot, chase camera), phone landscape (the
 * Nothing Phone (1) profile, emulated) and desktop (1280 x 720). COCO is moved to 20
 * scripted map poses by the model's own kidnap input; after the camera's springs settle,
 * COCO's projected bounding box (GameRenderer.robotScreenRect: its model only) must not
 * overlap the rectangle of any HUD element (the list below), and must lie on the canvas.
 *
 *   node tools/g1/chase_hud_check.mjs SITE OUT.json [--shots DIR]
 *
 * Exit 0 only if every pose passes in both profiles. Software rendering (SwiftShader) is
 * fine: this is geometry, not pixels.
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const shots = rest.includes('--shots') ? rest[rest.indexOf('--shots') + 1] : null;
if (shots) mkdirSync(shots, { recursive: true });

/** The HUD: everything drawn over the world while driving (transient toasts aside). */
const HUD = ['[data-testid="objective"]', '.g1-top-right > *', '.g1-chip', '[data-testid="speed"]', '[data-testid="hud-primary"]',
  '[data-testid="hud-autonomy"]', '[data-testid="hud-camera"]', '[data-testid="hud-stop"]', '[data-testid="hud-release"]',
  '[data-testid="minimap"]', '.g1-joy'];

/** Twenty map poses (x, y, heading): open floor, aisles, beside walls and racks, corners (G1.4's paths' starts and more). */
const POSES = [
  [30, 0.6, Math.PI], [20, 0.6, 0], [16.2, 2.0, Math.PI * 0.75], [26, 1.2, Math.PI / 2], [28, 0.55, 0],
  [16.5, 17.3, 0], [31, 21.9, Math.PI], [18, 16.4, 0], [15.2, 3, Math.PI], [15.5, 26.5, Math.PI],
  [37.6, 3.6, 0], [37, 23.65, 0], [47.4, 12, Math.PI / 2], [45.5, 1.5, 0], [30, 12, 0],
  [24, 8, Math.PI / 2], [40, 10, Math.PI], [35, 18, Math.PI / 4], [22, 12, -Math.PI / 2], [44, 20, -Math.PI * 0.75],
];

const browser = await chromium.launch({ ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const report = { scope: 'G1.12: COCO\'s projected box vs every HUD rectangle, chase camera, 20 poses', site, profiles: {}, passed: true };
for (const [name, ctxOpts] of [['phone-landscape', nothingPhone1(true)], ['desktop', { viewport: { width: 1280, height: 720 } }]]) {
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
  await page.goto(`${site}?view=play&game=free&world=depot&tier=low`);
  await page.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
  await page.click('[data-testid="g1-play"]');
  await page.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 3, null, { timeout: 120000 });
  const rows = [];
  for (const [k, [x, y, th]] of POSES.entries()) {
    await page.evaluate(([x, y, th]) => window.__cocoGame.session.send([{ kind: 'kidnap', x, y, theta: th, has_theta: true }]), [x, y, th]);
    await page.waitForFunction(([x, y]) => { const t = window.__cocoGame.tick; const p = t?.truth ?? t?.pose; return p && Math.hypot(p[0] - x, p[1] - y) < 0.05; }, [x, y], { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2200);   // the springs settle (chase k = 6/s, yaw 4.5/s)
    const r = await page.evaluate((sel) => {
      const g = window.__cocoGame;
      const box = g.renderer.robotScreenRect();
      const canvas = document.querySelector('[data-testid="arena-canvas"]').getBoundingClientRect();
      const hud = [];
      for (const s of sel) for (const el of document.querySelectorAll(s)) {
        const b = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        if (b.width < 1 || b.height < 1 || cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
        hud.push({ sel: s, testid: el.getAttribute('data-testid'), cls: el.className?.baseVal ?? el.className, left: b.left, top: b.top, right: b.right, bottom: b.bottom });
      }
      const t = g.tick; const p = t?.truth ?? t?.pose;
      return { box: box && { left: box.left + canvas.left, top: box.top + canvas.top, right: box.right + canvas.left, bottom: box.bottom + canvas.top }, canvas: { left: canvas.left, top: canvas.top, right: canvas.right, bottom: canvas.bottom }, hud, pose: p, cam: g.renderer.cam.mode };
    }, HUD);
    const overlaps = r.box ? r.hud.filter((h) => Math.min(r.box.right, h.right) - Math.max(r.box.left, h.left) > 0 && Math.min(r.box.bottom, h.bottom) - Math.max(r.box.top, h.top) > 0)
      .map((h) => h.testid || h.cls) : ['no box'];
    const onCanvas = !!r.box && r.box.left >= r.canvas.left && r.box.right <= r.canvas.right && r.box.top >= r.canvas.top && r.box.bottom <= r.canvas.bottom;
    const placed = !!r.pose && Math.hypot(r.pose[0] - x, r.pose[1] - y) < 0.05;
    const centreY = r.box ? ((r.box.top + r.box.bottom) / 2 - r.canvas.top) / (r.canvas.bottom - r.canvas.top) : null;
    const ok = overlaps.length === 0 && onCanvas && placed && r.cam === 'chase';
    if (!ok) report.passed = false;
    rows.push({ k, want: [x, y, th], placed, cam: r.cam, box: r.box && Object.fromEntries(Object.entries(r.box).map(([a, b]) => [a, Math.round(b)])), centre_y_fraction: centreY && Math.round(centreY * 1000) / 1000, on_canvas: onCanvas, overlaps, ok });
    if (shots) await page.screenshot({ path: join(shots, `${name}-${String(k + 1).padStart(2, '0')}.png`) });
  }
  report.profiles[name] = { viewport: ctxOpts.viewport, poses: rows.length, failed: rows.filter((x) => !x.ok).length, errors, rows };
  await ctx.close();
}
await browser.close();
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ passed: report.passed, ...Object.fromEntries(Object.entries(report.profiles).map(([k, v]) => [k, { poses: v.poses, failed: v.failed, errors: v.errors.length }])) }));
process.exit(report.passed ? 0 : 1);
