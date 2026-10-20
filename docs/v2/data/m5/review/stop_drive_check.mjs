// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from '../../../../../lab_web/node_modules/playwright/index.mjs';
import { writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone } from '../../../../../lab_web/tools/phone/nothing-phone-1.mjs';
import { conditions } from '../../../../../lab_web/tools/perf/conditions.mjs';
let page;
const [site,out]=process.argv.slice(2),start=conditions(),report={cases:[],errors:[]};
const browser=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});
try {
 for(const phone of process.env.STOP_PHONE_ONLY?[true]:[false,true]) {
  const ctx=await browser.newContext(phone?nothingPhone1(true):{viewport:{width:1440,height:900}}),p=await ctx.newPage();
  page=p;const row={profile:phone?'emulated Nothing Phone (1), two fingers':'desktop, W held while STOP clicked',stage:'boot'};report.cases.push(row);const save=()=>writeFileSync(out+'.json',JSON.stringify({...report,conditions:{start,end:conditions()}},null,2)+'\n');save();
  if(phone)await throttlePhone(ctx,p);
  p.on('pageerror',e=>report.errors.push(String(e)));
  await p.addInitScript(()=>{Element.prototype.requestFullscreen=async()=>{throw Error('review denied')};if(screen.orientation)screen.orientation.lock=async()=>{throw Error('review denied')};});
  await p.goto(site+'?view=arena');await p.waitForFunction(()=>!!window.__cocoArena?.client?.world,null,{timeout:120000});await p.evaluate(()=>window.dispatchEvent(new Event('coco:skip-tutorial')));
  row.stage='drive';save();let cdp,touch;
  if(phone){
   cdp=await ctx.newCDPSession(p);const b=await p.locator('.night-joystick .joystick').boundingBox();touch={x:b.x+b.width/2,y:b.y+b.height/2-45,id:1};
   await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]});
  } else {await p.getByTestId('arena-canvas').focus();await p.keyboard.down('w');}
  await p.waitForFunction(()=>window.__cocoArena?.mode()==='live'&&window.__cocoArena.last?.v>0,null,{timeout:30000});
  const before=await p.evaluate(()=>({tick:window.__cocoArena.last.tick,v:window.__cocoArena.last.v}));
  row.before=before;row.stage='STOP with first finger held';save();if(phone){const b=await p.getByTestId('hud-stop').boundingBox();const finger={x:b.x+b.width/2,y:b.y+b.height/2,id:2};await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch,finger]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[touch]});}
  else await p.getByTestId('hud-stop').click();
  await p.waitForFunction(()=>{const a=window.__cocoArena,s=a.log().filter(x=>x.kind==='stop').at(-1);return s&&a.last.tick>=s.tick+3&&a.last.v===0&&!!document.querySelector('[data-testid="hud-release"]');},null,{timeout:30000});
  if(phone)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{...touch,y:touch.y-5}]});
  const after=await p.evaluate(()=>({tick:window.__cocoArena.last.tick,v:window.__cocoArena.last.v,stops:window.__cocoArena.log().filter(x=>x.kind==='stop'),latched:!!document.querySelector('[data-testid="hud-release"]')}));
  row.after=after;row.stage='passed';save();
  if(phone)await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});else await p.keyboard.up('w');
  await p.screenshot({path:out+(phone?'-two-fingers.png':'-desktop.png')});await ctx.close();
 }
 report.passed=report.errors.length===0;
}catch(e){if(page){try{report.debug=await page.evaluate(()=>({mode:window.__cocoArena?.mode(),last:window.__cocoArena?.last,log:window.__cocoArena?.log(),latched:!!document.querySelector('[data-testid="hud-release"]')}));await page.screenshot({path:out+'-failure.png'});}catch{}}report.error=String(e);report.passed=false;process.exitCode=1;}
finally{await browser.close();writeFileSync(out+'.json',JSON.stringify({...report,conditions:{start,end:conditions()}},null,2)+'\n');}
