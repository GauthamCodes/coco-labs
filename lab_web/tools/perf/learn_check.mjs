// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Learn (M2.8) in a real browser:
 *
 *   node tools/perf/learn_check.mjs --site URL --out DIR
 *
 * Opens the mission list; plays every mission's seven beats with Next; on
 * each predict beat checks that no evidence shows before an answer, picks
 * the first option, and checks the options lock, the verdict says yes or
 * names the right answer, and the evidence appears; counts the claims each beat shows and the label on each. Then
 * follows two Arena links: a settings beat (Map lens, occupancy from the
 * MCL filter's belief) -- the model must apply exactly the beat's config lines,
 * with no lens default -- and a recording beat, and comes back by the
 * mission link. The mission list and one beat are also drawn at phone width
 * (390 px), which must not scroll sideways. M2.9: the "model gap" chips --
 * none on the planning missions, the right ones on the others and on the
 * Map lens, and the LiDAR chip opens to its measured text.
 * Exit 0 only with 0 console errors and every step.
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
const SITE = args.site ?? 'http://127.0.0.1:4194/coco-labs/';
const OUT = args.out ?? 'learn-out';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, steps: {}, missions: [], errors };
const fail = (msg) => { throw new Error(msg); };

try {
  await page.goto(`${SITE}?view=learn`);
  await page.getByTestId('mission-list').waitFor({ timeout: 30_000 });
  const ids = await page.$$eval('[data-testid="mission-list"] a', (as) => as.map((a) => a.dataset.testid.replace('mission-', '')));
  if (ids.length !== 6) fail(`mission list has ${ids.length}`);
  out.steps.list = ids;
  await page.screenshot({ path: join(OUT, 'learn_list.png'), fullPage: true });

  for (const id of ids) {
    await page.goto(`${SITE}?view=learn`);
    await page.getByTestId(`mission-${id}`).click();
    await page.getByTestId('mission').waitFor();
    const rec = { id, beats: [] };
    for (let i = 0; i < 7; i++) {
      const beat = await page.getByTestId('mission').getAttribute('data-beat');
      const b = { beat, url: page.url().replace(SITE, '') };
      if (beat === 'predict') {
        b.claims_before_answer = await page.locator('[data-testid^="claim-"]').count();
        if (b.claims_before_answer !== 0) fail(`${id}: evidence shown before the prediction`);
        // commit to the first option; a wrong one must be told the right answer
        await page.getByTestId('option-0').click();
        b.picked = 0;
        b.verdict = await page.getByTestId('verdict').textContent();
        b.options_locked = await page.locator('[data-testid^="option-"]:not([disabled])').count() === 0;
        if (!b.options_locked || !/^(Yes\.|Not quite: the answer is ")/.test(b.verdict)) fail(`${id}: verdict ${b.verdict}`);
        if (id === ids[0]) await page.screenshot({ path: join(OUT, `learn_${id}_predict.png`), fullPage: true });
      }
      b.claims = await page.$$eval('[data-testid^="claim-"]', (cs) => cs.map((c) => ({
        id: c.dataset.testid.replace('claim-', ''), label: c.querySelector('.claim-label')?.textContent,
        evidence_links: c.querySelectorAll('.cite a').length,
      })));
      if (b.claims.some((c) => !c.label || c.evidence_links === 0)) fail(`${id}/${beat}: a claim without a label or evidence`);
      const go = page.getByTestId('arena-go');
      b.arena = (await go.count()) ? await go.getAttribute('href') : null;
      rec.beats.push(b);
      if (i < 6) { await page.getByTestId('next').click(); await page.waitForFunction((k) => document.querySelector('[data-testid="mission"]')?.dataset.beat !== k, beat); }
    }
    rec.v1 = await page.getByTestId('v1-page').getAttribute('href');
    rec.gaps = await page.$$eval('details.gap-chip', (ds) => ds.map((d) => d.dataset.testid.replace('gap-', '')));
    rec.claims_shown = new Set(rec.beats.flatMap((b) => b.claims.map((c) => c.id))).size;
    out.missions.push(rec);
  }

  // M2.9 chips: the missions that depend on a model gap show it, the ones that do not show none
  const gapsOf = (id) => out.missions.find((m) => m.id === id).gaps;
  if (gapsOf('find-a-path').length || gapsOf('world-changes').length) fail('a planning mission shows a model gap chip');
  if (JSON.stringify(gapsOf('where-it-is')) !== '["lidar","odometry"]') fail(`where-it-is chips ${gapsOf('where-it-is')}`);
  if (JSON.stringify(gapsOf('avoid-things')) !== '["lidar","tracking"]') fail(`avoid-things chips ${gapsOf('avoid-things')}`);

  // a settings beat: the Map lens with the pose graph on the filter's belief
  const mapBeat = out.missions.find((m) => m.id === 'build-a-map').beats.find((b) => b.beat === 'manipulate');
  await page.goto(`${SITE}${mapBeat.arena.replace(/^\/coco-labs\//, '')}&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  await page.waitForFunction(() => window.__cocoArena.mode() === 'live', null, { timeout: 60_000 });
  await page.waitForFunction(() => window.__cocoArena.log().filter((x) => x.kind === 'config').length >= 4, null, { timeout: 90_000 });
  await page.waitForTimeout(1500);
  out.steps.settings_beat = {
    href: mapBeat.arena,
    applied: await page.evaluate(() => window.__cocoArena.log().filter((x) => x.kind === 'config').map((x) => x.choice)),
    // what the page SHOWS must be what the model was told (the controls start from the beat's lines)
    shown: { algorithm: await page.getByTestId('map-algorithm').inputValue(), poses: await page.getByTestId('map-poses').inputValue() },
  };
  const want = new URLSearchParams(mapBeat.arena.split('?')[1]).getAll('cfg');
  if (JSON.stringify(out.steps.settings_beat.applied) !== JSON.stringify(want)) fail(`applied ${out.steps.settings_beat.applied} != ${want}`);
  // the Map lens shows its chips; one opens to the measured text
  out.steps.settings_beat.gaps = await page.$$eval('details.gap-chip', (ds) => ds.map((d) => d.dataset.testid.replace('gap-', '')));
  await page.locator('[data-testid="gap-lidar"] summary').click();
  out.steps.settings_beat.lidar_chip = await page.getByTestId('gap-lidar').textContent();
  if (JSON.stringify(out.steps.settings_beat.gaps) !== '["lidar","odometry"]' || !/median 2\.2 mm/.test(out.steps.settings_beat.lidar_chip)) {
    fail(`map lens chips ${out.steps.settings_beat.gaps}: ${out.steps.settings_beat.lidar_chip}`);
  }
  const shown = out.steps.settings_beat.shown;
  if (shown.algorithm !== 'occupancy' || shown.poses !== 'belief') fail(`controls show ${JSON.stringify(shown)}`);
  await page.screenshot({ path: join(OUT, 'learn_arena_settings.png') });
  await page.getByTestId('mission-back').click();
  await page.getByTestId('mission').waitFor();
  out.steps.back = { url: page.url().replace(SITE, ''), beat: await page.getByTestId('mission').getAttribute('data-beat') };
  if (out.steps.back.beat !== 'manipulate') fail('the way back did not land on the beat');

  // a recording beat
  const recBeat = out.missions.find((m) => m.id === 'avoid-things').beats.find((b) => b.beat === 'stack');
  await page.goto(`${SITE}${recBeat.arena.replace(/^\/coco-labs\//, '')}`);
  await page.waitForFunction(() => document.querySelector('[data-testid="arena-mode"]')?.dataset.mode === 'recording', null, { timeout: 60_000 });
  await page.waitForFunction(() => /Recorded run \(STACK\)/.test(document.querySelector('[data-testid="arena-mode"]')?.textContent ?? ''), null, { timeout: 60_000 });
  out.steps.recording_beat = { href: recBeat.arena, banner: await page.getByTestId('arena-mode').textContent() };
  await page.waitForTimeout(2000);
  out.steps.recording_beat.converter_marker_shown = await page.evaluate(() => /Controller: (eval|rollout)/.test(document.body.textContent ?? ''));
  if (out.steps.recording_beat.converter_marker_shown) fail("the converter's record marker reached the caption");
  await page.screenshot({ path: join(OUT, 'learn_arena_recording.png') });

  // phone width
  await page.setViewportSize({ width: 390, height: 844 });
  const sideways = async () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.goto(`${SITE}?view=learn`);
  await page.getByTestId('mission-list').waitFor();
  const listOver = await sideways();
  await page.screenshot({ path: join(OUT, 'learn_phone_list.png'), fullPage: true });
  await page.goto(`${SITE}?view=learn&mission=where-it-is&beat=4`);
  await page.getByTestId('mission').waitFor();
  const beatOver = await sideways();
  await page.screenshot({ path: join(OUT, 'learn_phone_explain.png'), fullPage: true });
  out.steps.phone = { list_overflow_px: listOver, beat_overflow_px: beatOver };
  if (listOver > 0 || beatOver > 0) fail(`phone width scrolls sideways (${listOver}, ${beatOver})`);

  out.ok = errors.length === 0;
} catch (e) {
  out.ok = false;
  out.failure = String(e);
}
writeFileSync(join(OUT, 'learn_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
await browser.close();
console.log(JSON.stringify({ ok: out.ok, failure: out.failure, errors: errors.length,
  claims: out.missions.map((m) => `${m.id}:${m.claims_shown}`), phone: out.steps.phone }));
process.exit(out.ok ? 0 : 1);
