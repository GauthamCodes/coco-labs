// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.6: Fetch Rush, played through the page's own controls in a real browser:
 * AUTO (F) to the order's object, GRAB (G) when the button lights, AUTO to the
 * drop zone, DROP (G), until a delivery is counted or the clock runs out. Then
 * the session's record (spec, seed, input log) and hash chain are saved, for
 * tools/g1/game_node.mjs --record (Pyodide in Node) and tools/g1/game_parity.py
 * (CPython) to replay.
 *
 *   node tools/g1/fetch_play.mjs SITE OUTDIR [--deliveries N] [--results]
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const [site, out, ...rest] = process.argv.slice(2);
const WANT = rest.includes('--deliveries') ? Number(rest[rest.indexOf('--deliveries') + 1]) : 1;
mkdirSync(out, { recursive: true });
const b = await chromium.launch({ ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await b.newContext({ viewport: { width: 960, height: 540 } });
const p = await ctx.newPage();
const errors = [], log = [];
p.on('pageerror', (e) => errors.push(String(e)));
p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
await p.goto(`${site}?view=play&game=fetch_rush&seed=1&tier=low`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 180000 });
await p.click('[data-testid="g1-play"]');
const state = () => p.evaluate(() => { const t = window.__cocoGame.tick; const pr = document.querySelector('[data-testid="hud-primary"]'); return t ? { tick: t.tick, arrived: t.arrived, source: t.source, mode: t.mode, a: t.game?.assist, f: t.game?.fetch, primary: pr?.getAttribute('aria-label'), enabled: pr?.getAttribute('aria-disabled') === 'false' } : null; });
const until = async (fn, label, ms = 600000) => { const t0 = Date.now(); for (;;) { const s = await state(); if (s && fn(s)) { log.push([label, s.tick]); return s; } if (Date.now() - t0 > ms) { log.push([label + ' TIMEOUT', s?.tick]); return s; } await p.waitForTimeout(250); } };
await until((s) => s.tick > 2, 'started');
let s;
/** AUTO, checked: the model must take the goal (mode 'goal'); a press the page did not act on is logged and retried. */
async function auto(label) {
  for (let tries = 0; tries < 3; tries++) {
    await p.keyboard.press('KeyF');
    const s2 = await until((x) => x.mode === 'goal' || x.f?.over, label + ' (AUTO taken)', 8000);
    if (s2?.mode === 'goal' || s2?.f?.over) return;
    log.push(['AUTO press not acted on, retrying', s2?.tick]);
  }
}
for (let k = 0; k < WANT; k++) {
  await auto('to the object');
  s = await until((x) => x.f?.over || (x.tick > 5 && x.source !== 'planner' && x.enabled && /GRAB/.test(x.primary)), 'at the object (GRAB lit)');
  if (s.f?.over) break;
  await p.keyboard.press('KeyG');
  s = await until((x) => x.f?.over || !!x.a?.carried || (x.a?.phase === 'idle' && x.a?.reason && !/ok|holds/.test(x.a.reason)), 'carried');
  if (!s.a?.carried) break;
  await p.waitForTimeout(500);
  await auto('to the drop zone');
  s = await until((x) => x.f?.over || (x.enabled && /DROP/.test(x.primary)), 'in the drop zone (DROP lit)');
  if (s.f?.over) break;
  await p.keyboard.press('KeyG');
  s = await until((x) => x.f?.over || x.f?.deliveries > k, 'delivered');
}
await p.screenshot({ path: `${out}/after.png` });
if (rest.includes('--results')) {
  // play on to the end of the three minutes: the results screen (stars from coco_lab.games.stars)
  await p.waitForSelector('[data-testid="g1-results"]', { timeout: 900000 });
  await p.waitForTimeout(800);
  await p.screenshot({ path: `${out}/results.png` });
}
const rec = await p.evaluate(() => window.__cocoGame.session.query('record'));
const stars = await p.evaluate(() => window.__cocoGame.session.query('stars'));
writeFileSync(`${out}/browser_record.json`, JSON.stringify({ ...rec, scorecard: stars.card, log, errors, final: s, browser: 'Chromium (Playwright), SwiftShader', note: 'Pyodide in the browser worker; MODEL' }, null, 1) + '\n');
console.log(JSON.stringify({ log, deliveries: stars.card?.deliveries, contacts: stars.card?.contacts, ticks: rec.record.ticks, errors }));
await b.close();
