// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Regression: real custom-shader pixels must agree with the CSS/token sRGB. */
import {chromium} from 'playwright';
import {writeFileSync} from 'node:fs';
import {TOKENS} from '../src/ui/tokens.ts';
import {conditions} from './perf/conditions.mjs';
const start=conditions(),site=process.argv[2],out=process.argv[3],rows=[];
const browser=await chromium.launch();
try{for(const theme of ['dark','light']){
 const p=await browser.newPage({viewport:{width:1000,height:900}}),errors=[];
 p.on('pageerror',e=>errors.push(e.message));p.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await p.goto(site+'?view=arena&camera=topdown&theme='+theme);
 await p.waitForFunction(()=>window.__cocoArena?.session()?.shownTick,null,{timeout:120000});
 const result=await p.evaluate(expected=>{
  const r=window.__cocoArena.renderer;
  r.setLayers({occupancy:true,closed:false,heatmap:false,path:false,frontier:false,lidar:false,robot:false,footprint:false,truth:false});
  r.renderer.render(r.scene,r.camera);
  const gl=r.renderer.getContext(),width=gl.drawingBufferWidth,height=gl.drawingBufferHeight,pixels=new Uint8Array(width*height*4);
  gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
  const target=[1,3,5].map(i=>parseInt(expected.slice(i,i+2),16));let matching=0;
  for(let i=0;i<pixels.length;i+=4)if(target.every((value,c)=>Math.abs(value-pixels[i+c])<=1))matching++;
  return {expected,target,width,height,matching,total:width*height,pass:matching>width*height/10};
 },TOKENS.computation[theme].free);
 rows.push({theme,...result,errors});await p.close();
}}finally{await browser.close();writeFileSync(out,JSON.stringify({conditions:{start,end:conditions()},threshold:'At least 10% of this known mostly-free scene must match the free-cell token within one sRGB channel value; not a performance measurement',rows},null,1)+'\n');}
if(rows.some(r=>!r.pass||r.errors.length))throw Error('Rendered custom-shader colour regression');
console.log('Both themes: rendered free-cell pixels match their sRGB tokens.');
