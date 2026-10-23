// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from '../../../../../lab_web/node_modules/playwright/index.mjs';
import {writeFileSync} from 'node:fs';
import {conditions} from '../../../../../lab_web/tools/perf/conditions.mjs';
const [site,out]=process.argv.slice(2),start=conditions(),rows=[];
const b=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});
try{for(const noIdle of [false,true]){
 const c=await b.newContext({serviceWorkers:'block'}),p=await c.newPage(),row={noIdle,errors:[],requests:[]};rows.push(row);
 p.on('pageerror',e=>row.errors.push(String(e)));p.on('request',r=>{if(/wasm|stdlib/.test(r.url()))row.requests.push(r.url())});
 await p.addInitScript(noIdle=>{window.__starts=[];window.addEventListener('keydown',()=>window.__input=true,{capture:true});if(noIdle){delete window.requestIdleCallback;delete Window.prototype.requestIdleCallback;}const W=Worker;window.Worker=class extends W{constructor(...a){super(...a);window.__starts.push({ready:!!document.querySelector('canvas[data-scene-ready=true]'),input:!!window.__input});}};},noIdle);
 const workers=[];p.on('worker',async w=>{workers.push(w);try{await w.evaluate(()=>{globalThis.__streaming={calls:0,success:0};const f=WebAssembly.instantiateStreaming;WebAssembly.instantiateStreaming=(...a)=>{globalThis.__streaming.calls++;return f(...a).then(v=>{globalThis.__streaming.success++;return v;});};});}catch{}});
 await p.goto(site+'?perf');await p.waitForSelector('[data-testid=title] canvas[data-scene-ready=true]',{timeout:120000});
 if(noIdle){await p.waitForTimeout(100);row.beforeInput=await p.evaluate(()=>({starts:window.__starts,api:typeof requestIdleCallback}));if(row.beforeInput.starts.length)throw Error('Warm-up before first input without idle API');await p.keyboard.press('Shift');}
 await p.waitForFunction(()=>!!window.__cocoPerf?.marks.model_warm,null,{timeout:120000});
 row.starts=await p.evaluate(()=>window.__starts);row.preloads=await p.locator('link[rel=preload][as=fetch]').evaluateAll(es=>es.map(e=>e.href));row.streaming=await workers.at(-1).evaluate(()=>globalThis.__streaming);
 if(row.starts.some(s=>!s.ready)||noIdle&&!row.starts.every(s=>s.input)||!row.streaming?.success||row.errors.length)throw Error('Ordering or streaming failed');
 await c.close();
}}finally{await b.close();writeFileSync(out,JSON.stringify({rows,conditions:{start,end:conditions()}},null,2)+'\n');}
