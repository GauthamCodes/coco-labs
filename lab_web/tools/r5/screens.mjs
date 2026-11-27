// R5.6: before/after screenshots of the surfaces R5 changes: Play's HUD (Free drive), its pause menu, SIM view,
// Workbench (its tabs; the world editor after R5). Desktop and the emulated Nothing Phone (1), landscape.
//   node tools/r5/screens.mjs SITE OUT_DIR
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
const [site, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const b = await chromium.launch({ headless: true, args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] });
for (const [tag, ctxOpts] of [['desktop', { viewport: { width: 1280, height: 720 } }],
  ['phone-landscape', { viewport: { width: 915, height: 412 }, deviceScaleFactor: 2.625, isMobile: true, hasTouch: true }]]) {
  const ctx = await b.newContext(ctxOpts);
  await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
  const page = await ctx.newPage();
  await page.goto(`${site}?view=play&game=free`);
  await page.waitForFunction(() => { const x = document.querySelector('[data-testid="g1-play"]'); return x && !x.hasAttribute('disabled'); }, null, { timeout: 180000 });
  await page.getByTestId('g1-play').click(); await page.waitForTimeout(2500);
  await page.screenshot({ path: join(out, `${tag}_play.png`) });
  await page.getByTestId('g1-pause').click(); await page.waitForTimeout(600);
  await page.screenshot({ path: join(out, `${tag}_pause_menu.png`) });
  await page.keyboard.press('Escape'); await page.waitForTimeout(400);
  await page.keyboard.press('KeyV'); await page.waitForTimeout(1500);
  await page.screenshot({ path: join(out, `${tag}_sim.png`) });
  await page.goto(`${site}?view=workbench&tab=editor`); await page.waitForTimeout(6000);
  await page.screenshot({ path: join(out, `${tag}_workbench_editor_tab.png`) });
  await ctx.close();
}
await b.close();
console.log('ok', out);
