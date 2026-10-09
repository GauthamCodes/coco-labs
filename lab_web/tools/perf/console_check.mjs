// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Console hygiene for every public view, in headless Chromium (M0 fix A.2;
 * reused for M1's hygiene criterion).
 *
 *   node tools/perf/console_check.mjs --site http://127.0.0.1:4173/coco-labs/ \
 *        --out DIR [--recovery-port 8089] [--stub tools/perf/stub_stack.py]
 *
 * Part 1, for each of plan, live, localise, map, search, move: a fresh
 * browser loads the view, waits for network idle plus a settle window long
 * enough to cover the Live probe's first three backoff steps (2 + 4 s), and
 * records console errors and warnings, page errors, every WebSocket the page
 * opened, and every request that left the site's origin.
 *
 * Part 2 (with --recovery-port): the Live view is opened with
 * `?live=ws://localhost:PORT/ws` while nothing listens there: it must open
 * no socket and say "offline". Then a stand-in coco.v1 server
 * (stub_stack.py) starts, and the page must reach "connected" on its own,
 * through the backoff, with exactly one socket.
 */

import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4173/coco-labs/';
const OUT = args.out ?? 'console-out';
const SETTLE_MS = Number(args.settle ?? 8000);
const PORT = args['recovery-port'] ? Number(args['recovery-port']) : null;
const STUB = args.stub ?? join(new URL('.', import.meta.url).pathname, 'stub_stack.py');
const VIEWS = ['plan', 'live', 'localise', 'map', 'search', 'move', 'arena'];
mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const origin = new URL(SITE).origin;

async function open(url, width) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  const rec = { console_errors: [], console_warnings: [], page_errors: [], websockets: [], cross_origin_requests: [], failed_requests: [] };
  page.on('console', (m) => {
    if (m.type() === 'error') rec.console_errors.push(m.text());
    if (m.type() === 'warning') rec.console_warnings.push(m.text());
  });
  page.on('pageerror', (e) => rec.page_errors.push(String(e)));
  page.on('websocket', (ws) => rec.websockets.push(ws.url()));
  page.on('request', (r) => { if (!r.url().startsWith(origin) && !r.url().startsWith('data:')) rec.cross_origin_requests.push(r.url()); });
  page.on('requestfailed', (r) => rec.failed_requests.push(`${r.url()} ${r.failure()?.errorText ?? ''}`));
  const t0 = Date.now();
  await page.goto(url);
  await page.waitForLoadState('networkidle', { timeout: 120_000 });
  return { browser, page, rec, t0 };
}

const texts = (page) => page.evaluate(() => {
  const t = (id) => document.querySelector(`[data-testid="${id}"]`)?.textContent ?? null;
  return {
    badge: t('mode-badge'), conn: t('live-conn'), probe: t('live-probe'),
    status: t('live-status-words'), last_check: t('live-last-check'),
  };
});

const result = {
  meta: { site: SITE, settle_ms: SETTLE_MS, started_utc: new Date().toISOString(), headless: true },
  views: [], recovery: null,
};
{
  const b = await chromium.launch();
  result.meta.browser = `chromium ${b.version()} (Playwright)`;
  await b.close();
}

for (const view of VIEWS) {
  const { browser, page, rec, t0 } = await open(`${SITE}?view=${view}`, 1400);
  try {
    await sleep(SETTLE_MS);
    const shown = await texts(page);
    if (view === 'live') await page.screenshot({ path: join(OUT, 'live_1400.png'), fullPage: false });
    result.views.push({ view, ms_observed: Date.now() - t0, ...rec, shown });
    console.log(view, JSON.stringify({ errors: rec.console_errors.length, page_errors: rec.page_errors.length, ws: rec.websockets.length, xo: rec.cross_origin_requests.length }));
  } finally { await browser.close(); }
}
{
  // The same Live view at phone width (layout check only).
  const { browser, page, rec } = await open(`${SITE}?view=live`, 390);
  try {
    await sleep(SETTLE_MS);
    await page.screenshot({ path: join(OUT, 'live_390.png'), fullPage: true });
    result.live_390 = { ...rec, shown: await texts(page), scroll_width: await page.evaluate(() => document.documentElement.scrollWidth) };
  } finally { await browser.close(); }
}

if (PORT) {
  const url = `${SITE}?view=live&live=${encodeURIComponent(`ws://localhost:${PORT}/ws`)}`;
  const { browser, page, rec, t0 } = await open(url, 1400);
  let stub = null;
  try {
    await sleep(7000);
    const offline = { at_ms: Date.now() - t0, websockets: rec.websockets.length, shown: await texts(page),
      console_errors: [...rec.console_errors], healthz_requests: rec.cross_origin_requests.filter((u) => u.endsWith('/healthz')).length };
    await page.screenshot({ path: join(OUT, 'live_recovery_offline.png') });
    stub = spawn('python3', [STUB, String(PORT)], { stdio: ['ignore', 'pipe', 'pipe'] });
    await new Promise((r) => stub.stdout.once('data', r));
    const tStub = Date.now();
    let connectedAt = null;
    while (Date.now() - tStub < 45_000) {
      if ((await texts(page)).conn === 'connected') { connectedAt = Date.now(); break; }
      await sleep(100);
    }
    await sleep(3000); // a few pings: still connected, still one socket
    const after = { stub_up_to_connected_ms: connectedAt ? connectedAt - tStub : null, websockets: rec.websockets,
      shown: await texts(page), healthz_requests: rec.cross_origin_requests.filter((u) => u.endsWith('/healthz')).length,
      console_errors_after_stub: rec.console_errors.slice(offline.console_errors.length), page_errors: rec.page_errors };
    await page.screenshot({ path: join(OUT, 'live_recovery_connected.png') });
    result.recovery = { url, offline, after };
    console.log('recovery', JSON.stringify({ offline_ws: offline.websockets, conn: after.shown.conn, ms: after.stub_up_to_connected_ms, ws: after.websockets.length }));
  } finally {
    stub?.kill();
    await browser.close();
  }
}

result.meta.finished_utc = new Date().toISOString();
result.summary = {
  views_with_console_errors: result.views.filter((v) => v.console_errors.length).map((v) => v.view),
  views_with_page_errors: result.views.filter((v) => v.page_errors.length).map((v) => v.view),
  total_console_errors: result.views.reduce((n, v) => n + v.console_errors.length, 0),
  total_page_errors: result.views.reduce((n, v) => n + v.page_errors.length, 0),
  live_websockets_on_load: result.views.find((v) => v.view === 'live')?.websockets.length ?? null,
};
writeFileSync(join(OUT, 'console_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...result }, null, 1));
console.log('summary', JSON.stringify(result.summary));
