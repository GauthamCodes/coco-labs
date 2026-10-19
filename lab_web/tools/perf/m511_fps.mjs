// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [site,out,only]=process.argv.slice(2);mkdirSync(out,{recursive:true});const report={cases:[]};
const save=()=>writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n');
for(const scenario of [{gpu:'nvidia',mode:'play',quality:'high'},{gpu:'intel',mode:'play',quality:'medium'},{gpu:'intel',mode:'compare',quality:'auto'}].filter(s=>!only||s.mode===only)){
 const flags=scenario.gpu==='intel'?['--use-angle=vulkan','--enable-features=Vulkan','--ignore-gpu-blocklist','--enable-gpu']:['--use-angle=gl-egl','--ignore-gpu-blocklist','--enable-gpu'];const env={...process.env};if(scenario.gpu==='intel')env.VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/intel_icd.json';
 const row={...scenario,flags,conditions:conditions(),errors:[],lost:0,samples:[]};report.cases.push(row);let b;
 try{
 b=await chromium.launch({args:flags,env});const ctx=await b.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'}),p=await ctx.newPage();p.on('pageerror',e=>row.errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')row.errors.push(m.text())});
 await p.addInitScript(()=>{window.__draws={frames:0,serial:0,last:-1,lost:0};const raf=window.requestAnimationFrame.bind(window);window.requestAnimationFrame=fn=>raf(t=>{window.__draws.serial++;fn(t)});const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(...args){const gl=original.apply(this,args);if(gl&&gl.clear&&!gl.__counted){gl.__counted=true;this.addEventListener('webglcontextlost',()=>window.__draws.lost++);const clear=gl.clear.bind(gl);gl.clear=(...values)=>{if(window.__draws.last!==window.__draws.serial){window.__draws.last=window.__draws.serial;window.__draws.frames++}return clear(...values)}}return gl}});
 await p.goto(site+(scenario.mode==='play'?`?view=arena&world=v2&camera=follow&perf&quality=${scenario.quality}`:'?view=compare'));
 if(scenario.mode==='play'){await p.waitForFunction(()=>!!window.__cocoPerf?.marks?.arena_ready&&!!window.__cocoArena?.renderer?.three?.ready,null,{timeout:120000});await p.keyboard.press('Escape');await p.getByTestId('arena-canvas').focus();}
 else{await p.waitForSelector('[data-ready="true"]',{timeout:120000});await p.getByRole('combobox',{name:'Panes',exact:true}).selectOption('4');await p.waitForSelector('[data-ready="true"]',{timeout:120000});await p.getByRole('button',{name:'Replay',exact:true}).click();}
 row.renderer=await p.evaluate(()=>{const gl=document.querySelector('canvas').getContext('webgl2'),e=gl.getExtension('WEBGL_debug_renderer_info');return gl.getParameter(e?e.UNMASKED_RENDERER_WEBGL:gl.RENDERER)});
 if(!new RegExp(scenario.gpu==='intel'?'Intel':'NVIDIA','i').test(row.renderer))throw Error('Requested physical GPU not available: '+row.renderer);
 row.driverSoftware=execFileSync('dpkg-query',['-W','-f=${Package} ${Version}\n','libgl1-mesa-dri','mesa-vulkan-drivers'],{encoding:'utf8'}).trim();await p.waitForTimeout(3000);
 let previous=await p.evaluate(()=>({n:window.__draws.frames,t:performance.now()}));
 for(let i=0;i<20;i++){const key=['KeyW','KeyA','KeyW','KeyD','KeyS'][i%5];if(scenario.mode==='play')await p.keyboard.down(key);await p.waitForTimeout(1000);if(scenario.mode==='play')await p.keyboard.up(key);const now=await p.evaluate(()=>({n:window.__draws.frames,t:performance.now(),submitted:window.__cocoPerf?.snapshot()?.fps}));row.samples.push({seconds:(now.t-previous.t)/1000,frames:now.n-previous.n,fps:(now.n-previous.n)*1000/(now.t-previous.t),submitted:now.submitted});previous=now;save();}
 row.lost=await p.evaluate(()=>window.__draws.lost);row.actualTier=await p.evaluate(()=>window.__cocoArena?.renderer?.quality?.tier??document.querySelector('canvas').dataset.qualityTier);row.actual3D=await p.evaluate(()=>window.__cocoArena?.renderer?.is3D??null);const rates=row.samples.map(s=>s.fps).sort((a,b)=>a-b);row.median=rates[Math.floor(rates.length/2)];row.minimum=rates[0];row.completed=true;await p.screenshot({path:out+'/'+scenario.gpu+'-'+scenario.mode+'.png'});
 }catch(e){row.error=String(e);row.completed=false;}finally{await b?.close();row.conditions_end=conditions();save()}
}
report.passed=report.cases.every(r=>r.completed&&r.errors.length===0&&r.lost===0);save();
