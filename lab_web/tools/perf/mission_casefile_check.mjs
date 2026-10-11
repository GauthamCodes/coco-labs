// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Every Learn beat that opens a Case File, followed in a browser (M3.4):
 *
 *   node tools/perf/mission_casefile_check.mjs --site URL --out DIR [--gpu 1]
 *
 * For each such beat (generated/missions.json): the beat renders with 0
 * errors and its link says it opens a Case File; following the link, the
 * Arena plays the Case File as a recording (STACK), PAUSED at exactly the
 * tick the beat names -- the derived moment -- with the way back to the
 * beat; a screenshot of that frame is kept.
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
const OUT = args.out ?? 'mission-casefile-out';
const LAUNCH = args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {};
mkdirSync(OUT, { recursive: true });

const ms = (await (await fetch(`${SITE}generated/missions.json`)).json()).missions;
const links = ms.flatMap((m) => m.beats.map((b, i) => ({ mission: m.id, beat: i, name: b.beat, arena: b.arena }))
  .filter((x) => x.arena?.casefile));
const browser = await chromium.launch(LAUNCH);
const out = { site: SITE, beats: [] };
for (const l of links) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  const row = { ...l, errors };
  try {
    await page.goto(`${SITE}?view=learn&mission=${l.mission}&beat=${l.beat}`);
    const go = page.getByTestId('arena-go');
    await go.waitFor({ timeout: 30_000 });
    row.link_text = (await go.textContent())?.trim();
    row.href = await go.getAttribute('href');
    await Promise.all([page.waitForURL(/view=arena/), go.click()]);
    await page.waitForFunction(() => !!window.__cocoPerf?.marks?.recording_ready, null, { timeout: 120_000 });
    await page.waitForTimeout(1500);   // paused: the tick must not move
    row.mode = await page.evaluate(() => window.__cocoArena?.mode?.());
    row.badge = await page.getByTestId('evidence-badge').textContent();
    row.shown = await page.evaluate(() => {
      const s = window.__cocoArena.session();
      return { tick: s.shownTick?.tick, playing: s.playing };
    });
    row.back = await page.getByTestId('mission-back').count();
    await page.screenshot({ path: join(OUT, `${l.mission}_${l.beat}_${l.name}.png`) });
    row.ok = errors.length === 0 && /Case File/.test(row.link_text ?? '') && row.mode === 'recording'
      && row.badge === 'STACK' && row.shown.tick === l.arena.tick && row.shown.playing === false && row.back === 1;
  } catch (e) { row.ok = false; row.failure = String(e); }
  out.beats.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${l.mission} beat ${l.beat} (${l.name}) ${l.arena.casefile} @${l.arena.moment} tick ${l.arena.tick}: shown ${JSON.stringify(row.shown)} badge ${row.badge} back ${row.back}${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
  await context.close();
}
await browser.close();
out.ok = out.beats.length > 0 && out.beats.every((r) => r.ok);
out.summary = { beats: out.beats.length, ok: out.beats.filter((r) => r.ok).length };
writeFileSync(join(OUT, 'mission_casefile_check.json'), JSON.stringify({ ...out, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify(out.summary));
process.exit(out.ok ? 0 : 1);
