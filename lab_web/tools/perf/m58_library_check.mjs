// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { conditions } from './conditions.mjs';
import { nothingPhone1, throttlePhone, DEVICE_NAME } from '../phone/nothing-phone-1.mjs';
const CONDITIONS_AT_START = conditions();
const [site,out]=process.argv.slice(2);mkdirSync(out,{recursive:true});const report={profiles:[],errors:[]};
const b=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist']});
try{for(const profile of [{name:'desktop',viewport:{width:1440,height:900}},{name:'compact',viewport:{width:844,height:390}},{name:'nothing-landscape',phone:true,landscape:true},{name:'nothing-portrait',phone:true,landscape:false}]){
 const ctx=await b.newContext(profile.phone?nothingPhone1(profile.landscape):{viewport:profile.viewport});const p=await ctx.newPage();if(profile.phone)await throttlePhone(ctx,p);
 p.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});p.on('pageerror',e=>report.errors.push(String(e)));
 const mcap=[];p.on('request',r=>{if(r.url().endsWith('.mcap'))mcap.push(r.url())});await p.goto(site+'?view=research');await p.locator('.recording-card').first().waitFor();
 const cases=await(await p.request.get(site+'generated/casefiles/cases.json')).json(),runs=await(await p.request.get(site+'generated/v2/index.json')).json();
 const expected=[...new Set(cases.groups.flatMap(g=>g.casefiles.map(f=>'casefile:'+f.id))),...runs.runs.map(r=>'converted:'+r.id)].sort();
 const actual=await p.locator('.recording-card').evaluateAll(cards=>cards.map(e=>e.dataset.kind+':'+e.dataset.recordingId).sort());if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error('Library omitted or duplicated a recording');if(mcap.length)throw Error('Library fetched recordings before opening');
 if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal page overflow');
 await p.screenshot({path:out+'/'+profile.name+'.png',fullPage:false});
 await p.getByRole('button',{name:'Failures',exact:true}).click();const failures=await p.locator('.recording-card').count();if(!failures||failures===actual.length)throw Error('Failures filter ineffective');
 await p.getByRole('searchbox',{name:'Search recordings',exact:true}).fill('DWB');if(!await p.locator('.recording-card').count())throw Error('Search lost known DWB failures');
 if(profile.name!=='desktop')await p.getByRole('button',{name:'Filters',exact:true}).click();
 const controls=profile.name==='desktop'?p.locator('.library-sidebar'):p.getByRole('dialog',{name:'Recording filters'});
 await controls.getByRole('combobox',{name:'Evidence class',exact:true}).selectOption('MODEL');if(await p.locator('.recording-card').count())throw Error('Conjunctive filters not applied');
 await controls.getByRole('button',{name:'Clear filters',exact:true}).click();if(profile.name!=='desktop'){await p.keyboard.press('Escape');if(await p.evaluate(()=>document.activeElement?.textContent)!=='Filters')throw Error('Sheet did not restore focus')}
 if(await p.locator('.recording-card').count()!==expected.length)throw Error('Clear failed');await p.screenshot({path:out+'/'+profile.name+'-restored.png'});
 if(profile.name==='desktop'){
  await p.locator('[data-kind="casefile"] h2 a').first().click();await p.waitForFunction(()=>!!window.__cocoArena?.session()?.shownTick,null,{timeout:120000});
  if(!new URL(p.url()).searchParams.has('casefile'))throw Error('Case File not in viewer');
  await p.getByRole('link',{name:'Browse the Recordings library →'}).click();await p.locator('.recording-card').first().waitFor();
  await p.locator('[data-kind="converted"] h2 a').first().click();await p.waitForFunction(()=>!!window.__cocoArena?.session()?.shownTick,null,{timeout:120000});if(!new URL(p.url()).searchParams.has('replay'))throw Error('Converted run not in viewer');
 }
 report.profiles.push({name:profile.name,device:profile.phone?DEVICE_NAME:'desktop viewport',recordings:actual.length,failures,recordingFetchesBeforeOpen:0});await ctx.close();
}report.passed=report.errors.length===0}catch(e){report.error=String(e);report.passed=false;process.exitCode=1}finally{await b.close();writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n')}
