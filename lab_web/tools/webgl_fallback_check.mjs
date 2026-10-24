// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * No page goes blank when the browser gives no WebGL (the deployed site did, in Brave, 2026-10-24:
 * one failed 3D context unmounted the whole app). With WebGL refused (--disable-webgl) the title
 * keeps its menus and says why the Depot is not drawn, Play and Compare explain and offer Reload,
 * About is unaffected; with WebGL working nothing changes. Exit 1 on any blank page or page error.
 *
 *   node tools/webgl_fallback_check.mjs SITE [OUT.json]
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';

const [site, out] = process.argv.slice(2);
const expect = {
  'webgl-refused': { title: 'title-no-3d', play: 'page-error', compare: 'page-error', about: null },
  'webgl-ok': { title: null, play: null, compare: null, about: null },
};
const rows = [];
for (const [mode, args] of [['webgl-refused', ['--disable-webgl', '--disable-3d-apis']], ['webgl-ok', ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist']]]) {
  const b = await chromium.launch({ args });
  for (const [page, q] of [['title', ''], ['play', '?view=play&game=fetch_rush&seed=1'], ['compare', '?view=compare'], ['about', '?view=about']]) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
    await p.goto(site + q, { timeout: 90000 });
    await p.waitForTimeout(page === 'play' || page === 'compare' ? 12000 : 6000);
    const text = (await p.locator('body').innerText()).trim();
    const want = expect[mode][page];
    const fallbacks = { 'page-error': await p.locator('[data-testid="page-error"]').count(), 'title-no-3d': await p.locator('[data-testid="title-no-3d"]').count() };
    const ok = text.length > 0 && errors.length === 0 && (want ? fallbacks[want] > 0 : fallbacks['page-error'] === 0 && fallbacks['title-no-3d'] === 0);
    rows.push({ mode, page, ok, blank: text.length === 0, fallbacks, errors });
    console.log(mode, page, ok ? 'ok' : 'FAILED', JSON.stringify(fallbacks), errors.join(' | '));
    await ctx.close();
  }
  await b.close();
}
const passed = rows.every((r) => r.ok);
if (out) writeFileSync(out, JSON.stringify({ site, passed, rows }, null, 1) + '\n');
process.exitCode = passed ? 0 : 1;
