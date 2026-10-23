// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {useEffect,useRef} from 'react';
import {TOKENS} from '../ui/tokens';
import {activeTheme} from '../ui/theme';
import type {World} from '../arena/protocol';
export function PathReview({path,ghost,map}:{path:[number,number][];ghost?:[number,number][];map?:{world:World;occupancy:Uint8Array}}){
 const canvas=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{
  const ctx=canvas.current?.getContext('2d');if(!ctx||!path.length)return;
  const p=TOKENS.computation[activeTheme()],points=[...path,...(ghost??[])];
  const xs=points.map(x=>x[0]),ys=points.map(x=>x[1]);
  const x0=map?.world.origin[0]??Math.min(...xs),y0=map?.world.origin[1]??Math.min(...ys),width=map?map.world.width*map.world.resolution:Math.max(1,Math.max(...xs)-x0),height=map?map.world.height*map.world.resolution:Math.max(1,Math.max(...ys)-y0);
  const scale=Math.min(352/width,192/height),ox=24+(352-width*scale)/2,oy=24+(192-height*scale)/2;
  ctx.fillStyle=p.free;ctx.fillRect(0,0,400,240);
  if(map){const {world:w,occupancy}=map;ctx.fillStyle=p.occupied;for(let row=0;row<w.height;row++)for(let col=0;col<w.width;col++)if(occupancy[row*w.width+col])ctx.fillRect(ox+col*w.resolution*scale,oy+row*w.resolution*scale,Math.max(1,w.resolution*scale),Math.max(1,w.resolution*scale));}
  const draw=(track:[number,number][],color:string,dashed:boolean)=>{
   ctx.strokeStyle=color;ctx.lineWidth=3;ctx.setLineDash(dashed?[7,5]:[]);ctx.beginPath();
   track.forEach(([x,y],i)=>{const px=ox+(x-x0)*scale,py=240-oy-(y-y0)*scale;if(i)ctx.lineTo(px,py);else ctx.moveTo(px,py);});ctx.stroke();
  };
  if(ghost)draw(ghost,p.truth,true);draw(path,p.path,false);
 },[path,ghost,map]);
 return <figure className="score-path"><canvas width={400} height={240} ref={canvas} aria-label="Recorded route against the reference ghost"/><figcaption>{map?'Reference map · ':''}Your path · pink{ghost?' / reference ghost · dashed green':''}</figcaption></figure>;
}
