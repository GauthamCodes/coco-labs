// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Real app routes/modal behaviour. Layout checks are not startup benchmarks. */
import {chromium} from 'playwright';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {conditions} from './perf/conditions.mjs';
import {nothingPhone1,throttlePhone,DEVICE_NAME} from './phone/nothing-phone-1.mjs';
const site=process.argv[2],out=resolve(process.argv[3]),start=conditions(),rows=[];
mkdirSync(out,{recursive:true});const browser=await chromium.launch();
try{for(const profile of [
 {name:'desktop',device:'laptop Chromium',options:{viewport:{width:1440,height:900}}},
 {name:'compact',device:'laptop Chromium, compact viewport',options:{viewport:{width:844,height:390}}},
 {name:'nothing-landscape',device:DEVICE_NAME,options:nothingPhone1(true)},
 {name:'nothing-portrait',device:DEVICE_NAME,options:nothingPhone1(false)},
])for(const view of ['title','play','compare','research','about']){
 const context=await browser.newContext(profile.options),page=await context.newPage(),errors=[],external=[];
 if(profile.device===DEVICE_NAME)await throttlePhone(context,page);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('request',r=>{if(new URL(r.url()).origin!==new URL(site).origin)external.push(r.url());});
 await page.goto(site+(view==='title'?'':'?view='+view));
 const selector={title:'[data-testid="title"] canvas[data-scene-ready="true"]',play:'[data-testid="play"] .play-challenge',compare:'[data-testid="reference-compare"][data-ready="true"]',research:'[data-testid="casefiles"] [data-testid^="group-"]',about:'[data-testid="about"]'}[view];
 await page.waitForSelector(selector,{timeout:120000});await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(300);
 const inspection=await page.evaluate(()=>({viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],theme:document.documentElement.dataset.theme,quality:document.querySelector('.night-world')?.dataset.qualityTier,robot:document.querySelector('.night-world')?.dataset.robotPose,worldStart:window.__cocoReference?.world.start,header:[...document.querySelectorAll('.mode-head a,.mode-head button')].map(e=>({text:e.textContent||e.ariaLabel,box:e.getBoundingClientRect().toJSON()}))}));
 if(inspection.header.some(r=>r.box.left<-.5||r.box.right>inspection.viewport[0]+.5))throw Error(profile.name+' '+view+' header clipped');
 if(view==='compare'){const pose=JSON.parse(inspection.robot);if(pose.slice(0,2).some((x,i)=>Math.abs(x-inspection.worldStart[i])>1e-8))throw Error('CAD body and planner start disagree');}
 await page.screenshot({path:resolve(out,profile.name+'-'+view+'.png'),scale:'css'});
 let settings=null;
 if(view==='compare'){
  await page.evaluate(()=>{window.__beforeReference=window.__cocoReference;});await page.getByRole('button',{name:'Settings',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.waitFor();
  await dialog.getByLabel('Theme',{exact:true}).selectOption('light');await dialog.getByLabel('Quality',{exact:true}).selectOption('medium');await dialog.getByLabel('Wall display',{exact:true}).selectOption('half');await dialog.getByLabel('Reduced motion',{exact:true}).check();
  await page.waitForFunction(()=>document.documentElement.dataset.theme==='light'&&document.documentElement.dataset.motion==='reduced');
  for(let n=0;n<32;n++){await page.keyboard.press('Tab');if(!await page.evaluate(()=>!!document.activeElement?.closest('dialog')))throw Error('Keyboard focus escaped modal');}
  await dialog.getByRole('button',{name:'Close settings'}).focus();
  await page.screenshot({path:resolve(out,profile.name+'-settings-light.png'),scale:'css'});
  settings=await page.evaluate(()=>({theme:document.documentElement.dataset.theme,motion:document.documentElement.dataset.motion,sameModel:window.__beforeReference===window.__cocoReference,box:document.querySelector('dialog').getBoundingClientRect().toJSON()}));
  if(!settings.sameModel)throw Error('Settings reset the model');await page.getByRole('button',{name:'Close settings'}).click();if(await page.evaluate(()=>document.activeElement?.getAttribute('aria-label'))!=='Settings')throw Error('Modal did not restore focus');
 }
 rows.push({profile:profile.name,device:profile.device,cpuThrottle:profile.device===DEVICE_NAME?4:1,network:'local unthrottled; not a startup benchmark',view,...inspection,settings,errors,external});await context.close();
}}finally{await browser.close();writeFileSync(resolve(out,'shell-check.json'),JSON.stringify({conditions:{start,end:conditions()},rows},null,1)+'\n');}
if(rows.some(r=>r.errors.length||r.external.length))throw Error('Shell console/network check failed');
console.log('Captured '+rows.length+' app views and four Settings drawers; zero console errors/external requests; focus and model continuity pass.');
