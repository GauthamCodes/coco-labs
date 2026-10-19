// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {trapDialogTab} from '../ui/dialog';
import {useEffect,useRef,useState} from 'react';
import {Camera,Hand,Navigation2,Route,ScanEye,Settings,Square} from 'lucide-react';
import type {ArenaSceneModel} from '../arena/sceneCore';
import {ArenaSceneView} from '../arena/ArenaSceneView';
import {Joystick} from '../arena/Joystick';
import {ArenaPlayPanel} from './ArenaPlayPanel';
import {Minimap} from './Minimap';
import {PlayTutorial} from './PlayTutorial';
import {InstantReplay} from './InstantReplay';
import {PerfOverlay} from '../arena/PerfOverlay';
import {isBool,readPref,writePref} from '../prefs';
import {openSettings} from '../shell/settings_events';
import {enterPhonePlay,leavePhonePlay,isPhone,phoneHaptic} from './phone';
import {EvidenceBadge} from '../ui/ModeNav';
import '../ui/reference/reference.css';
import './hud.css';

export function PlayHUD({model:m}:{model:ArenaSceneModel}){
 const phone=isPhone();
 const menu=useRef<HTMLDialogElement>(null);
 const [controlsTarget,setControlsTarget]=useState<HTMLDivElement|null>(null);
 const [vision,setVision]=useState(0);
 const [costmapEpoch,setCostmapEpoch]=useState(0);
 const [tutorial,setTutorial]=useState(()=>!m.playOn&&!m.params.has('replay')&&!m.params.has('run')&&!readPref('tutorial',false,isBool));
 const [replaying,setReplaying]=useState(false);
 const [intro,setIntro]=useState(true);
 useEffect(()=>{const timer=setTimeout(()=>setIntro(false),5000);return()=>clearTimeout(timer);},[]);
 useEffect(()=>{if(m.qualityNote)setToast(m.qualityNote);},[m.qualityNote]);
 const [toast,setToast]=useState('');
 const phases=['Off','Scan area','Planner frontier and heatmap','Costmap','Localization particles'];
 const previous=useRef({blocked:false,grasp:''});
 useEffect(()=>{
  const ready=(event:Event)=>{setCostmapEpoch(v=>v+1);setToast(`Costmap snapshot · tick ${(event as CustomEvent<number>).detail}`);};
  window.addEventListener('coco:costmap-ready',ready);return()=>window.removeEventListener('coco:costmap-ready',ready);
 },[]);
 useEffect(()=>{
  if(vision!==3)return;
  if(m.mode==='live'&&m.liveReady&&m.session?.viewTick===null)m.client.current?.requestCostmap();
  else setToast('Costmap · static map; no cost snapshot recorded at this tick');
 },[vision,m.mode,m.liveReady]);
 useEffect(()=>{if(vision===4&&!m.session?.families.latest('coco.localise.particles.set.v1',m.tick?.tick??0))setToast('Localization particles · no active estimator');},[vision]);
 useEffect(()=>{
  document.documentElement.classList.add('playing-coco');
  return()=>{document.documentElement.classList.remove('playing-coco');void leavePhonePlay();};
 },[]);
 useEffect(()=>{const skip=()=>{writePref('tutorial',true);setTutorial(false);};const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&!document.querySelector('dialog[open]'))skip();};window.addEventListener('coco:skip-tutorial',skip);window.addEventListener('keydown',escape);return()=>{window.removeEventListener('coco:skip-tutorial',skip);window.removeEventListener('keydown',escape);};},[]);
 useEffect(()=>{const open=()=>menu.current?.showModal();window.addEventListener('coco:play-menu',open);return()=>window.removeEventListener('coco:play-menu',open);},[]);
 useEffect(()=>{
  const cycle=()=>setVision(v=>(v+1)%5);
  window.addEventListener('coco:robot-vision',cycle);
  return()=>window.removeEventListener('coco:robot-vision',cycle);
 },[]);
 useEffect(()=>{if(m.helpOpen){openSettings();m.setHelpOpen(false);}},[m.helpOpen]);
 useEffect(()=>{if(!toast)return;const t=setTimeout(()=>setToast(''),3200);return()=>clearTimeout(t);},[toast]);
 useEffect(()=>{
  const renderer=m.r.current;
  if(renderer?.three?.ready)renderer.three.setFollowFraming(5.2,40*Math.PI/180);
  renderer?.setScanArea(true);
  renderer?.setCostmapVisible(vision===3&&renderer.costmapTick!==null&&(m.tick?.tick??0)>=renderer.costmapTick);
  renderer?.setLayers({lidar:vision===1,frontier:vision===2,closed:vision===2,heatmap:vision===2,path:vision===2,footprint:false,truth:false,occupancy:!renderer?.is3D||vision===3});
  // Lens layers only display model-emitted data, never inferred particles.
  m.setLensOn(on=>{
   const next=Object.fromEntries(Object.keys(on).map(id=>[id,id==='particles'&&vision===4]));
   return Object.keys(next).every(id=>next[id]===on[id])?on:next;
  });
 },[vision,m.tick,m.tierNow,m.camera,costmapEpoch]);
 useEffect(()=>{
  if(!m.tick)return;
  const grasp=m.tick.grasp?.phase??'';
  if(m.tick.blocked&&!previous.current.blocked)phoneHaptic('contact');
  if(grasp!==previous.current.grasp&&grasp){if(grasp==='idle'&&previous.current.grasp==='release')phoneHaptic('delivery');else if(grasp==='pick')phoneHaptic('grasp');}
  previous.current={blocked:!!m.tick.blocked,grasp};
 },[m.tick]);
 const action=(kind:'grasp'|'autonomy')=>{
  if(m.raceOn){setToast('Race controls are locked: drive with teleop and STOP only.');return;}
  if(m.latchedRef.current)return;m.takeOver();m.queue.current.push({kind});
 };
 const stop=()=>{m.takeOver();m.queue.current.push({kind:'stop'});m.latchedRef.current=true;m.setLatched(true);};
 const release=()=>{m.latchedRef.current=false;m.setLatched(false);};
 useEffect(()=>{
  window.addEventListener('coco:stop',stop);
  return()=>window.removeEventListener('coco:stop',stop);
 });
 const elapsed=m.tick?.t_world??0;
 const source=m.tick?.source==='teleop'?'YOU':m.tick?.source==='planner'?'PLANNER':m.tick?.source==='mission'?'ASSIST':m.tick?.source==='stop'?'STOP':m.tick?.source==='idle'?'IDLE':'—';
 return <main className={`night-play coco-play ${phone?'night-phone':''}`} data-testid="arena" onPointerDown={event=>{if((event.target as HTMLElement).closest('button,a,dialog')&&!(event.target as HTMLElement).closest('.night-actions'))return;if(phone&&!document.fullscreenElement)void enterPhonePlay();}}>
  <div className="night-play-world"><canvas ref={m.canvas} className="arena-canvas night-game-canvas" data-testid="arena-canvas" tabIndex={0} role="application" aria-label="Click the floor for a goal; drive with WASD"/></div>
  <section className="night-objective night-glass"><span className="night-eyebrow">{m.playParam?.replaceAll('-',' ')??'FREE ROAM'}</span><strong>{m.raceOn?'Drive to the flag.':m.lastTick.current?.arrived?'Goal reached.':'Make your own path.'}</strong><span className="night-timer">{Math.floor(elapsed/60).toString().padStart(2,'0')}:{Math.floor(elapsed%60).toString().padStart(2,'0')}</span></section>
  <Minimap model={m}/>
  <button className="night-settings night-icon-button" aria-label="Settings" onClick={openSettings}><Settings size={20}/></button>
  <button className={`night-vision night-icon-button ${vision?'is-active':''}`} aria-label={`Robot vision (X): ${phases[vision]}`} onClick={()=>{setVision(v=>(v+1)%5);setToast(`Robot vision: ${phases[(vision+1)%5]}`);}}><ScanEye size={20}/><span>Vision</span></button>
  <section className="night-drive-readout night-glass"><strong>{m.tick?Math.abs(m.tick.v).toFixed(2):'—'} <span>m/s</span></strong><span className="night-source">{source}</span><div className="night-wheel-bars">{[0,1].map(side=><div key={side} className="night-wheel-track"><i style={{width:`${Math.min(100,Math.abs(m.tick?.wheels?.[side]??0)/m.fullWheel.current*100)}%`}}/></div>)}</div></section>
  {phone&&<div className="night-joystick"><Joystick onChange={m.onJoystick}/></div>}
  <div className="night-actions"><button className="night-action night-stop" data-testid={m.latched?'hud-release':'hud-stop'} onClick={m.latched?release:stop}><Square size={22} fill="currentColor"/><span>{m.latched?'Release':'STOP'}</span></button><button className="night-action night-grasp" data-testid="hud-context" onClick={()=>action('grasp')} aria-disabled={m.raceOn||m.latched}><Hand size={21}/><span>Grasp</span></button><button className="night-action night-auto" data-testid="hud-autonomy" onClick={()=>action('autonomy')} aria-disabled={m.raceOn||m.latched}><Route size={21}/><span>Auto</span></button><button className="night-action night-camera" onClick={()=>m.chooseCamera('next')}><Camera size={21}/><span>Camera</span></button></div>
  <div className="night-play-badge"><EvidenceBadge evidence={m.evidence}/>{m.converted?.evidence==='STACK'&&!m.converted.pose3d&&<span className="play-planar-note" data-testid="planar-chip">Planar recording · no height or tilt recorded</span>}</div>
  {(toast||m.error||m.raceNotice)&&<p className="night-toast" role={m.error?'alert':'status'}>{m.error||toast||m.raceNotice}</p>}
  <p className={`play-model-status ${intro?'':'is-hidden'}`} data-testid="arena-mode" data-mode={m.mode}>{m.mode==='replay'?m.replay.status:m.mode==='attract'?'Recorded MODEL demo · drive or click to take control.':'Live MODEL · kinematic'}</p>
  {tutorial&&<PlayTutorial model={m} vision={vision} onDone={()=>setTutorial(false)}/>}
  <section className="night-rotate"><div><Navigation2 size={32}/><h2>Rotate your phone</h2><p>COCO has room to move in landscape.</p><button onClick={stop}>STOP</button><a href={`${import.meta.env.BASE_URL}?view=play`}>Back to games</a></div></section>
  <dialog className="play-tools" onKeyDown={trapDialogTab} ref={menu} aria-label="Game menu" onClick={event=>event.stopPropagation()}><header><h1>Play</h1><button onClick={stop}>STOP</button><button autoFocus onClick={()=>menu.current?.close()}>Resume</button></header><nav><a href={`${import.meta.env.BASE_URL}?view=play`}>Games</a><a href={`${import.meta.env.BASE_URL}?view=compare`}>Compare</a><a href={`${import.meta.env.BASE_URL}?view=research`}>Research</a></nav><div ref={setControlsTarget}/><p>WASD / arrows drive · Space stops · R releases · X cycles robot vision. H shows all remappable keys.</p><button onClick={()=>{menu.current?.close();setReplaying(true);}} disabled={!m.session?.history.length}>Replay last 10 seconds</button><ArenaSceneView model={m} controlsOnly/></dialog>
  {m.showPerf&&<PerfOverlay/>}
  {replaying&&m.session&&<InstantReplay session={m.session} onClose={()=>setReplaying(false)}/>}
  {m.playOn&&<div className="play-challenge-panel"><ArenaPlayPanel referenceMap={m.world&&m.occupancy.current?{world:m.world,occupancy:m.occupancy.current}:undefined} compact controlsTarget={controlsTarget} challenge={m.playParam!} levelId={m.playLevel!} live={m.playParam==='map-the-arena'||m.raceOn?m.client.current:null} liveReady={m.liveReady} onReplay={()=>setReplaying(true)} trajectory={()=>m.session?.history.map(t=>[t.pose[0],t.pose[1]])??[]} lastTick={()=>m.lastTick.current} shownTick={()=>m.session?.shownTick?.tick??null} log={()=>m.log.current} onGhost={(flag,ghost)=>m.r.current?.setRace(flag,ghost)}/></div>}
 </main>;
}
