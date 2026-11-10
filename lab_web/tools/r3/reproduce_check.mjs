// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R3.9: "Reproduce this paper" end to end on a site: open About, follow the Reproduce link (it runs on
 * opening), and read the page's own verdict (wb-link-check: the digest it computed vs the link's), which
 * must also be the committed digest (docs/paper/generated/reproduce.json).
 *
 *   node tools/r3/reproduce_check.mjs SITE OUT.json [--minutes N]
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const [site, out, ...rest] = process.argv.slice(2);
const minutes = rest.includes('--minutes') ? Number(rest[rest.indexOf('--minutes') + 1]) : 20;
const ref = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'docs', 'paper', 'generated', 'reproduce.json'), 'utf-8'));
const report = { site, committed_digest: ref.digest, runs: ref.runs, started: new Date().toISOString() };
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(site + '?view=about', { waitUntil: 'domcontentloaded' });
  const href = await page.getAttribute('[data-testid="reproduce-paper"]', 'href', { timeout: 60000 });
  const target = new URL(href, site);
  report.link_digest = target.searchParams.get('d');
  report.link_carries_committed_digest = report.link_digest === ref.digest;
  const t0 = Date.now();
  await page.goto(target.toString(), { waitUntil: 'domcontentloaded' });
  const verdict = page.locator('[data-testid="wb-link-check"]');
  await verdict.waitFor({ timeout: minutes * 60000 });
  report.seconds = Math.round((Date.now() - t0) / 1000);
  report.verdict = (await verdict.innerText()).slice(0, 400);
  report.ok = (await verdict.getAttribute('class'))?.includes('wb-ok') ?? false;
  report.errors = errors;
} catch (e) {
  report.error = String(e).slice(0, 400);
} finally {
  await browser.close();
  writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
}
console.log(JSON.stringify(report));
process.exit(report.ok && report.link_carries_committed_digest ? 0 : 1);
