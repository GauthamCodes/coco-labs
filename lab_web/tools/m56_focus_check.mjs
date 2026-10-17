// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from 'playwright';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {conditions} from './perf/conditions.mjs';
import {nothingPhone1,throttlePhone,DEVICE_NAME} from './phone/nothing-phone-1.mjs';
const site=process.argv[2],out=resolve(process.argv[3]),start=conditions(),rows=[];
mkdirSync(out,{recursive:true});const browser=await chromium.launch();
try{for(const profile of [
 {name:'desktop',device:'laptop Chromium',options:{viewport:{width:1440,height:900}}},
 {name:'compact',device:'laptop Chromium compact',options:{viewport:{width:844,height:390}}},
 {name:'nothing-landscape',device:DEVICE_NAME,options:nothingPhone1(true)},
 {name:'nothing-portrait',device:DEVICE_NAME,options:nothingPhone1(false)},
]){
 const context=await browser.newContext(profile.options),page=await context.newPage(),errors=[];
 if(profile.device===DEVICE_NAME)await throttlePhone(context,page);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(site+'?view=arena&camera=follow');await page.waitForFunction(()=>!!window.__cocoArena?.client?.world,null,{timeout:120000});await page.waitForTimeout(2000);
 const layout=await page.evaluate(()=>{
  const visible=e=>{const b=e.getBoundingClientRect(),s=getComputedStyle(e);return b.width>0&&b.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&!e.closest('dialog:not([open])');};
  const controls=[...document.querySelectorAll('.coco-play button,.coco-play a,.coco-play input,.coco-play select,.coco-play [role=application],.coco-play canvas[data-testid=arena-canvas]')].filter(visible).map(e=>({name:e.ariaLabel||e.textContent.trim(),box:e.getBoundingClientRect().toJSON()}));
  return {viewport:[innerWidth,innerHeight],scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],controls,joysticks:[...document.querySelectorAll('[data-testid="arena-joystick"]')].filter(visible).length,rotate:getComputedStyle(document.querySelector('.night-rotate')).display};
 });
 if(layout.scroll[0]>layout.viewport[0]||layout.scroll[1]>layout.viewport[1])throw Error(profile.name+' page scroll');
 if(layout.controls.length>8)throw Error(profile.name+' '+layout.controls.length+' visible controls');
 if(profile.name==='nothing-portrait'&&layout.rotate==='none')throw Error('Missing rotate card');
 if(profile.device!==DEVICE_NAME&&layout.joysticks)throw Error('Desktop joystick');
 await page.screenshot({path:resolve(out,profile.name+'.png'),scale:'css'});
 if(errors.length)throw Error(errors.join('\n'));rows.push({...profile,options:undefined,layout,errors});await context.close();
}}finally{await browser.close();writeFileSync(resolve(out,'focus.json'),JSON.stringify({class:'TESTED layout; not a frame-rate measurement',conditions:{start,end:conditions()},rows},null,2)+'\n');}
console.log('Play focus: all four viewports, <=8 visible controls, no scroll, desktop has no joystick.');
