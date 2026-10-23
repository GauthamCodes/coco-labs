// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import{chromium}from'playwright';import{mkdirSync,writeFileSync}from'node:fs';
import { conditions } from './conditions.mjs';import{nothingPhone1,throttlePhone,DEVICE_NAME}from'../phone/nothing-phone-1.mjs';
const CONDITIONS_AT_START = conditions();
const site=process.argv[2]??'http://127.0.0.1:4206/coco-labs/',out=process.argv[3]??'../docs/v2/data/m5/screens/compare/families-refined',profile=process.argv[4]??'desktop';mkdirSync(out,{recursive:true});
const report={class:'Functional diagnostic, not acceptance timing/FPS',conditions:conditions(),profile:profile==='desktop'?'desktop':DEVICE_NAME+' '+profile,cases:[],errors:[],progress:[]};
const b=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});const ctx=await b.newContext(profile==='desktop'?{viewport:{width:1440,height:900}}:nothingPhone1(profile==='landscape'));const p=await ctx.newPage();if(profile!=='desktop')await throttlePhone(ctx,p);
p.on('pageerror',e=>report.errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});
const save=()=>writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');let timer,monitor=Promise.resolve();
const ready=()=>Promise.race([p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]',{timeout:240000}),p.locator('.compare-controls [role="alert"]').waitFor({timeout:240000}).then(async()=>{throw Error(await p.locator('.compare-controls [role="alert"]').innerText())})]);
const open=async()=>{if(profile!=='desktop')await p.getByRole('button',{name:'Controls',exact:true}).click()};const close=async()=>{if(profile!=='desktop')await p.getByRole('button',{name:'Close controls',exact:true}).click()};
const capture=async name=>{await close();await p.screenshot({path:out+'/'+name+'.png'});report.cases.push({name,results:await p.locator('.compare-results').innerText()});save();};
try{await p.goto(site+'?view=compare');await ready();timer=setInterval(()=>{monitor=monitor.then(async()=>{report.progress.push({at:new Date().toISOString(),status:await p.locator('.compare-controls [role="status"]').innerText()});save()}).catch(()=>{})},15000);
await open();await p.getByRole('combobox',{name:'Algorithm A',exact:true}).selectOption('dstar_lite');await ready();await capture('dstar');
await open();await p.getByRole('combobox',{name:'Family',exact:true}).selectOption('control');await ready();await capture('control');
if(profile==='desktop'){await p.getByRole('combobox',{name:'Algorithm A',exact:true}).selectOption('mppi');await ready();await capture('mppi');}
await open();await p.getByRole('combobox',{name:'Family',exact:true}).selectOption('localise');await ready();await capture('mcl-injection');
if(profile==='desktop'){await p.getByRole('combobox',{name:'Algorithm B',exact:true}).selectOption('ekf');await ready();await capture('ekf');}
const slider=p.getByRole('slider',{name:'Shared event cursor'});await slider.fill('1');await p.screenshot({path:out+'/lockstep.png'});await slider.fill('60');report.passed=report.errors.length===0;
}catch(error){report.error=String(error);report.passed=false;process.exitCode=1;}finally{clearInterval(timer);await monitor;report.conditions_end=conditions();save();await b.close();}
