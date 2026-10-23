// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.13: the REAL Nothing Phone (1) over USB (M5's USB/CDP procedure, PHONE_MEASURE.md).
 *
 *   ADB=<adb> node tools/phone/real_phone.mjs SITE OUT_DIR [--minutes 10] [--cold 3] [--trials 15]
 *
 * Preconditions (the caller): `adb forward tcp:9222 localabstract:chrome_devtools_remote`,
 * Chrome running on the phone, and SITE reachable from the phone (e.g. `adb reverse
 * tcp:4174 tcp:4174`, SITE = http://localhost:4174/coco-labs/, which is a secure context
 * like Pages, so the service worker behaves as deployed). Playwright drives a new Chrome
 * tab on the phone over CDP; everything is measured on the phone's own CPU, GPU and screen.
 *
 * Records: the device (adb: model, Android, build, Chrome), the CSS viewport, DPR, screen,
 * orientation and safe-area insets (portrait in a tab, and in Play); cold starts (cache and
 * the origin's storage cleared first): the title's first paint and visibility, Play's
 * loading marks, PLAY enabled, the first model tick; touch-to-motion
 * (`__cocoPerf.inputToMotion`, M4.10's definition) from real CDP touches on the joystick;
 * then Fetch Rush played by touch for N minutes: drawn frames per second (the first WebGL
 * clear of each animation frame), frame intervals, the tier and drawing-buffer pixel ratio,
 * WebGL context losses, reloads, errors, and the battery's level and temperature (adb
 * `dumpsys battery`) every 30 s. Statistics for the first minute and the whole run.
 * Play needs landscape: if the page is still portrait after PLAY, the phone is rotated with
 * `settings put system user_rotation 1` and every changed setting is restored at the end.
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const MINUTES = Number(opt('--minutes', '10')), COLD = Number(opt('--cold', '3')), TRIALS = Number(opt('--trials', '15'));
const ADB = process.env.ADB || 'adb';
mkdirSync(out, { recursive: true });
const adb = (...a) => { try { return execFileSync(ADB, ['shell', ...a], { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); } catch (e) { return `error: ${e.message}`; } };
const battery = () => {
  const s = adb('dumpsys', 'battery');
  const g = (k) => (s.match(new RegExp(`${k}: (\\S+)`)) || [])[1];
  return { at: new Date().toISOString(), level_pct: Number(g('level')), temperature_c: Number(g('temperature')) / 10, status: Number(g('status')), ac_powered: g('AC powered'), usb_powered: g('USB powered') };
};
const thermal = () => (adb('dumpsys', 'thermalservice').match(/Current temperatures from HAL:[\s\S]*?(?=\n\S|$)/) || [''])[0].split('\n').slice(0, 12).join('\n');
const sorted = (a) => [...a].sort((x, y) => x - y);
const q = (a, f) => (a.length ? sorted(a)[Math.min(a.length - 1, Math.floor(f * a.length))] : null);
const stats = (fps, iv) => ({ fps_median: q(fps, 0.5), fps_min: fps.length ? Math.min(...fps) : null, fps_p05: q(fps, 0.05), windows: fps.length,
  frame_ms_median: q(iv, 0.5), frame_ms_p95: q(iv, 0.95), frame_ms_p99: q(iv, 0.99), frame_ms_max: iv.length ? Math.max(...iv) : null, frames: iv.length + 1, over_50ms: iv.filter((x) => x > 50).length });

const report = {
  class: 'REAL DEVICE: Nothing Phone (1) over USB, Chrome driven over CDP (not emulation)',
  site, started: new Date().toISOString(),
  device: { model: adb('getprop', 'ro.product.model'), android: adb('getprop', 'ro.build.version.release'), build: adb('getprop', 'ro.build.display.id'),
    chrome: (adb('dumpsys', 'package', 'com.android.chrome').match(/versionName=(\S+)/) || [])[1], wm_size: adb('wm', 'size'), wm_density: adb('wm', 'density'),
    refresh: adb('dumpsys', 'display').match(/mRefreshRate=([\d.]+)|refreshRate ([\d.]+)/)?.[0] ?? null },
  network_note: 'SITE served by the laptop over USB (adb reverse), gzip as Pages; not the phone\'s mobile network (this build is not deployed)',
  battery: [battery()], thermal_start: thermal(), cold: [], touch_to_motion: null, play: null, errors: [], console_errors: [], settings_changed: [],
};
const save = () => writeFileSync(`${out}/phone.json`, JSON.stringify(report, null, 1) + '\n');
const rot0 = { acc: adb('settings', 'get', 'system', 'accelerometer_rotation'), user: adb('settings', 'get', 'system', 'user_rotation') };

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const ctx = browser.contexts()[0];
const instrument = () => {
  try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ }
  const g = window.__phone = { serial: 0, drawnAt: -1, at: [], lost: 0, on: false };
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (fn) => raf((t) => { g.serial++; fn(t); });
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (...args) {
    const gl = getContext.apply(this, args);
    if (gl && gl.clear && !gl.__phone) {
      gl.__phone = true;
      this.addEventListener('webglcontextlost', () => { g.lost++; });
      const clear = gl.clear.bind(gl);
      gl.clear = (...v) => { if (g.drawnAt !== g.serial) { g.drawnAt = g.serial; if (g.on) g.at.push(performance.now()); } return clear(...v); };
    }
    return gl;
  };
};
const layout = (p) => p.evaluate(() => {
  const d = document.createElement('div');
  d.style.cssText = 'position:fixed;visibility:hidden;padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)';
  document.body.appendChild(d); const cs = getComputedStyle(d); const safe = [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft]; d.remove();
  const gl = document.createElement('canvas').getContext('webgl2'); const e = gl?.getExtension('WEBGL_debug_renderer_info');
  return { innerWidth, innerHeight, visualViewport: [visualViewport?.width, visualViewport?.height], dpr: devicePixelRatio, screen: [screen.width, screen.height], orientation: screen.orientation?.type,
    fullscreen: !!document.fullscreenElement, safe_area_trbl: safe, coarse: matchMedia('(pointer: coarse)').matches,
    renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : null, connection: navigator.connection ? { type: navigator.connection.type, effectiveType: navigator.connection.effectiveType } : null };
});
async function fresh() {
  const p = await ctx.newPage();
  p.on('pageerror', (e) => report.errors.push(String(e)));
  p.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
  await p.addInitScript(instrument);
  const cdp = await ctx.newCDPSession(p);
  return { p, cdp };
}
const touch = (cdp, type, pts) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map(([x, y, id]) => ({ x, y, id, radiusX: 8, radiusY: 8 })) });
/** a real touch tap at an element's centre (Playwright's tap() needs an emulated touch context) */
async function tapEl(p, cdp, sel) {
  const b = await p.locator(sel).first().boundingBox();
  const x = b.x + b.width / 2, y = b.y + b.height / 2;
  await touch(cdp, 'touchStart', [[x, y, 3]]);
  await p.waitForTimeout(60);
  await touch(cdp, 'touchEnd', []);
}
const tick = (p) => p.evaluate(() => { const t = window.__cocoGame?.tick; return t ? { tick: t.tick, source: t.source, v: t.v } : null; });
async function landscape(p) {
  let o = await p.evaluate(() => screen.orientation?.type);
  if (!/landscape/.test(o)) {
    adb('settings', 'put', 'system', 'accelerometer_rotation', '0');
    adb('settings', 'put', 'system', 'user_rotation', '1');
    report.settings_changed.push('system.user_rotation 1 (landscape), accelerometer_rotation 0 — restored at the end');
    await p.waitForTimeout(2500);
    o = await p.evaluate(() => screen.orientation?.type);
  }
  return o;
}
const restore = () => { adb('settings', 'put', 'system', 'user_rotation', rot0.user); adb('settings', 'put', 'system', 'accelerometer_rotation', rot0.acc); };

try {
  // portrait layout in a plain tab
  { const { p } = await fresh(); await p.goto(site); await p.waitForTimeout(2500); report.layout_portrait_tab = await layout(p); await p.close(); }
  // the game's own landscape request: PLAY tapped while the phone is portrait
  {
    const { p, cdp } = await fresh();
    await p.goto(`${site}?view=play&game=fetch_rush&seed=1`);
    await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
    await tapEl(p, cdp, '[data-testid="g1-play"]');
    await p.waitForTimeout(6000);
    report.portrait_play_layout = await layout(p);
    report.portrait_play = { orientation: await p.evaluate(() => screen.orientation?.type), fullscreen: await p.evaluate(() => !!document.fullscreenElement),
      ticking: (await tick(p))?.tick ?? null, rotate_card_text: await p.evaluate(() => document.body.innerText.match(/rotate[^\n]{0,80}/i)?.[0] ?? null) };
    await p.screenshot({ path: `${out}/phone-portrait-after-play.png` });
    await p.close();
  }
  // Play is landscape: rotate the phone (restored at the end)
  { const { p } = await fresh(); await p.goto(site); await p.waitForTimeout(1500); report.orientation_set = await landscape(p); await p.waitForTimeout(1000); report.layout_landscape_tab = await layout(p); await p.close(); }
  // cold starts: cache and the origin's storage cleared, then the game URL
  const origin = new URL(site).origin;
  for (let k = 0; k < COLD; k++) {
    const { p, cdp } = await fresh();
    await cdp.send('Network.enable'); await cdp.send('Network.clearBrowserCache');
    await cdp.send('Storage.clearDataForOrigin', { origin, storageTypes: 'all' });
    const t0 = Date.now();
    await p.goto(site);
    await p.getByTestId('title').waitFor({ timeout: 180000 });
    const title = await p.evaluate(() => ({ paint: Object.fromEntries(performance.getEntriesByType('paint').map((e) => [e.name, Math.round(e.startTime)])), title_visible_ms: Math.round(performance.now()),
      js_bytes: performance.getEntriesByType('resource').filter((e) => /\.m?js$/.test(new URL(e.name).pathname)).reduce((s, e) => s + (e.transferSize || 0), 0) }));
    const t1 = Date.now();
    await p.goto(`${site}?view=play&game=fetch_rush&seed=1`);
    await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
    const playEnabled = Date.now() - t1;
    const marks = await p.evaluate(() => window.__cocoPerf?.marks ?? null);
    const t2 = Date.now();
    await tapEl(p, cdp, '[data-testid="g1-play"]');
    await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 1, null, { timeout: 300000 });
    report.cold.push({ run: k + 1, title, title_wall_ms: t1 - t0, play_url_to_play_enabled_ms: playEnabled, worker_marks: marks, play_to_first_tick_ms: Date.now() - t2 });
    console.log('cold', k + 1, JSON.stringify(report.cold.at(-1)).slice(0, 300));
    save();
    await p.close();
  }
  // Play: landscape, touch-to-motion, then N minutes
  const { p, cdp } = await fresh();
  let reloads = 0, ready = false;
  p.on('framenavigated', (f) => { if (ready && f === p.mainFrame()) reloads++; });
  await p.goto(`${site}?view=play&game=fetch_rush&seed=1`);
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
  await tapEl(p, cdp, '[data-testid="g1-play"]');
  report.orientation_in_play = await p.evaluate(() => screen.orientation?.type);
  await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 3, null, { timeout: 300000 });
  ready = true;
  await p.waitForTimeout(2000);
  report.layout_play = await layout(p);
  report.render = await p.evaluate(() => { const r = window.__cocoGame?.renderer; const three = r?.renderer ?? r?.three?.renderer; return { tier: r?.tier ?? r?.quality?.tier ?? null, pixel_ratio: three?.getPixelRatio?.() ?? null, canvas: (() => { const c = document.querySelector('canvas'); return c ? [c.width, c.height] : null; })() }; });
  const zone = await p.locator('[data-testid="joystick-zone"]').boundingBox();
  const J = [zone.x + Math.min(160, zone.width / 2), zone.y + zone.height * 0.6];
  // touch-to-motion: M4.10's definition, real touches
  const got = [];
  for (let k = 0; k < TRIALS; k++) {
    const before = await p.evaluate(() => window.__cocoPerf.inputToMotion.length);
    await touch(cdp, 'touchStart', [[...J, 9]]);
    await touch(cdp, 'touchMove', [[J[0], J[1] - 40, 9]]);
    await p.waitForTimeout(500);
    await touch(cdp, 'touchEnd', []);
    await p.waitForTimeout(1200);
    const arr = await p.evaluate(() => window.__cocoPerf.inputToMotion);
    if (arr.length > before || arr.length === 20) got.push(arr.at(-1));
  }
  report.touch_to_motion = { trials: TRIALS, samples: got, median_ms: q(got, 0.5), p90_ms: q(got, 0.9) };
  console.log('touch', JSON.stringify(report.touch_to_motion));
  save();
  // N minutes of play by touch
  await p.evaluate(() => { window.__phone.on = true; window.__phone.at = []; });
  const windows = [], ticks = [], trace = [], restartLog = [];
  let prev = await p.evaluate(() => ({ n: window.__phone.at.length, t: performance.now() }));
  const moves = [[0, -60], [0, -60], [-45, -45], [0, -60], [45, -45], [0, -60], [0, 50], [0, -60]];
  const t0 = Date.now(); let i = 0, restarts = 0, oneMinute = null, lastBattery = Date.now();
  while (Date.now() - t0 < MINUTES * 60000) {
    const [dx, dy] = moves[i++ % moves.length];
    await touch(cdp, 'touchStart', [[...J, 7]]);
    await touch(cdp, 'touchMove', [[J[0] + dx, J[1] + dy, 7]]);
    await p.waitForTimeout(1000);
    await touch(cdp, 'touchEnd', []);
    const now = await p.evaluate(() => ({ n: window.__phone.at.length, t: performance.now(), tick: window.__cocoGame?.tick?.tick ?? null }));
    windows.push(((now.n - prev.n) * 1000) / (now.t - prev.t)); ticks.push(now.tick);
    // G1.13: each window's state, so a slow window can be placed (results, full screen, visibility)
    trace.push({ s: Math.round((Date.now() - t0) / 100) / 10, ms: Math.round(now.t - prev.t), fps: Math.round(windows.at(-1) * 10) / 10, tick: now.tick,
      ...(await p.evaluate(() => ({ results: !!document.querySelector('[data-testid="g1-results"]'), play_button: !!document.querySelector('[data-testid="g1-play"]'), fs: !!document.fullscreenElement, hidden: document.hidden, o: screen.orientation?.type }))) });
    prev = now;
    if (oneMinute === null && Date.now() - t0 >= 60000) {
      const at = await p.evaluate(() => window.__phone.at);
      oneMinute = stats(windows, at.slice(1).map((t, k) => t - at[k]));
      oneMinute.battery = battery();
      console.log('1 min', JSON.stringify(oneMinute));
    }
    if (Date.now() - lastBattery > 30000) { report.battery.push(battery()); lastBattery = Date.now(); save(); }
    if (await p.getByTestId('g1-results').isVisible().catch(() => false)) {
      const r0 = Date.now(), ev = { at_s: Math.round((r0 - t0) / 1000) };
      await tapEl(p, cdp, '[data-testid="g1-results"] button');
      restarts++;
      await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
      ev.play_enabled_ms = Date.now() - r0;
      await tapEl(p, cdp, '[data-testid="g1-play"]');
      await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 1, null, { timeout: 300000 });
      ev.ticking_ms = Date.now() - r0;
      ev.fullscreen_after = await p.evaluate(() => !!document.fullscreenElement);
      restartLog.push(ev);
      console.log('restart', JSON.stringify(ev));
    }
  }
  const at = await p.evaluate(() => window.__phone.at);
  const atAll = await p.evaluate(() => window.__phone.at);
  const longGaps = atAll.slice(1).map((t, k) => [t - atAll[k], atAll[k] - atAll[0]]).filter(([g]) => g > 1000).map(([g, at]) => ({ gap_ms: Math.round(g), at_s: Math.round(at / 100) / 10 }));
  report.play = { minutes: MINUTES, restarts, restart_log: restartLog, long_gaps: longGaps, trace, reloads, one_minute: oneMinute, whole: stats(windows, at.slice(1).map((t, k) => t - at[k])),
    ticking_windows: ticks.filter((t, k) => k > 0 && t !== null && ticks[k - 1] !== null && t !== ticks[k - 1]).length,
    webgl_context_lost: await p.evaluate(() => window.__phone.lost), windows };
  report.render_end = await p.evaluate(() => { const r = window.__cocoGame?.renderer; const three = r?.renderer ?? r?.three?.renderer; return { tier: r?.tier ?? r?.quality?.tier ?? null, pixel_ratio: three?.getPixelRatio?.() ?? null }; });
  await p.screenshot({ path: `${out}/phone-play.png` });
  await p.close();
} catch (e) { report.error = String(e); console.error(e); process.exitCode = 1; }
finally {
  restore();
  report.settings_restored = { accelerometer_rotation: rot0.acc, user_rotation: rot0.user };
  report.battery.push(battery());
  report.thermal_end = thermal();
  report.ended = new Date().toISOString();
  save();
  await browser.close().catch(() => {});
}
console.log(JSON.stringify({ cold: report.cold.map((c) => [c.title_wall_ms, c.play_url_to_play_enabled_ms, c.play_to_first_tick_ms]), touch: report.touch_to_motion?.median_ms, one: report.play?.one_minute, whole: report.play?.whole, lost: report.play?.webgl_context_lost, battery: [report.battery[0], report.battery.at(-1)] }));
