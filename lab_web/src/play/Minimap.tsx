// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {useEffect,useRef} from 'react';
import type {ArenaSceneModel} from '../arena/sceneCore';
import {TOKENS} from '../ui/tokens';
import {activeTheme} from '../ui/theme';

/** The robot's prior map, or its emitted mapping keyframe when mapping is active. */
export function Minimap({model}:{model:ArenaSceneModel}){
 const canvas=useRef<HTMLCanvasElement>(null);
 const cache=useRef<{key:unknown;header:unknown;theme:string;image:HTMLCanvasElement}|null>(null);
 const theme=activeTheme();
 const head=model.session?.headers.get('coco.map.grid.header.v1');
 const snap=model.session?.families.latest('coco.map.grid.snapshot.v1',model.tick?.tick??0);
 useEffect(()=>{
  if(!model.world||!canvas.current||!model.occupancy.current)return;
  const world=model.world,p=TOKENS.computation[theme];
  const width=head?Number(head.width):world.width,height=head?Number(head.height):world.height;
  const resolution=head?Number(head.resolution):world.resolution;
  const origin=head?[Number(head.origin_x),Number(head.origin_y)]:world.origin;
  const values=head?snap?.columns.logodds_f32 as ArrayLike<number>|undefined:model.occupancy.current;
  const key=head?snap:model.occupancy.current;
  if(!cache.current||cache.current.key!==key||cache.current.header!==head||cache.current.theme!==theme){
   const image=document.createElement('canvas');image.width=width;image.height=height;
   const context=image.getContext('2d')!,pixels=context.createImageData(width,height);
   const rgb=(hex:string)=>[1,3,5].map(at=>parseInt(hex.slice(at,at+2),16));
   const free=rgb(p.free),occupied=rgb(p.occupied),unknown=rgb(p.unknown);
   for(let row=0;row<height;row++)for(let col=0;col<width;col++){
    const index=row*width+col,source=(head?height-1-row:row)*width+col;
    const value=values?.[source]??0;
    const probability=head?1/(1+Math.exp(-value)):value?1:0;
    const color=head&&value===0?unknown:free.map((channel,i)=>Math.round(channel+(occupied[i]-channel)*probability));
    pixels.data.set([...color,255],index*4);
   }
   context.putImageData(pixels,0,0);cache.current={key,header:head,theme,image};
  }
  const context=canvas.current.getContext('2d')!,size=192;
  const scale=Math.min(size/width,size/height),ox=(size-width*scale)/2,oy=(size-height*scale)/2;
  context.fillStyle=p.free;context.fillRect(0,0,size,size);context.imageSmoothingEnabled=false;
  context.drawImage(cache.current.image,ox,oy,width*scale,height*scale);
  const pose=model.tick?.pose;
  if(pose){
   const x=ox+(pose[0]-origin[0])/resolution*scale,y=oy+(height-(pose[1]-origin[1])/resolution)*scale;
   context.fillStyle=p.robot;context.beginPath();context.arc(x,y,4,0,Math.PI*2);context.fill();
   context.strokeStyle=p.path;context.lineWidth=2;context.beginPath();context.moveTo(x,y);context.lineTo(x+Math.cos(pose[2])*9,y-Math.sin(pose[2])*9);context.stroke();
  }
 },[model.world,model.tick,head,snap,theme]);
 return <figure className="night-minimap"><canvas ref={canvas} width={192} height={192} aria-label={head?"COCO's built occupancy map":"COCO's known planning occupancy map"}/><figcaption>{head?'BUILT MAP':'KNOWN MAP'}</figcaption></figure>;
}
