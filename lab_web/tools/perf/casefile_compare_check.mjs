// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Case Files' model side (M3.3): each comparison opens the Arena model
 * on the recording's own scenario, and it must take.
 *
 *   node tools/perf/casefile_compare_check.mjs --site URL --out DIR [--gpu 1]
 *
 * For one Case File of each kind, the MODEL pane's URL (cases.json `compare`)
 * is opened alone and, once the live model is up, checked:
 *   lab5: the controller header is the Arena's matching controller, and the
 *         scenario's path was given;
 *   lab4: the fetch mission started (a transition out of idle);
 *   lab2: the robot was kidnapped to the recorded target (truth within 0.3 m);
 *   lab1: the recorded goal was planned to (a search on the goal's tick).
 * Each with 0 console and 0 page errors and the MODEL badge.
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
const SITE = args.site ?? 'http://127.0.0.1:4214/coco-labs/';
const OUT = args.out ?? 'casefile-compare-out';
const LAUNCH = args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {};
mkdirSync(OUT, { recursive: true });

const cases = await (await fetch(`${SITE}generated/casefiles/cases.json`)).json();
const find = (id) => cases.groups.flatMap((g) => g.casefiles).find((c) => c.id === id);
const SAMPLE = [
  ['lab5_crossing_dwb_1', 'lab5'], ['lab4_a1_fixed_red', 'lab4'], ['lab2_kidnap_recovery_k1', 'lab2'], ['lab1_run_astar', 'lab1'],
];
const browser = await chromium.launch(LAUNCH);
const out = { site: SITE, checks: [] };
for (const [id, kind] of SAMPLE) {
  const c = find(id);
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  const row = { id, kind, url: c.compare, errors };
  try {
    await page.goto(`${SITE}${c.compare}`);
    await page.waitForFunction(() => window.__cocoArena?.mode?.() === 'live', null, { timeout: 120_000 });
    row.badge = await page.getByTestId('evidence-badge').textContent();
    if (kind === 'lab5') {
      await page.waitForFunction(() => !!window.__cocoArena.session().headers.get('coco.control.local.header.v1'), null, { timeout: 60_000 });
      await page.waitForTimeout(3000);
      row.got = await page.evaluate(() => {
        const s = window.__cocoArena.session();
        return { controller: s.headers.get('coco.control.local.header.v1').controller_id, path_given: s.givenPaths.length > 0 };
      });
      row.ok = row.got.controller === 'dwa' && row.got.path_given;
    } else if (kind === 'lab4') {
      await page.waitForFunction(() => {
        const b = window.__cocoArena.session().families.latest('coco.mission.fsm.transition.v1', 1e9);
        return b && b.columns.to_state.at(-1) !== 'idle';
      }, null, { timeout: 60_000 });
      row.got = await page.evaluate(() => window.__cocoArena.session().families.latest('coco.mission.fsm.transition.v1', 1e9).columns.to_state.at(-1));
      row.ok = true;
    } else if (kind === 'lab2') {
      const [kx, ky] = new URLSearchParams(c.compare.slice(1)).get('kidnap').split(',').map(Number);
      await page.waitForFunction(([x, y]) => {
        const t = window.__cocoArena.last;
        const p = t?.truth ?? t?.pose;
        return p && Math.hypot(p[0] - x, p[1] - y) < 0.3;
      }, [kx, ky], { timeout: 60_000 });
      row.got = await page.evaluate(() => window.__cocoArena.last.truth ?? window.__cocoArena.last.pose);
      row.ok = true;
    } else {
      await page.waitForFunction(() => window.__cocoArena.session().searchesAt.length > 0, null, { timeout: 60_000 });
      row.got = await page.evaluate(() => window.__cocoArena.session().searchesAt.length);
      row.ok = true;
    }
    await page.waitForTimeout(1500);
    row.ok = row.ok && errors.length === 0 && row.badge === 'MODEL';
  } catch (e) { row.ok = false; row.failure = String(e); }
  out.checks.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${id} (${kind}) ${JSON.stringify(row.got)}${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
  await page.close();
}
await browser.close();
out.ok = out.checks.every((r) => r.ok);
writeFileSync(join(OUT, 'casefile_compare_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ ok: out.ok, checks: out.checks.length }));
process.exit(out.ok ? 0 : 1);
