// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.13: the REAL Nothing Phone (1) as a player has it: full screen, with NO DevTools attached
 * while it plays.
 *
 *   ADB=<adb> node tools/phone/real_phone_free.mjs SITE OUT_DIR [--minutes 10] [--trials 15]
 *        [--game free|fetch_rush] [--tap X,Y] [--joy X,Y]
 *
 * Why: Chrome on Android keeps its status bar, address bar and navigation bar while a DevTools
 * session is attached, even when the page is in full screen (measured: 755 x 269 CSS px instead
 * of the whole screen), so tools/phone/real_phone.mjs measures a smaller window than a player
 * sees. Here DevTools is attached only to install a recorder in the page (drawn-frame times,
 * WebGL context losses, errors, every touch-to-motion sample) and to read it back at the end.
 * In between, the phone is driven only by Android itself: `input tap` on PLAY IN LANDSCAPE (the
 * portrait rotate card), `input swipe` on the joystick (real touches), `dumpsys battery` every
 * 30 s, `screencap` at the start, 1 minute and the end. SITE must be reachable from the phone
 * (`adb reverse tcp:4174 tcp:4174`). --tap / --joy: device-pixel coordinates of the rotate
 * card's PLAY IN LANDSCAPE button (portrait) and the joystick's centre (landscape), read from
 * a screencap. Every phone setting changed is restored.
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const MINUTES = Number(opt('--minutes', '10')), TRIALS = Number(opt('--trials', '15')), GAME = opt('--game', 'free');
const [TX, TY] = opt('--tap', '540,1300').split(',').map(Number), [JX, JY] = opt('--joy', '450,800').split(',').map(Number);
const ADB = process.env.ADB || 'adb';
mkdirSync(out, { recursive: true });
const run = (...a) => execFileSync(ADB, a, { maxBuffer: 64e6 });
const sh = (...a) => { try { return run('shell', ...a).toString().trim(); } catch (e) { return `error: ${e.message}`; } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const battery = () => { const s = sh('dumpsys', 'battery'); const g = (k) => (s.match(new RegExp(`${k}: (\\S+)`)) || [])[1];
  return { at: new Date().toISOString(), level_pct: Number(g('level')), temperature_c: Number(g('temperature')) / 10, ac_powered: g('AC powered') }; };
const temps = () => Object.fromEntries((sh('dumpsys', 'thermalservice').split('Current temperatures from HAL:')[1] || '').split('\n')
  .map((l) => l.match(/mValue=([-\d.]+), mType=\d+, mName=(\w+)/)).filter(Boolean).filter((m) => /skin|battery|GPU0|CPU7|CPU5/.test(m[2])).map((m) => [m[2], Number(m[1])]));
const shot = (name) => { const png = run('exec-out', 'screencap', '-p'); writeFileSync(`${out}/${name}.png`, png); return [png.readUInt32BE(16), png.readUInt32BE(20)]; };
const sorted = (a) => [...a].sort((x, y) => x - y);
const q = (a, f) => (a.length ? sorted(a)[Math.min(a.length - 1, Math.floor(f * a.length))] : null);

const rot0 = { acc: sh('settings', 'get', 'system', 'accelerometer_rotation'), user: sh('settings', 'get', 'system', 'user_rotation') };
const report = { class: 'REAL DEVICE, full screen, no DevTools attached while playing (Android input only)', site, game: GAME, minutes: MINUTES, started: new Date().toISOString(),
  device: { model: sh('getprop', 'ro.product.model'), android: sh('getprop', 'ro.build.version.release'), build: sh('getprop', 'ro.build.display.id'),
    chrome: (sh('dumpsys', 'package', 'com.android.chrome').match(/versionName=(\S+)/) || [])[1] },
  network_note: 'served by the laptop over USB (adb reverse); not the phone\'s mobile network', battery: [battery()], temps_start: temps(), shots: {}, settings_changed: [] };
const save = () => writeFileSync(`${out}/phone_free.json`, JSON.stringify(report, null, 1) + '\n');

const recorder = () => {
  try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ }
  const g = window.__free = { serial: 0, drawnAt: -1, at: [], lost: 0, errors: [], itm: [] };
  addEventListener('error', (e) => g.errors.push(String(e.message)));
  addEventListener('unhandledrejection', (e) => g.errors.push(String(e.reason)));
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (fn) => raf((t) => { g.serial++; fn(t); });
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (...args) {
    const gl = getContext.apply(this, args);
    if (gl && gl.clear && !gl.__free) {
      gl.__free = true;
      this.addEventListener('webglcontextlost', () => { g.lost++; });
      const clear = gl.clear.bind(gl);
      gl.clear = (...v) => { if (g.drawnAt !== g.serial) { g.drawnAt = g.serial; g.at.push(performance.now()); } return clear(...v); };
    }
    return gl;
  };
  // every touch-to-motion sample (perf.ts keeps only the last 20)
  const hook = setInterval(() => { const a = window.__cocoPerf?.inputToMotion; if (!a || a.__free) return; a.__free = true; const push = a.push.bind(a); a.push = (...v) => { g.itm.push(...v); return push(...v); }; clearInterval(hook); }, 200);
};

const marker = `run=${Date.now()}`;
const url = GAME === 'fetch_rush' ? `${site}?view=play&game=fetch_rush&seed=1&${marker}` : `${site}?view=play&game=free&world=depot&${marker}`;
const COOL_C = Number(opt('--cool', '36'));
try {
  // 1. install the recorder in the ordinary tab, upright, then detach
  sh('settings', 'put', 'system', 'accelerometer_rotation', '0'); sh('settings', 'put', 'system', 'user_rotation', '0');
  // a cool start: the phone rests (screen on, nothing driven) until its battery is <= COOL_C
  const c0 = Date.now();
  sh('input', 'keyevent', 'KEYCODE_HOME');
  while (battery().temperature_c > COOL_C && Date.now() - c0 < 20 * 60000) await sleep(30000);
  report.cooled = { waited_s: Math.round((Date.now() - c0) / 1000), battery: battery(), temps: temps() };
  // the page opened by Android in the foreground tab, found by its marker, the recorder installed by a reload
  sh('am', 'start', '-n', 'com.android.chrome/com.google.android.apps.chrome.Main', '-a', 'android.intent.action.VIEW', '-d', `'${url}'`);
  await sleep(5000);
  run('forward', 'tcp:9222', 'localabstract:chrome_devtools_remote');
  let browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  let p = browser.contexts()[0].pages().find((x) => x.url().includes(marker));
  if (!p) throw new Error(`no tab with ${marker}: ${browser.contexts()[0].pages().map((x) => x.url()).join(' | ')}`);
  await p.addInitScript(recorder);
  // --defaults: the person's saved quality / 120 fps choices are set aside for the run (the defaults:
  // a phone starts medium, 60 fps) and put back afterwards, exactly as they were
  if (rest.includes('--defaults')) {
    report.saved_prefs = await p.evaluate(() => { const o = {}; for (const k of ['coco.prefs.v1.quality', 'coco.prefs.v1.phone120']) { o[k] = localStorage.getItem(k); localStorage.removeItem(k); } return o; });
  }
  await p.reload();
  await p.waitForSelector('[data-testid="g1-rotate-play"]', { state: 'visible', timeout: 120000 });
  await p.waitForFunction(() => !document.querySelector('[data-testid="g1-play"]')?.disabled, null, { timeout: 300000 });
  report.before = await p.evaluate(() => ({ iw: innerWidth, ih: innerHeight, dpr: devicePixelRatio, o: screen.orientation.type }));
  await browser.close();
  run('forward', '--remove-all');
  await sleep(1500);
  report.shots.portrait_card = shot('01-portrait-card');
  // 2. a real tap on PLAY IN LANDSCAPE; then real swipes only
  sh('input', 'tap', String(TX), String(TY));
  await sleep(6000);
  report.shots.after_tap = shot('02-after-tap');
  report.full_screen_by_screencap = report.shots.after_tap[0] > report.shots.after_tap[1] ? 'landscape buffer' : 'portrait buffer';
  for (let k = 0; k < TRIALS; k++) { sh('input', 'swipe', String(JX), String(JY), String(JX), String(JY - 170), '500'); await sleep(1500); }
  const t0 = Date.now(); let i = 0, lastB = Date.now(), oneMin = false;
  const moves = [[0, -170], [0, -170], [-120, -120], [0, -170], [120, -120], [0, -170], [0, 150], [0, -170]];
  while (Date.now() - t0 < MINUTES * 60000) {
    const [dx, dy] = moves[i++ % moves.length];
    sh('input', 'swipe', String(JX), String(JY), String(JX + dx), String(JY + dy), '1000');
    await sleep(150);
    if (Date.now() - lastB > 30000) { report.battery.push(battery()); lastB = Date.now(); save(); }
    if (!oneMin && Date.now() - t0 > 60000) { report.shots.one_minute = shot('03-one-minute'); report.temps_1min = temps(); oneMin = true; }
  }
  report.shots.end = shot('04-end');
  report.temps_end = temps();
  report.battery.push(battery());
  // 3. re-attach and read the recorder
  run('forward', 'tcp:9222', 'localabstract:chrome_devtools_remote');
  browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  p = browser.contexts()[0].pages().find((x) => x.url().includes(marker));
  const r = await p.evaluate((t0wall) => {
    const g = window.__free; const r = window.__cocoGame?.renderer; const three = r?.renderer ?? r?.three?.renderer;
    return { at: g?.at ?? [], lost: g?.lost, errors: g?.errors, itm: g?.itm, fs: !!document.fullscreenElement, o: screen.orientation.type, iw: innerWidth, ih: innerHeight,
      tick: window.__cocoGame?.tick?.tick ?? null, tier: r?.tier ?? null, pixel_ratio: three?.getPixelRatio?.() ?? null, now: performance.now(), wall: Date.now() };
  }, t0);
  if (report.saved_prefs) {
    await p.evaluate((o) => { for (const [k, v] of Object.entries(o)) if (v !== null) localStorage.setItem(k, v); }, report.saved_prefs);
    report.prefs_restored = await p.evaluate(() => [localStorage.getItem('coco.prefs.v1.quality'), localStorage.getItem('coco.prefs.v1.phone120')]);
  }
  await browser.close();
  run('forward', '--remove-all');
  // the soak window in the page's clock: its last MINUTES minutes before the read-back
  const soakEnd = r.now - (r.wall - (t0 + MINUTES * 60000)), soakStart = soakEnd - MINUTES * 60000;
  const stats = (from, to) => {
    const at = r.at.filter((t) => t >= from && t <= to);
    const iv = at.slice(1).map((t, k) => t - at[k]);
    const fps = []; for (let s = from; s + 1000 <= to; s += 1000) fps.push(at.filter((t) => t >= s && t < s + 1000).length);
    return { fps_median: q(fps, 0.5), fps_min: fps.length ? Math.min(...fps) : null, fps_p05: q(fps, 0.05), windows: fps.length,
      frame_ms_median: q(iv, 0.5), frame_ms_p95: q(iv, 0.95), frame_ms_p99: q(iv, 0.99), frame_ms_max: iv.length ? Math.max(...iv) : null, frames: at.length, over_50ms: iv.filter((x) => x > 50).length };
  };
  report.play = { one_minute: stats(soakStart, soakStart + 60000), whole: stats(soakStart, soakEnd), webgl_context_lost: r.lost, page_errors: r.errors,
    end_state: { full_screen: r.fs, orientation: r.o, viewport: [r.iw, r.ih], tick: r.tick, tier: r.tier, pixel_ratio: r.pixel_ratio } };
  report.touch_to_motion = { samples: r.itm, n: r.itm?.length ?? 0, median_ms: q(r.itm ?? [], 0.5), p90_ms: q(r.itm ?? [], 0.9),
    note: 'every sample from the trials and the soak (perf.inputToMotion: drive input -> the robot drawn moved)' };
} catch (e) { report.error = String(e); console.error(e); process.exitCode = 1; }
finally {
  if (report.saved_prefs && !report.prefs_restored) {   // a failed run still puts the person's choices back
    try {
      run('forward', 'tcp:9222', 'localabstract:chrome_devtools_remote');
      const b = await chromium.connectOverCDP('http://127.0.0.1:9222');
      const pg = b.contexts()[0].pages().find((x) => x.url().includes(new URL(site).host));
      if (pg) { await pg.evaluate((o) => { for (const [k, v] of Object.entries(o)) if (v !== null) localStorage.setItem(k, v); }, report.saved_prefs); report.prefs_restored = 'in cleanup'; }
      await b.close();
    } catch (e) { report.prefs_restore_error = String(e); }
  }
  try { run('forward', '--remove-all'); } catch { /* none */ }
  sh('settings', 'put', 'system', 'user_rotation', rot0.user); sh('settings', 'put', 'system', 'accelerometer_rotation', rot0.acc);
  report.settings_restored = rot0; report.ended = new Date().toISOString(); save();
}
console.log(JSON.stringify({ shots: report.shots, fs: report.full_screen_by_screencap, one: report.play?.one_minute, whole: report.play?.whole, end: report.play?.end_state, lost: report.play?.webgl_context_lost,
  touch: report.touch_to_motion && { n: report.touch_to_motion.n, median: report.touch_to_motion.median_ms, p90: report.touch_to_motion.p90_ms }, temps: [report.temps_start, report.temps_end], battery: [report.battery[0], report.battery.at(-1)] }));
