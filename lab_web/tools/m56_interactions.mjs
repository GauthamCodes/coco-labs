// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from 'playwright';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {conditions} from './perf/conditions.mjs';
const site=process.argv[2],out=resolve(process.argv[3]),start=conditions(),errors=[],result={};
mkdirSync(out,{recursive:true});const browser=await chromium.launch();
try{
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(site+'?view=arena&camera=follow&perf');
 await page.waitForFunction(()=>!!window.__cocoArena?.client?.world,null,{timeout:120000});
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 await page.getByRole('button',{name:'Skip tutorial',exact:true}).click();
 await page.waitForFunction(()=>window.__cocoArena.renderer.three?.ready,null,{timeout:120000});
 await page.evaluate(()=>{document.activeElement?.blur();window.__cocoArena.renderer.setCameraMode('topdown');});
 result.historyView='top-down, to isolate functional history checks from software GL speed';
 console.log('Model and real CAD ready; top-down history check.');
 // Drive with the actual keyboard path, then let the reference clock accumulate 10 s of history.
 await page.keyboard.down('KeyW');await page.waitForTimeout(1200);await page.keyboard.up('KeyW');
 await page.waitForFunction(()=>window.__cocoArena.last?.tick>=115,null,{timeout:60000});
 await page.evaluate(()=>{window.__cocoArena.session().playing=false;});await page.waitForTimeout(150);
 const before=await page.evaluate(()=>({hash:window.__cocoArena.last.hash,log:window.__cocoArena.log().length}));
 result.vision=[];
 for(let phase=1;phase<=5;phase++){
  await page.keyboard.press('KeyX');await page.waitForTimeout(150);
  const state=await page.evaluate(()=>{const a=window.__cocoArena,r=a.renderer;return{label:document.querySelector('.night-vision').ariaLabel,hash:a.last.hash,log:a.log().length,rays:r.lidar.visible,area:r.scanFill.visible,hits:r.scanHits.geometry.attributes.position?.count??0};});
  if(state.hash!==before.hash||state.log!==before.log)throw Error('Vision changed model state or input log');
  if(phase===1&&(!state.area||state.rays||!state.hits))throw Error('Scan area not drawn from actual hits');
  result.vision.push(state);
  if(phase===1)await page.screenshot({path:resolve(out,'desktop-scan-area.png'),scale:'css'});
 }
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 const settings=page.getByRole('dialog',{name:'Settings',exact:true});
 for(const [value,expected] of [['full',1],['half',.5]]){
  await settings.getByLabel('Wall display',{exact:true}).selectOption(value);await page.waitForTimeout(100);
  const state=await page.evaluate(()=>({scales:window.__cocoArena.renderer.three.wallMeshes.map(m=>m.scale.z),hash:window.__cocoArena.last.hash}));
  if(!state.scales.length||state.scales.some(z=>z!==expected)||state.hash!==before.hash)throw Error('Wall display touched model or lost original cap geometry');
 }
 await settings.getByRole('button',{name:'Game menu and inspection'}).click();
 const menu=page.getByRole('dialog',{name:'Game menu',exact:true});await menu.waitFor();
 if(await menu.getByTestId('arena-joystick').count())throw Error('Desktop menu exposes a joystick');
 for(let n=0;n<40;n++){await page.keyboard.press('Tab');if(!await page.evaluate(()=>!!document.activeElement?.closest('dialog[open]')))throw Error('Menu focus escaped');}
 await menu.getByRole('button',{name:'Replay last 10 seconds'}).click();
 const replay=page.getByRole('dialog',{name:'Instant replay',exact:true});await replay.waitFor();
 await page.waitForTimeout(1000);
 result.replay=await page.evaluate(()=>({shown:window.__cocoArena.session().shownTick.tick,head:window.__cocoArena.session().head,hash:window.__cocoArena.last.hash}));
 if(result.replay.shown>=result.replay.head||result.replay.hash!==before.hash)throw Error('Instant replay re-simulated or failed to seek history');
 await page.screenshot({path:resolve(out,'desktop-instant-replay.png'),scale:'css'});
 await replay.getByRole('button',{name:'Back to Play'}).click();
 await page.evaluate(()=>{window.__cocoArena.session().playing=true;Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});});
 await page.waitForTimeout(150);const hiddenStart=await page.evaluate(()=>window.__cocoArena.last.tick);
 await page.waitForTimeout(650);result.hidden=await page.evaluate(()=>({tick:window.__cocoArena.last.tick,fps:window.__cocoPerf.snapshot().fps}));
 if(result.hidden.tick!==hiddenStart)throw Error('Hidden page still stepped');
 await page.evaluate(()=>{delete document.hidden;});await page.waitForTimeout(250);
 await page.close();
 const tutorial=await browser.newPage({viewport:{width:1440,height:900}});
 tutorial.on('pageerror',e=>errors.push(e.message));tutorial.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await tutorial.goto(site+'?view=arena&camera=follow');
 await tutorial.waitForFunction(()=>!!window.__cocoArena?.client?.world,null,{timeout:120000});
 await tutorial.evaluate(()=>{document.activeElement?.blur();window.__cocoArena.renderer.setCameraMode('topdown');});
 await tutorial.keyboard.down('KeyW');
 await tutorial.waitForFunction(()=>document.querySelector('.play-tutorial p')?.textContent.startsWith('Click or tap'),null,{timeout:90000});
 await tutorial.keyboard.up('KeyW');
 await tutorial.evaluate(()=>window.__cocoArena.goal(2.5,2));
 await tutorial.waitForFunction(()=>document.querySelector('.play-tutorial p')?.textContent.startsWith('Press X'),null,{timeout:90000});
 await tutorial.keyboard.press('KeyX');
 await tutorial.locator('.play-tutorial').waitFor({state:'detached'});
 await tutorial.reload();await tutorial.waitForFunction(()=>!!window.__cocoArena?.client?.world,null,{timeout:120000});
 if(await tutorial.locator('.play-tutorial').count())throw Error('Completed tutorial was not remembered');
 result.tutorial='Real drive to marker, real goal/search, X; completion remembered after reload. Skip exercised through Settings in the first session.';
 result.errors=errors;if(errors.length)throw Error(errors.join('\n'));
}finally{await browser.close();writeFileSync(resolve(out,'interactions.json'),JSON.stringify({class:'TESTED functional checks, synthetic visibility; no performance budget claim',conditions:{start,end:conditions()},result,errors},null,2)+'\n');}
console.log('Vision/walls preserve frozen model hash and input log; scan hits, modal focus, historical replay and hidden rendering checks pass.');
