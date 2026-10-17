// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {chromium} from 'playwright';
import {mkdirSync,writeFileSync} from 'node:fs';
import { conditions } from './conditions.mjs';
import {nothingPhone1,throttlePhone,DEVICE_NAME} from '../phone/nothing-phone-1.mjs';
const CONDITIONS_AT_START = conditions();
const site=process.argv[2]??'http://127.0.0.1:4205/coco-labs/';
const out=process.argv[3]??'../docs/v2/data/m5/screens/compare/workspace-first';mkdirSync(out,{recursive:true});
const browser=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']});
const report={conditions:conditions(),browser:browser.version(),cases:[]};
try {
 for(const [name,profile] of [['desktop',{viewport:{width:1440,height:900}}],['compact',{viewport:{width:844,height:390}}],['nothing-landscape',nothingPhone1(true)],['nothing-portrait',nothingPhone1(false)]]) {
  const context=await browser.newContext(profile),page=await context.newPage();const errors=[];
  if(name.startsWith('nothing'))await throttlePhone(context,page);
  page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext,seen=new Set();window.__compareContexts=seen;HTMLCanvasElement.prototype.getContext=function(...args){const result=get.apply(this,args);if(args[0].startsWith('webgl')&&result)seen.add(result);return result;}});
  await page.goto(site+'?view=compare');
  await page.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]',{timeout:180000});
  await page.waitForSelector('canvas[data-scene-ready="true"]',{timeout:90000});
  for(const panes of [2,4]) {
   if(panes===4){if(name!=='desktop')await page.getByRole('button',{name:'Controls',exact:true}).click();await page.locator('.compare-controls select').nth(1).selectOption('4');await page.waitForSelector('[data-testid="compare-workspace"][data-ready="true"]',{timeout:180000});if(name!=='desktop')await page.getByRole('button',{name:'Close controls',exact:true}).click();}
   await page.waitForTimeout(500);
   const layout=await page.evaluate(()=>{const canvas=document.querySelector('.compare-stage canvas'),b=canvas.getBoundingClientRect(),gl=canvas.getContext('webgl2'),debug=gl?.getExtension('WEBGL_debug_renderer_info');return {scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],viewport:[innerWidth,innerHeight],stage:{x:b.x,y:b.y,width:b.width,height:b.height},contexts:window.__compareContexts.size,renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):'unavailable',labels:[...document.querySelectorAll('.compare-labels>div')].map(e=>e.getBoundingClientRect().toJSON())};});
   if(layout.contexts!==1||layout.stage.width<100||layout.stage.height<80||layout.scroll[0]>layout.viewport[0]+1||layout.scroll[1]>layout.viewport[1]+1)throw Error(name+' bad layout '+JSON.stringify(layout));
   await page.screenshot({path:`${out}/${name}-${panes}.png`});
   report.cases.push({name,device:name.startsWith('nothing')?DEVICE_NAME:'desktop viewport',panes,layout,errors:[...errors]});
  }
  if(name!=='desktop')await page.getByRole('button',{name:'Controls',exact:true}).click();
  await page.getByRole('button',{name:'A/B difference',exact:true}).click();
  if(name!=='desktop')await page.getByRole('button',{name:'Close controls',exact:true}).click();
  await page.screenshot({path:`${out}/${name}-difference.png`});
  const timeline=page.getByRole('slider',{name:'Shared event cursor'});await timeline.fill('0');await timeline.press('ArrowRight');
  if(errors.length)throw Error(name+': '+errors.join('\n'));
  await context.close();
 }
 report.passed=true;
} catch(error){report.passed=false;report.error=String(error);process.exitCode=1;}finally{report.conditions_end=conditions();writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');await browser.close();}
