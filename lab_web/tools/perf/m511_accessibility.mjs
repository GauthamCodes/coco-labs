// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();
const [site,out]=process.argv.slice(2);mkdirSync(out,{recursive:true});const report={pages:[],errors:[]};const b=await chromium.launch({args:['--use-angle=gl-egl','--ignore-gpu-blocklist']});
const audit=()=>{
 const rgb=s=>{const n=s.match(/[\d.]+/g)?.map(Number)??[0,0,0,0];const scale=s.startsWith('color(srgb')?255:1;return[n[0]*scale,n[1]*scale,n[2]*scale,n[3]??1]},blend=(a,b,alpha=a[3])=>[0,1,2].map(i=>a[i]*alpha+b[i]*(1-alpha)),lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0),ratio=(a,b)=>{const x=lum(a),y=lum(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'&&!e.closest('dialog:not([open])')};
 const failures=[],checked=[],walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let text;
 while(text=walker.nextNode()){
  const e=text.parentElement;if(!e||!text.textContent.trim()||e.closest('script,style,svg')||!visible(e)||e.closest(':disabled'))continue;
  const style=getComputedStyle(e),layers=[];let opacity=1;
  for(let n=e;n;n=n.parentElement){const s=getComputedStyle(n);opacity*=Number(s.opacity);layers.push(rgb(s.backgroundColor))}
  let bg=[255,255,255];for(const layer of layers.reverse())bg=blend(layer,bg);
  const fg=rgb(style.color),effective=blend(fg,bg,fg[3]*opacity),contrast=ratio(effective,bg),size=parseFloat(style.fontSize),large=size>=24||(size>=18.66&&Number(style.fontWeight)>=700),minimum=large?3:4.5;
  const item={text:text.textContent.trim().slice(0,90),tag:e.tagName,foreground:style.color,background:bg,contrast,minimum,size};checked.push(item);if(contrast+0.01<minimum)failures.push(item);
 }
 const targets=[...document.querySelectorAll('button,a[href],input,select,textarea,canvas[tabindex],[role=application]')].filter(e=>visible(e)&&!e.disabled&&!e.closest(':disabled'));
 return{checked:checked.length,failures,nonFocusable:targets.filter(e=>e.tabIndex<0).map(e=>e.outerHTML.slice(0,150)),controls:targets.length};
};
try{for(const theme of ['dark','light'])for(const view of ['', '?view=play','?view=arena&world=v2','?view=compare','?view=research','?view=about']){
 const p=await b.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});p.on('pageerror',e=>report.errors.push(String(e)));await p.goto(site+view+(view?'&':'?')+'theme='+theme);
 await p.waitForSelector(view.includes('research')?'.recording-card':view.includes('compare')?'[data-testid="compare-workspace"][data-ready="true"]':view.includes('arena')?'.night-vision':view.includes('play')?'.game-card':view.includes('about')?'.about-page':'[data-scene-ready="true"]',{timeout:120000});
 const result=await p.evaluate(audit);report.pages.push({theme,view,...result,reducedMotion:await p.evaluate(()=>document.documentElement.dataset.motion)});
 if(view.includes('arena')){await p.keyboard.press('Escape');const cv=p.getByTestId('arena-canvas');await cv.focus();const seen=[];for(let i=0;i<12;i++){await p.keyboard.press('Tab');seen.push(await p.evaluate(()=>document.activeElement?.getAttribute('aria-label')||document.activeElement?.textContent?.trim().slice(0,40)||document.activeElement?.tagName))}report.pages.at(-1).tabs=seen;}
 await p.close();
}
 report.passed=report.errors.length===0&&report.pages.every(r=>r.failures.length===0&&r.nonFocusable.length===0&&r.reducedMotion==='reduced');
}catch(e){report.error=String(e);report.passed=false;process.exitCode=1}finally{await b.close();writeFileSync(out+'/checks.json',JSON.stringify({ ...report, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1)+'\n')}
