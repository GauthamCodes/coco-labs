// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.7: Compare on chosen scenarios shows the experiments' own numbers. Against the
 * committed COCO-Bench reference results (docs/v2/r1/bench/depot-nav-100/planning/):
 *   1. Compare on the Depot, scenario source = depot-nav-100, pair 1: panes A* and Dijkstra
 *      show exactly the reference expansions and path length for that scenario;
 *   2. Next: pair 2, the same check;
 *   3. a run opened from a results-table link (#xexp=...&xrun=i) opens that run first, with
 *      its scenario's other runs beside it, and the same numbers.
 *
 *   node tools/r1/compare_check.mjs SITE OUT.json
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const [site, out] = process.argv.slice(2);
const repo = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const ref = join(repo, 'docs', 'v2', 'r1', 'bench', 'depot-nav-100', 'planning');
const rows = readFileSync(join(ref, 'results.csv'), 'utf-8').trim().split('\n');
const head = rows[0].split(',');
const csv = rows.slice(1).map((r) => Object.fromEntries(r.split(',').map((v, i) => [head[i], v])));
const want = (algo, scenario) => csv.find((r) => r.algorithm === algo && r.scenario === scenario);
const spec = JSON.parse(readFileSync(join(ref, 'spec.json'), 'utf-8'));
const report = { site, when: new Date().toISOString(), checks: [], pass: false };
const check = (name, ok, extra) => { report.checks.push({ name, ok, ...extra }); console.log(ok ? 'ok  ' : 'FAIL', name, JSON.stringify(extra)); };
const b = await chromium.launch();
const pane = async (p, k) => p.locator('.compare-results > div').nth(k).innerText();
const numbers = (t) => ({ expansions: Number((/([\d,]+) expansions/.exec(t)?.[1] ?? 'NaN').replace(/,/g, '')), length: Number(/([\d.]+) m planned/.exec(t)?.[1]) });
try {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto(`${site}?view=compare&world=depot`);
  await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 300000 });
  await p.getByRole('button', { name: 'Controls' }).click({ timeout: 2000 }).catch(() => {}); // phones only
  for (const [step, scen] of [['suite pair 1', 's001'], ['next pair', 's002']]) {
    if (step === 'suite pair 1') {
      await p.locator('select[aria-label="Scenario source"]').selectOption('suite');
      await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 300000 });
      await p.locator('select[aria-label="Suite"]').selectOption('depot-nav-100');
    }
    else await p.getByRole('button', { name: 'Next', exact: true }).click();
    await p.waitForFunction((s) => document.querySelector('[data-testid="compare-scenario-note"]')?.textContent?.startsWith(s), scen, { timeout: 300000 });
    await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 300000 });
    for (const [k, algo] of [[0, 'astar'], [1, 'dijkstra']]) {
      const got = numbers(await pane(p, k)), w = want(algo, scen);
      check(`${step}: ${algo} on ${scen}`, got.expansions === Number(w.expansions) && Math.abs(got.length - Number(w.path_length_m)) < 0.006,
        { compare: got, reference: { expansions: Number(w.expansions), path_length_m: Number(w.path_length_m) } });
    }
  }
  const r = csv.find((x) => x.algorithm === 'dijkstra' && x.scenario === 's003');
  const b64 = Buffer.from(JSON.stringify(spec)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  await p.goto(`${site}?view=compare&world=depot&xrun=${r.run}#xexp=${b64}`);
  await p.waitForFunction(() => document.querySelector('[data-testid="compare-scenario-note"]')?.textContent?.startsWith('s003'), null, { timeout: 300000 });
  await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 300000 });
  const first = await pane(p, 0);
  check('table link: the run opens first', /dijkstra/i.test(first) && numbers(first).expansions === Number(r.expansions), { compare: numbers(first), reference: Number(r.expansions) });
  // every shipped world opens in Compare
  for (const w of ['v1', 'v2', 'depot', 'depot_colours']) {
    const q = await b.newPage({ viewport: { width: 1440, height: 900 } });
    const errs = []; q.on('pageerror', (e) => errs.push(String(e)));
    await q.goto(`${site}?view=compare&world=${w}`);
    const ok = await q.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 300000 }).then(() => true).catch(() => false);
    check(`world ${w} opens and compares`, ok && !errs.length, { errors: errs.slice(0, 2) });
    await q.close();
  }
  // a control scenario replays (a seeded random pair on the Proving Ground), then "Turn this into an experiment"
  const c = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await c.goto(`${site}?view=compare&world=v1`);
  await c.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 300000 });
  await c.locator('select[aria-label="Family"]').selectOption('control');
  await c.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 300000 });
  await c.locator('select[aria-label="Scenario source"]').selectOption('random');
  await c.waitForFunction(() => document.querySelector('[data-testid="compare-scenario-note"]')?.textContent?.startsWith('s001'), null, { timeout: 600000 });
  await c.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout: 600000 });
  const statuses = [await pane(c, 0), await pane(c, 1)].map((t) => t.split('\n').pop());
  check('control: a seeded pair replays to an outcome in both panes', statuses.every((s) => /succeeded|timeout|no_|failed|stopped/.test(s)), { statuses });
  await c.getByTestId('compare-to-experiment').click();
  await c.waitForSelector('[data-testid="workbench"] .wb-builder', { timeout: 120000 });
  const handed = JSON.parse(await c.locator('.wb-text textarea').inputValue());
  check('Turn this into an experiment: the builder opens with the panes', handed.family === 'control' && handed.algorithms.length === 2 && handed.scenarios.kind === 'sampled', { spec: { family: handed.family, algorithms: handed.algorithms.map((x) => x.name), scenarios: handed.scenarios } });
  report.pass = report.checks.every((c) => c.ok);
} catch (e) { report.error = String(e); }
await b.close();
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
process.exit(report.pass ? 0 : 1);
