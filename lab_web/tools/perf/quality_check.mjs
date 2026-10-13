// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.4: the 3D view's quality tiers and its fallback, in a real browser.
 *
 *   node tools/perf/quality_check.mjs --out DIR [--site URL] [--seconds 20]
 *
 * Two runs of the built site (?view=arena&camera=follow&world=v2):
 * - `gpu`: Chromium on the machine's GPU (ANGLE over EGL), tier 'auto': the
 *   tier the page settles on, and the frame intervals it measured;
 * - `cannot_draw`: software GL (SwiftShader) with the CPU throttled 20x
 *   (Chrome DevTools Protocol), starting on the low tier ('?quality=low'):
 *   a device that cannot hold the low tier. The page must fall back to the
 *   top-down view and say so (a notice), and keep running the model.
 * Each run records the page's quality marks, the notice, the camera at the
 * end, page errors, and the machine's conditions (power, GPU driver).
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
const OUT = args.out ?? 'quality-check';
const SECONDS = Number(args.seconds ?? 20);
mkdirSync(OUT, { recursive: true });
const CONDITIONS_AT_START = conditions();

async function run(name, launchArgs, query, throttle) {
  const start = conditions();
  const b = await chromium.launch({ args: launchArgs });
  const page = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(`${SITE}?view=arena&camera=follow&world=v2${query}`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks?.world3d_ready, null, { timeout: 240_000 });
  if (throttle) {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle });
  }
  const t0 = Date.now();
  // frame intervals, measured in the page the way the controller sees them
  await page.evaluate(() => {
    window.__qc = [];
    let last = performance.now();
    const f = (now) => { window.__qc.push(now - last); last = now; requestAnimationFrame(f); };
    requestAnimationFrame(f);
  });
  await page.waitForTimeout(SECONDS * 1000);
  const r = await page.evaluate(() => {
    const ren = window.__cocoArena.renderer;
    const iv = window.__qc.slice().sort((a, b) => a - b);
    const q = (p) => iv[Math.min(iv.length - 1, Math.round(p * (iv.length - 1)))];
    const marks = Object.fromEntries(Object.entries(window.__cocoPerf?.marks ?? {}).filter(([k]) => k.startsWith('quality_')));
    const gl = document.createElement('canvas').getContext('webgl2');
    const ext = gl?.getExtension('WEBGL_debug_renderer_info');
    return {
      tier: ren.quality?.tier ?? null, choice: ren.quality?.choice ?? null, fell_back: ren.quality?.fellBack ?? null,
      camera: ren.cameraMode, is3d: ren.is3D, pixel_ratio: ren.renderer.getPixelRatio(),
      notice: document.querySelector('.notice')?.textContent ?? null,
      frames: iv.length, interval_ms: { p50: q(0.5), p90: q(0.9) }, marks,
      model_tick: window.__cocoArena.last?.tick ?? null,
      renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown',
    };
  });
  await b.close();
  return { name, query, throttle: throttle ?? 1, seconds: SECONDS, wall_s: (Date.now() - t0) / 1000, ...r, errors,
    conditions: { start, end: conditions() } };
}

const runs = [];
runs.push(await run('gpu', ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'], '', null));
runs.push(await run('cannot_draw', ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'], '&quality=low', 20));
const verdict = {
  gpu_stays_3d: runs[0].is3d === true && runs[0].fell_back === false,
  cannot_draw_falls_back_with_notice: runs[1].fell_back === true && runs[1].camera === 'topdown' && !!runs[1].notice,
  no_page_errors: runs.every((r) => r.errors.length === 0),
};
const result = { criterion: 'M4.4: tiers from measured frame time; automatic top-down fallback with a notice when the low tier cannot hold about 24 fps', verdict, runs };
writeFileSync(join(OUT, 'quality_check.json'), JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify({ verdict, runs: runs.map((r) => [r.name, r.tier, r.camera, r.fell_back, r.interval_ms, r.marks]) }));
