// R2: debug helper -- upload one file to the Studio, run it, print what the page says.
//   node tools/r2/studio_debug.mjs SITE FILE.py [--compare]
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { basename } from 'node:path';

const [site, file] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await (await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } })).newPage();
page.on('pageerror', (e) => console.log('PAGEERROR', String(e)));
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('CONSOLE', m.type(), m.text().slice(0, 400)); });
await page.goto(`${site}?view=workbench&tab=studio`);
await page.locator('[data-testid=studio-editor] .cm-content').waitFor({ timeout: 120000 });
await page.locator('.studio-upload input').setInputFiles({ name: basename(file), mimeType: 'text/x-python', buffer: readFileSync(file) });
await page.waitForTimeout(300);
await page.locator(process.argv.includes('--compare') ? '[data-testid=studio-compare]' : '[data-testid=studio-run]').click();
for (let i = 0; i < 1200; i++) {
  await page.waitForTimeout(500);
  const busy = await page.locator('.studio-right [role=status]').count();
  const st = await page.locator('[data-testid=studio-status-0]').count() ? await page.locator('[data-testid=studio-status-0]').innerText() : '';
  if (await page.locator('[data-testid=studio-guard]').count() || (st && st !== 'running…' && !busy)) break;
}
for (const tab of ['Results', 'Validation', 'Console']) {
  if (await page.getByRole('tab', { name: tab }).count()) { await page.getByRole('tab', { name: tab }).click(); const sel = tab === 'Results' ? '[data-testid=studio-results]' : tab === 'Validation' ? '.studio-validation, .studio-right > p.studio-muted' : '[data-testid=studio-console]'; console.log(`--- ${tab}\n${(await page.locator(sel).first().innerText().catch(() => '?')).slice(0, 3000)}`); }
}
if (await page.locator('[data-testid=studio-guard]').count()) console.log('GUARD', await page.locator('[data-testid=studio-guard]').innerText());
await browser.close();
