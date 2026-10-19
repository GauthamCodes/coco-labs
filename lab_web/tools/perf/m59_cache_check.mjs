// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync, readFileSync, mkdtempSync, cpSync, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { gzipSync } from 'node:zlib';
import { buildServiceWorker } from '../build_service_worker.mjs';
import { conditions } from './conditions.mjs';
import { nothingPhone1, throttlePhone, DEVICE_NAME } from '../phone/nothing-phone-1.mjs';
const CONDITIONS_AT_START = conditions();
const [distArg,out]=process.argv.slice(2),requestedWorld=process.argv[4]??'default',root=mkdtempSync(join(tmpdir(),'coco-deploy-'));mkdirSync(out,{recursive:true});cpSync(resolve(distArg),root,{recursive:true});
const template=readFileSync(new URL('../../src/offline/sw.template.js',import.meta.url),'utf8');
const mime=p=>p.endsWith('.html')?'text/html':p.endsWith('.js')||p.endsWith('.mjs')?'text/javascript':p.endsWith('.wasm')?'application/wasm':p.endsWith('.json')?'application/json':p.endsWith('.css')?'text/css':p.endsWith('.svg')?'image/svg+xml':p.endsWith('.woff2')?'font/woff2':'application/octet-stream';
const serverRequests=[];const server=createServer((req,res)=>{serverRequests.push(req.url);const u=new URL(req.url,'http://localhost');let path=decodeURIComponent(u.pathname.replace(/^\/coco-labs\//,''));if(!path)path='index.html';const file=resolve(root,path);if(!file.startsWith(root+'/')||!existsSync(file)||!statSync(file).isFile()){res.writeHead(404);res.end();return}const raw=readFileSync(file),zip=/gzip/.test(req.headers['accept-encoding']??'')&&/\.(js|mjs|wasm|html|json|css)$/.test(file),body=zip?gzipSync(raw):raw;res.writeHead(200,{'Content-Type':mime(file),'Cache-Control':'no-cache',...(zip?{'Content-Encoding':'gzip'}:{}),'Content-Length':body.length});res.end(body)});await new Promise(r=>server.listen(0,'127.0.0.1',r));const site=`http://127.0.0.1:${server.address().port}/coco-labs/`;
const report={site,requestedWorld,errors:[],thirdParty:[],warm:[]};const browser=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});
const listen=p=>{p.on('pageerror',e=>report.errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});p.on('request',r=>{if(!r.url().startsWith(new URL(site).origin)&&/^https?:/.test(r.url()))report.thirdParty.push(r.url())})};
try{
 writeFileSync(join(root,'cache-deploy-probe.json'),'"A"');const a=buildServiceWorker(root,template);report.versionA=a.version;
 const ctx=await browser.newContext(),p=await ctx.newPage();listen(p);await p.goto(site);await p.waitForSelector('[data-scene-ready="true"]',{timeout:120000});
 await p.evaluate(async base=>{await navigator.serviceWorker.register(base+'sw.js',{scope:base,updateViaCache:'none'});await navigator.serviceWorker.ready;if(!navigator.serviceWorker.controller)await new Promise(r=>navigator.serviceWorker.addEventListener('controllerchange',r,{once:true}))},'/coco-labs/');
 const getProbe=()=>p.evaluate(async()=>JSON.parse(await(await fetch('./cache-deploy-probe.json')).text()));if(await getProbe()!=='A')throw Error('Initial static asset incorrect');
 await p.evaluate(()=>{localStorage.setItem('cache-test-preference','personal-sentinel');});
 // A hard reload receives the new index, then the new unversioned static asset.
 writeFileSync(join(root,'cache-deploy-probe.json'),'"B"');const b=buildServiceWorker(root,template);report.versionB=b.version;
 const cdp=await ctx.newCDPSession(p);await cdp.send('Network.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});await p.reload();
 await p.waitForFunction(version=>document.querySelector('meta[name="coco-build"]')?.content===version,b.version);
 if(await getProbe()!=='B')throw Error('Hard reload served stale static asset');
 await p.evaluate(async()=>{const r=await navigator.serviceWorker.getRegistration();await r.update();await navigator.serviceWorker.ready});
 await p.waitForFunction(async version=>{const worker=navigator.serviceWorker.controller;if(!worker)return false;const current=await new Promise(resolve=>{const c=new MessageChannel();c.port1.onmessage=e=>resolve(e.data);worker.postMessage('static-version',[c.port2]);setTimeout(()=>resolve(null),500)});return current===version&&(await caches.keys()).filter(k=>k.startsWith('coco-static-')&&!k.endsWith('active-version')).every(k=>k.endsWith(version))},b.version,{timeout:120000});
 await p.evaluate(()=>fetch('./generated/v2/index.json?private=personal-sentinel'));
 const cache=await p.evaluate(async()=>{const names=await caches.keys(),keys=[];for(const name of names)keys.push(...(await(await caches.open(name)).keys()).map(r=>r.url));return{names,keys,preference:localStorage.getItem('cache-test-preference')}});if(cache.keys.some(k=>k.includes('personal-sentinel')||k.includes('private=')))throw Error('Personal URL cached');if(cache.preference!=='personal-sentinel')throw Error('Preference changed');report.cache={names:cache.names,entries:cache.keys.length,personalUrls:0};report.deploy='hard reload: new index and static bytes, old caches removed';
 await ctx.setOffline(true);await p.reload();await p.waitForSelector('[data-scene-ready="true"]',{timeout:60000});report.offlineTitle=true;await ctx.setOffline(false);await ctx.close();
 for(const profile of ['desktop','landscape','portrait']){
  const warmCtx=await browser.newContext(profile==='desktop'?{viewport:{width:1440,height:900}}:nothingPhone1(profile==='landscape'));const page=await warmCtx.newPage();listen(page);await page.goto(site+'?view=arena&perf'+(requestedWorld==='v2'?'&world=v2':''));await page.waitForFunction(()=>!!window.__cocoArena?.client?.world&&!!window.__cocoPerf?.marks?.arena_ready,null,{timeout:120000});
  await page.evaluate(async()=>{await navigator.serviceWorker.register('./sw.js',{scope:'./',updateViaCache:'none'});await navigator.serviceWorker.ready;if(!navigator.serviceWorker.controller)await new Promise(r=>navigator.serviceWorker.addEventListener('controllerchange',r,{once:true}))});
  const session=profile==='desktop'?await warmCtx.newCDPSession(page):await throttlePhone(warmCtx,page,true);if(profile==='desktop'){await session.send('Network.enable');await session.send('Network.emulateNetworkConditions',{offline:false,latency:170,downloadThroughput:9e6/8,uploadThroughput:1.5e6/8})}
  const requestStart=serverRequests.length;await page.reload();await page.waitForFunction(()=>!!window.__cocoArena?.client?.world&&!!window.__cocoPerf?.marks?.arena_ready,null,{timeout:120000});report.warm.push(await page.evaluate(({profile,device})=>{const s=window.__cocoPerf.snapshot(),r=window.__cocoArena.renderer,gl=r.renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');return{profile,device,liveModelReadyMs:s.marks.arena_ready-s.navStart,marks:s.marks,renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):'unavailable'}},{profile,device:profile==='desktop'?'laptop · emulated 4G':DEVICE_NAME+' · emulated 4G · CPU 4×'}));report.warm.at(-1).serverRequests=serverRequests.slice(requestStart);report.warm.at(-1).controlled=await page.evaluate(()=>!!navigator.serviceWorker.controller);await warmCtx.close();
 }
 const disabled=await browser.newContext({serviceWorkers:'block'}),page=await disabled.newPage();listen(page);for(const view of ['', '?view=arena&world=v2','?view=compare','?view=research']){await page.goto(site+view);await page.waitForSelector(view.includes('research')?'.recording-card':view.includes('compare')?'[data-testid="compare-workspace"][data-ready="true"]':view.includes('arena')?'[data-testid="arena"]':'[data-scene-ready="true"]',{timeout:120000});}report.disabledWorks=true;await disabled.close();
 report.passed=report.errors.length===0&&report.thirdParty.length===0;
}catch(e){report.error=String(e);report.passed=false;process.exitCode=1}finally{await browser.close();await new Promise(r=>server.close(r));writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n')}
