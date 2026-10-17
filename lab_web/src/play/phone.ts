// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {isBool,readPref} from '../prefs';

export const isPhone = () => navigator.maxTouchPoints > 0 && matchMedia('(pointer: coarse)').matches;
export const phoneFrameCap = () => readPref('phone120',false,isBool) ? 120 : 60;

/** Call directly from a game-start gesture; denied APIs leave the rotate card usable. */
export async function enterPhonePlay() {
 if(!isPhone())return;
 try { if(!document.fullscreenElement) await document.documentElement.requestFullscreen({navigationUI:'hide'}); } catch { /* browser may refuse */ }
 try { await (screen.orientation as ScreenOrientation & {lock?:(mode:string)=>Promise<void>}).lock?.('landscape'); } catch { /* rotate card remains */ }
}
export function phoneHaptic(kind:'grasp'|'contact'|'delivery') {
 if(!isPhone()||!readPref('haptics',true,isBool))return;
 try { navigator.vibrate?.(kind==='delivery'?[12,35,18]:kind==='contact'?15:8); } catch { /* unsupported */ }
}

/** Dead zone preserves the full range outside it; no command before thumb travel. */
export function thumbTravel(dx:number,dy:number,deadZone=0.14):[number,number] {
 const length=Math.hypot(dx,dy);
 if(length<=deadZone)return [0,0];
 const gain=(Math.min(1,length)-deadZone)/(1-deadZone)/length;
 return [dx*gain,dy*gain];
}

/** Rendering only: the model's dt and hash clock are never rescaled. */
export class FrameGate {
 private next=0;
 reset(){this.next=0;}
 due(now:number,cap:number){
  const interval=1000/cap;
  if(this.next&&now+0.1<this.next)return false;
  // Preserve the phase on high-refresh displays, avoiding 60→40 fps quantisation.
  this.next=this.next&&now-this.next<interval?this.next+interval:now+interval;
  return true;
 }
}

/** Installed Play starts landscape; other purposes must be able to rotate again. */
export async function leavePhonePlay(){
 if(!isPhone())return;
 const q=new URLSearchParams(window.location.search),view=q.get('view');
 const anotherPlay=view==='play'||view==='arena'&&(q.has('play')||!['run','replay','casefile','lens','mission','compare'].some(key=>q.has(key)));
 if(anotherPlay)return;
 const orientation=screen.orientation as ScreenOrientation & {lock?:(mode:string)=>Promise<void>};
 try{if(orientation?.lock)await orientation.lock('any');else orientation?.unlock();}
 catch{try{orientation?.unlock();}catch{/* unsupported */}}
}
