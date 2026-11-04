// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.4: the end-to-end reproducibility check. In one browser context: build an experiment
 * in the Workbench (its JSON editor), run it, copy its link. In a FRESH context (no shared
 * storage, cache or workers): open the link, let it re-run, and require that
 *   - the page says "Reproduced exactly" (its digest equals the one in the link),
 *   - the runs table and the summary table are identical text,
 *   - Verify (a random 10% re-run) finds every hash chain and count matching.
 *
 *   node tools/r1/link_e2e.mjs SITE OUT.json [--browser chromium|firefox|webkit] [--webkit-exe PATH] [--long]
 *
 * --long adds 2,000 characters of notes so the link no longer fits ?exp= and travels
 * deflated in the fragment (#expz=).
 */
import { chromium, firefox, webkit } from 'playwright';
import { writeFileSync } from 'node:fs';

const [site, out, ...rest] = process.argv.slice(2);
const which = rest.includes('--browser') ? rest[rest.indexOf('--browser') + 1] : 'chromium';
const engine = { chromium, firefox, webkit }[which];
const SPEC = { schema: 'coco.experiment.v1', title: 'E2E: A* against Dijkstra', world: 'coco_arena_v1', family: 'planning', seed: 4,
  algorithms: [{ name: 'astar' }, { name: 'dijkstra' }, { name: 'weighted_astar', params: { heuristic_weight: 3 } }],
  scenarios: { kind: 'sampled', n: 8, seed: 4, min_separation_m: 3 } };
if (rest.includes('--long')) SPEC.notes = 'A long note so this link is deflated into the fragment. '.repeat(36);
const report = { site, browser: which, long: rest.includes('--long'), when: new Date().toISOString(), steps: [], pass: false };
const step = (name, ok, extra = {}) => { report.steps.push({ name, ok, ...extra }); console.log(ok ? 'ok  ' : 'FAIL', name, JSON.stringify(extra).slice(0, 200)); if (!ok) throw new Error(name); };
const text = (page, sel) => page.locator(sel).innerText();
const webkitExe = rest.includes('--webkit-exe') ? rest[rest.indexOf('--webkit-exe') + 1] : null;
const browser = await engine.launch(which === 'webkit' && webkitExe ? { executablePath: webkitExe } : {});
try {
  const a = await browser.newContext({ serviceWorkers: 'block', permissions: which === 'chromium' ? ['clipboard-read', 'clipboard-write'] : [] });
  const pa = await a.newPage();
  const errors = [];
  pa.on('pageerror', (e) => errors.push(String(e)));
  await pa.goto(`${site}?view=workbench`);
  await pa.locator('.wb-text summary').click();
  await pa.locator('.wb-text textarea').fill(JSON.stringify(SPEC, null, 2));
  await pa.getByRole('button', { name: 'Apply the text' }).click();
  await pa.locator('.wb-runbar button[type=submit]').click();
  await pa.locator('[data-testid="wb-digest"]').waitFor({ timeout: 600000 });
  const digestA = await text(pa, '[data-testid="wb-digest"]');
  const runsA = await text(pa, '[data-testid="wb-runs"]');
  const summaryA = await text(pa, '[data-testid="wb-summary"]');
  step('built and ran in context A', true, { digest: digestA, rows: runsA.split('\n').length });
  await pa.getByRole('button', { name: 'Copy link' }).click();
  const link = await pa.locator('[data-testid="wb-link"]').inputValue();
  step('copied the link', /view=workbench/.test(link) && /[?&]d=[0-9a-f]{64}/.test(link) && link.includes('#expz=') === rest.includes('--long'), { link_chars: link.length, compressed: link.includes('#expz=') });
  await a.close();

  const b = await browser.newContext({ serviceWorkers: 'block' });
  const pb = await b.newPage();
  pb.on('pageerror', (e) => errors.push(String(e)));
  await pb.goto(link);
  await pb.locator('[data-testid="wb-link-check"]').waitFor({ timeout: 600000 });
  const check = await text(pb, '[data-testid="wb-link-check"]');
  step('fresh context: reproduced exactly', check.startsWith('Reproduced exactly'), { check });
  step('fresh context: identical runs table', (await text(pb, '[data-testid="wb-runs"]')) === runsA);
  step('fresh context: identical summary', (await text(pb, '[data-testid="wb-summary"]')) === summaryA);
  step('fresh context: identical digest', (await text(pb, '[data-testid="wb-digest"]')).split(' · ')[0] === digestA.split(' · ')[0]);
  await pb.locator('[data-testid="wb-verify"]').click();
  await pb.locator('[data-testid="wb-verify-result"]').waitFor({ timeout: 600000 });
  const verify = await text(pb, '[data-testid="wb-verify-result"]');
  step('Verify: every re-run matches', /every hash chain and count matches/.test(verify), { verify });
  step('no page errors', errors.length === 0, { errors: errors.slice(0, 3) });
  report.pass = true;
} catch (e) {
  report.error = String(e);
} finally {
  await browser.close();
  writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
}
process.exit(report.pass ? 0 : 1);
