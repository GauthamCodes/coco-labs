// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M3.6: 100 Play submissions, scored in the browser, reproduced in three
 * browsers, and verified by `coco verify` (the M3 prompt's B.3
 * "Reproducibility" row).
 *
 *   node tools/perf/play_verify.mjs score --site URL --subs SUBS.json --out DIR [--gpu 1]
 *       Chromium scores every submission with the page's own scorer
 *       (window.__cocoPlay.score: coco_lab.play in the Arena worker) and
 *       writes DIR/links.json: each submission's challenge link, carrying
 *       the result hash the browser computed.
 *   node tools/perf/play_verify.mjs reproduce --site URL --out DIR --browser chromium|firefox|webkit [--webkit-exe PATH]
 *       Opens every link (a fresh page each) and records whether the page,
 *       re-scoring the link's inputs, says "Reproduced exactly".
 *   node tools/coco.mjs verify --file DIR/links.json --out DIR/verify_node.json
 *       Re-scores every link in Node.
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, firefox, webkit } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const [mode, ...rest] = process.argv.slice(2);
const args = Object.fromEntries(rest.reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4214/coco-labs/';
const OUT = args.out ?? 'play-verify-out';
mkdirSync(OUT, { recursive: true });

// the same encoding as src/play/share.ts's encodeScore
const b64url = (s) => Buffer.from(s, 'utf-8').toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const link = (s, r) => `${SITE}?view=play&c=${s.challenge}&l=${s.level}&s=${b64url(JSON.stringify({ v: 1, h: s.level_hash, i: s.inputs, r }))}`;

if (mode === 'score') {
  const subs = JSON.parse(readFileSync(args.subs, 'utf-8')).submissions;
  const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
  const page = await browser.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(`${SITE}?view=play&c=search-the-bays&l=no-idea`);
  await page.waitForFunction(() => !!window.__cocoPlay?.score, null, { timeout: 180_000 });
  const rows = [];
  for (const s of subs) {
    const r = await page.evaluate(async (sub) => {
      const t0 = performance.now();
      try { const x = await window.__cocoPlay.score(sub); return { hash: x.hash, stars: x.stars, valid: x.valid, score: x.score, ms: performance.now() - t0 }; }
      catch (e) { return { error: String(e), ms: performance.now() - t0 }; }
    }, s);
    rows.push({ challenge: s.challenge, level: s.level, ...r, link: r.hash ? link(s, r.hash) : null });
    console.log(`${r.error ? 'ERROR' : 'scored'} ${s.challenge}/${s.level} ${r.error ?? `${r.score.name} ${r.score.value} ${r.stars}★ ${r.hash.slice(0, 12)}`} (${Math.round(r.ms)} ms)`);
  }
  await browser.close();
  const out = { what: 'Play submissions scored in Chromium by the page (window.__cocoPlay.score)', site: SITE, errors, rows,
    links: rows.map((r) => r.link).filter(Boolean) };
  writeFileSync(join(OUT, 'links.json'), JSON.stringify({ ...out, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
  console.log(`${out.links.length} of ${subs.length} scored, ${errors.length} console errors`);
  process.exit(out.links.length === subs.length && !errors.length ? 0 : 1);
} else if (mode === 'reproduce') {
  const name = args.browser ?? 'chromium';
  const engine = { chromium, firefox, webkit }[name];
  const launch = name === 'chromium' && args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {};
  if (args['webkit-exe']) launch.executablePath = args['webkit-exe'];
  const { rows } = JSON.parse(readFileSync(join(OUT, 'links.json'), 'utf-8'));
  const browser = await engine.launch(launch);
  const res = [];
  const t0 = Date.now();
  for (const r of rows) {
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('pageerror', (e) => errors.push(String(e)));
    const t = Date.now();
    const row = { challenge: r.challenge, level: r.level, expected: r.hash, errors };
    try {
      await page.goto(r.link);
      await page.getByTestId('play-reproduced').waitFor({ timeout: 300_000 });
      row.text = await page.getByTestId('play-reproduced').textContent();
      row.hash = await page.getByTestId('play-result').getAttribute('data-hash');
      row.exact = /Reproduced exactly/.test(row.text) && row.hash === r.hash;
    } catch (e) { row.exact = false; row.failure = String(e); }
    row.ms = Date.now() - t;
    row.ok = row.exact && errors.length === 0;
    res.push(row);
    console.log(`${row.ok ? 'exact' : 'FAIL '} ${r.challenge}/${r.level} ${row.ms} ms${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
    await context.close();
  }
  const version = browser.version();
  await browser.close();
  const out = { browser: name, version, site: SITE, seconds: (Date.now() - t0) / 1000,
    exact: res.filter((r) => r.exact).length, ok: res.filter((r) => r.ok).length, links: res.length, rows: res };
  writeFileSync(join(OUT, `reproduce_${name}.json`), JSON.stringify({ ...out, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
  console.log(`${name} ${version}: ${out.exact} of ${out.links} reproduced exactly, ${out.ok} with 0 errors, ${out.seconds} s`);
  process.exit(out.ok === out.links ? 0 : 1);
} else {
  console.error('mode: score | reproduce');
  process.exit(2);
}
