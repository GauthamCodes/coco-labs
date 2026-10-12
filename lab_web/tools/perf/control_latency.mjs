// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.5: control latency (README §7 M4 acceptance: "key press to visible
 * motion within one model tick plus one frame (about 50 ms or less), median
 * over 100 presses").
 *
 *   node tools/perf/control_latency.mjs --out DIR [--site URL] [--presses 100] [--camera follow]
 *
 * Each press: the robot at rest; a scripted key-down (W, then S on the next,
 * so it stays near home); latency = from the key event's own timestamp
 * (`event.timeStamp`, when the browser dispatched it) to the end of the
 * first rendered frame whose drawn robot pose differs from the pose at the
 * press (the renderer's after-render hook). Key up; wait until the model
 * has the robot at rest again. Records every press, the median and the
 * 95th percentile, the camera, and the conditions (power, GPU driver).
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
const OUT = args.out ?? 'control-latency';
const N = Number(args.presses ?? 100);
const CAMERA = args.camera ?? 'follow';
mkdirSync(OUT, { recursive: true });
const CONDITIONS_AT_START = conditions();

const b = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const page = await b.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(`${SITE}?view=arena&perf&camera=${CAMERA}`);
await page.waitForFunction(() => !!window.__cocoPerf?.marks?.arena_ready
  && (window.__cocoArena?.renderer?.cameraMode === 'topdown' || !!window.__cocoPerf?.marks?.world3d_ready), null, { timeout: 180_000 });
await page.waitForTimeout(1500);
// the page opens on the attract recording; a first press takes over the live model (not measured)
await page.keyboard.press('KeyS');
await page.waitForFunction(() => !!window.__cocoArena?.last, null, { timeout: 30_000 });
await page.evaluate(() => {
  const r = window.__cocoArena.renderer;
  window.__lat = { armed: false, t0: 0, p0: null, out: [] };
  window.addEventListener('keydown', (e) => {
    if (e.code !== 'KeyW' && e.code !== 'KeyS') return;
    window.__lat.armed = true; window.__lat.t0 = e.timeStamp; window.__lat.p0 = [...r.lastPose];
  }, { capture: true });
  const prev = r.onAfterRender;
  r.onAfterRender = () => {
    prev?.();
    const L = window.__lat;
    if (!L.armed) return;
    const p = r.lastPose;
    if (p[0] !== L.p0[0] || p[1] !== L.p0[1] || p[2] !== L.p0[2]) { L.armed = false; L.out.push(performance.now() - L.t0); }
  };
});
const atRest = () => page.waitForFunction(() => {
  const t = window.__cocoArena?.last;
  return t && Math.abs(t.v) < 1e-9 && Math.abs(t.w) < 1e-9;
}, null, { timeout: 30_000, polling: 20 });
for (let k = 0; k < N; k += 1) {
  await atRest();
  await page.waitForTimeout(150);
  const key = k % 2 === 0 ? 'KeyW' : 'KeyS';
  await page.keyboard.down(key);
  await page.waitForFunction((n) => window.__lat.out.length > n, k, { timeout: 10_000, polling: 5 });
  await page.waitForTimeout(250);
  await page.keyboard.up(key);
}
const ms = await page.evaluate(() => window.__lat.out);
await b.close();
const s = [...ms].sort((a, c) => a - c);
const q = (p) => s[Math.min(s.length - 1, Math.round(p * (s.length - 1)))];
const res = { criterion: 'key press to visible motion, median over 100 presses: about 50 ms or less (README 7, M4)',
  camera: CAMERA, presses: ms.length, median_ms: q(0.5), p95_ms: q(0.95), max_ms: s.at(-1), min_ms: s[0],
  pass: ms.length === N && q(0.5) <= 50, latencies_ms: ms, errors };
writeFileSync(join(OUT, `control_latency_${CAMERA}.json`), JSON.stringify({ ...res, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify({ camera: CAMERA, presses: res.presses, median_ms: res.median_ms, p95_ms: res.p95_ms, max_ms: res.max_ms, pass: res.pass, errors: errors.length }));
