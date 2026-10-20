// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.5: each world's budget per quality tier (G1 prompt §1.1):
 *
 *   tier  download (gzip)  triangles  draw calls
 *   low   <= 1.2 MB        <= 150k    <= 120
 *   high  <= 3 MB          <= 400k    <= 250
 *
 *   node tools/g1/budgets.mjs SITE OUTDIR
 *
 * Download = the world's own assets as served gzip (the level's canonical spec, its baked
 * light map, COCO's glTF for the tier); the app code is budgeted separately (check_dist's
 * title budget) and reported here beside it. Triangles and draw calls are read from the
 * renderer (three's own per-frame counter) in three views — chase at the start, a wide
 * orbit, the tactical view — and the maximum is kept. Medium is measured too (it has no
 * stated budget; it sits between the two).
 */
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const [site, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const dist = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'dist');
const gz = (rel) => { const b = readFileSync(join(dist, rel)); return rel.endsWith('.png') || rel.endsWith('.glb') ? b.length : gzipSync(b, { level: 6 }).length; };
const BUDGET = { low: { bytes: 1.2e6, tris: 150e3, draws: 120 }, high: { bytes: 3e6, tris: 400e3, draws: 250 } };
const WORLDS = { depot: { query: 'world=depot', spec: 'generated/arena/coco_depot_v1.json', light: 'generated/g1/depot.light.png' },
  proving: { query: 'world=proving', spec: 'generated/arena/coco_arena_v1.json', light: 'generated/g1/proving_v1.light.png' } };
const gameChunks = readdirSync(join(dist, 'assets')).filter((f) => /^(GameApp|PlayGame|post)-.*\.js$/.test(f));
const report = { site, budgets: BUDGET, renderer: null, rows: [], game_js_gzip: gameChunks.reduce((s, f) => s + gz('assets/' + f), 0), game_js_files: gameChunks };
const browser = await chromium.launch({ ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
for (const [world, w] of Object.entries(WORLDS)) {
  for (const tier of ['low', 'medium', 'high']) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const p = await ctx.newPage();
    await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
    await p.goto(`${site}?view=play&game=free&${w.query}&tier=${tier}`);
    await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 180000 });
    await p.click('[data-testid="g1-play"]');
    await p.waitForTimeout(1500);
    const views = {};
    for (const [name, set] of [['chase', null], ['orbit-wide', (r) => { r.cam.setMode('orbit'); r.cam.orbit.dist = 14; r.cam.orbit.pitch = 0.55; }], ['tactical', (r) => { r.cam.setMode('tactical'); r.cam.tactical.h = 30; }]]) {
      if (set) await p.evaluate(`(${set.toString()})(window.__cocoGame.renderer)`);
      await p.waitForTimeout(1200);
      views[name] = await p.evaluate(() => ({ ...window.__cocoGame.renderer.stats, calls: window.__cocoGame.renderer.renderer.info.render.calls, frame_tris: window.__cocoGame.renderer.renderer.info.render.triangles }));
    }
    if (!report.renderer) report.renderer = await p.evaluate(() => { const g = document.createElement('canvas').getContext('webgl2'); const d = g?.getExtension('WEBGL_debug_renderer_info'); return d ? g.getParameter(d.UNMASKED_RENDERER_WEBGL) : null; });
    const robot = tier === 'high' ? 'assets3d/robot_high.glb' : 'assets3d/robot_low.glb';
    const bytes = { spec: gz(w.spec), light: gz(w.light), robot: gz(robot) };
    const total = bytes.spec + bytes.light + bytes.robot;
    const draws = Math.max(...Object.values(views).map((v) => v.draws));
    const tris = Math.max(...Object.values(views).map((v) => v.triangles));
    const b = BUDGET[tier];
    const row = { world, tier, download_gzip_bytes: total, bytes, scene_triangles: tris, max_draw_calls: draws, views,
      within: b ? { download: total <= b.bytes, triangles: tris <= b.tris, draws: draws <= b.draws } : 'no stated budget' };
    report.rows.push(row);
    console.log(world, tier, total, tris, draws, JSON.stringify(row.within));
    await ctx.close();
  }
}
await browser.close();
report.passed = report.rows.every((r) => typeof r.within === 'string' || Object.values(r.within).every(Boolean));
writeFileSync(join(out, 'budgets.json'), JSON.stringify(report, null, 1) + '\n');
process.exitCode = report.passed ? 0 : 1;
