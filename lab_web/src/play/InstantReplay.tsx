// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {trapDialogTab} from '../ui/dialog';
import {useEffect,useRef} from 'react';
import type {ArenaSession} from '../arena/session';
import {Timeline} from '../arena/Timeline';
/** Seek the existing world/computation timeline; no second simulation or hash clock. */
export function InstantReplay({session,onClose}:{session:ArenaSession;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{
  dialog.current?.showModal();const original=session.viewTick,head=session.shownTick?.tick??session.head,wasPlaying=session.playing;
  const start=Math.max(session.history[0]?.tick??0,head-Math.round(10/session.dt));
  session.playing=false;session.seekTick(start);
  const began=performance.now();
  const timer=setInterval(()=>{
   const tick=Math.min(head,start+Math.floor((performance.now()-began)/1000/session.dt));
   session.seekTick(tick);if(tick===head){session.playing=false;clearInterval(timer);}
  },50);
  return()=>{clearInterval(timer);if(original===null)session.goLive();else session.seekTick(original);session.playing=wasPlaying;};
 },[session]);
 return <dialog className="instant-replay" onKeyDown={trapDialogTab} ref={dialog} aria-label="Instant replay" onClose={onClose}><header><strong>Last 10 seconds</strong><button autoFocus onClick={()=>dialog.current?.close()}>Back to Play</button></header><Timeline session={session}/></dialog>;
}
