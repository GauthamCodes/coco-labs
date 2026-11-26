// R5.2 diagnosis: main-thread frame and timer gaps in Play (Free drive), headless, this machine
import { chromium, firefox } from 'playwright';
const [site, which = 'chromium', gpu = ''] = process.argv.slice(2);
const B = which === 'firefox' ? firefox : chromium;
const browser = await B.launch({ headless: true, ...(gpu && which === 'chromium' ? { args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] } : {}) });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
const page = await ctx.newPage();
await page.goto(`${site}?view=play&game=free`);
await page.waitForFunction(() => !document.querySelector('[data-testid="g1-play"]')?.hasAttribute('disabled'), null, { timeout: 180000 });
await page.getByTestId('g1-play').click();
await page.waitForTimeout(2000);
const r = await page.evaluate(() => new Promise((res) => {
  const raf = [], tim = []; let a = performance.now(), b = a;
  const f = (t) => { raf.push(t - a); a = t; if (raf.length < 400) requestAnimationFrame(f); };
  requestAnimationFrame(f);
  const id = setInterval(() => { const n = performance.now(); tim.push(n - b); b = n; }, 100);
  setTimeout(() => { clearInterval(id); const q = (x) => { const s = [...x].sort((p, q) => p - q); return { n: s.length, p50: +s[Math.floor(s.length / 2)].toFixed(1), p95: +s[Math.floor(s.length * 0.95)].toFixed(1), max: +s[s.length - 1].toFixed(1) }; }; res({ raf: q(raf.slice(1)), timer: q(tim.slice(1)), renderer: (() => { const c = document.createElement('canvas').getContext('webgl'); const d = c?.getExtension('WEBGL_debug_renderer_info'); return d ? c.getParameter(d.UNMASKED_RENDERER_WEBGL) : 'n/a'; })() }); }, 6000);
}));
console.log(which, gpu || 'default', JSON.stringify(r));
await browser.close();
