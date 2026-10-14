// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from 'playwright';
import {mkdirSync,writeFileSync} from 'node:fs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const out=process.argv[2],site=process.argv[3]||'http://127.0.0.1:4175/coco-labs/';
mkdirSync(out,{recursive:true});
const browser=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});
const ctx=await browser.newContext({viewport:{width:1440,height:900}});
const cases=await (await fetch(site+'generated/casefiles/cases.json')).json();
const ids=[...new Set(cases.groups.flatMap(g=>g.casefiles.map(c=>c.id)))];
const result={label:'emulated 4G, real robot_low.glb mesh; shared browser HTTP cache across Case Files',conditions:conditions(),browser:browser.version(),network:{latency:170,download_mbit:9,upload_mbit:1.5},rows:[]};
for(const id of ids) {
 const p=await ctx.newPage();const errors=[];
 p.on('pageerror',e=>errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const cdp=await ctx.newCDPSession(p);await cdp.send('Network.enable');await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:170,downloadThroughput:9e6/8,uploadThroughput:1.5e6/8});
 const started=Date.now(); let row;
 try {
  await p.goto(site+'?view=arena&casefile='+id);
  await p.waitForFunction(()=>window.__cocoPerf?.marks?.first_robot_frame && window.__cocoPerf?.marks?.recording_ready,{timeout:120000});
  row=await p.evaluate(()=>{const a=window.__cocoArena,r=a.renderer,s=r.three,m=window.__cocoPerf.marks;return {marks:m,placeholder:s.robotHolder.children.some(c=>c.name==='placeholder'),mesh:s.robotHolder.children.length,mode:a.mode()};});
  row.ms=row.marks.first_robot_frame-row.marks.casefile_fetch_start;
  row.ok=row.ms<=2000&&!row.placeholder&&row.mesh>0&&row.mode==='recording'&&!errors.length;
 } catch(e) {row={ok:false,failure:String(e),wall_ms:Date.now()-started};}
 result.rows.push({id,...row,errors});
 await p.close();
 if(result.rows.length%10===0)console.log(`${result.rows.length}/${ids.length}`);
}
result.passed=result.rows.filter(r=>r.ok).length;result.total=ids.length;
await browser.close();writeFileSync(out+'/first-frame.json',JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');
console.log(`${result.passed}/${result.total} <=2s with robot mesh`);
process.exitCode=result.passed===result.total?0:1;
