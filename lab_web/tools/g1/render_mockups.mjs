// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.1: render the static HUD and shell mockups (docs/v2/g1/mockups/src/*.html)
 * to PNG at 915 x 412 (the Nothing Phone (1) landscape, CSS px) and 1440 x 900.
 *
 *   node tools/g1/render_mockups.mjs
 */
import { chromium } from 'playwright';
import { readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '../../../docs/v2/g1/mockups/src');
const out = join(here, '../../../docs/v2/g1/mockups');
const browser = await chromium.launch(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {});
for (const [tag, viewport] of [['915x412', { width: 915, height: 412 }], ['1440x900', { width: 1440, height: 900 }]]) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  for (const f of readdirSync(src).filter((x) => x.endsWith('.html')).sort()) {
    await page.goto(pathToFileURL(join(src, f)).href);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: join(out, `${f.replace('.html', '')}-${tag}.png`) });
  }
  await ctx.close();
}
await browser.close();
console.log('rendered');
