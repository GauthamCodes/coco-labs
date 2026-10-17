// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Render token roles with redundant shapes, not experiment results. */
import {chromium} from 'playwright';
import {resolve} from 'node:path';
import {TOKENS} from '../src/ui/tokens.ts';
import {svgMatrix} from '../src/ui/colour_checks.ts';
const site=process.argv[2]??'http://localhost:4182/coco-labs/',out=resolve('../docs/v2/data/m5/screens/reference');
const b=await chromium.launch();
try{for(const theme of ['dark','light']){
 const p=await b.newPage({viewport:{width:1440,height:900}});await p.goto(site+'?reference=compare&view=arena&theme='+theme);await p.waitForSelector('[data-ready="true"]',{timeout:120000});await p.evaluate(()=>document.fonts.ready);
 if(theme==='light')await p.screenshot({path:resolve(out,'desktop-compare-light.png'),scale:'css'});
 await p.evaluate(({palette,theme})=>{
 const root=document.querySelector('#root');root.innerHTML='';const main=document.createElement('main');main.style.cssText='padding:48px;background:var(--bg);color:var(--fg);height:100dvh';
 const h=document.createElement('h1');h.textContent='Computation · '+theme;main.append(h);const note=document.createElement('p');note.textContent='Design swatches, not experiment results. Truth is an outline; uncertainty is translucent.';main.append(note);
 const grid=document.createElement('div');grid.style.cssText='display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:48px';
 for(const [key,label]of [['frontier','Frontier'],['closed','Expanded'],['path','Planned path'],['rejected','Rejected'],['particles','Uncertainty'],['truth','Ground truth']]){
 const card=document.createElement('section');card.style.cssText='background:var(--panel);padding:24px;border:1px solid var(--line);border-radius:12px';const heading=document.createElement('h2');heading.textContent=label;card.append(heading);
 const area=document.createElement('div');area.style.cssText='background:'+palette.free+';height:120px;display:grid;place-items:center';const glyph=document.createElement('i');glyph.style.cssText='display:block;width:60px;height:60px;background:'+palette[key];
 if(key==='path')glyph.style.height='6px';if(key==='rejected')glyph.style.clipPath='polygon(0 15%,15% 0,50% 35%,85% 0,100% 15%,65% 50%,100% 85%,85% 100%,50% 65%,15% 100%,0 85%,35% 50%)';
 if(key==='particles'){glyph.style.borderRadius='50%';glyph.style.opacity=String(palette.particlesAlpha);}if(key==='truth'){glyph.style.background='transparent';glyph.style.border='3px dashed '+palette.truth;glyph.style.borderRadius='50%';}
 area.append(glyph);card.append(area);const text=document.createElement('p');text.textContent=palette[key];card.append(text);grid.append(card);
 }main.append(grid);root.append(main);
 },{palette:TOKENS.computation[theme],theme});
 for(const kind of ['normal','protanopia','deuteranopia']){
 if(kind!=='normal')await p.evaluate(matrix=>{document.querySelector('#cvd-simulation')?.remove();const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.id='cvd-simulation';svg.setAttribute('style','position:absolute;width:0;height:0');svg.innerHTML='<filter id="cvd" color-interpolation-filters="linearRGB"><feColorMatrix type="matrix" values="'+matrix+'"/></filter>';document.body.append(svg);document.querySelector('#root').style.filter='url(#cvd)';},svgMatrix(kind));
 await p.screenshot({path:resolve(out,'palette-'+theme+'-'+kind+'.png'),scale:'css'});
 }await p.close();
}}finally{await b.close();}
