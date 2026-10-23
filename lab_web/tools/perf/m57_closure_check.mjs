// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [site,out]=process.argv.slice(2);mkdirSync(out,{recursive:true});const report={errors:[],tours:[]};
const browser=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist']});const page=await browser.newPage({viewport:{width:1440,height:900}});
page.on('pageerror',e=>report.errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});
try{
 await page.goto(site+'?view=arena&camera=topdown');await page.waitForFunction(()=>!!window.__cocoArena?.client?.world,null,{timeout:120000});
 await page.getByRole('button',{name:'Settings',exact:true}).click();await page.getByRole('button',{name:'Skip tutorial',exact:true}).click();
 await page.evaluate(()=>document.activeElement?.blur());await page.keyboard.press('KeyW');await page.waitForFunction(()=>!!window.__cocoArena?.last,null,{timeout:120000});await page.evaluate(()=>window.__cocoArena.session().playing=false);await page.waitForTimeout(300);
 const before=await page.evaluate(()=>({hash:window.__cocoArena.last.hash,log:window.__cocoArena.log().length}));
 await page.evaluate(()=>document.activeElement?.blur());for(let i=0;i<3;i++)await page.keyboard.press('KeyX');
 await page.waitForFunction(()=>window.__cocoArena.renderer.costmapTick!==null,null,{timeout:30000});
 report.costmap=await page.evaluate(()=>({tick:window.__cocoArena.renderer.costmapTick,hash:window.__cocoArena.last.hash,log:window.__cocoArena.log().length}));
 if(before.hash!==report.costmap.hash||before.log!==report.costmap.log)throw Error('Costmap snapshot mutated model');await page.screenshot({path:out+'/play-costmap.png'});
 const missions=['first-steps','heuristics','world-changes','mapping','kidnapped','search','local-control'];
 // Read committed mission IDs rather than assume names.
 const doc=await (await page.request.get(site+'generated/missions.json')).json();
 for(const m of doc.missions){await page.goto(site+'?view=compare&tour='+m.id);await page.locator('[data-testid="mission"][data-mission="'+m.id+'"]').waitFor({timeout:120000});report.tours.push(m.id)}
 const stories=JSON.parse(await (await import('node:fs/promises')).readFile(new URL('../../tours/stories.json',import.meta.url),'utf8'));
 for(const s of stories){await page.goto(site+'?view=compare&tour='+s.id);await page.getByTestId('story-tour').waitFor();const refs=await page.getByTestId('story-tour').locator('a.cite').count();if(refs<s.claims.length)throw Error('Missing story citations');report.tours.push(s.id)}
 report.passed=report.errors.length===0;
}catch(e){report.error=String(e);report.passed=false;process.exitCode=1}finally{await browser.close();writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n')}
