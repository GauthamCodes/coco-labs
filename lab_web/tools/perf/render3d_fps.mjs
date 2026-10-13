// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The 3D Arena's frame rate (M4.1 feasibility; M4.10's budgets), in headless Chromium:
 *
 *   node tools/perf/render3d_fps.mjs --site URL [--camera follow|orbit|robot_eye|topdown]
 *        [--gpu nvidia|intel|software] [--phone 1] [--cpu 1|4|6] [--seconds 20]
 *        [--scene plain|m2|stress] [--quality auto|high|medium|low] [--out FILE.json] [--shot FILE.png]
 *
 * - `--gpu nvidia`: ANGLE on EGL, the default EGL vendor (the laptop's RTX 4050).
 *   `--gpu intel`: ANGLE on Vulkan with Mesa's Intel driver (`VK_ICD_FILENAMES`), i.e. the
 *   laptop's integrated Raptor Lake-P graphics. `--gpu software`: SwiftShader.
 *   The renderer string the Arena's own context reports is recorded, so a run is never
 *   attributed to the wrong GPU.
 * - `--phone 1`: a phone viewport (412 x 915 CSS px, device pixel ratio 2.625, touch,
 *   mobile), and the robot's low level of detail (the page picks it for a coarse pointer).
 * - `--cpu N`: Chrome DevTools CPU throttling N x on the page AND on its workers (the
 *   Arena model runs in one). Results under `--phone`/`--cpu` are EMULATED, never a phone.
 * - `--scene plain`: a goal is set, so the robot drives with the Plan lens's layers on the
 *   floor. `--scene m2`: the fetch mission with every lens's layers (M2's laptop scene).
 *   `--scene stress` (M4.10): the m2 scene plus M2's stress load (`stress=m2`).
 * - `--quality` (M4.10): the 3D view's tier, forced (`?quality=`); the tier the page drew at
 *   is recorded (`tier`).
 *
 * After the 3D world and the live model are ready and the robot is moving, rAF frames per
 * second are sampled every second for `--seconds`, with the 95th-percentile frame time.
 */

import { writeFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4244/coco-labs/';
const CAMERA = args.camera ?? 'follow';
const GPU = args.gpu ?? 'nvidia';
const PHONE = args.phone === '1';
const CPU = Number(args.cpu ?? 1);
const SECONDS = Number(args.seconds ?? 20);
const SCENE = args.scene ?? 'plain';
const M2_CFG = ['arena.range_sigma=0.02', 'localise.filter=mcl', 'map.algorithm=occupancy', 'map.poses=belief',
  'move.controller=dwa', 'mission.start=red'];

// The Intel GPU is reached through ANGLE's Vulkan backend with Mesa's Intel driver only: forcing
// EGL onto Mesa made Chromium fall back to SwiftShader (measured, M4.1; the renderer string says so).
const INTEL_ICD = '/usr/share/vulkan/icd.d/intel_icd.json';
const flags = GPU === 'software' ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
  : GPU === 'intel' ? ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist', '--enable-gpu']
    : ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'];
const env = { ...process.env };
if (GPU === 'intel') env.VK_ICD_FILENAMES = INTEL_ICD;
const browser = await chromium.launch({ args: flags, env });
const context = await browser.newContext(PHONE
  ? { viewport: { width: 412, height: 915 }, deviceScaleFactor: 2.625, isMobile: true, hasTouch: true }
  : { viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
// `--net 4g`: the page and its workers at 9 Mbit/s down, 1.5 up, 170 ms (coldstart.mjs's profile)
const NET = args.net === '4g' ? { offline: false, downloadThroughput: 9e6 / 8, uploadThroughput: 1.5e6 / 8, latency: 170 } : null;
if (CPU > 1 || NET) {
  const throttle = async (t) => {
    const s = await context.newCDPSession(t);
    if (CPU > 1) await s.send('Emulation.setCPUThrottlingRate', { rate: CPU });
    if (NET) { await s.send('Network.enable'); await s.send('Network.emulateNetworkConditions', NET); }
  };
  await throttle(page);
  page.on('worker', (w) => { void throttle(w).catch(() => {}); });
}
const QUALITY = args.quality ?? 'auto';
const out = { site: SITE, camera: CAMERA, gpu: GPU, quality: QUALITY, flags, vk_icd: env.VK_ICD_FILENAMES ?? 'default',
  emulated: PHONE || CPU > 1 || !!NET, net: NET ? '4g' : 'none', phone_viewport: PHONE ? { width: 412, height: 915, dpr: 2.625 } : null, cpu_throttle: CPU,
  scene: SCENE, browser: browser.version() };
try {
  const cam = `&camera=${CAMERA}&quality=${QUALITY}`;   // explicit: the Arena's default camera became follow in M4.5 (D1)
  const q = SCENE === 'm2' || SCENE === 'stress'
    ? `?view=arena&perf&lens=decide&layers=all${cam}${SCENE === 'stress' ? '&stress=m2' : ''}&${M2_CFG.map((c) => `cfg=${encodeURIComponent(c)}`).join('&')}`
    : `?view=arena&perf${cam}`;
  await page.goto(`${SITE}${q}`);
  await page.waitForFunction((want3d) => !!window.__cocoPerf?.marks?.arena_ready && (!want3d || !!window.__cocoPerf.marks.world3d_ready),
    CAMERA !== 'topdown', { timeout: 240_000 });
  out.renderer = await page.evaluate(() => {
    const gl = window.__cocoArena?.renderer?.renderer.getContext();
    const ext = gl?.getExtension('WEBGL_debug_renderer_info');
    return gl ? gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER) : null;
  });
  out.triangles = await page.evaluate(() => window.__cocoArena.renderer.three?.triangles ?? null);
  out.tier = await page.evaluate(() => window.__cocoArena.renderer.quality?.tier ?? null);
  // load marks, ms since navigation (perf.ts records wall time; navigationStart is its zero)
  out.marks_ms = await page.evaluate(() => {
    const t0 = performance.timeOrigin;
    return Object.fromEntries(Object.entries(window.__cocoPerf.marks).map(([k, v]) => [k, Math.round(v - t0)]));
  });
  if (SCENE === 'm2') {
    await page.waitForFunction(() => {
      const b = window.__cocoArena.session()?.families.latest('coco.mission.fsm.transition.v1', 1e9);
      return b && b.columns.to_state.at(-1) === 'go_to_bay';
    }, null, { timeout: 240_000 });
  } else {
    await page.evaluate(() => window.__cocoArena.goal(6.0, 4.0));
  }
  await page.waitForTimeout(2000);
  const fps = [];
  const p95 = [];
  for (let s = 0; s < SECONDS; s += 1) {
    await page.waitForTimeout(1000);
    const snap = await page.evaluate(() => window.__cocoPerf.snapshot());
    fps.push(snap.fps);
    p95.push(Math.round(snap.frameMsP95 * 10) / 10);
  }
  const sorted = [...fps].sort((a, b) => a - b);
  Object.assign(out, { fps_per_second: fps, fps_median: sorted[sorted.length >> 1], fps_min: sorted[0],
    frame_ms_p95_per_second: p95 });
  if (args.shot) await page.screenshot({ path: args.shot });
} finally {
  out.console_errors = errors;
  await browser.close();
}
console.log(JSON.stringify({ camera: CAMERA, gpu: GPU, quality: QUALITY, tier: out.tier, scene: SCENE, phone: PHONE, cpu: CPU, renderer: out.renderer, fps_median: out.fps_median,
  fps_min: out.fps_min, errors: errors.length }));
if (args.out) writeFileSync(args.out, JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
