// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {useEffect,useRef,useState} from 'react';
import {ACTIONS,keyLabel,loadBindings,rebind,resetBindings,type Action} from '../arena/controls';
import {TIER_CHOICES,type TierChoice} from '../arena/render/quality';
import {isBool,readPref,reducedMotion,writePref} from '../prefs';
import {activeTheme,applyTheme,applyMotion} from '../ui/theme';
import {notifySettings} from './settings_events';
import './shell.css';
import {trapDialogTab} from '../ui/dialog';
export default function SettingsDrawer({onClose}:{onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [quality,setQuality]=useState(()=>readPref<TierChoice>('quality','auto',(v):v is TierChoice=>TIER_CHOICES.includes(v as TierChoice)));
 const [walls,setWalls]=useState(()=>readPref('walls',true,isBool));
 const [phone120,setPhone120]=useState(()=>readPref('phone120',false,isBool));
 const [haptics,setHaptics]=useState(()=>readPref('haptics',true,isBool));
 const [sound,setSound]=useState(()=>readPref('sound',false,isBool));
 const [motion,setMotion]=useState(reducedMotion);
 const [theme,setTheme]=useState(activeTheme);
 const [bindings,setBindings]=useState(loadBindings),[waiting,setWaiting]=useState<Action|null>(null);
 useEffect(()=>{dialog.current?.showModal();},[]);
 useEffect(()=>{
  if(!waiting)return;
  const key=(event:KeyboardEvent)=>{event.preventDefault();event.stopImmediatePropagation();if(event.code!=='Escape'){setBindings(rebind(bindings,waiting,event.code));notifySettings();}setWaiting(null);};
  window.addEventListener('keydown',key,{capture:true});return()=>window.removeEventListener('keydown',key,{capture:true});
 },[waiting,bindings]);
 return <dialog className="settings-drawer" ref={dialog} aria-labelledby="settings-title" onClose={onClose} data-testid="settings-drawer" onKeyDown={trapDialogTab}>
  <header><h1 id="settings-title">Settings</h1><button autoFocus onClick={()=>dialog.current?.close()} aria-label="Close settings">Close</button></header>
  <nav aria-label="App modes"><a href={`${import.meta.env.BASE_URL}`}>Title</a> · <a href={`${import.meta.env.BASE_URL}?view=play`}>Play</a> · <a href={`${import.meta.env.BASE_URL}?view=compare`}>Compare</a> · <a href={`${import.meta.env.BASE_URL}?view=research`}>Research</a></nav>
  {document.querySelector('.coco-play')&&<button onClick={()=>{dialog.current?.close();window.dispatchEvent(new Event('coco:play-menu'));}}>Game menu and inspection</button>}
  {document.querySelector('.play-tutorial')&&<button onClick={()=>{dialog.current?.close();window.dispatchEvent(new Event('coco:skip-tutorial'));}}>Skip tutorial</button>}
  <p className="muted">Saved on this device.</p>
  {document.querySelector('.coco-play')&&<button onPointerDown={()=>window.dispatchEvent(new Event('coco:stop'))} onClick={event=>{if(event.detail===0)window.dispatchEvent(new Event('coco:stop'));}}>STOP</button>}
  <label>Quality<select aria-label="Quality" value={quality} onChange={e=>{const value=e.target.value as TierChoice;setQuality(value);writePref('quality',value);notifySettings();}}>{TIER_CHOICES.map(value=><option key={value} value={value}>{value==='auto'?'Automatic (measured frame time)':value}</option>)}</select></label>
  <label>Wall display<select aria-label="Wall display" value={walls?'half':'full'} onChange={e=>{const value=e.target.value==='half';setWalls(value);writePref('walls',value);notifySettings();}}><option value="half">Half height</option><option value="full">Full height</option></select></label>
  <label>Theme<select aria-label="Theme" value={theme} onChange={e=>{const value=e.target.value==='light'?'light':'dark';setTheme(value);applyTheme(value,true);notifySettings();}}><option value="dark">Night Shift · dark</option><option value="light">Daylight · light</option></select></label>
  <label className="settings-check"><input type="checkbox" checked={sound} onChange={e=>{setSound(e.target.checked);writePref('sound',e.target.checked);notifySettings();}}/>Motor sound</label>
  <label className="settings-check"><input type="checkbox" checked={motion} onChange={e=>{setMotion(e.target.checked);writePref('motion',e.target.checked);applyMotion();notifySettings();}}/>Reduced motion</label>
  <label className="settings-check"><input type="checkbox" checked={phone120} onChange={e=>{setPhone120(e.target.checked);writePref('phone120',e.target.checked);notifySettings();}}/>Allow 120 fps on phones (uses more power)</label>
  <label className="settings-check"><input type="checkbox" checked={haptics} onChange={e=>{setHaptics(e.target.checked);writePref('haptics',e.target.checked);notifySettings();}}/>Phone haptics</label>
  <h2>Key bindings</h2>
  <table><tbody>{ACTIONS.map(action=><tr key={action.id}><th scope="row">{action.label}</th><td>{bindings[action.id].map(keyLabel).join(' / ')}</td><td><button aria-pressed={waiting===action.id} onClick={()=>setWaiting(action.id)} aria-label={`Change ${action.label}`}>{waiting===action.id?'Press a key…':'Change'}</button></td></tr>)}</tbody></table>
  <button onClick={()=>{setBindings(resetBindings());notifySettings();}}>Restore default keys</button>
 </dialog>;
}
