// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Does asking a dead endpoint log a console error? (M0 fix A.2's premise.)
 * In headless Chromium, from a blank page with no CSP: a fetch to a refused
 * loopback port, a fetch to an unresolvable host, an opaque (no-cors) fetch
 * to the refused port, and a WebSocket to it. Prints JSON; writes nothing.
 *   node tools/perf/probe_noise.mjs [--port 8099]
 */

import { chromium } from 'playwright';

const i = process.argv.indexOf('--port');
const PORT = i > 0 ? Number(process.argv[i + 1]) : 8099;
const browser = await chromium.launch();
const page = await browser.newPage();
const seen = [];
page.on('console', (m) => seen.push(`${m.type()}: ${m.text()}`));
await page.goto('data:text/html,<p>probe</p>');
const cases = {
  fetch_refused: `fetch('http://localhost:${PORT}/healthz', { cache: 'no-store' })`,
  fetch_no_cors_refused: `fetch('http://localhost:${PORT}/healthz', { mode: 'no-cors', cache: 'no-store' })`,
  fetch_unresolvable: "fetch('https://coco-live.taile7cb60.ts.net/healthz', { cache: 'no-store', credentials: 'omit' })",
  websocket_refused: `new Promise((r) => { const w = new WebSocket('ws://localhost:${PORT}/ws'); w.onerror = r; w.onclose = r; })`,
};
const out = { browser: `chromium ${browser.version()}`, at_utc: new Date().toISOString(), cases: {} };
for (const [name, js] of Object.entries(cases)) {
  seen.length = 0;
  const outcome = await page.evaluate(`(async () => { try { await ${js}; return 'resolved'; } catch (e) { return String(e); } })()`);
  await page.waitForTimeout(500);
  out.cases[name] = { outcome, console: [...seen], console_errors: seen.filter((s) => s.startsWith('error')).length };
}
await browser.close();
console.log(JSON.stringify(out, null, 1));
