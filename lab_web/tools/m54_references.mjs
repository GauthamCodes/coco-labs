// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Real rendered references. These are not acceptance timing measurements. */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { conditions } from './perf/conditions.mjs';
import { nothingPhone1, throttlePhone, DEVICE_NAME } from './phone/nothing-phone-1.mjs';
import { svgMatrix } from '../src/ui/colour_checks.ts';
const start=conditions(),site=process.argv[2]??'http://localhost:4181/coco-labs/',out=resolve(process.argv[3]??'../docs/v2/data/m5/screens/reference');
mkdirSync(out,{recursive:true});
const browser=await chromium.launch({args:['--enable-webgl','--ignore-gpu-blocklist']});
const rows=[];
try {
 for(const profile of [
  {name:'desktop',options:{viewport:{width:1440,height:900}},device:'laptop Chromium'},
  {name:'compact',options:{viewport:{width:844,height:390}},device:'laptop Chromium, compact viewport'},
  {name:'nothing-landscape',options:nothingPhone1(true),device:DEVICE_NAME},
  {name:'nothing-portrait',options:nothingPhone1(false),device:DEVICE_NAME},
 ]) for(const screen of ['title','play','compare']) {
  const context=await browser.newContext(profile.options);
  await context.addInitScript(()=>{
   const original=HTMLCanvasElement.prototype.getContext;window.__gl=new Set();
   HTMLCanvasElement.prototype.getContext=function(...args){const value=original.apply(this,args);if(value&&String(args[0]).startsWith('webgl'))window.__gl.add(value);return value;};
  });
  const page=await context.newPage();if(profile.device===DEVICE_NAME)await throttlePhone(context,page);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto(site+'?view=arena&reference='+screen+'&camera=follow&theme=dark');
  await page.waitForSelector('[data-testid="reference-'+screen+'"]',{timeout:60000});
  if(screen==='play')await page.waitForFunction(()=>document.querySelector('.night-timer')?.textContent!=='00:00',{timeout:60000});
  else await page.waitForSelector('canvas[data-scene-ready="true"]',{timeout:60000});
  if(screen==='compare')await page.waitForSelector('[data-ready="true"]',{timeout:60000});
  await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(500);
  const inspection=await page.evaluate(()=>{
   const canvas=document.querySelector('.night-world,.night-game-canvas'),gl=[...window.__gl][0],info=gl?.getExtension('WEBGL_debug_renderer_info');
   return {theme:document.documentElement.dataset.theme,viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],glContexts:window.__gl.size,renderer:info?gl.getParameter(info.UNMASKED_RENDERER_WEBGL):null,canvas:[canvas?.width,canvas?.height],result:window.__cocoReference??null,text:document.body.innerText};
  });
  const file=profile.name+'-'+screen+'.png';await page.screenshot({path:resolve(out,file),scale:'css'});
  if(profile.name==='desktop'&&screen==='compare')for(const kind of ['protanopia','deuteranopia']){
   await page.evaluate(matrix=>{
    document.querySelector('#cvd-simulation')?.remove();const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.id='cvd-simulation';svg.setAttribute('style','position:absolute;width:0;height:0');
    svg.innerHTML='<filter id="cvd" color-interpolation-filters="linearRGB"><feColorMatrix type="matrix" values="'+matrix+'"/></filter>';document.body.append(svg);document.querySelector('#root').style.filter='url(#cvd)';
   },svgMatrix(kind));await page.screenshot({path:resolve(out,'desktop-compare-'+kind+'.png'),scale:'css'});
  }
  rows.push({file,device:profile.device,cpuThrottle:profile.device===DEVICE_NAME?4:1,network:'local unthrottled; not a cold-start measurement',...inspection,errors});await context.close();
 }
} finally {await browser.close();writeFileSync(resolve(out,'references.json'),JSON.stringify({conditions:{start,end:conditions()},rows},null,1)+'\n');}
if(rows.some(row=>row.errors.length||row.glContexts!==1))throw Error('Reference console/GL check failed; inspect references.json');
console.log('Captured '+rows.length+' references and two colour-vision simulations; zero console errors, one GL context each.');
