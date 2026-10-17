// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from 'playwright';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
import {nothingPhone1,throttlePhone,DEVICE_NAME} from '../phone/nothing-phone-1.mjs';
const out=process.argv[2] || '../../docs/v2/data/m5/defects/browser';
const site=process.argv[3] || 'http://127.0.0.1:4175/coco-labs/';
mkdirSync(out,{recursive:true});
const screens=resolve(out,'../../screens/defects');mkdirSync(screens,{recursive:true});
const browser=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});
const result={conditions:conditions(),browser:browser.version(),picking:[],race:[],errors:[]};
const page=await browser.newPage({viewport:{width:1440,height:900}});
page.on('pageerror',e=>result.errors.push(String(e)));
page.on('console',m=>{if(m.type()==='error') result.errors.push(m.text());});
await page.goto(site+'?view=arena&attract=off&world=v2');
await page.waitForFunction(()=>window.__cocoArena?.client?.world && window.__cocoArena?.renderer?.three?.ready,{timeout:90000});
await page.evaluate(()=>{window.__cocoArena.session().playing=false;});
for(const camera of ['follow','orbit']) {
 await page.evaluate(camera=>window.__cocoArena.renderer.setCameraMode(camera,0),camera);
 await page.waitForTimeout(500);
 const pose=await page.evaluate(()=>window.__cocoArena.client.world.start);
 for(const point of [[pose[0]+.4,pose[1]],[pose[0]+1,pose[1]+.5],[pose[0]+.8,pose[1]-.3]]) {
  const row=await page.evaluate(point=>{
   const r=window.__cocoArena.renderer; const px=r.screenOf(...point); const picked=r.toWorld(...px);
   const expected=r.cellAt(...point),actual=r.cellAt(...picked);
   return {point,pixels:px,picked,expected,actual,error:Math.hypot(picked[0]-point[0],picked[1]-point[1])};
  },point);
  row.hit_element = await page.evaluate(([x,y])=>document.elementFromPoint(x,y)?.tagName,row.pixels);
  const previousGoals = await page.evaluate(()=>window.__cocoArena.log().filter(r=>r.kind==='goal').length);
  await page.mouse.click(row.pixels[0],row.pixels[1]);
  await page.waitForFunction(n=>window.__cocoArena.log().filter(r=>r.kind==='goal').length>n,previousGoals,{timeout:20000});
  row.sent = await page.evaluate(() => window.__cocoArena.queue.filter(r=>r.kind==='goal').at(-1) || window.__cocoArena.log().filter(r=>r.kind==='goal').at(-1) || null);
  row.sent_cell = row.sent ? await page.evaluate(g=>window.__cocoArena.renderer.cellAt(g.x,g.y),row.sent) : null;
  row.sent_cell_error = row.expected&&row.sent_cell ? Math.max(...row.expected.map((v,i)=>Math.abs(v-row.sent_cell[i]))) : Infinity;
  const delta=row.expected&&row.actual?Math.max(...row.expected.map((v,i)=>Math.abs(v-row.actual[i]))):Infinity;
  result.picking.push({...row,camera,cell_error:delta,ok:delta<=1&&row.sent_cell_error<=1});
 }
}
await page.close();
for(const layout of ['desktop','landscape','portrait']) {
 const context=await browser.newContext(layout==='desktop'?{viewport:{width:1440,height:900}}:nothingPhone1(layout==='landscape'));
 const p=await context.newPage();
 if(layout!=='desktop') await throttlePhone(context,p);
 await p.goto(site+'?view=arena&play=race-the-ghost&pl=warm-up&attract=off');
 await p.waitForFunction(()=>window.__cocoArena?.client?.world,{timeout:90000});
 const disabled=await p.locator('[data-testid^=planner-]').evaluateAll(el=>el.length>0&&el.every(x=>x.disabled));
 await p.keyboard.press('KeyE');await p.keyboard.press('Tab');
 await p.waitForTimeout(1000);
 const forbidden=await p.evaluate(()=>window.__cocoArena.log().filter(r=>['grasp','planner','autonomy'].includes(r.kind)));
 await p.screenshot({path:`${screens}/race-${layout==='desktop'?'desktop':'nothing-'+layout}.png`,fullPage:true});
 result.race.push({layout,device:layout==='desktop'?'laptop':DEVICE_NAME,cpu_throttle:layout==='desktop'?1:4,disabled,forbidden,ok:disabled&&!forbidden.length});
 await context.close();
}
await browser.close();
result.ok=!result.errors.length&&result.picking.every(r=>r.ok)&&result.race.every(r=>r.ok);
writeFileSync(out+'/check.json',JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');
console.log(JSON.stringify(result));
process.exitCode=result.ok?0:1;
