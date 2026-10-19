// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone, DEVICE_NAME } from '../phone/nothing-phone-1.mjs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [site,out]=process.argv.slice(2);mkdirSync(out,{recursive:true});const report={device:DEVICE_NAME,scope:'Viewport/CPU/network emulation on laptop GPU; no phone heat/battery inference',errors:[],samples:[],touchLatencyMs:[],lost:0,reloads:0};
const save=()=>writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');const b=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu']}),ctx=await b.newContext({...nothingPhone1(true),serviceWorkers:'block'}),p=await ctx.newPage();const cdp=await throttlePhone(ctx,p,true);
p.on('pageerror',e=>report.errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});let ready=false;p.on('framenavigated',f=>{if(ready&&f===p.mainFrame())report.reloads++});
try{
 await p.goto(site+'?view=arena&world=v2&camera=follow&perf');await p.waitForFunction(()=>!!window.__cocoArena?.last&&!!window.__cocoArena?.renderer?.three?.ready,null,{timeout:120000});await p.keyboard.press('Escape');
 report.renderer=await p.evaluate(()=>{const gl=window.__cocoArena.renderer.renderer.getContext(),e=gl.getExtension('WEBGL_debug_renderer_info');document.querySelector('[data-testid="arena-canvas"]').addEventListener('webglcontextlost',()=>window.__phoneLost=(window.__phoneLost??0)+1);return e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):'unknown'});ready=true;
 const pad=await p.locator('.night-joystick [data-testid="arena-joystick"]').boundingBox(),x=pad.x+pad.width/2,y=pad.y+pad.height/2;
 const touch=async on=>cdp.send('Input.dispatchTouchEvent',{type:on?'touchStart':'touchEnd',touchPoints:on?[{x,y:y-pad.height*.27,radiusX:12,radiusY:12,id:1}]:[]});
 for(let i=0;i<20;i++){
  await p.getByTestId('hud-stop').tap();await p.waitForTimeout(400);await p.getByTestId('hud-release').tap();await p.waitForTimeout(400);const count=await p.evaluate(()=>window.__cocoPerf.inputToMotion.length);await touch(true);await p.waitForTimeout(400);await touch(false);await p.waitForTimeout(400);const latency=await p.evaluate(()=>window.__cocoPerf.inputToMotion);if(latency.length>count||latency.length===20)report.touchLatencyMs.push(latency.at(-1));
 }
 await p.getByTestId('hud-stop').tap();await p.getByTestId('hud-release').tap();const started=Date.now();await touch(true);
 while(Date.now()-started<600000){await p.waitForTimeout(1000);const sample=await p.evaluate(()=>{const s=window.__cocoPerf.snapshot(),r=window.__cocoArena.renderer;return{fps:s.fps,p95:s.frameMsP95,tick:window.__cocoArena.last.tick,tier:r.quality?.tier,pixelRatio:r.renderer.getPixelRatio(),visible:!document.hidden,lost:window.__phoneLost??0}});report.samples.push({seconds:(Date.now()-started)/1000,...sample});if(report.samples.length%15===0)save();}
 await touch(false);report.elapsedSeconds=(Date.now()-started)/1000;report.lost=await p.evaluate(()=>window.__phoneLost??0);const stats=rows=>{const fps=rows.map(s=>s.fps).sort((a,b)=>a-b);return{seconds:rows.length,median:fps[Math.floor(fps.length/2)],minimum:fps[0],p05:fps[Math.floor(fps.length*.05)]}};report.firstMinute=stats(report.samples.filter(s=>s.seconds<=60));report.tenMinutes=stats(report.samples);await p.screenshot({path:out+'/landscape-after-ten-minutes.png'});report.passed=report.errors.length===0&&!report.lost&&!report.reloads;
}catch(e){report.error=String(e);report.passed=false;process.exitCode=1}finally{await b.close();save()}
