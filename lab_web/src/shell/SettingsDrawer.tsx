// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {useEffect,useRef,useState} from 'react';
import {ACTIONS,keyLabel,loadBindings,rebind,resetBindings,type Action} from '../arena/controls';
import {TIER_CHOICES,type TierChoice} from '../arena/render/quality';
import {isBool,readPref,reducedMotion,writePref} from '../prefs';
import {activeTheme,applyTheme,applyMotion} from '../ui/theme';
import {notifySettings} from './settings_events';
import './shell.css';
export default function SettingsDrawer({onClose}:{onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [quality,setQuality]=useState(()=>readPref<TierChoice>('quality','auto',(v):v is TierChoice=>TIER_CHOICES.includes(v as TierChoice)));
 const [walls,setWalls]=useState(()=>readPref('walls',false,isBool));
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
 return <dialog className="settings-drawer" ref={dialog} aria-labelledby="settings-title" onClose={onClose} data-testid="settings-drawer" onKeyDown={event=>{
  if(event.key!=='Tab'||event.ctrlKey||event.metaKey||event.altKey)return;
  const controls=[...event.currentTarget.querySelectorAll<HTMLElement>('button,input,select,a[href],[tabindex]')].filter(element=>element.tabIndex>=0&&!element.hasAttribute('disabled')&&element.getClientRects().length>0);
  const index=controls.indexOf(document.activeElement as HTMLElement);
  if(event.shiftKey&&index<=0){event.preventDefault();controls.at(-1)?.focus();}
  else if(!event.shiftKey&&index===controls.length-1){event.preventDefault();controls[0]?.focus();}
 }}>
  <header><h1 id="settings-title">Settings</h1><button autoFocus onClick={()=>dialog.current?.close()} aria-label="Close settings">Close</button></header>
  <p className="muted">Saved on this device.</p>
  <label>Quality<select aria-label="Quality" value={quality} onChange={e=>{const value=e.target.value as TierChoice;setQuality(value);writePref('quality',value);notifySettings();}}>{TIER_CHOICES.map(value=><option key={value} value={value}>{value==='auto'?'Automatic (measured frame time)':value}</option>)}</select></label>
  <label>Wall display<select aria-label="Wall display" value={walls?'half':'full'} onChange={e=>{const value=e.target.value==='half';setWalls(value);writePref('walls',value);notifySettings();}}><option value="half">Lower walls</option><option value="full">Full height</option></select></label>
  <label>Theme<select aria-label="Theme" value={theme} onChange={e=>{const value=e.target.value==='light'?'light':'dark';setTheme(value);applyTheme(value,true);notifySettings();}}><option value="dark">Night Shift · dark</option><option value="light">Daylight · light</option></select></label>
  <label className="settings-check"><input type="checkbox" checked={sound} onChange={e=>{setSound(e.target.checked);writePref('sound',e.target.checked);notifySettings();}}/>Motor sound</label>
  <label className="settings-check"><input type="checkbox" checked={motion} onChange={e=>{setMotion(e.target.checked);writePref('motion',e.target.checked);applyMotion();notifySettings();}}/>Reduced motion</label>
  <h2>Key bindings</h2>
  <table><tbody>{ACTIONS.map(action=><tr key={action.id}><th scope="row">{action.label}</th><td>{bindings[action.id].map(keyLabel).join(' / ')}</td><td><button aria-pressed={waiting===action.id} onClick={()=>setWaiting(action.id)} aria-label={`Change ${action.label}`}>{waiting===action.id?'Press a key…':'Change'}</button></td></tr>)}</tbody></table>
  <button onClick={()=>{setBindings(resetBindings());notifySettings();}}>Restore default keys</button>
 </dialog>;
}
