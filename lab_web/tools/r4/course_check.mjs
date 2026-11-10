// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4.7 / R4.8: the course on a real site, in Chromium.
 *  1. the home page: tracks, modules, the privacy statement; the glossary
 *  2. a predict step: a wrong pick shows its misconception note
 *  3. browser/native agreement: each case of NATIVE.json (tools/r4/native_grades.py) is entered on the
 *     site -- a file pasted into the editor, or slider keys -- and the grade's digest must equal native
 *  4. a completion link from the passed lessons, opened on the verify page, re-verifies them
 *
 *   node tools/r4/course_check.mjs SITE NATIVE.json OUT.json [--only CASE ...]
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'node:fs';

const [site, nativeFile, out, ...rest] = process.argv.slice(2);
const only = rest.includes('--only') ? rest.slice(rest.indexOf('--only') + 1) : null;
const native = JSON.parse(readFileSync(nativeFile, 'utf-8'));
const report = { site, started: new Date().toISOString(), steps: [], cases: {} };
const step = (name, ok, detail = {}) => { report.steps.push({ name, ok: !!ok, ...detail }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
try {
  if (!only) {
    await page.goto(site + '?view=learn', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="course-modules"]', { timeout: 60000 });
    const mods = await page.$$eval('[data-testid="course-modules"] > li', (l) => l.length);
    const tracks = await page.$$('[data-testid^="track-"]');
    const privacy = await page.textContent('[data-testid="course-privacy"]');
    step('home: 10 modules, 3 tracks, the privacy statement', mods === 10 && tracks.length === 3 && /No account, no analytics, no tracking/.test(privacy ?? ''), { mods, tracks: tracks.length });
    await page.goto(site + '?view=learn&page=glossary', { waitUntil: 'domcontentloaded' });
    const terms = await page.$$eval('[data-testid="glossary"] dt', (d) => d.length);
    step('glossary renders every term', terms >= 50, { terms });
    await page.goto(site + '?view=learn&lesson=astar-vs-dijkstra&step=predict', { waitUntil: 'domcontentloaded' });
    await page.click('[data-testid="option-0"]', { timeout: 60000 });
    const note = await page.textContent('[data-testid="misconception"]');
    step('predict: a wrong pick explains the misconception', (note ?? '').length > 40, { note: note?.slice(0, 80) });
  }
  for (const [k, c] of Object.entries(native)) {
    if (only && !only.includes(k)) continue;
    const t0 = Date.now();
    await page.goto(`${site}?view=learn&lesson=${c.lesson}&step=try`, { waitUntil: 'domcontentloaded' });
    if (c.answer.code !== undefined) {
      await page.waitForSelector('.cm-content', { timeout: 60000 });
      await page.click('.cm-content');
      await page.keyboard.press('Control+A');
      await page.keyboard.press('Delete');
      await page.keyboard.insertText(c.answer.code);
    } else if (c.answer.params) {
      for (const [p, v] of Object.entries(c.answer.params)) {
        const s = page.locator(`[data-testid="slider-${p}"]`);
        await s.focus();
        await page.keyboard.press('Home');
        const min = Number(await s.getAttribute('min')), stepv = Number(await s.getAttribute('step'));
        for (let i = 0; i < Math.round((v - min) / stepv); i++) await page.keyboard.press('ArrowRight');
        const shown = Number(await page.textContent(`[data-testid="value-${p}"]`));
        if (Math.abs(shown - v) > 1e-9) throw new Error(`${k}: slider shows ${shown}, wanted ${v}`);
      }
    }
    await page.click('[data-testid="check"]');
    const verdict = page.locator('[data-testid="check-result"] [data-testid="verdict"]');
    await verdict.waitFor({ timeout: 10 * 60000 });
    const digest = await verdict.getAttribute('data-digest');
    const passed = (await verdict.getAttribute('data-passed')) === 'true';
    const same = digest === c.digest && passed === c.passed;
    report.cases[k] = { native: c.digest, browser: digest, passed, native_passed: c.passed, same, seconds: Math.round((Date.now() - t0) / 1000) };
    step(`agreement ${k}: browser ${passed ? 'pass' : 'fail'} = native ${c.passed ? 'pass' : 'fail'}, digest equal`, same, report.cases[k]);
  }
  if (!only) {
    await page.goto(site + '?view=learn&module=find-a-path', { waitUntil: 'domcontentloaded' });
    await page.click('[data-testid="make-completion"]', { timeout: 60000 });
    const link = await page.getAttribute('[data-testid="completion-link"]', 'href', { timeout: 30000 });
    await page.goto(link, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => /Re-verified/.test(document.querySelector('[data-testid="verify-status"]')?.textContent ?? ''), null, { timeout: 10 * 60000 });
    const status = await page.textContent('[data-testid="verify-status"]');
    const m = /Re-verified: (\d+) of (\d+)/.exec(status ?? '');
    step('a completion link re-verifies its passed answers', m && m[1] === m[2] && Number(m[2]) >= 1, { status });
  }
  step('no page errors', errors.length === 0, { errors });
} catch (e) {
  step('ran to the end', false, { error: String(e).slice(0, 400) });
} finally {
  await browser.close();
  report.finished = new Date().toISOString();
  writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
}
process.exit(report.steps.every((s) => s.ok) ? 0 : 1);
