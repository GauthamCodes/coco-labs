// R5.3 debug: what a click + G does while LIVE (primary label, status, card, gateway goal)
import { chromium } from 'playwright';
const [site, code] = process.argv.slice(2);
let last = null; const obs = new WebSocket('ws://localhost:8766/ws');
await new Promise((r) => (obs.onopen = r));
obs.onmessage = (e) => { if (typeof e.data === 'string') { const m = JSON.parse(e.data); if (m.type === 'telemetry') last = m; } };
obs.send(JSON.stringify({ type: 'hello', client: 'dbg', binary: false }));
const b = await chromium.launch({ headless: true, args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] });
const ctx = await b.newContext({ viewport: { width: 1280, height: 720 } });
await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
const page = await ctx.newPage();
const S = async (tag) => console.log(tag, JSON.stringify({ primary: await page.getByTestId('hud-primary').getAttribute('aria-label'), rosout: (await page.getByTestId('g2-rosout').textContent()).slice(-90), card: await page.getByTestId('r5-compare').count(), latched: last?.platform?.stop?.latched, gw_goal: last?.nav?.goal, mode: last?.platform?.arbiter?.mode }));
await page.goto(`${site}?view=play&game=free`);
await page.waitForFunction(() => !document.querySelector('[data-testid="g1-play"]')?.hasAttribute('disabled'), null, { timeout: 180000 });
await page.getByTestId('g1-play').click();
await page.getByTestId('r5-live-button').click();
await page.getByTestId('r5-live-url').fill('ws://localhost:8765'); await page.getByTestId('r5-live-code').fill(code);
await page.getByTestId('r5-live-connect').click();
await page.waitForFunction(() => /LIVE/.test(document.querySelector('[data-testid="r5-evidence-chip"]')?.textContent ?? ''), null, { timeout: 45000 });
await page.getByRole('button', { name: 'Close' }).first().click().catch(() => {});
await page.waitForTimeout(1500); await S('connected');
await page.keyboard.down('KeyW'); await page.waitForTimeout(1500); await page.keyboard.up('KeyW'); await page.waitForTimeout(800); await S('after drive');
for (const y of [200, 240]) { await page.mouse.click(640, y); await page.waitForTimeout(500); await S(`click y=${y}`); }
await page.keyboard.press('KeyG'); await page.waitForTimeout(2500); await S('after G');
await page.waitForTimeout(8000); await S('after 8 s');
await b.close(); obs.close();
