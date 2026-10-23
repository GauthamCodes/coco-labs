// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Warm interpreters must create fresh, cold-equivalent models in both hash versions. */
import {chromium} from 'playwright';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {conditions} from './perf/conditions.mjs';
const site=process.argv[2],out=resolve(process.argv[3]),start=conditions(),rows=[];
mkdirSync(out,{recursive:true});
const browser=await chromium.launch();
try{
 for(const hashVersion of [1,2])for(const spec of ['coco_arena_v1.json','coco_arena_v2.json']){
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.addInitScript(()=>{window.__workers=[];const Native=Worker;window.Worker=class extends Native{constructor(...args){super(...args);window.__workers.push({worker:this,url:String(args[0]),worlds:0});const row=window.__workers.at(-1);this.addEventListener('message',e=>{if(e.data.type==='world')row.worlds++;});}};});
  await page.goto(site);await page.waitForFunction(()=>window.__cocoPerf?.marks.model_warm,null,{timeout:120000});
  // The title has drawn and warmed successfully. Hide only its presentation
  // while checking worker hashes; this is not a rendering/startup benchmark.
  await page.locator('.night-title-world').evaluate(element=>{element.style.display='none';});
  const inputs=[{tick:0,kind:'teleop',linear:.3,angular:.2},{tick:3,kind:'stop'},{tick:6,kind:'goal',x:2.5,y:2},{tick:9,kind:'grasp'},{tick:12,kind:'autonomy'},{tick:16,kind:'planner',choice:'greedy'},{tick:20,kind:'stop'}];
  const result=await page.evaluate(async({hashVersion,spec,inputs,site})=>{
   const warm=window.__workers[0],worldsBefore=warm.worlds;
   const request=(worker,message,type)=>new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{worker.removeEventListener('message',handle);reject(Error('Worker request timeout: '+type));},120000);
    const handle=event=>{const data=event.data;if(data.type==='error'||data.type===type){clearTimeout(timer);worker.removeEventListener('message',handle);if(data.type==='error')reject(Error(data.stage+': '+data.message));else resolve(data);}};
    worker.addEventListener('message',handle);worker.postMessage(message);
   });
   const boot={type:'boot',pyodideBase:site+'generated/pyodide/',assetsBase:site+'generated/',seed:7,planner:'astar',batchSize:2048,hashVersion,spec};
   const play=async worker=>{const world=await request(worker,boot,'world'),ticks=[];for(let tick=0;tick<25;tick++){const message=await request(worker,{type:'step',inputs:inputs.filter(row=>row.tick===tick)},'tick');ticks.push({tick:message.tick.tick,hash:message.tick.hash,chain:message.tick.chain});}return {world:world.world,ticks};};
   const warmed=await play(warm.worker),coldWorker=new Worker(warm.url,{type:'module'}),cold=await play(coldWorker);coldWorker.terminate();
   return {worldsBefore,warmed,cold,pass:worldsBefore===0&&JSON.stringify(warmed)===JSON.stringify(cold)};
  },{hashVersion,spec,inputs,site});
  const specBytes=readFileSync(new URL('../public/generated/arena/'+spec,import.meta.url));
  const kinds=['goal','teleop','stop','planner','reset','kidnap','config','autonomy','grasp'];
  const compact=inputs.map(row=>[row.tick,kinds.indexOf(row.kind),...(row.kind==='goal'?[row.x,row.y]:row.kind==='teleop'?[row.linear,row.angular]:row.kind==='planner'?[row.choice]:[])]);
  const payload={v:1,...(hashVersion===2?{hv:2}:{}),s:createHash('sha256').update(specBytes).digest('hex'),e:7,t:25,c:result.cold.ticks.at(-1).chain,i:compact};
  const link='?view=arena&run='+Buffer.from(JSON.stringify(payload)).toString('base64url')+(spec==='coco_arena_v2.json'?'&world=v2':'');
  rows.push({hashVersion,spec,inputs,...result,link,errors});await page.close();
 }
}finally{await browser.close();writeFileSync(resolve(out,'warm-model.json'),JSON.stringify({conditions:{start,end:conditions()},class:'MODEL / TESTED; software integration, not a startup benchmark',rows},null,1)+'\n');}
if(rows.some(row=>!row.pass||row.errors.length))throw Error('Warm/cold model equivalence failed');
console.log('Both hash versions × both shipped specs: warm/cold world and 25 state/chain hashes identical; title emitted no model world.');
