// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from 'playwright';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {conditions} from './perf/conditions.mjs';
import {nothingPhone1,throttlePhone,DEVICE_NAME} from './phone/nothing-phone-1.mjs';
const site=process.argv[2],out=resolve(process.argv[3]),start=conditions(),rows=[];
const fixture=JSON.parse(readFileSync(new URL('../../docs/v2/data/m5/play/challenges/play_check_chromium.json',import.meta.url))).rows.find(row=>row.challenge==='beat-the-planner');
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
 await page.goto(site+new URL(fixture.link).search);await page.getByTestId('play-reproduced').waitFor({timeout:180000});
 const result=page.getByTestId('play-result'),dialog=page.getByRole('dialog',{name:'Scorecard',exact:true});
 if(await result.getAttribute('data-hash')!==fixture.hash)throw Error('Shared score changed hash');
 await dialog.getByRole('button',{name:'Replay',exact:true}).waitFor();await dialog.getByRole('button',{name:'Try again',exact:true}).waitFor();await dialog.getByRole('button',{name:'Share',exact:true}).waitFor();
 await page.screenshot({path:resolve(out,profile.name+'-scorecard-initial.png'),scale:'css'});
 for(let n=0;n<30;n++){await page.keyboard.press('Tab');if(!await page.evaluate(()=>!!document.activeElement?.closest('dialog[open]')))throw Error('Scorecard focus escaped');}
 await page.screenshot({path:resolve(out,profile.name+'-scorecard.png'),scale:'css'});
 if(profile.name==='nothing-portrait')await page.setViewportSize({width:915,height:412});
 await dialog.getByRole('button',{name:'Replay',exact:true}).click();
 if(profile.name!=='nothing-portrait')await page.getByRole('img',{name:'Your recorded path and the reference path'}).waitFor();
 await page.getByRole('button',{name:'Back to scorecard'}).click();await dialog.waitFor();
 if(errors.length)throw Error(errors.join('\n'));
 rows.push({profile:profile.name,device:profile.device,hash:fixture.hash,stars:Number(await result.getAttribute('data-stars')),metrics:await result.locator('[data-metric]').count(),errors});await context.close();
}}finally{await browser.close();writeFileSync(resolve(out,'scorecards.json'),JSON.stringify({class:'TESTED shared inputs replay and layout; no performance-budget claim',conditions:{start,end:conditions()},rows},null,2)+'\n');}
console.log('Four scorecards reproduce the real shared hash, retain all metrics, trap focus and reopen after replay.');
