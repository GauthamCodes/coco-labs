// R5.4: "Download as ROS 2 package" in a real browser: Play (Free drive, the Depot), a goal set on the
// map, the pause menu's DOWNLOAD AS ROS 2 PACKAGE; the zip is saved for the native comparison and the run.
//   node tools/r5/package_e2e.mjs SITE OUT_ZIP [chromium|firefox]
import { writeFileSync } from 'node:fs';
import { chromium, firefox } from 'playwright';
const [site, out, which = 'chromium'] = process.argv.slice(2);
const B = which === 'firefox' ? firefox : chromium;
const b = await B.launch({ headless: true, ...(which === 'chromium' ? { args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] } : {}) });
const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, acceptDownloads: true });
await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
const page = await ctx.newPage();
const errors = []; page.on('pageerror', (e) => errors.push(String(e.message ?? e)));
await page.goto(`${site}?view=play&game=free`);
await page.waitForFunction(() => !document.querySelector('[data-testid="g1-play"]')?.hasAttribute('disabled'), null, { timeout: 180000 });
await page.getByTestId('g1-play').click();
await page.waitForTimeout(2000);
await page.mouse.click(640, 200); await page.waitForTimeout(500);
const primary = await page.getByTestId('hud-primary').getAttribute('aria-label');
await page.keyboard.press('Escape');
await page.getByTestId('r5-menu-package').waitFor({ timeout: 10000 });
const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 120000 }), page.getByTestId('r5-menu-package').click()]);
await dl.saveAs(out);
console.log(JSON.stringify({ browser: which, primary_before: primary, file: dl.suggestedFilename(), saved: out, page_errors: errors }));
await b.close();
