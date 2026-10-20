// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
// Independent M5 reviewer: real navigation, STOP, title ordering, pane trace capture.
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone } from '../phone/nothing-phone-1.mjs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [site, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const report = { class: 'TESTED functionality; no performance acceptance claim', conditions: { start: conditions() }, cases: [] };
const browser = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu', ...(process.env.REVIEW_CDP_PORT ? ['--remote-debugging-port='+process.env.REVIEW_CDP_PORT] : [])] });
const save = () => writeFileSync(out + '/checks.json', JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
let currentPage;
try {
 for (const [name, options] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['compact', { viewport: { width: 844, height: 390 } }], ['nothing-landscape', nothingPhone1(true)], ['nothing-portrait', nothingPhone1(false)]]) {
  if(process.env.REVIEW_PROFILES && !process.env.REVIEW_PROFILES.split(',').includes(name))continue;
  const ctx = await browser.newContext({ ...options, serviceWorkers: 'block' }), p = await ctx.newPage();
  currentPage=p;
  const row = { name, emulated: name.startsWith('nothing'), errors: [], thirdParty: [] }; report.cases.push(row); save();
  if (row.emulated) await throttlePhone(ctx, p);
  p.on('pageerror', e => row.errors.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') row.errors.push(m.text()); });
  p.on('request', r => { if (/^https?:/.test(r.url()) && !r.url().startsWith(new URL(site).origin)) row.thirdParty.push(r.url()); });
  await p.addInitScript(() => {
   window.__review = { workers: [], idle: false, input: false, denied: [], stops: [] };
   const nativeIdle = window.requestIdleCallback?.bind(window);
   if (nativeIdle) window.requestIdleCallback = (fn, opts) => nativeIdle(deadline => { window.__review.idle = true; fn(deadline); }, opts);
   for (const kind of ['pointerdown', 'keydown']) window.addEventListener(kind, () => { window.__review.input = true; }, { capture: true });
   const NativeWorker = window.Worker;
   window.Worker = class extends NativeWorker {
    constructor(...args) {
     super(...args);
     const row = { titleReady: !!document.querySelector('[data-testid="title"] canvas[data-scene-ready="true"]'), idle: window.__review.idle, input: window.__review.input, sent: [], messages: [] };
     window.__review.workers.push(row);
     row.costs = [];
     const send = this.postMessage.bind(this);
     this.postMessage = (...params) => { row.sent.push(structuredClone(params[0])); return send(...params); };
     this.addEventListener('message', event => {
      const d = event.data;
      if (d.type === 'tick' && d.tick.inputs?.some(x => x.kind === 'stop')) window.__review.stops.push({tick:d.tick.tick,source:d.tick.source,v:d.tick.v});
      if (d.type === 'family' && d.channel.startsWith('coco.costmap.layers.')) row.costs.push(JSON.parse(JSON.stringify(d, (_, v) => ArrayBuffer.isView(v) ? Array.from(v, Number) : v)));
      if ((d.type === 'plan_batch' && d.meta.compare) || ['compare_done', 'compare_loop_batch'].includes(d.type)) {
       const clone = JSON.parse(JSON.stringify(d, (_, v) => ArrayBuffer.isView(v) ? Array.from(v, Number) : typeof v === 'bigint' ? Number(v) : v));
       row.messages.push(clone);
      }
     });
    }
   };
   Element.prototype.requestFullscreen = async () => { window.__review.denied.push('fullscreen'); throw new Error('review: denied'); };
   if (screen.orientation) screen.orientation.lock = async () => { window.__review.denied.push('orientation'); throw new Error('review: denied'); };
  });
  await p.goto(site + '?perf');
  await p.waitForSelector('[data-testid="title"] canvas[data-scene-ready="true"]', { timeout: 120000 });
  await p.waitForFunction(() => window.__review.workers.length > 0, null, { timeout: 30000 });
  row.titleOrdering = await p.evaluate(() => window.__review.workers.map(({titleReady,idle,input}) => ({titleReady,idle,input})));
  if (row.titleOrdering.some(w => !w.titleReady || !(w.idle || w.input))) throw Error(name + ': premature title worker');
  await p.screenshot({ path: `${out}/${name}-title.png`, scale: 'css' });
  row.stage='enter Play';save();await p.getByRole('link', { name: /^Play Drive COCO/ }).click();
  await p.getByRole('link', { name: /Free roam Drive/ }).click();
  await p.waitForFunction(() => !!window.__cocoArena?.client?.world, null, { timeout: 120000 });
  await p.evaluate(() => window.dispatchEvent(new Event('coco:skip-tutorial')));
  await p.waitForTimeout(500);
  row.stage='STOP tests';save();const stopCount = await p.evaluate(() => window.__review.stops.length);
  if (name === 'nothing-portrait') {
   await p.locator('.night-rotate button').click();
   row.rotateVisible = await p.getByRole('heading', { name: 'Rotate your phone' }).isVisible();
  } else {
   row.stage='HUD STOP';save();await p.locator('[data-testid="hud-stop"]').click();
   await p.locator('[data-testid="hud-release"]').waitFor();
   await p.locator('[data-testid="hud-release"]').click();
   await p.getByRole('button', { name: 'Settings', exact: true }).click();
   row.stage='modal STOP';save();await p.getByRole('dialog').getByRole('button', { name: 'STOP', exact: true }).click();
   await p.getByRole('button', { name: 'Close settings' }).click();
   await p.locator('[data-testid="hud-release"]').waitFor();
   await p.locator('[data-testid="hud-release"]').click();
   await p.getByRole('button', { name: 'Settings', exact: true }).click();
   row.stage='keyboard STOP';save();await p.keyboard.press('Space');
   await p.getByRole('button', { name: 'Close settings' }).click();
   await p.locator('[data-testid="hud-release"]').waitFor();
  }
  row.stage='await worker STOP';row.stopBeforeWait=await p.evaluate(()=>window.__review.stops);save();await p.waitForFunction(count => window.__review.stops.length > count, stopCount, { timeout: 30000 });
  row.stop = await p.evaluate(() => ({receipts:window.__review.stops,latched:!!document.querySelector('[data-testid="hud-release"]'),latestVelocity:window.__cocoArena?.session()?.shownTick?.v}));
  if (row.stop.receipts.length < stopCount + (name==='nothing-portrait'?1:3) || !row.stop.latched || row.stop.receipts.some(r=>r.source!=='stop'||r.v!==0)) throw Error(name+': STOP did not win');
  row.layout = await p.evaluate(() => {
   const visible = e => { const b=e.getBoundingClientRect(),s=getComputedStyle(e);return b.width>0&&b.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&!e.closest('dialog:not([open])'); };
   const controls = [...document.querySelectorAll('.coco-play button,.coco-play a,.coco-play input,.coco-play select,.coco-play [role=application],.coco-play canvas[data-testid=arena-canvas]')].filter(visible);
   return { viewport:[innerWidth,innerHeight],scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],controls:controls.map(e=>({name:e.ariaLabel||e.textContent.trim(),box:e.getBoundingClientRect().toJSON()})) };
  });
  if (row.layout.controls.length > 8 || row.layout.scroll.some((n,i) => n > row.layout.viewport[i])) throw Error(name + ': Focus failed');
  await p.screenshot({ path: `${out}/${name}-play.png`, scale: 'css' });
  row.deniedApis = await p.evaluate(() => window.__review.denied);
  if (row.emulated) {
   const cdp = await ctx.newCDPSession(p);
   const insets = name === 'nothing-landscape' ? {top:0,left:44,right:0,bottom:16} : {top:44,left:0,right:0,bottom:16};
   await cdp.send('Emulation.setSafeAreaInsetsOverride',{insets});
   row.syntheticSafeArea = {insets, boxes:await p.locator('.night-objective,.night-minimap,.night-settings,.night-vision,.night-actions,.night-joystick,.night-rotate>div').evaluateAll(elements=>elements.filter(e=>getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none').map(e=>({class:e.className,box:e.getBoundingClientRect().toJSON()})))};
   await p.screenshot({path:`${out}/${name}-play-safe-insets.png`,scale:'css'});
   await cdp.send('Emulation.setSafeAreaInsetsOverride',{insets:{top:0,left:0,right:0,bottom:0}});
  }

  // Leave Play using its Settings navigation (portrait uses Back to games).
  if (name === 'nothing-portrait') { await p.getByRole('link', { name: 'Back to games' }).click(); await p.getByRole('button',{name:'Settings',exact:true}).click(); await p.getByRole('dialog').getByRole('link',{name:'Compare',exact:true}).click(); }
  else { await p.getByRole('button', { name: 'Settings', exact: true }).click(); await p.getByRole('dialog').getByRole('link', { name: 'Compare', exact: true }).click(); }
  await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', { timeout:180000 });
  await p.waitForSelector('canvas[data-scene-ready="true"]', { timeout: 90000 });
  await p.screenshot({ path: `${out}/${name}-compare-2.png`, scale:'css' });
  if (name === 'desktop') {
   const capture = async count => {
    const trace = await p.evaluate(() => ({ labels:[...document.querySelectorAll('.compare-labels strong')].map(e=>e.textContent), workers:window.__review.workers.map(({costs,...worker}) => worker) }));
    writeFileSync(`${out}/compare-${count}-events.json`,JSON.stringify(trace)+'\n');
   };
   await capture(2);
   writeFileSync(`${out}/costmap-emitted.json`,JSON.stringify(await p.evaluate(()=>window.__review.workers.flatMap(w=>w.costs)))+'\n');
   await p.locator('.compare-controls select').nth(1).selectOption('4');
   await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]', {timeout:180000});
   await capture(4);
   await p.screenshot({ path:`${out}/${name}-compare-4.png`,scale:'css' });
   for (const algorithm of process.env.REVIEW_LAYOUT_ONLY ? [] : ['bfs', 'dstar_lite']) {
    await p.getByRole('combobox',{name:'Algorithm A',exact:true}).selectOption(algorithm);
    await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]',{timeout:180000});
    await capture(algorithm);
   }
   for (const family of process.env.REVIEW_LAYOUT_ONLY ? [] : ['control', 'localise']) {
    await p.getByRole('combobox',{name:'Family',exact:true}).selectOption(family);
    await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]',{timeout:300000});
    await capture(family);
    await p.screenshot({path:`${out}/${name}-compare-${family}.png`,scale:'css'});
   }
  }
  await p.getByTestId('mode-research').click();
  await p.locator('.recording-card').first().waitFor();
  row.recordings = await p.locator('.recording-card').count();
  await p.screenshot({ path:`${out}/${name}-recordings.png`,scale:'css' });
  await p.getByRole('link', {name:'COCO Lab',exact:true}).click();
  await p.getByTestId('title').waitFor();
  row.returnedToTitle = true;
  if (row.errors.length || row.thirdParty.length) throw Error(name + ': console/network errors');
  await ctx.close(); save();
 }
 report.passed = true;
} catch(e) { if(currentPage){try{report.debug=await currentPage.evaluate(()=>({stops:window.__review?.stops,body:document.body.innerText.slice(0,1500)}));await currentPage.screenshot({path:out+'/failure.png'});}catch{}} report.error=String(e); report.passed=false; process.exitCode=1; }
finally { await browser.close(); report.conditions.end=conditions(); save(); }
