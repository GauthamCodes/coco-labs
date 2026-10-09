// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 1's runs in the Arena viewer, in a real browser (M1.9): each of the
 * three recorded full-stack runs plays to its end labelled STACK, with its
 * measured results, the stack's annotations and the whole search revealed;
 * a glass-box trace plays labelled MODEL; no model worker is started for
 * any of them. Screenshots and console errors per run.
 *
 *   node tools/perf/replay_check.mjs --site URL --out DIR
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
const SITE = args.site ?? 'http://127.0.0.1:4174/coco-labs/';
const OUT = args.out ?? 'replay-out';
const RUNS = [['lab1c_astar', 'STACK'], ['lab1c_dijkstra', 'STACK'], ['lab1c_greedy', 'STACK'], ['bfs_no_path', 'MODEL'],
  ['arena_native', 'MODEL']];
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const out = { site: SITE, runs: {}, errors: [] };
try {
  for (const [id, want] of RUNS) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 1100 } });
    const errs = [];
    page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    page.on('pageerror', (e) => errs.push(String(e)));
    let workers = 0;
    page.on('worker', () => { workers += 1; });
    const t0 = Date.now();
    await page.goto(`${SITE}?view=arena&replay=${id}`);
    await page.waitForFunction(() => !!window.__cocoArena?.session()?.shownTick, null, { timeout: 60_000 });
    const firstMs = Date.now() - t0;
    await page.evaluate(() => window.__cocoArena.session().setSpeed(4));
    // play to the end (STACK at 4x) and let the search finish revealing
    await page.waitForFunction(() => {
      const st = window.__cocoArena.session().shownSearch;
      return !!st && st.final && st.cursor >= st.received;
    }, null, { timeout: 120_000 });
    // wait until the world track stops growing (the recording's end)
    let last = -1;
    for (let k = 0; k < 120; k += 1) {
      const h = await page.evaluate(() => window.__cocoArena.session().head);
      if (h === last) break;
      last = h;
      await page.waitForTimeout(1000);
    }
    const st = await page.evaluate(() => {
      const s = window.__cocoArena.session();
      const t = s.shownTick;
      return { head: s.head, ticks: s.history.length, cursor: s.shownSearch?.cursor, received: s.shownSearch?.received,
        pose: t.pose, truth: t.truth ?? null, mode: window.__cocoArena.mode(), client: window.__cocoArena.client === null ? null : 'started' };
    });
    const badge = (await page.getByTestId('evidence-badge').textContent()).trim();
    const results = want === 'STACK' ? (await page.getByTestId('stack-results').textContent()).trim() : null;
    const note = want === 'STACK' ? (await page.getByTestId('stack-note').textContent()).trim() : null;
    const links = await page.getByTestId('recorded-runs').locator('a').count();
    await page.screenshot({ path: join(OUT, `${id}.png`) });
    const pass = badge === want && st.mode === 'recording' && st.client === null && workers === 0 && st.cursor === st.received
      && (want === 'MODEL' ? st.ticks === 1 : st.ticks > 100 && !!st.truth && /tracking error/.test(results) && !!note)
      && links >= 11 && errs.length === 0;
    out.runs[id] = { pass, badge, first_shown_ms: firstMs, ...st, results, note, links, workers, errors: errs };
    out.errors.push(...errs);
    console.log(`${pass ? 'PASS' : 'FAIL'} ${id} ${JSON.stringify({ badge, ticks: st.ticks, events: st.received, first_shown_ms: firstMs, workers, errors: errs.length })}`);
    await page.close();
  }
} finally {
  await browser.close();
}
out.pass = Object.values(out.runs).every((r) => r.pass);
writeFileSync(join(OUT, 'replay_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass, errors: out.errors.length }));
process.exit(out.pass ? 0 : 1);
