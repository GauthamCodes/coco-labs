// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Fault injection: corrupt optional preload, then verify a real boot retries. */
import {chromium} from 'playwright';
import {writeFileSync} from 'node:fs';
import {conditions} from './perf/conditions.mjs';
const start=conditions(),site=process.argv[2],output=process.argv[3],errors=[];
const browser=await chromium.launch();let result;
try{
 const context=await browser.newContext(),page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 let injected=0;
 await context.route('**/generated/arena/coco_lab.zip',async route=>{injected++;await route.fulfill({status:200,contentType:'application/octet-stream',body:Buffer.from([0,1,2])});});
 await page.goto(site);await page.waitForFunction(()=>window.__cocoPerf?.marks.model_warm_failed,null,{timeout:120000});
 await context.unroute('**/generated/arena/coco_lab.zip');
 await page.getByRole('link',{name:'Compare One map. Different decisions.'}).click();
 await page.waitForSelector('[data-ready="true"]',{timeout:120000});
 result={injected,reference:await page.evaluate(()=>window.__cocoReference),marks:await page.evaluate(()=>window.__cocoPerf.snapshot().marks),errors};
 if(injected!==1||errors.length||result.reference.result.A.status!=='found'||result.reference.result.B.status!=='found')throw Error('Warm-up recovery failed');
}finally{await browser.close();writeFileSync(output,JSON.stringify({conditions:{start,end:conditions()},class:'TESTED fault injection; not a startup measurement',result,errors},null,1)+'\n');}
console.log('Corrupt optional warm ZIP refused; subsequent real boot verifies the normal ZIP and completes both searches, zero console errors.');
