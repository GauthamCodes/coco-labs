// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {describe,it,expect} from 'vitest';
import {FrameGate,thumbTravel} from '../src/play/phone';
describe('phone Play presentation',()=>{
 it('thumb dead zone is quiet, continuous and reaches the full command',()=>{
  expect(thumbTravel(.1,0)).toEqual([0,0]);
  expect(thumbTravel(.14,0)).toEqual([0,0]);
  expect(thumbTravel(.57,0)[0]).toBeCloseTo(.5);
  expect(thumbTravel(0,-1)).toEqual([0,-1]);
  expect(Math.hypot(...thumbTravel(1,1))).toBeCloseTo(1);
 });
 it('caps 120 Hz and 144 Hz callbacks at 60 rendered frames per second',()=>{
  for(const hz of [120,144]){
   const gate=new FrameGate();let drawn=0;
   for(let i=0;i<hz*10;i++)if(gate.due(i*1000/hz,60))drawn++;
   expect(drawn).toBe(600);
  }
 });
 it('allows 120 and resets after a hidden tab without a catch-up burst',()=>{
  const gate=new FrameGate();let drawn=0;
  for(let i=0;i<120;i++)if(gate.due(i*1000/120,120))drawn++;
  expect(drawn).toBe(120);gate.reset();
  expect(gate.due(100000,60)).toBe(true);
  expect(gate.due(100001,60)).toBe(false);
 });
});

import {vi,afterEach} from 'vitest';
import {enterPhonePlay,phoneHaptic,phoneFrameCap} from '../src/play/phone';
afterEach(()=>vi.unstubAllGlobals());
it('phone APIs fail silently and haptics respect the saved preference',async()=>{
 const vibrate=vi.fn();let muted=false;
 vi.stubGlobal('navigator',{maxTouchPoints:5,vibrate});
 vi.stubGlobal('matchMedia',()=>({matches:true}));
 vi.stubGlobal('window',{localStorage:{getItem:(key:string)=>key.endsWith('haptics')&&muted?'false':null}});
 vi.stubGlobal('document',{fullscreenElement:null,documentElement:{requestFullscreen:()=>Promise.reject(new Error('denied'))}});
 const lock=vi.fn(()=>Promise.reject(new Error('denied')));
 vi.stubGlobal('screen',{orientation:{lock}});
 await expect(enterPhonePlay()).resolves.toBeUndefined();expect(lock).toHaveBeenCalledWith('landscape');
 phoneHaptic('grasp');expect(vibrate).toHaveBeenCalledWith(8);
 muted=true;phoneHaptic('contact');expect(vibrate).toHaveBeenCalledTimes(1);
 expect(phoneFrameCap()).toBe(60);
});
it('a desktop never requests phone fullscreen or vibrates',async()=>{
 const vibrate=vi.fn();vi.stubGlobal('navigator',{maxTouchPoints:0,vibrate});
 await enterPhonePlay();phoneHaptic('delivery');expect(vibrate).not.toHaveBeenCalled();
});
it('leaving installed Play allows portrait elsewhere without undoing another game start',async()=>{
 const {leavePhonePlay}=await import('../src/play/phone');
 const lock=vi.fn(()=>Promise.resolve()),unlock=vi.fn();
 const location={search:'?view=compare'};
 vi.stubGlobal('navigator',{maxTouchPoints:5});vi.stubGlobal('matchMedia',()=>({matches:true}));
 vi.stubGlobal('window',{location});vi.stubGlobal('screen',{orientation:{lock,unlock}});
 await leavePhonePlay();expect(lock).toHaveBeenCalledWith('any');
 location.search='?view=arena&play=race-the-ghost&lens=plan';await leavePhonePlay();
 expect(lock).toHaveBeenCalledTimes(1);expect(unlock).not.toHaveBeenCalled();
});
