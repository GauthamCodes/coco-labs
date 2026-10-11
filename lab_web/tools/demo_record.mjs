// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Record a 60-90 s demo of COCO Lab (M3.8; a DRAFT for Gautham, never
 * published by the agent):
 *
 *   node tools/demo_record.mjs --site URL --out DIR [--gpu 1]
 *
 * One continuous browser video (Playwright's recordVideo, WebM, 1280 x 720):
 *   1. the Arena, Plan lens at Inspect: two goals, the search spreading,
 *      the heatmap of the order cells were expanded (MODEL);
 *   2. Learn, mission 7: the reveal beat, then its Case File opened at the
 *      moment the stack's belief leaves the truth (STACK);
 *   3. Case Files: Run 15's reproduction beside the model on the same
 *      scenario (STACK | MODEL).
 * Writes DIR/coco_lab_demo.webm and DIR/demo.json (the scenes and timings).
 */

import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4214/coco-labs/';
const OUT = args.out ?? 'demo-out';
mkdirSync(OUT, { recursive: true });
const size = { width: 1280, height: 720 };
const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const context = await browser.newContext({ viewport: size, recordVideo: { dir: OUT, size } });
const page = await context.newPage();
const t0 = Date.now();
const scenes = [];
const scene = (name) => scenes.push({ name, at_s: (Date.now() - t0) / 1000 });

// 1. a goal, the search spreading, the heatmap
scene('Arena: Plan lens, Inspect -- goals, the search, the heatmap');
await page.goto(`${SITE}?view=arena&lens=plan&level=inspect`);
await page.waitForFunction(() => !!window.__cocoPerf?.marks?.arena_ready, null, { timeout: 120_000 });
await page.waitForTimeout(1500);
await page.evaluate(() => window.__cocoArena.goal(10.0, 3.0));
await page.waitForTimeout(12000);
await page.evaluate(() => window.__cocoArena.goal(3.0, -6.5));
await page.waitForTimeout(12000);

// 2. mission 7: the reveal, then the Case File at the divergence
scene('Learn: mission 7, the reveal beat');
await page.goto(`${SITE}?view=learn&mission=why-did-it-fail&beat=2`);
await page.waitForTimeout(6000);
scene('Arena: the Case File, paused where the belief leaves the truth');
await page.getByTestId('arena-go').click();
await page.waitForFunction(() => !!window.__cocoPerf?.marks?.recording_ready, null, { timeout: 60_000 });
await page.waitForTimeout(5000);
await page.evaluate(() => { const s = window.__cocoArena.session(); s.playing = true; });
await page.waitForTimeout(9000);

// 3. Case Files: STACK beside MODEL
scene('Case Files: Run 15 reproduced, beside the model');
await page.goto(`${SITE}?view=casefiles&case=run15&file=lab5_mislocalised_dwb_1`);
await page.waitForTimeout(20000);
scene('end');

const video = page.video();
await context.close();
await browser.close();
const path = await video.path();
const file = join(OUT, 'coco_lab_demo.webm');
renameSync(path, file);
const seconds = (Date.now() - t0) / 1000;
writeFileSync(join(OUT, 'demo.json'), JSON.stringify({ site: SITE, file: 'coco_lab_demo.webm', seconds, scenes }, null, 1) + '\n');
console.log(`${file}: ${seconds.toFixed(1)} s, ${scenes.length - 1} scenes`);
