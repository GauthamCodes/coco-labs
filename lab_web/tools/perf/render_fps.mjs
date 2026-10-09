// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Renderer frame rate under the M1 laptop load (M1.6 / M1.10): the Arena
 * plus `?stress` = 50,000 instanced points and 20,000 line segments over the
 * grid texture, LiDAR fan and robot.
 *
 *   node tools/perf/render_fps.mjs --site URL [--gl gpu|swiftshader] [--headed 1]
 *        [--seconds 10] [--out FILE.json]
 *
 * Reports the WebGL renderer string (so a software rasteriser is never
 * mistaken for the GPU), rAF frames per second sampled every second, and
 * the 95th-percentile frame time, after the Arena is ready.
 */

import { writeFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4174/coco-labs/';
const GL = args.gl ?? 'gpu';
const SECONDS = Number(args.seconds ?? 10);
const flags = GL === 'gpu'
  ? ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu']
  : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'];
const browser = await chromium.launch({ headless: args.headed !== '1', args: flags });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
const out = { site: SITE, gl_mode: GL, flags, browser: browser.version(), load: { points: 50000, segments: 20000 } };
try {
  await page.goto(`${SITE}?view=arena&perf&stress`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  // the Arena's OWN context: what actually draws (null = the renderer failed)
  out.renderer = await page.evaluate(() => {
    const gl = window.__cocoArena?.renderer?.renderer.getContext();
    if (!gl) return null;
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    return { vendor: gl.getParameter(ext ? ext.UNMASKED_VENDOR_WEBGL : gl.VENDOR),
      renderer: gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER) };
  });
  out.renderer_error = await page.locator('.error').textContent().catch(() => null);
  // a goal, so the search layers are live during the measurement too
  await page.evaluate(() => window.__cocoArena.goal(6.0, 4.0));
  await page.waitForTimeout(2000);
  const fps = [];
  const p95 = [];
  for (let s = 0; s < SECONDS; s += 1) {
    await page.waitForTimeout(1000);
    const snap = await page.evaluate(() => window.__cocoPerf.snapshot());
    fps.push(snap.fps);
    p95.push(snap.frameMsP95);
  }
  const sorted = [...fps].sort((a, b) => a - b);
  out.fps_per_second = fps;
  out.fps_median = sorted[sorted.length >> 1];
  out.fps_min = sorted[0];
  out.frame_ms_p95_per_second = p95.map((v) => Math.round(v * 10) / 10);
  out.console_errors = errors;
  if (args.shot) await page.screenshot({ path: args.shot });
} finally {
  await browser.close();
}
console.log(JSON.stringify({ gl: GL, renderer: out.renderer, fps_median: out.fps_median, fps_min: out.fps_min }));
if (args.out) writeFileSync(args.out, JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
