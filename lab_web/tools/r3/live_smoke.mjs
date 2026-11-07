// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R3 (README §9, standing authority 3): the live smoke test of the PUBLIC site after a deploy.
 *
 *   node tools/r3/live_smoke.mjs URL OUT_DIR [--wait-signal FILE]
 *
 * With --wait-signal, a tab is opened on the live site FIRST and kept open; the script waits until
 * FILE exists (written once the deploy run has finished), asks that tab's service worker to look
 * for an update and expects "New version ready" without a reload. Then, in a fresh context:
 * the title; Play (a Fetch Rush round starts and COCO moves under AUTO); Compare (the workspace
 * is ready); Workbench (a small experiment runs to a digest); the Studio (the A* starter runs);
 * the Leaderboard (boards render); Learn. Every step's result, page errors and screenshots go to
 * OUT_DIR (smoke.json). Exit 1 on any failure.
 */
import { chromium } from 'playwright';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [site, out, ...rest] = process.argv.slice(2);
const signal = rest.includes('--wait-signal') ? rest[rest.indexOf('--wait-signal') + 1] : null;
mkdirSync(out, { recursive: true });
const report = { site, started_utc: new Date().toISOString(), steps: [], errors: [] };
let failed = 0;
const step = (name, ok, detail = {}) => {
  report.steps.push({ name, ok, ...detail });
  if (!ok) failed++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name} ${JSON.stringify(detail).slice(0, 300)}`);
};
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const watch = (p, tag) => {
  p.on('pageerror', (e) => report.errors.push(`${tag}: ${String(e)}`));
  p.on('console', (m) => { if (m.type() === 'error') report.errors.push(`${tag}: ${m.text()}`.slice(0, 400)); });
};
try {
  // 0. the already-open tab (before the deploy finished)
  if (signal) {
    const ctx0 = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const p0 = await ctx0.newPage();
    watch(p0, 'open-tab');
    await p0.goto(site);
    await p0.waitForTimeout(8000);   // the service worker installs and controls the page
    const before = await p0.evaluate(() => ({ controlled: !!navigator.serviceWorker?.controller, build: document.querySelector('meta[name="coco-build"]')?.getAttribute('content') ?? null }));
    report.open_tab_before = before;
    console.log('open tab ready; waiting for', signal);
    const t0 = Date.now();
    while (!existsSync(signal)) { await p0.waitForTimeout(5000); if (Date.now() - t0 > 3 * 3600e3) break; }
    let shown = false;
    for (let i = 0; i < 36 && !shown; i++) {   // up to 6 minutes for Pages' CDN to serve the new worker
      await p0.evaluate(() => navigator.serviceWorker?.getRegistration().then((r) => r?.update()).catch(() => {}));
      await p0.waitForTimeout(10000);
      shown = await p0.locator('[data-testid="update-notice"]').isVisible().catch(() => false);
    }
    const reloaded = await p0.evaluate(() => performance.getEntriesByType('navigation')[0]?.type === 'reload');
    step('an open tab shows "New version ready" and was not reloaded', shown && !reloaded, { shown, reloaded });
    await p0.screenshot({ path: join(out, 'open-tab-update.png') });
    await ctx0.close();
  }
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
  const p = await ctx.newPage();
  watch(p, 'smoke');
  // 1. title
  await p.goto(site);
  await p.waitForTimeout(3000);
  const title = await p.title();
  step('title screen', /COCO/.test(title), { title });
  await p.screenshot({ path: join(out, 'title.png') });
  // 2. Play: a Fetch Rush round starts and COCO moves under AUTO
  await p.goto(`${site}?view=play&game=fetch_rush&seed=1&tier=low`);
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 240000 });
  await p.click('[data-testid="g1-play"]');
  await p.waitForTimeout(3000);
  const pose = () => p.evaluate(() => { const t = window.__cocoGame?.tick; return t ? { tick: t.tick, pose: t.pose ?? t.truth ?? null } : null; });
  const a = await pose();
  await p.keyboard.press('f');
  await p.waitForTimeout(12000);
  const b = await pose();
  const moved = !!(a && b && b.tick > a.tick && JSON.stringify(a.pose) !== JSON.stringify(b.pose));
  step('Play: a Fetch Rush round starts and COCO moves under AUTO', moved, { a, b });
  await p.screenshot({ path: join(out, 'play.png') });
  // 3. Compare
  await p.goto(`${site}?view=compare`);
  const cmp = await p.locator('[data-testid="compare-workspace"][data-ready="true"]').waitFor({ timeout: 240000 }).then(() => true, () => false);
  step('Compare: the workspace is ready', cmp);
  await p.screenshot({ path: join(out, 'compare.png') });
  // 4. Workbench: a small experiment runs to a digest
  const spec = { schema: 'coco.experiment.v1', family: 'planning', world: 'coco_arena_v1',
    algorithms: [{ name: 'astar' }, { name: 'dijkstra' }], scenarios: { kind: 'sampled', n: 3, seed: 7 } };
  await p.goto(`${site}?view=workbench`);
  await p.locator('.wb-text summary').click({ timeout: 120000 });
  await p.locator('.wb-text textarea').fill(JSON.stringify(spec));
  await p.getByRole('button', { name: 'Apply the text' }).click();
  await p.locator('.wb-runbar button[type=submit]').click();
  const digest = await p.locator('[data-testid="wb-digest"]').innerText({ timeout: 600000 }).catch(() => '');
  step('Workbench: a small experiment runs', /[0-9a-f]{16}/.test(digest), { digest: digest.slice(0, 80) });
  await p.screenshot({ path: join(out, 'workbench.png') });
  // 5. Studio: the A* starter runs
  await p.goto(`${site}?view=workbench&tab=studio`);
  await p.locator('[data-testid=studio-editor] .cm-content').waitFor({ timeout: 240000 });
  await p.locator('[data-testid=studio-run]').click();
  const st = await p.locator('[data-testid=studio-results]').innerText({ timeout: 600000 }).catch(() => '');
  step('Studio: the A* starter runs', /found/.test(st), { results: st.slice(0, 120) });
  await p.screenshot({ path: join(out, 'studio.png') });
  // 6. Leaderboard
  await p.goto(`${site}?view=workbench&tab=leaderboard`);
  const lb = await p.locator('[data-testid="leaderboard"] table').first().waitFor({ timeout: 120000 }).then(() => true, () => false);
  const lbText = lb ? await p.locator('[data-testid="leaderboard"]').innerText() : '';
  step('Leaderboard: the boards render', lb, { theta_listed: /Theta/.test(lbText) });
  await p.screenshot({ path: join(out, 'leaderboard.png'), fullPage: true });
  // 7. Learn
  await p.goto(`${site}?view=learn`);
  const learn = await p.locator('[data-testid="learn-page"]').waitFor({ timeout: 120000 }).then(() => true, () => false);
  step('Learn renders', learn);
  await p.screenshot({ path: join(out, 'learn.png') });
  report.page_errors = report.errors.length;
  step('no page errors', report.errors.length === 0, { n: report.errors.length });
} catch (e) {
  step('the smoke test ran to the end', false, { error: String(e).slice(0, 400) });
} finally {
  await browser.close();
  report.finished_utc = new Date().toISOString();
  report.pass = failed === 0;
  writeFileSync(join(out, 'smoke.json'), JSON.stringify(report, null, 1) + '\n');
  console.log(report.pass ? 'LIVE SMOKE PASS' : `LIVE SMOKE: ${failed} failure(s)`);
}
process.exit(failed ? 1 : 0);
