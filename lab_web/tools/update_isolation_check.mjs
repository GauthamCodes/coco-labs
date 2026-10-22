// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.8: update isolation, as a CI regression (M5's review probe,
 * tools/perf/m5_review_update.mjs, with assertions). A copy of the built site is
 * served as build A; a page opens and is controlled by A's service worker; the site
 * is rebuilt in place as build B (static hosting: A's files are gone) and B's worker
 * takes over the open page. Then, for the page that is still build A:
 *
 *   - openDocumentMixed: false -- a file it asks for is A's bytes, never B's, both
 *     by its own fetch and by its workers' build-pinned path (__b/<A>/...);
 *   - "New version ready" is shown, and the page was not reloaded;
 *   - A's cache is kept while the page is open, and deleted once no page of A is;
 *   - a reload gives a consistent build B.
 *
 *   node tools/update_isolation_check.mjs DIST OUTDIR [--template SW_TEMPLATE.js]
 */
import { chromium } from 'playwright';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { buildServiceWorker } from './build_service_worker.mjs';

const [dist, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const root = mkdtempSync(join(tmpdir(), 'g1-update-'));
cpSync(resolve(dist), root, { recursive: true, filter: (p) => !p.includes('/v1') });
// --template OLD.js runs the same checks against another worker template (M5's fails them: the control)
const ti = process.argv.indexOf('--template');
const template = readFileSync(ti > 0 ? process.argv[ti + 1] : new URL('../src/offline/sw.template.js', import.meta.url), 'utf8');
const server = createServer((req, res) => {
  const u = new URL(req.url, 'http://localhost'), path = decodeURIComponent(u.pathname.replace(/^\/coco-labs\//, '')) || 'index.html', file = resolve(root, path);
  if (!file.startsWith(root + '/') || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404).end(); return; }
  const mime = file.endsWith('.html') ? 'text/html' : /\.m?js$/.test(file) ? 'text/javascript' : file.endsWith('.wasm') ? 'application/wasm' : file.endsWith('.json') ? 'application/json' : file.endsWith('.css') ? 'text/css' : 'application/octet-stream';
  res.writeHead(200, { 'Content-Type': mime, 'Cache-Control': 'no-store' }).end(readFileSync(file));
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const site = `http://127.0.0.1:${server.address().port}/coco-labs/`;
const browser = await chromium.launch(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {});
const report = { scope: 'Functional deploy test (G1.8 update isolation), not a timing measurement', errors: [], checks: {} };
const PROBE = 'review-static-probe.json';
try {
  writeFileSync(join(root, PROBE), '"A"');
  const a = buildServiceWorker(root, template); report.versionA = a.version;
  const p = await browser.newPage();
  p.on('pageerror', (e) => report.errors.push(String(e)));
  // navigations wait for the document, then for the title -- not for every subresource ('load'),
  // which a busy CI runner has taken over 30 s to fire (twice: 05b1553, 5d3cdb2)
  const NAV = { waitUntil: 'domcontentloaded', timeout: 90000 };
  await p.goto(site, NAV); await p.getByTestId('title').waitFor({ timeout: 90000 });
  await p.evaluate(() => { window.__notReloaded = true; });
  await p.evaluate(async () => { await navigator.serviceWorker.register('./sw.js', { scope: './', updateViaCache: 'none' }); });
  await p.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 60000 });
  const controllerVersion = () => p.evaluate(() => new Promise((r) => { const c = new MessageChannel(); c.port1.onmessage = (e) => r(e.data); navigator.serviceWorker.controller.postMessage('static-version', [c.port2]); }));
  const snapshot = () => p.evaluate(async ([probe]) => {
    const build = document.querySelector('meta[name="coco-build"]').content;
    const own = await (await fetch('./' + probe)).json();
    const pr = await fetch(`./__b/${build}/${probe}`), pinned = pr.ok ? await pr.json() : `HTTP ${pr.status}`;
    const controller = await new Promise((r) => { const c = new MessageChannel(); c.port1.onmessage = (e) => r(e.data); navigator.serviceWorker.controller.postMessage('static-version', [c.port2]); });
    return { documentBuild: build, asset: own, pinnedAsset: pinned, controller };
  }, [PROBE]);
  // the page says hello (its build) on controllerchange; give it a moment, then read A's files once
  await p.waitForTimeout(500);
  report.before = await snapshot();
  const cachesOf = () => p.evaluate(() => caches.keys());
  writeFileSync(join(root, PROBE), '"B"');
  const b = buildServiceWorker(root, template); report.versionB = b.version;
  await p.evaluate(async () => { await (await navigator.serviceWorker.getRegistration()).update(); });
  await p.waitForFunction(async (version) => { const w = navigator.serviceWorker.controller; if (!w) return false; return await new Promise((r) => { const c = new MessageChannel(); c.port1.onmessage = (e) => r(e.data === version); w.postMessage('static-version', [c.port2]); }); }, b.version, { timeout: 120000 });
  report.observations = [];
  for (let i = 0; i < 20; i++) { report.observations.push(await snapshot()); await p.waitForTimeout(100); }
  report.openDocumentMixed = report.observations.some((x) => x.documentBuild !== x.controller && (x.asset === 'B' || x.pinnedAsset === 'B'));
  report.stableBSeen = report.observations.some((x) => x.controller === b.version);
  await p.getByTestId('update-notice').waitFor({ timeout: 15000 }).catch(() => {});
  report.noticeShown = await p.getByTestId('update-notice').isVisible();
  report.noticeButtons = await p.evaluate(() => [...document.querySelectorAll('[data-testid="update-notice"] button')].map((x) => x.textContent));
  report.notReloaded = await p.evaluate(() => window.__notReloaded === true);
  report.cachesWhileAOpen = await cachesOf();
  report.aCacheKeptWhileOpen = report.cachesWhileAOpen.some((n) => n.endsWith('-' + a.version));
  await p.reload(NAV); await p.getByTestId('title').waitFor({ timeout: 90000 });
  await p.waitForTimeout(1500);
  report.afterReload = await snapshot();
  report.hardReloadConsistent = report.afterReload.documentBuild === b.version && report.afterReload.asset === 'B' && report.afterReload.pinnedAsset === 'B';
  report.cachesAfterReload = await cachesOf();
  report.aCacheDeletedOnceClosed = !report.cachesAfterReload.some((n) => n.endsWith('-' + a.version));
  report.controllerAfterReload = await controllerVersion();
  // the game's model worker boots through the build-pinned path (Pyodide, the packs) under B
  const pinnedRequests = [];
  p.on('request', (r) => { if (r.url().includes('/__b/')) pinnedRequests.push(r.url().replace(site, '')); });
  await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
  await p.goto(`${site}?view=play&game=free&world=proving&tier=low`);
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 240000 });
  report.pinnedRequests = pinnedRequests.slice(0, 12);
  report.pinnedWorkerBoots = pinnedRequests.some((u) => u.includes(`__b/${b.version}/generated/pyodide/`)) && pinnedRequests.some((u) => u.includes(`__b/${b.version}/generated/arena/`));
  report.checks = {
    openDocumentMixed_false: report.openDocumentMixed === false && report.stableBSeen,
    page_A_reads_A: report.observations.every((x) => x.asset === 'A' && x.pinnedAsset === 'A'),
    new_version_notice: report.noticeShown && report.noticeButtons.join('|') === 'Save run|Reload',
    no_forced_reload: report.notReloaded,
    old_cache_kept_while_open: report.aCacheKeptWhileOpen,
    old_cache_deleted_once_closed: report.aCacheDeletedOnceClosed,
    reload_consistent_B: report.hardReloadConsistent,
    model_worker_pinned: report.pinnedWorkerBoots,
    no_page_errors: report.errors.length === 0,
  };
  report.passed = Object.values(report.checks).every(Boolean);
} catch (e) {
  report.error = String(e); report.passed = false;
} finally {
  writeFileSync(join(out, 'checks.json'), JSON.stringify(report, null, 1) + '\n');
  await browser.close(); await new Promise((r) => server.close(r));
}
console.log(JSON.stringify({ passed: report.passed, checks: report.checks, error: report.error }));
process.exitCode = report.passed ? 0 : 1;
