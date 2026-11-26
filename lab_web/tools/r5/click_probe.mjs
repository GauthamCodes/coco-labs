// R5.3 test aid: where a click in Play's chase view puts the goal (no LIVE needed)
import { chromium } from 'playwright';
const [site] = process.argv.slice(2);
const b = await chromium.launch({ headless: true, args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] });
const ctx = await b.newContext({ viewport: { width: 1280, height: 720 } });
await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
const page = await ctx.newPage();
await page.goto(`${site}?view=play&game=free`);
await page.waitForFunction(() => !document.querySelector('[data-testid="g1-play"]')?.hasAttribute('disabled'), null, { timeout: 180000 });
await page.getByTestId('g1-play').click();
await page.waitForTimeout(2500);
for (const y of [420, 380, 340, 300, 260, 220, 190]) {
  await page.mouse.click(640, y); await page.waitForTimeout(500);
  console.log(y, await page.getByTestId('hud-primary').getAttribute('aria-label'));
}
await b.close();
