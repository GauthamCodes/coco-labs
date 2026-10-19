// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { gzipSync } from 'node:zlib';
import { nothingPhone1, throttlePhone, DEVICE_NAME } from '../phone/nothing-phone-1.mjs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [site,out]=process.argv.slice(2);mkdirSync(out,{recursive:true});const report={cases:[],protocol:'Fresh browser contexts; emulated 4G 9 Mbit/s down, 1.5 up, 170 ms; title starts warming interpreter; immediate Play/Free roam entry once title is visible; Vision selected immediately when ready. Default World Spec v1. Phone uses shared 4× CPU proxy.'};
const save=()=>writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');
for(const profile of ['desktop','landscape'])for(let run=0;run<3;run++){
 const row={profile,run,device:profile==='desktop'?'laptop · emulated 4G':DEVICE_NAME,errors:[],requests:[]};report.cases.push(row);const b=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']}),ctx=await b.newContext({...profile==='desktop'?{viewport:{width:1440,height:900}}:nothingPhone1(true),serviceWorkers:'block'}),p=await ctx.newPage();const pending=[];
 try{
 if(profile==='landscape')await throttlePhone(ctx,p,true);else{const c=await ctx.newCDPSession(p);await c.send('Network.enable');await c.send('Network.emulateNetworkConditions',{offline:false,latency:170,downloadThroughput:9e6/8,uploadThroughput:1.5e6/8})}
 p.on('pageerror',e=>row.errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')row.errors.push(m.text())});ctx.on('requestfinished',r=>pending.push((async()=>{try{row.requests.push({url:r.url(),timing:r.timing(),sizes:await r.sizes()})}catch{}})()));
 const titleJs=new Set();let isTitle=true;ctx.on('request',r=>{if(isTitle&&/\.(?:m?js)(?:\?|$)/.test(r.url()))titleJs.add(r.url())});
 await p.goto(site+'?perf');await p.waitForSelector('[data-scene-ready="true"]',{timeout:120000});row.titleVisibleMs=await p.evaluate(()=>performance.now());
 /* Enter as soon as the title is visible; interpreter warms concurrently. */row.titleJavaScript=[...titleJs].map(url=>{const path=new URL(url).pathname.slice(new URL(site).pathname.length),file=resolve('dist',path);return{path,gzipBytes:existsSync(file)?gzipSync(readFileSync(file)).length:null}});row.titleJavaScriptGzipBytes=row.titleJavaScript.reduce((n,r)=>n+(r.gzipBytes??0),0);row.criticalUiJavaScriptGzipBytes=row.titleJavaScript.filter(r=>r.path.startsWith('assets/')).reduce((n,r)=>n+(r.gzipBytes??0),0);isTitle=false;
 await p.getByRole('link',{name:/^Play Drive COCO/}).click();await p.getByRole('link',{name:/Free roam Drive/}).click();await p.waitForFunction(()=>!!window.__cocoPerf?.marks.arena_ready&&!!window.__cocoArena?.renderer?.three?.ready,null,{timeout:120000});await p.locator('.night-vision').click();await p.waitForFunction(()=>!!window.__cocoPerf.marks.first_computation_shown,null,{timeout:30000});
 Object.assign(row,await p.evaluate(()=>{const s=window.__cocoPerf.snapshot(),gl=window.__cocoArena.renderer.renderer.getContext(),e=gl.getExtension('WEBGL_debug_renderer_info');return{marks:s.marks,liveModelReadyMs:s.marks.arena_ready-s.navStart,worldInteractiveMs:Math.max(s.marks.arena_ready,s.marks.world3d_ready,s.marks.world3d_robot)-s.navStart,firstVisibleComputationMs:s.marks.first_computation_shown-s.navStart,renderer:e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):'unknown'}}));await Promise.all(pending);row.thirdParty=row.requests.filter(r=>!r.url.startsWith(new URL(site).origin)&&/^https?:/.test(r.url));row.completed=true;
 }catch(e){row.error=String(e);row.completed=false}finally{await b.close();row.conditions_end=conditions();save()}
}
report.passed=report.cases.every(r=>r.completed&&!r.errors.length&&!r.thirdParty.length);save();
