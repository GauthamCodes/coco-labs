// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from 'playwright';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {conditions} from './perf/conditions.mjs';
import {nothingPhone1,throttlePhone,DEVICE_NAME} from './phone/nothing-phone-1.mjs';
const site=process.argv[2],out=resolve(process.argv[3]),start=conditions(),rows=[];
const levels=JSON.parse(readFileSync(new URL('../play/levels.json',import.meta.url)));
const cases=[{name:'games',query:'?view=play',wait:'[data-testid="challenge-race-the-ghost"]'}];
for(const challenge of ['beat-the-planner','next-node','search-the-bays']){
 const level=levels.challenges[challenge].levels[0];
 cases.push({name:challenge,query:`?view=play&c=${challenge}&l=${level.id}`,wait:challenge==='search-the-bays'?'[data-testid="bay-0"]':'[data-testid="grid-board"]'});
}
for(const challenge of ['map-the-arena','race-the-ghost']){
 const level=levels.challenges[challenge].levels[0],q=new URLSearchParams({view:'arena',play:challenge,pl:level.id,camera:'follow'});
 if(challenge==='map-the-arena'){q.set('lens','map');q.set('level','explain');for(const line of level.config)q.append('cfg',line);}
 else q.set('seed',String(level.seed));
 cases.push({name:challenge,query:'?'+q,wait:'[data-testid="play-meter"]'});
}
mkdirSync(out,{recursive:true});const browser=await chromium.launch();
try{for(const profile of [
 {name:'desktop',device:'laptop Chromium',options:{viewport:{width:1440,height:900}}},
 {name:'compact',device:'laptop Chromium compact',options:{viewport:{width:844,height:390}}},
 {name:'nothing-landscape',device:DEVICE_NAME,options:nothingPhone1(true)},
 {name:'nothing-portrait',device:DEVICE_NAME,options:nothingPhone1(false)},
])for(const game of cases){
 const context=await browser.newContext(profile.options),page=await context.newPage(),errors=[];
 if(profile.device===DEVICE_NAME)await throttlePhone(context,page);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(site+game.query);await page.waitForSelector(game.wait,{state:'attached',timeout:180000});await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(600);
 const layout=await page.evaluate(()=>{
  const visible=e=>{const b=e.getBoundingClientRect(),s=getComputedStyle(e);return b.width>0&&b.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&!e.closest('dialog:not([open])');};
  const controls=[...document.querySelectorAll('main button,main a,main input,main select,main summary,main [role=application],main canvas[data-testid=arena-canvas],main canvas[data-testid=grid-board]')].filter(visible).map(e=>({name:e.ariaLabel||e.textContent.trim()||e.dataset.testid,box:e.getBoundingClientRect().toJSON()}));
  const canvas=document.querySelector('[data-testid="arena-canvas"]'),gl=canvas?.getContext('webgl2'),ext=gl?.getExtension('WEBGL_debug_renderer_info');
  return {viewport:[innerWidth,innerHeight],scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],controls,renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):null};
 });
 const failure=layout.scroll[0]>layout.viewport[0]||layout.scroll[1]>layout.viewport[1]?'page scroll':layout.controls.length>8?`${layout.controls.length} controls`:layout.controls.some(c=>c.box.left<0||c.box.top<0||c.box.right>layout.viewport[0]+1||c.box.bottom>layout.viewport[1]+1)?'control outside viewport':null;
 await page.screenshot({path:resolve(out,profile.name+'-'+game.name+'.png'),scale:'css'});
 rows.push({profile:profile.name,device:profile.device,game:game.name,layout,errors,failure});await context.close();
 if(profile.device===DEVICE_NAME&&layout.controls.some(control=>control.box.width<47.9||control.box.height<47.9))throw Error(`${profile.name} ${game.name}: touch target below 48 CSS px`);
 if(failure||errors.length)throw Error(`${profile.name} ${game.name}: ${failure??errors.join('; ')}`);
}}finally{await browser.close();writeFileSync(resolve(out,'decisions-focus.json'),JSON.stringify({class:'TESTED functional layout; not FPS/startup measurement',conditions:{start,end:conditions()},rows},null,2)+'\n');}
console.log('All menu/decision/drive layouts meet Focus, including their interactive canvases.');
