// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import type {ArenaSceneModel} from '../arena/sceneCore';
import {writePref} from '../prefs';
import {TOKENS} from '../ui/tokens';
import {activeTheme} from '../ui/theme';

export function PlayTutorial({model:m,vision,onDone}:{model:ArenaSceneModel;vision:number;onDone:()=>void}){
 const [step,setStep]=useState(0),marker=useRef<[number,number]|null>(null);
 const finish=()=>{writePref('tutorial',true);onDone();};
 useEffect(()=>{
  if(step!==0||!m.world||!m.r.current||!m.occupancy.current)return;
  const w=m.world,occupancy=m.occupancy.current;
  const [x,y]=w.start;
  // Pick a free, nearby marker in the actual known map; this changes no model goal.
  const point=[[x+1,y],[x,y+1],[x-1,y],[x,y-1]].find(([px,py])=>{
   const col=Math.floor((px-w.origin[0])/w.resolution),row=w.height-1-Math.floor((py-w.origin[1])/w.resolution);
   return row>=0&&row<w.height&&col>=0&&col<w.width&&!occupancy[row*w.width+col];
  });
  if(!point)return;
  marker.current=point as [number,number];
  const ring=new THREE.Mesh(new THREE.RingGeometry(.22,.28,48),new THREE.MeshBasicMaterial({color:TOKENS.computation[activeTheme()].goal,transparent:true,opacity:.9,side:THREE.DoubleSide,depthWrite:false}));
  ring.position.set(point[0],point[1],m.r.current.liftAt(point[0],point[1])+.055);
  m.r.current.scene.add(ring);
  const timer=setInterval(()=>{ring.visible=step===0;},100);
  return()=>{clearInterval(timer);ring.removeFromParent();ring.geometry.dispose();ring.material.dispose();};
 },[m.world,step]);
 useEffect(()=>{
  if(step===0&&m.mode==='live'&&m.tick&&marker.current&&Math.hypot(m.tick.pose[0]-marker.current[0],m.tick.pose[1]-marker.current[1])<.35)setStep(1);
  if(step===1&&m.log.current.some(row=>row.kind==='goal')&&m.plan)setStep(2);
  if(step===2&&vision>0)finish();
 },[m.tick,m.plan,vision,step]);
 return <section className="play-tutorial night-glass" aria-label="First drive tutorial"><span className="night-eyebrow">FIRST DRIVE · ABOUT 20 SECONDS</span><p>{['Drive to the glowing ring with WASD, arrows or the thumb stick.','Click or tap the floor for a goal. Watch the planner take over.','Press X or tap Vision to see what COCO computes.'][step]}</p><small>Skip in Settings · Esc on a keyboard</small></section>;
}
