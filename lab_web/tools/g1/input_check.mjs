// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.3: Play's controls, driven like a person would, checked against what the
 * MODEL reports (its command source, speed and mode), not against the DOM alone.
 *
 *   node tools/g1/input_check.mjs SITE OUTDIR [--latency-trials N]
 *
 * Cases (emulated Nothing Phone (1) landscape, multi-touch through CDP, unless noted):
 *  1. one-finger drive: the left thumb drags up; the model drives forward (source teleop)
 *  2. a second finger on STOP while the first still drives: STOP wins (source stop, latched);
 *     a HOLD on STOP releases it
 *  3. joystick nudge: a drag past the ring moves the base along; driving continues
 *  4. minimap goal: tap the minimap, tap the tactical map, tap GO; the model plans to it
 *  5. gamepad (mocked navigator.getGamepads): the left stick drives, B is STOP
 *  6. keyboard only (desktop): Tab to PLAY, Enter, W drives, Space STOPs, R releases,
 *     Esc pauses, Enter resumes
 *  7. touch-to-motion latency: perf.inputToMotion (M4.10's definition, the same one M5
 *     measured) for G1 Play and for M5 Play (?view=arena), same machine, same profile
 *
 * The emulated phone is viewport + touch + 4x CPU throttle on THIS machine's renderer
 * (recorded); it is never a phone measurement.
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const TRIALS = rest.includes('--latency-trials') ? Number(rest[rest.indexOf('--latency-trials') + 1]) : 10;
const ONLY_LATENCY = rest.includes('--only-latency');
mkdirSync(out, { recursive: true });
const launch = { ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] };
const browser = await chromium.launch(launch);
const report = { site, when: new Date().toISOString(), class: 'TESTED (emulated profile, cloud software renderer)', cases: [], latency: {} };
const GAME = `${site}?view=play&game=fetch_rush&seed=1`;

async function open(profile, url = GAME, { throttle = false, pad = false } = {}) {
  const ctx = await browser.newContext(profile === 'desktop' ? { viewport: { width: 1440, height: 900 } } : nothingPhone1(true));
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e)));
  p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await p.addInitScript((mockPad) => {
    try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ }
    if (mockPad) {
      window.__pad = { id: 'mock pad', index: 0, connected: true, mapping: 'standard', axes: [0, 0, 0, 0], buttons: Array.from({ length: 17 }, () => ({ pressed: false, value: 0 })), timestamp: 0 };
      navigator.getGamepads = () => [window.__pad];
    }
  }, pad);
  const cdp = throttle ? await throttlePhone(ctx, p) : await ctx.newCDPSession(p);
  await p.goto(url);
  return { ctx, p, cdp, errors };
}
const tick = (p) => p.evaluate(() => { const t = window.__cocoGame?.tick; return t ? { tick: t.tick, v: t.v, source: t.source, mode: t.mode, plans: t.plans.length, pose: t.pose } : null; });
const until = async (p, fn, ms = 15000) => { const t0 = Date.now(); for (;;) { const t = await tick(p); if (t && fn(t)) return t; if (Date.now() - t0 > ms) return t; await p.waitForTimeout(100); } };
const touch = (cdp, type, points) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: points.map(([x, y, id]) => ({ x, y, id, radiusX: 10, radiusY: 10 })) });
const centre = async (p, sel) => { const b = await p.locator(sel).boundingBox(); return [b.x + b.width / 2, b.y + b.height / 2]; };
async function startGame(p) { await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 180000 }); await p.tap('[data-testid="g1-play"]').catch(() => p.click('[data-testid="g1-play"]')); await until(p, (t) => t.tick > 3); }
const record = (name, ok, detail) => { report.cases.push({ name, ok, ...detail }); console.log(ok ? 'ok  ' : 'FAIL', name, JSON.stringify(detail)); };

try {
  // 1-3: touch on the emulated phone
  if (!ONLY_LATENCY) {
    const { ctx, p, cdp, errors } = await open('phone');
    await startGame(p);
    const J = [180, 300];
    await touch(cdp, 'touchStart', [[...J, 1]]);
    for (let k = 1; k <= 7; k++) { await touch(cdp, 'touchMove', [[J[0], J[1] - k * 10, 1]]); await p.waitForTimeout(30); }
    const driving = await until(p, (t) => t.source === 'teleop' && t.v > 0.2);
    record('1 one-finger drive', driving?.source === 'teleop' && driving.v > 0.2, { tick: driving });
    const S = await centre(p, '[data-testid="hud-stop"]');
    await touch(cdp, 'touchStart', [[J[0], J[1] - 70, 1], [...S, 2]]);
    await p.waitForSelector('[data-testid="hud-release"]', { timeout: 5000 }).catch(() => {});
    const stopped = await until(p, (t) => t.source === 'stop' || (t.v === 0 && t.source !== 'teleop'), 5000);
    await touch(cdp, 'touchMove', [[J[0] + 5, J[1] - 70, 1], [...S, 2]]);
    await p.waitForTimeout(800);
    const still = await tick(p);
    const latched = await p.locator('[data-testid="hud-release"]').count();
    record('2 second finger on STOP while driving: STOP wins', !!latched && still.v === 0, { at_stop: stopped, while_thumb_still_down: still });
    await touch(cdp, 'touchEnd', []);
    await p.waitForTimeout(200);
    // release: a hold on STOP
    await touch(cdp, 'touchStart', [[...S, 3]]);
    await p.waitForTimeout(900);
    await touch(cdp, 'touchEnd', []);
    const released = await p.locator('[data-testid="hud-stop"]').count();
    record('2b a hold on STOP releases it', !!released, {});
    // 3: nudge
    await touch(cdp, 'touchStart', [[150, 330, 4]]);
    for (let k = 1; k <= 18; k++) { await touch(cdp, 'touchMove', [[150, 330 - k * 10, 4]]); await p.waitForTimeout(20); }
    const base = await p.locator('.g1-joy.is-active').evaluate((e) => ({ left: parseFloat(e.style.left), top: parseFloat(e.style.top) }));
    const zone = await p.locator('[data-testid="joystick-zone"]').boundingBox();
    const nudged = await until(p, (t) => t.source === 'teleop' && t.v > 0.2);
    // the thumb is at y 150 (page); the base followed to within the 60 px travel of it
    const thumbY = 150 - zone.y, gap = base.top - thumbY;
    record('3 joystick nudge: the base follows past the ring', Math.abs(gap - 60) < 2 && nudged?.source === 'teleop', { base, thumb_y_in_zone: thumbY, gap_px: gap, tick: nudged });
    await touch(cdp, 'touchEnd', []);
    await until(p, (t) => Math.abs(t.v) < 0.01);
    // 4: minimap goal
    await p.tap('[data-testid="minimap"]');
    await p.waitForSelector('[data-testid="tactical-map"]');
    const m = await p.locator('[data-testid="tactical-map"] canvas').boundingBox();
    await p.tap('[data-testid="tactical-map"] canvas', { position: { x: m.width / 2 + 60, y: m.height / 2 - 30 } });
    const closed = !(await p.locator('[data-testid="tactical-map"]').count());
    await p.tap('[data-testid="hud-primary"]');
    const planned = await until(p, (t) => t.plans > 0 || t.mode === 'goal', 10000);
    record('4 minimap goal set (tap minimap, tap map, GO)', closed && planned?.mode === 'goal', { tick: planned });
    record('1-4 no console or page errors', errors.length === 0, { errors });
    await p.screenshot({ path: `${out}/touch.png` });
    await ctx.close();
  }
  // 5: gamepad (mocked)
  if (!ONLY_LATENCY) {
    const { ctx, p, errors } = await open('desktop', GAME, { pad: true });
    await startGame(p);
    await p.evaluate(() => { window.__pad.axes = [0, -1, 0, 0]; });
    const drove = await until(p, (t) => t.source === 'teleop' && t.v > 0.2);
    await p.evaluate(() => { window.__pad.axes = [0, 0, 0, 0]; window.__pad.buttons[1] = { pressed: true, value: 1 }; });
    await p.waitForTimeout(400);
    await p.evaluate(() => { window.__pad.buttons[1] = { pressed: false, value: 0 }; });
    const stopped = await until(p, (t) => t.source === 'stop' || t.v === 0, 5000);
    const latched = await p.locator('[data-testid="hud-release"]').count();
    record('5 gamepad: stick drives, B is STOP', drove?.source === 'teleop' && !!latched, { drove, stopped, errors });
    await ctx.close();
  }
  // 6: keyboard only
  if (!ONLY_LATENCY) {
    const { ctx, p, errors } = await open('desktop');
    await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 180000 });
    let focused = '';
    for (let k = 0; k < 20 && focused !== 'g1-play'; k++) { await p.keyboard.press('Tab'); focused = await p.evaluate(() => document.activeElement?.getAttribute('data-testid') ?? ''); }
    await p.keyboard.press('Enter');
    await until(p, (t) => t.tick > 3);
    await p.keyboard.down('KeyW');
    const drove = await until(p, (t) => t.source === 'teleop' && t.v > 0.2);
    await p.keyboard.up('KeyW');
    await p.keyboard.press('Space');
    const stopped = await until(p, (t) => t.source === 'stop' || t.v === 0, 5000);
    const latched = await p.locator('[data-testid="hud-release"]').count();
    await p.keyboard.press('KeyR');
    const released = await p.locator('[data-testid="hud-stop"]').count();
    await p.keyboard.press('Escape');
    const paused = await p.locator('[data-testid="g1-pause-menu"]').count();
    await p.keyboard.press('Enter');
    await p.waitForTimeout(300);
    const resumed = !(await p.locator('[data-testid="g1-pause-menu"]').count());
    record('6 keyboard-only playthrough', focused === 'g1-play' && drove?.source === 'teleop' && !!latched && !!released && !!paused && resumed && !errors.length,
      { tabbed_to_play: focused === 'g1-play', drove, stopped, latched: !!latched, released: !!released, paused: !!paused, resumed, errors });
    await ctx.close();
  }
  // 7: touch-to-motion latency, G1 vs M5, same definition and profile
  for (const [name, url, joySel] of [['g1', GAME, '[data-testid="joystick-zone"]'], ['m5', `${site}?view=arena`, '.night-joystick']]) {
    const { ctx, p, cdp } = await open('phone', url, { throttle: true });
    if (name === 'g1') await startGame(p);
    else { await p.waitForFunction(() => !!window.__cocoArena?.client?.world, null, { timeout: 180000 }); await p.evaluate(() => window.dispatchEvent(new Event('coco:skip-tutorial'))); }
    await p.waitForTimeout(1500);
    const pad = await p.locator(joySel).boundingBox();
    const [x, y] = name === 'g1' ? [pad.x + 160, pad.y + pad.height * 0.6] : [pad.x + pad.width / 2, pad.y + pad.height / 2];
    const got = [];
    for (let k = 0; k < TRIALS; k++) {
      const before = await p.evaluate(() => window.__cocoPerf.inputToMotion.length);
      await touch(cdp, 'touchStart', [[x, y, 9]]);
      await touch(cdp, 'touchMove', [[x, y - (name === 'g1' ? 40 : pad.height * 0.27), 9]]);
      await p.waitForTimeout(500);
      await touch(cdp, 'touchEnd', []);
      await p.waitForTimeout(1200);
      const arr = await p.evaluate(() => window.__cocoPerf.inputToMotion);
      if (arr.length > before || arr.length === 20) got.push(arr.at(-1));
    }
    const s = [...got].sort((a, b) => a - b);
    report.latency[name] = { url, trials: TRIALS, samples: got, median_ms: s[Math.floor(s.length / 2)] ?? null };
    console.log('latency', name, report.latency[name].median_ms, got.length);
    await ctx.close();
  }
} catch (e) { report.error = String(e); console.error(e); }
report.renderer = 'Chromium SwiftShader (cloud container, no GPU); emulated Nothing Phone (1) = viewport + touch (+4x CPU throttle for latency)';
report.passed = report.cases.length >= 8 && report.cases.every((c) => c.ok);
writeFileSync(`${out}/checks.json`, JSON.stringify(report, null, 1) + '\n');
await browser.close();
process.exitCode = report.passed ? 0 : 1;
