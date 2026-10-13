// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.10: a scripted session in the 3D Arena (README §7 M4 acceptance, Hygiene and Camera):
 * "0 console errors; no WebGL context loss in a 30-minute scripted session"; "no long tasks
 * while driving".
 *
 *   node tools/perf/soak3d.mjs --out DIR [--site URL] [--minutes 30] [--gpu nvidia|intel]
 *
 * On `?view=arena&world=v2&camera=follow`, round after round until the time is up: drive with
 * the keys (forward, turns, reverse) for 20 s; walk the cameras (C, through follow, orbit,
 * robot-eye, top-down) and back (V); open each of the five lenses (1-5); send a goal onto a
 * platform and let the planner drive; grasp (E) and release; STOP and release. Recorded for
 * the whole session: WebGL context-lost events on the canvas, console errors and page errors;
 * long tasks (PerformanceObserver 'longtask': main-thread tasks over 50 ms), split into those
 * while the person drives and the rest; frames per second each second. Conditions (power,
 * GPU driver) recorded.
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
const OUT = args.out ?? 'soak3d';
const MINUTES = Number(args.minutes ?? 30);
const GPU = args.gpu ?? 'nvidia';
mkdirSync(OUT, { recursive: true });
const env = { ...process.env };
const flags = GPU === 'intel'
  ? ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist', '--enable-gpu']
  : ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'];
if (GPU === 'intel') env.VK_ICD_FILENAMES = '/usr/share/vulkan/icd.d/intel_icd.json';

const b = await chromium.launch({ args: flags, env });
const page = await b.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(`page: ${String(e)}`));
page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
await page.goto(`${SITE}?view=arena&world=v2&camera=follow`);
await page.waitForFunction(() => !!window.__cocoPerf?.marks?.world3d_ready && !!window.__cocoPerf?.marks?.arena_ready, null, { timeout: 240_000 });
await page.evaluate(() => {
  const s = { lost: 0, restored: 0, long: [], driving: false, fps: [] };
  window.__soak = s;
  const cv = document.querySelector('canvas');
  cv.addEventListener('webglcontextlost', () => { s.lost += 1; });
  cv.addEventListener('webglcontextrestored', () => { s.restored += 1; });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) s.long.push({ ms: e.duration, at: e.startTime, driving: s.driving }); })
    .observe({ type: 'longtask', buffered: false });
  let n = 0; let t = performance.now();
  const f = (now) => { n += 1; if (now - t >= 1000) { s.fps.push(n * 1000 / (now - t)); n = 0; t = now; } requestAnimationFrame(f); };
  requestAnimationFrame(f);
});
const blur = () => page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
const driving = (on) => page.evaluate((v) => { window.__soak.driving = v; }, on);
const hold = async (key, ms) => { await page.keyboard.down(key); await page.waitForTimeout(ms); await page.keyboard.up(key); };
const t0 = Date.now();
let rounds = 0;
const goals = [[5.6, 2.0], [5.6, -2.0], [5.6, 6.0], [0.0, 0.0]];
while (Date.now() - t0 < MINUTES * 60_000) {
  rounds += 1;
  await blur();
  // drive: 20 s of keys
  await driving(true);
  for (const [k, ms] of [['KeyW', 4000], ['KeyA', 1500], ['KeyW', 3000], ['KeyD', 1500], ['KeyS', 2500], ['KeyD', 2500], ['KeyW', 5000]]) await hold(k, ms);
  await driving(false);
  // cameras round and back
  for (let i = 0; i < 4; i += 1) { await page.keyboard.press('KeyC'); await page.waitForTimeout(900); }
  await page.keyboard.press('KeyV');
  // lenses 1-5 (each loads its pack the first time)
  for (const k of ['Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit1']) { await page.keyboard.press(k); await page.waitForTimeout(1500); }
  // a goal onto a platform, the planner driving
  const g = goals[rounds % goals.length];
  const [x, y] = await page.evaluate((p) => window.__cocoArena.renderer.screenOf(p[0], p[1]), g);
  await page.mouse.click(x, y);
  await page.waitForTimeout(12000);
  await blur();
  await page.keyboard.press('KeyE');
  await page.waitForTimeout(6000);
  await page.keyboard.press('KeyE');
  await page.waitForTimeout(3000);
  await page.keyboard.press('Space');
  await page.waitForTimeout(500);
  await page.keyboard.press('KeyR');
  await page.waitForTimeout(500);
}
const s = await page.evaluate(() => window.__soak);
await b.close();
const fps = [...s.fps].sort((a, c) => a - c);
const drivingLong = s.long.filter((e) => e.driving);
const result = {
  criterion: 'M4.10: no WebGL context loss and 0 console errors in a 30-minute scripted session; no long tasks while driving',
  minutes: (Date.now() - t0) / 60000, rounds, gpu: GPU,
  context_lost: s.lost, context_restored: s.restored, errors: errors.length, error_samples: errors.slice(0, 10),
  long_tasks_while_driving: drivingLong.length, long_tasks_while_driving_max_ms: drivingLong.reduce((m, e) => Math.max(m, e.ms), 0),
  long_tasks_other: s.long.length - drivingLong.length, long_tasks_other_max_ms: s.long.filter((e) => !e.driving).reduce((m, e) => Math.max(m, e.ms), 0),
  fps_p05: fps[Math.floor(fps.length * 0.05)], fps_median: fps[Math.floor(fps.length / 2)], fps_seconds: fps.length,
  pass: s.lost === 0 && errors.length === 0 && drivingLong.length === 0,
};
writeFileSync(join(OUT, `soak3d_${GPU}.json`), JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify(result));
