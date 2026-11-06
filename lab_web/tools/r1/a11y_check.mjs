// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.3: accessibility of the Workbench and Learn pages -- M5.11's audit (tools/perf/
 * m511_accessibility.mjs, copied verbatim below): every visible text node's contrast
 * against its composed background (AA: 4.5, large text 3), every control focusable,
 * reduced motion honoured; dark and light themes; desktop and emulated phone landscape.
 * The results view is audited with a small experiment finished on the page.
 *
 *   node tools/r1/a11y_check.mjs SITE OUT_DIR [--views workbench,benchmarks,datasets,learn]
 *   (R2: also studio,leaderboard)
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const VIEWS = { workbench: '?view=workbench', benchmarks: '?view=workbench&tab=benchmarks', datasets: '?view=workbench&tab=datasets', learn: '?view=learn',
  // R2: the Algorithm Studio and the Leaderboard (opt-in with --views; the default set is R1's)
  studio: '?view=workbench&tab=studio', leaderboard: '?view=workbench&tab=leaderboard' };
const R2_WAIT = { '?view=workbench&tab=studio': '[data-testid="studio"]', '?view=workbench&tab=leaderboard': '[data-testid="leaderboard"] h2' };
const DEFAULT_VIEWS = 'workbench,benchmarks,datasets,learn';
const views = (rest.includes('--views') ? rest[rest.indexOf('--views') + 1] : DEFAULT_VIEWS).split(',').map((v) => VIEWS[v]);
mkdirSync(out, { recursive: true });
const audit = () => {
  const rgb = s => { const n = s.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0, 0]; const scale = s.startsWith('color(srgb') ? 255 : 1; return [n[0] * scale, n[1] * scale, n[2] * scale, n[3] ?? 1]; }, blend = (a, b, alpha = a[3]) => [0, 1, 2].map(i => a[i] * alpha + b[i] * (1 - alpha)), lum = c => c.map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0), ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const visible = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('dialog:not([open])') && !e.closest('details:not([open]) > :not(summary)'); };
  const failures = [], checked = [], walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let text;
  while (text = walker.nextNode()) {
    const e = text.parentElement; if (!e || !text.textContent.trim() || e.closest('script,style,svg') || !visible(e) || e.closest(':disabled')) continue;
    const style = getComputedStyle(e), layers = []; let opacity = 1;
    for (let n = e; n; n = n.parentElement) { const s = getComputedStyle(n); opacity *= Number(s.opacity); layers.push(rgb(s.backgroundColor)); }
    let bg = [255, 255, 255]; for (const layer of layers.reverse()) bg = blend(layer, bg);
    const fg = rgb(style.color), effective = blend(fg, bg, fg[3] * opacity), contrast = ratio(effective, bg), size = parseFloat(style.fontSize), large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700), minimum = large ? 3 : 4.5;
    const item = { text: text.textContent.trim().slice(0, 90), tag: e.tagName, foreground: style.color, background: bg, contrast, minimum, size }; checked.push(item); if (contrast + 0.01 < minimum) failures.push(item);
  }
  const targets = [...document.querySelectorAll('button,a[href],input,select,textarea,summary')].filter(e => visible(e) && !e.disabled && !e.closest(':disabled'));
  const small = targets.filter(e => { const r = e.getBoundingClientRect(); return r.height < 24 && !e.closest('table,p,li,figcaption'); }).map(e => e.outerHTML.slice(0, 120));
  return { checked: checked.length, failures, nonFocusable: targets.filter(e => e.tabIndex < 0).map(e => e.outerHTML.slice(0, 150)), controls: targets.length, small_targets: small,
    scroll: document.documentElement.scrollWidth, width: window.innerWidth };
};
const SPEC = { schema: 'coco.experiment.v1', title: 'A11y: A* against Dijkstra', world: 'coco_arena_v1', family: 'planning', seed: 2,
  algorithms: [{ name: 'astar' }, { name: 'dijkstra' }], scenarios: { kind: 'sampled', n: 8, seed: 2, min_separation_m: 3 } };
const report = { site, when: new Date().toISOString(), pages: [], errors: [] };
const b = await chromium.launch();
try {
  for (const [profile, opts] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['phone-landscape', nothingPhone1(true)]]) {
    for (const theme of ['dark', 'light']) {
      for (const view of views) {
        const ctx = await b.newContext({ ...opts, reducedMotion: 'reduce', serviceWorkers: 'block' });
        const p = await ctx.newPage(); p.on('pageerror', e => report.errors.push(String(e)));
        await p.goto(`${site}${view}&theme=${theme}`);
        await p.waitForSelector(R2_WAIT[view] ?? (view.includes('learn') ? '[data-mission]' : view.includes('tab=') ? '.wb-section h2' : '.wb-builder'), { timeout: 120000 });
        if (view === '?view=workbench') {
          await p.locator('.wb-text summary').click();
          await p.locator('.wb-text textarea').fill(JSON.stringify(SPEC));
          await p.getByRole('button', { name: 'Apply the text' }).click();
          await p.locator('.wb-runbar button[type=submit]').click();
          await p.locator('[data-testid="wb-digest"]').waitFor({ timeout: 600000 });
        } else if (view.includes('tab=')) await p.waitForTimeout(1500);
        const result = await p.evaluate(audit);
        report.pages.push({ profile, theme, view, ...result, reducedMotion: await p.evaluate(() => document.documentElement.dataset.motion) });
        await p.screenshot({ path: `${out}/${profile}-${theme}-${view.replace(/[^a-z]+/g, '_')}.png`, scale: 'css', fullPage: true });
        await ctx.close();
      }
    }
  }
  report.passed = report.errors.length === 0 && report.pages.every(r => r.failures.length === 0 && r.nonFocusable.length === 0 && r.reducedMotion === 'reduced' && r.scroll <= r.width);
} catch (e) { report.errors.push(String(e)); report.passed = false; }
await b.close();
writeFileSync(`${out}/a11y.json`, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ passed: report.passed, pages: report.pages.map(r => [r.profile, r.theme, r.view, r.checked, r.failures.length, r.nonFocusable.length, r.scroll <= r.width]), errors: report.errors.slice(0, 3) }));
process.exit(report.passed ? 0 : 1);
