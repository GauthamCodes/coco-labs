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
 * G1.13: a third profile, the REAL Nothing Phone (1)'s landscape viewport in a Chrome tab as
 * measured over USB (710 x 269 CSS px, DPR 2.9875; docs/v2/g1/data/g113/README.md section 5), and
 * in every profile no two HUD elements may overlap each other (STOP covered the MODEL badge
 * and the minimap the joystick's label at 269 px before the fix).
 *
 * Exit 0 only if every pose passes in every profile. Software rendering (SwiftShader) is
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
  '[data-testid="minimap"]', '.g1-joy',
  // G2.3: the telemetry strip and the /rosout console (always on); the Gazebo-style clock (desktop SIM)
  '[data-testid="g2-telemetry"]', '[data-testid="g2-rosout"]', '[data-testid="g2-gazebo"]'];
/** G1.13: HUD elements that must not overlap one another (the joystick's label included) */
const HUD_PAIRS = [...HUD, '.g1-joy-hint'];

/**
 * Twenty map poses (x, y, heading): open floor, aisles, beside walls and racks, corners (G1.4's
 * paths' starts and more) -- all on free plan-grid cells outside the forklift lanes (y 10-13.5 m),
 * where a forklift could stand at the pose and the result would depend on timing.
 */
const POSES = [
  [30, 0.6, Math.PI], [20, 0.6, 0], [16.2, 2.0, Math.PI * 0.75], [26, 1.2, Math.PI / 2], [28, 0.55, 0],
  [16.5, 17.3, 0], [31, 21.9, Math.PI], [18, 16.4, 0], [15.2, 3, Math.PI], [15.5, 26.5, Math.PI],
  [37.6, 3.6, 0], [37, 23.65, 0], [47.4, 16, Math.PI / 2], [45.5, 1.5, 0], [30, 7, 0],
  [24, 8, Math.PI / 2], [40, 7, Math.PI], [35, 18, Math.PI / 4], [22, 7, -Math.PI / 2], [44, 20, -Math.PI * 0.75],
];

const browser = await chromium.launch({ ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const report = { scope: 'G1.12: COCO\'s projected box vs every HUD rectangle, chase camera, 20 poses; G2.2: SIM view\'s HUD (no overlaps, STOP visible, the run goes on)', site, profiles: {}, passed: true };
const REAL_TAB = { viewport: { width: 710, height: 269 }, deviceScaleFactor: 2.9875, isMobile: true, hasTouch: true, userAgent: nothingPhone1(true).userAgent };
for (const [name, ctxOpts] of [['phone-landscape', nothingPhone1(true)], ['desktop', { viewport: { width: 1280, height: 720 } }], ['real-phone-tab-710x269', REAL_TAB]]) {
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
    // the springs settle after the teleport (chase k = 6/s, yaw 4.5/s): wait until COCO's box stops
    // moving (< 1.5 px over two samples 300 ms apart), up to 20 s -- a slow software renderer
    // takes longer frames, and the spring is stepped per frame
    const t0 = Date.now();
    let prev = null, still = 0;
    while (Date.now() - t0 < 20000) {
      await page.waitForTimeout(300);
      const b = await page.evaluate(() => window.__cocoGame.renderer.robotScreenRect());
      const moved = !b || !prev ? Infinity : Math.max(Math.abs(b.left - prev.left), Math.abs(b.top - prev.top), Math.abs(b.right - prev.right), Math.abs(b.bottom - prev.bottom));
      still = moved < 1.5 ? still + 1 : 0;
      prev = b;
      if (still >= 2 && Date.now() - t0 > 1500) break;
    }
    const settleMs = Date.now() - t0;
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
    const clashes = await page.evaluate((sel) => {
      const els = [];
      for (const s of sel) for (const el of document.querySelectorAll(s)) {
        const b = el.getBoundingClientRect(); const cs = getComputedStyle(el);
        if (b.width < 1 || b.height < 1 || cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
        els.push([s, el, b]);
      }
      const out = [];
      for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
        const [sa, a, A] = els[i], [sb, b, B] = els[j];
        if (a === b || a.contains(b) || b.contains(a)) continue;
        const w = Math.min(A.right, B.right) - Math.max(A.left, B.left), h = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
        if (w > 1 && h > 1) out.push(`${sa} x ${sb}`);
      }
      return [...new Set(out)];
    }, HUD_PAIRS);
    const overlaps = r.box ? r.hud.filter((h) => Math.min(r.box.right, h.right) - Math.max(r.box.left, h.left) > 0 && Math.min(r.box.bottom, h.bottom) - Math.max(r.box.top, h.top) > 0)
      .map((h) => h.testid || h.cls) : ['no box'];
    const onCanvas = !!r.box && r.box.left >= r.canvas.left && r.box.right <= r.canvas.right && r.box.top >= r.canvas.top && r.box.bottom <= r.canvas.bottom;
    const placed = !!r.pose && Math.hypot(r.pose[0] - x, r.pose[1] - y) < 0.05;
    const centreY = r.box ? ((r.box.top + r.box.bottom) / 2 - r.canvas.top) / (r.canvas.bottom - r.canvas.top) : null;
    const ok = overlaps.length === 0 && clashes.length === 0 && onCanvas && placed && r.cam === 'chase';
    if (!ok) report.passed = false;
    rows.push({ k, hud_clashes: clashes, want: [x, y, th], settle_ms: settleMs, placed, cam: r.cam, box: r.box && Object.fromEntries(Object.entries(r.box).map(([a, b]) => [a, Math.round(b)])), centre_y_fraction: centreY && Math.round(centreY * 1000) / 1000, on_canvas: onCanvas, overlaps, ok });
    if (shots) await page.screenshot({ path: join(shots, `${name}-${String(k + 1).padStart(2, '0')}.png`) });
  }
  // G2.2: SIM view -- the HUD shrinks to STOP, the joystick, the primary action and the switch (plus pause,
  // the MODEL chip, the SIM caption, telemetry and /rosout): none may overlap another, STOP stays visible,
  // and the run keeps going (the model's ticks advance across the switch)
  const before = await page.evaluate(() => window.__cocoGame.tick.tick);
  await page.click('[data-testid="g2-view-sim"]');
  await page.waitForTimeout(2500);
  const sim = await page.evaluate((sel) => {
    const els = [];
    for (const s of sel) for (const el of document.querySelectorAll(s)) {
      const b = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      if (b.width < 1 || b.height < 1 || cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
      els.push([s, el, b]);
    }
    const out = [];
    for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
      const [sa, a, A] = els[i], [sb, b, B] = els[j];
      if (a === b || a.contains(b) || b.contains(a)) continue;
      const w = Math.min(A.right, B.right) - Math.max(A.left, B.left), h = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
      if (w > 1 && h > 1) out.push(`${sa} x ${sb}`);
    }
    const stop = document.querySelector('[data-testid="hud-stop"], [data-testid="hud-release"]')?.getBoundingClientRect();
    return { clashes: [...new Set(out)], shown: els.map(([s]) => s), stop_visible: !!stop && stop.width > 10 && stop.right <= innerWidth && stop.bottom <= innerHeight,
      view: document.querySelector('[data-testid="g2-view"]')?.getAttribute('data-view'), tick: window.__cocoGame.tick.tick };
  }, [...HUD_PAIRS, '[data-testid="g2-view"]', '[data-testid="g2-sim-caption"]']);
  sim.kept_ticking = sim.tick > before;
  sim.ok = sim.clashes.length === 0 && sim.stop_visible && sim.view === 'sim' && sim.kept_ticking;
  if (!sim.ok) report.passed = false;
  if (shots) await page.screenshot({ path: join(shots, `${name}-sim.png`) });
  report.profiles[name] = { viewport: ctxOpts.viewport, poses: rows.length, failed: rows.filter((x) => !x.ok).length, errors, rows, sim };
  await ctx.close();
}
await browser.close();
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
for (const [name, v] of Object.entries(report.profiles)) for (const r of v.rows.filter((x) => !x.ok)) console.log(`${name} pose ${r.k + 1} failed: ${JSON.stringify(r)}`);
for (const [name, v] of Object.entries(report.profiles)) if (!v.sim.ok) console.log(`${name} SIM failed: ${JSON.stringify(v.sim)}`);
console.log(JSON.stringify({ passed: report.passed, ...Object.fromEntries(Object.entries(report.profiles).map(([k, v]) => [k, { poses: v.poses, failed: v.failed, errors: v.errors.length, sim: v.sim.ok }])) }));
process.exit(report.passed ? 0 : 1);
