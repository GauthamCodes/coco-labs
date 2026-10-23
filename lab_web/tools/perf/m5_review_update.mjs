// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
// Inspect an already-open document across deployment, beyond the hard-reload test.
import { chromium } from 'playwright';
import { cpSync, mkdtempSync, readFileSync, writeFileSync, existsSync, statSync, mkdirSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { buildServiceWorker } from '../build_service_worker.mjs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [dist, out] = process.argv.slice(2), root = mkdtempSync(join(tmpdir(), 'm5-review-update-'));
mkdirSync(out,{recursive:true}); cpSync(resolve(dist),root,{recursive:true,filter:p=>!p.includes('/v1')});
const template=readFileSync(new URL('../../src/offline/sw.template.js',import.meta.url),'utf8');
const server=createServer((req,res)=>{
 const u=new URL(req.url,'http://localhost'),path=decodeURIComponent(u.pathname.replace(/^\/coco-labs\//,''))||'index.html',file=resolve(root,path);
 if(!file.startsWith(root+'/')||!existsSync(file)||!statSync(file).isFile()){res.writeHead(404).end();return;}
 const mime=file.endsWith('.html')?'text/html':/\.m?js$/.test(file)?'text/javascript':file.endsWith('.wasm')?'application/wasm':file.endsWith('.json')?'application/json':file.endsWith('.css')?'text/css':'application/octet-stream';
 res.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'}).end(readFileSync(file));
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const site=`http://127.0.0.1:${server.address().port}/coco-labs/`,browser=await chromium.launch();
const report={scope:'Functional deploy test, not a timing measurement',errors:[],stages:[]};
const save=()=>writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');
const stage=name=>{report.stages.push({name,at:new Date().toISOString()});save();};
try {
 writeFileSync(join(root,'review-static-probe.json'),'"A"'); const a=buildServiceWorker(root,template);report.versionA=a.version;
 const p=await browser.newPage();p.on('pageerror',e=>report.errors.push(String(e)));
 stage('navigate A');await p.goto(site); await p.getByTestId('title').waitFor();stage('register A');
 await p.evaluate(async()=>{window.__reviewSwStates=[];const r=await navigator.serviceWorker.register('./sw.js',{scope:'./',updateViaCache:'none'});const w=r.installing;if(w)w.addEventListener('statechange',()=>window.__reviewSwStates.push(w.state));});
 await p.waitForFunction(()=>!!navigator.serviceWorker.controller,null,{timeout:60000});stage('A controlled');
 const snapshot=()=>p.evaluate(async()=>({documentBuild:document.querySelector('meta[name="coco-build"]').content,asset:await(await fetch('./review-static-probe.json')).json(),controller:await new Promise(r=>{const c=new MessageChannel();c.port1.onmessage=e=>r(e.data);navigator.serviceWorker.controller.postMessage('static-version',[c.port2]);})}));
 report.before=await snapshot();stage('A snapshot');
 writeFileSync(join(root,'review-static-probe.json'),'"B"');const b=buildServiceWorker(root,template);report.versionB=b.version;
 stage('update B');await p.evaluate(async()=>{await(await navigator.serviceWorker.getRegistration()).update();});
 await p.waitForFunction(async version=>{const worker=navigator.serviceWorker.controller;if(!worker)return false;return await new Promise(r=>{const c=new MessageChannel();c.port1.onmessage=e=>r(e.data===version);worker.postMessage('static-version',[c.port2]);});},b.version,{timeout:120000});
 report.afterUpdate=await snapshot();stage('B controlled');
 report.observations=[];for(let i=0;i<20;i++){report.observations.push(await snapshot());await p.waitForTimeout(100);}
 report.openDocumentMixed=report.observations.some(x=>x.documentBuild!==x.controller&&x.asset==='B');
 report.stableBSeen=report.observations.some(x=>x.controller===b.version);stage('open-tab observations');
 await p.reload();await p.getByTestId('title').waitFor();report.afterReload=await snapshot();
 report.hardReloadConsistent=report.afterReload.documentBuild===b.version&&report.afterReload.asset==='B';
 report.completed=true;
}catch(e){report.error=String(e);process.exitCode=1;}
finally{writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');await browser.close();await new Promise(r=>server.close(r));}
