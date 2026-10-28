// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2 rule: every phone screenshot has its status bar blacked out before it is committed.
 *
 *   node tools/g2/redact_statusbar.mjs OUT_DIR IN.png [IN.png ...] [--top PX] [--landscape-top PX]
 *
 * Writes OUT_DIR/<name>.png. A PORTRAIT shot gets its top PX device pixels (default 150) filled
 * black: the Nothing Phone (1)'s status bar is 136 px in portrait (`adb shell dumpsys window`,
 * statusBars insets, 2026-10-24). A LANDSCAPE shot gets its top 108 px (the landscape status bar)
 * blacked out by default too: Play is full screen, where Android hides the bar, but it shows it
 * for a moment on entering full screen (seen in G2.0's 02-after-tap: the clock icon and the battery
 * level). `--landscape-top 0` keeps the game's own top HUD readable, for shots looked at one by one
 * and seen to have no status bar. Every shot is looked at before it is committed: a heads-up
 * notification (an alarm, a message) can cover any part of the screen, and a shot that shows one
 * is not committed. Prints the redacted files' sha256.
 */
import { chromium } from 'playwright';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename } from 'node:path';

const args = process.argv.slice(2);
const flag = (k, d) => { const i = args.indexOf(k); return i >= 0 ? Number(args.splice(i, 2)[1]) : d; };
const TOP = flag('--top', 150), LANDSCAPE_TOP = flag('--landscape-top', 108);
const [out, ...inputs] = args;
if (!out || !inputs.length) throw new Error('usage: redact_statusbar.mjs OUT_DIR IN.png [...] [--top PX] [--landscape-top PX]');
mkdirSync(out, { recursive: true });
const b = await chromium.launch();
const page = await b.newPage();
for (const f of inputs) {
  const src = `data:image/png;base64,${readFileSync(f).toString('base64')}`;
  const png = await page.evaluate(async ([s, top, ltop]) => {
    const img = new Image();
    img.src = s;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    const g = c.getContext('2d');
    g.drawImage(img, 0, 0);
    g.fillStyle = '#000';
    const band = c.width > c.height ? ltop : top;
    if (band > 0) g.fillRect(0, 0, c.width, Math.min(band, c.height));
    return c.toDataURL('image/png').split(',')[1];
  }, [src, TOP, LANDSCAPE_TOP]);
  const buf = Buffer.from(png, 'base64');
  const dest = `${out}/${basename(f)}`;
  writeFileSync(dest, buf);
  console.log(createHash('sha256').update(buf).digest('hex'), dest);
}
await b.close();
