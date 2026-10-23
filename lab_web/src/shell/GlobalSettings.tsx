// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {lazy,Suspense,useEffect,useState} from 'react';
import {SETTINGS_OPEN} from './settings_events';
const SettingsDrawer=lazy(()=>import('./SettingsDrawer'));
export function GlobalSettings(){
 const [open,setOpen]=useState(false);
 useEffect(()=>{
  const show=()=>setOpen(true),close=()=>setOpen(false);
  window.addEventListener(SETTINGS_OPEN,show);
  window.addEventListener('popstate',close);
  return()=>{window.removeEventListener(SETTINGS_OPEN,show);window.removeEventListener('popstate',close);};
 },[]);
 return open?<Suspense fallback={null}><SettingsDrawer onClose={()=>setOpen(false)}/></Suspense>:null;
}
