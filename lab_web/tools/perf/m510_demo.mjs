// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [site,out]=process.argv.slice(2);mkdirSync(out,{recursive:true});const report={class:'Local silent demo draft, not a benchmark',errors:[],steps:[]};
const b=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});const ctx=await b.newContext({viewport:{width:1440,height:900},recordVideo:{dir:out,size:{width:1440,height:900}}}),p=await ctx.newPage(),video=p.video(),started=Date.now();
p.on('pageerror',e=>report.errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});const step=name=>report.steps.push({name,seconds:(Date.now()-started)/1000});
try{
 await p.goto(site);await p.waitForSelector('[data-scene-ready="true"]',{timeout:120000});step('Title');await p.waitForTimeout(6000);
 await p.getByRole('link',{name:/^Play Drive COCO/}).click();await p.getByRole('link',{name:/Free roam Drive/}).waitFor();step('Play cards');await p.waitForTimeout(4000);await p.getByRole('link',{name:/Free roam Drive/}).click();
 await p.waitForFunction(()=>!!window.__cocoArena?.client?.world,null,{timeout:120000});await p.keyboard.press('Escape');await p.keyboard.down('KeyW');await p.waitForTimeout(2200);await p.keyboard.up('KeyW');await p.keyboard.down('KeyD');await p.waitForTimeout(700);await p.keyboard.up('KeyD');await p.keyboard.down('KeyW');await p.waitForTimeout(1300);await p.keyboard.up('KeyW');step('Drive');
 await p.keyboard.press('KeyX');await p.waitForTimeout(4000);await p.keyboard.press('KeyX');const xy=await p.evaluate(()=>window.__cocoArena.renderer.screenOf(2.5,2));await p.mouse.click(...xy);await p.waitForTimeout(7000);step('Robot vision and goal');
 await p.evaluate(base=>{history.pushState(null,'',base+'?view=compare');dispatchEvent(new PopStateEvent('popstate'))},new URL(site).pathname);await p.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]',{timeout:120000});step('Compare');await p.waitForTimeout(6000);
 await p.getByRole('button',{name:'A/B difference'}).first().click();await p.waitForTimeout(5000);const timeline=p.getByRole('slider',{name:'Shared event cursor'});await timeline.fill('500');await p.waitForTimeout(4000);await timeline.press('End');await p.waitForTimeout(3000);
 await p.getByRole('link',{name:'Research',exact:true}).click();await p.locator('.recording-card').first().waitFor();step('Research');await p.waitForTimeout(3000);await p.getByRole('button',{name:'Failures',exact:true}).click();await p.getByRole('searchbox',{name:'Search recordings'}).fill('DWB');await p.waitForTimeout(5000);await p.locator('.recording-card h2 a').first().click();await p.waitForFunction(()=>!!window.__cocoArena?.session()?.shownTick,null,{timeout:120000});step('STACK recording');
 await p.waitForTimeout(Math.max(0,80000-(Date.now()-started)));report.durationSeconds=(Date.now()-started)/1000;report.renderer=await p.evaluate(()=>{const gl=window.__cocoArena.renderer.renderer.getContext(),e=gl.getExtension('WEBGL_debug_renderer_info');return e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):'unknown'});report.passed=report.errors.length===0;
}catch(e){report.error=String(e);report.passed=false;process.exitCode=1}finally{await ctx.close();await video.saveAs(out+'/coco-m5-demo.webm');await b.close();writeFileSync(out+'/demo.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n')}
