// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * Fetch by colour (owner request 2026-10-24), played in a real browser through the page's own
 * controls, for each colour: the mode card's chip opens the colour's round, PLAY, AUTO (F) to the
 * rod, GRAB (G) when it lights, AUTO to Dispatch, DROP (G), the results screen. Checks that the
 * delivered rod is the chosen colour (window.__cocoGame's tick and the glue's scorecard), that no
 * toast is drawn over the results (and whether the results card fits without scrolling), that
 * the AUTO planner chooser still adds &planner= to the chips, and that the page logged no error.
 * Saves each run's record (spec id, seed, input log, hash chain) for a CPython replay.
 *
 *   G1_GPU=nvidia node tools/g2/fetch_colour_check.mjs SITE OUTDIR [--colours red,green] [--phone] [--shots] [--race]
 *
 * --phone: the emulated Nothing Phone (1) in landscape (tools/phone/nothing-phone-1.mjs; viewport,
 * touch and user agent only -- no CPU throttle, these are looks, not measurements).
* --race (G2): Race Nav2 -- the colour card's RACE NAV2 link, then the race chooser's chip for the
 * colour (offered only for a colour with a recorded Gazebo + Nav2 run); requires the STACK race
 * chip while playing and the three-way card (you, the model's planner, Nav2 in Gazebo) on results.
 * --shots: screenshots of the mode card, the row of rods, COCO carrying a rod and the results
 * (the first colour), as OUTDIR/<profile>-<n>-<name>.png.
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { launchOptions, renderer } from '../g1/gpu.mjs';
import { DEVICE_NAME, nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const COLOURS = opt('--colours', 'red,green,blue,yellow').split(',');
const PHONE = rest.includes('--phone'), SHOTS = rest.includes('--shots'), RACE = rest.includes('--race');
const profile = (PHONE ? 'phone-landscape' : 'desktop') + (RACE ? '-race' : '');
mkdirSync(out, { recursive: true });
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ ...(PHONE ? nothingPhone1(true) : { viewport: { width: 1440, height: 900 } }), serviceWorkers: 'block' });
const p = await ctx.newPage();
const errors = [];
p.on('pageerror', (e) => errors.push(String(e)));
p.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
const report = { site, profile, device: PHONE ? `${DEVICE_NAME} (emulated viewport, landscape; no CPU throttle)` : 'desktop 1440 x 900', gpu: process.env.G1_GPU || 'software',
  renderer: null, when: new Date().toISOString(), planner_links: null, runs: {}, shots: [], errors };
let shot = 0;
const snap = async (name) => { shot += 1; const f = `${profile}-${shot}-${name}.png`; await p.screenshot({ path: `${out}/${f}` }); report.shots.push(f); };
const state = () => p.evaluate(() => { const g = window.__cocoGame; const t = g?.tick; const pr = document.querySelector('[data-testid="hud-primary"]');
  return t ? { tick: t.tick, source: t.source, mode: t.mode, a: t.game?.assist, f: t.game?.fetch, primary: pr?.getAttribute('aria-label') ?? pr?.textContent, enabled: pr?.getAttribute('aria-disabled') === 'false',
    objective: document.querySelector('[data-testid="objective"]')?.textContent } : null; });

// the mode card: four chips with text; the AUTO planner chooser adds &planner= to them
await p.goto(`${site}?view=play`);
await p.getByTestId('mode-fetch-colour').waitFor({ timeout: 120000 });
await p.waitForTimeout(1500);
const chips = await p.$$eval('[data-testid^="mode-fetch-colour-"]', (as) => as.map((a) => ({ text: a.textContent, href: a.getAttribute('href') })));
await p.click('[data-testid="planner-dijkstra"]');
const withDijkstra = await p.$$eval('[data-testid^="mode-fetch-colour-"]', (as) => as.map((a) => a.getAttribute('href')));
await p.click('[data-testid="planner-astar"]');
const backToAstar = await p.$$eval('[data-testid^="mode-fetch-colour-"]', (as) => as.map((a) => a.getAttribute('href')));
report.planner_links = { chips, dijkstra: withDijkstra, astar: backToAstar,
  ok: chips.length === 4 && withDijkstra.every((h) => h.endsWith('&planner=dijkstra')) && backToAstar.every((h) => !h.includes('planner=')) };
if (SHOTS) {
  await p.getByTestId('mode-fetch-colour').scrollIntoViewIfNeeded();
  await p.waitForTimeout(500);
  await snap('mode-card');
}

for (const [k, colour] of COLOURS.entries()) {
  const t0 = Date.now(), log = [];
  const until = async (fn, label, ms = 900000) => { const s0 = Date.now(); for (;;) { const s = await state(); if (s && fn(s)) { log.push([label, s.tick]); return s; } if (Date.now() - s0 > ms) { log.push([`${label} TIMEOUT`, s?.tick]); return s; } await p.waitForTimeout(250); } };
  // open the colour from the mode card's chip (the link the player taps)
  await p.goto(`${site}?view=play`);
  if (RACE) {
    await p.getByTestId('mode-race-nav2-colour').click();
    await p.getByTestId(`choose-colour-${colour}`).click();
  } else await p.getByTestId(`mode-fetch-colour-${colour}`).click();
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 600000 });
  const url = p.url();
  await p.click('[data-testid="g1-play"]');
  await until((s) => s.tick > 2, 'started', 300000);
  report.renderer ??= await renderer(p).catch(() => null);
  if (SHOTS && k === 0) { await p.waitForTimeout(1500); await snap('row-of-rods'); }
  const raceChip = RACE ? await p.locator('[data-testid="g2-race-chip"]').textContent({ timeout: 5000 }).catch(() => null) : null;
  const auto = async (label) => {
    for (let tries = 0; tries < 3; tries++) {
      await p.keyboard.press('KeyF');
      const s2 = await until((x) => x.mode === 'goal' || x.f?.over, `${label} (AUTO taken)`, 20000);
      if (s2?.mode === 'goal' || s2?.f?.over) return;
      log.push(['AUTO press not acted on, retrying', s2?.tick]);
    }
  };
  await auto('to the rod');
  let s = await until((x) => x.f?.over || (x.tick > 5 && x.source !== 'planner' && x.enabled && /GRAB/.test(x.primary ?? '')), 'at the rod (GRAB lit)');
  const objectiveBefore = s?.objective;
  if (!s?.f?.over) {
    await p.keyboard.press('KeyG');
    s = await until((x) => x.f?.over || !!x.a?.carried || (x.a?.phase === 'idle' && x.a?.reason && !/ok|holds/.test(x.a.reason)), 'carried');
  }
  const carried = s?.a?.carried ?? null;
  if (carried) {
    await p.waitForTimeout(500);
    await auto('to Dispatch');
    if (SHOTS && k === 0) { await p.waitForTimeout(6000); await snap('carrying'); }
    s = await until((x) => x.f?.over || (x.enabled && /DROP/.test(x.primary ?? '')), 'at Dispatch (DROP lit)');
    if (!s?.f?.over) { await p.keyboard.press('KeyG'); s = await until((x) => x.f?.over || x.f?.deliveries > 0, 'delivered'); }
  }
  const final = s;
  await p.waitForSelector('[data-testid="g1-results"]', { timeout: 300000 }).catch(() => log.push(['results TIMEOUT', null]));
  await p.waitForTimeout(1200);
  if (SHOTS && k === 0) await snap('results');
  const stars = await p.evaluate(() => window.__cocoGame.session.query('stars'));
  const rec = await p.evaluate(() => window.__cocoGame.session.query('record'));
  const resultsTitle = await p.textContent('[data-testid="results-title"]').catch(() => null);
  // no toast drawn over the results; the results card fits the screen (no scrolling needed)
  const layout = await p.evaluate(() => { const r = document.querySelector('[data-testid="g1-results"]');
    return { toasts: document.querySelectorAll('.g1-toast').length, scroll_h: r?.scrollHeight ?? null, client_h: r?.clientHeight ?? null }; });
  const delivered = stars?.card?.delivered?.[0]?.object ?? null;
  const threeway = RACE ? await p.locator('[data-testid="g2-threeway"]').textContent().catch(() => null) : null;
  report.runs[colour] = { url, ok: delivered === `rod_${colour}` && stars?.card?.colour === colour && final?.f?.colour === colour && rec.record.arg === colour && layout.toasts === 0 && (!RACE || (/STACK/.test(raceChip ?? '') && /NAV2 IN GAZEBO/.test(threeway ?? ''))),
    race_chip: raceChip, threeway,
    toast_hidden: layout.toasts === 0, results_fit: layout.scroll_h !== null && layout.scroll_h <= layout.client_h, results_scroll_h: layout.scroll_h, results_client_h: layout.client_h,
    delivered, carried, hud_colour: final?.f?.colour ?? null, objective_at_grab: objectiveBefore, results_title: resultsTitle,
    stars: stars?.stars ?? null, time_used: stars?.card?.time_used ?? null, contacts: stars?.card?.contacts ?? null, reference_time: stars?.reference?.time_used ?? null,
    ticks: rec.record.ticks, inputs: rec.record.inputs.length, wall_s: (Date.now() - t0) / 1000, log };
  writeFileSync(`${out}/${profile}-${colour}-record.json`, JSON.stringify({ ...rec, scorecard: stars.card, stars: stars.stars, profile, browser: `Chromium (Playwright), ${report.gpu}`, note: 'Pyodide in the browser worker; MODEL' }, null, 1) + '\n');
  console.log(colour, JSON.stringify(report.runs[colour]));
}
await b.close();
report.ok = report.planner_links.ok && Object.values(report.runs).every((r) => r.ok) && errors.length === 0;
writeFileSync(`${out}/${profile}-check.json`, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ ok: report.ok, planner_links: report.planner_links.ok, renderer: report.renderer, errors, shots: report.shots }));
process.exit(report.ok ? 0 : 1);
